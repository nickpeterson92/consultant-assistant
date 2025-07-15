"""ServiceNow specialized agent for ITSM operations via A2A protocol."""

import os
import asyncio
from typing import Dict, Any, List, TypedDict, Annotated, Optional
import operator
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver

from src.tools.servicenow import UNIFIED_SERVICENOW_TOOLS
from src.a2a import A2AServer, AgentCard
from src.utils.config import get_llm_config
from src.utils.logging import get_logger
from src.utils.llm import create_azure_openai_chat
from src.utils.agents.prompts import servicenow_agent_sys_msg

logger = get_logger("servicenow")

# Agent state definition
class ServiceNowAgentState(TypedDict):
    """State for the ServiceNow agent."""
    messages: Annotated[List[Any], operator.add]
    current_task: str
    tool_results: List[Dict[str, Any]]
    error: str
    task_context: Dict[str, Any]
    external_context: Dict[str, Any]

def get_servicenow_system_message(task_context: Optional[Dict[Any, Any]] = None, external_context: Optional[Dict[Any, Any]] = None) -> str:
    """Generate the system message that defines the ServiceNow agent's behavior and capabilities.
    
    Returns a comprehensive system prompt that:
    - Defines the agent's role as an IT Service Management specialist
    - Lists all available tools and their capabilities
    - Provides guidance on natural language understanding
    - Sets expectations for response formatting
    """
    return servicenow_agent_sys_msg(task_context, external_context)

def build_servicenow_graph():
    """Build the ServiceNow agent graph using LangGraph."""
    
    # Initialize LLM
    llm = create_azure_openai_chat()
    
    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(UNIFIED_SERVICENOW_TOOLS)
    
    # Define agent function
    def servicenow_agent(state: ServiceNowAgentState):
        """Main agent logic for ServiceNow operations."""
        task_id = state.get("task_context", {}).get("task_id", "unknown")
        
        # Log agent entry
        logger.info("servicenow_agent_entry",
            component="servicenow",
            operation="process_task",
            task_id=task_id,
            message_count=len(state.get("messages", [])),
            has_task_context=bool(state.get("task_context")),
            has_external_context=bool(state.get("external_context"))
        )
        
        # Get system message with context
        system_msg = get_servicenow_system_message(
            task_context=state.get("task_context"),
            external_context=state.get("external_context")
        )
        
        # Import trimming utility
        from src.utils.agents.message_processing import trim_messages_for_context, estimate_message_tokens
        
        # Trim messages to prevent token limit issues
        state_messages = state.get("messages", [])
        trimmed_messages = trim_messages_for_context(
            state_messages,
            max_tokens=70000,  # Conservative limit for agent (less than orchestrator)
            keep_system=False,  # System message added separately
            keep_first_n=2,     # Keep original request context
            keep_last_n=10,     # Keep recent tool interactions
            use_smart_trimming=True
        )
        
        # Log token usage
        system_tokens = estimate_message_tokens([SystemMessage(content=system_msg)])
        message_tokens = estimate_message_tokens(trimmed_messages)
        total_tokens = system_tokens + message_tokens
        
        logger.info("servicenow_token_usage",
            component="servicenow",
            operation="prepare_messages",
            task_id=task_id,
            original_message_count=len(state_messages),
            trimmed_message_count=len(trimmed_messages),
            system_tokens=system_tokens,
            message_tokens=message_tokens,
            total_tokens=total_tokens,
            token_limit=128000
        )
        
        # Prepare messages
        messages = [SystemMessage(content=system_msg)] + trimmed_messages
        
        try:
            # Call LLM with tools
            response = llm_with_tools.invoke(messages)
            
            # Log successful response
            logger.info("servicenow_agent_response",
                component="servicenow",
                operation="llm_invoke",
                task_id=task_id,
                response_length=len(response.content),
                has_tool_calls=bool(response.tool_calls) if hasattr(response, 'tool_calls') else False  # pyright: ignore[reportAttributeAccessIssue]
            )
            
            return {"messages": [response]}
            
        except Exception as e:
            logger.error("servicenow_agent_error",
                component="servicenow",
                operation="llm_invoke",
                task_id=task_id,
                error=str(e),
                error_type=type(e).__name__
            )
            error_msg = AIMessage(content=f"I encountered an error processing your ServiceNow request: {str(e)}")
            return {"messages": [error_msg], "error": str(e)}
    
    # Create tool node
    tool_node = ToolNode(UNIFIED_SERVICENOW_TOOLS)
    
    # Build the graph
    graph_builder = StateGraph(ServiceNowAgentState)
    
    # Add nodes
    graph_builder.add_node("agent", servicenow_agent)
    graph_builder.add_node("tools", tool_node)
    
    # Add edges
    graph_builder.set_entry_point("agent")
    graph_builder.add_conditional_edges(
        "agent",
        tools_condition,
        {
            "tools": "tools",
            "__end__": END
        }
    )
    graph_builder.add_edge("tools", "agent")
    
    # Compile with memory
    memory = MemorySaver()
    return graph_builder.compile(checkpointer=memory)

