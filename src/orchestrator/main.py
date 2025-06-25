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
import time
from typing import Annotated, Dict, Any, List
import operator
from typing_extensions import TypedDict, Optional

from dotenv import load_dotenv

from src.utils.logging import get_logger, init_session_tracking
from src.utils.tool_execution import create_tool_node

from trustcall import create_extractor

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from langgraph.graph.message import RemoveMessage, add_messages

from langgraph.prebuilt import tools_condition

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import AzureChatOpenAI


from .agent_registry import AgentRegistry
from .agent_caller_tools import SalesforceAgentTool, JiraAgentTool, AgentRegistryTool
from src.utils.helpers import type_out, smart_preserve_messages
from src.utils.message_serialization import serialize_messages
from src.utils.storage import get_async_store_adapter
from src.utils.storage.memory_schemas import SimpleMemory
from src.utils.config import get_llm_config, get_conversation_config, get_database_config
from src.utils.sys_msg import (
    orchestrator_chatbot_sys_msg, 
    orchestrator_summary_sys_msg, 
    get_fallback_summary,
    TRUSTCALL_INSTRUCTION
)
from src.utils.config import (
    MEMORY_NAMESPACE_PREFIX, SIMPLE_MEMORY_KEY, STATE_KEY_PREFIX,
    SUMMARY_KEY, NO_SUMMARY_TEXT,
    SUMMARY_USER_MESSAGE_THRESHOLD, SUMMARY_TIME_THRESHOLD_SECONDS,
    MEMORY_TOOL_CALL_THRESHOLD, MEMORY_AGENT_CALL_THRESHOLD,
    LOCALHOST, SALESFORCE_AGENT_PORT,
    ENTERPRISE_ASSISTANT_BANNER,
    DETERMINISTIC_TEMPERATURE, DETERMINISTIC_TOP_P
)

import logging


# Disable LangSmith tracing to prevent circular reference errors in async context
os.environ["LANGCHAIN_TRACING_V2"] = "false"


# Initialize logger
logger = get_logger()

from src.utils.events import (
    EventType, OrchestratorEvent, EventAnalyzer,
    create_user_message_event, create_ai_response_event, 
    create_tool_call_event, create_summary_triggered_event,
    create_memory_update_triggered_event
)

# Initialize global agent registry for service discovery
agent_registry = AgentRegistry()

