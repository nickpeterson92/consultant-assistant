"""Multi-agent orchestrator implementation using LangGraph.

This module serves as the central coordination hub for the multi-agent orchestrator system,
managing communication between users and specialized agents through the A2A protocol.
It implements enterprise patterns including circuit breakers, connection pooling, and
intelligent agent selection based on capabilities.

The orchestrator uses LangGraph's state management for conversation flow, memory
persistence, and background task execution. It coordinates with specialized agents
(Salesforce, Travel, HR, etc.) to fulfill user requests while maintaining conversation
context and extracting structured data for future reference.

Key responsibilities:
- Route user requests to appropriate specialized agents
- Maintain conversation state and memory across sessions
- Summarize long conversations to manage token usage
- Extract and persist structured data from agent responses
- Handle resilience patterns for distributed system reliability
"""

import os
import asyncio
import argparse
import time
from typing import Annotated, Dict, Any, List
import operator
from typing_extensions import TypedDict, Optional

from dotenv import load_dotenv

from src.utils.logging import get_logger, get_performance_tracker, get_cost_tracker, init_session_tracking

from trustcall import create_extractor

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.graph.message import RemoveMessage, add_messages

from langgraph.prebuilt import ToolNode, tools_condition

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import AzureChatOpenAI


from .agent_registry import AgentRegistry
from .agent_caller_tools import SalesforceAgentTool, GenericAgentTool, AgentRegistryTool
from src.utils.helpers import type_out, smart_preserve_messages
from src.utils.storage import get_async_store_adapter
from src.utils.storage.memory_schemas import SimpleMemory
from src.utils.logging import get_summary_logger
from .enhanced_sys_msg import orchestrator_chatbot_sys_msg, orchestrator_summary_sys_msg, get_fallback_summary
from src.utils.config import get_llm_config, get_conversation_config
from src.utils.sys_msg import TRUSTCALL_INSTRUCTION

import logging


# Disable LangSmith tracing to prevent circular reference errors in async context
os.environ["LANGCHAIN_TRACING_V2"] = "false"


from src.utils.logging import log_orchestrator_activity, log_cost_activity
from src.utils.events import (
    EventType, OrchestratorEvent, EventAnalyzer,
    create_user_message_event, create_ai_response_event, 
    create_tool_call_event, create_summary_triggered_event,
    create_memory_update_triggered_event
)



logger = logging.getLogger(__name__)

# Initialize global agent registry for service discovery
agent_registry = AgentRegistry()

def load_events_with_limit(state: dict, limit: Optional[int] = None) -> List[OrchestratorEvent]:
    """Load events from state with automatic limiting to prevent unbounded growth.
    
    Args:
        state: Orchestrator state containing events
        limit: Maximum number of recent events to keep (default: from config)
        
    Returns:
        List of OrchestratorEvent objects, limited to most recent 'limit' events
        
    Note: Default limit (50) is sufficient because:
    - Summary triggers every 5 user messages
    - Each interaction creates ~3-5 events (user, AI, tools)
    - We need at most 25 events to find the last trigger
    - 50 provides a safety margin
    """
    if limit is None:
        limit = get_conversation_config().max_event_history
        
    stored_events = state.get('events', [])
    if len(stored_events) > limit:
        # Keep only recent events
        stored_events = stored_events[-limit:]
        logger.info(f"Trimmed event history from {len(state.get('events', []))} to {limit} events")
    return [OrchestratorEvent.from_dict(e) for e in stored_events]

def create_azure_openai_chat():
    """Create and configure Azure OpenAI chat instance.
    
    Returns:
        AzureChatOpenAI: Configured LLM instance with settings from environment
        and global configuration including temperature, token limits, and timeouts.
    """
    llm_config = get_llm_config()
    return AzureChatOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=llm_config.azure_deployment,
        openai_api_version=llm_config.api_version,
        openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
        temperature=llm_config.temperature,
        max_tokens=llm_config.max_tokens,
        timeout=llm_config.timeout,
    )

