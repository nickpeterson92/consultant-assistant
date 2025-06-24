"""
Error Details Logger

Provides centralized error logging with full context and stack traces
to help debug issues across the multi-agent system.
"""

import logging
import json
import time
import traceback
from typing import Any, Dict, Optional
from pathlib import Path

# Create logs directory if it doesn't exist
logs_dir = Path("logs/debug")
logs_dir.mkdir(parents=True, exist_ok=True)

class ErrorDetailsLogger:
    """Dedicated logger for detailed error tracking"""
    
    def __init__(self, log_file: str = "logs/debug/error_details.log"):
        self.logger = logging.getLogger("error_details")
        self.logger.setLevel(logging.ERROR)
        self.logger.propagate = False
        
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
        
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def log_error(self, component: str, operation: str, error: Exception, 
                  context: Dict[str, Any] = None, user_id: str = None,
                  thread_id: str = None, task_id: str = None):
        """Log detailed error information with full context"""
        
        # Get stack trace
        tb_str = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        
        log_data = {
            "timestamp": time.time(),
            "component": component,
            "operation": operation,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "stack_trace": tb_str,
            "user_id": user_id,
            "thread_id": thread_id,
            "task_id": task_id,
            "context": context or {}
        }
        
        self.logger.error(json.dumps(log_data))
    
    def log_warning(self, component: str, operation: str, message: str,
                   context: Dict[str, Any] = None, user_id: str = None,
                   thread_id: str = None):
        """Log warning with context"""
        
        log_data = {
            "timestamp": time.time(),
            "level": "WARNING",
            "component": component,
            "operation": operation,
            "message": message,
            "user_id": user_id,
            "thread_id": thread_id,
            "context": context or {}
        }
        
        # Use error level to ensure it gets logged
        self.logger.error(json.dumps(log_data))
    
    def log_recovery(self, component: str, operation: str, error_type: str,
                    recovery_action: str, success: bool, duration: float = None):
        """Log error recovery attempts and outcomes"""
        
        log_data = {
            "timestamp": time.time(),
            "level": "RECOVERY",
            "component": component,
            "operation": operation,
            "error_type": error_type,
            "recovery_action": recovery_action,
            "recovery_success": success,
            "recovery_duration": duration
        }
        
        self.logger.error(json.dumps(log_data))

# Global logger instance
_error_logger = None

def get_error_logger() -> ErrorDetailsLogger:
    """Get the global error logger instance"""
    global _error_logger
    if _error_logger is None:
        _error_logger = ErrorDetailsLogger()
    return _error_logger

# Convenience functions
def log_error(component: str, operation: str, error: Exception, **kwargs):
    """Log an error with full details"""
    get_error_logger().log_error(component, operation, error, **kwargs)

def log_warning(component: str, operation: str, message: str, **kwargs):
    """Log a warning with context"""
    get_error_logger().log_warning(component, operation, message, **kwargs)

def log_recovery(component: str, operation: str, error_type: str, 
                recovery_action: str, success: bool, **kwargs):
    """Log recovery attempt"""
    get_error_logger().log_recovery(component, operation, error_type, 
                                   recovery_action, success, **kwargs)