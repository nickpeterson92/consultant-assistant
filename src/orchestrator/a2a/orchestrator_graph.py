"""Orchestrator graph following Salesforce agent pattern."""

from typing import Annotated, Dict, Any, List, Literal
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import tools_condition
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from src.utils.logging.framework import SmartLogger, log_execution
import asyncio
import nest_asyncio

# Allow nested event loops for sync/async compatibility
nest_asyncio.apply()

logger = SmartLogger("orchestrator")


class OrchestratorGraphState(TypedDict):
    """State for orchestrator graph - simple like Salesforce."""
    messages: Annotated[list, add_messages]
    thread_id: str
    task_id: str
    user_id: str
    # Routing fields for plan-execute
    needs_plan_execute: bool = False
    plan_execute_task: str = ""
    plan_execute_context: str = ""
    # Interrupt handling fields
    subgraph_interrupted: bool = False
    interrupt_message: str = ""


def route_after_tools(state: OrchestratorGraphState) -> Literal["agent", "plan_execute"]:
    """Route after tools execution - check if we need plan-execute."""
    if state.get("needs_plan_execute", False):
        return "plan_execute"
    return "agent"


@log_execution("orchestrator", "orchestrator_agent", include_args=False, include_result=False)
def orchestrator_agent(state: OrchestratorGraphState, config: RunnableConfig):
    """Orchestrator agent node - follows Salesforce pattern."""
    try:
        # Get LLM with tools from globals
        llm_with_tools = globals().get("llm_with_tools")
        if not llm_with_tools:
            raise RuntimeError("LLM with tools not initialized")
        
        # Get system prompt from globals
        system_prompt = globals().get("system_prompt", "")
        
        # Format messages with system prompt
        messages = state["messages"]
        
        # If first message, prepend system prompt
        if len(messages) == 1 and messages[0].type == "human":
            from langchain_core.messages import SystemMessage
            formatted_messages = [
                SystemMessage(content=system_prompt),
                messages[0]
            ]
        else:
            formatted_messages = messages
        
        # Invoke LLM with tools
        response = llm_with_tools.invoke(formatted_messages)
        
        return {"messages": [response]}
        
    except Exception as e:
        logger.error("orchestrator_agent_error", error=str(e))
        raise


