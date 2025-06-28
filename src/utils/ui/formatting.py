"""Text formatting utilities for console output."""

import re
import random
from typing import Optional
from .colors import BOLD, ITALIC, CYAN, YELLOW, RESET


def format_markdown_for_console(text: str) -> str:
    """Convert markdown-style formatting to ANSI codes for console display.
    
    Args:
        text: Markdown-formatted text
        
    Returns:
        Text with ANSI formatting codes
    """
    # Handle code blocks with cyan coloring
    text = re.sub(
        r'```[\w]*\n(.*?)\n```',
        lambda m: f"{CYAN}{m.group(1)}{RESET}",
        text,
        flags=re.DOTALL
    )
    
    # Handle inline code with cyan
    text = re.sub(r'`([^`]+)`', f"{CYAN}\\1{RESET}", text)
    
    # Handle headers with bold
    text = re.sub(r'^### (.+)$', f"{BOLD}\\1{RESET}", text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+)$', f"{BOLD}\\1{RESET}", text, flags=re.MULTILINE)
    text = re.sub(r'^# (.+)$', f"{BOLD}\\1{RESET}", text, flags=re.MULTILINE)
    
    # Handle bold text
    text = re.sub(r'\*\*([^*]+)\*\*', f"{BOLD}\\1{RESET}", text)
    
    # Handle italic text
    text = re.sub(r'\*([^*]+)\*', f"{ITALIC}\\1{RESET}", text)
    
    # Handle bullet points with yellow bullets
    text = re.sub(r'^- ', f"{YELLOW}•{RESET} ", text, flags=re.MULTILINE)
    text = re.sub(r'^  - ', f"  {YELLOW}◦{RESET} ", text, flags=re.MULTILINE)
    
    return text


def get_empty_input_response() -> str:
    """Get a random response for empty input."""
    responses = [
        "I need a bit more to work with. What would you like help with?",
        "Could you tell me what you're looking for?",
        "What can I assist you with today?",
        "I'm here to help! What would you like to know?",
        "Please share what you'd like me to help you with.",
        "I'm ready to assist. What's on your mind?",
        "Feel free to ask me anything about your CRM, tickets, or IT services.",
        "What would you like to explore today?"
    ]
    return random.choice(responses)


def format_error(error_message: str, error_type: Optional[str] = None) -> str:
    """Format an error message for console display.
    
    Args:
        error_message: The error message
        error_type: Optional error type/category
        
    Returns:
        Formatted error string
    """
    from .colors import RED
    
    if error_type:
        return f"{RED}[{error_type}] {error_message}{RESET}"
    return f"{RED}{error_message}{RESET}"


def format_success(message: str) -> str:
    """Format a success message for console display.
    
    Args:
        message: Success message
        
    Returns:
        Formatted success string
    """
    from .colors import GREEN
    return f"{GREEN}✓ {message}{RESET}"


def format_warning(message: str) -> str:
    """Format a warning message for console display.
    
    Args:
        message: Warning message
        
    Returns:
        Formatted warning string
    """
    return f"{YELLOW}⚠ {message}{RESET}"


def format_info(message: str) -> str:
    """Format an info message for console display.
    
    Args:
        message: Info message
        
    Returns:
        Formatted info string
    """
    return f"{CYAN}ℹ {message}{RESET}"


def create_box(content: str, title: Optional[str] = None, width: Optional[int] = None) -> str:
    """Create a box around content with optional title.
    
    Args:
        content: Content to box
        title: Optional title for the box
        width: Box width (auto-sizes if None)
        
    Returns:
        Boxed content string
    """
    from .terminal import visible_length, strip_ansi
    
    lines = content.strip().split('\n')
    
    # Calculate width if not provided
    if width is None:
        max_line_length = max(visible_length(line) for line in lines)
        if title:
            max_line_length = max(max_line_length, len(title) + 2)
        width = max_line_length + 4  # 2 spaces padding + 2 borders
    
    # Box characters
    top_left = '┌'
    top_right = '┐'
    bottom_left = '└'
    bottom_right = '┘'
    horizontal = '─'
    vertical = '│'
    
    # Build box
    result = []
    
    # Top border with optional title
    if title:
        title_str = f" {title} "
        padding = width - len(title_str) - 2
        left_pad = padding // 2
        right_pad = padding - left_pad
        result.append(top_left + horizontal * left_pad + title_str + horizontal * right_pad + top_right)
    else:
        result.append(top_left + horizontal * (width - 2) + top_right)
    
    # Content lines
    for line in lines:
        visible_len = visible_length(line)
        padding = width - visible_len - 2
        result.append(f"{vertical} {line}{' ' * padding}{vertical}")
    
    # Bottom border
    result.append(bottom_left + horizontal * (width - 2) + bottom_right)
    
    return '\n'.join(result)


def format_table(headers: list[str], rows: list[list[str]], 
                 align: Optional[list[str]] = None) -> str:
    """Format data as a simple ASCII table.
    
    Args:
        headers: Column headers
        rows: Table rows
        align: Optional alignment for each column ('left', 'right', 'center')
        
    Returns:
        Formatted table string
    """
    from .terminal import visible_length
    
    # Calculate column widths
    col_widths = []
    for i, header in enumerate(headers):
        max_width = len(header)
        for row in rows:
            if i < len(row):
                max_width = max(max_width, visible_length(str(row[i])))
        col_widths.append(max_width)
    
    # Default alignment
    if align is None:
        align = ['left'] * len(headers)
    
    # Format functions based on alignment
    def format_cell(text: str, width: int, alignment: str) -> str:
        text_len = visible_length(text)
        if alignment == 'right':
            return ' ' * (width - text_len) + text
        elif alignment == 'center':
            padding = width - text_len
            left_pad = padding // 2
            right_pad = padding - left_pad
            return ' ' * left_pad + text + ' ' * right_pad
        else:  # left
            return text + ' ' * (width - text_len)
    
    # Build table
    result = []
    
    # Header
    header_cells = []
    for i, header in enumerate(headers):
        header_cells.append(format_cell(header, col_widths[i], align[i]))
    result.append(' │ '.join(header_cells))
    
    # Separator
    separators = ['─' * width for width in col_widths]
    result.append('─┼─'.join(separators))
    
    # Rows
    for row in rows:
        cells = []
        for i in range(len(headers)):
            text = str(row[i]) if i < len(row) else ''
            cells.append(format_cell(text, col_widths[i], align[i]))
        result.append(' │ '.join(cells))
    
    return '\n'.join(result)