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


async def type_out(text, delay=None):
    """Stream text output using semantic chunking for optimal UX.
    
    Implements research-backed progressive disclosure and perception of progress
    patterns. Instead of character-by-character typing, uses semantic chunks
    (sentences, phrases) to maintain readability while creating streaming effect.
    
    Key features:
    - First sentence types normally to establish rhythm
    - Subsequent content streams in semantic chunks
    - Tables/structure appear instantly
    - Natural pauses at paragraph boundaries
    - Fully configurable via system_config.json
    
    Args:
        text: String to animate
        delay: Override for character delay (uses config if None)
        
    Example:
        >>> await type_out("Hello! I found 5 accounts. Here are the details...")
        # First sentence types normally, rest streams smoothly
    """
    import re
    from .config import get_conversation_config
    
    config = get_conversation_config()
    
    # Check if typing effect is enabled
    if not config.typing_effect_enabled:
        print(text, flush=True)
        return
    
    # Use config values or override
    char_delay = delay or config.typing_char_delay
    chunk_delay = config.typing_chunk_delay
    line_delay = config.typing_line_delay
    paragraph_delay = config.typing_paragraph_delay
    first_line_limit = config.typing_first_line_char_limit
    instant_elements = config.typing_instant_elements
    
    lines = text.split('\n')
    first_chunk = True
    
    for i, line in enumerate(lines):
        # Instant display for structured elements (tables, ASCII art, etc.)
        if instant_elements and (
            line.strip().startswith(('━', '│', '└', '├', '─', '█', '╔', '╗', '╚', '╝')) or
            line.strip().startswith('|') or  # Table markers
            (i > 0 and '|' in line and line.count('|') > 2)):  # Table rows
            print(line, flush=True)
            await asyncio.sleep(chunk_delay * 0.5)  # Brief pause for readability
            continue
            
        # Handle empty lines
        if not line.strip():
            print()
            await asyncio.sleep(paragraph_delay)  # Natural paragraph pause
            continue
            
        # Semantic chunking for regular text
        if first_chunk and len(line) < first_line_limit:
            # First short line gets character-by-character for engagement
            for char in line:
                sys.stdout.write(char)
                sys.stdout.flush()
                await asyncio.sleep(char_delay)
            print()
            first_chunk = False
        else:
            # Split into semantic chunks (sentences or phrases)
            # This regex splits on sentence endings but keeps the punctuation
            chunks = re.split(r'([.!?]+\s*)', line)
            chunks = [chunks[i] + (chunks[i+1] if i+1 < len(chunks) else '') 
                     for i in range(0, len(chunks), 2) if chunks[i]]
            
            for j, chunk in enumerate(chunks):
                if chunk.strip():
                    # Stream each chunk
                    print(chunk, end='', flush=True)
                    # Pause between chunks for natural reading rhythm
                    if j < len(chunks) - 1:
                        await asyncio.sleep(chunk_delay)
            
            print()  # New line after the line is complete
            
        # Pause between lines for readability
        if i < len(lines) - 1:
            await asyncio.sleep(line_delay)


def type_out_sync(text, delay=None):
    """Synchronous streaming with semantic chunking for non-async contexts.
    
    Mirrors the async version's intelligent streaming approach using
    semantic chunks for optimal readability and engagement.
    Fully configurable via system_config.json.
    
    Args:
        text: String to animate
        delay: Override for character delay (uses config if None)
    """
    import time
    import re
    from .config import get_conversation_config
    
    config = get_conversation_config()
    
    # Check if typing effect is enabled
    if not config.typing_effect_enabled:
        print(text, flush=True)
        return
    
    # Use config values or override
    char_delay = delay or config.typing_char_delay
    chunk_delay = config.typing_chunk_delay
    line_delay = config.typing_line_delay
    paragraph_delay = config.typing_paragraph_delay
    first_line_limit = config.typing_first_line_char_limit
    instant_elements = config.typing_instant_elements
    
    lines = text.split('\n')
    first_chunk = True
    
    for i, line in enumerate(lines):
        # Instant display for structured elements
        if instant_elements and (
            line.strip().startswith(('━', '│', '└', '├', '─', '█', '╔', '╗', '╚', '╝')) or
            line.strip().startswith('|') or
            (i > 0 and '|' in line and line.count('|') > 2)):
            print(line, flush=True)
            time.sleep(chunk_delay * 0.5)
            continue
            
        # Handle empty lines
        if not line.strip():
            print()
            time.sleep(paragraph_delay)
            continue
            
        # Semantic chunking
        if first_chunk and len(line) < first_line_limit:
            # First short line gets character effect
            for char in line:
                sys.stdout.write(char)
                sys.stdout.flush()
                time.sleep(char_delay)
            print()
            first_chunk = False
        else:
            # Stream semantic chunks
            chunks = re.split(r'([.!?]+\s*)', line)
            chunks = [chunks[i] + (chunks[i+1] if i+1 < len(chunks) else '') 
                     for i in range(0, len(chunks), 2) if chunks[i]]
            
            for j, chunk in enumerate(chunks):
                if chunk.strip():
                    print(chunk, end='', flush=True)
                    if j < len(chunks) - 1:
                        time.sleep(chunk_delay)
            
            print()
            
        if i < len(lines) - 1:
            time.sleep(line_delay)


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

