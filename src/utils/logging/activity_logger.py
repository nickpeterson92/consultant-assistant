"""
Centralized Activity Logging System for Multi-Agent Architecture

This module provides backward-compatible convenience functions that delegate to the
unified StructuredLogger implementation. All logging now goes through the standard
Python logging framework with proper rotation, levels, and structured JSON output.

Key changes in the unified architecture:
1. Single implementation using StructuredLogger for all components
2. Proper log rotation and size management
3. Standard Python logging levels (DEBUG, INFO, WARNING, ERROR)
4. Consistent JSON structure across all log entries
5. Cost tracking unified through CostTracker class

For new code, prefer using get_logger() directly:
    from src.utils.logging import get_logger
    logger = get_logger('component_name')
    logger.info('operation', key='value')
"""

from typing import Any
from .logging_config import get_logger, get_cost_tracker


# Backward-compatible convenience functions that delegate to StructuredLogger
def log_orchestrator_activity(operation_type: str, **data: Any) -> None:
    """Log orchestrator-specific activity"""
    logger = get_logger("orchestrator")
    # Use operation_type as the message, and pass other data as structured fields
    logger.info(operation_type, operation_type=operation_type, **data)


def log_salesforce_activity(operation_type: str, **data: Any) -> None:
    """Log Salesforce agent activity"""
    logger = get_logger("salesforce_agent")
    logger.info(operation_type, operation_type=operation_type, **data)


def log_a2a_activity(operation_type: str, **data: Any) -> None:
    """Log A2A protocol activity"""
    logger = get_logger("a2a_protocol")
    logger.info(operation_type, operation_type=operation_type, **data)


def log_tool_activity(tool_name: str, operation: str, **data: Any) -> None:
    """Log tool usage activity"""
    logger = get_logger("tools")
    logger.info(operation, operation=operation, tool=tool_name, **data)


def log_cost_activity(operation: str, tokens_used: int, model: str = None, **data: Any) -> None:
    """Log cost tracking activity using unified logging.
    
    This maintains backward compatibility by accepting a single token count
    and using the configured pricing. For accurate cost tracking with
    separate input/output counts, use get_cost_tracker() directly.
    
    The pricing comes from the config hierarchy:
    1. Environment variables (if set)
    2. system_config.json llm.pricing section
    3. constants.py MODEL_PRICING defaults
    """
    from ..config import get_llm_config
    
    # Get model and pricing from unified config
    llm_config = get_llm_config()
    model_name = model or llm_config.model
    pricing = llm_config.get_pricing(model_name)
    
    # Calculate cost using average pricing for backward compatibility
    cost_per_1k = pricing.average_per_1k
    estimated_cost = f"${(tokens_used * cost_per_1k / 1000):.4f}"
    
    # Log via unified logger (not CostTracker to maintain exact compatibility)
    logger = get_logger("cost_tracking")
    logger.info("LLM_USAGE",
                operation=operation,
                model=model_name,
                tokens_used=tokens_used,
                estimated_cost=estimated_cost,
                **data)


def log_performance_activity(operation_type: str, **data: Any) -> None:
    """Log performance tracking activity"""
    logger = get_logger("performance")
    logger.info(operation_type, operation_type=operation_type, **data)