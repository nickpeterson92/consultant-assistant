"""Advanced logging framework for the multi-agent orchestrator system."""

# Legacy logging functions (kept for backward compatibility)
from .logger import (
    get_logger,
    log_orchestrator_activity,
    log_cost_activity,
    log_salesforce_activity,
    log_a2a_activity,
    log_performance_activity,
    log_tool_activity
)

# Advanced logging framework
from .framework import (
    logger,  # Global smart logger
    log_execution,  # Decorator for function logging
    log_operation,  # Context manager for scoped operations
    get_smart_logger,  # Factory for smart loggers
    LoggedTool,  # Base class for tools
    LoggedAgent,  # Base class for agents
)

# Import multi-file logging migration
from .multi_file_logger import migrate_to_multi_file_logging

# Automatically migrate to multi-file logging on import
migrate_to_multi_file_logging()

# For modules that use the old imports
from .logger import get_logger as get_performance_tracker
from .logger import get_logger as get_cost_tracker

__all__ = [
    # Legacy functions
    "log_orchestrator_activity",
    "log_cost_activity",
    "log_salesforce_activity", 
    "log_a2a_activity",
    "log_performance_activity",
    "log_tool_activity",
    "get_logger",
    "get_performance_tracker",
    "get_cost_tracker",
    
    # Advanced framework
    "logger",  # Most commonly used - global smart logger
    "log_execution",
    "log_operation", 
    "get_smart_logger",
    "LoggedTool",
    "LoggedAgent",
]