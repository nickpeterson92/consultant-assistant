"""User Experience (UX) utilities for the multi-agent orchestrator system.

This module provides all UI/UX-related functionality including:
- Animated banner displays with gradient effects
- Dynamic console-width responsive layouts
- Capabilities table with color-coded categories
- Typing effects for natural conversation flow
- Markdown to ANSI formatting for rich console output
- Loading animations and progress indicators

All functions dynamically adjust to terminal width for optimal display.
"""

import sys
import asyncio
import time
import random
import os
import re
import math


# ANSI color codes for consistent styling across the application
CYAN = '\033[36m'
BLUE = '\033[34m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
BOLD = '\033[1m'
ITALIC = '\033[3m'
UNDERLINE = '\033[4m'
DIM = '\033[2m'
RESET = '\033[0m'


def get_terminal_width():
    """Get terminal width with fallback to 80 columns."""
    try:
        return os.get_terminal_size().columns
    except:
        return 80


def center_text(text, width=None, fill_char=' '):
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


def center_multiline(text, width=None):
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


async def animated_banner_display(banner_text):
    """Display a professional data visualization-inspired animation.
    
    Creates an elegant enterprise-grade reveal sequence:
    - Data particle convergence effect
    - Neural network connection visualization
    - Smooth crystallization reveal
    - Professional gradient transitions
    - Subtle tech-inspired accents
    
    Args:
        banner_text: The ASCII art banner to animate
    """
    # Subtle professional color palette - muted blues
    CORP_BLUES = [
        '\033[38;5;17m',   # Navy blue
        '\033[38;5;18m',   # Dark blue
        '\033[38;5;19m',   # Deep blue
        '\033[38;5;20m',   # Royal blue
        '\033[38;5;21m',   # Blue
        '\033[38;5;33m',   # Sky blue
        '\033[38;5;39m',   # Light blue
    ]
    
    ACCENT_COLORS = [
        '\033[38;5;60m',   # Muted purple-gray
        '\033[38;5;67m',   # Subtle blue-gray
    ]
    
    DATA_COLORS = [
        '\033[38;5;245m',  # Light gray
        '\033[38;5;250m',  # Very light gray
    ]
    
    lines = banner_text.strip().split('\n')
    if not lines:
        return
    
    terminal_width = get_terminal_width()
    terminal_height = 40  # Assume reasonable height
    
    # Clear screen for dramatic effect
    print('\033[2J\033[H', end='')  # Clear screen and move cursor to top
    
    # Phase 1: Data particle convergence - particles streaming in
    print('\033[H', end='')
    banner_height = len(lines)
    banner_width = max(len(line) for line in lines)
    banner_start_y = (terminal_height - banner_height) // 2
    banner_start_x = (terminal_width - banner_width) // 2
    
    # Create data particles that will converge to form the banner
    particles = []
    for y, line in enumerate(lines):
        for x, char in enumerate(line):
            if char != ' ':
                # Start particles from random edges
                edge = random.choice(['top', 'bottom', 'left', 'right'])
                if edge == 'top':
                    start_x = random.randint(0, terminal_width - 1)
                    start_y = 0
                elif edge == 'bottom':
                    start_x = random.randint(0, terminal_width - 1)
                    start_y = terminal_height - 1
                elif edge == 'left':
                    start_x = 0
                    start_y = random.randint(0, terminal_height - 1)
                else:  # right
                    start_x = terminal_width - 1
                    start_y = random.randint(0, terminal_height - 1)
                
                target_x = banner_start_x + x
                target_y = banner_start_y + y
                particles.append({
                    'char': char,
                    'start_x': start_x,
                    'start_y': start_y,
                    'current_x': float(start_x),
                    'current_y': float(start_y),
                    'target_x': target_x,
                    'target_y': target_y,
                    'speed': random.uniform(0.15, 0.25),
                    'trail': random.choice(['·', '•', '°', '¤'])
                })
    
    # Animate particles converging and forming the banner
    for frame in range(20):
        screen = [[' ' for _ in range(terminal_width)] for _ in range(terminal_height)]
        
        all_arrived = True
        formation_progress = frame / 20.0  # Track how formed the banner is
        
        for particle in particles:
            # Update position
            dx = particle['target_x'] - particle['current_x']
            dy = particle['target_y'] - particle['current_y']
            distance = (dx**2 + dy**2)**0.5
            
            if distance > 0.5:
                all_arrived = False
                # Move towards target with acceleration as we get closer
                speed_factor = min(particle['speed'] * (1 + formation_progress), 0.4)
                particle['current_x'] += dx * speed_factor
                particle['current_y'] += dy * speed_factor
                
                # Draw moving particle with trail
                trail_x = int(particle['current_x'])
                trail_y = int(particle['current_y'])
                if 0 <= trail_x < terminal_width and 0 <= trail_y < terminal_height:
                    # Trail gets brighter as particles approach their targets
                    color_intensity = min(4 + int(formation_progress * 3), len(CORP_BLUES) - 1)
                    color = CORP_BLUES[color_intensity]
                    screen[trail_y][trail_x] = color + particle['trail'] + RESET
            else:
                # Particle has arrived and is forming the banner
                particle['current_x'] = particle['target_x']
                particle['current_y'] = particle['target_y']
                x = int(particle['current_x'])
                y = int(particle['current_y'])
                if 0 <= x < terminal_width and 0 <= y < terminal_height:
                    # Characters solidify with increasing brightness
                    if formation_progress < 0.3:
                        # Just arrived, dim and flickering
                        color = CORP_BLUES[2] + DIM
                    elif formation_progress < 0.7:
                        # Solidifying
                        color = CORP_BLUES[4]
                    else:
                        # Fully formed, bright and bold
                        color = CORP_BLUES[6] + BOLD
                    screen[y][x] = color + particle['char'] + RESET
        
        # Render frame
        print('\033[H', end='')
        for row in screen:
            print(''.join(row))
        
        # Dynamic timing - slow start, accelerate, then slow for final formation
        if frame < 5:
            await asyncio.sleep(0.12)  # Slow start
        elif frame < 15:
            await asyncio.sleep(0.06)  # Fast convergence
        else:
            await asyncio.sleep(0.10)  # Slow crystallization
    
    # Brief pause to appreciate the formed banner
    await asyncio.sleep(0.3)
    
    # Phase 2: Banner stabilization and final formation
    # The banner is now formed, let's add a final stabilization effect
    
    # Smooth transition to final banner state - characters brighten and stabilize
    for stabilization_frame in range(8):
        print('\033[H', end='')  # Move cursor to top
        
        # Add subtle background shimmer effect
        if stabilization_frame < 4:
            for _ in range(5):
                gx = random.randint(0, terminal_width - 1)
                gy = random.randint(0, terminal_height - 1)
                print(f'\033[{gy};{gx}H{CORP_BLUES[0]}{DIM}·{RESET}', end='')
        
        # Position and display the final banner
        print(f'\033[{banner_start_y};0H', end='')
        for y, line in enumerate(lines):
            display_line = ''
            for x, char in enumerate(line):
                if char != ' ':
                    # Final stabilization - characters get progressively brighter and more stable
                    if stabilization_frame < 3:
                        # Still stabilizing with slight flicker
                        color = CORP_BLUES[4] if random.random() < 0.8 else CORP_BLUES[5]
                    elif stabilization_frame < 6:
                        # Almost stable, consistent brightness
                        color = CORP_BLUES[5] + BOLD
                    else:
                        # Fully stable, final professional appearance
                        gradient_factor = (y / len(lines) + x / len(line)) / 2
                        color_idx = min(4 + int(gradient_factor * 2), len(CORP_BLUES) - 1)
                        color = CORP_BLUES[color_idx] + BOLD
                    
                    display_line += color + char + RESET
                else:
                    display_line += char
            
            print(center_text(display_line, terminal_width))
        
        await asyncio.sleep(0.12)
    
    # Clear screen one final time for clean banner presentation
    print('\033[2J\033[H', end='')
    
    # Phase 3: Final banner presentation - seamless transition
    # The banner is now fully formed and ready for the final display
    
    # Display the final formed banner - this becomes the static banner
    # Position and show the completed banner with professional gradient
    print(f'\033[{banner_start_y};0H', end='')
    for y, line in enumerate(lines):
        display_line = ''
        for x, char in enumerate(line):
            if char != ' ':
                # Final professional gradient
                gradient_factor = (y / len(lines) + x / len(line)) / 2
                color_idx = min(4 + int(gradient_factor * 2), len(CORP_BLUES) - 1)
                color = CORP_BLUES[color_idx] + BOLD
                display_line += color + char + RESET
            else:
                display_line += char
        
        print(center_text(display_line, terminal_width))


