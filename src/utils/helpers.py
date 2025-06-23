"""Helper utilities for the multi-agent orchestrator system.

This module provides common utility functions used throughout the orchestrator
and agent implementations. It includes message processing utilities, UI helpers
for enhanced user experience, and other shared functionality.

Key utilities:
- Message preservation for conversation context management
- Typing effect functions for natural conversational UI
- Response variety for better user interactions
- Token optimization helpers for cost management
"""


import sys
import asyncio

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
        def simple_token_counter(messages):
            return len(messages) * 400  # Calibrated from logs: 717 avg with ~1.5K tool overhead
        
        # CALIBRATED: Token budget based on real multi-tool conversation analysis
        # More aggressive since we're summarizing more frequently
        max_tokens = keep_count * 800  # Reduced from 1200 - tighter token budget
        
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


async def type_out(text, delay=0.02):
    """Asynchronously animate text output with typewriter effect.
    
    Creates a natural conversational feel by printing text one character
    at a time with configurable delay. Useful for AI assistant responses
    to feel more human-like and engaging.
    
    Args:
        text: String to animate
        delay: Seconds between each character (default: 0.02)
        
    Note:
        Uses sys.stdout for immediate output without buffering.
        Requires async context (await) for execution.
        
    Example:
        >>> await type_out("Hello, how can I help you today?")
        # Text appears character by character
    """
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        await asyncio.sleep(delay)


def type_out_sync(text, delay=0.02):
    """Synchronous version of type_out for non-async contexts."""
    import time
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)


def get_empty_input_response():
    """Get a varied response for empty input to maintain conversational flow."""
    import random
    responses = [
        "I'm listening! What would you like to know about your enterprise data?",
        "I'm here to help! What can I assist you with today?",
        "Please share what you'd like to explore in your enterpirse.",
        "What would you like me to help you with?",
        "I'm ready to assist! What's on your mind?",
        "Feel free to ask me anything about your enterprise data.",
        "What information can I find for you today?",
        "I'm all ears! How can I help you with your enterprise data or tasks?",
    ]
    return random.choice(responses)

