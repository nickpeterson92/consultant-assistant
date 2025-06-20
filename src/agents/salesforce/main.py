"""
Salesforce Specialized Agent
Handles all Salesforce CRM operations via A2A protocol
"""

import os
import json
import asyncio
import argparse
from typing import Annotated, Dict, Any
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
# Add the project root to path
project_root = os.path.join(os.path.dirname(__file__), '..', '..', '..')
sys.path.insert(0, project_root)
# Add the agent directory to path
agent_path = os.path.join(os.path.dirname(__file__), '..', '..', 'agent')
sys.path.insert(0, agent_path)

from src.a2a import A2AServer, AgentCard, A2ATask

# Now import from the agent directory
from store.sqlite_store import SQLiteStore
from store.memory_schemas import AccountList
from utils.state_manager import StateManager
from utils.sys_msg import chatbot_sys_msg, summary_sys_msg, TRUSTCALL_INSTRUCTION
from utils.helpers import clean_orphaned_tool_calls
from tools.salesforce_tools import (
    CreateLeadTool, GetLeadTool, UpdateLeadTool,
    GetOpportunityTool, UpdateOpportunityTool, CreateOpportunityTool,
    GetAccountTool, CreateAccountTool, UpdateAccountTool,
    GetContactTool, CreateContactTool, UpdateContactTool,
    GetCaseTool, CreateCaseTool, UpdateCaseTool,
    GetTaskTool, CreateTaskTool, UpdateTaskTool
)

import logging

# Disable LangSmith tracing to avoid circular reference errors
os.environ["LANGCHAIN_TRACING_V2"] = "false"

logger = logging.getLogger(__name__)

# Global state manager for Salesforce agent
salesforce_state_mgr = StateManager()

def create_azure_openai_chat():
    """Create Azure OpenAI chat instance"""
    return AzureChatOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"], 
        azure_deployment=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"],
        openai_api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
        temperature=0.0,
    )

