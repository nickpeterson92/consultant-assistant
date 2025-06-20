# helpers.property


import sys
import asyncio
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage


def smart_preserve_messages(messages: list, keep_count: int = 2):
    """Preserve complete tool call exchanges while respecting keep_count
    
    Enhanced state-aware version that prevents orphaned tool messages.
    Based on LangGraph best practices and timing issue research.
    """
    if len(messages) <= keep_count:
        return messages
    
    def extract_tool_calls(msg):
        """Extract tool calls from either tool_calls or additional_kwargs format"""
        if not hasattr(msg, '__class__') or msg.__class__.__name__ != 'AIMessage':
            return []
        
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            return msg.tool_calls
        elif hasattr(msg, 'additional_kwargs') and 'tool_calls' in msg.additional_kwargs:
            return msg.additional_kwargs.get('tool_calls', [])
        return []
    
    def has_orphaned_tool_messages(candidate_messages):
        """Check if any ToolMessage lacks its corresponding AI message with tool_calls"""
        ai_tool_call_ids = set()
        
        # Collect all tool call IDs from AI messages
        for msg in candidate_messages:
            if hasattr(msg, '__class__') and msg.__class__.__name__ == 'AIMessage':
                tool_calls = extract_tool_calls(msg)
                for tc in tool_calls:
                    if tc.get('id'):
                        ai_tool_call_ids.add(tc.get('id'))
        
        # Check if any ToolMessage references a missing tool call ID
        for msg in candidate_messages:
            if (hasattr(msg, '__class__') and 
                msg.__class__.__name__ == 'ToolMessage' and
                hasattr(msg, 'tool_call_id')):
                if msg.tool_call_id not in ai_tool_call_ids:
                    return True
                    
        return False
    
    def find_complete_tool_groups(messages):
        """Identify complete tool call groups that must be preserved together"""
        groups = []
        
        for i, msg in enumerate(messages):
            if hasattr(msg, '__class__') and msg.__class__.__name__ == 'AIMessage':
                tool_calls = extract_tool_calls(msg)
                if tool_calls:
                    # Find all corresponding tool messages
                    tool_messages = []
                    tool_call_ids = [tc.get('id') for tc in tool_calls if tc.get('id')]
                    
                    for tc_id in tool_call_ids:
                        for j in range(i + 1, len(messages)):
                            candidate = messages[j]
                            if (hasattr(candidate, '__class__') and 
                                candidate.__class__.__name__ == 'ToolMessage' and
                                getattr(candidate, 'tool_call_id', None) == tc_id):
                                tool_messages.append((j, candidate))
                                break
                    
                    # Only consider complete groups
                    if len(tool_messages) == len(tool_call_ids):
                        group_indices = [i] + [idx for idx, _ in tool_messages]
                        group_messages = [msg] + [tmsg for _, tmsg in tool_messages]
                        groups.append((min(group_indices), max(group_indices), group_messages))
        
        return groups
    
    # Strategy: Work backwards, but validate no orphaned tool messages
    preserved = []
    
    # Start with last keep_count messages
    candidate_preserved = messages[-keep_count:]
    
    # Check for orphaned tool messages
    if has_orphaned_tool_messages(candidate_preserved):
        # Find complete tool groups
        complete_groups = find_complete_tool_groups(messages)
        
        # Work backwards through complete units
        preserved = []
        remaining_space = keep_count
        
        # Add messages from the end, respecting tool group boundaries
        i = len(messages) - 1
        while i >= 0 and remaining_space > 0:
            msg = messages[i]
            
            # Check if this message is part of a tool group
            in_group = False
            for start_idx, end_idx, group_msgs in complete_groups:
                if start_idx <= i <= end_idx:
                    # Include entire group if it fits
                    if len(group_msgs) <= remaining_space:
                        preserved.extend(group_msgs)
                        remaining_space -= len(group_msgs)
                    # Skip to before this group
                    i = start_idx - 1
                    in_group = True
                    break
            
            if not in_group:
                # Regular message not in a tool group
                if remaining_space > 0:
                    preserved.append(msg)
                    remaining_space -= 1
                i -= 1
        
        # Sort by original order
        original_order = {id(msg): idx for idx, msg in enumerate(messages)}
        preserved.sort(key=lambda msg: original_order.get(id(msg), float('inf')))
        
        # Final validation
        if has_orphaned_tool_messages(preserved):
            # Fallback: include only regular messages (no tool sequences)
            preserved = []
            for msg in messages[-keep_count:]:
                if not (hasattr(msg, '__class__') and msg.__class__.__name__ == 'ToolMessage'):
                    preserved.append(msg)
            preserved = preserved[-keep_count:]  # Ensure we don't exceed limit
    else:
        # No orphaned messages, use simple preservation
        preserved = candidate_preserved
    
    return preserved


async def type_out(text, delay=0.02):
    # Animates printing of the given text one character at a time.
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        await asyncio.sleep(delay)

