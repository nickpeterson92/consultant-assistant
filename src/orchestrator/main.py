"""
Orchestrator Agent - Main LangGraph Implementation
Coordinates communication between user and specialized agents via A2A protocol
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

# Add logging configuration
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

# Imports no longer need path manipulation

from .agent_registry import AgentRegistry
from .agent_caller_tools import SalesforceAgentTool, GenericAgentTool, AgentRegistryTool
from src.utils.helpers import type_out, smart_preserve_messages
from src.utils.storage import get_async_store_adapter
from src.utils.storage.memory_schemas import SimpleMemory
from src.utils.logging import get_summary_logger
# Removed custom caching - Azure OpenAI provides automatic prompt caching for GPT-4o/4o-mini
from .enhanced_sys_msg import orchestrator_chatbot_sys_msg, orchestrator_summary_sys_msg
from src.utils.config import get_llm_config
from src.utils.sys_msg import TRUSTCALL_INSTRUCTION

import logging


# Disable LangSmith tracing to avoid circular reference errors
os.environ["LANGCHAIN_TRACING_V2"] = "false"


# Import centralized logging
from src.utils.logging import log_orchestrator_activity, log_cost_activity

# Logging functions now imported from centralized activity_logger


logger = logging.getLogger(__name__)

# State management now handled by LangGraph + SQLiteStore + A2A protocol
agent_registry = AgentRegistry()

def create_azure_openai_chat():
    """Create Azure OpenAI chat instance using global config"""
    llm_config = get_llm_config()
    return AzureChatOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],  # Keep sensitive info in env
        azure_deployment=llm_config.azure_deployment,
        openai_api_version=llm_config.api_version,
        openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],  # Keep sensitive info in env
        temperature=llm_config.temperature,
        max_tokens=llm_config.max_tokens,
        timeout=llm_config.timeout,
    )

def build_orchestrator_graph(debug_mode: bool = False):
    """Build and compile the orchestrator LangGraph"""
    
    load_dotenv()
    
    # Define the orchestrator state schema (with legacy memory support)
    class OrchestratorState(TypedDict):
        messages: Annotated[list, add_messages]
        summary: str  # Using legacy name for compatibility
        memory: dict  # Using legacy structured memory
        turns: int
        active_agents: List[str]
        last_agent_interaction: Dict[str, Any]
        # Add fields for parallel background operations
        background_operations: Annotated[List[str], operator.add]
        background_results: Annotated[Dict[str, Any], lambda x, y: {**x, **y}]
        last_summarized_turn: int
        # Background tasks now run as fire-and-forget threads
    
    memory = MemorySaver()
    # Use enhanced async store adapter with performance monitoring and resilience
    memory_store = get_async_store_adapter(
        db_path="memory_store.db",
        use_async=False,  # Use thread pool adapter for reliability
        max_workers=4,
        max_connections=10,
        enable_circuit_breaker=True
    )
    
    # Removed custom LLM cache - Azure OpenAI now provides automatic prompt caching
    
    graph_builder = StateGraph(OrchestratorState)
    
    # Initialize orchestrator tools
    tools = [
        SalesforceAgentTool(agent_registry, debug_mode),
        GenericAgentTool(agent_registry),
        AgentRegistryTool(agent_registry)
    ]
    
    llm = create_azure_openai_chat()
    llm_with_tools = llm.bind_tools(tools)
    # Enhanced TrustCall configuration following best practices
    # SIMPLE: TrustCall extractor with flat schema to avoid patch conflicts
    trustcall_extractor = create_extractor(
        llm,
        tools=[SimpleMemory],
        tool_choice="SimpleMemory",  # Explicit choice prevents conflicts
        enable_inserts=True  # Enable new record creation
    )
    
    # Direct LLM invocation - Azure OpenAI handles caching automatically
    def invoke_llm(messages, use_tools=False):
        """Invoke LLM directly - Azure OpenAI provides automatic prompt caching"""
        if use_tools:
            return llm_with_tools.invoke(messages)
        else:
            return llm.invoke(messages)
    
    
    # Enhanced system message using merged legacy + orchestrator approach
    def get_orchestrator_system_message(state: OrchestratorState) -> str:
        summary = state.get("summary", "No summary available")
        memory_val = state.get("memory", "No memory available")
        active_agents = state.get("active_agents", [])
        
        # Get registry stats for context
        registry_stats = agent_registry.get_registry_stats()
        
        # Build agent context information
        agent_context = f"""AVAILABLE SPECIALIZED AGENTS:
{', '.join(registry_stats['available_capabilities']) if registry_stats['available_capabilities'] else 'None currently available'}

