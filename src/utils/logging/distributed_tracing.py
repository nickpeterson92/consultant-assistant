"""
Distributed Tracing for Multi-Agent System
Provides correlation IDs and request tracing across all agent interactions
"""

import asyncio
import time
import uuid
import logging
from typing import Dict, Any, Optional, List, Callable, ContextManager
from contextvars import ContextVar
from dataclasses import dataclass, asdict
from datetime import datetime
from contextlib import asynccontextmanager, contextmanager
import functools
import weakref

logger = logging.getLogger(__name__)

# Context variables for distributed tracing
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
trace_id: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)
span_id: ContextVar[Optional[str]] = ContextVar('span_id', default=None)
parent_span_id: ContextVar[Optional[str]] = ContextVar('parent_span_id', default=None)

@dataclass
class Span:
    """Distributed tracing span"""
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    correlation_id: str
    operation_name: str
    component: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str = "started"  # started, success, error
    tags: Dict[str, Any] = None
    logs: List[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}
        if self.logs is None:
            self.logs = []
    
    def finish(self, status: str = "success", error: Optional[str] = None):
        """Finish the span"""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.status = status
        self.error = error
    
    def add_tag(self, key: str, value: Any):
        """Add a tag to the span"""
        self.tags[key] = value
    
    def add_log(self, message: str, level: str = "INFO", **fields):
        """Add a log entry to the span"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            **fields
        }
        self.logs.append(log_entry)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary"""
        return asdict(self)

class TraceContext:
    """Context manager for distributed tracing"""
    
    def __init__(self, operation_name: str, component: str, 
                 correlation_id: Optional[str] = None,
                 trace_id: Optional[str] = None,
                 parent_span_id: Optional[str] = None,
                 auto_finish: bool = True):
        self.operation_name = operation_name
        self.component = component
        self.auto_finish = auto_finish
        
        # Use existing IDs or generate new ones
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.trace_id = trace_id or str(uuid.uuid4())
        self.span_id = str(uuid.uuid4())
        self.parent_span_id = parent_span_id
        
        self.span = Span(
            span_id=self.span_id,
            trace_id=self.trace_id,
            parent_span_id=self.parent_span_id,
            correlation_id=self.correlation_id,
            operation_name=operation_name,
            component=component,
            start_time=time.time()
        )
        
        # Store previous context values
        self._prev_correlation_id = None
        self._prev_trace_id = None
        self._prev_span_id = None
        self._prev_parent_span_id = None
    
    def __enter__(self):
        # Store previous values
        self._prev_correlation_id = correlation_id.get()
        self._prev_trace_id = trace_id.get()
        self._prev_span_id = span_id.get()
        self._prev_parent_span_id = parent_span_id.get()
        
        # Set new values
        correlation_id.set(self.correlation_id)
        trace_id.set(self.trace_id)
        span_id.set(self.span_id)
        parent_span_id.set(self.parent_span_id)
        
        # Register span with tracer
        tracer = get_tracer()
        tracer.start_span(self.span)
        
        return self.span
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Finish span
        if self.auto_finish:
            if exc_type is not None:
                self.span.finish(status="error", error=str(exc_val))
            else:
                self.span.finish(status="success")
        
        # Register span completion with tracer
        tracer = get_tracer()
        tracer.finish_span(self.span)
        
        # Restore previous values
        correlation_id.set(self._prev_correlation_id)
        trace_id.set(self._prev_trace_id)
        span_id.set(self._prev_span_id)
        parent_span_id.set(self._prev_parent_span_id)

class AsyncTraceContext:
    """Async context manager for distributed tracing"""
    
    def __init__(self, operation_name: str, component: str, 
                 correlation_id: Optional[str] = None,
                 trace_id: Optional[str] = None,
                 parent_span_id: Optional[str] = None,
                 auto_finish: bool = True):
        self.sync_context = TraceContext(
            operation_name, component, correlation_id, 
            trace_id, parent_span_id, auto_finish
        )
    
    async def __aenter__(self):
        return self.sync_context.__enter__()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.sync_context.__exit__(exc_type, exc_val, exc_tb)

