"""
Tool Execution Utilities for LangGraph Command Pattern

This module provides utilities for executing tools that return Command objects,
which is the modern LangGraph pattern for state management and tool execution.
"""

import uuid
from typing import Dict, Any, List
from langchain_core.messages import ToolMessage
from src.utils.logging import get_logger

# Initialize logger
logger = get_logger()


async def execute_command_tools(state: Dict[str, Any], tools: List[Any], component: str = "tools") -> Dict[str, Any]:
    """
    Execute tools that may return Command objects and handle state updates.
    
    Args:
        state: The current LangGraph state
        tools: List of available tools
        component: Component name for logging (e.g., "salesforce", "jira")
        
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
                # Create clean args copy for tool (no custom params)
                clean_args = {k: v for k, v in tool_args.items() if k not in ['tool_call_id']}
                
                # Log tool call - IDENTICAL format to orchestrator
                logger.info("tool_call",
                    component=component,
                    tool_name=tool_name,
                    tool_args=clean_args,
                    tool_call_id=tool_call_id
                )
                
                # Call tool with state injection and tool_call_id
                if hasattr(tool, '_arun'):
                    result = await tool._arun(**clean_args, state=state, tool_call_id=tool_call_id)
                else:
                    result = tool._run(**clean_args, state=state, tool_call_id=tool_call_id)
                
                # Debug log for workflow agent
                if tool_name == "workflow_agent":
                    logger.info("workflow_tool_execution_result",
                        component=component,
                        tool_name=tool_name,
                        result_type=type(result).__name__,
                        is_command=hasattr(result, 'update'),
                        has_messages="messages" in getattr(result, 'update', {})
                    )
                
                # Log tool success - IDENTICAL format to orchestrator pattern
                logger.info("tool_result",
                    component=component,
                    tool_name=tool_name,
                    tool_call_id=tool_call_id,
                    result_type=type(result).__name__,
                    result_preview=str(result)[:200] if result else "None"
                )
                
                # Handle Command result
                if hasattr(result, 'update') and isinstance(result.update, dict):
                    # This is a Command object
                    logger.info("tool_command_received",
                        component=component,
                        tool_name=tool_name,
                        update_keys=list(result.update.keys()),
                        has_messages="messages" in result.update,
                        has_interrupted_workflow="interrupted_workflow" in result.update
                    )
                    for key, value in result.update.items():
                        if key == "messages":
                            message_updates.extend(value)
                        else:
                            state_updates[key] = value
                            if key == "interrupted_workflow":
                                logger.info("interrupted_workflow_state_update",
                                    component=component,
                                    tool_name=tool_name,
                                    workflow_data=value
                                )
                else:
                    # Legacy string result - convert to ToolMessage
                    message_updates.append(ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call_id,
                        name=tool_name
                    ))
            except Exception as e:
                # Log tool call error
                logger.error("tool_call_error",
                    component=component,
                    tool_name=tool_name,
                    tool_call_id=tool_call_id,
                    error=str(e),
                    error_type=type(e).__name__
                )
                
                # Error handling
                message_updates.append(ToolMessage(
                    content=f"Error executing {tool_name}: {str(e)}",
                    tool_call_id=tool_call_id,
                    name=tool_name
                ))
    
    # Return state updates
    result = {"messages": message_updates}
    result.update(state_updates)
    
    # Log final state updates
    if state_updates:
        logger.info("tool_node_state_updates",
            component=component,
            update_keys=list(state_updates.keys()),
            has_memory="memory" in state_updates
        )
    
    return result


def create_tool_node(tools: List[Any], component: str = "tools"):
    """
    Create a LangGraph tool node that supports Command pattern tools.
    
    Args:
        tools: List of tools to include in the node
        component: Component name for logging (e.g., "salesforce", "jira")
        
    Returns:
        Async function that can be used as a LangGraph node
    """
    async def tool_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """Custom tool node that handles Command-returning tools."""
        return await execute_command_tools(state, tools, component)
    
    return tool_node