def build_salesforce_graph(debug_mode: bool = False):
    """Build and compile the Salesforce agent LangGraph"""
    
    load_dotenv()
    
    # Define the Salesforce agent state schema
    class SalesforceState(TypedDict):
        messages: Annotated[list, add_messages]
        summary: str
        memory: dict
        turns: int
        task_context: Dict[str, Any]
        external_context: Dict[str, Any]
    
    memory = MemorySaver()
    memory_store = SQLiteStore()
    
    graph_builder = StateGraph(SalesforceState)
    
    # All Salesforce tools
    tools = [
        CreateLeadTool(), GetLeadTool(), UpdateLeadTool(),
        GetOpportunityTool(), UpdateOpportunityTool(), CreateOpportunityTool(),
        GetAccountTool(), CreateAccountTool(), UpdateAccountTool(),
        GetContactTool(), CreateContactTool(), UpdateContactTool(),
        GetCaseTool(), CreateCaseTool(), UpdateCaseTool(),
        GetTaskTool(), CreateTaskTool(), UpdateTaskTool()
    ]
    
    llm = create_azure_openai_chat()
    llm_with_tools = llm.bind_tools(tools)
    trustcall_extractor = create_extractor(
        llm,
        tools=[AccountList],
        tool_choice="AccountList",
    )
    
    # Node function: salesforce_chatbot
    def salesforce_chatbot(state: SalesforceState, config: RunnableConfig):
        """Main Salesforce agent conversation handler"""
        try:
            if debug_mode:
                logger.info(f"=== SALESFORCE AGENT START ===")
            
            summary = state.get("summary", "No summary available")
            memory_val = state.get("memory", "No memory available")
            turn = state.get("turns", 0)
            task_context = state.get("task_context", {})
            external_context = state.get("external_context", {})
            
            if debug_mode:
                logger.info(f"Processing turn: {turn}")
                logger.info(f"State keys: {list(state.keys())}")
                logger.info(f"Message count: {len(state.get('messages', []))}")
                logger.info(f"Task context: {task_context}")
                logger.info(f"External context keys: {list(external_context.keys())}")
                logger.info(f"Summary length: {len(summary)}")
                logger.info(f"Memory type: {type(memory_val)}")
            
            # Load existing memory
            if memory_val == "No memory available":
                if debug_mode:
                    logger.info("Loading memory from store...")
                user_id = config["configurable"].get("user_id", "default")
                namespace = ("memory", user_id)
                key = "AccountList"
                store_conn = memory_store.get_connection("salesforce_memory.db")
                existing_memory = store_conn.get(namespace, key)
                if debug_mode:
                    logger.info(f"Loaded existing memory: {existing_memory is not None}")
                existing_memory = {"AccountList": existing_memory} if existing_memory else {"AccountList": AccountList().model_dump()}
            else:
                if debug_mode:
                    logger.info("Using provided memory")
                existing_memory = memory_val
            
            if debug_mode:
                logger.info(f"Memory keys: {list(existing_memory.keys()) if isinstance(existing_memory, dict) else 'not dict'}")
            
            # Create enhanced system message with A2A context
            if debug_mode:
                logger.info("Creating enhanced system message...")
            enhanced_summary = summary
            if task_context:
                enhanced_summary += f"\n\nCURRENT TASK CONTEXT:\n{json.dumps(task_context, indent=2)}"
                if debug_mode:
                    logger.info("Added task context to summary")
            
            if external_context:
                enhanced_summary += f"\n\nEXTERNAL CONTEXT:\n{json.dumps(external_context, indent=2)}"
                if debug_mode:
                    logger.info("Added external context to summary")
            
            if debug_mode:
                logger.info(f"Enhanced summary length: {len(enhanced_summary)}")
                logger.info("Creating system message...")
            system_message = chatbot_sys_msg(enhanced_summary, existing_memory)
            if debug_mode:
                logger.info(f"System message length: {len(system_message)}")
            
            messages = [SystemMessage(content=system_message)] + state["messages"]
            if debug_mode:
                logger.info(f"Total messages before conversion: {len(messages)}")
            
            # Clean orphaned tool calls to prevent 400 errors
            if debug_mode:
                logger.info("Cleaning orphaned tool calls...")
            clean_messages = clean_orphaned_tool_calls(messages)
            if debug_mode:
                logger.info(f"Clean messages count: {len(clean_messages)}")
                # Log message types for debugging
                for i, msg in enumerate(clean_messages):
                    logger.info(f"Message {i}: {type(msg).__name__} - {str(msg)[:100]}...")
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
                logger.info("Updating state manager...")
            salesforce_state_mgr.update_state({
                "messages": response, 
                "memory": existing_memory, 
                "turns": turn + 1
            })
            
            final_state = {
                "messages": response,
                "memory": existing_memory, 
                "turns": turn + 1
            }
            
            if debug_mode:
                logger.info(f"Final state keys: {list(final_state.keys())}")
                logger.info(f"=== SALESFORCE AGENT SUCCESS ===")
            return final_state
            
        except Exception as e:
            if debug_mode:
                logger.error(f"=== SALESFORCE AGENT ERROR ===")
                logger.error(f"Error type: {type(e).__name__}")
                logger.error(f"Error message: {str(e)}")
                logger.error(f"State keys: {list(state.keys())}")
                logger.error(f"Config keys: {list(config.keys()) if isinstance(config, dict) else 'not dict'}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
            else:
                logger.error(f"Error in Salesforce agent: {e}")
            raise
    
    # Node function: summarize_conversation
    def summarize_conversation(state: SalesforceState):
        """Summarize conversation when it gets too long"""
        summary = state.get("summary", "No summary available")
        memory_val = state.get("memory", "No memory available")
        
        if debug_mode:
            logger.info("Summarizing Salesforce conversation")
        
        system_message = summary_sys_msg(summary, memory_val)
        messages = state["messages"] + [HumanMessage(content=system_message)]
        # Clean orphaned tool calls to prevent 400 errors
        clean_messages = clean_orphaned_tool_calls(messages)
        response = llm.invoke(clean_messages)
        
        delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-2]]
        return {"summary": response.content, "messages": delete_messages}
    
    # Node function: memorize_records
    async def memorize_records(state: SalesforceState, config: RunnableConfig):
        """Update Salesforce records memory"""
        user_id = config["configurable"].get("user_id", "default")
        namespace = ("memory", user_id)
        key = "AccountList"
        store_conn = memory_store.get_connection("salesforce_memory.db")
        existing_memory = store_conn.get(namespace, key)
        existing_records = {"AccountList": existing_memory} if existing_memory else {"AccountList": AccountList().model_dump()}
        
        if debug_mode:
            logger.info(f"Updating Salesforce memory")
        
        messages = {
            "messages": [SystemMessage(content=TRUSTCALL_INSTRUCTION),
                        HumanMessage(content=state.get("summary", ""))],
            "existing": existing_records,
        }
        
        response = await trustcall_extractor.ainvoke(messages)
        if debug_mode:
            logger.info(f"Memory update response received")
        
        response = response["responses"][0].model_dump()
        store_conn.put(namespace, key, response)
        
        return {"memory": response, "turns": 0}
    
    # Conditional functions
    def needs_summary(state: SalesforceState):
        if len(state["messages"]) > 6:
            return "summarize_conversation"
        return END
    
    def needs_memory(state: SalesforceState):
        if state.get("turns", 0) > 6:
            return "memorize_records"
        return END
    
    # Build the graph
    tool_node = ToolNode(tools=tools)
    graph_builder.add_node("tools", tool_node)
    graph_builder.add_node("conversation", salesforce_chatbot)
    graph_builder.add_node("summarize_conversation", summarize_conversation)
    graph_builder.add_node("memorize_records", memorize_records)
    
    graph_builder.set_entry_point("conversation")
    graph_builder.add_conditional_edges("conversation", tools_condition)
    graph_builder.add_conditional_edges("conversation", needs_summary)
    graph_builder.add_conditional_edges("conversation", needs_memory)
    graph_builder.add_edge("tools", "conversation")
    graph_builder.set_finish_point("conversation")
    
    return graph_builder.compile(checkpointer=memory, store=memory_store)