async def display_capabilities_banner(capabilities_list, terminal_width=None, agent_stats=None):
    """Display a modern, perfectly aligned capabilities table.
    
    Creates a professional display using modern table alignment techniques:
    - Proper Unicode width calculation for perfect alignment
    - Responsive column layout that adapts to terminal width
    - Category grouping with professional symbols
    - Dynamic column distribution for optimal readability
    - Modern box drawing with consistent spacing
    
    Args:
        capabilities_list: List of capability strings
        terminal_width: Terminal width (auto-detected if None)
        agent_stats: Optional dict with agent statistics (online_agents, total_agents, etc.)
    """
    from .config import get_conversation_config
    
    if not capabilities_list:
        return
    
    config = get_conversation_config()
    
    # ANSI color codes for different sections - muted professional palette
    HEADER_COLOR = '\033[38;5;33m'    # Sky blue for header
    BORDER_COLOR = '\033[38;5;240m'   # Gray for borders
    CATEGORY_COLORS = {
        "▣ CRM & Sales": '\033[38;5;67m',            # Subtle blue-gray
        "⚡ IT Service Management": '\033[38;5;60m',  # Muted purple-gray
        "◆ Project Management": '\033[38;5;65m',     # Muted green-gray
        "▲ Analytics & Reporting": '\033[38;5;94m',  # Muted brown
        "● Operations & Workflows": '\033[38;5;66m'  # Muted teal
    }
    STATUS_COLOR = '\033[38;5;245m'   # Light gray for status
    TIP_COLOR = '\033[38;5;240m'      # Medium gray for tips
    BULLET_COLOR = '\033[38;5;242m'   # Gray for bullets
    
    # Get terminal dimensions
    if terminal_width is None:
        terminal_width = get_terminal_width()
    
    # Group capabilities by category (based on common prefixes/suffixes)
    # Using professional Unicode symbols that align with our tech aesthetic
    categories = {
        "▣ CRM & Sales": [],           # Solid square - business/structure
        "⚡ IT Service Management": [], # Lightning bolt - tech/systems
        "◆ Project Management": [],    # Diamond - precision/planning  
        "▲ Analytics & Reporting": [], # Triangle - insights/direction
        "● Operations & Workflows": [] # Circle - processes/flow
    }
    
    # Deduplicate capabilities first
    unique_capabilities = list(set(capabilities_list))
    
    # Categorize capabilities
    for cap in sorted(unique_capabilities):
        cap_lower = cap.lower()
        if any(word in cap_lower for word in ['salesforce', 'lead', 'account', 'opportunity', 'contact', 'crm']):
            categories["▣ CRM & Sales"].append(cap)
        elif any(word in cap_lower for word in ['servicenow', 'incident', 'change', 'problem', 'cmdb', 'itsm', 'encoded']):
            categories["⚡ IT Service Management"].append(cap)
        elif any(word in cap_lower for word in ['jira', 'sprint', 'agile', 'epic', 'project', 'jql']):
            categories["◆ Project Management"].append(cap)
        elif any(word in cap_lower for word in ['analytics', 'metrics', 'analysis', 'reporting', 'aggregate', 'business_metrics']):
            categories["▲ Analytics & Reporting"].append(cap)
        else:
            categories["● Operations & Workflows"].append(cap)
    
    # Remove empty categories
    categories = {k: v for k, v in categories.items() if v}
    
    # Calculate layout
    max_width = min(terminal_width - 4, 120)  # Max 120 chars wide
    content_width = max_width - 4  # Account for borders
    
    # Build the banner content
    lines = []
    
    # Top border with title
    title = " SYSTEM CAPABILITIES "
    border_inner_width = max_width - 2  # Subtract 2 for the border characters
    padding = (border_inner_width - len(title)) // 2
    right_padding = border_inner_width - padding - len(title)
    top_line = f"{BORDER_COLOR}{BOLD}╔" + "═" * padding + f"{HEADER_COLOR}{title}{BORDER_COLOR}" + "═" * right_padding + f"╗{RESET}"
    lines.append(top_line)
    
    # Status line
    if agent_stats:
        online_count = agent_stats.get('online_agents', 0)
        total_count = agent_stats.get('total_agents', 0)
        agent_text = f"Online Agents: {online_count}/{total_count}"
    else:
        agent_text = f"Categories: {len(categories)}"
    
    status = f"{agent_text} | Total Capabilities: {len(capabilities_list)}"
    # Account for the border and spacing: "║ " and " ║"
    inner_content_width = max_width - 4
    lines.append(f"{BORDER_COLOR}║{RESET} {STATUS_COLOR}{status.center(inner_content_width)}{RESET} {BORDER_COLOR}║{RESET}")
    lines.append(f"{BORDER_COLOR}╟" + "─" * (max_width - 2) + f"╢{RESET}")
    
    def safe_string_width(text):
        """Calculate display width accounting for ANSI codes and Unicode"""
        if not text:
            return 0
        # Remove ANSI escape codes using the same pattern as center_text
        ansi_escape = re.compile(r'\x1b\[[0-9;]*[mHJKDCBAsu]|\x1b\[[\?]?[0-9;]*[hlp]')
        clean_text = ansi_escape.sub('', text)
        return len(clean_text)
    
    def format_capability_item(text, width):
        """Format a capability item with proper truncation"""
        # Clean and format the capability name (title case, replace underscores)
        clean_text = text.replace('_', ' ').title()
        
        if safe_string_width(clean_text) <= width - 2:  # Account for "• " prefix
            return f"• {clean_text}"
        else:
            # Truncate with ellipsis
            max_len = width - 5  # Account for "• " and "..."
            return f"• {clean_text[:max_len]}..."
    
    # Categories
    for cat_idx, (cat_name, caps) in enumerate(categories.items()):
        # Category header - properly aligned
        cat_color = CATEGORY_COLORS.get(cat_name, '\033[38;5;255m')
        cat_display = f"▸ {cat_name}"
        inner_width = max_width - 4  # Account for "║ " and " ║"
        
        # Left-align category header with proper padding
        padded_header = cat_display.ljust(inner_width)
        lines.append(f"{BORDER_COLOR}║{RESET} {cat_color}{BOLD}{padded_header}{RESET} {BORDER_COLOR}║{RESET}")
        
        # Calculate optimal column layout
        inner_width = max_width - 4  # Account for "║ " and " ║"
        
        # Determine number of columns based on terminal width and content
        if inner_width >= 100:
            num_columns = 3
        elif inner_width >= 70:
            num_columns = 2
        else:
            num_columns = 1
        
        # Calculate column widths with proper spacing
        # Format: "║ col1   col2   col3 ║"
        #         ^^ ^^   ^^   ^^ ^^
        #         border spaces border
        
        if num_columns == 1:
            col_width = inner_width
        else:
            # Reserve space for gaps between columns (3 spaces each)
            gap_space = (num_columns - 1) * 3
            available_space = inner_width - gap_space
            col_width = available_space // num_columns
        
        # Sort and format capabilities first
        sorted_caps = sorted(caps)
        formatted_caps = []
        
        for cap in sorted_caps:
            # Convert snake_case to Title Case
            formatted = ' '.join(word.capitalize() for word in cap.split('_'))
            
            # Add bullet point without emoji
            bullet_item = f"• {formatted}"
            formatted_caps.append(bullet_item)
        
        # Calculate rows needed
        rows = math.ceil(len(formatted_caps) / num_columns)
        
        # Build table row by row
        for row_idx in range(rows):
            row_parts = []
            
            for col_idx in range(num_columns):
                # Calculate which item to show in this cell
                item_idx = col_idx * rows + row_idx
                
                if item_idx < len(formatted_caps):
                    item = formatted_caps[item_idx]
                    # Apply bullet coloring
                    if item.startswith("• "):
                        colored_item = f"{BULLET_COLOR}•{RESET} {item[2:]}"
                    else:
                        colored_item = item
                    
                    # Ensure item fits in column width
                    visible_width = safe_string_width(item)
                    if visible_width > col_width:
                        # Truncate with ellipsis
                        truncated = item[:col_width-3] + "..."
                        colored_item = f"{BULLET_COLOR}•{RESET} {truncated[2:]}"
                    
                    # Pad to exact column width
                    padding = col_width - safe_string_width(item)
                    padded_item = colored_item + " " * max(0, padding)
                else:
                    # Empty cell
                    padded_item = " " * col_width
                
                row_parts.append(padded_item)
            
            # Join columns with 3-space separators
            if num_columns > 1:
                row_content = "   ".join(row_parts)
            else:
                row_content = row_parts[0]
            
            # Final width adjustment
            content_width = safe_string_width(row_content)
            if content_width < inner_width:
                row_content += " " * (inner_width - content_width)
            elif content_width > inner_width:
                row_content = row_content[:inner_width]
            
            # Create the bordered line
            lines.append(f"{BORDER_COLOR}║{RESET} {row_content} {BORDER_COLOR}║{RESET}")
        
        # Add spacing between categories
        if cat_idx < len(categories) - 1:
            lines.append(f"{BORDER_COLOR}║{RESET}" + " " * (max_width - 2) + f"{BORDER_COLOR}║{RESET}")
    
    # Bottom section with quick tips
    lines.append(f"{BORDER_COLOR}╟" + "─" * (max_width - 2) + f"╢{RESET}")
    quick_start = "Quick Start: Type your request naturally - I'll route it to the right agent!"
    commands = "Commands: /help • /state • /new • /list • /switch <id>"
    bottom_inner_width = max_width - 4
    lines.append(f"{BORDER_COLOR}║{RESET} {TIP_COLOR}{DIM}{quick_start.center(bottom_inner_width)}{RESET} {BORDER_COLOR}║{RESET}")
    lines.append(f"{BORDER_COLOR}║{RESET} {TIP_COLOR}{DIM}{commands.center(bottom_inner_width)}{RESET} {BORDER_COLOR}║{RESET}")
    
    # Bottom border
    lines.append(f"{BORDER_COLOR}{BOLD}╚" + "═" * (max_width - 2) + f"╝{RESET}")
    
    # Center and display each line
    if config.animated_capabilities_enabled:
        print('\033[?25l', end='')  # Hide cursor
        
        # Quick fade-in effect with gradient
        for i, line in enumerate(lines):
            # Center the entire line
            print(center_text(line, terminal_width))
            await asyncio.sleep(0.02)  # Fast cascade effect
        
        print('\033[?25h', end='')  # Show cursor
    else:
        # Static display
        for line in lines:
            print(center_text(line, terminal_width))
    
    print()  # Extra line after banner


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


