"""Text streaming and typing effects for console output."""

import sys
import asyncio
import re
import math
from typing import Optional, Callable, Union


async def type_out(text: str, delay: float = 0.003, 
                   natural_pauses: bool = True,
                   format_func: Optional[Callable[[str], str]] = None) -> None:
    """Stream text to console with natural typing effect.
    
    Uses semantic chunking for smoother output and natural pauses
    at punctuation marks.
    
    Args:
        text: Text to stream
        delay: Base delay between chunks
        natural_pauses: Whether to add pauses at punctuation
        format_func: Optional function to format text before output
    """
    if format_func:
        text = format_func(text)
    
    # Semantic chunking patterns
    chunk_patterns = [
        # Code blocks - output immediately
        (r'```[\s\S]*?```', 0),
        # Inline code - quick output
        (r'`[^`]+`', delay * 0.5),
        # URLs - output as single unit
        (r'https?://[^\s]+', delay * 0.5),
        # Numbers with units
        (r'\d+\.?\d*\s*(?:ms|s|min|hr|hours?|days?|GB|MB|KB|%)', delay * 0.5),
        # End of sentence
        (r'[^.!?]+[.!?]+\s*', delay * 2 if natural_pauses else delay),
        # Comma-separated phrases
        (r'[^,]+,\s*', delay * 1.5 if natural_pauses else delay),
        # List items
        (r'^\s*[-•◦]\s+[^\n]+', delay),
        # Headers
        (r'^#+\s+[^\n]+', delay * 0.5),
        # Words and spaces
        (r'\S+\s*', delay),
        # Individual characters as fallback
        (r'.', delay)
    ]
    
    # Find all semantic chunks
    chunks = []
    remaining = text
    
    while remaining:
        best_match = None
        best_delay = delay
        
        for pattern, chunk_delay in chunk_patterns:
            match = re.match(pattern, remaining, re.MULTILINE)
            if match:
                best_match = match
                best_delay = chunk_delay
                break
        
        if best_match:
            chunk = best_match.group(0)
            chunks.append((chunk, best_delay))
            remaining = remaining[len(chunk):]
        else:
            # Fallback to single character
            chunks.append((remaining[0], delay))
            remaining = remaining[1:]
    
    # Output chunks with appropriate delays
    for chunk, chunk_delay in chunks:
        sys.stdout.write(chunk)
        sys.stdout.flush()
        
        # Add delay if not at end
        if chunk != chunks[-1][0]:
            # Variable delay based on chunk type
            if chunk_delay > 0:
                # Add some randomness for natural feel
                actual_delay = chunk_delay * (0.8 + 0.4 * math.sin(len(chunk)))
                await asyncio.sleep(max(0.001, actual_delay))
    
    sys.stdout.write('\n')
    sys.stdout.flush()


def type_out_sync(text: str, delay: float = 0.003,
                  natural_pauses: bool = True,
                  format_func: Optional[Callable[[str], str]] = None) -> None:
    """Synchronous version of type_out for non-async contexts.
    
    Args:
        text: Text to stream
        delay: Base delay between chunks
        natural_pauses: Whether to add pauses at punctuation
        format_func: Optional function to format text before output
    """
    import time
    
    if format_func:
        text = format_func(text)
    
    # Semantic chunking patterns (same as async version)
    chunk_patterns = [
        # Code blocks - output immediately
        (r'```[\s\S]*?```', 0),
        # Inline code - quick output
        (r'`[^`]+`', delay * 0.5),
        # URLs - output as single unit
        (r'https?://[^\s]+', delay * 0.5),
        # Numbers with units
        (r'\d+\.?\d*\s*(?:ms|s|min|hr|hours?|days?|GB|MB|KB|%)', delay * 0.5),
        # End of sentence
        (r'[^.!?]+[.!?]+\s*', delay * 2 if natural_pauses else delay),
        # Comma-separated phrases
        (r'[^,]+,\s*', delay * 1.5 if natural_pauses else delay),
        # List items
        (r'^\s*[-•◦]\s+[^\n]+', delay),
        # Headers
        (r'^#+\s+[^\n]+', delay * 0.5),
        # Words and spaces
        (r'\S+\s*', delay),
        # Individual characters as fallback
        (r'.', delay)
    ]
    
    # Find all semantic chunks
    chunks = []
    remaining = text
    
    while remaining:
        best_match = None
        best_delay = delay
        
        for pattern, chunk_delay in chunk_patterns:
            match = re.match(pattern, remaining, re.MULTILINE)
            if match:
                best_match = match
                best_delay = chunk_delay
                break
        
        if best_match:
            chunk = best_match.group(0)
            chunks.append((chunk, best_delay))
            remaining = remaining[len(chunk):]
        else:
            # Fallback to single character
            chunks.append((remaining[0], delay))
            remaining = remaining[1:]
    
    # Output chunks with appropriate delays
    for i, (chunk, chunk_delay) in enumerate(chunks):
        sys.stdout.write(chunk)
        sys.stdout.flush()
        
        # Add delay if not at end
        if i < len(chunks) - 1 and chunk_delay > 0:
            # Add some randomness for natural feel
            actual_delay = chunk_delay * (0.8 + 0.4 * math.sin(len(chunk)))
            time.sleep(max(0.001, actual_delay))
    
    sys.stdout.write('\n')
    sys.stdout.flush()


def instant_print(text: str, format_func: Optional[Callable[[str], str]] = None) -> None:
    """Print text instantly without streaming effect.
    
    Args:
        text: Text to print
        format_func: Optional function to format text before output
    """
    if format_func:
        text = format_func(text)
    print(text)


class StreamingContext:
    """Context manager for streaming text output."""
    
    def __init__(self, delay: float = 0.003, natural_pauses: bool = True):
        self.delay = delay
        self.natural_pauses = natural_pauses
        self.is_async = False
    
    async def __aenter__(self):
        self.is_async = True
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def __enter__(self):
        self.is_async = False
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def write(self, text: str, format_func: Optional[Callable[[str], str]] = None):
        """Write text with streaming effect."""
        if self.is_async:
            await type_out(text, self.delay, self.natural_pauses, format_func)
        else:
            type_out_sync(text, self.delay, self.natural_pauses, format_func)
    
    def write_sync(self, text: str, format_func: Optional[Callable[[str], str]] = None):
        """Write text synchronously."""
        type_out_sync(text, self.delay, self.natural_pauses, format_func)