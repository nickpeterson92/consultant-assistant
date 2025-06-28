"""Message serialization using LangGraph's built-in serializer.

This module uses LangGraph's JsonPlusSerializer which properly handles:
- All LangChain message types
- Tool calls with proper type preservation
- Response metadata
- Message IDs and names
- Any custom attributes
"""

import json
from typing import Dict, Any, List, Union
from langchain_core.messages import BaseMessage, AIMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver

# Global saver instance for consistent serialization
_saver = MemorySaver()


def serialize_messages(messages: List[BaseMessage]) -> bytes:
    """Serialize LangChain messages using LangGraph's serializer.
    
    Args:
        messages: List of LangChain message objects
        
    Returns:
        Serialized bytes that can be stored and later deserialized
    """
    return _saver.serde.dumps(messages)


def serialize_messages_to_dict(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
    """Serialize messages to JSON-serializable dict format.
    
    Used for A2A protocol and other contexts that need JSON.
    
    Args:
        messages: List of LangChain message objects
        
    Returns:
        List of JSON-serializable dictionaries
    """
    # LangGraph's serializer produces JSON bytes, so we can decode and parse
    serialized_bytes = _saver.serde.dumps(messages)
    return json.loads(serialized_bytes.decode('utf-8'))


def deserialize_messages(data: Union[bytes, List[Dict]]) -> List[BaseMessage]:
    """Deserialize messages from bytes or dict format.
    
    Args:
        data: Either bytes from LangGraph serialization or dict from JSON
        
    Returns:
        List of LangChain message objects with ALL fields preserved
    """
    if isinstance(data, bytes):
        return _saver.serde.loads(data)
    else:
        # If it's already a dict/list, convert to bytes first
        json_str = json.dumps(data)
        return _saver.serde.loads(json_str.encode('utf-8'))


def extract_message_metadata(message: BaseMessage) -> Dict[str, Any]:
    """Extract metadata from a message for logging or analysis.
    
    Args:
        message: LangChain message object
        
    Returns:
        Dictionary of extracted metadata
    """
    metadata = {
        "type": message.__class__.__name__,
        "content_length": len(str(message.content)),
        "has_additional_kwargs": bool(message.additional_kwargs)
    }
    
    # Add response metadata if present
    if hasattr(message, 'response_metadata'):
        metadata["has_response_metadata"] = bool(message.response_metadata)
        if message.response_metadata:
            metadata["model"] = message.response_metadata.get("model", "unknown")
    
    if isinstance(message, AIMessage):
        metadata["has_tool_calls"] = bool(getattr(message, 'tool_calls', None))
        if hasattr(message, 'tool_calls') and message.tool_calls:
            metadata["tool_call_count"] = len(message.tool_calls)
            metadata["tool_names"] = [tc.get('name', 'unknown') for tc in message.tool_calls]
    
    elif isinstance(message, ToolMessage):
        metadata["tool_call_id"] = message.tool_call_id
        metadata["tool_name"] = getattr(message, 'name', None)
    
    # Extract message ID if present
    if hasattr(message, 'id'):
        metadata["message_id"] = message.id
    
    return metadata