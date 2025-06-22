# Logging and Observability Documentation

## Overview

The logging and observability system provides comprehensive visibility into the multi-agent system's behavior, performance, and health. It implements structured logging, distributed tracing, performance metrics, and cost tracking across all components. The system is designed for both development debugging and production monitoring.

## Architecture

### Logging Infrastructure

```
┌─────────────────────────────────────────────────────────────────┐
│                     Logging & Observability Stack               │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────┐   │
│  │   Component     │  │   Structured     │  │     File      │   │
│  │    Loggers      │─>│   Formatters     │─>│   Handlers    │   │
│  └─────────────────┘  └──────────────────┘  └───────────────┘   │
│           │                                           │         │
│           ▼                                           ▼         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Activity Loggers                     │    │
│  ├──────────────┬──────────────┬──────────────┬────────────┤    │
│  │ Orchestrator │  Salesforce  │     A2A      │  Memory    │    │
│  │   Logger     │    Logger    │   Logger     │  Logger    │    │
│  └──────────────┴──────────────┴──────────────┴────────────┘    │
│                              │                                  │
│  ┌───────────────────────────┴──────────────────────────────┐   │
│  │                  Specialized Trackers                    │   │
│  ├─────────────────────┬────────────────┬───────────────────┤   │
│  │ Performance Tracker │  Cost Tracker  │ Summary Logger    │   │
│  └─────────────────────┴────────────────┴───────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Log File Organization

```
logs/
├── orchestrator.log          # Main orchestrator operations
├── salesforce_agent.log      # Salesforce agent activities
├── a2a_protocol.log         # A2A communications
├── memory.log               # Memory system operations
├── performance.log          # Performance metrics
├── cost_tracking.log        # Token usage and costs
├── multi_agent.log          # Cross-agent coordination
├── circuit_breaker.log      # Resilience events
└── summary.log             # Conversation summaries
```

## Structured Logging

### JSON Log Format

All logs use structured JSON for machine readability:

```json
{
  "timestamp": "2024-01-15T10:30:45.123456",
  "level": "INFO",
  "component": "orchestrator",
  "operation": "TOOL_CALL",
  "trace_id": "abc123-def456",
  "user_id": "user789",
  "tool_name": "SalesforceAgentTool",
  "duration_ms": 245,
  "status": "success",
  "metadata": {
    "task_id": "task-123",
    "instruction_preview": "Get all accounts..."
  }
}
```

### Log Levels

```python
# Standard Python log levels with specific usage
DEBUG    # Detailed diagnostic information
INFO     # General informational messages
WARNING  # Warning conditions that might need attention
ERROR    # Error conditions that don't stop execution
CRITICAL # Critical failures requiring immediate attention
```

## Activity Loggers

### Orchestrator Logger

Tracks high-level orchestration activities:

```python
def log_orchestrator_activity(
    operation_type: str,
    user_id: Optional[str] = None,
    **kwargs
) -> None:
    """Log orchestrator operations with context"""
    
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "operation_type": operation_type,
        "user_id": user_id,
        **kwargs
    }
    
    # File logging
    with open("logs/orchestrator.log", "a") as f:
        f.write(json.dumps(log_data) + "\n")
    
    # Also log to standard logger
    logger.info(f"ORCHESTRATOR_{operation_type}", extra=log_data)
```

**Common Operations:**
- `USER_MESSAGE`: New user input received
- `AI_RESPONSE`: Response generated
- `TOOL_CALL`: Tool invoked
- `SUMMARY_TRIGGERED`: Conversation summarized
- `MEMORY_UPDATE`: Memory extraction triggered
- `AGENT_SELECTED`: Agent chosen for task

### Salesforce Agent Logger

Tracks CRM-specific operations:

```python
def log_salesforce_activity(
    operation_type: str,
    task_id: Optional[str] = None,
    **kwargs
) -> None:
    """Log Salesforce agent activities"""
    
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "operation_type": operation_type,
        "task_id": task_id,
        "agent": "salesforce",
        **kwargs
    }
    
    with open("logs/salesforce_agent.log", "a") as f:
        f.write(json.dumps(log_data) + "\n")
