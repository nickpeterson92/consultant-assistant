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


async def animated_banner_display(banner_text):
    """Display an animated 'explosion' effect for the ASCII banner.
    
    Creates a cinematic reveal of the banner with:
    - Initial flash/explosion effect
    - Progressive reveal from center outward
    - Subtle fade-in for dramatic effect
    - Final static display
    
    Args:
        banner_text: The ASCII art banner to animate
    """
    import random
    import os
    
    lines = banner_text.strip().split('\n')
    if not lines:
        return
    
    # Get terminal dimensions
    try:
        terminal_width = os.get_terminal_size().columns
    except:
        terminal_width = 80
    
    # Clear screen for dramatic effect
    print('\033[2J\033[H', end='')  # Clear screen and move cursor to top
    
    # Phase 1: Flash effect - rapid random characters
    flash_frames = 3
    for frame in range(flash_frames):
        print('\033[H', end='')  # Move cursor to top
        for line in lines:
            flash_line = ''
            for char in line:
                if char != ' ':
                    # Random "explosion" characters
                    flash_line += random.choice('*+×·•○◊◈★☆✦✧⚡')
                else:
                    flash_line += ' '
            print(flash_line.center(terminal_width))
        await asyncio.sleep(0.1)
        if frame < flash_frames - 1:
            print('\033[2J', end='')  # Clear for next frame
    
    # Phase 2: Ripple reveal from center
    print('\033[2J\033[H', end='')  # Clear screen
    
    # Calculate center points
    center_y = len(lines) // 2
    max_line_len = max(len(line) for line in lines)
    center_x = max_line_len // 2
    
    # Create reveal mask
    revealed = [[False for _ in line] for line in lines]
    
    # Maximum distance from center
    max_distance = max(
        max(center_y, len(lines) - center_y),
        max(center_x, max_line_len - center_x)
    )
    
    # Reveal in expanding circles
    for radius in range(max_distance + 1):
        print('\033[H', end='')  # Move cursor to top
        
        # Mark characters to reveal based on distance from center
        for y, line in enumerate(lines):
            for x, char in enumerate(line):
                if char != ' ':
                    # Calculate distance from center
                    dist = ((x - center_x) ** 2 + ((y - center_y) * 2) ** 2) ** 0.5
                    if dist <= radius * 3:  # Scale factor for oval shape
                        revealed[y][x] = True
        
        # Display current state
        for y, line in enumerate(lines):
            display_line = ''
            for x, char in enumerate(line):
                if revealed[y][x]:
                    display_line += char
                else:
                    display_line += ' '
            print(display_line.center(terminal_width))
        
        # Speed up as we go
        delay = 0.05 if radius < 5 else 0.02
        await asyncio.sleep(delay)
    
    # Phase 3: Final shimmer effect
    print('\033[H', end='')  # Move cursor to top
    for line in lines:
        print(line.center(terminal_width))
    
    # Add a subtle sparkle finish
    sparkle_positions = []
    for y, line in enumerate(lines):
        for x, char in enumerate(line):
            if char != ' ' and random.random() < 0.1:  # 10% chance
                sparkle_positions.append((x, y))
    
    # Quick sparkle animation
    for _ in range(3):
        print('\033[H', end='')  # Move cursor to top
        for y, line in enumerate(lines):
            display_line = ''
            for x, char in enumerate(line):
                if (x, y) in sparkle_positions and random.random() < 0.5:
                    display_line += random.choice('✦✧★☆')
                else:
                    display_line += char
            print(display_line.center(terminal_width))
        await asyncio.sleep(0.1)
    
    # Final static display
    print('\033[H', end='')  # Move cursor to top
    for line in lines:
        print(line.center(terminal_width))
    
    print()  # Extra line after banner


