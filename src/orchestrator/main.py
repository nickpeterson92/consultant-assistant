"""
Orchestrator Agent - Main LangGraph Implementation
Coordinates communication between user and specialized agents via A2A protocol
"""

import os
import json
import asyncio
import argparse
from typing import Annotated, Dict, Any, List
from typing_extensions import TypedDict

from dotenv import load_dotenv

from trustcall import create_extractor

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from langgraph.graph.message import RemoveMessage, add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import AzureChatOpenAI

# Fix path resolution for imports
import sys
import os
# Add the project root to path for relative imports
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)
# Add the agent directory to path
agent_path = os.path.join(os.path.dirname(__file__), '..', 'agent')
sys.path.insert(0, agent_path)

from .agent_registry import AgentRegistry
from .state_manager import MultiAgentStateManager
from .agent_caller_tools import SalesforceAgentTool, GenericAgentTool, AgentRegistryTool
from utils.helpers import type_out, smart_preserve_messages
from utils.sys_msg import summary_sys_msg, TRUSTCALL_INSTRUCTION
from store.sqlite_store import SQLiteStore
from store.memory_schemas import AccountList
from .enhanced_sys_msg import orchestrator_chatbot_sys_msg, orchestrator_summary_sys_msg, ORCHESTRATOR_TRUSTCALL_INSTRUCTION

import logging

# Disable LangSmith tracing to avoid circular reference errors
os.environ["LANGCHAIN_TRACING_V2"] = "false"

logger = logging.getLogger(__name__)

