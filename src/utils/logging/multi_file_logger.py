"""Multi-File Logging System for Better Traceability.

This module provides component-based log file separation for easier debugging
and monitoring. Each component gets its own log file, with an additional 
error log that captures all ERROR level messages across components.

Log Files:
- orchestrator.log: Main orchestrator operations
- salesforce.log: Salesforce agent and tool operations
- a2a_protocol.log: A2A/network communications
- storage.log: Database operations
- system.log: System-wide events (startup/shutdown)
- errors.log: All ERROR level messages (cross-component)
"""

import json
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from threading import Lock

from .logger import StructuredLogger, _thread_local


class MultiFileLogger(StructuredLogger):
    """Logger that routes messages to different files based on component."""
    
    # Component to log file mapping
    COMPONENT_FILES = {
        'orchestrator': 'orchestrator.log',
        'salesforce': 'salesforce.log',
        'a2a': 'a2a_protocol.log',
        'storage': 'storage.log',
        'system': 'system.log',
        'config': 'system.log',  # Config goes to system log
        'async_store_adapter_sync': 'storage.log',  # Storage alias
    }
    
    def __init__(self, log_dir: str = "logs", level: int = logging.INFO):
        """Initialize multi-file logger.
        
        Args:
            log_dir: Directory for log files
            level: Logging level (default: INFO)
        """
        # Don't call parent __init__ - we'll set up our own logger
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.level = level
        self.handlers: Dict[str, logging.Handler] = {}
        self.lock = Lock()
        
        # Create main logger (don't add any handlers to it)
        self.logger = logging.getLogger("multi_agent_orchestrator")
        self.logger.setLevel(level)
        self.logger.handlers.clear()
        self.logger.propagate = False
        
        # Cost tracking state
        self.session_tokens = 0
        self.session_cost = 0.0
        
        # Create handlers for each component
        self._setup_handlers()
        
        # Create error handler that captures all ERROR messages
        self._setup_error_handler()
    
    def _setup_handlers(self):
        """Create a handler for each component log file."""
        for component, filename in self.COMPONENT_FILES.items():
            handler = logging.handlers.RotatingFileHandler(
                self.log_dir / filename,
                maxBytes=50*1024*1024,  # 50MB per file
                backupCount=5,
                encoding='utf-8'
            )
            handler.setFormatter(logging.Formatter('%(message)s'))
            handler.setLevel(self.level)
            self.handlers[component] = handler
    
    def _setup_error_handler(self):
        """Create special handler for all ERROR level messages."""
        error_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / 'errors.log',
            maxBytes=50*1024*1024,  # 50MB
            backupCount=10,  # Keep more error logs
            encoding='utf-8'
        )
        error_handler.setFormatter(logging.Formatter('%(message)s'))
        error_handler.setLevel(logging.ERROR)
        self.handlers['_errors'] = error_handler
    
    def _get_handler(self, component: Optional[str]) -> logging.Handler:
        """Get the appropriate handler for a component."""
        if component and component in self.handlers:
            return self.handlers[component]
        
        # Check aliases
        if component and component in self.COMPONENT_FILES:
            mapped_component = self.COMPONENT_FILES[component]
            for comp, filename in self.COMPONENT_FILES.items():
                if filename == mapped_component and comp in self.handlers:
                    return self.handlers[comp]
        
        # Default to system log
        return self.handlers.get('system', self.handlers['orchestrator'])
    
    def _log(self, level: int, message: str, **kwargs):
        """Internal logging method that routes to appropriate file."""
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
        
        # Get component from kwargs
        component = kwargs.get('component', None)
        
        # Format as JSON
        log_message = json.dumps(entry, default=str)
        
        # Create a LogRecord
        record = logging.LogRecord(
            name=self.logger.name,
            level=level,
            pathname="",
            lineno=0,
            msg=log_message,
            args=(),
            exc_info=None
        )
        
        with self.lock:
            # Route to component-specific handler
            handler = self._get_handler(component)
            if handler and level >= handler.level:
                handler.emit(record)
            
            # Also send ERROR and above to error log
            if level >= logging.ERROR:
                error_handler = self.handlers.get('_errors')
                if error_handler:
                    error_handler.emit(record)


# Global multi-file logger instance
_multi_logger = None
_multi_logger_lock = Lock()


def get_multi_file_logger() -> MultiFileLogger:
    """Get the global multi-file logger instance (singleton).
    
    Returns:
        The global MultiFileLogger instance
    """
    global _multi_logger
    if _multi_logger is None:
        with _multi_logger_lock:
            if _multi_logger is None:
                _multi_logger = MultiFileLogger()
    return _multi_logger


def migrate_to_multi_file_logging():
    """Replace the single-file logger with multi-file logger.
    
    This function updates the global logger instance to use multi-file logging.
    """
    import src.utils.logging.logger as logger_module
    
    # Replace the global logger with multi-file logger
    logger_module._logger = get_multi_file_logger()
    
    # Log migration
    logger = get_multi_file_logger()
    logger.info("logging_migrated_to_multi_file", 
                component="system",
                operation="migrate_logging",
                components=list(MultiFileLogger.COMPONENT_FILES.keys()))