class DistributedTracer:
    """Distributed tracer for multi-agent system"""
    
    def __init__(self, max_spans: int = 10000):
        self.max_spans = max_spans
        self._active_spans: Dict[str, Span] = {}
        self._completed_spans: List[Span] = []
        self._lock = asyncio.Lock()
        
        # Statistics
        self.total_spans = 0
        self.active_traces = 0
        self._trace_counts: Dict[str, int] = {}
    
    def start_span(self, span: Span):
        """Register a started span"""
        self._active_spans[span.span_id] = span
        self.total_spans += 1
        
        # Track active traces
        if span.trace_id not in self._trace_counts:
            self._trace_counts[span.trace_id] = 0
            self.active_traces += 1
        self._trace_counts[span.trace_id] += 1
        
        logger.debug(f"Started span: {span.operation_name} ({span.span_id[:8]}...)")
    
    def finish_span(self, span: Span):
        """Register a finished span"""
        if span.span_id in self._active_spans:
            del self._active_spans[span.span_id]
        
        # Add to completed spans (with size limit)
        self._completed_spans.append(span)
        if len(self._completed_spans) > self.max_spans:
            self._completed_spans.pop(0)
        
        # Update trace counts
        if span.trace_id in self._trace_counts:
            self._trace_counts[span.trace_id] -= 1
            if self._trace_counts[span.trace_id] <= 0:
                del self._trace_counts[span.trace_id]
                self.active_traces -= 1
        
        logger.debug(f"Finished span: {span.operation_name} ({span.duration_ms:.2f}ms)")
    
    def get_active_spans(self) -> List[Span]:
        """Get all active spans"""
        return list(self._active_spans.values())
    
    def get_completed_spans(self, limit: int = 100) -> List[Span]:
        """Get recently completed spans"""
        return self._completed_spans[-limit:]
    
    def get_trace_spans(self, trace_id: str) -> List[Span]:
        """Get all spans for a specific trace"""
        spans = []
        
        # Check active spans
        for span in self._active_spans.values():
            if span.trace_id == trace_id:
                spans.append(span)
        
        # Check completed spans
        for span in self._completed_spans:
            if span.trace_id == trace_id:
                spans.append(span)
        
        # Sort by start time
        spans.sort(key=lambda s: s.start_time)
        return spans
    
    def get_correlation_spans(self, correlation_id: str) -> List[Span]:
        """Get all spans for a specific correlation ID"""
        spans = []
        
        # Check active spans
        for span in self._active_spans.values():
            if span.correlation_id == correlation_id:
                spans.append(span)
        
        # Check completed spans
        for span in self._completed_spans:
            if span.correlation_id == correlation_id:
                spans.append(span)
        
        # Sort by start time
        spans.sort(key=lambda s: s.start_time)
        return spans
    
    def get_stats(self) -> Dict[str, Any]:
        """Get tracer statistics"""
        return {
            "total_spans": self.total_spans,
            "active_spans": len(self._active_spans),
            "completed_spans": len(self._completed_spans),
            "active_traces": self.active_traces,
            "max_spans": self.max_spans
        }
    
    def clear_completed_spans(self) -> int:
        """Clear completed spans and return count"""
        count = len(self._completed_spans)
        self._completed_spans.clear()
        return count

# Global tracer instance
_tracer: Optional[DistributedTracer] = None

def get_tracer() -> DistributedTracer:
    """Get the global distributed tracer"""
    global _tracer
    if _tracer is None:
        _tracer = DistributedTracer()
    return _tracer

def get_current_correlation_id() -> Optional[str]:
    """Get the current correlation ID"""
    return correlation_id.get()

def get_current_trace_id() -> Optional[str]:
    """Get the current trace ID"""
    return trace_id.get()

def get_current_span_id() -> Optional[str]:
    """Get the current span ID"""
    return span_id.get()

def create_child_context(operation_name: str, component: str) -> Dict[str, str]:
    """Create context for child operations"""
    return {
        "correlation_id": correlation_id.get() or str(uuid.uuid4()),
        "trace_id": trace_id.get() or str(uuid.uuid4()),
        "parent_span_id": span_id.get()
    }

@contextmanager
def trace_operation(operation_name: str, component: str, **tags):
    """Context manager for tracing an operation"""
    with TraceContext(operation_name, component) as span:
        # Add tags
        for key, value in tags.items():
            span.add_tag(key, value)
        yield span

@asynccontextmanager
async def trace_async_operation(operation_name: str, component: str, **tags):
    """Async context manager for tracing an operation"""
    async with AsyncTraceContext(operation_name, component) as span:
        # Add tags
        for key, value in tags.items():
            span.add_tag(key, value)
        yield span

def trace_function(operation_name: Optional[str] = None, component: str = "unknown"):
    """Decorator for tracing function calls"""
    def decorator(func: Callable):
        op_name = operation_name or func.__name__
        
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                async with trace_async_operation(op_name, component) as span:
                    span.add_tag("function", func.__name__)
                    span.add_tag("args_count", len(args))
                    span.add_tag("kwargs_count", len(kwargs))
                    try:
                        result = await func(*args, **kwargs)
                        span.add_tag("success", True)
                        return result
                    except Exception as e:
                        span.add_tag("success", False)
                        span.add_tag("error_type", type(e).__name__)
                        raise
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                with trace_operation(op_name, component) as span:
                    span.add_tag("function", func.__name__)
                    span.add_tag("args_count", len(args))
                    span.add_tag("kwargs_count", len(kwargs))
                    try:
                        result = func(*args, **kwargs)
                        span.add_tag("success", True)
                        return result
                    except Exception as e:
                        span.add_tag("success", False)
                        span.add_tag("error_type", type(e).__name__)
                        raise
            return sync_wrapper
    return decorator

def inject_trace_headers() -> Dict[str, str]:
    """Inject trace headers for HTTP requests"""
    headers = {}
    
    if corr_id := correlation_id.get():
        headers["X-Correlation-ID"] = corr_id
    
    if t_id := trace_id.get():
        headers["X-Trace-ID"] = t_id
    
    if s_id := span_id.get():
        headers["X-Parent-Span-ID"] = s_id
    
    return headers

def extract_trace_headers(headers: Dict[str, str]) -> Dict[str, Optional[str]]:
    """Extract trace headers from HTTP request"""
    return {
        "correlation_id": headers.get("X-Correlation-ID") or headers.get("x-correlation-id"),
        "trace_id": headers.get("X-Trace-ID") or headers.get("x-trace-id"),
        "parent_span_id": headers.get("X-Parent-Span-ID") or headers.get("x-parent-span-id")
    }