"""Animation and formatting utilities for the textual UI."""

import asyncio
from typing import Optional


async def animated_banner_display(banner: str, delay: float = 0.05) -> None:
    """Display ASCII banner with simple animation.
    
    Args:
        banner: ASCII art banner to display
        delay: Delay between each line in seconds
    """
    lines = banner.strip().split('\n')
    
    for line in lines:
        print(line)
        await asyncio.sleep(delay)


def format_compact_logo_for_textual(logo: str) -> str:
    """Format compact logo for textual display.
    
    Args:
        logo: ASCII art logo string
        
    Returns:
        Formatted logo ready for textual rich markup
    """
    # Remove leading/trailing whitespace and ensure consistent formatting
    formatted_lines = []
    for line in logo.strip().split('\n'):
        # Add rich markup for styling
        if line.strip():
            formatted_lines.append(f"[bold cyan]{line}[/bold cyan]")
        else:
            formatted_lines.append("")
    
    return '\n'.join(formatted_lines)