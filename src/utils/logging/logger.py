"""Simplified Unified Logging System for Multi-Agent Orchestrator.

This module provides a single, simple logging interface for the entire system.
Following 2024 best practices: centralized logging, JSON format, correlation IDs.

Key features:
- Single log file with rotation
- JSON structured logging
- Correlation ID support for request tracing
- Performance tracking via context managers
- Simple cost tracking
- Thread-safe operation
"""

import json
import logging
import logging.handlers
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from threading import local
from typing import Any, Dict, Optional

# Thread-local storage for correlation IDs
_thread_local = local()

class StructuredLogger:
    """Unified logger for all components with built-in correlation and performance tracking."""
    
    def __init__(self, log_file: str = "logs/system.log", level: int = logging.INFO):
        """Initialize the unified logger.
        
        Args:
            log_file: Path to log file (will create directory if needed)
            level: Logging level (default: INFO)
        """
        self.logger = logging.getLogger("multi_agent_orchestrator")
        self.logger.setLevel(level)
        
        # Remove any existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Create log directory if needed
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Single rotating file handler
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=50*1024*1024,  # 50MB per file
            backupCount=5,
            encoding='utf-8'
        )
        
        # Use a simple formatter - we'll add JSON in the log method
        handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(handler)
        
        # Prevent propagation to avoid duplicate console output
        self.logger.propagate = False
        
        # Cost tracking state (simple session totals)
        self.session_tokens = 0
        self.session_cost = 0.0
    
    def _get_correlation_id(self) -> Optional[str]:
        """Get current correlation ID from thread-local storage."""
        return getattr(_thread_local, 'correlation_id', None)
    
    def set_correlation_id(self, correlation_id: Optional[str] = None) -> str:
        """Set correlation ID for current thread/request.
        
        Args:
            correlation_id: ID to use, or None to generate new one
            
        Returns:
            The correlation ID that was set
        """
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())
        _thread_local.correlation_id = correlation_id
        return correlation_id
    
    def clear_correlation_id(self):
        """Clear correlation ID for current thread."""
        if hasattr(_thread_local, 'correlation_id'):
            delattr(_thread_local, 'correlation_id')
    
    def _log(self, level: int, message: str, **kwargs):
        """Internal logging method with JSON formatting."""
        # Build log entry
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": logging.getLevelName(level),
            "message": message,
            **kwargs
        }
        
        # Add correlation ID if available
        correlation_id = self._get_correlation_id()
        if correlation_id:
            entry["correlation_id"] = correlation_id
        
        # Log as JSON
        self.logger.log(level, json.dumps(entry, default=str))
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message."""
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self._log(logging.CRITICAL, message, **kwargs)
    
    @contextmanager
    def track_performance(self, operation: str, **context):
        """Context manager for tracking operation performance.
        
        Usage:
            with logger.track_performance("database_query", query="SELECT *"):
                # Do operation
                pass
        """
        start_time = time.time()
        
        # Log operation start
        self.info(f"{operation}_started", operation=operation, **context)
        
        try:
            yield
        finally:
            # Calculate duration
            duration = time.time() - start_time
            
            # Log operation completion with duration
            self.info(
                f"{operation}_completed",
                operation=operation,
                duration_seconds=round(duration, 3),
                **context
            )
    
    def track_cost(self, operation: str, tokens: int, model: str = "gpt-4o-mini", **context):
        """Track LLM token usage and cost.
        
        Args:
            operation: Operation name
            tokens: Total tokens used
            model: Model name for pricing lookup
            **context: Additional context to log
        """
        # Simple pricing lookup (can be extended)
        pricing_per_1k = {
            "gpt-4": 0.03,
            "gpt-4o": 0.005,
            "gpt-4o-mini": 0.00015,
            "gpt-3.5-turbo": 0.0005
        }
        
        # Get price or use default
        price_per_1k = pricing_per_1k.get(model, 0.001)
        cost = (tokens / 1000) * price_per_1k
        
        # Update session totals
        self.session_tokens += tokens
        self.session_cost += cost
        
        # Log cost tracking
        self.info(
            "token_usage",
            operation=operation,
            model=model,
            tokens=tokens,
            cost=round(cost, 4),
            session_tokens=self.session_tokens,
            session_cost=round(self.session_cost, 4),
            **context
        )
    
    def log_tool_call(self, tool_name: str, operation: str, **kwargs):
        """Log tool usage (backward compatible)."""
        self.info(f"tool_{operation}", tool=tool_name, operation=operation, **kwargs)
    
    def log_agent_activity(self, agent: str, operation: str, **kwargs):
        """Log agent activity (backward compatible)."""
        self.info(f"agent_{operation}", agent=agent, operation=operation, **kwargs)


# Global logger instance
_logger = None

def get_logger(component: Optional[str] = None) -> StructuredLogger:
    """Get the global logger instance (singleton).
    
    Args:
        component: Component name (ignored - kept for backward compatibility)
        
    Returns:
        The global StructuredLogger instance
    """
    global _logger
    if _logger is None:
        _logger = StructuredLogger()
    return _logger


# Backward compatibility functions
def log_tool_activity(tool_name: str, operation: str, **kwargs):
    """Legacy function for tool activity logging."""
    get_logger().log_tool_call(tool_name, operation, **kwargs)


def log_orchestrator_activity(operation: str, **kwargs):
    """Legacy function for orchestrator logging."""
    get_logger().log_agent_activity("orchestrator", operation, **kwargs)


def log_salesforce_activity(operation: str, **kwargs):
    """Legacy function for Salesforce agent logging."""
    get_logger().log_agent_activity("salesforce_agent", operation, **kwargs)


def log_a2a_activity(operation: str, **kwargs):
    """Legacy function for A2A protocol logging."""
    get_logger().log_agent_activity("a2a_protocol", operation, **kwargs)


def log_cost_activity(operation: str, tokens_used: int, model: Optional[str] = None, **kwargs):
    """Legacy function for cost tracking."""
    get_logger().track_cost(operation, tokens_used, model or "gpt-4o-mini", **kwargs)


def log_performance_activity(operation: str, **kwargs):
    """Legacy function for performance logging."""
    get_logger().info(f"performance_{operation}", operation=operation, **kwargs)