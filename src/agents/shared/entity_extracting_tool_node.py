"""Shared custom tool node that preserves raw results for entity extraction."""

from typing import Dict, Any, List
from langchain_core.messages import ToolMessage
import json
import asyncio

from src.agents.shared.memory_writer import write_tool_result_to_memory
from src.utils.thread_utils import create_thread_id
from src.utils.logging.framework import SmartLogger

logger = SmartLogger("entity_extraction")


async def create_entity_extracting_tool_node(tools: List[Any], agent_name: str):
    """
    Create a custom tool node that executes tools and preserves raw results for entity extraction.
    
    This async function returns an async function that can be used as a LangGraph node.
    
    Args:
        tools: List of available tools
        agent_name: Name of the agent (e.g., "salesforce", "jira", "servicenow")
        
    Returns:
        An async function that can be used as a tool node in LangGraph
    """
    
    async def custom_tool_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tools and preserve raw results for entity extraction."""
        
        logger.info(f"{agent_name}_custom_tool_node_called", 
                   state_keys=list(state.keys()),
                   message_count=len(state.get("messages", [])))
        
        # Get the last message which should contain tool calls
        messages = state.get("messages", [])
        if not messages:
            logger.warning(f"{agent_name}_custom_tool_node_no_messages")
            return {"messages": []}
        
        last_message = messages[-1]
        if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
            logger.warning(f"{agent_name}_custom_tool_node_no_tool_calls",
                          message_type=type(last_message).__name__)
            return {"messages": []}
        
        # Extract context for memory storage
        task_context = state.get("task_context", {})
        external_context = state.get("external_context", {})
        task_id = task_context.get("task_id", "unknown")
        user_id = external_context.get("user_id")
        
        # Create tools_by_name mapping
        tools_by_name = {tool.name: tool for tool in tools}
        
        outputs = []
        for tool_call in last_message.tool_calls:
            try:
                # Execute the tool
                tool = tools_by_name[tool_call["name"]]
                tool_result = tool.invoke(tool_call["args"])
                
                # Write raw result to memory BEFORE formatting
                logger.info(f"{agent_name}_tool_result_debug",
                           user_id=user_id,
                           tool_result_type=type(tool_result).__name__,
                           is_dict=isinstance(tool_result, dict),
                           has_success=tool_result.get('success') if isinstance(tool_result, dict) else False)
                
                if isinstance(tool_result, dict) and tool_result.get('success'):
                    try:
                        # Since we're in an async context, we can await directly
                        # Domain entities will be stored globally regardless of user_id
                        await write_tool_result_to_memory(
                            thread_id=create_thread_id(agent_name, task_id),
                            tool_name=tool_call["name"],
                            tool_args=tool_call["args"],
                            tool_result=tool_result,  # Pass the raw structured result
                            task_id=task_id,
                            agent_name=agent_name,
                            user_id=user_id  # Can be None, entities will still be stored globally
                        )
                        
                        logger.info(f"{agent_name}_tool_result_written_to_memory",
                                   tool_name=tool_call["name"],
                                   has_data=bool(tool_result.get('data')),
                                   user_id=user_id,
                                   storing_entities_globally=True)
                    except Exception as e:
                        logger.warning(f"{agent_name}_failed_to_write_raw_tool_result",
                                     tool_name=tool_call["name"],
                                     error=str(e))
                
                # Create ToolMessage with JSON-serialized result
                outputs.append(
                    ToolMessage(
                        content=json.dumps(tool_result),
                        name=tool_call["name"],
                        tool_call_id=tool_call["id"],
                    )
                )
            except Exception as e:
                # Handle tool execution errors
                outputs.append(
                    ToolMessage(
                        content=f"Error executing tool: {str(e)}",
                        name=tool_call["name"],
                        tool_call_id=tool_call["id"],
                        status="error"
                    )
                )
                logger.error(f"{agent_name}_tool_execution_error",
                           tool_name=tool_call["name"],
                           error=str(e))
        
        return {"messages": outputs}
    
    return custom_tool_node