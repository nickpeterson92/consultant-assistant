"""Advanced logging framework with decorators, context managers, and auto-detection.

This framework provides clean, powerful logging while keeping extensive detail:
- Decorators for automatic function/method logging
- Context managers for scoped operations 
- Auto component detection from module paths
- Event emission system for structured events
- Zero code clutter while maintaining rich logging detail
"""

import functools
import inspect
import time
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Optional, Callable, Union
import threading

from .multi_file_logger import get_multi_file_logger

# Thread-local storage for context
_local = threading.local()


def _get_component_from_module(module_name: str) -> str:
    """Auto-detect component from module path."""
    parts = module_name.split('.')
    
    # Map common patterns
    component_map = {
        'orchestrator': 'orchestrator',
        'agents.salesforce': 'salesforce',
        'agents.jira': 'jira', 
        'agents.servicenow': 'servicenow',
        'agents.workflow': 'workflow',
        'tools.salesforce': 'salesforce',
        'tools.jira': 'jira',
        'tools.servicenow': 'servicenow',
        'tools.utility': 'utility',
        'a2a': 'a2a',
        'utils.storage': 'storage',
        'utils.config': 'system',
        'utils.llm': 'system',
        'extraction': 'extraction',
        'client': 'client'
    }
    
    # Try exact matches first
    for pattern, component in component_map.items():
        if pattern in module_name:
            return component
    
    # Default fallback
    if 'agents' in parts:
        return parts[parts.index('agents') + 1] if len(parts) > parts.index('agents') + 1 else 'agent'
    elif 'tools' in parts:
        return parts[parts.index('tools') + 1] if len(parts) > parts.index('tools') + 1 else 'tool'
    
    return 'system'


def _get_correlation_id() -> Optional[str]:
    """Get current correlation ID from context."""
    return getattr(_local, 'correlation_id', None)


def _set_correlation_id(correlation_id: str):
    """Set correlation ID for current context."""
    _local.correlation_id = correlation_id


def _get_operation_context() -> Dict[str, Any]:
    """Get current operation context."""
    return getattr(_local, 'operation_context', {})


def _update_operation_context(context: Dict[str, Any]):
    """Update operation context."""
    current = getattr(_local, 'operation_context', {})
    current.update(context)
    _local.operation_context = current


