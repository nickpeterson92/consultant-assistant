"""Message processing utilities for agents."""

from .unified_serialization import (
    serialize_messages_for_json,
    is_already_serialized
)
from .helpers import (
    trim_messages_for_context,
    estimate_message_tokens,
    extract_user_intent,
    count_tool_calls,
    format_message_for_display,
    smart_preserve_messages
)

__all__ = [
    # Serialization
    "serialize_messages_for_json",
    "is_already_serialized",
    
    # Helpers
    "trim_messages_for_context",
    "estimate_message_tokens",
    "extract_user_intent",
    "count_tool_calls",
    "format_message_for_display",
    "smart_preserve_messages"
]