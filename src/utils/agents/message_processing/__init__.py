"""Message processing utilities for agent communication."""

from .serialization import (
    serialize_messages,
    serialize_messages_to_dict,
    deserialize_messages,
    extract_message_metadata
)
from .helpers import (
    trim_messages_for_context,
    estimate_message_tokens,
    extract_user_intent,
    count_tool_calls,
    extract_entities_from_messages,
    format_message_for_display,
    smart_preserve_messages
)

# Add helper functions
def serialize_message(message):
    """Serialize a single message to JSON-serializable format for A2A."""
    import json
    from langgraph.checkpoint.memory import MemorySaver
    _saver = MemorySaver()
    # Return JSON-serializable dict, not bytes
    serialized_bytes = _saver.serde.dumps(message)
    return json.loads(serialized_bytes.decode('utf-8'))

def serialize_recent_messages(messages, count=None, message_count=None):
    """Serialize recent messages to JSON-serializable format for A2A."""
    from .serialization import serialize_messages_to_dict
    limit = count or message_count or len(messages)
    recent = messages[-limit:] if len(messages) > limit else messages
    return serialize_messages_to_dict(recent)

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