@log_execution("orchestrator", "tools_node", include_args=False, include_result=False)
async def tools_node(state: OrchestratorGraphState) -> Dict[str, Any]:
    """Execute tools - handles both regular tools and routing tool.
    
    This is similar to Salesforce's tool node but also handles
    the TaskAgentTool's routing response.
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    logger.info("tools_node_invoked",
               has_tool_calls=hasattr(last_message, "tool_calls"),
               tool_call_count=len(last_message.tool_calls) if hasattr(last_message, "tool_calls") else 0,
               last_message_type=type(last_message).__name__)
    
    # Get tools from globals
    tools = globals().get("tools", [])
    if not tools:
        raise RuntimeError("Tools not initialized")
    
    # If no tool calls, this shouldn't have been called
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        logger.warning("tools_node_called_without_tool_calls")
        return {"messages": []}
    
    # Execute tool calls
    tool_messages = []
    state_updates = {}
    
    for tool_call in last_message.tool_calls:
        # Find the tool
        tool = next((t for t in tools if t.name == tool_call["name"]), None)
        if not tool:
            logger.warning("tool_not_found", tool_name=tool_call["name"])
            continue
        
        try:
            logger.info("executing_tool",
                       tool_name=tool_call["name"],
                       tool_args=tool_call["args"])
            
            # Execute tool with state injection
            # For TaskAgentTool, we need to call _arun directly to get the dict
            if tool_call["name"] == "task_agent" and hasattr(tool, '_arun'):
                # Call _arun directly to get the routing dict
                result = await tool._arun(**tool_call["args"], state=state)
            elif hasattr(tool, 'ainvoke'):
                result = await tool.ainvoke(tool_call["args"], state=state)
            else:
                result = tool.invoke(tool_call["args"], state=state)
            
            logger.info("tool_execution_result",
                       tool_name=tool_call["name"],
                       result_type=type(result).__name__,
                       is_dict=isinstance(result, dict),
                       has_routing_keys=isinstance(result, dict) and "needs_plan_execute" in result,
                       result_preview=str(result)[:100] if not isinstance(result, dict) else None)
            
            # Check if this is the routing tool response
            if isinstance(result, dict) and "needs_plan_execute" in result:
                # Extract routing information
                state_updates["needs_plan_execute"] = result["needs_plan_execute"]
                state_updates["plan_execute_task"] = result["plan_execute_task"]
                state_updates["plan_execute_context"] = result.get("plan_execute_context", "")
                
                # Create tool message
                from langchain_core.messages import ToolMessage
                tool_messages.append(ToolMessage(
                    content=result.get("routing_message", "Routing to plan-execute workflow..."),
                    tool_call_id=tool_call["id"]
                ))
            else:
                # Regular tool response
                from langchain_core.messages import ToolMessage
                tool_messages.append(ToolMessage(
                    content=str(result),
                    tool_call_id=tool_call["id"]
                ))
                
        except Exception as e:
            from langchain_core.messages import ToolMessage
            tool_messages.append(ToolMessage(
                content=f"Error: {str(e)}",
                tool_call_id=tool_call["id"]
            ))
    
    # Return messages and state updates
    return {
        "messages": tool_messages,
        **state_updates
    }


@log_execution("orchestrator", "plan_execute_node", include_args=False, include_result=False)
async def plan_execute_node(state: OrchestratorGraphState) -> Dict[str, Any]:
    """Execute plan-execute subgraph - similar to a complex tool."""
    # Get subgraph from globals
    plan_execute_subgraph = globals().get("plan_execute_subgraph")
    if not plan_execute_subgraph:
        raise RuntimeError("Plan-execute subgraph not initialized")
    
    # Transform state for plan-execute
    plan_execute_input = {
        "input": state["plan_execute_task"],
        "plan": [],
        "past_steps": [],
        "response": "",
        "messages": state.get("messages", []),
        "thread_id": state.get("thread_id", "default-thread"),
        "task_id": state.get("task_id", "default-task"),
        "user_id": state.get("user_id", "default-user"),
    }
    
    # Add context if available
    if state.get("plan_execute_context"):
        plan_execute_input["input"] += f"\n\nContext: {state['plan_execute_context']}"
    
    logger.info("plan_execute_node_invoking",
               task=state["plan_execute_task"][:100])
    
    # Invoke subgraph with shared config
    config = {"configurable": {"thread_id": state["thread_id"]}}
    
    try:
        result = await plan_execute_subgraph.ainvoke(plan_execute_input, config)
        
        # Check if the subgraph was interrupted
        if "__interrupt__" in result:
            # The plan-execute subgraph was interrupted
            from langgraph.errors import GraphInterrupt
            
            interrupt_data = result["__interrupt__"]
            if interrupt_data and len(interrupt_data) > 0:
                logger.info("plan_execute_subgraph_interrupt_detected",
                           interrupt_count=len(interrupt_data))
                # Re-raise the interrupt to propagate to parent
                raise GraphInterrupt(interrupt_data[0])
        
        # Extract response
        response = result.get("response", "Task completed.")
        
    except Exception as e:
        # Check if this is a GraphInterrupt from the subgraph
        from langgraph.errors import GraphInterrupt
        
        if isinstance(e, GraphInterrupt):
            logger.info("plan_execute_subgraph_interrupt",
                       interrupt_type=type(e).__name__,
                       has_args=bool(e.args))
            
            # IMPORTANT: Re-raise the interrupt to propagate to parent graph
            # This allows the main orchestrator to handle it properly
            # According to Context7 docs, interrupts from subgraphs should bubble up
            raise
        else:
            # Other errors should be re-raised
            logger.error("plan_execute_subgraph_error",
                        error=str(e),
                        error_type=type(e).__name__)
            raise
    
    # Create AI message
    from langchain_core.messages import AIMessage
    ai_message = AIMessage(content=response)
    
    # Reset routing flags
    return {
        "messages": [ai_message],
        "needs_plan_execute": False,
        "plan_execute_task": "",
        "plan_execute_context": "",
        "subgraph_interrupted": False,
        "interrupt_message": ""
    }


async def build_orchestrator_graph(tools, llm, system_prompt, plan_execute_subgraph=None):
    """Build orchestrator graph following Salesforce pattern.
    
    Args:
        tools: List of tools for the orchestrator
        llm: Language model to use
        system_prompt: System prompt for the agent
        plan_execute_subgraph: Optional pre-built plan-execute subgraph (for testing)
    """
    
    # Create plan-execute subgraph without checkpointer if not provided
    if plan_execute_subgraph is None:
        from src.orchestrator.plan_and_execute import create_plan_execute_graph
        plan_execute_subgraph = await create_plan_execute_graph(use_checkpointer=False)
    
    # Store in globals for node access
    globals()["plan_execute_subgraph"] = plan_execute_subgraph
    globals()["llm_with_tools"] = llm.bind_tools(tools)
    globals()["tools"] = tools
    globals()["system_prompt"] = system_prompt
    
    # Create sync wrappers for async nodes
    def sync_tools_node(state: OrchestratorGraphState) -> Dict[str, Any]:
        """Sync wrapper for tools node."""
        return asyncio.run(tools_node(state))
    
    def sync_plan_execute_node(state: OrchestratorGraphState) -> Dict[str, Any]:
        """Sync wrapper for plan-execute node."""
        return asyncio.run(plan_execute_node(state))
    
    # Build graph following Salesforce pattern
    graph_builder = StateGraph(OrchestratorGraphState)
    
    # Add nodes - agent is sync, others need sync wrappers
    graph_builder.add_node("agent", orchestrator_agent)
    graph_builder.add_node("tools", sync_tools_node)
    graph_builder.add_node("plan_execute", sync_plan_execute_node)
    
    # Set entry point
    graph_builder.set_entry_point("agent")
    
    # Use standard tools_condition for agent routing
    graph_builder.add_conditional_edges(
        "agent",
        tools_condition,
        {
            "tools": "tools",
            "__end__": END,
        }
    )
    
    # After tools, check if we need plan-execute
    graph_builder.add_conditional_edges(
        "tools",
        route_after_tools,
        {
            "agent": "agent",
            "plan_execute": "plan_execute"
        }
    )
    
    # Plan-execute goes to END
    graph_builder.add_edge("plan_execute", END)
    
    # Compile with MemorySaver
    return graph_builder.compile(checkpointer=MemorySaver())