# Initialize global memory store for access in main
global_memory_store = None

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
        max_workers=4
    )
    
    # Set global store for access in main
    global global_memory_store
    global_memory_store = memory_store
    
    
    graph_builder = StateGraph(OrchestratorState)
    
    # Initialize orchestrator tools
    tools = [
        SalesforceAgentTool(agent_registry),
        JiraAgentTool(agent_registry),
        AgentRegistryTool(agent_registry)
    ]
    
    # Create LLM instance with configuration
    llm_config = get_llm_config()
    llm_kwargs = {
        "azure_endpoint": os.environ["AZURE_OPENAI_ENDPOINT"],
        "azure_deployment": llm_config.azure_deployment,
        "openai_api_version": llm_config.api_version,
        "openai_api_key": os.environ["AZURE_OPENAI_API_KEY"],
        "temperature": llm_config.temperature,
        "max_tokens": llm_config.max_tokens,
        "timeout": llm_config.timeout,
    }
    if llm_config.top_p is not None:
        llm_kwargs["top_p"] = llm_config.top_p
    
    llm = AzureChatOpenAI(**llm_kwargs)
    llm_with_tools = llm.bind_tools(tools)
    
    # Create deterministic LLM for TrustCall memory extraction
    # This needs to be a separate instance since TrustCall requires an LLM object,
    # not a function, and we want deterministic extraction regardless of user-facing config
    deterministic_llm = AzureChatOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=llm_config.azure_deployment,
        openai_api_version=llm_config.api_version,
        openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
        temperature=DETERMINISTIC_TEMPERATURE,  # Always deterministic for memory extraction
        top_p=DETERMINISTIC_TOP_P,  # Focused sampling for consistency
        max_tokens=llm_config.max_tokens,
        timeout=llm_config.timeout,
    )
    
    # Configure TrustCall for structured data extraction
    trustcall_extractor = create_extractor(
        deterministic_llm,  # Use deterministic LLM for consistent extraction
        tools=[SimpleMemory],
        tool_choice="SimpleMemory",  # Explicit choice prevents tool conflicts
        enable_inserts=True
    )
    
    def invoke_llm(messages, use_tools=False, temperature=None, top_p=None):
        """Invoke LLM with optional tool binding and generation parameters.
        
        Azure OpenAI automatically caches prompts for efficiency.
        
        Args:
            messages: List of conversation messages
            use_tools: Whether to bind tools for function calling
            temperature: Override temperature for this call (0.0 = deterministic, 1.0 = creative)
            top_p: Override top_p for nucleus sampling (0.1 = focused, 1.0 = diverse)
            
        Returns:
            AI response message with optional tool calls
        """
        if temperature is not None or top_p is not None:
            # Create a new LLM with custom parameters for experimentation
            llm_config = get_llm_config()
            temp_llm = AzureChatOpenAI(
                azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                azure_deployment=llm_config.azure_deployment,
                openai_api_version=llm_config.api_version,
                openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
                temperature=temperature if temperature is not None else llm_config.temperature,
                max_tokens=llm_config.max_tokens,
                timeout=llm_config.timeout,
                top_p=top_p  # Azure OpenAI accepts top_p parameter
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
            
            # Log state entry for debugging
            logger.info("orchestrator_state_entry",
                component="orchestrator",
                operation="conversation_processing",
                message_count=msg_count,
                has_summary=bool(state.get('summary')),
                has_memory=bool(state.get('memory')),
                thread_id=config["configurable"].get("thread_id", "default")
            )
            
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
                    logger.info("user_request".lower(), component="orchestrator", user_message=str(last_msg.content)[:200],
                                             message_count=msg_count,
                                             event_count=len(events))
                elif isinstance(last_msg, AIMessage):
                    logger.info("ai_response_processing".lower(), component="orchestrator", ai_message=str(last_msg.content)[:200],
                                             message_count=msg_count,
                                             event_count=len(events))
                        
            # Load persistent memory using flat schema for simplicity
            user_id = config["configurable"].get("user_id", "default")
            namespace = (MEMORY_NAMESPACE_PREFIX, user_id)
            key = SIMPLE_MEMORY_KEY
            
            # Log memory load operation
            logger.info("memory_load_start",
                component="orchestrator",
                operation="load_memory",
                user_id=user_id,
                namespace=str(namespace),
                key=key
            )
            
            existing_memory_data = memory_store.sync_get(namespace, key)
            
            if existing_memory_data:
                try:
                    validated_data = SimpleMemory(**existing_memory_data)
                    existing_memory = {SIMPLE_MEMORY_KEY: validated_data.model_dump()}
                    logger.info("memory_load_success",
                        component="orchestrator",
                        operation="load_memory",
                        memory_size=len(str(existing_memory))
                    )
                except Exception as e:
                    logger.error("memory_validation_error",
                        component="orchestrator",
                        operation="load_memory",
                        error=str(e),
                        error_type=type(e).__name__
                    )
                    existing_memory = {SIMPLE_MEMORY_KEY: SimpleMemory().model_dump()}
            else:
                existing_memory = {SIMPLE_MEMORY_KEY: SimpleMemory().model_dump()}
            
            # Update state memory before system message generation
            state["memory"] = existing_memory
            
            # Load summary from persistent store if not in state
            summary = state.get(SUMMARY_KEY, NO_SUMMARY_TEXT)
            if summary == NO_SUMMARY_TEXT:
                # Try to load from store using thread_id as key
                conv_config = get_conversation_config()
                user_id = config["configurable"].get("user_id", conv_config.default_user_id)
                thread_id = config["configurable"].get("thread_id", conv_config.default_thread_id)
                namespace = (conv_config.memory_namespace_prefix, user_id)
                key = f"summary_{thread_id}"  # Use thread_id in the key
                
                try:
                    stored_summary = memory_store.sync_get(namespace, key)
                    if stored_summary and "summary" in stored_summary:
                        state["summary"] = stored_summary["summary"]
                        summary = stored_summary["summary"]
                        logger.info("summary_loaded_from_store".lower(), component="orchestrator", summary_preview=summary[:200],
                                                thread_id=thread_id,
                                                timestamp=stored_summary.get("timestamp"))
                except Exception as e:
                    logger.info("summary_load_error".lower(), component="orchestrator", error=str(e), thread_id=thread_id)
            
            logger.info("summary_state_check".lower(), component="orchestrator", operation="conversation_node_entry",
                                    has_summary=bool(summary and summary != "No summary available"),
                                    summary_length=len(summary) if summary else 0,
                                    summary_preview=summary[:200] if summary else "NO_SUMMARY")
            
            system_message = get_orchestrator_system_message(state)
            messages = [SystemMessage(content=system_message)] + state["messages"]
            
            # Log LLM invocation start
            logger.info("llm_invocation_start",
                component="orchestrator",
                operation="invoke_llm",
                message_count=len(messages),
                system_message_length=len(system_message),
                use_tools=True
            )
            
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
                    logger.info("tool_call".lower(), component="orchestrator", tool_name=tool_call.get('name', 'unknown'),
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
            
            logger.info("llm_generation_complete".lower(), component="orchestrator", response_length=len(response_content),
                                     response_content=response_content[:500],  # Truncate for readability
                                     has_tool_calls=bool(hasattr(response, 'tool_calls') and response.tool_calls),
                                     event_count=len(events))
            
            logger.track_cost("ORCHESTRATOR_LLM".lower(), tokens=estimated_tokens, 
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
                logger.info("event_history_trimmed".lower(), component="orchestrator", total_events=len(events),
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
                logger.info("summary_initialized".lower(), component="orchestrator", operation="setting_default_summary")
            
            # Check and mark if we need background tasks
            conv_config = get_conversation_config()
            
            # Check if we should trigger summary based on events
            # More aggressive summarization since we have good memory extraction
            if EventAnalyzer.should_trigger_summary(events, 
                                                   user_message_threshold=SUMMARY_USER_MESSAGE_THRESHOLD,
                                                   time_threshold_seconds=SUMMARY_TIME_THRESHOLD_SECONDS):  # Reduced from 300 (3 min instead of 5)
                
                # Create summary triggered event
                summary_event = create_summary_triggered_event(
                    msg_count,
                    "Threshold reached based on user messages or time"
                )
                events.append(summary_event)
                event_dicts.append(summary_event.to_dict())
                
                logger.info("summary_trigger".lower(), component="orchestrator", message_count=len(state["messages"]), 
                                        event_count=len(events))
                
                # Fire and forget background summarization
                user_id = config["configurable"].get("user_id", "default")
                thread_id = config["configurable"].get("thread_id", "default")
                
                # Use asyncio.create_task instead of threading for better resource management
                asyncio.create_task(
                    _run_background_summary_async(
                        state["messages"], 
                        state.get("summary", ""), 
                        events, 
                        existing_memory, 
                        user_id, 
                        thread_id
                        # Don't pass store - create new one in async context
                    )
                )
            
            # Check if we should trigger memory update based on events
            if EventAnalyzer.should_trigger_memory_update(events,
                                                        tool_call_threshold=MEMORY_TOOL_CALL_THRESHOLD,
                                                        agent_call_threshold=MEMORY_AGENT_CALL_THRESHOLD):
                
                # Create memory update triggered event
                memory_event = create_memory_update_triggered_event(
                    msg_count,
                    "Threshold reached based on tool/agent calls"
                )
                events.append(memory_event)
                event_dicts.append(memory_event.to_dict())
                
                logger.info("memory_trigger".lower(), component="orchestrator", event_count=len(events),
                                        message_count=len(state["messages"]))
                
                # Fire and forget background memory extraction
                # Use asyncio.create_task for better resource management
                asyncio.create_task(
                    _run_background_memory_async(
                        state["messages"], 
                        state.get("summary", ""), 
                        events, 
                        existing_memory,
                        user_id
                        # Don't pass store - create new one in async context
                    )
                )
            
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
        logger.info("summary_request",
            component="orchestrator",
            messages_count=messages_count,
            current_summary=summary,
            memory_context=memory_val
        )
        
        system_message = orchestrator_summary_sys_msg(summary, memory_val)
        # System message format must remain pure - tool responses stay in conversation
        messages = [SystemMessage(content=system_message)] + state["messages"]
        
        # Use deterministic temperature for background summarization
        response = invoke_llm(messages, use_tools=False, temperature=DETERMINISTIC_TEMPERATURE, top_p=DETERMINISTIC_TOP_P)
        
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
        logger.info("summary_format_validation".lower(), component="orchestrator", operation="format_check",
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
            logger.info("summary_format_error".lower(), component="orchestrator", error="Invalid summary format",
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
        logger.info("llm_generation_complete".lower(), component="orchestrator", response_length=len(response_content),
                                 response_content=response_content[:500],
                                 operation="SUMMARIZATION",
                                 event_count=len(events))
        
        # Log token usage based on preserved message count
        message_chars = sum(len(str(m.content if hasattr(m, 'content') else m)) for m in messages)
        estimated_tokens = message_chars // 4
        logger.track_cost("ORCHESTRATOR_LLM_CALL".lower(), tokens=estimated_tokens, 
                         message_count=len(messages_to_preserve),
                         response_length=len(str(response.content)) if hasattr(response, 'content') else 0,
                         event_count=len(events))
        
        # Log summary response
        processing_time = time.time() - start_time
        logger.info("summary_response",
            component="orchestrator",
            new_summary=response_content,
            messages_preserved=len(messages_to_preserve),
            messages_deleted=len(messages_to_delete),
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
        
        # Memory extraction logging now handled through main logger
        conv_config = get_conversation_config()
        user_id = config["configurable"].get("user_id", conv_config.default_user_id)
        thread_id = config["configurable"].get("thread_id")
        namespace = (conv_config.memory_namespace_prefix, user_id)
        key = conv_config.memory_key
        
        # Log extraction start
        extraction_start_time = time.time()
        logger.info("memory_extraction_start",
            component="orchestrator",
            operation="extract_records",
            message_count=len(state.get("messages", [])),
            user_id=user_id,
            thread_id=thread_id
        )
        
        # Load existing memory for TrustCall context
        try:
            stored = memory_store.sync_get(namespace, key)
        except Exception as e:
            logger.error("memory_load_error",
                component="orchestrator",
                operation="load_existing_memory",
                error=str(e),
                error_type=type(e).__name__
            )
            stored = None
        
        if stored:
            existing_records = {"SimpleMemory": stored}
        else:
            existing_records = {"SimpleMemory": SimpleMemory().model_dump()}
        
        # Extract data from tool responses, not just summary
        recent_tool_responses = []
        messages = state.get("messages", [])
        
        logger.info("memory_extraction_start".lower(), component="orchestrator", message_count=len(messages),
                                user_id=user_id)
        
        # Scan recent messages for tool responses with data
        for msg in reversed(messages[-10:]):
            # Handle both message objects and dictionaries (from background thread)
            msg_name = None
            msg_content = None
            
            if isinstance(msg, dict):
                # Serialized message from background thread
                msg_name = msg.get('name', '')
                msg_content = msg.get('content', '')
            else:
                # Direct message object
                msg_name = getattr(msg, 'name', '')
                msg_content = getattr(msg, 'content', '')
            
            # Log what we're examining
            logger.info("memory_extraction_debug".lower(), component="orchestrator", operation="examining_message",
                                    msg_type=type(msg).__name__,
                                    msg_name=msg_name[:50] if msg_name else "NO_NAME",
                                    msg_content_length=len(msg_content) if msg_content else 0,
                                    has_structured_data="[STRUCTURED_TOOL_DATA]:" in str(msg_content))
            
            # Log message scan details
            logger.debug("memory_extraction_message_scan",
                component="orchestrator",
                msg_type=type(msg).__name__,
                msg_name=msg_name or "NO_NAME",
                has_content=bool(msg_content),
                content_preview=str(msg_content)[:100] if msg_content else None,
                has_structured_data="[STRUCTURED_TOOL_DATA]:" in str(msg_content)
            )
            
            if msg_name and any(agent in msg_name.lower() for agent in ['salesforce', 'travel', 'expense', 'hr', 'ocr']):
                if msg_content and len(msg_content) > 50:  # Meaningful content
                    # Parse structured data if present
                    if "[STRUCTURED_TOOL_DATA]:" in msg_content:
                        parts = msg_content.split("[STRUCTURED_TOOL_DATA]:")
                        conversational_part = parts[0].strip()
                        try:
                            import json
                            structured_part = json.loads(parts[1].strip())
                            # Format for TrustCall extraction
                            enhanced_content = f"{conversational_part}\n\nDETAILED SALESFORCE RECORDS WITH REAL IDS:\n{json.dumps(structured_part, indent=2)}"
                            recent_tool_responses.append(enhanced_content[:2000])
                            logger.info("memory_extraction_debug".lower(), component="orchestrator", operation="structured_data_found",
                                                    records_count=len(structured_part) if isinstance(structured_part, list) else 1)
                            
                            # Log structured data found
                            tool_name = structured_part.get('tool_name', 'unknown') if isinstance(structured_part, dict) else 'unknown'
                            logger.info("memory_extraction_structured_data_found",
                                component="orchestrator",
                                tool_name=tool_name,
                                data_preview=str(structured_part)[:200],
                                data_size=len(json.dumps(structured_part)),
                                record_count=len(structured_part) if isinstance(structured_part, list) else 1
                            )
                        except (json.JSONDecodeError, IndexError) as e:
                            logger.info("memory_extraction_debug".lower(), component="orchestrator", operation="structured_data_parse_error",
                                                    error=str(e))
                            recent_tool_responses.append(msg_content[:1500])
                    else:
                        recent_tool_responses.append(msg_content[:1500])
        
        # Build extraction prompt with tool responses and summary
        summary_content = state.get("summary", "")
        
        # DEBUG LOGGING: Track summary extraction issue
        logger.info("memory_extraction_debug".lower(), component="orchestrator", operation="summary_retrieval",
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
                logger.info("memory_extraction_debug".lower(), component="orchestrator", operation="tool_response_added",
                                        response_index=i,
                                        response_length=len(response),
                                        response_preview=response[:100])
        else:
            extraction_content += "No recent tool responses found."
            logger.info("memory_extraction_debug".lower(), component="orchestrator", operation="no_tool_responses",
                                    message="No recent tool responses found for extraction")
        
        # Log final extraction content
        logger.info("memory_extraction_debug".lower(), component="orchestrator", operation="final_extraction_content",
                                content_length=len(extraction_content),
                                content_preview=extraction_content[:500],
                                has_summary=bool(summary_content),
                                has_tool_responses=bool(recent_tool_responses))
        
        # Invoke TrustCall with timeout for background safety
        try:
            llm_config = get_llm_config()
            
            # Log TrustCall attempt
            logger.info("trustcall_extraction_start",
                component="orchestrator",
                operation="trustcall_invoke",
                input_size=len(extraction_content),
                extraction_prompt_preview=TRUSTCALL_INSTRUCTION[:200]
            )
            
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
                
                # Log extracted records by type
                for entity_type in ['accounts', 'contacts', 'opportunities', 'cases', 'tasks', 'leads']:
                    extracted_items = clean_data.get(entity_type, [])
                    if extracted_items:
                        sample_ids = [item.get('id') for item in extracted_items if isinstance(item, dict) and 'id' in item]
                        logger.info("records_extracted",
                            component="orchestrator",
                            operation="extract_records",
                            record_type=entity_type,
                            count=len(extracted_items),
                            sample_ids=sample_ids[:3] if sample_ids else []  # Limit to first 3 for brevity
                        )
                
                # Merge with existing data, deduplicating by ID
                memory_before = stored.copy() if stored and isinstance(stored, dict) else SimpleMemory().model_dump()
                if stored and isinstance(stored, dict):
                    # Merge each entity type, removing duplicates by ID
                    for entity_type in ['accounts', 'contacts', 'opportunities', 'cases', 'tasks', 'leads']:
                        existing_items = stored.get(entity_type, [])
                        new_items = clean_data.get(entity_type, [])
                        
                        before_count = len(existing_items)
                        
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
                        
                        # Log deduplication results
                        after_count = len(clean_data[entity_type])
                        if before_count > 0 or len(new_items) > 0:
                            logger.info("deduplication_complete",
                                component="orchestrator",
                                operation="deduplicate_records",
                                record_type=entity_type,
                                before_count=before_count + len(new_items),
                                after_count=after_count,
                                duplicates_removed=before_count + len(new_items) - after_count
                            )
                
                # Calculate changes
                changes = {}
                for entity_type in ['accounts', 'contacts', 'opportunities', 'cases', 'tasks', 'leads']:
                    before = len(memory_before.get(entity_type, []))
                    after = len(clean_data.get(entity_type, []))
                    if after != before:
                        changes[entity_type] = after - before
                
                # Log memory update
                logger.info("memory_update_complete",
                    component="orchestrator",
                    operation="update_memory",
                    user_id=user_id,
                    changes=changes,
                    total_before=sum(len(memory_before.get(et, [])) for et in ['accounts', 'contacts', 'opportunities', 'cases', 'tasks', 'leads']),
                    total_after=sum(len(clean_data.get(et, [])) for et in ['accounts', 'contacts', 'opportunities', 'cases', 'tasks', 'leads'])
                )
                
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
                
                # Log successful extraction completion
                logger.info("memory_extraction_complete",
                    component="orchestrator",
                    operation="extract_records",
                    user_id=user_id,
                    duration_seconds=round(time.time() - extraction_start_time, 2),
                    total_extracted=total_records,
                    success=True
                )
                
                return {
                    "memory": {"SimpleMemory": clean_data}, 
                    "events": [memory_completed_event.to_dict()]
                }
                
        except asyncio.TimeoutError:
            logger.warning("memory_extraction_timeout",
                component="orchestrator",
                operation="trustcall_extraction",
                error="Timeout during TrustCall extraction",
                timeout_seconds=float(llm_config.timeout)
            )
            logger.info("memory_extraction_complete",
                component="orchestrator",
                operation="extract_records",
                user_id=user_id,
                duration_seconds=round(time.time() - extraction_start_time, 2),
                total_extracted=0,
                success=False
            )
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
            logger.warning("memory_extraction_error",
                component="orchestrator",
                operation="memory_extraction",
                error=str(e),
                error_type=type(e).__name__
            )
            logger.info("memory_extraction_complete",
                component="orchestrator",
                operation="extract_records",
                user_id=user_id,
                duration_seconds=round(time.time() - extraction_start_time, 2),
                total_extracted=0,
                success=False
            )
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
    async def _run_background_summary_async(messages, summary, events, memory, user_id, thread_id):
        """Execute summarization in background using async.
        
        Runs in the same event loop, avoiding thread safety issues.
        Creates its own store instance to avoid thread conflicts.
        """
        try:
            # Create new store instance for this async context
            memory_store = get_async_store_adapter(
                db_path=get_database_config().path
            )
            
            mock_state = {
                "messages": serialize_messages(messages),
                "summary": summary,
                "events": [e.to_dict() for e in events],
                "memory": memory
            }
            
            result = await summarize_conversation(mock_state)
            
            if result and "summary" in result:
                new_summary = result["summary"]
                logger.info("background_summary_save", 
                    component="orchestrator", 
                    operation="saving_summary_to_store",
                    summary_preview=new_summary[:200] if new_summary else "NO_SUMMARY"
                )
                
                # Save using the new store instance (no thread issues)
                conv_config = get_conversation_config()
                namespace = (conv_config.memory_namespace_prefix, user_id)
                key = f"{STATE_KEY_PREFIX}{thread_id}"
                
                mock_state["summary"] = new_summary
                
                # Use async put instead of sync_put
                await memory_store.put(namespace, key, {
                    "state": mock_state,
                    "thread_id": thread_id,
                    "timestamp": time.time()
                })
                
        except Exception as e:
            logger.error("background_summary_error",
                component="orchestrator",
                operation="background_summary",
                error=str(e),
                error_type=type(e).__name__
            )
    
    async def _run_background_memory_async(messages, summary, events, memory, user_id):
        """Execute memory extraction in background using async.
        
        Runs in the same event loop, avoiding thread safety issues.
        Creates its own store instance to avoid thread conflicts.
        """
        try:
            # Create new store instance for this async context
            memory_store = get_async_store_adapter(
                db_path=get_database_config().path
            )
            mock_state = {
                "messages": serialize_messages(messages),
                "summary": summary,
                "events": [e.to_dict() for e in events],
                "memory": memory
            }
            conv_config = get_conversation_config()
            mock_config = {"configurable": {"user_id": user_id}}
            
            result = await memorize_records(mock_state, mock_config)
            
            # memorize_records already saves to the store
            logger.info("background_memory_complete",
                component="orchestrator",
                operation="background_memory",
                success=True
            )
            
        except Exception as e:
            logger.error("background_memory_error",
                component="orchestrator",
                operation="background_memory",
                error=str(e),
                error_type=type(e).__name__
            )
    
    # Keep the old thread-based functions for backward compatibility, but deprecated
    def _run_background_summary(messages, summary, events, memory, user_id, thread_id):
        """Execute summarization in background thread and save to store.
        
        Creates new event loop for async execution in thread context.
        Saves summary directly to the persistent store.
        """
        try:
            mock_state = {
                "messages": serialize_messages(messages),
                "summary": summary,
                "events": [e.to_dict() for e in events],
                "memory": memory
            }
            mock_config = {"configurable": {"user_id": user_id, "thread_id": thread_id}}
            import asyncio
            result = asyncio.run(summarize_conversation(mock_state))
            
            if result and "summary" in result:
                new_summary = result["summary"]
                logger.info("background_summary_save".lower(), component="orchestrator", operation="saving_summary_to_store",
                                        summary_preview=new_summary[:200] if new_summary else "NO_SUMMARY")
                
                # Save the entire state to the persistent store using thread_id as key
                conv_config = get_conversation_config()
                namespace = (conv_config.memory_namespace_prefix, user_id)
                key = f"{STATE_KEY_PREFIX}{thread_id}"  # Store full state with thread_id
                
                # Update mock_state with the new summary
                mock_state["summary"] = new_summary
                
                # Use the global memory store which now handles thread-local connections
                memory_store.sync_put(namespace, key, {
                    "state": mock_state,
                    "thread_id": thread_id,
                    "timestamp": time.time()
                })
                
        except Exception as e:
            import traceback
            logger.info("background_summary_error".lower(), component="orchestrator", error=str(e),
                                     traceback=traceback.format_exc()[:500])
    
    def _run_background_memory(messages, summary, events, memory):
        """Execute memory extraction in background thread.
        
        Analyzes tool messages for structured data extraction.
        Creates new event loop for async execution.
        """
        try:
            # Convert messages to serializable format using centralized utility
            mock_state = {
                "messages": serialize_messages(messages),
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
            logger.info("background_memory_error".lower(), component="orchestrator", error=str(e),
                                     traceback=traceback.format_exc()[:500])
    
    # Build graph with tool integration supporting Command pattern
    tool_node = create_tool_node(tools)
    graph_builder.add_node("tools", tool_node)
    graph_builder.add_node("conversation", orchestrator)
    
    graph_builder.set_entry_point("conversation")
    
    # Route to tools when needed
    graph_builder.add_conditional_edges(
        "conversation",
        tools_condition,
        {
            "tools": "tools",
            "__end__": END,
        }
    )
    
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
            db_path=get_database_config().path,
            max_workers=4
        )
        
        # No longer clearing summaries - each thread has its own summary
        # Thread-specific summaries are preserved across sessions
        logger.info("Initialized without clearing summaries - thread-specific summaries preserved")
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
            f"http://{LOCALHOST}:{SALESFORCE_AGENT_PORT}",  # Salesforce agent
            f"http://{LOCALHOST}:8002",  # Travel agent (future)
            f"http://{LOCALHOST}:8003",  # Expense agent (future)
            f"http://{LOCALHOST}:8004",  # HR agent (future)
            f"http://{LOCALHOST}:8005",  # OCR agent (future)
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
    
    # Setup comprehensive external logging
    init_session_tracking()
    
    # Get structured loggers
    orchestrator_logger = get_logger('orchestrator')
    
    # Setup basic logging for console output - only for user interface
    log_level = logging.WARNING
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Log session start
    orchestrator_logger.info("orchestrator_session_start",
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
    logging.getLogger('src.a2a.circuit_breaker').setLevel(logging.WARNING)
    logging.getLogger('src.utils.config').setLevel(logging.WARNING)
    logging.getLogger('src.orchestrator.agent_registry').setLevel(logging.WARNING)
    logging.getLogger('src.orchestrator.main').setLevel(logging.WARNING)
    logging.getLogger('src.a2a.protocol').setLevel(logging.WARNING)
    
    # Initialize orchestrator
    await initialize_orchestrator()
    
    # Use the default orchestrator graph
    local_graph = orchestrator_graph
    
    # Banner display
    from src.utils.helpers import animated_banner_display, display_capabilities_banner
    conv_config = get_conversation_config()
    
    if conv_config.animated_banner_enabled:
        # Animated explosion effect
        await animated_banner_display(ENTERPRISE_ASSISTANT_BANNER)
    else:
        # Simple static display
        print(ENTERPRISE_ASSISTANT_BANNER)
    
    # Get available capabilities
    stats = agent_registry.get_registry_stats()
    
    # Display the slick capabilities sub-banner
    if stats['available_capabilities']:
        await display_capabilities_banner(stats['available_capabilities'], agent_stats=stats)
    else:
        # Fallback if no agents available
        print("\n╔════════════════════════════════════════╗")
        print("║      No agents currently available     ║")
        print("║    Please check agent configuration    ║")
        print("╚════════════════════════════════════════╝\n")
    
    conv_config = get_conversation_config()
    import uuid
    current_thread_id = f"orchestrator-{str(uuid.uuid4())[:8]}"
    config = {"configurable": {"thread_id": current_thread_id, "user_id": conv_config.default_user_id}}
    
    # Create new thread entry
    active_threads = {current_thread_id: {"created": time.time(), "messages": 0}}
    namespace = (conv_config.memory_namespace_prefix, conv_config.default_user_id)
    thread_list_key = "thread_list"
    try:
        if global_memory_store:
            stored_threads = global_memory_store.sync_get(namespace, thread_list_key) or {}
            if "threads" in stored_threads:
                active_threads.update(stored_threads["threads"])
                logger.info("threads_loaded".lower(), component="orchestrator", thread_count=len(stored_threads["threads"]))
    except Exception as e:
        logger.info("thread_load_error".lower(), component="orchestrator", error=str(e))
    
    print(f"\nStarting new conversation thread: {current_thread_id}\n")
    
    while True:
        try:
            user_input = input("USER: ")
            
            logger.info("user_input_raw".lower(), component="orchestrator", input=user_input[:1000])
            
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                logger.info("user_quit", component="orchestrator")
                break
            
            # Handle special commands
            if user_input.startswith("/"):
                command_parts = user_input.split()
                command = command_parts[0].lower()
                
                if command == "/help":
                    print("\nAvailable commands:")
                    print("  /help         - Show this help message")
                    print("  /state        - Show current conversation state")
                    print("  /state -v     - Show detailed state with raw data")
                    print("  /new          - Start a new conversation thread")
                    print("  /list         - List all conversation threads")
                    print("  /switch <id>  - Switch to a different thread")
                    print("  quit/exit/q   - Exit the orchestrator\n")
                    continue
                
                elif command == "/state":
                    # Check for verbose flag
                    verbose = len(command_parts) > 1 and command_parts[1] == "-v"
                    
                    print("\n=== Current Conversation State ===")
                    try:
                        # Get current state from the graph
                        current_state = local_graph.get_state(config)
                        
                        # Format state for display
                        print(f"Thread ID: {current_thread_id}")
                        print(f"User ID: {config['configurable']['user_id']}")
                        
                        # Try to get state from checkpointer first, then fallback to storage
                        state_values = None
                        if current_state and current_state.values:
                            state_values = current_state.values
                        else:
                            # Try loading from storage
                            if global_memory_store:
                                namespace = (conv_config.memory_namespace_prefix, conv_config.default_user_id)
                                key = f"state_{current_thread_id}"
                                stored_state = global_memory_store.sync_get(namespace, key)
                                if stored_state and "state" in stored_state:
                                    state_values = stored_state["state"]
                                    print("[Loaded from storage]")
                        
                        if state_values:
                            print(f"\nMessages: {len(state_values.get('messages', []))}")
                            
                            # Show summary if available
                            summary = state_values.get('summary', 'No summary available')
                            if summary and summary != 'No summary available':
                                print(f"\nSummary Preview (first 200 chars):")
                                print(f"  {summary[:200]}...")
                            
                            # Show memory if available
                            memory = state_values.get('memory', {})
                            if memory and isinstance(memory, dict):
                                simple_memory = memory.get('SimpleMemory', {})
                                if simple_memory:
                                    print(f"\nMemory Contents:")
                                    for key, value in simple_memory.items():
                                        if isinstance(value, list) and value:
                                            print(f"  {key}: {len(value)} items")
                                            # Show first few items if verbose
                                            if verbose and len(value) > 0:
                                                print(f"    First item: {str(value[0])[:100]}...")
                            
                            # Show events count
                            events = state_values.get('events', [])
                            print(f"\nEvents: {len(events)}")
                            if verbose and events:
                                print("  Recent events:")
                                for event in events[-3:]:  # Show last 3 events
                                    # Handle both dict and object formats
                                    if isinstance(event, dict):
                                        event_type = event.get('event_type', 'Unknown')
                                    else:
                                        event_type = getattr(event, 'event_type', 'Unknown')
                                    print(f"    - {event_type}")
                            
                            # Show last message
                            messages = state_values.get('messages', [])
                            if messages:
                                last_msg = messages[-1]
                                msg_type = type(last_msg).__name__
                                content_preview = str(getattr(last_msg, 'content', ''))[:100]
                                print(f"\nLast Message ({msg_type}):")
                                print(f"  {content_preview}...")
                            
                            # Show background operations status
                            bg_ops = state_values.get('background_operations', [])
                            if bg_ops:
                                print(f"\nBackground Operations: {len(bg_ops)} active")
                            
                            # Show raw state if verbose
                            if verbose:
                                print("\n=== Raw State Keys ===")
                                for key in state_values.keys():
                                    print(f"  - {key}")
                                print("\nTip: Use '/state' without -v for a simpler view")
                        else:
                            print("No state data available for this thread.")
                    except Exception as e:
                        print(f"Error retrieving state: {e}")
                    print("\n")
                    continue
                
                elif command == "/new":
                    # Create new thread
                    import uuid
                    new_thread_id = f"orchestrator-{str(uuid.uuid4())[:8]}"
                    current_thread_id = new_thread_id
                    config = {"configurable": {"thread_id": current_thread_id, "user_id": conv_config.default_user_id}}
                    active_threads[current_thread_id] = {"created": time.time(), "messages": 0}
                    
                    # Save thread metadata to store
                    namespace = (conv_config.memory_namespace_prefix, conv_config.default_user_id)
                    thread_list_key = "thread_list"
                    try:
                        if global_memory_store:
                            # Load existing thread list
                            existing_threads = global_memory_store.sync_get(namespace, thread_list_key) or {}
                            thread_list = existing_threads.get("threads", {})
                            
                            # Add new thread
                            thread_list[current_thread_id] = {
                                "created": time.time(),
                                "last_accessed": time.time(),
                                "messages": 0
                            }
                            
                            # Save updated list
                            global_memory_store.sync_put(namespace, thread_list_key, {
                                "threads": thread_list,
                                "updated": time.time()
                            })
                    except Exception as e:
                        logger.info("thread_save_error".lower(), component="orchestrator", error=str(e))
                    
                    print(f"\nStarted new conversation thread: {current_thread_id}\n")
                    logger.info("new_thread_created".lower(), component="orchestrator", thread_id=current_thread_id)
                    continue
                
                elif command == "/list":
                    print("\n=== Active Conversation Threads ===")
                    
                    # Load threads from storage - try multiple approaches
                    namespace = (conv_config.memory_namespace_prefix, conv_config.default_user_id)
                    all_threads = {}
                    
                    try:
                        # Approach 1: Load from thread list
                        thread_list_key = "thread_list"
                        if global_memory_store:
                            stored_threads = global_memory_store.sync_get(namespace, thread_list_key) or {}
                            if "threads" in stored_threads:
                                all_threads.update(stored_threads.get("threads", {}))
                        
                        # Approach 2: Scan for all keys with summary_ prefix to find threads
                        # This catches threads that might not be in the thread list
                        if global_memory_store:
                            from src.utils.storage.sqlite_store import SQLiteStore
                            if hasattr(global_memory_store, '_store') and isinstance(global_memory_store._store, SQLiteStore):
                                # Direct database query to find all summary keys
                                import sqlite3
                                conn = sqlite3.connect(global_memory_store._store.db_path)
                                cursor = conn.cursor()
                                cursor.execute(
                                    "SELECT key, value FROM store WHERE namespace = ? AND key LIKE 'state_%'",
                                    (str(namespace),)
                                )
                                for row in cursor.fetchall():
                                    key = row[0]
                                    if key.startswith("state_"):
                                        thread_id = key[6:]  # Remove 'state_' prefix
                                        if thread_id not in all_threads:
                                            # Try to get state info
                                            state_data = global_memory_store.sync_get(namespace, key)
                                            if state_data:
                                                all_threads[thread_id] = {
                                                    "created": state_data.get("timestamp", 0),
                                                    "messages": len(state_data.get("state", {}).get("messages", [])) if "state" in state_data else 0,
                                                    "has_summary": bool(state_data.get("state", {}).get("summary")),
                                                    "from_storage": True
                                                }
                                conn.close()
                        
                        # Merge with active threads (current session)
                        for thread_id, info in active_threads.items():
                            if thread_id in all_threads:
                                # Update with more recent info
                                all_threads[thread_id].update(info)
                            else:
                                all_threads[thread_id] = info
                        
                        # Check which threads have state/summaries
                        if global_memory_store:
                            for thread_id in all_threads:
                                if not all_threads[thread_id].get("has_summary"):
                                    state_key = f"state_{thread_id}"
                                    stored_state = global_memory_store.sync_get(namespace, state_key)
                                    all_threads[thread_id]["has_summary"] = bool(stored_state and "state" in stored_state and stored_state["state"].get("summary"))
                        
                        # Display threads sorted by creation time
                        sorted_threads = sorted(all_threads.items(), key=lambda x: x[1].get('created', 0), reverse=True)
                        
                        for thread_id, info in sorted_threads:
                            created_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(info.get('created', 0)))
                            current_marker = " (current)" if thread_id == current_thread_id else ""
                            summary_marker = " [S]" if info.get("has_summary", False) else ""
                            messages = info.get('messages', '?')
                            storage_marker = " [stored]" if info.get('from_storage') else ""
                            print(f"  {thread_id}: created {created_time}, {messages} messages{summary_marker}{storage_marker}{current_marker}")
                        
                        if not all_threads:
                            print("  No threads found.")
                        else:
                            print("\n  [S] = Has saved summary, [stored] = From persistent storage")
                            print("  Use /switch <thread_id> to resume a conversation")
                    except Exception as e:
                        print(f"  Error loading threads: {e}")
                        # Fallback to just showing current thread
                        print(f"  {current_thread_id}: current session (active)")
                    
                    print()
                    continue
                
                elif command == "/switch":
                    if len(command_parts) < 2:
                        print("Usage: /switch <thread_id>")
                        continue
                    
                    target_thread = command_parts[1]
                    
                    # Always allow switching - thread might be in storage
                    current_thread_id = target_thread
                    config = {"configurable": {"thread_id": current_thread_id, "user_id": conv_config.default_user_id}}
                    
                    # Check if thread exists in storage
                    thread_found = target_thread in active_threads
                    if not thread_found and global_memory_store:
                        namespace = (conv_config.memory_namespace_prefix, conv_config.default_user_id)
                        state_key = f"state_{target_thread}"
                        stored_state = global_memory_store.sync_get(namespace, state_key)
                        if stored_state:
                            thread_found = True
                            # Add to active threads
                            active_threads[target_thread] = {
                                "created": stored_state.get("timestamp", time.time()),
                                "messages": len(stored_state.get("state", {}).get("messages", [])) if "state" in stored_state else 0,
                                "from_storage": True
                            }
                    
                    if thread_found:
                        print(f"\nSwitched to thread: {current_thread_id}\n")
                        logger.info("thread_switched".lower(), component="orchestrator", thread_id=current_thread_id)
                    else:
                        print(f"\nStarting new thread: {current_thread_id}\n")
                        active_threads[current_thread_id] = {"created": time.time(), "messages": 0}
                        logger.info("new_thread_created".lower(), component="orchestrator", thread_id=current_thread_id)
                    continue
                
                else:
                    print(f"Unknown command: {command}. Type /help for available commands.")
                    continue
            
            # Validate input for security
            try:
                from src.utils.input_validation import validate_orchestrator_input, ValidationError
                validated_input = validate_orchestrator_input(user_input)
                user_input = validated_input
            except ValidationError as e:
                # Handle validation errors with more specific messaging
                error_message = str(e)
                
                # Special handling for empty input - make it conversational
                if "empty input" in error_message.lower():
                    from src.utils.helpers import type_out_sync, get_empty_input_response
                    print("\nASSISTANT: ", end="", flush=True)
                    # Get a varied response and type it out naturally
                    response = get_empty_input_response()
                    type_out_sync(response, delay=0.015)  # Slightly faster for snappier feel
                    print()  # New line after message
                elif "too long" in error_message.lower():
                    print(f"\n❌ Input Error: Your message is too long. Please keep it under 50,000 characters.")
                elif "malicious content" in error_message.lower():
                    print(f"\n❌ Security Error: Your input contains potentially harmful content and cannot be processed.")
                else:
                    print(f"\n❌ Validation Error: {error_message}")
                    
                logger.info("validation_error".lower(), component="orchestrator", error_type="user_input",
                                        error_message=error_message,
                                        input_length=len(user_input))
                continue
            except Exception as e:
                # Catch any other unexpected errors during validation
                print(f"\n❌ Unexpected error during input validation: {e}")
                logger.error(f"Unexpected validation error: {type(e).__name__}: {e}")
                continue
            
            print("\nASSISTANT: ", end="", flush=True)
            
            # Show processing indicator
            import threading
            processing_done = threading.Event()
            
            def show_processing_indicator():
                """Show a blinking sparkle emoji while processing"""
                frames = ["✨", " "]
                i = 0
                while not processing_done.is_set():
                    # Position after "ASSISTANT: "
                    print(f"\rASSISTANT: {frames[i % 2]} ", end="", flush=True)
                    time.sleep(0.5)
                    i += 1
                # Clear the indicator and reset cursor
                print("\rASSISTANT: ", end="", flush=True)
            
            # Start indicator in background thread
            indicator_thread = threading.Thread(target=show_processing_indicator)
            indicator_thread.daemon = True
            indicator_thread.start()
            
            # Stream response immediately
            conversation_response = None
            response_shown = False
            
            async for event in local_graph.astream(
                {
                    "messages": [{"role": "user", "content": user_input}],
                    "background_operations": [],
                    "background_results": {}
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
                            # Stop the processing indicator
                            processing_done.set()
                            indicator_thread.join(timeout=1.0)
                            
                            conversation_response = last_msg.content
                            logger.info("user_message_displayed".lower(), component="orchestrator", response=conversation_response[:1000],
                                                    full_length=len(conversation_response))
                            await type_out(conversation_response, delay=0.01)
                            response_shown = True
                            print("\n")
                            # Continue processing for background tasks
            
            if not response_shown:
                # Stop the indicator if still running
                processing_done.set()
                indicator_thread.join(timeout=1.0)
                print("Processing your request...\n")
            
            # Update message count for current thread and save to storage
            if current_thread_id in active_threads:
                active_threads[current_thread_id]["messages"] += 1
                active_threads[current_thread_id]["last_accessed"] = time.time()
                
                # Update thread list in storage - merge with existing
                try:
                    if global_memory_store:
                        namespace = (conv_config.memory_namespace_prefix, conv_config.default_user_id)
                        thread_list_key = "thread_list"
                        
                        # Retry logic for thread list updates (non-critical)
                        max_retries = 3
                        for attempt in range(max_retries):
                            try:
                                # Load existing threads
                                existing = global_memory_store.sync_get(namespace, thread_list_key) or {}
                                all_stored_threads = existing.get("threads", {})
                                
                                # Update with current thread info
                                all_stored_threads[current_thread_id] = active_threads[current_thread_id]
                                
                                # Save merged list
                                global_memory_store.sync_put(namespace, thread_list_key, {
                                    "threads": all_stored_threads,
                                    "updated": time.time()
                                })
                                break  # Success, exit retry loop
                                
                            except Exception as e:
                                if "readonly database" in str(e) and attempt < max_retries - 1:
                                    # Database is busy, wait and retry
                                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                                    continue
                                elif attempt == max_retries - 1:
                                    # Log only on final failure
                                    logger.debug("thread_list_update_failed", 
                                        component="orchestrator", 
                                        error=str(e),
                                        attempts=attempt + 1,
                                        info="Non-critical - thread list is for UI only"
                                    )
                                    break
                except Exception as e:
                    # Outer exception handler for unexpected errors
                    logger.debug("thread_update_error", 
                        component="orchestrator", 
                        error=str(e),
                        info="Non-critical - thread list is for UI only"
                    )
                        
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