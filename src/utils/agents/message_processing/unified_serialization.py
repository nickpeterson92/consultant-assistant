"""Unified message serialization - single source of truth."""

import json
from typing import List, Dict, Any, Optional, Union
from langchain_core.messages import BaseMessage
from langgraph.checkpoint.memory import MemorySaver

# Global saver instance for consistent serialization
_saver = MemorySaver()

def serialize_messages_for_json(
    messages: Union[List[BaseMessage], BaseMessage], 
    limit: Optional[int] = None
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """Single source of truth for message serialization to JSON format.
    
    This function replaces:
    - serialize_messages() 
    - serialize_messages_to_dict()
    - serialize_message()
    - serialize_recent_messages()
    
    Args:
        messages: Single message or list of LangChain message objects
        limit: Optional limit for recent messages (applied to end of list)
        
    Returns:
        JSON-serializable dict(s) using LangGraph's official serializer
    """
    # Handle single message case
    if isinstance(messages, BaseMessage):
        messages = [messages]
    
    # Apply limit if specified (take most recent)
    if limit is not None and len(messages) > limit:
        messages = messages[-limit:]
    
    # Use LangGraph's official serializer
    serialized_bytes = _saver.serde.dumps(messages)
    result = json.loads(serialized_bytes.decode('utf-8'))
    
    # Return single dict if input was single message
    if len(result) == 1 and isinstance(messages, list) and len(messages) == 1:
        return result[0]
    
    return result

def is_already_serialized(data: Any) -> bool:
    """Check if data is already serialized (dict/list of dicts) vs LangChain objects."""
    if isinstance(data, dict):
        return True
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return True
    return False