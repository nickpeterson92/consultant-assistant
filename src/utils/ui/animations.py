"""Animation effects for terminal UI including banners and capabilities display."""

import asyncio
import random
from typing import List, Dict, Any

from .colors import (
    CORP_BLUES, BOLD, DIM, RESET, CLEAR_SCREEN, CURSOR_HOME
)
from .terminal import (
    get_terminal_width, center_text
)


async def animated_banner_display(banner_text: str) -> None:
    """Display animated banner with particle effects.
    
    Args:
        banner_text: The ASCII art banner to animate
    """
    # Additional color palettes for effects
    
    
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
    particles: List[Dict[str, Any]] = []
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
        
        formation_progress = frame / 20.0  # Track how formed the banner is
        
        for particle in particles:
            # Update position
            dx = particle['target_x'] - particle['current_x']
            dy = particle['target_y'] - particle['current_y']
            distance = (dx**2 + dy**2)**0.5
            
            if distance > 0.5:
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


def format_compact_logo_for_textual(logo_text: str) -> str:
    """Format the compact logo with the same gradient styling as the main banner for Textual.
    
    Args:
        logo_text: The ASCII art logo text
        
    Returns:
        Formatted logo with Textual-compatible markup
    """
    lines = logo_text.strip().split('\n')
    if not lines:
        return ""
    
    formatted_lines = []
    for y, line in enumerate(lines):
        formatted_line = ""
        for x, char in enumerate(line):
            if char != ' ':
                # Apply the same gradient as the main banner
                gradient_factor = (y / len(lines) + x / len(line)) / 2
                
                # Map to modern colors similar to the banner animation
                if gradient_factor < 0.2:
                    color = "#3b82f6"  # Blue
                elif gradient_factor < 0.4:
                    color = "#60a5fa"  # Light blue
                elif gradient_factor < 0.6:
                    color = "#7dd3fc"  # Cyan
                elif gradient_factor < 0.8:
                    color = "#a5f3fc"  # Light cyan
                else:
                    color = "#bfdbfe"  # Very light cyan
                
                formatted_line += f"[bold {color}]{char}[/bold {color}]"
            else:
                formatted_line += char
        formatted_lines.append(formatted_line)
    
    return "\n".join(formatted_lines)