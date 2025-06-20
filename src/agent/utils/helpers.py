# helpers.property


import sys
import asyncio
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage


def clean_orphaned_tool_calls(messages: list) -> list:
    """
    Extremely robust message cleanup that ensures OpenAI API compatibility.
    
    Handles all edge cases:
    - Multi-tool calls with partial responses
    - Out-of-order tool responses  
    - Missing tool responses
    - Duplicate tool calls
    - Mixed conversation flows
    
    Strategy: Use a straightforward sequential approach that ensures every 
    AI message with tool calls is immediately followed by ALL its tool responses.
    """
    if not messages:
        return messages

    def extract_tool_calls(msg):
        """Extract tool calls from either tool_calls or additional_kwargs format"""
        if not isinstance(msg, AIMessage):
            return []
        
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            return msg.tool_calls
        elif hasattr(msg, 'additional_kwargs') and 'tool_calls' in msg.additional_kwargs:
            return msg.additional_kwargs.get('tool_calls', [])
        return []

    def get_tool_call_ids(tool_calls):
        """Get all tool call IDs from a list of tool calls"""
        return [tc.get("id") for tc in tool_calls if tc.get("id")]

    # Build a map of all tool call IDs to their responses
    tool_response_map = {}
    for msg in messages:
        if isinstance(msg, ToolMessage):
            tool_call_id = getattr(msg, 'tool_call_id', None)
            if tool_call_id:
                tool_response_map[tool_call_id] = msg

    cleaned = []
    i = 0
    
    while i < len(messages):
        msg = messages[i]
        
        if isinstance(msg, AIMessage):
            tool_calls = extract_tool_calls(msg)
            
            if tool_calls:
                # AI message with tool calls - check which ones have responses
                tool_call_ids = get_tool_call_ids(tool_calls)
                valid_tool_calls = []
                corresponding_responses = []
                
                # Find which tool calls have responses available
                for tool_call in tool_calls:
                    tool_call_id = tool_call.get("id")
                    if tool_call_id and tool_call_id in tool_response_map:
                        valid_tool_calls.append(tool_call)
                        corresponding_responses.append(tool_response_map[tool_call_id])
                
                if valid_tool_calls:
                    # Create AI message with only the valid tool calls
                    if len(valid_tool_calls) == len(tool_calls):
                        # All tool calls are valid, use original message
                        cleaned.append(msg)
                    else:
                        # Some tool calls are valid, create new message with only valid ones
                        if hasattr(msg, 'tool_calls'):
                            # Use tool_calls attribute
                            new_msg = AIMessage(content=msg.content or "", tool_calls=valid_tool_calls)
                        else:
                            # Use additional_kwargs format
                            new_msg = AIMessage(
                                content=msg.content or "",
                                additional_kwargs={"tool_calls": valid_tool_calls}
                            )
                        
                        # Copy other attributes
                        for attr in ['response_metadata', 'id']:
                            if hasattr(msg, attr):
                                setattr(new_msg, attr, getattr(msg, attr))
                        
                        cleaned.append(new_msg)
                    
                    # Add all corresponding tool responses immediately after
                    for response in corresponding_responses:
                        cleaned.append(response)
                else:
                    # No valid tool calls, convert to regular AI message
                    content = msg.content or "I'll help you with that request."
                    cleaned.append(AIMessage(content=content))
            else:
                # Regular AI message without tool calls
                cleaned.append(msg)
        
        elif isinstance(msg, ToolMessage):
            # Tool messages are handled when processing AI messages with tool calls
            # Skip standalone tool messages as they would be orphaned
            pass
        
        else:
            # Other message types (System, Human, etc.)
            cleaned.append(msg)
        
        i += 1

    # Final validation: ensure no AI message with tool calls lacks responses
    final_cleaned = []
    
    for i, msg in enumerate(cleaned):
        if isinstance(msg, AIMessage):
            tool_calls = extract_tool_calls(msg)
            
            if tool_calls:
                tool_call_ids = get_tool_call_ids(tool_calls)
                
                # Look for tool responses immediately following this message
                found_responses = []
                j = i + 1
                while j < len(cleaned) and isinstance(cleaned[j], ToolMessage):
                    tool_msg = cleaned[j]
                    if getattr(tool_msg, 'tool_call_id', None) in tool_call_ids:
                        found_responses.append(tool_msg)
                    j += 1
                
                found_ids = {getattr(resp, 'tool_call_id', None) for resp in found_responses}
                missing_ids = set(tool_call_ids) - found_ids
                
                if missing_ids:
                    # Missing responses, convert to regular AI message
                    content = msg.content or "I'll help you with that request."
                    final_cleaned.append(AIMessage(content=content))
                else:
                    # All responses found, keep as-is
                    final_cleaned.append(msg)
            else:
                # Regular AI message
                final_cleaned.append(msg)
        else:
            final_cleaned.append(msg)
    
    return final_cleaned


async def type_out(text, delay=0.02):
    # Animates printing of the given text one character at a time.
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        await asyncio.sleep(delay)

