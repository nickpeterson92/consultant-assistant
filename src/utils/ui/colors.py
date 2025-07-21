"""Color definitions for terminal UI."""

# ANSI color codes
RESET = '\033[0m'
BOLD = '\033[1m'
DIM = '\033[2m'
ITALIC = '\033[3m'
UNDERLINE = '\033[4m'

# Basic colors
BLACK = '\033[30m'
RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
BLUE = '\033[34m'
MAGENTA = '\033[35m'
CYAN = '\033[36m'
WHITE = '\033[37m'

# Corporate blue gradient (from darker to lighter)
CORP_BLUES = [
    '\033[38;5;17m',   # Very dark blue
    '\033[38;5;18m',   # Dark blue
    '\033[38;5;19m',   # Medium dark blue
    '\033[38;5;20m',   # Medium blue
    '\033[38;5;21m',   # Blue
    '\033[38;5;33m',   # Light blue
    '\033[38;5;39m',   # Bright blue
    '\033[38;5;51m',   # Very bright blue
]

# Terminal control
CLEAR_SCREEN = '\033[2J'
CURSOR_HOME = '\033[H'