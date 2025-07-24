"""Salesforce specialized agent for CRM operations via A2A protocol."""

import os
import asyncio
import argparse
from typing import Annotated, Dict, Any
from typing_extensions import TypedDict

from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import AzureChatOpenAI

# Imports no longer need path manipulation

from src.a2a import A2AServer, AgentCard
from src.agents.shared.memory_writer import write_tool_result_to_memory
from src.utils.thread_utils import create_thread_id

# Import from the centralized tools directory
# Using new unified tools for better performance and maintainability
from src.agents.salesforce.tools.unified import UNIFIED_SALESFORCE_TOOLS
# Fallback to old tools if needed
# from src.tools.salesforce_tools import ALL_SALESFORCE_TOOLS

import logging

# Disable LangSmith tracing to avoid circular reference errors
os.environ["LANGCHAIN_TRACING_V2"] = "false"

# Import SmartLogger framework
from src.utils.logging.framework import SmartLogger, log_execution
from src.utils.config import config
from src.utils.prompt_templates import create_salesforce_agent_prompt, ContextInjector

# Initialize structured logger
logger = SmartLogger("salesforce")


@log_execution(component="salesforce", operation="periodic_cleanup")
async def periodic_cleanup():
    """Periodically clean up idle A2A connections."""
    from src.a2a.protocol import get_connection_pool
    
    while True:
        try:
            # Wait 60 seconds between cleanups
            await asyncio.sleep(60)
            
            # Clean up idle sessions
            pool = get_connection_pool()
            await pool.cleanup_idle_sessions()
            
            logger.info("periodic_cleanup_completed",
                       component="salesforce",
                       cleanup_type="a2a_connection_pool")
                       
        except asyncio.CancelledError:
            # Task was cancelled, exit gracefully
            raise
        except Exception as e:
            logger.error("periodic_cleanup_error",
                        component="salesforce",
                        error=str(e),
                        error_type=type(e).__name__)
            # Continue running even if cleanup fails
            await asyncio.sleep(60)

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
    llm_config = config
    llm_kwargs = {
        "azure_endpoint": os.environ["AZURE_OPENAI_ENDPOINT"],  # Keep sensitive info in env
        "azure_deployment": os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4o-mini"),
        "openai_api_version": os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01"),
        "openai_api_key": os.environ["AZURE_OPENAI_API_KEY"],  # Keep sensitive info in env
        "temperature": llm_config.llm_temperature,
        "max_tokens": llm_config.llm_max_tokens,
        "timeout": llm_config.llm_timeout,
    }
    if llm_config.get('llm.top_p') is not None:
        llm_kwargs["top_p"] = llm_config.get('llm.top_p')
    return AzureChatOpenAI(**llm_kwargs)

def build_salesforce_graph():
    """Build modern LangGraph using 2024 best practices"""
    
    load_dotenv()
    
    # Modern minimal state schema - LangGraph prefers MessagesState when possible
    class SalesforceState(TypedDict):
        messages: Annotated[list, add_messages]
        task_context: Dict[str, Any]
        external_context: Dict[str, Any]
        orchestrator_state: Dict[str, Any]  # Receive state from orchestrator (one-way)
    
    # Using new unified Salesforce tools (reduced from 23 to 6 tools)
    tools = UNIFIED_SALESFORCE_TOOLS
    
    llm = create_azure_openai_chat()
    llm_with_tools = llm.bind_tools(tools)
    
    # Create the prompt template once at module level
    salesforce_prompt = create_salesforce_agent_prompt()
    
    # Simplified agent node following 2024 patterns
    @log_execution("salesforce", "salesforce_agent", include_args=False, include_result=False)
    def salesforce_agent(state: SalesforceState, config: RunnableConfig):
        """Modern Salesforce agent node using LangChain prompt templates"""
        state.get("task_context", {}).get("task_id", "unknown")
        
        
        try:
            task_context = state.get("task_context", {})
            external_context = state.get("external_context", {})
            
            # Prepare context using the new ContextInjector
            context_dict = ContextInjector.prepare_salesforce_context(task_context, external_context)
            
            # Use the prompt template to format messages
            # This leverages LangChain's prompt template features
            formatted_prompt = salesforce_prompt.format_prompt(
                messages=state["messages"],
                **context_dict
            )
            
            # Convert to messages for the LLM
            messages = formatted_prompt.to_messages()
            
            # Invoke LLM with tools
            response = llm_with_tools.invoke(messages)
            
            # Cost tracking removed - activity logger no longer exists
            
            return {"messages": [response]}
            
        except Exception:
            raise
    
    # Build modern graph following 2024 best practices
    graph_builder = StateGraph(SalesforceState)
    
    # Add nodes
    graph_builder.add_node("agent", salesforce_agent)
    graph_builder.add_node("tools", ToolNode(tools))
    
    # Modern routing using prebuilt tools_condition
    graph_builder.set_entry_point("agent")
    graph_builder.add_conditional_edges(
        "agent",
        tools_condition,
        {
            "tools": "tools",
            "__end__": END,
        }
    )
    graph_builder.add_edge("tools", "agent")
    
    return graph_builder.compile()

# Build the graph at module level
salesforce_graph = None  # Will be created when needed

