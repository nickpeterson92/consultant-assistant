"""LangGraph compatibility layer for version 0.4.x

This module provides compatibility between LangGraph 0.2.x and 0.4.x by implementing
the missing ToolNode and tools_condition functionality.
"""

from typing import List, Dict, Any, Union, Literal
from langchain_core.tools import BaseTool
from langchain_core.messages import ToolMessage, AIMessage
from langchain_core.runnables import RunnableLambda
from langgraph.graph import END


class ToolNode:
    """Compatibility implementation of ToolNode for LangGraph 0.4.x
    
    This replicates the functionality of the original ToolNode from LangGraph 0.2.x
    which executed tool calls from the last AI message.
    """
    
    def __init__(self, tools: List[BaseTool]):
        """Initialize with a list of tools.
        
        Args:
            tools: List of LangChain tools to make available for execution
        """
        self.tools = tools
        self.tools_by_name = {tool.name: tool for tool in tools}
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tools based on the last message in state.
        
        Args:
            state: Graph state containing messages
            
        Returns:
            Updated state with tool results as ToolMessages
        """
        messages = state.get("messages", [])
        if not messages:
            return state
            
        last_message = messages[-1]
        
        # Check if the last message has tool calls
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return state
        
        # Execute each tool call
        tool_results = []
        for tool_call in last_message.tool_calls:
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("args", {})
            tool_id = tool_call.get("id")
            
            if tool_name not in self.tools_by_name:
                tool_results.append(
                    ToolMessage(
                        content=f"Error: Tool '{tool_name}' not found",
                        tool_call_id=tool_id,
                        name=tool_name
                    )
                )
                continue
            
            try:
                tool = self.tools_by_name[tool_name]
                result = tool.invoke(tool_args)
                tool_results.append(
                    ToolMessage(
                        content=str(result),
                        tool_call_id=tool_id,
                        name=tool_name
                    )
                )
            except Exception as e:
                tool_results.append(
                    ToolMessage(
                        content=f"Error executing tool: {str(e)}",
                        tool_call_id=tool_id,
                        name=tool_name
                    )
                )
        
        return {"messages": tool_results}


def tools_condition(state: Dict[str, Any]) -> Union[Literal["tools"], Literal["__end__"]]:
    """Compatibility implementation of tools_condition for LangGraph 0.4.x
    
    Routes to 'tools' node if the last message contains tool calls,
    otherwise ends the graph.
    
    Args:
        state: Graph state containing messages
        
    Returns:
        Either "tools" to execute tools or END to finish
    """
    messages = state.get("messages", [])
    if not messages:
        return END
    
    last_message = messages[-1]
    
    # Check if this is an AI message with tool calls
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    
    return END