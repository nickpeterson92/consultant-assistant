"""
LLM Cache Fix - Proper serialization for AIMessage objects
"""

from typing import Any, Dict
import json
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

def serialize_message(msg: Any) -> Dict[str, Any]:
    """Serialize LangChain message objects to JSON-compatible format"""
    if isinstance(msg, AIMessage):
        data = {
            "type": "ai",
            "content": msg.content,
            "additional_kwargs": msg.additional_kwargs
        }
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            data["tool_calls"] = msg.tool_calls
        return data
    elif isinstance(msg, HumanMessage):
        return {
            "type": "human",
            "content": msg.content
        }
    elif isinstance(msg, SystemMessage):
        return {
            "type": "system",
            "content": msg.content
        }
    elif isinstance(msg, ToolMessage):
        return {
            "type": "tool",
            "content": msg.content,
            "tool_call_id": msg.tool_call_id,
            "name": getattr(msg, 'name', None)
        }
    else:
        # Fallback for unknown message types
        return {
            "type": str(type(msg).__name__),
            "content": str(msg)
        }

def deserialize_message(data: Dict[str, Any]) -> Any:
    """Deserialize JSON data back to LangChain message objects"""
    msg_type = data.get("type", "unknown")
    
    if msg_type == "ai":
        msg = AIMessage(content=data.get("content", ""))
        if "additional_kwargs" in data:
            msg.additional_kwargs = data["additional_kwargs"]
        if "tool_calls" in data:
            msg.tool_calls = data["tool_calls"]
        return msg
    elif msg_type == "human":
        return HumanMessage(content=data.get("content", ""))
    elif msg_type == "system":
        return SystemMessage(content=data.get("content", ""))
    elif msg_type == "tool":
        return ToolMessage(
            content=data.get("content", ""),
            tool_call_id=data.get("tool_call_id", ""),
            name=data.get("name", "")
        )
    else:
        # Return as AIMessage by default
        return AIMessage(content=data.get("content", ""))

class EnhancedJSONEncoder(json.JSONEncoder):
    """Enhanced JSON encoder that handles LangChain message objects"""
    def default(self, obj):
        if hasattr(obj, '__class__') and 'Message' in obj.__class__.__name__:
            return serialize_message(obj)
        return super().default(obj)