```

**Common Operations:**
- `A2A_TASK_START`: Task processing begins
- `TOOL_CALL`: Salesforce tool executed
- `SOQL_QUERY`: Database query performed
- `RECORD_CREATED`: New CRM record
- `RECORD_UPDATED`: CRM record modified
- `TASK_COMPLETED`: Task finished

### A2A Protocol Logger

Tracks inter-agent communication:

```python
def log_a2a_activity(
    operation_type: str,
    task_id: Optional[str] = None,
    agent_url: Optional[str] = None,
    **kwargs
) -> None:
    """Log A2A protocol operations"""
    
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "operation_type": operation_type,
        "task_id": task_id,
        "agent_url": agent_url,
        "protocol": "a2a",
        **kwargs
    }
    
    with open("logs/a2a_protocol.log", "a") as f:
        f.write(json.dumps(log_data) + "\n")
```

**Common Operations:**
- `CONNECTION_CREATED`: New connection established
- `REQUEST_SENT`: A2A request initiated
- `RESPONSE_RECEIVED`: A2A response received
- `CIRCUIT_BREAKER_OPEN`: Circuit opened
- `RETRY_ATTEMPT`: Request retry
- `TIMEOUT_ERROR`: Request timeout

### Memory Logger

Tracks memory system operations:

```python
def log_memory_activity(
    operation_type: str,
    user_id: str,
    entities_count: Optional[Dict[str, int]] = None,
    **kwargs
) -> None:
    """Log memory extraction and storage"""
    
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "operation_type": operation_type,
        "user_id": user_id,
        "subsystem": "memory",
        **kwargs
    }
    
    if entities_count:
        log_data["entities_extracted"] = entities_count
    
    with open("logs/memory.log", "a") as f:
        f.write(json.dumps(log_data) + "\n")
```

## Performance Tracking

### Performance Metrics

```python
class PerformanceTracker:
    """Track operation performance metrics"""
    
    def __init__(self, component: str):
        self.component = component
        self.metrics = {}
    
    @contextmanager
    def track_operation(self, operation: str, **metadata):
        """Context manager for timing operations"""
        start_time = time.time()
        
        try:
            yield
            status = "success"
        except Exception as e:
            status = "error"
            metadata["error"] = str(e)
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.log_performance(
                operation=operation,
                duration_ms=duration_ms,
                status=status,
                **metadata
            )
```

### Performance Log Format

```json
{
  "timestamp": "2024-01-15T10:30:45.123456",
  "component": "orchestrator",
  "operation": "llm_call",
  "duration_ms": 1234.56,
  "status": "success",
  "metadata": {
    "model": "gpt-4",
    "input_tokens": 500,
    "output_tokens": 200
  }
}
```

### Key Performance Indicators

1. **Response Times**
   - LLM call duration
   - Tool execution time
   - A2A request latency
   - Database query time

2. **Throughput Metrics**
   - Requests per second
   - Messages processed
   - Tools executed
   - Memory updates

3. **Resource Usage**
   - Token consumption
   - API calls made
   - Database operations
   - Network connections

## Cost Tracking

### Token Usage Tracking

```python
def log_cost_activity(
    operation: str,
    tokens: int,
    model: str = "gpt-4",
    **kwargs
) -> None:
    """Track LLM token usage and costs"""
    
    # Calculate cost based on model
    cost_per_1k = {
        "gpt-4": {"input": 0.01, "output": 0.03},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015}
    }
    
    # Estimate cost (simplified)
    estimated_cost = (tokens / 1000) * cost_per_1k[model]["input"]
    
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "operation": operation,
        "model": model,
        "tokens": tokens,
        "estimated_cost_usd": estimated_cost,
        **kwargs
    }
    
    with open("logs/cost_tracking.log", "a") as f:
        f.write(json.dumps(log_data) + "\n")
