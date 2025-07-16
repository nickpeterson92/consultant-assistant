"""Global progress state for plan execution UI coordination."""

import threading
from typing import Optional, Callable, Dict, Any, List

# Global state for progressive plan execution UI
_progress_state = {
    "current_operation": None,
    "update_progressive_step": None,
    "complete_current_step": None,
    "thread_lock": threading.Lock(),
    "active": False
}

def set_progress_functions(
    current_operation: Dict[str, Any],
    update_progressive_step: Callable,
    complete_current_step: Callable
):
    """Set the progress tracking functions from main.py."""
    global _progress_state
    with _progress_state["thread_lock"]:
        _progress_state["current_operation"] = current_operation
        _progress_state["update_progressive_step"] = update_progressive_step
        _progress_state["complete_current_step"] = complete_current_step
        _progress_state["active"] = True

def get_progress_functions():
    """Get the progress tracking functions for use in conversation_handler.py."""
    global _progress_state
    with _progress_state["thread_lock"]:
        if _progress_state["active"]:
            return (
                _progress_state["update_progressive_step"],
                _progress_state["complete_current_step"]
            )
        return None, None

def clear_progress_functions():
    """Clear the progress functions when execution is complete."""
    global _progress_state
    with _progress_state["thread_lock"]:
        _progress_state["active"] = False
        _progress_state["current_operation"] = None
        _progress_state["update_progressive_step"] = None
        _progress_state["complete_current_step"] = None