def format_markdown_for_console(text):
    """Convert markdown-style formatting to ANSI escape codes for console display.
    
    Transforms:
    - **bold** → ANSI bold
    - *italic* → ANSI italic
    - `code` → ANSI cyan/monospace style
    - # Headers → ANSI bold + underline
    - --- → horizontal rule
    
    Args:
        text: String with markdown formatting
        
    Returns:
        String with ANSI escape codes for terminal display
    """
    # Copy text to avoid modifying original
    formatted = text
    
    # Headers (# Header → bold + underline)
    formatted = re.sub(r'^(#{1,6})\s+(.+)$', lambda m: f"{BOLD}{UNDERLINE}{m.group(2)}{RESET}", formatted, flags=re.MULTILINE)
    
    # Bold text (**text** → bold)
    formatted = re.sub(r'\*\*([^*]+)\*\*', f'{BOLD}\\1{RESET}', formatted)
    
    # Italic text (*text* → italic, but not **text**)
    # This regex ensures we don't match asterisks that are part of bold
    formatted = re.sub(r'(?<!\*)\*(?!\*)([^*]+)\*(?!\*)', f'{ITALIC}\\1{RESET}', formatted)
    
    # Code blocks (`code` → cyan)
    formatted = re.sub(r'`([^`]+)`', f'{CYAN}\\1{RESET}', formatted)
    
    # Horizontal rules (---, ***, ___) → proper line
    formatted = re.sub(r'^(---+|___+|\*\*\*+)\s*$', '─' * 50, formatted, flags=re.MULTILINE)
    
    # Table formatting - make pipes more visible
    formatted = re.sub(r'\|', f'{CYAN}│{RESET}', formatted)
    
    return formatted


def get_empty_input_response():
    """Get a varied response for empty input to maintain conversational flow."""
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