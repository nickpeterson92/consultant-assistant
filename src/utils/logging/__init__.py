"""Simplified logging utilities for the multi-agent orchestrator system."""

from .logger import (
    get_logger,
    log_orchestrator_activity,
    log_cost_activity,
    log_salesforce_activity,
    log_a2a_activity,
    log_performance_activity,
    log_tool_activity
)

# Import multi-file logging migration
from .multi_file_logger import migrate_to_multi_file_logging

# Automatically migrate to multi-file logging on import
migrate_to_multi_file_logging()

# For modules that use the old imports
from .logger import get_logger as get_performance_tracker
from .logger import get_logger as get_cost_tracker

__all__ = [
    "log_orchestrator_activity",
    "log_cost_activity",
    "log_salesforce_activity", 
    "log_a2a_activity",
    "log_performance_activity",
    "log_tool_activity",
    "get_logger",
    "get_performance_tracker",
    "get_cost_tracker"
]