# Global orchestrator state manager
orchestrator_state_mgr = MultiAgentStateManager()
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
    memory_store = SQLiteStore()
    graph_builder = StateGraph(OrchestratorState)
    
    # Initialize orchestrator tools
    tools = [
        SalesforceAgentTool(agent_registry, debug_mode),
        GenericAgentTool(agent_registry),
        AgentRegistryTool(agent_registry)
    ]
    
    llm = create_azure_openai_chat()
    llm_with_tools = llm.bind_tools(tools)
    trustcall_extractor = create_extractor(
        llm,
        tools=[AccountList],
        tool_choice="AccountList",
    )
    
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
    def orchestrator(state: OrchestratorState, config: RunnableConfig):
        """Main orchestrator node that coordinates with specialized agents"""
        try:
            # POST-SUMMARIZATION DEBUG: Log when we're called after summarization
            if debug_mode and len(state.get('messages', [])) <= 3:
                logger.info("=== ORCHESTRATOR POST-SUMMARIZATION CALL ===")
                logger.info(f"Messages count: {len(state.get('messages', []))}")
                logger.info(f"Turn: {state.get('turns', 0)}")
                logger.info(f"Has summary: {bool(state.get('summary', '').strip())}")
                for i, msg in enumerate(state.get('messages', [])):
                    logger.info(f"Message {i}: {type(msg).__name__} - {str(msg.content)[:100]}...")
                logger.info("=== END POST-SUMMARIZATION DEBUG ===")
            
            # Load and manage memory like legacy system
            summary = state.get("summary", "No summary available")
            memory_val = state.get("memory", "No memory available")
            turn = state.get("turns", 0)
            
            # Load existing memory from store if needed
            if memory_val == "No memory available":
                user_id = config["configurable"].get("user_id", "default")
                namespace = ("memory", user_id)
                key = "AccountList"
                store_conn = memory_store.get_connection("memory_store.db")
                existing_memory = store_conn.get(namespace, key)
                existing_memory = {"AccountList": existing_memory} if existing_memory else {"AccountList": AccountList().model_dump()}
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
            response = llm_with_tools.invoke(messages)
            
            # Update orchestrator state (legacy style)
            turn = state.get("turns", 0)
            updated_state = {
                "messages": response,
                "memory": existing_memory,
                "turns": turn + 1
            }
            
            # Update global state manager
            orchestrator_state_mgr.update_conversation_summary(
                state.get("summary", "")
            )
            
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
    def summarize_conversation(state: OrchestratorState):
        """Summarize conversation using smart message preservation"""
        if debug_mode:
            logger.info("=== SUMMARIZE_CONVERSATION START ===")
            logger.info(f"Input state keys: {list(state.keys())}")
            logger.info(f"Messages in state: {len(state.get('messages', []))}")
            logger.info(f"Turn: {state.get('turns', 0)}")
            
            # Show each message going into summarization
            for i, msg in enumerate(state.get('messages', [])):
                logger.info(f"Input Message {i}: {type(msg).__name__} - {str(msg.content)[:100]}...")
        
        summary = state.get("summary", "No summary available")
        memory_val = state.get("memory", "No memory available")
        
        # Use enhanced orchestrator summary system message
        system_message = orchestrator_summary_sys_msg(summary, memory_val)
        messages = [SystemMessage(content=system_message)] + state["messages"]
        
        if debug_mode:
            logger.info(f"System message for summarization: {system_message[:200]}...")
            logger.info(f"Total messages for LLM: {len(messages)}")
            logger.info("Using smart preservation - no cleanup needed")
        
        response = llm.invoke(messages)
        
        if debug_mode:
            logger.info(f"LLM summary response type: {type(response)}")
            logger.info(f"LLM summary content: {str(response.content)[:300]}...")
        
        # Update global state manager with new summary
        orchestrator_state_mgr.update_conversation_summary(response.content)
        
        # Use smart preservation instead of simple slice
        messages_to_preserve = smart_preserve_messages(state["messages"], keep_count=3)
        messages_to_delete = []
        
        # Find messages that are NOT in the preserved list
        preserved_ids = {getattr(msg, 'id', None) for msg in messages_to_preserve if hasattr(msg, 'id')}
        for msg in state["messages"]:
            if hasattr(msg, 'id') and msg.id not in preserved_ids:
                messages_to_delete.append(RemoveMessage(id=msg.id))
        
        if debug_mode:
            logger.info(f"Messages to delete: {len(messages_to_delete)}")
            logger.info(f"Messages to preserve: {len(messages_to_preserve)}")
            logger.info("Smart preservation ensures no orphaned tool calls")
            logger.info("=== SUMMARIZE_CONVERSATION END ===")
        
        return {
            "summary": response.content,
            "messages": messages_to_delete
        }
    
    # Node function: memorize_records (legacy approach)
    async def memorize_records(state: OrchestratorState, config: RunnableConfig):
        """Update memory using legacy TrustCall approach"""
        if debug_mode:
            logger.info("Updating memory (legacy TrustCall approach)")
        
        user_id = config["configurable"].get("user_id", "default")
        namespace = ("memory", user_id)
        key = "AccountList"
        store_conn = memory_store.get_connection("memory_store.db")
        existing_memory = store_conn.get(namespace, key)
        existing_records = {"AccountList": existing_memory} if existing_memory else {"AccountList": AccountList().model_dump()}
        
        if debug_mode:
            logger.info(f"Existing memory: {existing_records}")
        
        messages = {
            "messages": [SystemMessage(content=ORCHESTRATOR_TRUSTCALL_INSTRUCTION),
                        HumanMessage(content=state.get("summary", ""))],
            "existing": existing_records,
        }
        
        if debug_mode:
            logger.info(f"TrustCall messages: {messages}")
        
        response = await trustcall_extractor.ainvoke(messages)
        if debug_mode:
            logger.info(f"TrustCall response: {response}")
        
        response = response["responses"][0].model_dump()
        store_conn.put(namespace, key, response)
        
        if debug_mode:
            logger.info(f"Updated memory: {response}")
        
        return {"memory": response, "turns": 0}
    
    # Conditional functions (legacy approach)
    def needs_summary(state: OrchestratorState):
        """Check if conversation needs summarization (legacy)"""
        if len(state["messages"]) > 12:  # Legacy threshold
            return "summarize_conversation"
        return END
    
    def needs_memory(state: OrchestratorState):
        """Check if memory needs updating (legacy)"""
        if state.get("turns", 0) > 6:  # Legacy threshold
            return "memorize_records"
        return END
    
    # Build the graph with nodes and edges (legacy approach)
    tool_node = ToolNode(tools=tools)
    graph_builder.add_node("tools", tool_node)
    graph_builder.add_node("conversation", orchestrator)  # Legacy name
    graph_builder.add_node("summarize_conversation", summarize_conversation)
    graph_builder.add_node("memorize_records", memorize_records)
    
    # Set entry point
    graph_builder.set_entry_point("conversation")
      
    # Sequential routing function (fixes timing issue)
    def smart_routing(state: OrchestratorState):
        """Route to tools first, then summarization - prevents 400 errors"""
        # STEP 1: Check for tools first (highest priority)
        tool_result = tools_condition(state)
        if tool_result != END:
            return tool_result
        
        # STEP 2: Then check for summary (only after tools complete)
        summary_result = needs_summary(state)
        if summary_result != END:
            return summary_result
            
        # STEP 3: Finally check memory (lowest priority)
        memory_result = needs_memory(state)
        if memory_result != END:
            return memory_result
            
        return END
    
    # Add sequential routing (fixes tool/summary timing issue)
    graph_builder.add_conditional_edges("conversation", smart_routing)
    
    # Add standard edges - removed tools->conversation to prevent duplicate responses
    graph_builder.add_edge("tools", "conversation")
    graph_builder.add_edge("summarize_conversation", "conversation")
    graph_builder.add_edge("memorize_records", "conversation")
    
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
    
    # Setup logging
    log_level = logging.DEBUG if DEBUG_MODE else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Suppress verbose HTTP request logging from third-party libraries
    # Always suppress HTTP noise regardless of debug mode
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('simple_salesforce').setLevel(logging.WARNING)
    
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
            
            if DEBUG_MODE:
                # In debug mode, stream all events
                event_count = 0
                async for event in local_graph.astream(
                    {"messages": [{"role": "user", "content": user_input}]},
                    config,
                    stream_mode="values",
                ):
                    event_count += 1
                    logger.info(f"=== STREAM EVENT {event_count} ===")
                    logger.info(f"Event keys: {list(event.keys())}")
                    
                    if "messages" in event:
                        logger.info(f"Messages in event: {len(event['messages'])}")
                        if event["messages"]:
                            last_msg = event["messages"][-1]
                            logger.info(f"Last message type: {type(last_msg).__name__}")
                            logger.info(f"Last message preview: {str(last_msg)[:100]}...")
                            last_msg.pretty_print()
                    
                    logger.info(f"=== END STREAM EVENT {event_count} ===")
                    
                logger.info(f"Total stream events processed: {event_count}")
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