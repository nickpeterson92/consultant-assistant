"""Message processing utilities for agent communication."""

from .serialization import (
    deserialize_messages,
    extract_message_metadata
)
# Legacy functions - use unified_serialization.serialize_messages_for_json instead
from .serialization import serialize_messages, serialize_messages_to_dict
from .helpers import (
    trim_messages_for_context,
    estimate_message_tokens,
    extract_user_intent,
    count_tool_calls,
    extract_entities_from_messages,
    format_message_for_display,
    smart_preserve_messages
)

# DEPRECATED: Use unified_serialization.serialize_messages_for_json instead
def serialize_message(message):
    """DEPRECATED: Use unified_serialization.serialize_messages_for_json instead."""
    from .unified_serialization import serialize_messages_for_json
    return serialize_messages_for_json(message)

def serialize_recent_messages(messages, count=None, message_count=None):
    """DEPRECATED: Use unified_serialization.serialize_messages_for_json instead."""
    from .unified_serialization import serialize_messages_for_json
    limit = count or message_count or len(messages)
    return serialize_messages_for_json(messages, limit=limit)

__all__ = [
    # Serialization
    'serialize_messages',
    'serialize_messages_to_dict',
    'serialize_message',
    'serialize_recent_messages',
    'deserialize_messages', 
    'extract_message_metadata',
    
    # Helpers
    'trim_messages_for_context',
    'estimate_message_tokens',
    'extract_user_intent',
    'count_tool_calls',
    'extract_entities_from_messages',
    'format_message_for_display',
    'smart_preserve_messages'
]