# Build the graph at module level - removed to avoid blocking import
# salesforce_graph = build_salesforce_graph(debug_mode=False)

class SalesforceA2AHandler:
    """Handles A2A protocol requests for the Salesforce agent"""
    
    def __init__(self, graph, debug_mode: bool = False):
        self.graph = graph
        self.debug_mode = debug_mode
    
    async def process_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process an A2A task request"""
        try:
            task_data = params.get("task", {})
            
            if self.debug_mode:
                logger.info(f"Processing A2A task: {task_data.get('id', 'unknown')}")
            
            # Extract task information
            instruction = task_data.get("instruction", "")
            context = task_data.get("context", {})
            state_snapshot = task_data.get("state_snapshot", {})
            
            # Prepare initial state for the Salesforce graph
            initial_state = {
                "messages": [{"role": "user", "content": instruction}],
                "task_context": {
                    "task_id": task_data.get("id"),
                    "instruction": instruction
                },
                "external_context": context
            }
            
            # Include state snapshot information
            if "messages" in state_snapshot:
                # Include context from previous messages (last few for context)
                previous_messages = state_snapshot["messages"][-3:] if len(state_snapshot["messages"]) > 3 else state_snapshot["messages"]
                initial_state["external_context"]["previous_messages"] = previous_messages
            
            if "memory" in state_snapshot:
                initial_state["memory"] = state_snapshot["memory"]
            
            # Configure the graph execution
            config = {
                "configurable": {
                    "thread_id": f"sf-task-{task_data.get('id', 'default')}",
                    "user_id": context.get("user_context", {}).get("user_id", "default")
                }
            }
            
            # Process the task through the Salesforce graph
            result = await self.graph.ainvoke(initial_state, config)
            
            # Extract response and prepare A2A response
            response_message = result.get("messages", [])
            if response_message and len(response_message) > 0:
                last_message = response_message[-1]
                if hasattr(last_message, 'content'):
                    response_content = last_message.content
                else:
                    response_content = str(last_message)
            else:
                response_content = "Task completed successfully"
            
            # Prepare state updates for the orchestrator
            state_updates = {}
            
            if "memory" in result:
                state_updates["memory_updates"] = result["memory"]
            
            # Extract any Salesforce entities created/updated
            if "messages" in result:
                # Look for tool call results that might contain Salesforce records
                salesforce_entities = {}
                for message in result["messages"]:
                    if hasattr(message, 'tool_calls') and message.tool_calls:
                        for tool_call in message.tool_calls:
                            if any(sf_term in tool_call.get("name", "").lower() 
                                  for sf_term in ["lead", "account", "opportunity", "contact", "case", "task"]):
                                # This is a Salesforce operation
                                entity_type = tool_call.get("name", "").replace("get_", "").replace("create_", "").replace("update_", "")
                                if entity_type not in salesforce_entities:
                                    salesforce_entities[entity_type] = []
                
                if salesforce_entities:
                    state_updates["shared_entities"] = salesforce_entities
            
            return {
                "artifacts": [{
                    "id": f"sf-response-{task_data.get('id', 'unknown')}",
                    "task_id": task_data.get("id"),
                    "content": response_content,
                    "content_type": "text/plain"
                }],
                "state_updates": state_updates,
                "status": "completed"
            }
            
        except Exception as e:
            logger.error(f"Error processing A2A task: {e}")
            return {
                "artifacts": [{
                    "id": f"sf-error-{task_data.get('id', 'unknown')}",
                    "task_id": task_data.get("id"),
                    "content": f"Error processing Salesforce request: {str(e)}",
                    "content_type": "text/plain"
                }],
                "status": "failed",
                "error": str(e)
            }
    
    async def get_agent_card(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return the Salesforce agent card"""
        return {
            "name": "salesforce-agent",
            "version": "1.0.0",
            "description": "Specialized agent for Salesforce CRM operations including leads, accounts, opportunities, contacts, cases, and tasks",
            "capabilities": [
                "salesforce_operations",
                "lead_management", 
                "account_management",
                "opportunity_tracking",
                "contact_management",
                "case_handling",
                "task_management",
                "crm_operations"
            ],
            "endpoints": {
                "process_task": "/a2a",
                "agent_card": "/a2a/agent-card"
            },
            "communication_modes": ["sync", "streaming"],
            "metadata": {
                "framework": "langgraph",
                "tools_count": 15,
                "memory_type": "sqlite_with_trustcall"
            }
        }