```

### Cost Analysis

```python
def analyze_costs(start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """Analyze costs over a time period"""
    
    total_tokens = 0
    total_cost = 0
    operations = defaultdict(int)
    
    with open("logs/cost_tracking.log", "r") as f:
        for line in f:
            entry = json.loads(line)
            timestamp = datetime.fromisoformat(entry["timestamp"])
            
            if start_date <= timestamp <= end_date:
                total_tokens += entry["tokens"]
                total_cost += entry["estimated_cost_usd"]
                operations[entry["operation"]] += 1
    
    return {
        "period": f"{start_date} to {end_date}",
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost,
        "operations": dict(operations),
        "average_tokens_per_operation": total_tokens / sum(operations.values())
    }
```

## Distributed Tracing

### Trace Context Propagation

```python
def create_trace_context() -> Dict[str, str]:
    """Create new trace context"""
    return {
        "trace_id": str(uuid.uuid4()),
        "span_id": str(uuid.uuid4()),
        "flags": "01"  # Sampled
    }

def propagate_trace_context(parent_context: Dict[str, str]) -> Dict[str, str]:
    """Create child span context"""
    return {
        "trace_id": parent_context["trace_id"],
        "parent_span_id": parent_context["span_id"],
        "span_id": str(uuid.uuid4()),
        "flags": parent_context["flags"]
    }
```

### Cross-Component Tracing

```python
# In orchestrator
trace_context = create_trace_context()
log_orchestrator_activity("USER_REQUEST", trace_id=trace_context["trace_id"])

# Pass to A2A
task = A2ATask(
    id=task_id,
    instruction=instruction,
    metadata={"trace_context": trace_context}
)

# In agent
parent_trace = task.metadata.get("trace_context")
child_context = propagate_trace_context(parent_trace)
log_salesforce_activity("PROCESSING", trace_id=child_context["trace_id"])
```

## Log Aggregation

### Multi-File Search

```python
def search_logs(
    pattern: str,
    log_files: List[str] = None,
    start_time: datetime = None,
    end_time: datetime = None
) -> List[Dict[str, Any]]:
    """Search across multiple log files"""
    
    if log_files is None:
        log_files = glob.glob("logs/*.log")
    
    results = []
    
    for log_file in log_files:
        with open(log_file, "r") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    
                    # Time filter
                    if start_time or end_time:
                        timestamp = datetime.fromisoformat(entry["timestamp"])
                        if start_time and timestamp < start_time:
                            continue
                        if end_time and timestamp > end_time:
                            continue
                    
                    # Pattern match
                    if pattern in json.dumps(entry):
                        entry["_source_file"] = log_file
                        results.append(entry)
                        
                except json.JSONDecodeError:
                    continue
    
    return sorted(results, key=lambda x: x["timestamp"])
```

### Log Analysis Tools

```python
def analyze_errors(time_window: timedelta = timedelta(hours=1)) -> Dict[str, Any]:
    """Analyze recent errors across all components"""
    
    end_time = datetime.now()
    start_time = end_time - time_window
    
    errors = search_logs(
        pattern='"level": "ERROR"',
        start_time=start_time,
        end_time=end_time
    )
    
    # Group by component and error type
    error_summary = defaultdict(lambda: defaultdict(int))
    
    for error in errors:
        component = error.get("component", "unknown")
        error_type = error.get("error_type", "unknown")
        error_summary[component][error_type] += 1
    
    return {
        "time_window": str(time_window),
        "total_errors": len(errors),
        "errors_by_component": dict(error_summary),
        "recent_errors": errors[-10:]  # Last 10 errors
    }
```

## Monitoring Integration

### Metrics Export

```python
class MetricsExporter:
    """Export metrics to monitoring systems"""
    
    def export_to_prometheus(self):
        """Format metrics for Prometheus"""
        metrics = []
        
        # Response time histogram
        metrics.append(
            "# HELP response_time_seconds Response time in seconds\n"
            "# TYPE response_time_seconds histogram"
        )
        
        # Error rate counter
        metrics.append(
            "# HELP errors_total Total number of errors\n"
            "# TYPE errors_total counter"
        )
        
        return "\n".join(metrics)
    
    def export_to_datadog(self):
        """Send metrics to DataDog"""
        # Implementation depends on DataDog client
        pass
```

### Health Check Endpoint

```python
async def health_check() -> Dict[str, Any]:
    """System health check for monitoring"""
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {}
    }
    
    # Check each component
    components = ["orchestrator", "salesforce_agent", "database", "a2a"]
    
    for component in components:
        try:
            # Component-specific health check
            if component == "database":
                # Test database connection
                await test_database_connection()
            elif component == "a2a":
                # Test A2A connectivity
                await test_a2a_connection()
                
            health_status["components"][component] = "healthy"
            
        except Exception as e:
            health_status["components"][component] = "unhealthy"
            health_status["status"] = "degraded"
            logger.error(f"Health check failed for {component}: {e}")
    
    return health_status
