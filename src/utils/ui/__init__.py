"""User interface utilities for terminal output."""

# Import color constants
from .colors import (
    CYAN, BLUE, GREEN, YELLOW, RED, MAGENTA, WHITE, BLACK,
    BOLD, ITALIC, UNDERLINE, DIM, RESET,
    CORP_BLUES, 
    BG_BLACK, BG_RED, BG_GREEN, BG_YELLOW, BG_BLUE, BG_MAGENTA, BG_CYAN, BG_WHITE,
    CLEAR_SCREEN, CLEAR_LINE, CURSOR_HOME, CURSOR_SAVE, CURSOR_RESTORE,
    CURSOR_HIDE, CURSOR_SHOW
)

# Import terminal utilities
from .terminal import (
    get_terminal_width, get_terminal_height, get_terminal_size,
    center_text, center_multiline, strip_ansi, visible_length,
    truncate_text, clear_screen, clear_line, move_cursor,
    save_cursor, restore_cursor, hide_cursor, show_cursor
)

# Import formatting utilities
from .formatting import (
    format_markdown_for_console, get_empty_input_response,
    format_error, format_success, format_warning, format_info,
    create_box, format_table
)

# Import text effects
from .text_effects import (
    type_out, type_out_sync, instant_print, StreamingContext
)

# Import animations
from .animations import (
    animated_banner_display, display_capabilities_banner
)

# Import categorized banner
from .categorized_banner import display_categorized_capabilities_banner

# Import table utilities
from .tables import (
    TableFormatter, create_simple_table, create_box_table, format_record_table
)

__all__ = [
    # Colors
    'CYAN', 'BLUE', 'GREEN', 'YELLOW', 'RED', 'MAGENTA', 'WHITE', 'BLACK',
    'BOLD', 'ITALIC', 'UNDERLINE', 'DIM', 'RESET', 'CORP_BLUES',
    'BG_BLACK', 'BG_RED', 'BG_GREEN', 'BG_YELLOW', 'BG_BLUE', 'BG_MAGENTA', 'BG_CYAN', 'BG_WHITE',
    'CLEAR_SCREEN', 'CLEAR_LINE', 'CURSOR_HOME', 'CURSOR_SAVE', 'CURSOR_RESTORE',
    'CURSOR_HIDE', 'CURSOR_SHOW',
    
    # Terminal utilities
    'get_terminal_width', 'get_terminal_height', 'get_terminal_size',
    'center_text', 'center_multiline', 'strip_ansi', 'visible_length',
    'truncate_text', 'clear_screen', 'clear_line', 'move_cursor',
    'save_cursor', 'restore_cursor', 'hide_cursor', 'show_cursor',
    
    # Formatting
    'format_markdown_for_console', 'get_empty_input_response',
    'format_error', 'format_success', 'format_warning', 'format_info',
    'create_box', 'format_table',
    
    # Text effects
    'type_out', 'type_out_sync', 'instant_print', 'StreamingContext',
    
    # Animations
    'animated_banner_display', 'display_capabilities_banner',
    'display_categorized_capabilities_banner',
    
    # Tables
    'TableFormatter', 'create_simple_table', 'create_box_table', 'format_record_table'
]