CURRENTLY ACTIVE AGENTS: {', '.join(active_agents) if active_agents else 'None'}

ORCHESTRATOR TOOLS:
1. salesforce_agent: For Salesforce CRM operations (leads, accounts, opportunities, contacts, cases, tasks)
2. call_agent: For general agent calls (travel, expenses, HR, OCR, etc.)
3. manage_agents: To check agent status and capabilities"""
        
        # Use the enhanced orchestrator system message
        return orchestrator_chatbot_sys_msg(summary, memory_val, agent_context)
    
    # Node function: orchestrator (main conversation handler)
    async def orchestrator(state: OrchestratorState, config: RunnableConfig):
        """Main orchestrator node that coordinates with specialized agents"""
        try:
            # Track when orchestrator is called
            msg_count = len(state.get('messages', []))
            last_msg = state.get('messages', [])[-1] if state.get('messages') else None
            
            # Log message based on type - distinguish user vs AI messages
            if hasattr(last_msg, 'content'):
                from langchain_core.messages import HumanMessage, AIMessage
                if isinstance(last_msg, HumanMessage):
                    log_orchestrator_activity("USER_REQUEST", 
                                             message=str(last_msg.content)[:200],
                                             message_count=msg_count,
                                             turn=state.get('turns', 0))
                elif isinstance(last_msg, AIMessage):
                    log_orchestrator_activity("AI_RESPONSE_PROCESSING", 
                                             message=str(last_msg.content)[:200],
                                             message_count=msg_count,
                                             turn=state.get('turns', 0))
            
            if debug_mode:
                last_type = type(last_msg).__name__ if last_msg else "None"
                
                # Check for potential duplicate scenario
                if last_type == "AIMessage" and hasattr(last_msg, 'content') and last_msg.content:
                    logger.warning(f"DUPLICATE CHECK: Orchestrator called with AIMessage response already present")
                    logger.warning(f"  Message count: {msg_count}, Turn: {state.get('turns', 0)}")
                    logger.warning(f"  Last message preview: {str(last_msg.content)[:100]}...")
            
            # Load and manage memory like legacy system
            summary = state.get("summary", "No summary available")
            turn = state.get("turns", 0)
            
            # SIMPLE: Load memory from store using flat schema
            user_id = config["configurable"].get("user_id", "default")
            namespace = ("memory", user_id)
            key = "SimpleMemory"
            existing_memory_data = memory_store.sync_get(namespace, key)
            
            if existing_memory_data:
                try:
                    # Simple validation with flat schema
                    validated_data = SimpleMemory(**existing_memory_data)
                    existing_memory = {"SimpleMemory": validated_data.model_dump()}
                    total_records = (len(validated_data.accounts) + len(validated_data.contacts) + 
                                   len(validated_data.opportunities) + len(validated_data.cases) + 
                                   len(validated_data.tasks) + len(validated_data.leads))
                    if debug_mode:
                        logger.info(f"Loaded existing memory with {total_records} total records")
                except Exception as e:
                    if debug_mode:
                        logger.warning(f"Existing memory data invalid, using fresh schema: {e}")
                    existing_memory = {"SimpleMemory": SimpleMemory().model_dump()}
            else:
                existing_memory = {"SimpleMemory": SimpleMemory().model_dump()}
                if debug_mode:
                    logger.info("No existing memory found, using fresh schema")
            
            # Update state with loaded memory BEFORE creating system message
            state["memory"] = existing_memory
            
            # Create system message with current context (now including loaded memory)
            system_message = get_orchestrator_system_message(state)
            messages = [SystemMessage(content=system_message)] + state["messages"]
            
            # Check if we already have tool results that answer the user's question
            recent_tool_results = []
            for msg in reversed(state.get("messages", [])):
                if hasattr(msg, 'name') and getattr(msg, 'name', None) in ['salesforce_agent', 'call_agent']:
                    recent_tool_results.append(msg)
                    if len(recent_tool_results) >= 2:  # Stop after finding recent results
                        break
            
            # No need to clean orphaned tool calls - smart preservation prevents them
            response = invoke_llm(messages, use_tools=True)
            
            # Log tool calls if present
            if hasattr(response, 'tool_calls') and response.tool_calls:
                for tool_call in response.tool_calls:
                    log_orchestrator_activity("TOOL_CALL",
                                             tool_name=tool_call.get('name', 'unknown'),
                                             tool_args=tool_call.get('args', {}),
                                             turn=state.get('turns', 0))
            
            # Log LLM response and cost
            response_content = str(response.content) if hasattr(response, 'content') else ""
            log_orchestrator_activity("LLM_RESPONSE", 
                                     response_length=len(response_content),
                                     response_content=response_content[:500],  # Truncate for readability
                                     has_tool_calls=bool(hasattr(response, 'tool_calls') and response.tool_calls),
                                     turn=state.get('turns', 0))
            
            # Log token usage for cost tracking
            message_chars = sum(len(str(m.content if hasattr(m, 'content') else m)) for m in messages)
            response_chars = len(str(response.content)) if hasattr(response, 'content') else 0
            estimated_tokens = (message_chars + response_chars) // 4
            log_cost_activity("ORCHESTRATOR_LLM", estimated_tokens,
                            message_count=len(messages),
                            turn=state.get('turns', 0))
            
            # Update orchestrator state and check for background tasks
            turn = state.get("turns", 0)
            new_turn = turn + 1
            
            # Return immediate response and fire background tasks asynchronously
            updated_state = {
                "messages": response,
                "memory": existing_memory,
                "turns": new_turn
            }
            
            # Fire-and-forget background tasks (don't block response)
            if len(state["messages"]) >= 6 and new_turn % 3 == 0:
                if debug_mode:
                    logger.info(f"Starting fire-and-forget summary task for turn {new_turn}")
                log_orchestrator_activity("SUMMARY_TRIGGER", 
                                        message_count=len(state["messages"]), 
                                        turn=new_turn)
                # Run summary in background thread without blocking
                import threading
                threading.Thread(
                    target=_run_background_summary,
                    args=(state["messages"], state.get("summary", ""), new_turn, existing_memory, debug_mode),
                    daemon=True
                ).start()
            
            if new_turn > 5:
                if debug_mode:
                    logger.info(f"Starting fire-and-forget memory task for turn {new_turn}")
                log_orchestrator_activity("MEMORY_TRIGGER",
                                        turn=new_turn,
                                        message_count=len(state["messages"]))
                # Run memory extraction in background thread without blocking
                import threading
                threading.Thread(
                    target=_run_background_memory,
                    args=(state["messages"], state.get("summary", ""), new_turn, existing_memory, debug_mode),
                    daemon=True
                ).start()
            
            return updated_state
            
        except Exception as e:
            if debug_mode:
                logger.error(f"=== ORCHESTRATOR ERROR ===")
                logger.error(f"Error type: {type(e).__name__}")
                logger.error(f"Error message: {str(e)}")
                logger.error(f"State keys: {list(state.keys())}")
                logger.error(f"Message count: {len(state.get('messages', []))}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
            else:
                logger.error(f"Error processing request: {e}")
            raise
    
    # Smart message preservation now imported from helpers
    
    # Node function: summarize_conversation (with smart preservation)
    async def summarize_conversation(state: OrchestratorState):
        """Summarize conversation using smart message preservation with cooldown protection"""
        start_time = time.time()
        messages_count = len(state.get('messages', []))
        turn = state.get('turns', 0)
        
        if debug_mode:
            logger.info(f"Summarizing conversation: {messages_count} messages, turn {turn}")
        
        # DOMINATION: Set summarization cooldown to prevent cascading
        current_state = state.copy()
        current_state["last_summarized_turn"] = turn
        
        summary = state.get("summary", "No summary available")
        memory_val = state.get("memory", "No memory available")
        
        # Log summary request
        summary_logger = get_summary_logger()
        summary_logger.log_summary_request(
            messages_count=messages_count,
            current_summary=summary,
            memory_context=memory_val,
            component="orchestrator",
            turn=turn
        )
        
        # Let TrustCall handle all data extraction from tool messages
        
        # Get recent tool responses to include in summary for TrustCall extraction
        recent_tool_responses = []
        structured_tool_data = []
        
        for msg in reversed(state["messages"][-10:]):  # Last 10 messages
            if hasattr(msg, 'name') and msg.name and any(agent in msg.name.lower() for agent in ['salesforce', 'travel', 'expense', 'hr', 'ocr']):
                content = getattr(msg, 'content', '')
                if content and len(content) > 50:  # Meaningful content
                    # Check if this message contains structured tool data
                    if "[STRUCTURED_TOOL_DATA]:" in content:
                        parts = content.split("[STRUCTURED_TOOL_DATA]:")
                        conversational_part = parts[0].strip()
                        try:
                            import json
                            structured_part = json.loads(parts[1].strip())
                            structured_tool_data.extend(structured_part)
                            # For summary, include both parts but emphasize structured data
                            enhanced_content = f"{conversational_part}\n\nDETAILED TOOL RESULTS WITH REAL IDS:\n{json.dumps(structured_part, indent=2)}"
                            recent_tool_responses.append(enhanced_content[:1500])
                        except (json.JSONDecodeError, IndexError):
                            # Fallback to regular content
                            recent_tool_responses.append(content[:1000])
                    else:
                        recent_tool_responses.append(content[:1000])  # Truncate long responses
        
        # Use enhanced orchestrator summary system message
        system_message = orchestrator_summary_sys_msg(summary, memory_val)
        
        # Enhance the summary prompt to include recent tool responses
        if recent_tool_responses:
            system_message += f"\n\nRECENT AGENT TOOL RESPONSES (include relevant details and IDs in summary):\n"
            for i, response in enumerate(recent_tool_responses[-3:]):  # Last 3 responses
                system_message += f"\nResponse {i+1}:\n{response}\n"
        messages = [SystemMessage(content=system_message)] + state["messages"]
        
        response = invoke_llm(messages, use_tools=False)
        
        # Use smart preservation instead of simple slice
        messages_to_preserve = smart_preserve_messages(state["messages"], keep_count=3)
        messages_to_delete = []
        
        # DEBUG: Detailed preservation analysis
        if debug_mode:
            logger.warning("=== SMART PRESERVATION DEBUG ===")
            logger.warning(f"Total messages before: {len(state['messages'])}")
            logger.warning(f"Messages to preserve: {len(messages_to_preserve)}")
            for i, msg in enumerate(messages_to_preserve):
                msg_type = type(msg).__name__
                if msg_type == "AIMessage" and hasattr(msg, 'tool_calls') and msg.tool_calls:
                    logger.warning(f"  Preserved {i}: {msg_type} with {len(msg.tool_calls)} tool calls")
                elif msg_type == "ToolMessage":
                    logger.warning(f"  Preserved {i}: {msg_type} (call_id: {getattr(msg, 'tool_call_id', 'unknown')})")
                else:
                    logger.warning(f"  Preserved {i}: {msg_type}")
        
        # Find messages that are NOT in the preserved list
        preserved_ids = {getattr(msg, 'id', None) for msg in messages_to_preserve if hasattr(msg, 'id')}
        for msg in state["messages"]:
            if hasattr(msg, 'id') and msg.id not in preserved_ids:
                messages_to_delete.append(RemoveMessage(id=msg.id))
        
        if debug_mode:
            logger.info(f"Summary complete: deleting {len(messages_to_delete)}, preserving {len(messages_to_preserve)}")
            logger.warning("=== END PRESERVATION DEBUG ===")
        
        # Log the actual summary response (after message preservation)
        response_content = str(response.content) if hasattr(response, 'content') else ""
        log_orchestrator_activity("LLM_RESPONSE", 
                                 response_length=len(response_content),
                                 response_content=response_content[:500],  # Truncate for readability
                                 operation="SUMMARIZATION",
                                 turn=turn)
        
        # Estimate and log token usage with CORRECTED message count (after preservation)
        message_chars = sum(len(str(m.content if hasattr(m, 'content') else m)) for m in messages)
        estimated_tokens = message_chars // 4  # Rough estimate: 4 chars per token
        log_cost_activity("ORCHESTRATOR_LLM_CALL", estimated_tokens,
                         message_count=len(messages_to_preserve),  # FIXED: Use preserved count, not original
                         response_length=len(str(response.content)) if hasattr(response, 'content') else 0,
                         turn=turn)
        
        # Log summary response
        processing_time = time.time() - start_time
        summary_logger.log_summary_response(
            new_summary=response.content,
            messages_preserved=len(messages_to_preserve),
            messages_deleted=len(messages_to_delete),
            component="orchestrator",
            turn=turn,
            processing_time=processing_time
        )
        
        return {
            "summary": response.content,
            "messages": messages_to_delete,
            "last_summarized_turn": state.get("turns", 0)  # Track when we last summarized
        }
    
    # SIMPLE: Simplified memory extraction with flat schema
    async def memorize_records(state: OrchestratorState, config: RunnableConfig):
        """Simple memory extraction using flat schema"""
        if debug_mode:
            logger.info("Updating memory with simplified approach")
        
        user_id = config["configurable"].get("user_id", "default")
        namespace = ("memory", user_id)
        key = "SimpleMemory"
        
        # SIMPLE: Get existing memory in TrustCall-friendly format
        try:
            stored = memory_store.sync_get(namespace, key)
            if stored:
                existing_records = {"SimpleMemory": stored}
            else:
                existing_records = {"SimpleMemory": SimpleMemory().model_dump()}
        except:
            existing_records = {"SimpleMemory": SimpleMemory().model_dump()}
        
        # FIX: Extract Salesforce data from actual tool messages, not just summary
        recent_tool_responses = []
        messages = state.get("messages", [])
        
        # Log memory extraction start
        log_orchestrator_activity("MEMORY_EXTRACTION_START",
                                message_count=len(messages),
                                user_id=user_id)
        
        # Get recent tool responses containing Salesforce data (same logic as summarize_conversation)
        for msg in reversed(messages[-10:]):  # Last 10 messages
            if hasattr(msg, 'name') and msg.name and any(agent in msg.name.lower() for agent in ['salesforce', 'travel', 'expense', 'hr', 'ocr']):
                content = getattr(msg, 'content', '')
                if content and len(content) > 50:  # Meaningful content
                    # Check if this message contains structured tool data
                    if "[STRUCTURED_TOOL_DATA]:" in content:
                        parts = content.split("[STRUCTURED_TOOL_DATA]:")
                        conversational_part = parts[0].strip()
                        try:
                            import json
                            structured_part = json.loads(parts[1].strip())
                            # For TrustCall, include both parts with emphasis on structured data
                            enhanced_content = f"{conversational_part}\n\nDETAILED SALESFORCE RECORDS WITH REAL IDS:\n{json.dumps(structured_part, indent=2)}"
                            recent_tool_responses.append(enhanced_content[:2000])
                        except (json.JSONDecodeError, IndexError):
                            # Fallback to regular content
                            recent_tool_responses.append(content[:1500])
                    else:
                        recent_tool_responses.append(content[:1500])  # Truncate long responses
        
        # Build content for TrustCall - use actual tool responses, not just summary
        summary_content = state.get("summary", "")
        extraction_content = f"CONVERSATION SUMMARY:\n{summary_content}\n\n"
        
        if recent_tool_responses:
            extraction_content += "RECENT SALESFORCE TOOL RESPONSES WITH DATA TO EXTRACT:\n"
            for i, response in enumerate(recent_tool_responses):
                extraction_content += f"\nTool Response {i+1}:\n{response}\n"
        else:
            extraction_content += "No recent tool responses found."
        
        if debug_mode:
            logger.info(f"Memory extraction - Total content length: {len(extraction_content)}")
            logger.info(f"Memory extraction - Tool responses found: {len(recent_tool_responses)}")
            logger.info(f"Memory extraction - Content preview: {extraction_content[:300]}...")
        
        # SIMPLE: Enhanced TrustCall invocation with actual data
        try:
            # Get LLM config for timeout
            from src.utils.config import get_llm_config
            llm_config = get_llm_config()
            
            # Add timeout to prevent hanging in background threads
            import asyncio
            response = await asyncio.wait_for(
                trustcall_extractor.ainvoke({
                    "messages": [
                        SystemMessage(content=TRUSTCALL_INSTRUCTION),
                        HumanMessage(content=extraction_content)
                    ],
                    "existing": existing_records
                }),
                timeout=float(llm_config.timeout)  # Use LLM timeout from config
            )
            
            if response and response.get("responses"):
                extracted_data = response["responses"][0]
                
                # Simple storage - no complex validation
                if hasattr(extracted_data, 'model_dump'):
                    clean_data = extracted_data.model_dump()
                else:
                    clean_data = extracted_data
                
                # DEDUPLICATION: Merge with existing data to prevent duplicates
                if stored and isinstance(stored, dict):
                    # Merge each entity type, removing duplicates by ID
                    for entity_type in ['accounts', 'contacts', 'opportunities', 'cases', 'tasks', 'leads']:
                        existing_items = stored.get(entity_type, [])
                        new_items = clean_data.get(entity_type, [])
                        
                        # Create a dict keyed by ID for deduplication
                        merged_dict = {}
                        
                        # Add existing items
                        for item in existing_items:
                            if isinstance(item, dict) and 'id' in item:
                                merged_dict[item['id']] = item
                        
                        # Add/update with new items
                        for item in new_items:
                            if isinstance(item, dict) and 'id' in item:
                                merged_dict[item['id']] = item
                        
                        # Convert back to list
                        clean_data[entity_type] = list(merged_dict.values())
                
                memory_store.sync_put(namespace, key, clean_data)
                
                if debug_mode:
                    total_records = (len(clean_data.get('accounts', [])) + len(clean_data.get('contacts', [])) + 
                                   len(clean_data.get('opportunities', [])) + len(clean_data.get('cases', [])) + 
                                   len(clean_data.get('tasks', [])) + len(clean_data.get('leads', [])))
                    logger.info(f"Memory updated successfully with {total_records} total records")
                
                return {"memory": {"SimpleMemory": clean_data}, "turns": 0}
                
        except asyncio.TimeoutError:
            logger.warning("Memory extraction timed out after 30 seconds")
            # Simple fallback - return empty structure
            empty_memory = SimpleMemory().model_dump()
            return {"memory": {"SimpleMemory": empty_memory}, "turns": 0}
        except Exception as e:
            logger.warning(f"Memory extraction failed: {type(e).__name__}: {e}")
            # Simple fallback - return empty structure
            empty_memory = SimpleMemory().model_dump()
            return {"memory": {"SimpleMemory": empty_memory}, "turns": 0}
    
    # Background nodes for parallel execution
    async def background_summary(state: OrchestratorState, config: RunnableConfig):
        """Run summarization in background without blocking main response"""
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
        """Run memory extraction in background without blocking main response"""
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
    
    # Background aggregator no longer needed - tasks run independently
    
    # Conditional functions (legacy approach)
    def needs_summary(state: OrchestratorState):
        """Check if conversation needs summarization with multi-tool protection and cooldown"""
        message_count = len(state["messages"])
        current_turn = state.get("turns", 0)
        last_summarized = state.get("last_summarized_turn", -1)
        
        # Cooldown protection - don't summarize if we just did
        if current_turn - last_summarized < 1:  # At least 1 turn between summaries
            if debug_mode:
                logger.warning(f"COOLDOWN BLOCK: Last summarized turn {last_summarized}, current turn {current_turn}")
            return END
        
        # Higher threshold to prevent multi-tool cascade
        # Get conversation config
        from src.utils.config import get_conversation_config
        conv_config = get_conversation_config()
        
        # Multi-tool scenarios can generate up to 15+ messages in one turn
        # Balanced threshold for better memory capture
        if message_count > conv_config.summary_threshold:
            return "summarize_conversation"
        return END
    
    def needs_memory(state: OrchestratorState):
        """Check if memory needs updating (legacy)"""
        # Balanced threshold for better memory capture  
        if state.get("turns", 0) > 5:  # Balanced threshold to capture Salesforce data
            return "memorize_records"
        return END

    # Fire-and-forget background functions (run in separate threads with async support)
    def _run_background_summary(messages, summary, turns, memory, debug_mode):
        """Run summary task in background thread - fire and forget"""
        try:
            if debug_mode:
                # Use activity logger for structured logging to files
                log_orchestrator_activity("BACKGROUND_SUMMARY_START",
                                         message_count=len(messages),
                                         turn=turns,
                                         memory_keys=list(memory.keys()) if memory else [])
            # Reuse existing background_summary logic with mock config
            mock_state = {
                "messages": messages,
                "summary": summary,
                "turns": turns,
                "memory": memory,
                "last_summarized_turn": -1  # Add required field
            }
            mock_config = {"configurable": {"user_id": "user-1"}}
            # Run async function in new event loop
            import asyncio
            result = asyncio.run(background_summary(mock_state, mock_config))
            if debug_mode:
                log_orchestrator_activity("BACKGROUND_SUMMARY_COMPLETE",
                                         result_keys=list(result.keys()) if result else [],
                                         turn=turns)
        except Exception as e:
            import traceback
            log_orchestrator_activity("BACKGROUND_SUMMARY_ERROR",
                                     error=str(e),
                                     traceback=traceback.format_exc()[:500])
    
    def _run_background_memory(messages, summary, turns, memory, debug_mode):
        """Run memory extraction task in background thread - fire and forget"""
        try:
            if debug_mode:
                # Count tool messages to verify we have data to extract
                tool_messages = [m for m in messages if hasattr(m, 'name') and getattr(m, 'name', '')]
                tool_message_details = []
                for i, tm in enumerate(tool_messages[-3:]):  # Last 3 tool messages
                    content_preview = str(getattr(tm, 'content', ''))[:100]
                    tool_message_details.append({
                        "index": i,
                        "name": getattr(tm, 'name', 'unknown'),
                        "content_preview": content_preview
                    })
                
                # Use activity logger for structured logging to files
                log_orchestrator_activity("BACKGROUND_MEMORY_START",
                                         message_count=len(messages),
                                         turn=turns,
                                         tool_message_count=len(tool_messages),
                                         tool_message_details=tool_message_details)
                    
            # Reuse existing background_memory logic with mock config
            mock_state = {
                "messages": messages,
                "summary": summary,
                "turns": turns,
                "memory": memory
            }
            mock_config = {"configurable": {"user_id": "user-1"}}
            # Run async function in new event loop
            import asyncio
            result = asyncio.run(background_memory(mock_state, mock_config))
            if debug_mode:
                total_records = 0
                if result and 'memory' in result:
                    memory_data = result['memory'].get('SimpleMemory', {})
                    total_records = sum(len(memory_data.get(k, [])) for k in ['accounts', 'contacts', 'opportunities', 'cases', 'tasks', 'leads'])
                
                log_orchestrator_activity("BACKGROUND_MEMORY_COMPLETE",
                                         result_keys=list(result.keys()) if result else [],
                                         turn=turns,
                                         total_records_extracted=total_records)
        except Exception as e:
            import traceback
            log_orchestrator_activity("BACKGROUND_MEMORY_ERROR",
                                     error=str(e),
                                     traceback=traceback.format_exc()[:500])

    # Build simplified graph - background tasks run as fire-and-forget threads
    tool_node = ToolNode(tools=tools)
    graph_builder.add_node("tools", tool_node)
    graph_builder.add_node("conversation", orchestrator)
    
    # Set entry point
    graph_builder.set_entry_point("conversation")
    
    # Add simple routing - just check for tools
    graph_builder.add_conditional_edges("conversation", tools_condition)
    
    # Add edges following LangGraph best practices:
    # - tools->conversation: Continue conversation after tool execution
    graph_builder.add_edge("tools", "conversation")
    
    # DEBUG: Log simplified graph structure in debug mode
    if debug_mode:
        logger.info("GRAPH STRUCTURE: conversation -> tools_condition -> tools->conversation | background_tasks run as fire-and-forget threads")
    
    # Set finish point
    graph_builder.set_finish_point("conversation")
    
    # Compile and return the graph
    return graph_builder.compile(checkpointer=memory, store=memory_store)

# Build and export the graph at module level
orchestrator_graph = build_orchestrator_graph(debug_mode=False)

async def initialize_orchestrator():
    """Initialize the orchestrator system"""
    logger.info("Initializing Consultant Assistant Orchestrator...")
    
    # Perform health check on all registered agents
    logger.info("Checking agent health...")
    health_results = await agent_registry.health_check_all_agents()
    
    online_agents = [name for name, status in health_results.items() if status]
    offline_agents = [name for name, status in health_results.items() if not status]
    
    if online_agents:
        logger.info(f"Online agents: {', '.join(online_agents)}")
    if offline_agents:
        logger.warning(f"Offline agents: {', '.join(offline_agents)}")
    
    # Auto-discover agents if none are registered
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
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()
    
    DEBUG_MODE = args.debug
    
    # Setup comprehensive external logging
    init_session_tracking(DEBUG_MODE)
    
    # Get structured loggers
    orchestrator_logger = get_logger('orchestrator', DEBUG_MODE)
    perf_tracker = get_performance_tracker('orchestrator', DEBUG_MODE)
    cost_tracker = get_cost_tracker(DEBUG_MODE)
    
    # Setup basic logging for console output - only for user interface
    # Suppress all INFO level logging to console in non-debug mode
    log_level = logging.DEBUG if DEBUG_MODE else logging.WARNING
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Log session start
    orchestrator_logger.info("ORCHESTRATOR_SESSION_START", 
                           debug_mode=DEBUG_MODE,
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
    
    # Rebuild graph with debug mode if requested
    if DEBUG_MODE:
        local_graph = build_orchestrator_graph(debug_mode=True)
    else:
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
    
    # Control which node's output gets streamed to user (legacy approach)
    node_to_stream = "conversation"
    
    while True:
        try:
            user_input = input("USER: ")
            
            # Log raw user input
            log_orchestrator_activity("USER_INPUT_RAW", input=user_input[:1000])  # Limit to 1000 chars
            
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                log_orchestrator_activity("USER_QUIT")
                break
            
            # Validate user input for security
            try:
                from src.utils.input_validation import AgentInputValidator
                validated_input = AgentInputValidator.validate_orchestrator_input(user_input)
                user_input = validated_input
            except Exception as e:
                print(f"Error: Invalid input - {e}")
                continue
            
            if DEBUG_MODE:
                # In debug mode, track duplicate responses
                event_count = 0
                ai_responses = []
                
                async for event in local_graph.astream(
                    {
                        "messages": [{"role": "user", "content": user_input}],
                        "background_operations": [],
                        "background_results": {},
                        "last_summarized_turn": -1
                    },
                    config,
                    stream_mode="values",
                ):
                    event_count += 1
                    
                    if "messages" in event and event["messages"]:
                        last_msg = event["messages"][-1]
                        msg_type = type(last_msg).__name__
                        
                        # Track AI responses for duplicate detection
                        if msg_type == "AIMessage" and hasattr(last_msg, 'content') and last_msg.content:
                            ai_responses.append({
                                'event': event_count,
                                'content': last_msg.content[:100],
                                'has_tool_calls': bool(getattr(last_msg, 'tool_calls', None))
                            })
                        
                        # Log concisely
                        logger.info(f"Event {event_count}: {msg_type} (msgs: {len(event['messages'])})")
                        
                        # Pretty print for visibility
                        last_msg.pretty_print()
                
                # Duplicate detection summary
                if len(ai_responses) > 1:
                    logger.warning(f"DUPLICATE WARNING: {len(ai_responses)} AI responses detected!")
                    for resp in ai_responses:
                        logger.warning(f"  Event {resp['event']}: {resp['content']}... (tools: {resp['has_tool_calls']})")
                
                logger.info(f"Total events: {event_count}, AI responses: {len(ai_responses)}")
            else:
                print("\nASSISTANT: ", end="", flush=True)
                # Stream conversation response immediately, let background ops continue silently
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
                    # Show conversation response immediately when available
                    if "messages" in event and event["messages"] and not response_shown:
                        last_msg = event["messages"][-1]
                        if hasattr(last_msg, 'content') and last_msg.content and hasattr(last_msg, 'type'):
                            from langchain_core.messages import AIMessage
                            if isinstance(last_msg, AIMessage) and not getattr(last_msg, 'tool_calls', None):
                                conversation_response = last_msg.content
                                # Log assistant response
                                log_orchestrator_activity("ASSISTANT_RESPONSE", 
                                                        response=conversation_response[:1000],  # Limit logged length
                                                        full_length=len(conversation_response))
                                # Type out the response immediately
                                await type_out(conversation_response, delay=0.01)
                                response_shown = True
                                print("\n")
                                # DON'T break - let background operations continue silently
                
                # If we didn't get a response through streaming, fall back 
                if not response_shown:
                    print("Processing your request...\n")
                        
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except EOFError:
            # Handle EOF gracefully (e.g., when input is redirected or piped)
            print("\nInput stream ended. Goodbye!")
            break
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            print(f"Error: {e}")
            # For serious errors, consider breaking the loop
            if "connection" in str(e).lower() or "network" in str(e).lower():
                print("Network error encountered. Exiting...")
                break

if __name__ == "__main__":
    asyncio.run(main())