"""Custom ReAct agent implementation for plan-execute subgraph.

This implementation is designed to work without a checkpointer and properly
propagate interrupts to the parent graph.
"""

from typing import Dict, List, Any, Literal, Union, Annotated
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.errors import GraphInterrupt
from src.utils.logging.framework import SmartLogger

logger = SmartLogger("orchestrator")


class ReactAgentState(TypedDict):
    """State for custom ReAct agent."""
    messages: Annotated[List[BaseMessage], add_messages]
    # Pass through fields from plan-execute
    thread_id: str
    user_id: str
    task_id: str
    memory_context: str
    schema_context: str
    past_steps: List[Dict[str, Any]]


def create_custom_react_agent(llm, tools: List[BaseTool], prompt: str = None):
    """Create a custom ReAct agent that works without checkpointer.
    
    This agent is designed to be used as a subgraph within plan-execute
    and properly propagates interrupts to the parent.
    
    Args:
        llm: Language model with tools bound
        tools: List of tools available to the agent
        prompt: Optional system prompt
        
    Returns:
        Compiled graph without checkpointer
    """
    
    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(tools)
    
    # Create custom tool execution function that handles interrupts
    def execute_tools(state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tools and handle interrupts properly.
        
        If a tool raises GraphInterrupt (like HumanInputTool),
        we let it propagate to the parent graph.
        """
        messages = state["messages"]
        last_message = messages[-1]
            
        # If no tool calls, nothing to do
        if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
            return {"messages": []}
            
        # Execute each tool call
        tool_messages = []
        
        for tool_call in last_message.tool_calls:
            # Find the tool
            tool = next((t for t in tools if t.name == tool_call["name"]), None)
            if not tool:
                tool_messages.append(ToolMessage(
                    content=f"Tool {tool_call['name']} not found",
                    tool_call_id=tool_call["id"]
                ))
                continue
                
            try:
                logger.info("executing_tool_in_custom_react",
                           tool_name=tool_call["name"],
                           has_state=True)
                
                # Execute tool - pass full state for InjectedState
                # The tool expects state to be part of the args, not a separate parameter
                tool_args = {**tool_call["args"], "state": state}
                result = tool.invoke(tool_args)
                    
                # Add tool message
                tool_messages.append(ToolMessage(
                    content=str(result),
                    tool_call_id=tool_call["id"]
                ))
                
            except GraphInterrupt as e:
                # This is expected - HumanInputTool raises this
                # We need to propagate it to the parent
                logger.info("custom_tool_execution_interrupt_caught",
                           tool_name=tool_call["name"],
                           interrupt_value=str(e.args[0])[:100] if e.args else "",
                           will_propagate=True)
                
                # IMPORTANT: Re-raise the interrupt to propagate to parent
                # Do NOT return a message, just let the exception bubble up
                raise
                    
            except Exception as e:
                # Other errors get converted to tool messages
                logger.error("custom_tool_execution_error",
                            tool_name=tool_call["name"],
                            error=str(e))
                
                tool_messages.append(ToolMessage(
                    content=f"Error: {str(e)}",
                    tool_call_id=tool_call["id"]
                ))
        
        return {"messages": tool_messages}
    
    # Create the agent node
    def agent_node(state: ReactAgentState) -> Dict[str, Any]:
        """Agent node that calls LLM with tools."""
        messages = state["messages"]
        
        # Add system prompt if provided and this is the first call
        if prompt and len(messages) == 1:
            from langchain_core.messages import SystemMessage
            messages = [SystemMessage(content=prompt)] + messages
        
        logger.debug("custom_react_agent_calling_llm",
                    message_count=len(messages),
                    has_system_prompt=prompt is not None)
        
        # Call LLM
        response = llm_with_tools.invoke(messages)
        
        # Log if the LLM decided to use tools
        has_tool_calls = hasattr(response, "tool_calls") and response.tool_calls
        logger.debug("custom_react_agent_llm_response",
                    has_tool_calls=has_tool_calls,
                    tool_count=len(response.tool_calls) if has_tool_calls else 0,
                    tool_names=[tc["name"] for tc in response.tool_calls] if has_tool_calls else [])
        
        return {"messages": [response]}
    
    
    # Build the graph
    graph_builder = StateGraph(ReactAgentState)
    
    # Add nodes
    graph_builder.add_node("agent", agent_node)
    graph_builder.add_node("tools", execute_tools)
    
    # Set entry point
    graph_builder.set_entry_point("agent")
    
    # Add conditional edge from agent
    # Note: tools_condition returns "tools" or "__end__"
    graph_builder.add_conditional_edges(
        "agent",
        tools_condition,
        {
            "tools": "tools",
            "__end__": END,
        }
    )
    
    # Tools always go back to agent
    graph_builder.add_edge("tools", "agent")
    
    # Compile WITHOUT checkpointer - this is key!
    # The parent graph has the checkpointer
    return graph_builder.compile()