"""Salesforce specialized agent for CRM operations via A2A protocol."""

import os
import asyncio
import argparse
import json
from typing import Annotated, Dict, Any
from typing_extensions import TypedDict

from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

# Imports no longer need path manipulation

from src.a2a import A2AServer, AgentCard

# Import from the centralized tools directory
# Using new unified tools for better performance and maintainability
from src.tools.salesforce import UNIFIED_SALESFORCE_TOOLS

import logging

# Disable LangSmith tracing to avoid circular reference errors
os.environ["LANGCHAIN_TRACING_V2"] = "false"

# Import unified logger
from src.utils.logging import get_logger
from src.utils.config.unified_config import config as app_config
from src.utils.llm import create_azure_openai_chat
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
            
            # Import trimming utility
            from src.utils.agents.message_processing import trim_messages_for_context, estimate_message_tokens
            
            # Trim messages to prevent token limit issues
            state_messages = state.get("messages", [])
            trimmed_messages = trim_messages_for_context(
                state_messages,
                max_tokens=70000,  # Conservative limit for agent
                keep_system=False,  # System message added separately
                keep_first_n=2,     # Keep original request context
                keep_last_n=10,     # Keep recent tool interactions
                use_smart_trimming=True
            )
            
            # Log token usage
            system_tokens = estimate_message_tokens([SystemMessage(content=system_message_content)])
            message_tokens = estimate_message_tokens(trimmed_messages)
            total_tokens = system_tokens + message_tokens
            
            logger.info("salesforce_token_usage",
                component="salesforce",
                operation="prepare_messages",
                task_id=task_id,
                original_message_count=len(state_messages),
                trimmed_message_count=len(trimmed_messages),
                system_tokens=system_tokens,
                message_tokens=message_tokens,
                total_tokens=total_tokens,
                token_limit=128000
            )
            
            messages = [SystemMessage(content=system_message_content)] + trimmed_messages
            
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
            
            # Log LLM response with full content for debugging
            has_tool_calls = bool(hasattr(response, 'tool_calls') and response.tool_calls)  # pyright: ignore[reportAttributeAccessIssue]
            response_content = str(response.content) if hasattr(response, 'content') else ""
            
            # Include tool call details in the debug log
            tool_call_details = []
            if has_tool_calls and hasattr(response, 'tool_calls'):
                for tc in response.tool_calls:  # pyright: ignore[reportAttributeAccessIssue]
                    # Handle both dict and object access patterns
                    if isinstance(tc, dict):
                        tool_name = tc.get('name', 'unknown')
                        tool_args = tc.get('args', {})
                    else:
                        tool_name = getattr(tc, 'name', 'unknown')
                        tool_args = getattr(tc, 'args', {})
                    
                    tool_call_details.append({
                        'name': tool_name,
                        'args': tool_args
                    })
            
            logger.info("salesforce_llm_invocation_complete",
                component="salesforce",
                operation="invoke_llm",
                task_id=task_id,
                has_tool_calls=has_tool_calls,
                response_length=len(response_content),
                response_content_full=response_content if not has_tool_calls else "TOOL_CALLS_PRESENT",
                tool_calls=tool_call_details if has_tool_calls else None
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
    
    def __init__(self, graph, server=None):
        self.graph = graph
        self.server = server
    async def process_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process A2A task using modern LangGraph pattern"""
        # Initialize task_id for use in except block
        task_id = "unknown"
        
        try:
            # A2A protocol wraps task in "task" key
            task_data = params.get("task", params)  # Support both wrapped and unwrapped
            task_id = task_data.get("id", task_data.get("task_id", "unknown"))
            
            # Check for immediate interrupt before processing
            if self.server and self.server.is_task_interrupted(task_id):
                logger.info("salesforce_task_interrupted",
                           component="salesforce",
                           operation="process_a2a_task",
                           task_id=task_id,
                           status="interrupted_before_start")
                self.server.clear_task_interrupt(task_id)
                return {
                    "artifacts": [{
                        "id": f"sf-interrupt-{task_id}",
                        "task_id": task_id,
                        "content": "Task was interrupted before execution started",
                        "content_type": "text/plain"
                    }],
                    "status": "failed",
                    "error": "Task was interrupted",
                    "error_type": "TaskInterrupted"
                }
            instruction = task_data.get("instruction", "")
            context = task_data.get("context", {})
            state_snapshot = task_data.get("state_snapshot", {})
            
            # Merge state_snapshot into context for full orchestrator state access
            merged_context = {
                **context,
                "orchestrator_state": state_snapshot
            }
            
            # Log task start with more detail
            logger.info("salesforce_a2a_task_start",
                component="salesforce",
                operation="process_a2a_task",
                task_id=task_id,
                instruction_preview=instruction[:100] if instruction else "",
                instruction_length=len(instruction) if instruction else 0,
                context_keys=list(context.keys()) if context else [],
                context_size=len(str(context)) if context else 0,
                has_state_snapshot=bool(state_snapshot),
                state_snapshot_keys=list(state_snapshot.keys()) if state_snapshot else []
            )
            
            # Simple state preparation - modern LangGraph prefers minimal state
            initial_state = {
                "messages": [HumanMessage(content=instruction)],
                "task_context": {"task_id": task_id, "instruction": instruction},
                "external_context": merged_context
            }
            
            # Modern config - no need for complex setup
            # Get recursion limit from config
            config = {
                "configurable": {
                    "thread_id": f"sf-{task_id}",
                },
                "recursion_limit": app_config.llm_recursion_limit  # Prevent runaway tool calls
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
            
            # Check if this is an error message from agent (follows standard Error: prefix pattern)
            is_error_response = False
            if isinstance(response_content, str) and response_content.startswith("Error:"):
                is_error_response = True
            
            # Check final tool outcome - agents may retry multiple times before succeeding
            final_tool_success = None
            from langchain_core.messages import ToolMessage
            
            # Find the LAST ToolMessage result to determine final outcome
            for msg in reversed(messages):
                if isinstance(msg, ToolMessage) and hasattr(msg, 'content'):
                    # Try to parse tool result as JSON to check success field
                    try:
                        if isinstance(msg.content, str) and (msg.content.startswith('{') or msg.content.startswith('[')):
                            tool_result = json.loads(msg.content)
                            if isinstance(tool_result, dict) and 'success' in tool_result:
                                final_tool_success = tool_result.get('success')
                                break
                    except (json.JSONDecodeError, AttributeError):
                        # If not valid JSON, continue checking other messages
                        pass
            
            # Determine actual task success based on multiple factors:
            # 1. If final response starts with "Error:", it's a failure
            # 2. If tool execution failed (final_tool_success is False), it's a failure
            # 3. If no tool results found and no error response, assume success
            task_success = not is_error_response and final_tool_success is not False
            status = "completed" if task_success else "failed"
            
            # Log tool calls found in messages
            for msg in messages:
                if hasattr(msg, 'tool_calls') and msg.tool_calls:  # pyright: ignore[reportAttributeAccessIssue]
                    for tool_call in msg.tool_calls:  # pyright: ignore[reportAttributeAccessIssue]
                        # Handle both dict and object access patterns
                        if isinstance(tool_call, dict):
                            tool_name = tool_call.get("name", "unknown")
                            tool_args = tool_call.get("args", {})
                        else:
                            tool_name = getattr(tool_call, "name", "unknown")
                            tool_args = getattr(tool_call, "args", {})
                        
                        logger.info("tool_call", component="salesforce",
                                               task_id=task_id,
                                               tool_name=tool_name,
                                               tool_args=tool_args)
            
            # Log task completion with actual success status
            logger.info("salesforce_a2a_task_complete",
                component="salesforce",
                operation="process_a2a_task",
                task_id=task_id,
                success=task_success,
                final_tool_success=final_tool_success,
                is_error_response=is_error_response,
                response_preview=response_content[:200])
            
            # Create result with computed status
            result_dict = {
                "artifacts": [{
                    "id": f"sf-response-{task_id}",
                    "task_id": task_id,
                    "content": response_content,
                    "content_type": "text/plain"
                }],
                "status": status
            }
            
            # Include error information if task failed
            if not task_success:
                result_dict["error"] = "Task execution encountered errors"
                
            return result_dict
            
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
    
    # Create and configure A2A server
    server = A2AServer(agent_card, args.host, args.port)
    
    # Create A2A handler with server reference for interrupt checking
    handler = SalesforceA2AHandler(local_graph, server)
    server.register_handler("process_task", handler.process_task)
    server.register_handler("get_agent_card", handler.get_agent_card)
    
    # Set up interrupt WebSocket endpoint
    await server.setup_interrupt_websocket()
    
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