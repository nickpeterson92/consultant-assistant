"""Terminal utility functions."""

import shutil
import re
import os


def get_terminal_width() -> int:
    """Get the terminal width."""
    try:
        return shutil.get_terminal_size().columns
    except:
        return 80  # fallback


def get_terminal_height() -> int:
    """Get the terminal height."""
    try:
        return shutil.get_terminal_size().lines
    except:
        return 24  # fallback


def center_text(text: str, width: int) -> str:
    """Center text within given width."""
    visible_len = visible_length(text)
    if visible_len >= width:
        return text
    
    padding = (width - visible_len) // 2
    return ' ' * padding + text


def visible_length(text: str) -> int:
    """Calculate visible length of text, ignoring ANSI escape sequences."""
    return len(strip_ansi(text))


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)