def build_orchestrator_graph():
    """Build and compile the orchestrator LangGraph.
    
    Constructs the state graph that manages conversation flow, tool execution,
    and background tasks like summarization and memory extraction. The graph
    implements parallel processing for efficiency while maintaining conversation
    coherence.
        
    Returns:
        CompiledStateGraph: Compiled LangGraph with checkpointing and storage
    """
    
    load_dotenv()
    
    class OrchestratorState(TypedDict):
        """State schema for orchestrator graph.
        
        Maintains conversation context, memory, and tracks background operations.
        Uses annotations for LangGraph's state merging behaviors.
        """
        messages: Annotated[list, add_messages]
        summary: str  # Conversation summary for context compression
        memory: dict  # Structured memory of extracted entities
        events: Annotated[List[Dict[str, Any]], operator.add]  # Event history
        active_agents: List[str]
        last_agent_interaction: Dict[str, Any]
        background_operations: Annotated[List[str], operator.add]
        background_results: Annotated[Dict[str, Any], lambda x, y: {**x, **y}]
    
    memory = MemorySaver()
    # Configure persistent storage with resilience patterns
    memory_store = get_async_store_adapter(
        db_path="memory_store.db",
        use_async=False,  # Thread pool for reliability in mixed sync/async context
        max_workers=4,
        max_connections=10,
        enable_circuit_breaker=True
    )
    
    
    graph_builder = StateGraph(OrchestratorState)
    
    # Initialize orchestrator tools
    tools = [
        SalesforceAgentTool(agent_registry),
        GenericAgentTool(agent_registry),
        AgentRegistryTool(agent_registry)
    ]
    
    llm = create_azure_openai_chat()
    llm_with_tools = llm.bind_tools(tools)
    
    # Configure TrustCall for structured data extraction
    trustcall_extractor = create_extractor(
        llm,
        tools=[SimpleMemory],
        tool_choice="SimpleMemory",  # Explicit choice prevents tool conflicts
        enable_inserts=True
    )
    
    def invoke_llm(messages, use_tools=False, temperature=None):
        """Invoke LLM with optional tool binding.
        
        Azure OpenAI automatically caches prompts for efficiency.
        
        Args:
            messages: List of conversation messages
            use_tools: Whether to bind tools for function calling
            temperature: Override temperature for this call
            
        Returns:
            AI response message with optional tool calls
        """
        if temperature is not None:
            # Create a new LLM with custom temperature for this call
            llm_config = get_llm_config()
            temp_llm = AzureChatOpenAI(
                azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                azure_deployment=llm_config.azure_deployment,
                openai_api_version=llm_config.api_version,
                openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
                temperature=temperature,  # Use the override temperature
                max_tokens=llm_config.max_tokens,
                timeout=llm_config.timeout,
            )
            if use_tools:
                temp_llm = temp_llm.bind_tools(tools)
            return temp_llm.invoke(messages)
        
        if use_tools:
            return llm_with_tools.invoke(messages)
        else:
            return llm.invoke(messages)
    
    
    def get_orchestrator_system_message(state: OrchestratorState) -> str:
        """Generate dynamic system message with current context.
        
        Includes conversation summary, memory state, and available agent
        capabilities to guide the LLM's responses.
        
        Args:
            state: Current orchestrator state
            
        Returns:
            Formatted system message string
        """
        summary = state.get("summary", "No summary available")
        memory_val = state.get("memory", "No memory available")
        active_agents = state.get("active_agents", [])
        
        registry_stats = agent_registry.get_registry_stats()
        
        agent_context = f"""AVAILABLE SPECIALIZED AGENTS:
{', '.join(registry_stats['available_capabilities']) if registry_stats['available_capabilities'] else 'None currently available'}

CURRENTLY ACTIVE AGENTS: {', '.join(active_agents) if active_agents else 'None'}

ORCHESTRATOR TOOLS:
1. salesforce_agent: For Salesforce CRM operations (leads, accounts, opportunities, contacts, cases, tasks)
2. call_agent: For general agent calls (travel, expenses, HR, OCR, etc.)
3. manage_agents: To check agent status and capabilities"""
        
        return orchestrator_chatbot_sys_msg(summary, memory_val, agent_context)
    
    async def orchestrator(state: OrchestratorState, config: RunnableConfig):
        """Main conversation handler node.
        
        Processes user messages, invokes appropriate tools, manages memory,
        and coordinates background tasks. Implements sophisticated message
        handling to prevent duplicate responses and maintain conversation flow.
        
        Args:
            state: Current conversation state
            config: Runtime configuration including user ID and thread ID
            
        Returns:
            Dict with updated messages, memory, and turn count
        """
        try:
            msg_count = len(state.get('messages', []))
            last_msg = state.get('messages', [])[-1] if state.get('messages') else None
            
            # Track events instead of turns - with automatic limiting
            events = load_events_with_limit(state)
            
            # Log message types to track conversation flow
            if hasattr(last_msg, 'content'):
                from langchain_core.messages import HumanMessage, AIMessage
                if isinstance(last_msg, HumanMessage):
                    # Create user message event
                    event = create_user_message_event(
                        str(last_msg.content), 
                        msg_count
                    )
                    events.append(event)
                    log_orchestrator_activity("USER_REQUEST", 
                                             message=str(last_msg.content)[:200],
                                             message_count=msg_count,
                                             event_count=len(events))
                elif isinstance(last_msg, AIMessage):
                    log_orchestrator_activity("AI_RESPONSE_PROCESSING", 
                                             message=str(last_msg.content)[:200],
                                             message_count=msg_count,
                                             event_count=len(events))
                        
            # Load persistent memory using flat schema for simplicity
            user_id = config["configurable"].get("user_id", "default")
            namespace = ("memory", user_id)
            key = "SimpleMemory"
            existing_memory_data = memory_store.sync_get(namespace, key)
            
            if existing_memory_data:
                try:
                    validated_data = SimpleMemory(**existing_memory_data)
                    existing_memory = {"SimpleMemory": validated_data.model_dump()}
                    # Count total records for logging
                    total_records = (len(validated_data.accounts) + len(validated_data.contacts) + 
                                   len(validated_data.opportunities) + len(validated_data.cases) + 
                                   len(validated_data.tasks) + len(validated_data.leads))
                except Exception as e:
                    existing_memory = {"SimpleMemory": SimpleMemory().model_dump()}
            else:
                existing_memory = {"SimpleMemory": SimpleMemory().model_dump()}
            
            # Update state memory before system message generation
            state["memory"] = existing_memory
            
            # Load summary from persistent store if not in state
            summary = state.get("summary", "No summary available")
            if summary == "No summary available":
                # Try to load from store
                conv_config = get_conversation_config()
                user_id = config["configurable"].get("user_id", conv_config.default_user_id)
                namespace = (conv_config.memory_namespace_prefix, user_id)
                key = conv_config.summary_key
                
                try:
                    stored_summary = memory_store.sync_get(namespace, key)
                    if stored_summary and "summary" in stored_summary:
                        state["summary"] = stored_summary["summary"]
                        summary = stored_summary["summary"]
                        log_orchestrator_activity("SUMMARY_LOADED_FROM_STORE",
                                                summary_preview=summary[:200],
                                                timestamp=stored_summary.get("timestamp"))
                except Exception as e:
                    log_orchestrator_activity("SUMMARY_LOAD_ERROR", error=str(e))
            
            log_orchestrator_activity("SUMMARY_STATE_CHECK",
                                    operation="conversation_node_entry",
                                    has_summary=bool(summary and summary != "No summary available"),
                                    summary_length=len(summary) if summary else 0,
                                    summary_preview=summary[:200] if summary else "NO_SUMMARY")
            
            system_message = get_orchestrator_system_message(state)
            messages = [SystemMessage(content=system_message)] + state["messages"]
            
            # Check for recent tool results to inform response
            recent_tool_results = []
            for msg in reversed(state.get("messages", [])):
                if hasattr(msg, 'name') and getattr(msg, 'name', None) in ['salesforce_agent', 'call_agent']:
                    recent_tool_results.append(msg)
                    if len(recent_tool_results) >= 2:
                        break
            
            response = invoke_llm(messages, use_tools=True)
            
            if hasattr(response, 'tool_calls') and response.tool_calls:
                for tool_call in response.tool_calls:
                    # Create tool call event
                    tool_event = create_tool_call_event(
                        tool_call.get('name', 'unknown'),
                        tool_call.get('args', {}),
                        msg_count
                    )
                    events.append(tool_event)
                    log_orchestrator_activity("TOOL_CALL",
                                             tool_name=tool_call.get('name', 'unknown'),
                                             tool_args=tool_call.get('args', {}),
                                             event_count=len(events))
            
            response_content = str(response.content) if hasattr(response, 'content') else ""
            
            # Estimate token usage for cost tracking (rough 4 chars/token)
            message_chars = sum(len(str(m.content if hasattr(m, 'content') else m)) for m in messages)
            response_chars = len(response_content)
            estimated_tokens = (message_chars + response_chars) // 4
            
            # Create AI response event
            ai_event = create_ai_response_event(
                response_content,
                msg_count,
                estimated_tokens
            )
            events.append(ai_event)
            
            log_orchestrator_activity("LLM_GENERATION_COMPLETE", 
                                     response_length=len(response_content),
                                     response_content=response_content[:500],  # Truncate for readability
                                     has_tool_calls=bool(hasattr(response, 'tool_calls') and response.tool_calls),
                                     event_count=len(events))
            
            log_cost_activity("ORCHESTRATOR_LLM", estimated_tokens,
                            message_count=len(messages),
                            event_count=len(events))
            
            # Convert events back to dicts for state storage
            # IMPORTANT: Only keep recent events to prevent unbounded growth
            conv_config = get_conversation_config()
            max_events = conv_config.max_event_history
            recent_events = events[-max_events:] if len(events) > max_events else events
            event_dicts = [e.to_dict() for e in recent_events]
            
            # Log if we're trimming events
            if len(events) > max_events:
                log_orchestrator_activity("EVENT_HISTORY_TRIMMED", 
                                        total_events=len(events),
                                        kept_events=max_events,
                                        trimmed_events=len(events) - max_events)
            
            updated_state = {
                "messages": response,
                "memory": existing_memory,
                "events": event_dicts  # Store trimmed event history
            }
            
            # Check if we need to initialize summary
            if "summary" not in state or not state.get("summary"):
                updated_state["summary"] = "No summary available"
                log_orchestrator_activity("SUMMARY_INITIALIZED",
                                        operation="setting_default_summary")
            
            # Check and mark if we need background tasks
            conv_config = get_conversation_config()
            
            # Check if we should trigger summary based on events
            # More aggressive summarization since we have good memory extraction
            if EventAnalyzer.should_trigger_summary(events, 
                                                   user_message_threshold=3,  # Reduced from 5
                                                   time_threshold_seconds=180):  # Reduced from 300 (3 min instead of 5)
                
                # Create summary triggered event
                summary_event = create_summary_triggered_event(
                    msg_count,
                    "Threshold reached based on user messages or time"
                )
                events.append(summary_event)
                event_dicts.append(summary_event.to_dict())
                
                log_orchestrator_activity("SUMMARY_TRIGGER", 
                                        message_count=len(state["messages"]), 
                                        event_count=len(events))
                
                # Fire and forget background summarization
                import threading
                user_id = config["configurable"].get("user_id", "default")
                thread_id = config["configurable"].get("thread_id", "default")
                threading.Thread(
                    target=_run_background_summary,
                    args=(state["messages"], state.get("summary", ""), events, existing_memory, user_id, thread_id),
                    daemon=True
                ).start()
            
            # Check if we should trigger memory update based on events
            if EventAnalyzer.should_trigger_memory_update(events,
                                                        tool_call_threshold=3,
                                                        agent_call_threshold=2):
                
                # Create memory update triggered event
                memory_event = create_memory_update_triggered_event(
                    msg_count,
                    "Threshold reached based on tool/agent calls"
                )
                events.append(memory_event)
                event_dicts.append(memory_event.to_dict())
                
                log_orchestrator_activity("MEMORY_TRIGGER",
                                        event_count=len(events),
                                        message_count=len(state["messages"]))
                
                # Fire and forget background memory extraction
                import threading
                threading.Thread(
                    target=_run_background_memory,
                    args=(state["messages"], state.get("summary", ""), events, existing_memory),
                    daemon=True
                ).start()
            
            return updated_state
            
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            raise
    
    async def summarize_conversation(state: OrchestratorState):
        """Summarize conversation with intelligent message preservation.
        
        Uses smart preservation to maintain tool call/response pairs while
        compressing conversation history. Implements cooldown to prevent
        cascading summarization in multi-tool scenarios.
        
        Args:
            state: Current orchestrator state
            
        Returns:
            Dict with new summary, messages to delete, and cooldown marker
        """
        start_time = time.time()
        messages_count = len(state.get('messages', []))
        # Load events with automatic limiting
        events = load_events_with_limit(state)
        
        summary = state.get("summary", "No summary available")
        memory_val = state.get("memory", "No memory available")
        
        # Log summary request
        summary_logger = get_summary_logger()
        summary_logger.log_summary_request(
            messages_count=messages_count,
            current_summary=summary,
            memory_context=memory_val,
            component="orchestrator"
        )
        
        system_message = orchestrator_summary_sys_msg(summary, memory_val)
        # System message format must remain pure - tool responses stay in conversation
        messages = [SystemMessage(content=system_message)] + state["messages"]
        
        # Use standard config temperature (already 0.0)
        response = invoke_llm(messages, use_tools=False)
        
        # VALIDATE SUMMARY FORMAT
        response_content = str(response.content) if hasattr(response, 'content') else ""
        
        # Check if summary follows the required format
        has_technical_section = "TECHNICAL/SYSTEM INFORMATION:" in response_content
        has_user_section = "USER INTERACTION:" in response_content
        has_agent_section = "AGENT COORDINATION CONTEXT:" in response_content
        is_valid_format = has_technical_section and has_user_section and has_agent_section
        
        # Check for common invalid patterns
        has_conversational_intro = any(phrase in response_content.lower() for phrase in [
            "here are", "the records", "i found", "the details", "let me", 
            "based on", "according to", "shows that", "indicates"
        ])
        
        # Log format validation
        log_orchestrator_activity("SUMMARY_FORMAT_VALIDATION",
                                operation="format_check",
                                is_valid_format=is_valid_format,
                                has_technical_section=has_technical_section,
                                has_user_section=has_user_section,
                                has_agent_section=has_agent_section,
                                has_conversational_intro=has_conversational_intro,
                                response_preview=response_content[:300],
                                response_length=len(response_content))
        
        # If invalid format, log debug and use a fallback
        if not is_valid_format or has_conversational_intro:
            logger.debug(f"Invalid summary format detected - using fallback structured summary")
            log_orchestrator_activity("SUMMARY_FORMAT_ERROR",
                                    error="Invalid summary format",
                                    response_content=response_content[:500])
            
            # Use a fallback structured summary with dynamic data
            # Extract relevant data from the conversation
            messages = state.get('messages', [])
            message_count = len(messages)
            
            # Check for tool calls
            has_tool_calls = any(
                hasattr(msg, 'tool_calls') and msg.tool_calls 
                for msg in messages if hasattr(msg, 'tool_calls')
            )
            
            # Check for agent invocations
            agent_names = []
            for msg in messages:
                if hasattr(msg, 'name') and msg.name:
                    if 'salesforce' in msg.name.lower():
                        agent_names.append('salesforce-agent')
                    elif 'agent' in msg.name.lower():
                        agent_names.append(msg.name)
            agent_names = list(set(agent_names))  # Remove duplicates
            
            # Count errors from events
            events = load_events_with_limit(state)
            error_count = sum(1 for e in events if e.event_type == EventType.ERROR)
            
            # Generate fallback with actual data
            response_content = get_fallback_summary(
                message_count=message_count,
                has_tool_calls=has_tool_calls,
                agent_names=agent_names,
                error_count=error_count
            )
        
        # Smart preservation maintains tool call/response integrity
        # Can be more aggressive with culling since we summarize more frequently
        messages_to_preserve = smart_preserve_messages(state["messages"], keep_count=2)  # Reduced from 3
        messages_to_delete = []
        
        # Mark non-preserved messages for deletion
        preserved_ids = {getattr(msg, 'id', None) for msg in messages_to_preserve if hasattr(msg, 'id')}
        for msg in state["messages"]:
            if hasattr(msg, 'id') and msg.id not in preserved_ids:
                messages_to_delete.append(RemoveMessage(id=msg.id))
        
        # Don't overwrite response_content - it may have been updated with fallback
        log_orchestrator_activity("LLM_GENERATION_COMPLETE", 
                                 response_length=len(response_content),
                                 response_content=response_content[:500],
                                 operation="SUMMARIZATION",
                                 event_count=len(events))
        
        # Log token usage based on preserved message count
        message_chars = sum(len(str(m.content if hasattr(m, 'content') else m)) for m in messages)
        estimated_tokens = message_chars // 4
        log_cost_activity("ORCHESTRATOR_LLM_CALL", estimated_tokens,
                         message_count=len(messages_to_preserve),
                         response_length=len(str(response.content)) if hasattr(response, 'content') else 0,
                         event_count=len(events))
        
        # Log summary response
        processing_time = time.time() - start_time
        summary_logger.log_summary_response(
            new_summary=response_content,
            messages_preserved=len(messages_to_preserve),
            messages_deleted=len(messages_to_delete),
            component="orchestrator",
            processing_time=processing_time
        )
        
        # Create summary completed event
        summary_completed_event = OrchestratorEvent(
            event_type=EventType.SUMMARY_COMPLETED,
            details={
                "messages_preserved": len(messages_to_preserve),
                "messages_deleted": len(messages_to_delete),
                "processing_time": processing_time
            },
            message_count=messages_count
        )
        
        return {
            "summary": response_content,  # Use validated/fallback content
            "messages": messages_to_delete,
            "events": [summary_completed_event.to_dict()]
        }
    
    async def memorize_records(state: OrchestratorState, config: RunnableConfig):
        """Extract and persist structured data from conversation.
        
        Uses TrustCall to extract Salesforce entities (accounts, contacts, etc.)
        from tool responses and conversation context. Implements deduplication
        to prevent duplicate records.
        
        Args:
            state: Current orchestrator state
            config: Runtime configuration with user ID
            
        Returns:
            Dict with updated memory and reset turn counter
        """
        
        conv_config = get_conversation_config()
        user_id = config["configurable"].get("user_id", conv_config.default_user_id)
        namespace = (conv_config.memory_namespace_prefix, user_id)
        key = conv_config.memory_key
        
        # Load existing memory for TrustCall context
        try:
            stored = memory_store.sync_get(namespace, key)
            if stored:
                existing_records = {"SimpleMemory": stored}
            else:
                existing_records = {"SimpleMemory": SimpleMemory().model_dump()}
        except:
            existing_records = {"SimpleMemory": SimpleMemory().model_dump()}
        
        # Extract data from tool responses, not just summary
        recent_tool_responses = []
        messages = state.get("messages", [])
        
        log_orchestrator_activity("MEMORY_EXTRACTION_START",
                                message_count=len(messages),
                                user_id=user_id)
        
        # Scan recent messages for tool responses with data
        for msg in reversed(messages[-10:]):
            if hasattr(msg, 'name') and msg.name and any(agent in msg.name.lower() for agent in ['salesforce', 'travel', 'expense', 'hr', 'ocr']):
                content = getattr(msg, 'content', '')
                if content and len(content) > 50:  # Meaningful content
                    # Parse structured data if present
                    if "[STRUCTURED_TOOL_DATA]:" in content:
                        parts = content.split("[STRUCTURED_TOOL_DATA]:")
                        conversational_part = parts[0].strip()
                        try:
                            import json
                            structured_part = json.loads(parts[1].strip())
                            # Format for TrustCall extraction
                            enhanced_content = f"{conversational_part}\n\nDETAILED SALESFORCE RECORDS WITH REAL IDS:\n{json.dumps(structured_part, indent=2)}"
                            recent_tool_responses.append(enhanced_content[:2000])
                        except (json.JSONDecodeError, IndexError):
                            recent_tool_responses.append(content[:1500])
                    else:
                        recent_tool_responses.append(content[:1500])
        
        # Build extraction prompt with tool responses and summary
        summary_content = state.get("summary", "")
        
        # DEBUG LOGGING: Track summary extraction issue
        log_orchestrator_activity("MEMORY_EXTRACTION_DEBUG",
                                operation="summary_retrieval",
                                summary_exists=bool(summary_content),
                                summary_length=len(summary_content) if summary_content else 0,
                                summary_preview=summary_content[:200] if summary_content else "NO_SUMMARY",
                                tool_responses_count=len(recent_tool_responses))
        
        extraction_content = f"CONVERSATION SUMMARY:\n{summary_content}\n\n"
        
        if recent_tool_responses:
            extraction_content += "RECENT SALESFORCE TOOL RESPONSES WITH DATA TO EXTRACT:\n"
            for i, response in enumerate(recent_tool_responses):
                extraction_content += f"\nTool Response {i+1}:\n{response}\n"
                # Log each tool response being added
                log_orchestrator_activity("MEMORY_EXTRACTION_DEBUG",
                                        operation="tool_response_added",
                                        response_index=i,
                                        response_length=len(response),
                                        response_preview=response[:100])
        else:
            extraction_content += "No recent tool responses found."
            log_orchestrator_activity("MEMORY_EXTRACTION_DEBUG",
                                    operation="no_tool_responses",
                                    message="No recent tool responses found for extraction")
        
        # Log final extraction content
        log_orchestrator_activity("MEMORY_EXTRACTION_DEBUG",
                                operation="final_extraction_content",
                                content_length=len(extraction_content),
                                content_preview=extraction_content[:500],
                                has_summary=bool(summary_content),
                                has_tool_responses=bool(recent_tool_responses))
        
        # Invoke TrustCall with timeout for background safety
        try:
            llm_config = get_llm_config()
            
            import asyncio
            response = await asyncio.wait_for(
                trustcall_extractor.ainvoke({
                    "messages": [
                        SystemMessage(content=TRUSTCALL_INSTRUCTION),
                        HumanMessage(content=extraction_content)
                    ],
                    "existing": existing_records
                }),
                timeout=float(llm_config.timeout)
            )
            
            if response and response.get("responses"):
                extracted_data = response["responses"][0]
                
                if hasattr(extracted_data, 'model_dump'):
                    clean_data = extracted_data.model_dump()
                else:
                    clean_data = extracted_data
                
                # Merge with existing data, deduplicating by ID
                if stored and isinstance(stored, dict):
                    # Merge each entity type, removing duplicates by ID
                    for entity_type in ['accounts', 'contacts', 'opportunities', 'cases', 'tasks', 'leads']:
                        existing_items = stored.get(entity_type, [])
                        new_items = clean_data.get(entity_type, [])
                        
                        merged_dict = {}
                        
                        # Index existing items by ID
                        for item in existing_items:
                            if isinstance(item, dict) and 'id' in item:
                                merged_dict[item['id']] = item
                        
                        # Add/update with new items
                        for item in new_items:
                            if isinstance(item, dict) and 'id' in item:
                                merged_dict[item['id']] = item
                        
                        clean_data[entity_type] = list(merged_dict.values())
                
                memory_store.sync_put(namespace, key, clean_data)
                
                total_records = (len(clean_data.get('accounts', [])) + len(clean_data.get('contacts', [])) + 
                               len(clean_data.get('opportunities', [])) + len(clean_data.get('cases', [])) + 
                               len(clean_data.get('tasks', [])) + len(clean_data.get('leads', [])))
                
                # Create memory update completed event
                memory_completed_event = OrchestratorEvent(
                    event_type=EventType.MEMORY_UPDATE_COMPLETED,
                    details={
                        "total_records": total_records,
                        "entity_counts": {k: len(v) for k, v in clean_data.items() if isinstance(v, list)}
                    },
                    message_count=len(state.get('messages', []))
                )
                
                return {
                    "memory": {"SimpleMemory": clean_data}, 
                    "events": [memory_completed_event.to_dict()]
                }
                
        except asyncio.TimeoutError:
            logger.warning("Memory extraction timed out")
            empty_memory = SimpleMemory().model_dump()
            error_event = OrchestratorEvent(
                event_type=EventType.ERROR,
                details={"error": "Memory extraction timed out"},
                message_count=len(state.get('messages', []))
            )
            return {
                "memory": {"SimpleMemory": empty_memory}, 
                "events": [error_event.to_dict()]
            }
        except Exception as e:
            logger.warning(f"Memory extraction failed: {type(e).__name__}: {e}")
            empty_memory = SimpleMemory().model_dump()
            error_event = OrchestratorEvent(
                event_type=EventType.ERROR,
                details={"error": f"Memory extraction failed: {str(e)}"},
                message_count=len(state.get('messages', []))
            )
            return {
                "memory": {"SimpleMemory": empty_memory}, 
                "events": [error_event.to_dict()]
            }
    
    
    
    # Background task helpers that save directly to persistent store
    def _run_background_summary(messages, summary, events, memory, user_id, thread_id):
        """Execute summarization in background thread and save to store.
        
        Creates new event loop for async execution in thread context.
        Saves summary directly to the persistent store.
        """
        try:
            mock_state = {
                "messages": messages,
                "summary": summary,
                "events": [e.to_dict() for e in events],
                "memory": memory
            }
            mock_config = {"configurable": {"user_id": user_id, "thread_id": thread_id}}
            import asyncio
            result = asyncio.run(summarize_conversation(mock_state))
            
            if result and "summary" in result:
                new_summary = result["summary"]
                log_orchestrator_activity("BACKGROUND_SUMMARY_SAVE",
                                        operation="saving_summary_to_store",
                                        summary_preview=new_summary[:200] if new_summary else "NO_SUMMARY")
                
                # Save directly to the persistent store
                conv_config = get_conversation_config()
                namespace = (conv_config.memory_namespace_prefix, user_id)
                key = conv_config.summary_key
                memory_store.sync_put(namespace, key, {
                    "summary": new_summary,
                    "thread_id": thread_id,
                    "timestamp": time.time()
                })
                
        except Exception as e:
            import traceback
            log_orchestrator_activity("BACKGROUND_SUMMARY_ERROR",
                                     error=str(e),
                                     traceback=traceback.format_exc()[:500])
    
    def _run_background_memory(messages, summary, events, memory):
        """Execute memory extraction in background thread.
        
        Analyzes tool messages for structured data extraction.
        Creates new event loop for async execution.
        """
        try:
            mock_state = {
                "messages": messages,
                "summary": summary,
                "events": [e.to_dict() for e in events],
                "memory": memory
            }
            conv_config = get_conversation_config()
            mock_config = {"configurable": {"user_id": conv_config.default_user_id}}
            import asyncio
            result = asyncio.run(memorize_records(mock_state, mock_config))
        except Exception as e:
            import traceback
            log_orchestrator_activity("BACKGROUND_MEMORY_ERROR",
                                     error=str(e),
                                     traceback=traceback.format_exc()[:500])
    
    # Build graph with tool integration
    tool_node = ToolNode(tools=tools)
    graph_builder.add_node("tools", tool_node)
    graph_builder.add_node("conversation", orchestrator)
    
    graph_builder.set_entry_point("conversation")
    
    # Route to tools when needed
    graph_builder.add_conditional_edges("conversation", tools_condition)
    
    # Return to conversation after tool execution
    graph_builder.add_edge("tools", "conversation")
    
    graph_builder.set_finish_point("conversation")
    
    return graph_builder.compile(checkpointer=memory, store=memory_store)

