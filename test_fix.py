#!/usr/bin/env python3
"""
Test script to validate the infinite loop fixes
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'agent'))

from utils.helpers import smart_truncate_messages, unify_messages_to_dicts, convert_dicts_to_lc_messages
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage

def test_message_conversion():
    """Test that message conversion preserves tool call information"""
    print("Testing message conversion...")
    
    # Create test messages with tool calls
    ai_msg_with_tool_call = AIMessage(
        content="",
        tool_calls=[{
            "name": "salesforce_agent",
            "args": {"instruction": "Retrieve the Lundgren account details"},
            "id": "call_123",
            "type": "tool_call"
        }]
    )
    
    tool_response = ToolMessage(
        content="I have retrieved the account details: Lundgren Karate Academy",
        tool_call_id="call_123"
    )
    
    messages = [
        SystemMessage(content="You are an assistant"),
        HumanMessage(content="Get Lundgren account"),
        ai_msg_with_tool_call,
        tool_response,
        AIMessage(content="Here are the account details...")
    ]
    
    # Test conversion
    print(f"Original messages: {len(messages)}")
    
    # Convert to dicts
    dict_messages = unify_messages_to_dicts(messages)
    print(f"Dict messages: {len(dict_messages)}")
    
    # Check that tool calls are preserved
    for i, msg in enumerate(dict_messages):
        print(f"Message {i}: role={msg.get('role')}, has_tool_calls={'tool_calls' in msg}")
    
    # Convert back to LangChain
    lc_messages = convert_dicts_to_lc_messages(dict_messages)
    print(f"Converted back: {len(lc_messages)}")
    
    # Check preservation
    for i, msg in enumerate(lc_messages):
        msg_type = type(msg).__name__
        has_tool_calls = hasattr(msg, 'tool_calls') and msg.tool_calls
        print(f"Message {i}: {msg_type}, has_tool_calls={has_tool_calls}")

def test_smart_truncation():
    """Test smart truncation preserves system messages and tool chains"""
    print("\nTesting smart truncation...")
    
    messages = [
        SystemMessage(content="You are an assistant"),
        HumanMessage(content="Hello"),
        AIMessage(content="Hi there"),
        HumanMessage(content="Get account"),
        AIMessage(content="", tool_calls=[{"name": "get_account", "args": {}, "id": "call_1", "type": "tool_call"}]),
        ToolMessage(content="Account found", tool_call_id="call_1"),
        AIMessage(content="Here's the account"),
        HumanMessage(content="Thanks"),
        AIMessage(content="You're welcome"),
        HumanMessage(content="Get another account"),
        AIMessage(content="", tool_calls=[{"name": "get_account", "args": {}, "id": "call_2", "type": "tool_call"}]),
        ToolMessage(content="Second account found", tool_call_id="call_2"),
        AIMessage(content="Here's the second account"),
    ]
    
    print(f"Original messages: {len(messages)}")
    
    # Test truncation with limit of 8
    truncated = smart_truncate_messages(messages, max_messages=8)
    print(f"Truncated messages: {len(truncated)}")
    
    # Should preserve system message
    if isinstance(truncated[0], SystemMessage):
        print("✓ System message preserved")
    else:
        print("✗ System message lost")
    
    # Check for broken tool chains
    tool_chain_intact = True
    for i, msg in enumerate(truncated):
        if isinstance(msg, ToolMessage):
            # Check if previous message has matching tool call
            if i > 0:
                prev_msg = truncated[i-1]
                if hasattr(prev_msg, 'tool_calls') and prev_msg.tool_calls:
                    tool_call_id = getattr(msg, 'tool_call_id', None)
                    matching = any(tc.get('id') == tool_call_id for tc in prev_msg.tool_calls)
                    if not matching:
                        tool_chain_intact = False
                        print(f"✗ Broken tool chain at message {i}")
                        break
    
    if tool_chain_intact:
        print("✓ Tool chains preserved")

if __name__ == "__main__":
    test_message_conversion()
    test_smart_truncation()
    print("\nTests completed!")