async def main():
    """Main function to run the Salesforce agent"""
    parser = argparse.ArgumentParser(description="Salesforce Specialized Agent")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--port", type=int, default=8001, help="Port to run the A2A server on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the A2A server to")
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
    
    logger.info("Starting Salesforce Specialized Agent...")
    
    # Create the agent card
    agent_card = AgentCard(
        name="salesforce-agent",
        version="1.0.0", 
        description="Specialized agent for Salesforce CRM operations",
        capabilities=[
            "salesforce_operations", "lead_management", "account_management",
            "opportunity_tracking", "contact_management", "case_handling", "task_management"
        ],
        endpoints={
            "process_task": f"http://{args.host}:{args.port}/a2a",
            "agent_card": f"http://{args.host}:{args.port}/a2a/agent-card"
        },
        communication_modes=["sync", "streaming"]
    )
    
    # Build the graph with debug mode if requested
    logger.info("Building Salesforce graph...")
    local_graph = build_salesforce_graph(debug_mode=DEBUG_MODE)
    logger.info("Graph built successfully")
    
    # Create A2A handler
    handler = SalesforceA2AHandler(local_graph, DEBUG_MODE)
    
    # Create and configure A2A server
    server = A2AServer(agent_card, args.host, args.port)
    server.register_handler("process_task", handler.process_task)
    server.register_handler("get_agent_card", handler.get_agent_card)
    
    # Start the server
    runner = await server.start()
    
    logger.info(f"Salesforce Agent running on {args.host}:{args.port}")
    logger.info("Agent capabilities: " + ", ".join(agent_card.capabilities))
    logger.info("Press Ctrl+C to stop")
    
    try:
        # Keep the server running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down Salesforce Agent...")
        await server.stop(runner)

if __name__ == "__main__":
    asyncio.run(main())