# Create default orchestrator graph for module export
orchestrator_graph = build_orchestrator_graph()

async def initialize_orchestrator():
    """Initialize orchestrator and discover available agents.
    
    Performs health checks on registered agents and attempts
    auto-discovery of unregistered agents on standard ports.
    """
    logger.info("Initializing Consultant Assistant Orchestrator...")
    
    # Clear any existing conversation summaries for fresh start
    try:
        memory_store = get_async_store_adapter(
            db_path="memory_store.db",
            use_async=False,
            max_workers=4,
            max_connections=10,
            enable_circuit_breaker=True
        )
        
        # Clear summaries for all users
        # In production, you might want to clear only for specific users
        conv_config = get_conversation_config()
        users_to_clear = [conv_config.default_user_id, "default", "test_user"]
        
        for user in users_to_clear:
            namespace = (conv_config.memory_namespace_prefix, user)
            key = conv_config.summary_key
            try:
                # Try to delete if it exists
                existing = memory_store.sync_get(namespace, key)
                if existing:
                    # Overwrite with empty value since delete might not be implemented
                    memory_store.sync_put(namespace, key, None)
            except:
                pass  # If it doesn't exist, that's fine
        
        logger.info("Cleared conversation summaries for fresh start")
    except Exception as e:
        logger.warning(f"Could not clear summaries: {e}")
    
    logger.info("Checking agent health...")
    health_results = await agent_registry.health_check_all_agents()
    
    online_agents = [name for name, status in health_results.items() if status]
    offline_agents = [name for name, status in health_results.items() if not status]
    
    if online_agents:
        logger.info(f"Online agents: {', '.join(online_agents)}")
    if offline_agents:
        logger.warning(f"Offline agents: {', '.join(offline_agents)}")
    
    # Attempt auto-discovery if no agents registered
    if not agent_registry.list_agents():
        logger.info("No agents registered, attempting auto-discovery...")
        discovery_endpoints = [
            "http://localhost:8001",  # Salesforce agent
            "http://localhost:8002",  # Travel agent (future)
            "http://localhost:8003",  # Expense agent (future)
            "http://localhost:8004",  # HR agent (future)
            "http://localhost:8005",  # OCR agent (future)
        ]
        
        discovered = await agent_registry.discover_agents(discovery_endpoints)
        if discovered > 0:
            logger.info(f"Discovered {discovered} agents")
        else:
            logger.warning("No agents discovered - you may need to start specialized agents manually")
    
    logger.info("Orchestrator initialization complete")