class SmartLogger:
    """Smart logger that auto-detects component and provides rich functionality."""
    
    def __init__(self, component: Optional[str] = None, auto_detect: bool = True):
        """Initialize smart logger.
        
        Args:
            component: Explicit component name
            auto_detect: Whether to auto-detect component from caller
        """
        self._logger = get_multi_file_logger()
        
        if component:
            self._component = component
        elif auto_detect:
            # Auto-detect from caller's module
            frame = inspect.currentframe()
            try:
                caller_frame = frame.f_back
                module_name = caller_frame.f_globals.get('__name__', 'unknown')
                self._component = _get_component_from_module(module_name)
            finally:
                del frame
        else:
            self._component = 'system'
    
    def _log(self, level: str, message: str, **kwargs):
        """Internal logging with automatic context injection."""
        # Auto-inject component
        kwargs.setdefault('component', self._component)
        
        # Auto-inject correlation ID if available
        correlation_id = _get_correlation_id()
        if correlation_id:
            kwargs['correlation_id'] = correlation_id
        
        # Auto-inject operation context
        context = _get_operation_context()
        kwargs.update(context)
        
        # Call the appropriate log level
        getattr(self._logger, level.lower())(message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message with auto-context."""
        self._log('info', message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with auto-context."""
        self._log('error', message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with auto-context."""
        self._log('warning', message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with auto-context."""
        self._log('debug', message, **kwargs)
    
    def isEnabledFor(self, level: int) -> bool:
        """Check if logger is enabled for given level.
        
        Args:
            level: Logging level (10=DEBUG, 20=INFO, 30=WARNING, 40=ERROR)
            
        Returns:
            bool: True if logging is enabled for this level
        """
        # Check the underlying logger's effective level
        return self._logger.isEnabledFor(level)
    


# Global smart logger instance
logger = SmartLogger()


def log_execution(func_or_component: Union[Callable, str, None] = None, operation: Optional[str] = None, 
                 include_args: bool = True, include_result: bool = True,
                 log_errors: bool = True, component: Optional[str] = None):
    """Decorator for automatic function/method execution logging.
    
    Args:
        func_or_component: Function (when used as @log_execution) or component name
        operation: Operation name (defaults to function name)
        include_args: Whether to log function arguments
        include_result: Whether to log return value
        log_errors: Whether to log exceptions
        component: Component name (backward compatibility)
    
    Example:
        @log_execution  # Auto-detect component
        @log_execution("salesforce", "search_accounts")  # With parameters
        @log_execution(component="salesforce", operation="search")  # Keyword args
        def search_accounts(self, query: str):
            return self.sf.query(query)
    """
    # Handle both @log_execution and @log_execution() syntaxes
    if callable(func_or_component):
        # Called as @log_execution (without parentheses)
        func = func_or_component
        actual_component = component
        return _create_wrapper(func, actual_component, operation, include_args, include_result, log_errors)
    else:
        # Called as @log_execution(...) (with parentheses)
        # func_or_component could be a string (component name) or None
        actual_component = func_or_component or component
        def decorator(func: Callable) -> Callable:
            return _create_wrapper(func, actual_component, operation, include_args, include_result, log_errors)
        return decorator


def _create_wrapper(func: Callable, component: Optional[str], operation: Optional[str], 
                   include_args: bool, include_result: bool, log_errors: bool) -> Callable:
    """Create the actual wrapper function for logging."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Auto-detect component if not provided
        func_component = component
        if not func_component:
            module_name = func.__module__
            func_component = _get_component_from_module(module_name)
        
        # Get operation name
        op_name = operation or func.__name__
        
        # Create logger for this component
        func_logger = SmartLogger(func_component)
        
        # Generate execution ID
        exec_id = str(uuid.uuid4())[:8]
        
        # Prepare arguments for logging
        log_args = {}
        if include_args and args:
            # Skip 'self' for methods
            start_idx = 1 if args and hasattr(args[0], func.__name__) else 0
            log_args['args'] = args[start_idx:]
        if include_args and kwargs:
            log_args['kwargs'] = kwargs
        
        # Log function start
        func_logger.info(f"function_start_{op_name}",
                       operation=op_name,
                       function=func.__name__,
                       execution_id=exec_id,
                       **log_args)
        
        start_time = time.time()
        
        try:
            # Execute function
            result = func(*args, **kwargs)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Prepare result for logging
            log_result = {}
            if include_result:
                # Be careful with large results
                result_str = str(result)
                if len(result_str) > 1000:
                    log_result['result_preview'] = result_str[:500] + '...'
                    log_result['result_size'] = len(result_str)
                else:
                    log_result['result'] = result
            
            # Log successful completion
            func_logger.info(f"function_complete_{op_name}",
                           operation=op_name,
                           function=func.__name__,
                           execution_id=exec_id,
                           duration_seconds=round(duration, 3),
                           success=True,
                           **log_result)
            
            return result
            
        except Exception as e:
            # Calculate duration
            duration = time.time() - start_time
            
            if log_errors:
                # Check if this is a GraphInterrupt (expected behavior)
                from langgraph.errors import GraphInterrupt
                if isinstance(e, GraphInterrupt):
                    # Log as INFO, not ERROR - this is expected behavior
                    func_logger.info(f"function_interrupt_{op_name}",
                                   operation=op_name,
                                   function=func.__name__,
                                   execution_id=exec_id,
                                   duration_seconds=round(duration, 3),
                                   interrupt_type="GraphInterrupt",
                                   interrupt_value=str(e.args[0]) if e.args else "")
                else:
                    # Log actual error
                    func_logger.error(f"function_error_{op_name}",
                                    operation=op_name,
                                    function=func.__name__,
                                    execution_id=exec_id,
                                    duration_seconds=round(duration, 3),
                                    success=False,
                                    error=str(e),
                                    error_type=type(e).__name__)
            
            # Re-raise the exception
            raise
    
    return wrapper


@contextmanager
def log_operation(component: Optional[str] = None, operation: str = "operation",
                 correlation_id: Optional[str] = None, **context):
    """Context manager for scoped operation logging with automatic correlation.
    
    Args:
        component: Component name (auto-detected if not provided)
        operation: Operation name
        correlation_id: Correlation ID (generated if not provided)
        **context: Additional context to include in all logs within scope
    
    Example:
        with log_operation("extraction", "plan_extraction", request=request):
            result = extractor.invoke(prompt)
            # All logs inside get correlation ID and context
    """
    # Auto-detect component if not provided
    if not component:
        frame = inspect.currentframe()
        try:
            caller_frame = frame.f_back
            module_name = caller_frame.f_globals.get('__name__', 'unknown')
            component = _get_component_from_module(module_name)
        finally:
            del frame
    
    # Generate correlation ID if not provided
    if not correlation_id:
        correlation_id = str(uuid.uuid4())[:8]
    
    # Create logger
    op_logger = SmartLogger(component)
    
    # Store previous context
    prev_correlation_id = _get_correlation_id()
    prev_context = _get_operation_context().copy()
    
    try:
        # Set new context
        _set_correlation_id(correlation_id)
        _update_operation_context({
            'operation': operation,
            **context
        })
        
        # Log operation start
        op_logger.info(f"operation_start_{operation}",
                      operation=operation,
                      correlation_id=correlation_id,
                      **context)
        
        start_time = time.time()
        
        yield correlation_id
        
        # Log successful completion
        duration = time.time() - start_time
        op_logger.info(f"operation_complete_{operation}",
                      operation=operation,
                      correlation_id=correlation_id,
                      duration_seconds=round(duration, 3),
                      success=True,
                      **context)
        
    except Exception as e:
        # Log error
        duration = time.time() - start_time
        op_logger.error(f"operation_error_{operation}",
                       operation=operation,
                       correlation_id=correlation_id,
                       duration_seconds=round(duration, 3),
                       success=False,
                       error=str(e),
                       error_type=type(e).__name__,
                       **context)
        raise
        
    finally:
        # Restore previous context
        if prev_correlation_id:
            _set_correlation_id(prev_correlation_id)
        else:
            _local.correlation_id = None
        
        _local.operation_context = prev_context


def get_smart_logger(component: Optional[str] = None) -> SmartLogger:
    """Get a smart logger instance with optional component override.
    
    Args:
        component: Component name (auto-detected if not provided)
        
    Returns:
        SmartLogger instance
    """
    return SmartLogger(component)


class LoggedTool:
    """Base class for tools with automatic logging."""
    
    def __init__(self, tool_name: str, component: Optional[str] = None):
        """Initialize logged tool.
        
        Args:
            tool_name: Name of the tool
            component: Component name (auto-detected if not provided)
        """
        self.tool_name = tool_name
        self.logger = SmartLogger(component)
    
    @log_execution(include_args=True, include_result=True)
    def run(self, **kwargs) -> Any:
        """Execute tool with automatic logging."""
        return self._execute(**kwargs)
    
    def _execute(self, **kwargs) -> Any:
        """Override this method with tool logic."""
        raise NotImplementedError("Subclasses must implement _execute method")
    
    def emit_event(self, event_type: str, **data):
        """Emit tool-specific event."""
        self.logger.info(event_type, tool_name=self.tool_name, **data)


class LoggedAgent:
    """Base class for agents with automatic logging."""
    
    def __init__(self, agent_name: str, component: Optional[str] = None):
        """Initialize logged agent.
        
        Args:
            agent_name: Name of the agent
            component: Component name (defaults to agent_name)
        """
        self.agent_name = agent_name
        self.logger = SmartLogger(component or agent_name)
    
    @log_execution(include_args=True, include_result=False)  # Results often too large
    def process_task(self, **kwargs) -> Any:
        """Process task with automatic logging."""
        return self._process(**kwargs)
    
    def _process(self, **kwargs) -> Any:
        """Override this method with agent logic."""
        raise NotImplementedError("Subclasses must implement _process method")
    
    def emit_event(self, event_type: str, **data):
        """Emit agent-specific event."""
        self.logger.info(event_type, agent_name=self.agent_name, **data)