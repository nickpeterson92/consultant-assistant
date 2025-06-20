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
from utils.helpers import clean_orphaned_tool_calls, type_out

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
    
    # Define the orchestrator state schema
    class OrchestratorState(TypedDict):
        messages: Annotated[list, add_messages]
        conversation_summary: str
        global_memory: Annotated[Dict[str, Any], lambda existing, new: {**existing, **new} if existing else new]
        turns: int
        active_agents: List[str]
        last_agent_interaction: Dict[str, Any]
    
    memory = MemorySaver()
    graph_builder = StateGraph(OrchestratorState)
    
    # Initialize orchestrator tools
    tools = [
        SalesforceAgentTool(agent_registry, debug_mode),
        GenericAgentTool(agent_registry),
        AgentRegistryTool(agent_registry)
    ]
    
    llm = create_azure_openai_chat()
    llm_with_tools = llm.bind_tools(tools)
    
    # System message for orchestrator
    def get_orchestrator_system_message(state: OrchestratorState) -> str:
        summary = state.get("conversation_summary", "No summary available")
        global_memory = state.get("global_memory", {})
        active_agents = state.get("active_agents", [])
        
        # Get registry stats for context
        registry_stats = agent_registry.get_registry_stats()
        
        system_msg = f"""You are the Consultant Assistant Orchestrator, coordinating between specialized AI agents to help consultants with their workflows.

CONVERSATION CONTEXT:
{summary}

AVAILABLE SPECIALIZED AGENTS:
{', '.join(registry_stats['available_capabilities']) if registry_stats['available_capabilities'] else 'None currently available'}

CURRENTLY ACTIVE AGENTS: {', '.join(active_agents) if active_agents else 'None'}

GLOBAL MEMORY CONTEXT:
{json.dumps(global_memory, indent=2) if global_memory else 'No global memory available'}

YOUR ROLE:
- Route user requests to appropriate specialized agents
- Coordinate multi-agent workflows when needed
- Maintain conversation context and memory across agents
- Provide unified responses combining results from multiple agents

TOOLS AVAILABLE:
1. salesforce_agent: For Salesforce CRM operations (leads, accounts, opportunities, contacts, cases, tasks)
2. call_agent: For general agent calls (travel, expenses, HR, OCR, etc.)
3. manage_agents: To check agent status and capabilities

CRITICAL INSTRUCTIONS - FOLLOW THESE EXACTLY:
- NEVER call the same tool multiple times for the same user request
- When a tool returns results, respond directly to the user with those results
- Do NOT make additional tool calls after receiving successful results
- STOP IMMEDIATELY after getting tool results - synthesize and respond to user
- If you see ANY tool results in conversation history, use those instead of making new calls
- Only make NEW tool calls when the user asks for completely different information
- IMPORTANT: If you see tool results containing account details, respond with those details - DO NOT call tools again
- NEVER EVER make duplicate tool calls - if you see previous tool results, USE THEM
- EXAMINE THE CONVERSATION HISTORY CAREFULLY before making any tool calls
- For Salesforce-related queries, use the salesforce_agent tool
- For other enterprise systems (travel, expenses, HR), use call_agent
- If unsure which agents are available, use manage_agents first
- Combine results from multiple agents when beneficial
- Keep responses concise and helpful
- Pass relevant context from previous interactions to agents

RESPONSE BEHAVIOR:
- ALWAYS check conversation history for existing tool results BEFORE making new calls
- If you see tool results in the conversation, DO synthesize and present them to the user
- DO NOT repeat tool calls for information that has already been retrieved
- Focus on providing helpful responses based on available information
- Prefer using existing information over making redundant tool calls
- NEVER respond with generic "Is there anything else" - ALWAYS provide the actual data from tool results
- When tool results contain specific data (accounts, contacts, opportunities), PRESENT THAT DATA to the user
- NEVER ask follow-up questions like "Is there anything else?" or "What would you like to do next?"
- If you have already provided the requested information, do NOT generate additional responses"""
        
        return system_msg
    
    # Node function: orchestrator (main conversation handler)
    def orchestrator(state: OrchestratorState, config: RunnableConfig):
        """Main orchestrator node that coordinates with specialized agents"""
        try:
            if debug_mode:
                logger.info(f"=== ORCHESTRATOR START ===")
                logger.info(f"Processing with {len(state.get('messages', []))} messages")
                logger.info(f"Current turn: {state.get('turns', 0)}")
                
                # Debug: Show all messages in state
                logger.info("=== CURRENT STATE MESSAGES ===")
                for i, msg in enumerate(state.get('messages', [])):
                    msg_type = type(msg).__name__
                    has_tool_calls = hasattr(msg, 'tool_calls') and msg.tool_calls
                    has_tool_call_id = hasattr(msg, 'tool_call_id')
                    content_preview = str(msg.content)[:150] if hasattr(msg, 'content') else "No content"
                    logger.info(f"State Message {i}: {msg_type} | HasToolCalls: {has_tool_calls} | HasToolCallId: {has_tool_call_id}")
                    logger.info(f"  Content: {content_preview}...")
                    if has_tool_calls:
                        for j, tc in enumerate(msg.tool_calls):
                            logger.info(f"    Tool call {j}: {tc.get('name', 'unknown')} - {tc.get('args', {})}")
                logger.info("=== END STATE MESSAGES ===")
            
            # Create system message with current context
            system_message = get_orchestrator_system_message(state)
            if debug_mode:
                logger.info(f"System message length: {len(system_message)}")
            
            messages = [SystemMessage(content=system_message)] + state["messages"]
            if debug_mode:
                logger.info(f"Total messages before conversion: {len(messages)}")
            
            # Check if we already have tool results that answer the user's question
            recent_tool_results = []
            for msg in reversed(state.get("messages", [])):
                if hasattr(msg, 'name') and getattr(msg, 'name', None) in ['salesforce_agent', 'call_agent']:
                    recent_tool_results.append(msg)
                    if len(recent_tool_results) >= 2:  # Stop after finding recent results
                        break
            
            # If we have recent tool results, check if they answer the current question
            if recent_tool_results and debug_mode:
                logger.info(f"Found {len(recent_tool_results)} recent tool results")
                for i, result in enumerate(recent_tool_results):
                    logger.info(f"Tool result {i}: {str(result.content)[:200]}...")
            
            # Clean orphaned tool calls to prevent 400 errors
            if debug_mode:
                logger.info("Cleaning orphaned tool calls...")
            clean_messages = clean_orphaned_tool_calls(messages)
            if debug_mode:
                logger.info(f"Messages after cleanup: {len(clean_messages)}")
                
                # Debug: Show what gets sent to LLM
                logger.info("=== MESSAGES SENT TO LLM ===")
                for i, msg in enumerate(clean_messages):
                    msg_type = type(msg).__name__
                    content = str(getattr(msg, 'content', ''))[:150]
                    has_tool_calls = hasattr(msg, 'tool_calls') and getattr(msg, 'tool_calls', None)
                    logger.info(f"LLM Message {i}: {msg_type} - {content}..." + (f" [HAS_TOOL_CALLS]" if has_tool_calls else ""))
                logger.info("=== END LLM MESSAGES ===")
                
                logger.info("Invoking LLM with tools...")
            response = llm_with_tools.invoke(clean_messages)
            if debug_mode:
                logger.info(f"LLM response type: {type(response)}")
                logger.info(f"Response content: {str(response)[:200]}...")
                
                # Check for tool calls
                has_tool_calls = hasattr(response, 'tool_calls') and response.tool_calls
                logger.info(f"Response has tool calls: {has_tool_calls}")
                if has_tool_calls:
                    logger.info(f"Number of tool calls: {len(response.tool_calls)}")
                    for i, tc in enumerate(response.tool_calls):
                        logger.info(f"Tool call {i}: {tc.get('name', 'unknown')} - {str(tc)[:100]}...")
                        
                # Show why LLM might be making tool calls
                if has_tool_calls:
                    logger.info("=== LLM DECISION ANALYSIS ===")
                    logger.info("LLM generated tool calls despite having conversation history.")
                    logger.info("This suggests the LLM either:")
                    logger.info("1. Doesn't see the previous tool results")
                    logger.info("2. Doesn't recognize them as answering the user's question") 
                    logger.info("3. System prompt is not clear enough about using existing results")
                    logger.info("=== END ANALYSIS ===")
            
            # Update orchestrator state
            turn = state.get("turns", 0)
            updated_state = {
                "messages": response,
                "turns": turn + 1
            }
            
            # Update global state manager
            orchestrator_state_mgr.update_conversation_summary(
                state.get("conversation_summary", "")
            )
            
            if debug_mode:
                logger.info(f"=== ORCHESTRATOR END - SUCCESS ===")
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
    
    # Node function: summarize_conversation  
    def summarize_conversation(state: OrchestratorState):
        """Summarize conversation when it gets too long"""
        if debug_mode:
            logger.info("Summarizing conversation")
        
        summary = state.get("conversation_summary", "No summary available")
        global_memory = state.get("global_memory", {})
        
        system_message = f"""Please provide a concise summary of this conversation, maintaining important context for future interactions.

Previous summary: {summary}

Global context: {json.dumps(global_memory, indent=2) if global_memory else 'None'}

Focus on:
- User's current goals and requests
- Key information discovered or processed
- Important entities (contacts, accounts, etc.) mentioned
- Outstanding tasks or next steps
- Agent interactions and their outcomes"""
        
        messages = state["messages"] + [HumanMessage(content=system_message)]
        # Clean orphaned tool calls to avoid 400 errors
        clean_messages = clean_orphaned_tool_calls(messages)
        response = llm.invoke(clean_messages)
        
        # Update global state manager with new summary
        orchestrator_state_mgr.update_conversation_summary(response.content)
        
        # Remove old messages but keep the last 2
        delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-2]]
        
        return {
            "conversation_summary": response.content,
            "messages": delete_messages,
            "global_memory": orchestrator_state_mgr.export_state()
        }
    
    # Node function: update_global_memory
    def update_global_memory(state: OrchestratorState):
        """Update global memory with information from recent interactions"""
        if debug_mode:
            logger.info("Updating global memory")
        
        # Export current state from state manager
        global_state = orchestrator_state_mgr.export_state()
        
        return {
            "global_memory": global_state,
            "turns": 0  # Reset turn counter after memory update
        }
    
    # Conditional function: needs_summary
    def needs_summary(state: OrchestratorState):
        """Check if conversation needs summarization"""
        if len(state["messages"]) > 8:  # Increased threshold for orchestrator
            return "summarize_conversation"
        return END
    
    # Conditional function: needs_memory_update
    def needs_memory_update(state: OrchestratorState):
        """Check if global memory needs updating"""
        if state.get("turns", 0) > 8:  # Update memory less frequently
            return "update_global_memory"
        return END
    
    # Build the graph with nodes and edges
    tool_node = ToolNode(tools=tools)
    graph_builder.add_node("tools", tool_node)
    graph_builder.add_node("orchestrator", orchestrator)
    graph_builder.add_node("summarize_conversation", summarize_conversation)
    graph_builder.add_node("update_global_memory", update_global_memory)
    
    # Set entry point
    graph_builder.set_entry_point("orchestrator")
      
    # Add conditional edges
    graph_builder.add_conditional_edges("orchestrator", tools_condition)
    graph_builder.add_conditional_edges("orchestrator", needs_summary)
    graph_builder.add_conditional_edges("orchestrator", needs_memory_update)
    
    # Add standard edges
    graph_builder.add_edge("tools", "orchestrator")
    graph_builder.add_edge("summarize_conversation", "orchestrator")
    graph_builder.add_edge("update_global_memory", "orchestrator")
    
    # Set finish point
    graph_builder.set_finish_point("orchestrator")
    
    # Compile and return the graph
    return graph_builder.compile(checkpointer=memory)

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
                async for event in local_graph.astream(
                    {"messages": [{"role": "user", "content": user_input}]},
                    config,
                    stream_mode="values",
                ):
                    if "messages" in event and event["messages"]:
                        result = event["messages"][-1]
                
                # Display the final response with typeout animation
                if result and hasattr(result, 'content'):
                    await type_out(result.content)
                elif result:
                    await type_out(str(result))
                
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