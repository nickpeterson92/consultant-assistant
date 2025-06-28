"""Animation effects for terminal UI including banners and capabilities display."""

import asyncio
import random
import math
from typing import List, Dict, Any, Optional

from .colors import (
    CORP_BLUES, CYAN, BLUE, GREEN, YELLOW, BOLD, ITALIC, 
    UNDERLINE, DIM, RESET, CLEAR_SCREEN, CURSOR_HOME
)
from .terminal import (
    get_terminal_width, get_terminal_height, center_text, 
    visible_length, strip_ansi
)


async def animated_banner_display(banner_text: str) -> None:
    """Display animated banner with particle effects.
    
    Args:
        banner_text: The ASCII art banner to animate
    """
    # Additional color palettes for effects
    ACCENT_COLORS = [
        '\033[38;5;73m',   # Cyan-green accent
        '\033[38;5;80m',   # Light cyan-green
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
    print(CLEAR_SCREEN + CURSOR_HOME, end='')
    
    # Phase 1: Data particle convergence - particles streaming in
    print(CURSOR_HOME, end='')
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
        print(CURSOR_HOME, end='')
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
        print(CURSOR_HOME, end='')  # Move cursor to top
        
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
    print(CLEAR_SCREEN + CURSOR_HOME, end='')
    
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


def safe_string_width(s: str) -> int:
    """Calculate display width of a string, handling ANSI codes and unicode."""
    return visible_length(s)


def format_capability_item(capability: str, width: int, is_highlighted: bool = False) -> str:
    """Format a capability item to fit within given width."""
    if is_highlighted:
        color = CYAN + BOLD
    else:
        color = ''
    
    if safe_string_width(capability) > width - 2:
        # Truncate if too long
        capability = capability[:width-5] + "..."
    
    # Pad to fill width
    padding = width - safe_string_width(capability) - 2
    return f" {color}{capability}{RESET}{' ' * padding} "


async def display_capabilities_banner(capabilities_list: List[str], 
                                    terminal_width: Optional[int] = None,
                                    agent_stats: Optional[Dict[str, Any]] = None) -> None:
    """Display a modern, perfectly aligned capabilities table.
    
    Args:
        capabilities_list: List of capabilities to display
        terminal_width: Terminal width (auto-detected if None)
        agent_stats: Optional statistics to display
    """
    if terminal_width is None:
        terminal_width = get_terminal_width()
    
    # Calculate dimensions
    num_capabilities = len(capabilities_list)
    columns = 3
    rows = math.ceil(num_capabilities / columns)
    
    # Dynamic column width based on terminal size
    total_table_width = min(terminal_width - 4, 100)  # Max 100 chars wide
    col_width = total_table_width // columns
    
    # Table styling
    border_color = CORP_BLUES[5]
    header_color = CORP_BLUES[6] + BOLD
    
    # Top border
    print(center_text(f"{border_color}╔{'═' * (total_table_width - 2)}╗{RESET}", terminal_width))
    
    # Header
    header = "SYSTEM CAPABILITIES"
    header_padding = (total_table_width - len(header) - 2) // 2
    print(center_text(
        f"{border_color}║{RESET}{' ' * header_padding}{header_color}{header}{RESET}"
        f"{' ' * (total_table_width - len(header) - header_padding - 2)}{border_color}║{RESET}", 
        terminal_width
    ))
    
    # Header separator
    print(center_text(f"{border_color}╠{'═' * (total_table_width - 2)}╣{RESET}", terminal_width))
    
    # Capability rows with animation
    for row in range(rows):
        row_items = []
        for col in range(columns):
            idx = row * columns + col
            if idx < num_capabilities:
                capability = capabilities_list[idx]
                # Highlight certain capabilities
                is_highlighted = any(keyword in capability.lower() for keyword in 
                                   ['orchestrat', 'ai', 'integrat', 'salesforce', 'jira', 'servicenow'])
                row_items.append(format_capability_item(capability, col_width, is_highlighted))
            else:
                row_items.append(' ' * col_width)
        
        # Animate row appearance
        row_content = f"{border_color}║{RESET}{''.join(row_items)}{border_color}║{RESET}"
        print(center_text(row_content, terminal_width))
        await asyncio.sleep(0.05)  # Small delay for animation effect
    
    # Stats separator if we have stats
    if agent_stats:
        print(center_text(f"{border_color}╠{'═' * (total_table_width - 2)}╣{RESET}", terminal_width))
        
        # Agent stats
        stats_lines = []
        if 'total_agents' in agent_stats:
            stats_lines.append(f"Active Agents: {agent_stats['total_agents']}")
        if 'systems' in agent_stats:
            stats_lines.append(f"Connected Systems: {', '.join(agent_stats['systems'])}")
        if 'readiness' in agent_stats:
            stats_lines.append(f"System Status: {agent_stats['readiness']}")
        
        for stat in stats_lines:
            stat_padding = (total_table_width - len(stat) - 2) // 2
            print(center_text(
                f"{border_color}║{RESET}{' ' * stat_padding}{CYAN}{stat}{RESET}"
                f"{' ' * (total_table_width - len(stat) - stat_padding - 2)}{border_color}║{RESET}",
                terminal_width
            ))
            await asyncio.sleep(0.03)
    
    # Bottom border
    print(center_text(f"{border_color}╚{'═' * (total_table_width - 2)}╝{RESET}", terminal_width))
    
    # Add a subtle fade effect at the end
    await asyncio.sleep(0.1)