async def display_capabilities_banner(capabilities_list, terminal_width=None, agent_stats=None):
    """Display a stylish sub-banner for system capabilities.
    
    Creates a modern, clean display of available capabilities with:
    - Elegant box drawing
    - Smart column layout
    - Category grouping
    - Smooth fade-in animation
    
    Args:
        capabilities_list: List of capability strings
        terminal_width: Terminal width (auto-detected if None)
        agent_stats: Optional dict with agent statistics (online_agents, total_agents, etc.)
    """
    import os
    import math
    from .config import get_conversation_config
    
    if not capabilities_list:
        return
    
    config = get_conversation_config()
    
    # Get terminal dimensions
    if terminal_width is None:
        try:
            terminal_width = os.get_terminal_size().columns
        except:
            terminal_width = 80
    
    # Group capabilities by category (based on common prefixes/suffixes)
    categories = {
        "CRM & Sales": [],
        "IT Service Management": [],
        "Project Management": [],
        "Analytics & Reporting": [],
        "Operations & Workflows": []
    }
    
    # Deduplicate capabilities first
    unique_capabilities = list(set(capabilities_list))
    
    # Categorize capabilities
    for cap in sorted(unique_capabilities):
        cap_lower = cap.lower()
        if any(word in cap_lower for word in ['salesforce', 'lead', 'account', 'opportunity', 'contact', 'crm']):
            categories["CRM & Sales"].append(cap)
        elif any(word in cap_lower for word in ['servicenow', 'incident', 'change', 'problem', 'cmdb', 'itsm', 'encoded']):
            categories["IT Service Management"].append(cap)
        elif any(word in cap_lower for word in ['jira', 'sprint', 'agile', 'epic', 'project', 'jql']):
            categories["Project Management"].append(cap)
        elif any(word in cap_lower for word in ['analytics', 'metrics', 'analysis', 'reporting', 'aggregate', 'business_metrics']):
            categories["Analytics & Reporting"].append(cap)
        else:
            categories["Operations & Workflows"].append(cap)
    
    # Remove empty categories
    categories = {k: v for k, v in categories.items() if v}
    
    # Calculate layout
    max_width = min(terminal_width - 4, 120)  # Max 120 chars wide
    content_width = max_width - 4  # Account for borders
    
    # Build the banner content
    lines = []
    
    # Top border with title
    title = " SYSTEM CAPABILITIES "
    padding = (max_width - len(title) - 2) // 2
    top_line = "╔" + "═" * padding + title + "═" * (max_width - padding - len(title) - 2) + "╗"
    lines.append(top_line)
    
    # Status line
    if agent_stats:
        online_count = agent_stats.get('online_agents', 0)
        total_count = agent_stats.get('total_agents', 0)
        agent_text = f"Online Agents: {online_count}/{total_count}"
    else:
        agent_text = f"Categories: {len(categories)}"
    
    status = f"{agent_text} | Total Capabilities: {len(capabilities_list)}"
    lines.append("║ " + status.center(content_width) + " ║")
    lines.append("╟" + "─" * (max_width - 2) + "╢")
    
    # Categories
    for cat_name, caps in categories.items():
        # Category header
        cat_header = f" ▸ {cat_name} "
        lines.append("║" + cat_header.ljust(content_width + 1) + "║")
        
        # Capabilities in columns - using proper console table rendering
        num_columns = 3 if content_width >= 90 else 2 if content_width >= 60 else 1
        
        # Calculate exact column width accounting for padding and separators
        # Formula: (content_width - left_padding - (separators * separator_width)) / num_columns
        left_padding = 2  # "║  " at start
        separator_width = 2  # "  " between columns
        available_width = content_width - left_padding - ((num_columns - 1) * separator_width)
        col_width = available_width // num_columns
        
        # Sort and format capabilities first
        sorted_caps = sorted(caps)
        formatted_caps = []
        for cap in sorted_caps:
            # Convert snake_case to Title Case
            formatted = ' '.join(word.capitalize() for word in cap.split('_'))
            # Add bullet point
            bullet_item = f"• {formatted}"
            # Truncate if needed (leave room for ellipsis)
            if len(bullet_item) > col_width:
                bullet_item = bullet_item[:col_width-3] + "..."
            formatted_caps.append(bullet_item)
        
        # Calculate rows needed
        rows = math.ceil(len(formatted_caps) / num_columns)
        
        # Build rows by filling columns from left to right, top to bottom
        for row_idx in range(rows):
            row_items = []
            for col_idx in range(num_columns):
                # Calculate index - fill by column first
                item_idx = col_idx * rows + row_idx
                if item_idx < len(formatted_caps):
                    row_items.append(formatted_caps[item_idx])
                else:
                    row_items.append("")  # Empty cell
            
            # Build the row with exact spacing
            row_parts = ["║ "]  # Start with border and single space
            
            for i, item in enumerate(row_items):
                # Pad each item to exactly col_width
                padded_item = item.ljust(col_width)
                row_parts.append(padded_item)
                
                # Add separator between columns (not after last)
                if i < len(row_items) - 1:
                    row_parts.append("  ")
            
            # Join all parts
            row_line = "".join(row_parts)
            
            # Calculate remaining space and distribute it
            current_length = len(row_line)
            remaining_space = max_width - 1 - current_length
            
            # Add remaining space before closing border
            row_line = row_line + " " * remaining_space + "║"
            lines.append(row_line)
        
        # Add spacing between categories
        if cat_name != list(categories.keys())[-1]:
            lines.append("║" + " " * content_width + " ║")
    
    # Bottom section with quick tips
    lines.append("╟" + "─" * (max_width - 2) + "╢")
    lines.append("║ " + "Quick Start: Type your request naturally - I'll route it to the right agent!".center(content_width) + " ║")
    lines.append("║ " + "Commands: /help • /state • /new • /list • /switch <id>".center(content_width) + " ║")
    
    # Bottom border
    lines.append("╚" + "═" * (max_width - 2) + "╝")
    
    # Animate the display
    if config.animated_capabilities_enabled:
        print('\033[?25l', end='')  # Hide cursor
        
        # Quick fade-in effect
        for i, line in enumerate(lines):
            # Center the line
            centered_line = line.center(terminal_width)
            print(centered_line)
            await asyncio.sleep(0.02)  # Fast cascade effect
        
        print('\033[?25h', end='')  # Show cursor
    else:
        # Static display
        for line in lines:
            print(line.center(terminal_width))
    
    print()  # Extra line after banner

