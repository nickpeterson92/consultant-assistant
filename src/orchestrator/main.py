"""Multi-agent orchestrator implementation using LangGraph.

This module serves as the central coordination hub for the consultant assistant system,
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
import json
import asyncio
import argparse
import time
from typing import Annotated, Dict, Any, List
import operator
from typing_extensions import TypedDict

from dotenv import load_dotenv

from src.utils.logging import get_logger, get_performance_tracker, get_cost_tracker, init_session_tracking

from trustcall import create_extractor

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from langgraph.graph.message import RemoveMessage, add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import Send

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import AzureChatOpenAI


from .agent_registry import AgentRegistry
from .agent_caller_tools import SalesforceAgentTool, GenericAgentTool, AgentRegistryTool
from src.utils.helpers import type_out, smart_preserve_messages
from src.utils.storage import get_async_store_adapter
from src.utils.storage.memory_schemas import SimpleMemory
from src.utils.logging import get_summary_logger
from .enhanced_sys_msg import orchestrator_chatbot_sys_msg, orchestrator_summary_sys_msg
from src.utils.config import get_llm_config
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
    
    def invoke_llm(messages, use_tools=False):
        """Invoke LLM with optional tool binding.
        
        Azure OpenAI automatically caches prompts for efficiency.
        
        Args:
            messages: List of conversation messages
            use_tools: Whether to bind tools for function calling
            
        Returns:
            AI response message with optional tool calls
        """
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
            
            # Track events instead of turns
            events = [OrchestratorEvent.from_dict(e) for e in state.get('events', [])]
            
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
            
            
            summary = state.get("summary", "No summary available")
            
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
            
            log_orchestrator_activity("LLM_RESPONSE", 
                                     response_length=len(response_content),
                                     response_content=response_content[:500],  # Truncate for readability
                                     has_tool_calls=bool(hasattr(response, 'tool_calls') and response.tool_calls),
                                     event_count=len(events))
            
            log_cost_activity("ORCHESTRATOR_LLM", estimated_tokens,
                            message_count=len(messages),
                            event_count=len(events))
            
            # Convert events back to dicts for state storage
            event_dicts = [e.to_dict() for e in events]
            
            updated_state = {
                "messages": response,
                "memory": existing_memory,
                "events": event_dicts  # Store event history
            }
            
            # Trigger background tasks based on events
            from src.utils.config import get_conversation_config
            conv_config = get_conversation_config()
            
            # Check if we should trigger summary based on events
            if EventAnalyzer.should_trigger_summary(events, 
                                                   user_message_threshold=5,
                                                   time_threshold_seconds=300):
                
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
                import threading
                threading.Thread(
                    target=_run_background_summary,
                    args=(state["messages"], state.get("summary", ""), events, existing_memory),
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
        events = [OrchestratorEvent.from_dict(e) for e in state.get('events', [])]
        
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
        
        response = invoke_llm(messages, use_tools=False)
        
        # Smart preservation maintains tool call/response integrity
        messages_to_preserve = smart_preserve_messages(state["messages"], keep_count=3)
        messages_to_delete = []
        
        # Mark non-preserved messages for deletion
        preserved_ids = {getattr(msg, 'id', None) for msg in messages_to_preserve if hasattr(msg, 'id')}
        for msg in state["messages"]:
            if hasattr(msg, 'id') and msg.id not in preserved_ids:
                messages_to_delete.append(RemoveMessage(id=msg.id))
        
        response_content = str(response.content) if hasattr(response, 'content') else ""
        log_orchestrator_activity("LLM_RESPONSE", 
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
            new_summary=response.content,
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
            "summary": response.content,
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
        
        user_id = config["configurable"].get("user_id", "default")
        namespace = ("memory", user_id)
        key = "SimpleMemory"
        
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
        extraction_content = f"CONVERSATION SUMMARY:\n{summary_content}\n\n"
        
        if recent_tool_responses:
            extraction_content += "RECENT SALESFORCE TOOL RESPONSES WITH DATA TO EXTRACT:\n"
            for i, response in enumerate(recent_tool_responses):
                extraction_content += f"\nTool Response {i+1}:\n{response}\n"
        else:
            extraction_content += "No recent tool responses found."
        
        # Invoke TrustCall with timeout for background safety
        try:
            from src.utils.config import get_llm_config
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
    
    async def background_summary(state: OrchestratorState, config: RunnableConfig):
        """Background task for conversation summarization.
        
        Runs asynchronously to avoid blocking main conversation flow.
        Tracks completion status for monitoring.
        """
        try:
            result = await summarize_conversation(state)
            # Add background operation tracking
            result["background_operations"] = ["summary_completed"]
            result["background_results"] = {"summary_time": time.time()}
            return result
        except Exception as e:
            logger.error(f"Background summary failed: {e}")
            return {
                "background_operations": ["summary_failed"], 
                "background_results": {"summary_error": str(e)}
            }
    
    async def background_memory(state: OrchestratorState, config: RunnableConfig):
        """Background task for memory extraction.
        
        Runs asynchronously to extract and persist structured data
        without blocking conversation flow.
        """
        try:
            result = await memorize_records(state, config)
            # Add background operation tracking
            result["background_operations"] = ["memory_completed"]
            result["background_results"] = {"memory_time": time.time()}
            return result
        except Exception as e:
            logger.error(f"Background memory failed: {e}")
            return {
                "background_operations": ["memory_failed"],
                "background_results": {"memory_error": str(e)}
            }
    
    # Note: Background tasks (summary and memory) are triggered directly in the orchestrator function
    # using fire-and-forget threads based on event analysis, not through graph edges.
    
    def _run_background_summary(messages, summary, events, memory):
        """Execute summarization in background thread.
        
        Creates new event loop for async execution in thread context.
        Logs progress and errors for monitoring.
        """
        try:
            mock_state = {
                "messages": messages,
                "summary": summary,
                "events": [e.to_dict() for e in events],
                "memory": memory
            }
            mock_config = {"configurable": {"user_id": "user-1"}}
            import asyncio
            result = asyncio.run(background_summary(mock_state, mock_config))
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
            mock_config = {"configurable": {"user_id": "user-1"}}
            import asyncio
            result = asyncio.run(background_memory(mock_state, mock_config))
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
    
    config = {"configurable": {"thread_id": "orchestrator-1", "user_id": "user-1"}}
    
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
                            log_orchestrator_activity("ASSISTANT_RESPONSE", 
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