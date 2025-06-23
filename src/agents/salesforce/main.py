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

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from langgraph.prebuilt import ToolNode

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import AzureChatOpenAI

# Imports no longer need path manipulation

from src.a2a import A2AServer, AgentCard

# Import from the centralized tools directory
from src.tools.salesforce_tools import ALL_SALESFORCE_TOOLS

import logging

# Disable LangSmith tracing to avoid circular reference errors
os.environ["LANGCHAIN_TRACING_V2"] = "false"

# Add structured logging
# Path manipulation no longer needed
from src.utils.logging import log_salesforce_activity
from src.utils.config import get_llm_config
from src.utils.sys_msg import salesforce_agent_sys_msg

# Logging function now imported from centralized activity_logger

logger = logging.getLogger(__name__)

# Suppress verbose HTTP debug logs
logging.getLogger('openai._base_client').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('httpcore.http11').setLevel(logging.WARNING)
logging.getLogger('httpcore.connection').setLevel(logging.WARNING)
# Remove structured logger in favor of direct file logging
# Remove structured perf tracker in favor of direct file logging

# Salesforce agent is now "dumb" - no state management or memory

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

def build_salesforce_graph():
    """Build and compile the Salesforce agent LangGraph"""
    
    load_dotenv()
    
    # Define the simple Salesforce agent state schema (dumb agent)
    class SalesforceState(TypedDict):
        messages: Annotated[list, add_messages]
        task_context: Dict[str, Any]
        external_context: Dict[str, Any]
    
    graph_builder = StateGraph(SalesforceState)
    
    # All Salesforce tools including CRUD and analytics
    tools = ALL_SALESFORCE_TOOLS
    
    llm = create_azure_openai_chat()
    llm_with_tools = llm.bind_tools(tools)
    
    # Node function: salesforce_chatbot (simplified dumb agent)
    def salesforce_chatbot(state: SalesforceState, config: RunnableConfig):
        """Simplified Salesforce agent conversation handler - no memory/summarization"""
        try:
            
            task_context = state.get("task_context", {})
            external_context = state.get("external_context", {})
            
            # Create system message for Salesforce operations using centralized function
            system_message_content = salesforce_agent_sys_msg(task_context, external_context)
            
            messages = [SystemMessage(content=system_message_content)] + state["messages"]
            
            # Log Salesforce LLM call
            log_salesforce_activity("SALESFORCE_LLM_CALL",
                                   message_count=len(messages),
                                   task_id=state.get("task_context", {}).get("task_id", "unknown"))
            
            # Estimate token usage for cost tracking
            message_chars = sum(len(str(m.content if hasattr(m, 'content') else m)) for m in messages)
            estimated_tokens = message_chars // 4  # Rough estimate: 4 chars per token
            
            response = llm_with_tools.invoke(messages)
            
            # Log cost after response
            from src.utils.logging.activity_logger import log_cost_activity
            log_cost_activity("SALESFORCE_LLM_CALL", estimated_tokens,
                             message_count=len(messages),
                             response_length=len(str(response.content)) if hasattr(response, 'content') else 0,
                             task_id=state.get("task_context", {}).get("task_id", "unknown"))
            
            return {"messages": response}
            
        except Exception as e:
            logger.error(f"Error in Salesforce agent: {e}")
            raise
    
    # No memory or summarization functions needed - dumb agent
    
    # Build the simplified graph (dumb agent)
    tool_node = ToolNode(tools=tools)
    graph_builder.add_node("tools", tool_node)
    graph_builder.add_node("conversation", salesforce_chatbot)
    
    # Custom condition to prevent infinite loops
    def should_continue(state: SalesforceState):
        """Check if we should continue or end"""
        messages = state.get("messages", [])
        if not messages:
            return END
            
        last_message = messages[-1]
        
        # If the last message has tool calls, go to tools
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"
        
        # If we have more than 15 messages, force end to prevent loops (increased from 10)
        if len(messages) > 15:
            return END
            
        # Otherwise end
        return END
    
    graph_builder.set_entry_point("conversation")
    graph_builder.add_conditional_edges("conversation", should_continue)
    graph_builder.add_edge("tools", "conversation")  # Go back to conversation to handle tool results
    
    return graph_builder.compile()

# Build the graph at module level
salesforce_graph = None  # Will be created when needed

