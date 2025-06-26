"""Helper utilities for the multi-agent orchestrator system.

This module provides common utility functions used throughout the orchestrator
and agent implementations. It includes message processing utilities and other
shared functionality.

Key utilities:
- Message preservation for conversation context management
- Token optimization helpers for cost management

Note: UI/UX functions have been moved to the ux module.
"""

def smart_preserve_messages(messages: list, keep_count: int = 2):
    """Preserve complete tool call exchanges while respecting message count limits.
    
    Intelligently trims conversation history to maintain context while staying
    within token limits. Uses LangGraph's trim_messages utility to ensure
    tool call/response pairs remain intact.
    
    Args:
        messages: List of conversation messages (HumanMessage, AIMessage, etc.)
        keep_count: Target number of messages to preserve (default: 2)
        
    Returns:
        List of preserved messages maintaining tool call integrity.
        
    Implementation Notes:
        - Uses calibrated token estimates based on production usage analysis
        - Preserves tool calls and their responses as atomic units
        - Prioritizes recent messages while maintaining conversation flow
        - Falls back to simple slicing if trim_messages unavailable
        
    Token Calibration:
        - Average message: ~400 tokens (calibrated from logs showing 717 avg)
        - Tool overhead: ~1.5K tokens for multi-tool responses
        - Budget calculation: keep_count * 800 tokens (reduced from 1200)
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













