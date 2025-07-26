"""Thread context manager for passing thread_id to tools."""

import contextvars
from typing import Optional, Dict, Any

# Context variable to store thread context
_thread_context: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar('thread_context', default={})


def set_thread_context(thread_id: str, user_id: str, task_id: Optional[str] = None) -> None:
    """Set thread context for the current execution.
    
    Args:
        thread_id: Thread ID for the current execution
        user_id: User ID for the current execution
        task_id: Optional task ID for the current execution
    """
    context = {
        'thread_id': thread_id,
        'user_id': user_id,
        'task_id': task_id
    }
    _thread_context.set(context)


def get_thread_context() -> Dict[str, Any]:
    """Get the current thread context.
    
    Returns:
        Dictionary containing thread_id, user_id, and task_id
    """
    return _thread_context.get()


def get_thread_id() -> Optional[str]:
    """Get the current thread ID.
    
    Returns:
        Thread ID or None if not set
    """
    context = _thread_context.get()
    return context.get('thread_id')


def get_user_id() -> Optional[str]:
    """Get the current user ID.
    
    Returns:
        User ID or None if not set
    """
    context = _thread_context.get()
    return context.get('user_id')


def clear_thread_context() -> None:
    """Clear the thread context."""
    _thread_context.set({})