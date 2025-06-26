"""Helper utilities for message processing and token management."""

def smart_preserve_messages(messages: list, keep_count: int = 2):
    """Preserve tool call/response pairs while trimming to keep_count messages.
    
    Uses LangGraph's trim_messages when available, falls back to simple slicing.
    Token budget: keep_count * 800 (based on 400 avg + tool overhead).
    
    Args:
        messages: List of LangChain message objects
        keep_count: Target number of messages to preserve (default: 2)
        
    Returns:
        List of preserved messages with tool call pairs intact
    """
    if len(messages) <= keep_count:
        return messages
    
    # Use LangGraph's official approach: trim_messages with proper constraints
    try:
        from langchain_core.messages.utils import trim_messages
        
        # CALIBRATED: Realistic token counter based on actual usage analysis
        from .config import get_conversation_config
        conv_config = get_conversation_config()
        
        def simple_token_counter(messages):
            return len(messages) * conv_config.token_per_message_estimate  # Calibrated from logs
        
        # CALIBRATED: Token budget based on real multi-tool conversation analysis
        # More aggressive since we're summarizing more frequently
        max_tokens = keep_count * conv_config.token_budget_multiplier  # Configurable token budget
        
        # Use trim_messages with tool call preservation
        preserved = trim_messages(
            messages,
            strategy="last",
            token_counter=simple_token_counter,
            max_tokens=max_tokens,
            start_on="human",
            end_on=("human", "tool"),  # Critical: allows ending on tool messages
            include_system=True
        )
        
        return preserved
        
    except ImportError:
        # Fallback to simple preservation if trim_messages not available
        return messages[-keep_count:]