class SalesforceA2AHandler:
    """Handles A2A protocol requests for the Salesforce agent"""
    
    def __init__(self, graph):
        self.graph = graph
    @log_execution("salesforce", "process_task", include_args=False, include_result=False)
    async def process_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process A2A task using modern LangGraph pattern"""
        try:
            task_data = params.get("task", {})
            task_id = task_data.get("id", "unknown")
            instruction = task_data.get("instruction", "")
            context = task_data.get("context", {})
            state_snapshot = task_data.get("state_snapshot", {})
            
            
            # Merge orchestrator state with agent state
            initial_state = {
                "messages": [HumanMessage(content=instruction)],
                "task_context": {"task_id": task_id, "instruction": instruction},
                "external_context": context,
                "orchestrator_state": state_snapshot  # Include for state merging
            }
            
            # Modern config - no need for complex setup
            config = {
                "configurable": {
                    "thread_id": create_thread_id("salesforce", task_id),
                },
                "recursion_limit": 15  # Prevent runaway tool calls
            }
            
            # Execute graph
            result = await self.graph.ainvoke(initial_state, config)
            
            # Extract response content - modern simplified approach
            messages = result.get("messages", [])
            if messages:
                last_message = messages[-1]
                response_content = getattr(last_message, 'content', str(last_message))
            else:
                response_content = "Task completed successfully"
            
            # Log tool calls and write results to memory
            thread_id = create_thread_id("salesforce", task_id)
            for i, msg in enumerate(messages):
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        logger.info("tool_call", component="salesforce",
                                               task_id=task_id,
                                               tool_name=tool_call.get("name", "unknown"),
                                               tool_args=tool_call.get("args", {}))
                        
                        # Look for the corresponding tool result in the next message
                        if i + 1 < len(messages):
                            next_msg = messages[i + 1]
                            if hasattr(next_msg, 'name') and hasattr(next_msg, 'content'):
                                # This is likely the tool result
                                try:
                                    # Write to persistent memory
                                    from src.agents.shared.memory_writer import write_tool_result_to_memory
                                    import json
                                    
                                    # Parse tool result if it's JSON
                                    tool_result = next_msg.content
                                    if isinstance(tool_result, str) and tool_result.strip().startswith('{'):
                                        try:
                                            tool_result = json.loads(tool_result)
                                        except:
                                            pass
                                    
                                    write_tool_result_to_memory(
                                        thread_id=thread_id,
                                        tool_name=tool_call.get("name", "unknown"),
                                        tool_args=tool_call.get("args", {}),
                                        tool_result=tool_result,
                                        task_id=task_id,
                                        agent_name="salesforce"
                                    )
                                except Exception as e:
                                    logger.warning("failed_to_write_tool_result",
                                                 error=str(e),
                                                 tool_name=tool_call.get("name"))
            
            
            # Modern response with state merging capability
            response = {
                "artifacts": [{
                    "id": f"sf-response-{task_id}",
                    "task_id": task_id,
                    "content": response_content,
                    "content_type": "text/plain"
                }],
                "status": "completed"
            }
            
            # No need to pass state back - we use persistent memory for tool results
            
            return response
            
        except Exception as e:
            error_msg = str(e)
            # Check for specific error types
            if "GraphRecursionError" in type(e).__name__ or "recursion limit" in error_msg.lower():
                error_msg = "Query complexity exceeded maximum iterations. Please try a more specific search."
            elif "GRAPH_RECURSION_LIMIT" in error_msg:
                error_msg = "Too many tool calls required. Please simplify your request."
                
            return {
                "artifacts": [{
                    "id": f"sf-error-{task_data.get('id', 'unknown')}",
                    "task_id": task_data.get("id"),
                    "content": f"Error processing Salesforce request: {error_msg}",
                    "content_type": "text/plain"
                }],
                "status": "failed",
                "error": error_msg
            }
    
    @log_execution("salesforce", "get_agent_card", include_args=True, include_result=True)
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
    
    # Use unified logging system - don't override global config
    # Individual tools will log at INFO level to logs/app.log

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
    # Don't suppress our own tool logging!
    # logging.getLogger('salesforce').setLevel(logging.WARNING)
    
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
    
    logger.info("agent_starting",
        component="system",
        agent="salesforce",
        operation="startup"
    )
    
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
    logger.info("graph_building",
        component="system",
        agent="salesforce",
        operation="build_graph"
    )
    local_graph = build_salesforce_graph()
    logger.info("graph_built",
        component="system",
        agent="salesforce",
        operation="build_graph",
        success=True
    )
    
    # Create A2A handler
    handler = SalesforceA2AHandler(local_graph)
    
    # Create and configure A2A server
    server = A2AServer(agent_card, args.host, args.port)
    server.register_handler("process_task", handler.process_task)
    server.register_handler("get_agent_card", handler.get_agent_card)
    
    # Start the server
    runner = await server.start()
    
    logger.info("salesforce_agent_started",
        component="system",
        operation="startup",
        agent="salesforce",
        host=args.host,
        port=args.port,
        endpoint=f"http://{args.host}:{args.port}"
    )
    logger.info("agent_capabilities",
        component="system",
        agent="salesforce",
        capabilities=agent_card.capabilities,
        capability_count=len(agent_card.capabilities)
    )
    logger.info("agent_ready",
        component="system",
        agent="salesforce",
        operation="ready"
    )
    
    # Create background tasks
    cleanup_task = asyncio.create_task(periodic_cleanup())
    
    try:
        # Keep the server running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("agent_shutdown",
            component="system",
            agent="salesforce",
            operation="shutdown"
        )
    finally:
        # Cancel background tasks
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
            
        await server.stop(runner)
        
        # Clean up the global connection pool
        from src.a2a.protocol import get_connection_pool
        pool = get_connection_pool()
        await pool.close_all()

if __name__ == "__main__":
    asyncio.run(main())