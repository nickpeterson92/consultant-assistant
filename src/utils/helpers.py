# helpers.property


import sys
import asyncio
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage


def smart_preserve_messages(messages: list, keep_count: int = 2):
    """Preserve complete tool call exchanges while respecting keep_count
    
    SIMPLE approach using LangGraph's trim_messages best practices.
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
    # Animates printing of the given text one character at a time.
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        await asyncio.sleep(delay)