# Main CLI function for orchestrator
async def main():
    """Main CLI interface for the orchestrator"""
    parser = argparse.ArgumentParser(description="Consultant Assistant Orchestrator")
    args = parser.parse_args()
    
    # Setup comprehensive external logging
    init_session_tracking()
    
    # Get structured loggers
    orchestrator_logger = get_logger('orchestrator')
    perf_tracker = get_performance_tracker('orchestrator')
    cost_tracker = get_cost_tracker()
    
    # Setup basic logging for console output - only for user interface
    log_level = logging.WARNING
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Log session start
    orchestrator_logger.info("ORCHESTRATOR_SESSION_START",
                           components=['orchestrator', 'agents', 'a2a'])
    
    # Suppress verbose logging from third-party libraries and internal components
    # Always suppress noise regardless of debug mode
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('simple_salesforce').setLevel(logging.WARNING)
    logging.getLogger('openai._base_client').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('httpcore.connection').setLevel(logging.WARNING)
    logging.getLogger('httpcore.http11').setLevel(logging.WARNING)
    
    # Suppress internal system component logging to console
    logging.getLogger('src.utils.circuit_breaker').setLevel(logging.WARNING)
    logging.getLogger('src.utils.config').setLevel(logging.WARNING)
    logging.getLogger('src.orchestrator.agent_registry').setLevel(logging.WARNING)
    logging.getLogger('src.orchestrator.main').setLevel(logging.WARNING)
    logging.getLogger('src.a2a.protocol').setLevel(logging.WARNING)
    
    # Initialize orchestrator
    await initialize_orchestrator()
    
    # Use the default orchestrator graph
    local_graph = orchestrator_graph
    
    print("\n=== Consultant Assistant Orchestrator ===")
    print("Multi-agent system ready. Available capabilities:")
    
    # Show available agents and capabilities
    stats = agent_registry.get_registry_stats()
    if stats['available_capabilities']:
        for capability in stats['available_capabilities']:
            print(f"  • {capability}")
    else:
        print("  • No agents currently available")
    
    print("\nType your request, or 'quit' to exit.\n")
    
    conv_config = get_conversation_config()
    config = {"configurable": {"thread_id": "orchestrator-1", "user_id": conv_config.default_user_id}}
    
    while True:
        try:
            user_input = input("USER: ")
            
            log_orchestrator_activity("USER_INPUT_RAW", input=user_input[:1000])
            
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                log_orchestrator_activity("USER_QUIT")
                break
            
            # Validate input for security
            try:
                from src.utils.input_validation import AgentInputValidator
                validated_input = AgentInputValidator.validate_orchestrator_input(user_input)
                user_input = validated_input
            except Exception as e:
                print(f"Error: Invalid input - {e}")
                continue
            
            print("\nASSISTANT: ", end="", flush=True)
            # Stream response immediately
            conversation_response = None
            response_shown = False
            
            async for event in local_graph.astream(
                {
                    "messages": [{"role": "user", "content": user_input}],
                    "background_operations": [],
                    "background_results": {},
                    "last_summarized_turn": -1
                },
                config,
                stream_mode="values"
            ):
                # Display AI response as soon as available
                if "messages" in event and event["messages"] and not response_shown:
                    last_msg = event["messages"][-1]
                    if hasattr(last_msg, 'content') and last_msg.content and hasattr(last_msg, 'type'):
                        from langchain_core.messages import AIMessage
                        if isinstance(last_msg, AIMessage) and not getattr(last_msg, 'tool_calls', None):
                            conversation_response = last_msg.content
                            log_orchestrator_activity("USER_MESSAGE_DISPLAYED", 
                                                    response=conversation_response[:1000],
                                                    full_length=len(conversation_response))
                            await type_out(conversation_response, delay=0.01)
                            response_shown = True
                            print("\n")
                            # Continue processing for background tasks
            
            if not response_shown:
                print("Processing your request...\n")
                        
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except EOFError:
            print("\nInput stream ended. Goodbye!")
            break
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            print(f"Error: {e}")
            # Exit on critical network errors
            if "connection" in str(e).lower() or "network" in str(e).lower():
                print("Network error encountered. Exiting...")
                break

if __name__ == "__main__":
    asyncio.run(main())