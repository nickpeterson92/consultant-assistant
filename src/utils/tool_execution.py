"""
Tool Execution Utilities for LangGraph Command Pattern

This module provides utilities for executing tools that return Command objects,
which is the modern LangGraph pattern for state management and tool execution.
"""

import uuid
from typing import Dict, Any, List
from langchain_core.messages import ToolMessage


async def execute_command_tools(state: Dict[str, Any], tools: List[Any]) -> Dict[str, Any]:
    """
    Execute tools that may return Command objects and handle state updates.
    
    Args:
        state: The current LangGraph state
        tools: List of available tools
        
    Returns:
        Dictionary of state updates to apply
    """
    messages = state.get("messages", [])
    if not messages:
        return {"messages": []}
    
    last_message = messages[-1]
    
    # Extract tool calls from the last message
    tool_calls = getattr(last_message, 'tool_calls', [])
    if not tool_calls:
        return {"messages": []}
    
    # Execute tools and collect updates
    state_updates = {}
    message_updates = []
    
    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_call_id = tool_call.get("id", str(uuid.uuid4()))
        
        # Find the tool by name
        tool = None
        for t in tools:
            if t.name == tool_name:
                tool = t
                break
        
        if tool:
            try:
                # Call tool with state injection and tool_call_id
                tool_args["tool_call_id"] = tool_call_id
                if hasattr(tool, '_arun'):
                    result = await tool._arun(**tool_args, state=state)
                else:
                    result = tool._run(**tool_args, state=state)
                
                # Handle Command result
                if hasattr(result, 'update') and isinstance(result.update, dict):
                    # This is a Command object
                    for key, value in result.update.items():
                        if key == "messages":
                            message_updates.extend(value)
                        else:
                            state_updates[key] = value
                else:
                    # Legacy string result - convert to ToolMessage
                    message_updates.append(ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call_id,
                        name=tool_name
                    ))
            except Exception as e:
                # Error handling
                message_updates.append(ToolMessage(
                    content=f"Error executing {tool_name}: {str(e)}",
                    tool_call_id=tool_call_id,
                    name=tool_name
                ))
    
    # Return state updates
    result = {"messages": message_updates}
    result.update(state_updates)
    return result


def create_tool_node(tools: List[Any]):
    """
    Create a LangGraph tool node that supports Command pattern tools.
    
    Args:
        tools: List of tools to include in the node
        
    Returns:
        Async function that can be used as a LangGraph node
    """
    async def tool_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """Custom tool node that handles Command-returning tools."""
        return await execute_command_tools(state, tools)
    
    return tool_node