class SalesforceA2AHandler:
    """Handles A2A protocol requests for the Salesforce agent"""
    
    def __init__(self, graph):
        self.graph = graph
    async def process_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process an A2A task request"""
        try:
            # Log A2A task processing
            log_salesforce_activity("A2A_TASK_START", 
                                   task_id=params.get("task", {}).get("id", "unknown"),
                                   instruction_preview=params.get("task", {}).get("instruction", "")[:100])
            task_data = params.get("task", {})
            
            
            # Extract task information
            instruction = task_data.get("instruction", "")
            
            # Log task details
            log_salesforce_activity("A2A_TASK_RECEIVED", 
                                   task_id=task_data.get("id", "unknown"),
                                   instruction=instruction[:200])
            context = task_data.get("context", {})
            state_snapshot = task_data.get("state_snapshot", {})
            
            # Prepare initial state for the Salesforce graph
            initial_state = {
                "messages": [HumanMessage(content=instruction)],  # Use proper LangChain message objects!
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
                },
                "recursion_limit": 50  # Increase from default 25 to handle complex queries
            }
            
            # Process the task through the Salesforce graph
            result = await self.graph.ainvoke(initial_state, config)
            
            # Log Salesforce operation result
            if "messages" in result:
                for msg in result["messages"]:
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            log_salesforce_activity("TOOL_CALL",
                                                   task_id=task_data.get("id", "unknown"),
                                                   tool_name=tool_call.get("name", "unknown"),
                                                   tool_args=tool_call.get("args", {}))
            
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
            
            log_salesforce_activity("TASK_COMPLETED", 
                                   task_id=task_data.get("id", "unknown"),
                                   response_preview=response_content[:200])
            
            # Prepare state updates for the orchestrator
            state_updates = {}
            
            if "memory" in result:
                state_updates["memory_updates"] = result["memory"]
            
            # Extract any Salesforce entities created/updated
            tool_results = []
            if "messages" in result:
                # Look for tool messages that contain actual Salesforce data
                for message in result["messages"]:
                    # Check for ToolMessage (which contains tool results)
                    if hasattr(message, 'name') and hasattr(message, 'content'):
                        # This is a ToolMessage with actual tool results
                        tool_name = getattr(message, 'name', '') or ''  # Handle None case
                        tool_content = getattr(message, 'content', '')
                        
                        if tool_name and any(sf_term in tool_name.lower() for sf_term in ["lead", "account", "opportunity", "contact", "case", "task"]):
                            # This is a Salesforce tool result with structured data
                            try:
                                import json
                                if isinstance(tool_content, str) and tool_content.strip().startswith('{'):
                                    parsed_content = json.loads(tool_content)
                                    tool_results.append({
                                        "tool_name": tool_name,
                                        "tool_data": parsed_content
                                    })
                                elif isinstance(tool_content, dict):
                                    tool_results.append({
                                        "tool_name": tool_name,
                                        "tool_data": tool_content
                                    })
                            except (json.JSONDecodeError, AttributeError):
                                # If tool result isn't JSON, include as-is
                                tool_results.append({
                                    "tool_name": tool_name,
                                    "tool_data": str(tool_content)
                                })
                
                if tool_results:
                    state_updates["tool_results"] = tool_results
            
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
            "description": "Specialized agent for Salesforce CRM operations including leads, accounts, opportunities, contacts, cases, tasks, and advanced analytics",
            "capabilities": [
                "salesforce_operations",
                "lead_management", 
                "account_management",
                "opportunity_tracking",
                "contact_management",
                "case_handling",
                "task_management",
                "crm_operations",
                "sales_analytics",
                "pipeline_analysis",
                "business_metrics",
                "global_search",
                "aggregate_reporting"
            ],
            "endpoints": {
                "process_task": "/a2a",
                "agent_card": "/a2a/agent-card"
            },
            "communication_modes": ["sync", "streaming"],
            "metadata": {
                "framework": "langgraph",
                "tools_count": 20,
                "memory_type": "sqlite_with_trustcall"
            }
        }

async def main():
    """Main function to run the Salesforce agent"""
    parser = argparse.ArgumentParser(description="Salesforce Specialized Agent")
    parser.add_argument("--port", type=int, default=8001, help="Port to run the A2A server on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the A2A server to")
    args = parser.parse_args()
    
    # Setup logging - suppress console output
    log_level = logging.WARNING
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Suppress ALL HTTP noise comprehensively
    # OpenAI/Azure related
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('openai._base_client').setLevel(logging.WARNING)
    logging.getLogger('openai.resources').setLevel(logging.WARNING)
    logging.getLogger('azure').setLevel(logging.WARNING)
    
    # HTTP libraries
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('httpcore.http11').setLevel(logging.WARNING)
    logging.getLogger('httpcore.connection').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('aiohttp.access').setLevel(logging.WARNING)
    
    # Salesforce related
    logging.getLogger('simple_salesforce').setLevel(logging.WARNING)
    logging.getLogger('salesforce').setLevel(logging.WARNING)
    
    # Any other potential HTTP noise
    for logger_name in logging.root.manager.loggerDict:
        if any(term in logger_name.lower() for term in ['http', 'request', 'urllib', 'connection']):
            logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    # Suppress internal system component logging to console (keep file logging)
    logging.getLogger('src.a2a.circuit_breaker').setLevel(logging.WARNING)
    logging.getLogger('src.utils.config').setLevel(logging.WARNING)
    logging.getLogger('src.a2a.protocol').setLevel(logging.WARNING)
    
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
        description="Specialized agent for Salesforce CRM operations including advanced analytics",
        capabilities=[
            "salesforce_operations", "lead_management", "account_management",
            "opportunity_tracking", "contact_management", "case_handling", 
            "task_management", "sales_analytics", "pipeline_analysis",
            "business_metrics", "global_search", "aggregate_reporting"
        ],
        endpoints={
            "process_task": f"http://{args.host}:{args.port}/a2a",
            "agent_card": f"http://{args.host}:{args.port}/a2a/agent-card"
        },
        communication_modes=["sync", "streaming"]
    )
    
    # Build the graph with debug mode if requested
    logger.info("Building Salesforce graph...")
    local_graph = build_salesforce_graph()
    logger.info("Graph built successfully")
    
    # Create A2A handler
    handler = SalesforceA2AHandler(local_graph)
    
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