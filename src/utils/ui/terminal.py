"""Terminal utilities for dimension handling and text positioning."""

import os
import re
from typing import Optional


def get_terminal_width() -> int:
    """Get terminal width with fallback to 80 columns."""
    try:
        return os.get_terminal_size().columns
    except:
        return 80


def get_terminal_height() -> int:
    """Get terminal height with fallback to 24 rows."""
    try:
        return os.get_terminal_size().lines
    except:
        return 24


def get_terminal_size() -> tuple[int, int]:
    """Get terminal size as (width, height) tuple."""
    return get_terminal_width(), get_terminal_height()


def center_text(text: str, width: Optional[int] = None, fill_char: str = ' ') -> str:
    """Center text accounting for ANSI escape codes.
    
    Args:
        text: Text to center (may contain ANSI codes)
        width: Target width (uses terminal width if None)
        fill_char: Character to use for padding
        
    Returns:
        Centered text with proper padding
    """
    if width is None:
        width = get_terminal_width()
    
    # More comprehensive ANSI escape code pattern
    # Matches all ANSI escape sequences including:
    # - Color codes: \033[38;5;123m
    # - Style codes: \033[1m, \033[0m
    # - Cursor codes: \033[H, \033[2J
    ansi_escape = re.compile(r'\x1b\[[0-9;]*[mHJKDCBAsu]|\x1b\[[\?]?[0-9;]*[hlp]')
    visible_text = ansi_escape.sub('', text)
    visible_len = len(visible_text)
    
    if visible_len >= width:
        return text
    
    # Calculate padding
    total_padding = width - visible_len
    left_padding = total_padding // 2
    right_padding = total_padding - left_padding
    
    return fill_char * left_padding + text + fill_char * right_padding


def center_multiline(text: str, width: Optional[int] = None) -> str:
    """Center multiple lines of text, each line independently.
    
    Args:
        text: Multi-line text to center
        width: Target width (uses terminal width if None)
        
    Returns:
        Centered multi-line text
    """
    if width is None:
        width = get_terminal_width()
    
    lines = text.strip().split('\n')
    centered_lines = []
    
    for line in lines:
        centered_lines.append(center_text(line, width))
    
    return '\n'.join(centered_lines)


def strip_ansi(text: str) -> str:
    """Remove all ANSI escape codes from text.
    
    Args:
        text: Text containing ANSI codes
        
    Returns:
        Plain text without ANSI codes
    """
    ansi_escape = re.compile(r'\x1b\[[0-9;]*[mHJKDCBAsu]|\x1b\[[\?]?[0-9;]*[hlp]')
    return ansi_escape.sub('', text)


def visible_length(text: str) -> int:
    """Calculate visible length of text (excluding ANSI codes).
    
    Args:
        text: Text that may contain ANSI codes
        
    Returns:
        Length of visible characters
    """
    return len(strip_ansi(text))


def truncate_text(text: str, max_length: int, suffix: str = '...') -> str:
    """Truncate text to max length, preserving ANSI codes.
    
    Args:
        text: Text to truncate
        max_length: Maximum visible length
        suffix: Suffix to add when truncated
        
    Returns:
        Truncated text with suffix if needed
    """
    if visible_length(text) <= max_length:
        return text
    
    # This is complex with ANSI codes - simple implementation
    plain = strip_ansi(text)
    if len(plain) <= max_length:
        return text
    
    # For now, strip ANSI and truncate
    # A full implementation would preserve ANSI codes properly
    truncated_plain = plain[:max_length - len(suffix)] + suffix
    return truncated_plain


def clear_screen():
    """Clear the terminal screen."""
    print('\033[2J\033[H', end='', flush=True)


def clear_line():
    """Clear the current line."""
    print('\033[2K\r', end='', flush=True)


def move_cursor(x: int, y: int):
    """Move cursor to specific position.
    
    Args:
        x: Column (1-based)
        y: Row (1-based)
    """
    print(f'\033[{y};{x}H', end='', flush=True)


def save_cursor():
    """Save current cursor position."""
    print('\033[s', end='', flush=True)


def restore_cursor():
    """Restore saved cursor position."""
    print('\033[u', end='', flush=True)


def hide_cursor():
    """Hide the terminal cursor."""
    print('\033[?25l', end='', flush=True)


def show_cursor():
    """Show the terminal cursor."""
    print('\033[?25h', end='', flush=True)