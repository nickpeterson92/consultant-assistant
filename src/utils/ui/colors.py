"""ANSI color codes and style constants for terminal UI."""

# ANSI color codes for consistent styling across the application
CYAN = '\033[36m'
BLUE = '\033[34m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
RED = '\033[31m'
MAGENTA = '\033[35m'
WHITE = '\033[37m'
BLACK = '\033[30m'

# Style modifiers
BOLD = '\033[1m'
ITALIC = '\033[3m'
UNDERLINE = '\033[4m'
DIM = '\033[2m'
RESET = '\033[0m'

# Extended cyan palette for animations
CORP_BLUES = [
    '\033[38;5;30m',   # Dark teal/cyan
    '\033[38;5;36m',   # Cyan (matches prompt)
    '\033[38;5;37m',   # Light cyan
    '\033[38;5;43m',   # Cyan-teal
    '\033[38;5;44m',   # Bright cyan
    '\033[38;5;45m',   # Light bright cyan
    '\033[38;5;51m',   # Very bright cyan
    '\033[38;5;87m',   # Pale cyan
]

# Background colors
BG_BLACK = '\033[40m'
BG_RED = '\033[41m'
BG_GREEN = '\033[42m'
BG_YELLOW = '\033[43m'
BG_BLUE = '\033[44m'
BG_MAGENTA = '\033[45m'
BG_CYAN = '\033[46m'
BG_WHITE = '\033[47m'

# Clear/cursor controls
CLEAR_SCREEN = '\033[2J'
CLEAR_LINE = '\033[2K'
CURSOR_HOME = '\033[H'
CURSOR_SAVE = '\033[s'
CURSOR_RESTORE = '\033[u'
CURSOR_HIDE = '\033[?25l'
CURSOR_SHOW = '\033[?25h'