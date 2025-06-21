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
from typing_extensions import TypedDict

from dotenv import load_dotenv

# Add logging configuration
from src.utils.logging import get_logger, get_performance_tracker, get_cost_tracker, init_session_tracking

from trustcall import create_extractor

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from langgraph.graph.message import RemoveMessage, add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import AzureChatOpenAI

# Imports no longer need path manipulation

from .agent_registry import AgentRegistry
from .agent_caller_tools import SalesforceAgentTool, GenericAgentTool, AgentRegistryTool
from src.utils.helpers import type_out, smart_preserve_messages
from src.utils.storage import get_async_store_adapter, AccountList
from src.utils.logging import get_summary_logger
from src.utils.caching import get_llm_cache
from .enhanced_sys_msg import orchestrator_chatbot_sys_msg, orchestrator_summary_sys_msg, ORCHESTRATOR_TRUSTCALL_INSTRUCTION

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
    """Create Azure OpenAI chat instance"""
    return AzureChatOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"],
        openai_api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
        temperature=0.0,
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
    
    memory = MemorySaver()
    # Use enhanced async store adapter with performance monitoring and resilience
    memory_store = get_async_store_adapter(
        db_path="memory_store.db",
        use_async=False,  # Use thread pool adapter for reliability
        max_workers=4,
        max_connections=10,
        enable_circuit_breaker=True
    )
    
    # Initialize LLM cache for orchestrator
    llm_cache = get_llm_cache("orchestrator")
    
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
    trustcall_extractor = create_extractor(
        llm,
        tools=[AccountList],
        tool_choice="any",  # Allow flexible schema updates
        enable_inserts=True  # Enable new record creation
    )
    
    # Cached LLM wrapper for regular calls
    async def cached_llm_invoke(messages, model_name="orchestrator", use_tools=False):
        """Invoke LLM with caching support"""
        # Convert messages to cacheable format
        cache_messages = []
        for msg in messages:
            if hasattr(msg, 'content'):
                cache_messages.append({
                    "role": getattr(msg, 'type', 'unknown'),
                    "content": str(msg.content)
                })
        
        # Try cache first
        cached_response = await llm_cache.get(
            messages=cache_messages,
            model=model_name,
            temperature=0.0,
            max_tokens=4000
        )
        
        if cached_response:
            logger.debug("Using cached LLM response")
            return cached_response
        
        # Cache miss - call LLM
        logger.debug("Cache miss - calling LLM")
        if use_tools:
            response = llm_with_tools.invoke(messages)
        else:
            response = llm.invoke(messages)
        
        # Cache the response
        await llm_cache.put(
            messages=cache_messages,
            model=model_name,
            response=response,
            temperature=0.0,
            max_tokens=4000,
            token_count=len(str(response.content)) // 4 if hasattr(response, 'content') else 0
        )
        
        return response
    
    
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
            memory_val = state.get("memory", "No memory available")
            turn = state.get("turns", 0)
            
            # Load existing memory from store if needed
            if memory_val == "No memory available":
                user_id = config["configurable"].get("user_id", "default")
                namespace = ("memory", user_id)
                key = "AccountList"
                existing_memory_data = memory_store.sync_get(namespace, key)
                existing_memory = {"AccountList": existing_memory_data} if existing_memory_data else {"AccountList": AccountList().model_dump()}
            else:
                existing_memory = memory_val
            
            # Update state with loaded memory
            state["memory"] = existing_memory
            
            # Create system message with current context
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
            response = await cached_llm_invoke(messages, model_name="orchestrator_main", use_tools=True)
            
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
            
            # Update orchestrator state (legacy style)
            turn = state.get("turns", 0)
            updated_state = {
                "messages": response,
                "memory": existing_memory,
                "turns": turn + 1
            }
            
            # Conversation summary already handled by LangGraph state
            
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
        
        response = await cached_llm_invoke(messages, model_name="orchestrator_summary", use_tools=False)
        response_content = str(response.content) if hasattr(response, 'content') else ""
        log_orchestrator_activity("LLM_RESPONSE", 
                                 response_length=len(response_content),
                                 response_content=response_content[:500],  # Truncate for readability
                                 operation="SUMMARIZATION")
        
        # Estimate and log token usage
        message_chars = sum(len(str(m.content if hasattr(m, 'content') else m)) for m in messages)
        estimated_tokens = message_chars // 4  # Rough estimate: 4 chars per token
        log_cost_activity("ORCHESTRATOR_LLM_CALL", estimated_tokens, 
                         message_count=len(messages),
                         response_length=len(str(response.content)) if hasattr(response, 'content') else 0)
        
        
        # Summary already stored in LangGraph state
        
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
    
    # Node function: memorize_records (legacy approach)
    async def memorize_records(state: OrchestratorState, config: RunnableConfig):
        """Update memory using legacy TrustCall approach"""
        if debug_mode:
            logger.info("Updating memory (legacy TrustCall approach)")
        
        user_id = config["configurable"].get("user_id", "default")
        namespace = ("memory", user_id)
        key = "AccountList"
        existing_memory_data = memory_store.sync_get(namespace, key)
        existing_records = {"AccountList": existing_memory_data} if existing_memory_data else {"AccountList": AccountList().model_dump()}
        
        if debug_mode:
            logger.info(f"Existing memory: {existing_records}")
        
        # Enhanced TrustCall message with more context
        summary_content = state.get("summary", "")
        
        # Log TrustCall input for debugging
        if debug_mode:
            logger.info(f"=== TRUSTCALL DEBUG ===")
            logger.info(f"Summary being passed to TrustCall: {summary_content[:500]}...")
            logger.info(f"Existing records: {existing_records}")
        
        messages = {
            "messages": [
                SystemMessage(content=ORCHESTRATOR_TRUSTCALL_INSTRUCTION),
                HumanMessage(content=summary_content)
            ],
            "existing": existing_records,
        }
        
        if debug_mode:
            logger.info(f"TrustCall full messages structure prepared")
        
        response = await trustcall_extractor.ainvoke(messages)
        if debug_mode:
            logger.info(f"TrustCall raw response: {response}")
        
        if response and "responses" in response and len(response["responses"]) > 0:
            extracted_data = response["responses"][0].model_dump()
            if debug_mode:
                logger.info(f"TrustCall extracted data: {extracted_data}")
            
            memory_store.sync_put(namespace, key, extracted_data)
            
            if debug_mode:
                logger.info(f"Memory updated with: {extracted_data}")
            
            return {"memory": extracted_data, "turns": 0}
        else:
            if debug_mode:
                logger.error(f"TrustCall failed - no responses in: {response}")
            return {"memory": existing_records, "turns": 0}
    
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
        # Multi-tool scenarios can generate up to 15+ messages in one turn
        # Balanced threshold for better memory capture
        if message_count > 12:  # Balanced threshold to capture Salesforce data
            return "summarize_conversation"
        return END
    
    def needs_memory(state: OrchestratorState):
        """Check if memory needs updating (legacy)"""
        # Balanced threshold for better memory capture  
        if state.get("turns", 0) > 5:  # Balanced threshold to capture Salesforce data
            return "memorize_records"
        return END

    # Sequential routing function (fixes timing issue)
    def smart_routing(state: OrchestratorState):
        """Route to tools first, then summarization - prevents 400 errors"""
        # STEP 1: Check for tools first (highest priority)
        tool_result = tools_condition(state)
        if tool_result != END:
            return tool_result
        
        # STEP 2: Then check for summary (only after tools complete)
        # Memory will be automatically called after summarization via graph edges
        summary_result = needs_summary(state)
        if summary_result != END:
            return summary_result
            
        return END

    # Build the graph with nodes and edges (legacy approach)
    tool_node = ToolNode(tools=tools)
    graph_builder.add_node("tools", tool_node)
    graph_builder.add_node("conversation", orchestrator)  # Legacy name
    graph_builder.add_node("summarize_conversation", summarize_conversation)
    graph_builder.add_node("memorize_records", memorize_records)
    
    # Set entry point
    graph_builder.set_entry_point("conversation")
    
    # Add sequential routing (fixes tool/summary timing issue)
    graph_builder.add_conditional_edges("conversation", smart_routing)
    
    # Add edges following LangGraph best practices:
    # - tools->conversation: Continue conversation after tool execution
    # - summarize_conversation->memorize_records: Memory extraction after summarization
    # - memorize_records->END: Terminate after memory update
    graph_builder.add_edge("tools", "conversation")
    graph_builder.add_edge("summarize_conversation", "memorize_records")  # Chain summary → memory
    graph_builder.add_edge("memorize_records", END)
    
    # DEBUG: Log corrected graph structure in debug mode
    if debug_mode:
        logger.warning("GRAPH STRUCTURE: conversation -> smart_routing -> tools->conversation | summary->memory->END")
    
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
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
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
                    {"messages": [{"role": "user", "content": user_input}]},
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
                # In non-debug mode, get final result and show with animation
                result = None
                async for event in local_graph.astream_events(
                    {"messages": [{"role": "user", "content": user_input}]},
                    config,
                    stream_mode="values",
                    version="v2"
                ):  
                    #print(event)
                    if (event.get("event") == "on_chat_model_stream" and 
                        event.get("metadata", {}).get("langgraph_node", "") == node_to_stream):
                        data = event.get("data", {})
                        chunk = data.get("chunk", {})
                        if hasattr(chunk, "content") and chunk.content:
                            await type_out(chunk.content, delay=0.01)
                
                print("\n")
                        
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