```

## Debug Logging

### Debug Mode Configuration

```python
def configure_debug_logging():
    """Enable comprehensive debug logging"""
    
    # Set all loggers to DEBUG
    logging.getLogger().setLevel(logging.DEBUG)
    
    # Add console handler with detailed format
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - '
            '%(filename)s:%(lineno)d - %(message)s'
        )
    )
    
    # Enable SQL query logging
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
    
    # Enable HTTP request logging
    logging.getLogger('aiohttp.client').setLevel(logging.DEBUG)
    
    # Enable LangChain internals
    logging.getLogger('langchain').setLevel(logging.DEBUG)
```

### Debug Context Manager

```python
@contextmanager
def debug_context(operation: str, **context):
    """Enhanced logging for debugging"""
    
    debug_id = str(uuid.uuid4())[:8]
    logger.debug(f"[{debug_id}] Starting {operation}", extra=context)
    
    try:
        yield debug_id
        logger.debug(f"[{debug_id}] Completed {operation}")
    except Exception as e:
        logger.exception(f"[{debug_id}] Failed {operation}: {e}")
        raise
```

## Log Rotation

### Configuration

```python
def setup_log_rotation():
    """Configure log file rotation"""
    
    from logging.handlers import RotatingFileHandler
    
    # Create rotating handler
    handler = RotatingFileHandler(
        filename="logs/app.log",
        maxBytes=100 * 1024 * 1024,  # 100MB
        backupCount=5,
        encoding='utf-8'
    )
    
    # Set format
    handler.setFormatter(
        JsonFormatter()  # Custom JSON formatter
    )
    
    # Add to logger
    logging.getLogger().addHandler(handler)
```

### Cleanup Strategy

```python
def cleanup_old_logs(days_to_keep: int = 7):
    """Remove logs older than specified days"""
    
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    
    for log_file in glob.glob("logs/*.log*"):
        # Check file modification time
        mtime = datetime.fromtimestamp(os.path.getmtime(log_file))
        
        if mtime < cutoff_date:
            logger.info(f"Removing old log file: {log_file}")
            os.remove(log_file)
```

## Best Practices

### 1. Logging Guidelines

- Use structured JSON format
- Include trace IDs for correlation
- Log at appropriate levels
- Avoid logging sensitive data
- Include relevant context

### 2. Performance

- Use async logging where possible
- Buffer log writes
- Compress old logs
- Index for fast searching
- Monitor log volume

### 3. Security

- Sanitize sensitive information
- Encrypt logs at rest
- Control access permissions
- Audit log access
- Comply with retention policies

### 4. Troubleshooting

- Correlate logs by trace ID
- Search across time windows
- Analyze error patterns
- Monitor performance trends
- Set up alerts

## Troubleshooting Guide

### Common Issues

1. **Missing Logs**
   - Check file permissions
   - Verify log directory exists
   - Review log level settings
   - Check disk space

2. **Performance Impact**
   - Enable log buffering
   - Reduce log verbosity
   - Use async handlers
   - Implement sampling

3. **Log Correlation**
   - Ensure trace ID propagation
   - Synchronize timestamps
   - Use consistent field names
   - Implement log aggregation

4. **Storage Issues**
   - Enable log rotation
   - Compress old logs
   - Archive to cold storage
   - Monitor disk usage

## Future Enhancements

1. **OpenTelemetry Integration**: Full observability stack
2. **Real-time Analytics**: Stream processing for logs
3. **ML-based Anomaly Detection**: Automatic issue detection
4. **Distributed Tracing UI**: Visualization tools
5. **Custom Dashboards**: Business-specific metrics