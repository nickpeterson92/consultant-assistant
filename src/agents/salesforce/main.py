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

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import AzureChatOpenAI

# Imports no longer need path manipulation

from src.a2a import A2AServer, AgentCard

# Import from the centralized tools directory
# Using new unified tools for better performance and maintainability
from src.tools.salesforce import UNIFIED_SALESFORCE_TOOLS
# Fallback to old tools if needed
# from src.tools.salesforce_tools import ALL_SALESFORCE_TOOLS

import logging

# Disable LangSmith tracing to avoid circular reference errors
os.environ["LANGCHAIN_TRACING_V2"] = "false"

# Import unified logger
from src.utils.logging import get_logger
from src.utils.config import get_llm_config
from src.utils.agents.prompts import salesforce_agent_sys_msg

# Initialize structured logger
logger = get_logger("salesforce")

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
    llm_kwargs = {
        "azure_endpoint": os.environ["AZURE_OPENAI_ENDPOINT"],  # Keep sensitive info in env
        "azure_deployment": llm_config.azure_deployment,
        "openai_api_version": llm_config.api_version,
        "openai_api_key": os.environ["AZURE_OPENAI_API_KEY"],  # Keep sensitive info in env
        "temperature": llm_config.temperature,
        "max_tokens": llm_config.max_tokens,
        "timeout": llm_config.timeout,
    }
    if llm_config.top_p is not None:
        llm_kwargs["top_p"] = llm_config.top_p
    return AzureChatOpenAI(**llm_kwargs)

def build_salesforce_graph():
    """Build modern LangGraph using 2024 best practices"""
    
    load_dotenv()
    
    # Modern minimal state schema - LangGraph prefers MessagesState when possible
    class SalesforceState(TypedDict):
        messages: Annotated[list, add_messages]
        task_context: Dict[str, Any]
        external_context: Dict[str, Any]
    
    # Using new unified Salesforce tools (reduced from 23 to 6 tools)
    tools = UNIFIED_SALESFORCE_TOOLS
    
    llm = create_azure_openai_chat()
    llm_with_tools = llm.bind_tools(tools)
    
    # Simplified agent node following 2024 patterns
    def salesforce_agent(state: SalesforceState, config: RunnableConfig):
        """Modern Salesforce agent node"""
        task_id = state.get("task_context", {}).get("task_id", "unknown")
        
        # Log agent node entry
        logger.info("salesforce_agent_node_entry",
            component="salesforce",
            operation="process_messages",
            task_id=task_id,
            message_count=len(state.get("messages", [])),
            has_task_context=bool(state.get("task_context")),
            has_external_context=bool(state.get("external_context"))
        )
        
        try:
            task_context = state.get("task_context", {})
            external_context = state.get("external_context", {})
            
            # Create system message
            system_message_content = salesforce_agent_sys_msg(task_context, external_context)
            messages = [SystemMessage(content=system_message_content)] + state["messages"]
            
            # Log LLM call
            logger.info("salesforce_llm_invocation_start",
                component="salesforce",
                operation="invoke_llm",
                task_id=task_id,
                message_count=len(messages),
                system_message_length=len(system_message_content)
            )
            
            # Invoke LLM with tools
            response = llm_with_tools.invoke(messages)
            
            # Log LLM response
            logger.info("salesforce_llm_invocation_complete",
                component="salesforce",
                operation="invoke_llm",
                task_id=task_id,
                has_tool_calls=bool(hasattr(response, 'tool_calls') and response.tool_calls),
                response_length=len(str(response.content)) if hasattr(response, 'content') else 0
            )
            
            # Cost tracking removed - activity logger no longer exists
            
            return {"messages": [response]}
            
        except Exception as e:
            logger.error("salesforce_agent_error",
                component="salesforce",
                operation="process_messages",
                task_id=task_id,
                error=str(e),
                error_type=type(e).__name__
            )
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
    async def process_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process A2A task using modern LangGraph pattern"""
        try:
            # A2A protocol wraps task in "task" key
            task_data = params.get("task", params)  # Support both wrapped and unwrapped
            task_id = task_data.get("id", task_data.get("task_id", "unknown"))
            instruction = task_data.get("instruction", "")
            context = task_data.get("context", {})
            
            # Log task start with more detail
            logger.info("salesforce_a2a_task_start",
                component="salesforce",
                operation="process_a2a_task",
                task_id=task_id,
                instruction_preview=instruction[:100] if instruction else "",
                instruction_length=len(instruction) if instruction else 0,
                context_keys=list(context.keys()) if context else [],
                context_size=len(str(context)) if context else 0
            )
            
            # Simple state preparation - modern LangGraph prefers minimal state
            initial_state = {
                "messages": [HumanMessage(content=instruction)],
                "task_context": {"task_id": task_id, "instruction": instruction},
                "external_context": context
            }
            
            # Modern config - no need for complex setup
            # Get recursion limit from config
            llm_config = get_llm_config()
            config = {
                "configurable": {
                    "thread_id": f"sf-{task_id}",
                },
                "recursion_limit": llm_config.recursion_limit  # Prevent runaway tool calls
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
            
            # Log tool calls found in messages
            for msg in messages:
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        logger.info("tool_call", component="salesforce",
                                               task_id=task_id,
                                               tool_name=tool_call.get("name", "unknown"),
                                               tool_args=tool_call.get("args", {}))
            
            # Log task completion
            logger.info("salesforce_a2a_task_complete",
                component="salesforce",
                operation="process_a2a_task",
                task_id=task_id,
                success=True,
                                   response_preview=response_content[:200])
            
            # Modern simplified response
            return {
                "artifacts": [{
                    "id": f"sf-response-{task_id}",
                    "task_id": task_id,
                    "content": response_content,
                    "content_type": "text/plain"
                }],
                "status": "completed"
            }
            
        except Exception as e:
            error_msg = str(e)
            # Check for specific error types
            if "GraphRecursionError" in type(e).__name__ or "recursion limit" in error_msg.lower():
                error_msg = "Query complexity exceeded maximum iterations. Please try a more specific search."
            elif "GRAPH_RECURSION_LIMIT" in error_msg:
                error_msg = "Too many tool calls required. Please simplify your request."
                
            logger.error("salesforce_a2a_task_error",
                component="salesforce",
                operation="process_a2a_task",
                task_id=task_id,
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "artifacts": [{
                    "id": f"sf-error-{task_id}",
                    "task_id": task_id,
                    "content": f"Error processing Salesforce request: {error_msg}",
                    "content_type": "text/plain"
                }],
                "status": "failed",
                "error": error_msg
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
        await server.stop(runner)
        
        # Clean up the global connection pool
        from src.a2a.protocol import get_connection_pool
        pool = get_connection_pool()
        await pool.close_all()

if __name__ == "__main__":
    asyncio.run(main())