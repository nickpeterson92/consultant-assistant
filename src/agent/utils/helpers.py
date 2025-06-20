# helpers.property


import sys
import asyncio
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage


def clean_orphaned_tool_calls(messages: list) -> list:
    """Remove orphaned AI messages with tool calls and orphaned tool messages"""
    if not messages:
        return messages
    
    cleaned = []
    
    for i, msg in enumerate(messages):
        # Check if this is an AI message with tool calls
        if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
            tool_call_ids = [tc.get("id") for tc in msg.tool_calls if tc.get("id")]
            
            if tool_call_ids:
                # Check if all tool calls have responses in the remaining messages
                all_have_responses = True
                
                for tool_call_id in tool_call_ids:
                    has_response = False
                    # Look ahead in remaining messages
                    for j in range(i + 1, len(messages)):
                        next_msg = messages[j]
                        if (isinstance(next_msg, ToolMessage) and 
                            getattr(next_msg, 'tool_call_id', None) == tool_call_id):
                            has_response = True
                            break
                        # Stop looking if we hit another AI message
                        if isinstance(next_msg, AIMessage):
                            break
                    
                    if not has_response:
                        all_have_responses = False
                        break
                
                if all_have_responses:
                    # All tool calls have responses, keep the message
                    cleaned.append(msg)
                else:
                    # Some tool calls are orphaned, convert to regular AI message
                    content = msg.content if msg.content else "I'll help you with that request."
                    cleaned.append(AIMessage(content=content))
            else:
                # No valid tool call IDs, treat as regular message
                cleaned.append(msg)
        
        # Check if this is a ToolMessage
        elif isinstance(msg, ToolMessage):
            tool_call_id = getattr(msg, 'tool_call_id', None)
            if tool_call_id:
                # Look backward to find a preceding AI message with this tool call
                has_preceding_call = False
                for j in range(i - 1, -1, -1):
                    prev_msg = messages[j]
                    if isinstance(prev_msg, AIMessage) and hasattr(prev_msg, 'tool_calls') and prev_msg.tool_calls:
                        for tc in prev_msg.tool_calls:
                            if tc.get("id") == tool_call_id:
                                has_preceding_call = True
                                break
                        if has_preceding_call:
                            break
                    # Stop looking if we hit another ToolMessage
                    elif isinstance(prev_msg, ToolMessage):
                        break
                
                if has_preceding_call:
                    # ToolMessage has a valid preceding call, keep it
                    cleaned.append(msg)
                # If no preceding call, skip this ToolMessage (it's orphaned)
            else:
                # ToolMessage without tool_call_id, skip it
                pass
        
        else:
            # Other message types, keep as is
            cleaned.append(msg)
    
    return cleaned


async def type_out(text, delay=0.02):
    # Animates printing of the given text one character at a time.
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        await asyncio.sleep(delay)

