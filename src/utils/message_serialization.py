"""JSON serialization for LangChain messages."""

from typing import List, Dict, Any, Union
import logging

from .logging import get_logger

logger = get_logger()


def serialize_message(message) -> Dict[str, Any]:
    """Serialize a LangChain message to JSON-compatible dict.
    
    Uses .model_dump() with fallbacks for older versions.
    
    Args:
        message: LangChain message object or dict
        
    Returns:
        JSON-serializable dictionary
    """
    try:
        if hasattr(message, 'model_dump'):
            # Modern LangChain/Pydantic serialization
            result = message.model_dump()
        elif hasattr(message, 'dict'):
            # Fallback for older versions (deprecated but supported)
            result = message.dict()
        elif isinstance(message, dict):
            # Already serialized
            result = message
        else:
            # Manual fallback for unknown types
            result = {
                "type": type(message).__name__,
                "content": str(getattr(message, 'content', str(message)))
            }
        
        # Basic validation - ensure required fields exist
        if not isinstance(result, dict):
            raise ValueError(f"Serialization produced non-dict: {type(result)}")
        
        # Ensure we have at minimum the required fields
        if "type" not in result and "content" not in result:
            logger.warning("serialized_message_incomplete",
                component="utils",
                operation="serialize_message",
                result=result
            )
            # Add missing fields with safe defaults
            result.setdefault("type", type(message).__name__)
            result.setdefault("content", str(getattr(message, 'content', str(message))))
        
        return result
        
    except Exception as e:
        logger.error("message_serialization_failed",
            component="utils",
            operation="serialize_message",
            message_type=type(message).__name__,
            error=str(e),
            error_type=type(e).__name__
        )
        # Return safe fallback
        return {
            "type": "serialization_error",
            "content": f"Failed to serialize message: {str(e)}",
            "original_type": type(message).__name__
        }


def serialize_messages(messages: List) -> List[Dict[str, Any]]:
    """
    Serialize a list of LangChain messages to JSON-compatible format.
    
    Args:
        messages: List of LangChain message objects
        
    Returns:
        List of JSON-serializable dictionaries
    """
    return [serialize_message(msg) for msg in messages]


def serialize_recent_messages(messages: List, count: int = 5) -> List[Dict[str, Any]]:
    """
    Serialize the most recent N messages for context passing.
    
    Args:
        messages: List of LangChain message objects
        count: Number of recent messages to include
        
    Returns:
        List of JSON-serializable dictionaries for recent messages
    """
    if not messages:
        return []
    
    recent = messages[-count:] if len(messages) > count else messages
    return serialize_messages(recent)