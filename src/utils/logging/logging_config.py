"""
Comprehensive External Logging Configuration
Provides structured logging for all system components with external file outputs
"""

import logging
import logging.handlers
import os
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

# Create logs directory at project root
LOG_DIR = Path(__file__).parent.parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

class StructuredLogger:
    """Enhanced logger with structured data and external file output"""
    
    def __init__(self, name: str, log_file: str, level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Prevent duplicate handlers
        if self.logger.handlers:
            return
            
        # Create formatter for structured logging
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # File handler with rotation (external logging only)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        
        # Only add file handler - no console output for external logs
        self.logger.addHandler(file_handler)
        
        # Prevent propagation to root logger to avoid console output
        self.logger.propagate = False
        
        # Force immediate flushing for real-time logging
        for handler in self.logger.handlers:
            if hasattr(handler, 'flush'):
                handler.flush()
    
    def log_structured(self, level: int, message: str, **kwargs):
        """Log with structured data"""
        structured_data = {
            'timestamp': datetime.now().isoformat(),
            'message': message,
            **kwargs
        }
        self.logger.log(level, json.dumps(structured_data, default=str))
        
        # Force flush after each log entry for real-time logging
        for handler in self.logger.handlers:
            if hasattr(handler, 'flush'):
                handler.flush()
    
    def info(self, message: str, **kwargs):
        self.log_structured(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self.log_structured(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self.log_structured(logging.ERROR, message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        self.log_structured(logging.DEBUG, message, **kwargs)

class PerformanceTracker:
    """Track and log performance metrics"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
        self.start_times = {}
    
    def start_operation(self, operation_id: str, operation_type: str, **context):
        """Start tracking an operation"""
        self.start_times[operation_id] = time.time()
        self.logger.info(f"PERF_START: {operation_type}", 
                        operation_id=operation_id,
                        operation_type=operation_type,
                        **context)
    
    def end_operation(self, operation_id: str, success: bool = True, **results):
        """End tracking an operation"""
        if operation_id in self.start_times:
            duration = time.time() - self.start_times[operation_id]
            del self.start_times[operation_id]
            
            self.logger.info(f"PERF_END: {operation_id}",
                           operation_id=operation_id,
                           duration_seconds=duration,
                           success=success,
                           **results)
            return duration
        return None

class CostTracker:
    """Track token usage and costs"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
        self.session_tokens = 0
        self.session_cost = 0.0
    
    def log_token_usage(self, operation: str, input_tokens: int, output_tokens: int, 
                       model: str = None, **context):
        """Log token usage for cost tracking using global configuration"""
        from ..config import get_llm_config
        
        # Get pricing from global config
        llm_config = get_llm_config()
        model_name = model or llm_config.model
        pricing = llm_config.get_pricing(model_name)
        
        # Convert per 1K to per token
        cost_per_input_token = pricing.input_per_1k / 1000
        cost_per_output_token = pricing.output_per_1k / 1000
        
        operation_cost = (input_tokens * cost_per_input_token + 
                         output_tokens * cost_per_output_token)
        
        self.session_tokens += input_tokens + output_tokens
        self.session_cost += operation_cost
        
        self.logger.info(f"TOKEN_USAGE: {operation}",
                        operation=operation,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=input_tokens + output_tokens,
                        operation_cost=operation_cost,
                        session_total_tokens=self.session_tokens,
                        session_total_cost=self.session_cost,
                        model=model,
                        **context)

# Global logger instances
LOGGERS = {}

def get_logger(component: str) -> StructuredLogger:
    """Get or create a logger for a specific component"""
    
    if component in LOGGERS:
        return LOGGERS[component]
    
    log_level = logging.INFO
    
    # Component-specific log files
    log_files = {
        'orchestrator': 'orchestrator.log',
        'salesforce_agent': 'salesforce_agent.log', 
        'a2a_protocol': 'a2a_protocol.log',
        'cost_tracking': 'cost_tracking.log',
        'performance': 'performance.log',
        'multi_agent': 'multi_agent.log',
        'tools': 'tools.log'
    }
    
    log_file = log_files.get(component, f'{component}.log')
    
    # All log files go to logs/ directory
    log_path = LOG_DIR / log_file
    
    logger = StructuredLogger(component, str(log_path), log_level)
    LOGGERS[component] = logger
    
    return logger

def get_performance_tracker(component: str) -> PerformanceTracker:
    """Get performance tracker for a component"""
    logger = get_logger('performance')
    return PerformanceTracker(logger)

def get_cost_tracker() -> CostTracker:
    """Get cost tracker"""
    logger = get_logger('cost_tracking')
    return CostTracker(logger)

# Initialize session tracking
cost_tracker = None
perf_tracker = None

def init_session_tracking():
    """Initialize session-wide tracking"""
    global cost_tracker, perf_tracker
    cost_tracker = get_cost_tracker()
    perf_tracker = get_performance_tracker('session')
    
    # Log session start
    logger = get_logger('multi_agent')
    logger.info("SESSION_START: Multi-agent system initialized",
                timestamp=datetime.now().isoformat())