# A2A Server implementation
async def handle_a2a_request(params: dict) -> dict:
    """Process a ServiceNow task via A2A protocol."""
    # Initialize task_id for use in except block
    task_id = "unknown"
    
    try:
        # Extract task data from params (support both wrapped and unwrapped formats)
        task_data = params.get("task", params)  # Support both wrapped and unwrapped
        task_id = task_data.get("id", task_data.get("task_id", "unknown"))
        instruction = task_data.get("instruction", "")
        context = task_data.get("context", {})
        state_snapshot = task_data.get("state_snapshot", {})
        
        # Merge state_snapshot into context for full orchestrator state access
        merged_context = {
            **context,
            "orchestrator_state": state_snapshot
        }
        
        logger.info("a2a_task_received",
            component="servicenow",
            operation="process_task",
            task_id=task_id,
            instruction_preview=instruction[:100] if instruction else "",
            has_context=bool(context),
            has_state_snapshot=bool(state_snapshot),
            state_snapshot_keys=list(state_snapshot.keys()) if state_snapshot else []
        )
        
        # Build the graph
        app = build_servicenow_graph()
        
        # Prepare initial state
        initial_state = {
            "messages": [HumanMessage(content=instruction)],
            "current_task": instruction,
            "tool_results": [],
            "error": "",
            "task_context": {"task_id": task_id},
            "external_context": merged_context
        }
        
        # Configure thread
        llm_config = get_llm_config()
        config = RunnableConfig(
            configurable={
                "thread_id": f"servicenow_{task_id}"
            },
            recursion_limit=llm_config.recursion_limit
        )
        
        # Run the graph
        final_state = await app.ainvoke(initial_state, config)
        
        # Extract response
        messages = final_state.get("messages", [])
        last_message = messages[-1] if messages else None
        
        if last_message:
            response_content = last_message.content
            
            # Check final tool outcome - agents may retry multiple times before succeeding
            final_tool_success = None
            from langchain_core.messages import ToolMessage
            
            # Find the LAST ToolMessage result to determine final outcome
            for msg in reversed(messages):
                if isinstance(msg, ToolMessage) and hasattr(msg, 'content'):
                    # Try to parse tool result as JSON to check success field
                    try:
                        import json
                        if isinstance(msg.content, str) and (msg.content.startswith('{') or msg.content.startswith('[')):
                            tool_result = json.loads(msg.content)
                            if isinstance(tool_result, dict) and 'success' in tool_result:
                                final_tool_success = tool_result.get('success')
                                break
                    except (json.JSONDecodeError, AttributeError):
                        # If not valid JSON, continue checking other messages
                        pass
            
            # Determine actual task success based on final tool execution result
            # If no tool results found, assume success (agent completed without tools)
            task_success = final_tool_success is not False
            status = "completed" if task_success else "failed"
            
            # Log completion with actual success status
            logger.info("a2a_task_complete",
                component="servicenow",
                operation="process_task",
                task_id=task_id,
                response_length=len(response_content),
                tool_calls_made=len([m for m in messages if hasattr(m, 'tool_calls') and m.tool_calls]),
                success=task_success,
                final_tool_success=final_tool_success
            )
            
            # Return with correct status
            result = {
                "artifacts": [{
                    "type": "text",
                    "content": response_content
                }],
                "status": status
            }
            
            # Include error information if task failed
            if not task_success:
                result["error"] = "Task execution encountered tool errors"
            
            return result
        else:
            raise ValueError("No response generated")
            
    except Exception as e:
        error_msg = str(e)
        # Check for specific error types (align with Salesforce agent)
        if "GraphRecursionError" in type(e).__name__ or "recursion limit" in error_msg.lower():
            error_msg = "Query complexity exceeded maximum iterations. Please try a more specific search."
        elif "GRAPH_RECURSION_LIMIT" in error_msg:
            error_msg = "Too many tool calls required. Please simplify your request."
            
        logger.error("a2a_task_error",
            component="servicenow",
            operation="process_task",
            task_id=task_id if 'task_id' in locals() else 'unknown',
            error=str(e),
            error_type=type(e).__name__
        )
        
        # Return error in expected format (align with Salesforce agent)
        return {
            "artifacts": [{
                "type": "text",
                "content": f"Error processing ServiceNow request: {error_msg}"
            }],
            "status": "failed",
            "error": error_msg
        }

def create_servicenow_agent_card() -> AgentCard:
    """Create the agent card for ServiceNow agent."""
    return AgentCard(
        name="servicenow-agent",
        version="1.0.0",
        description="Specialized agent for ServiceNow IT Service Management operations",
        capabilities=[
            "servicenow_operations",
            "incident_management",
            "change_management", 
            "problem_management",
            "task_management",
            "cmdb_operations",
            "user_management",
            "itsm_workflows",
            "encoded_queries"
        ],
        endpoints={
            "process_task": "/a2a",
            "agent_card": "/a2a/agent-card"
        },
        communication_modes=["sync", "streaming"],
        metadata={
            "framework": "langgraph",
            "tools_count": len(UNIFIED_SERVICENOW_TOOLS),
            "tool_names": [tool.name for tool in UNIFIED_SERVICENOW_TOOLS]
        }
    )

async def main(port: int = 8003):
    """Main entry point for ServiceNow agent."""
    agent_card = create_servicenow_agent_card()
    
    logger.info("servicenow_agent_startup",
        component="servicenow",
        operation="startup",
        port=port,
        tools_count=len(UNIFIED_SERVICENOW_TOOLS),
        capabilities=agent_card.capabilities
    )
    
    # Create A2A server
    server = A2AServer(agent_card, "0.0.0.0", port)
    
    # Register handlers
    server.register_handler("process_task", handle_a2a_request)
    
    async def get_agent_card_handler(params):
        return agent_card.to_dict()
    
    server.register_handler("get_agent_card", get_agent_card_handler)
    
    # Start the server
    runner = await server.start()
    
    try:
        # Keep the server running
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        await server.stop(runner)
        
        # Clean up the global connection pool
        from src.a2a.protocol import get_connection_pool
        pool = get_connection_pool()
        await pool.close_all()

if __name__ == "__main__":
    import asyncio
    import argparse
    
    parser = argparse.ArgumentParser(description="ServiceNow Agent")
    parser.add_argument("--port", type=int, default=8003, help="Port to run on")
    args = parser.parse_args()
    
    asyncio.run(main(port=args.port))