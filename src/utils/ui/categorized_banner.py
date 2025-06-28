"""Categorized capabilities banner display with perfect alignment."""

import asyncio
import math
from typing import List, Dict, Any, Optional

from .colors import *
from .terminal import get_terminal_width, center_text, visible_length
from .capability_categories import categorize_capabilities, format_capability_name, get_category_icon


async def display_categorized_capabilities_banner(
    capabilities_list: List[str], 
    terminal_width: Optional[int] = None,
    agent_stats: Optional[Dict[str, Any]] = None
) -> None:
    """Display a beautifully categorized capabilities table with perfect alignment.
    
    Args:
        capabilities_list: List of capabilities to display
        terminal_width: Terminal width (auto-detected if None)
        agent_stats: Optional statistics to display
    """
    if terminal_width is None:
        terminal_width = get_terminal_width()
    
    # Categorize capabilities
    categorized = categorize_capabilities(capabilities_list)
    
    # Calculate table dimensions dynamically
    max_width = min(terminal_width - 4, 120)  # Leave room for centering
    table_width = max_width
    inner_width = table_width - 2  # Account for borders
    
    # Column setup
    num_columns = 3
    left_margin = 1   # Space before first column
    right_margin = 1  # Space after last column  
    gutter_width = 2  # Space between columns
    
    # Calculate exact column width
    total_gutters = gutter_width * (num_columns - 1)
    available_for_columns = inner_width - left_margin - right_margin - total_gutters
    col_width = available_for_columns // num_columns
    
    # Calculate any remainder pixels to distribute
    remainder = available_for_columns % num_columns
    
    # Colors
    border_color = CORP_BLUES[5]
    header_color = CORP_BLUES[6] + BOLD
    category_color = CORP_BLUES[4] + BOLD
    
    # Helper to create perfectly aligned content lines
    def make_content_line(content: str, fill_char: str = ' ') -> str:
        """Create a content line with proper padding."""
        # Calculate how much padding we need
        content_visible_len = visible_length(content)
        padding_needed = inner_width - content_visible_len
        return f"{border_color}║{RESET}{content}{fill_char * padding_needed}{border_color}║{RESET}"
    
    # Helper to create border lines
    def make_border_line(left: str, middle: str, right: str) -> str:
        return f"{border_color}{left}{middle * inner_width}{right}{RESET}"
    
    # Top border
    print(center_text(make_border_line('╔', '═', '╗'), terminal_width))
    
    # Header
    header_text = "SYSTEM CAPABILITIES"
    header_formatted = f"{header_color}{header_text}{RESET}"
    header_padding_left = (inner_width - len(header_text)) // 2
    header_padding_right = inner_width - len(header_text) - header_padding_left
    header_line = f"{' ' * header_padding_left}{header_formatted}{' ' * header_padding_right}"
    print(center_text(make_content_line(header_line), terminal_width))
    
    # Stats line
    if agent_stats:
        online = agent_stats.get('online_agents', 0)
        total = agent_stats.get('total_agents', 0)
        stats_text = f"Online Agents: {online}/{total} | Total Capabilities: {len(capabilities_list)}"
        stats_formatted = f"{CYAN}{stats_text}{RESET}"
        stats_padding_left = (inner_width - len(stats_text)) // 2
        stats_padding_right = inner_width - len(stats_text) - stats_padding_left
        stats_line = f"{' ' * stats_padding_left}{stats_formatted}{' ' * stats_padding_right}"
        print(center_text(make_content_line(stats_line), terminal_width))
    
    # Separator
    print(center_text(make_border_line('╟', '─', '╢'), terminal_width))
    
    # Categories
    for cat_idx, (category, caps) in enumerate(categorized.items()):
        # Category header
        icon = get_category_icon(category)
        cat_header = f"▸ {icon} {category}"
        cat_formatted = f" {category_color}{cat_header}{RESET}"
        cat_line = cat_formatted + ' ' * (inner_width - visible_length(cat_formatted))
        print(center_text(make_content_line(cat_line), terminal_width))
        
        # Capabilities in columns
        num_caps = len(caps)
        rows = math.ceil(num_caps / num_columns)
        
        for row in range(rows):
            # Build items for this row
            items = []
            actual_items = 0  # Track how many actual items we have
            
            for col in range(num_columns):
                idx = row * num_columns + col
                if idx < num_caps:
                    cap_name = format_capability_name(caps[idx])
                    cap_text = f"• {cap_name}"
                    actual_items += 1
                    
                    # Adjust column width - give extra space to first columns if there's remainder
                    this_col_width = col_width + (1 if col < remainder else 0)
                    
                    # Truncate if needed
                    if len(cap_text) > this_col_width:
                        cap_text = cap_text[:this_col_width-3] + "..."
                    
                    items.append(cap_text.ljust(this_col_width))
                else:
                    # Empty column - use appropriate width
                    this_col_width = col_width + (1 if col < remainder else 0)
                    items.append(' ' * this_col_width)
            
            # Build the complete row
            if actual_items > 0:
                # Start with left margin
                row_parts = [' ' * left_margin]
                
                # Add items with gutters between them
                for i, item in enumerate(items):
                    row_parts.append(item)
                    if i < len(items) - 1:  # Not the last item
                        row_parts.append(' ' * gutter_width)
                
                # Add right margin
                row_parts.append(' ' * right_margin)
                
                # Join all parts
                row_content = ''.join(row_parts)
                
                # Verify the length and pad if needed (should not be needed if math is correct)
                if len(row_content) < inner_width:
                    row_content += ' ' * (inner_width - len(row_content))
                elif len(row_content) > inner_width:
                    # Trim if too long (safety check)
                    row_content = row_content[:inner_width]
            else:
                # Empty row
                row_content = ' ' * inner_width
            
            print(center_text(make_content_line(row_content), terminal_width))
            await asyncio.sleep(0.015)  # Animation
        
        # Empty line between categories (except last)
        if cat_idx < len(categorized) - 1:
            empty = ' ' * inner_width
            print(center_text(make_content_line(empty), terminal_width))
    
    # Footer separator
    print(center_text(make_border_line('╟', '─', '╢'), terminal_width))
    
    # Footer messages
    messages = [
        "Quick Start: Type your request naturally - I'll route it to the right agent!",
        "Commands: /help • /state • /new • /list • /switch <id>"
    ]
    
    for msg in messages:
        msg_formatted = f"{DIM}{msg}{RESET}"
        msg_padding_left = (inner_width - len(msg)) // 2
        msg_padding_right = inner_width - len(msg) - msg_padding_left
        msg_line = f"{' ' * msg_padding_left}{msg_formatted}{' ' * msg_padding_right}"
        print(center_text(make_content_line(msg_line), terminal_width))
    
    # Bottom border
    print(center_text(make_border_line('╚', '═', '╝'), terminal_width))
    
    await asyncio.sleep(0.1)