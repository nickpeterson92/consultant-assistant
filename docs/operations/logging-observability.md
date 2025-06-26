# Logging & Observability

Structured logging and monitoring system for multi-agent orchestrator with JSON formatting, component separation, and performance tracking.

## Architecture

Multi-component structured JSON logging system:

```
┌─────────────────────────────────────────────────────────┐
│                 Log Architecture                        │
├─────────────────────────────────────────────────────────┤
│ orchestrator.log     │ Core workflow operations         │
│ salesforce_agent.log │ CRM operations and errors        │
│ jira_agent.log       │ Issue tracking operations        │
│ servicenow_agent.log │ ITSM operations and queries      │
│ a2a_protocol.log     │ Inter-agent communication        │
│ memory_system.log    │ Storage and retrieval            │
│ circuit_breaker.log  │ Resilience and failures          │
├─────────────────────────────────────────────────────────┤
│         JSON Format - Machine Readable                  │
└─────────────────────────────────────────────────────────┘
```

### JSON Format Structure

```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "component": "orchestrator",
  "level": "INFO",
  "operation_type": "AGENT_CALL_START",
  "message": "Calling Salesforce agent",
  "task_id": "abc-123",
  "agent_name": "salesforce",
  "duration_ms": 1234
}
```

## Component Loggers

### Orchestrator Logger
```python
# Core workflow operations
logger.info("LangGraph state transition", extra={
    "operation_type": "STATE_TRANSITION",
    "from_node": "understand_request",
    "to_node": "call_agent",
    "thread_id": thread_id
})
```

### Agent Loggers
```python
# Tool execution tracking
logger.info("Tool execution complete", extra={
    "operation_type": "TOOL_COMPLETE",
    "tool_name": "GetAccountTool",
    "duration_ms": 456,
    "records_returned": 5
})
```

### A2A Protocol Logger
```python
# Inter-agent communication
logger.info("A2A task complete", extra={
    "operation_type": "A2A_TASK_COMPLETE",
    "task_id": "def-456",
    "agent_url": "http://localhost:8001/a2a",
    "status_code": 200
})
```

## Configuration

### Logger Setup
```python
# src/utils/logging/logger_setup.py
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "component": record.name.split('.')[0],
            "level": record.levelname,
            "message": record.getMessage()
        }
        
        # Add structured fields
        for attr in ['operation_type', 'task_id', 'duration_ms', 'agent_name']:
            if hasattr(record, attr):
                log_data[attr] = getattr(record, attr)
                
        return json.dumps(log_data)
```

### Component Setup
```python
# Individual loggers for each component
orchestrator_logger = logging.getLogger('orchestrator')
salesforce_logger = logging.getLogger('salesforce_agent')
a2a_logger = logging.getLogger('a2a_protocol')

# File handlers with rotation
handler = RotatingFileHandler('logs/orchestrator.log', maxBytes=50MB, backupCount=5)
handler.setFormatter(JsonFormatter())
orchestrator_logger.addHandler(handler)
```

## Log Analysis

### Common Queries
```bash
# Find all errors across components
jq 'select(.level=="ERROR")' logs/*.log

# Track specific task execution
jq 'select(.task_id=="abc-123")' logs/*.log | jq -s 'sort_by(.timestamp)'

# Performance analysis
jq 'select(.operation_type=="TOOL_COMPLETE") | {tool_name, duration_ms}' logs/salesforce_agent.log

# Circuit breaker events
jq 'select(.operation_type | contains("CIRCUIT"))' logs/circuit_breaker.log
```

### Monitoring Integration
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "component": "orchestrator",
  "operation_type": "MEMORY_SUMMARY_TRIGGERED",
  "trigger_reason": "message_count_threshold",
  "messages_before": 15,
  "messages_after": 5,
  "tokens_saved": 2500
}
```

## Performance Tracking

### Key Metrics
- **Request Duration**: End-to-end processing time
- **Tool Execution**: Individual tool performance
- **A2A Latency**: Inter-agent communication overhead
- **Memory Operations**: Storage and retrieval timing
- **Circuit Breaker**: Failure rates and recovery

### Alert Conditions
```python
# Performance alerts
if duration_ms > 5000:
    logger.warning("Slow operation detected", extra={
        "operation_type": "PERFORMANCE_ALERT",
        "threshold_ms": 5000,
        "actual_ms": duration_ms
    })

# Error rate alerts
if error_count > 5:
    logger.error("High error rate", extra={
        "operation_type": "ERROR_RATE_ALERT",
        "error_count": error_count,
        "time_window": "5min"
    })
```

## Implementation Details

### File Structure
```
logs/
├── orchestrator.log         # Core orchestration events
├── salesforce_agent.log     # CRM operations
├── jira_agent.log          # Issue management
├── servicenow_agent.log    # ITSM operations
├── a2a_protocol.log        # Communication events
├── memory_system.log       # Storage operations
└── circuit_breaker.log     # Resilience events
```

### Log Rotation
- **File Size**: 50MB per component
- **Retention**: 5 backup files
- **Total Storage**: ~250MB per component

### Best Practices
- Use structured fields consistently
- Include task_id for request tracing
- Log performance metrics for optimization
- Separate concerns by component
- Include error context for debugging

## Operation Types

### Orchestrator Operations
- `STATE_TRANSITION`: LangGraph node changes
- `AGENT_CALL_START/COMPLETE`: A2A delegations
- `MEMORY_SUMMARY_TRIGGERED`: Background summarization
- `USER_MESSAGE_RECEIVED`: New conversation input

### Agent Operations
- `TOOL_START/COMPLETE`: Individual tool execution
- `A2A_TASK_RECEIVED`: Incoming task processing
- `EXTERNAL_API_CALL`: Third-party service calls

### System Operations
- `CIRCUIT_BREAKER_OPEN/CLOSE`: Resilience events
- `CONNECTION_POOL_STATS`: Resource utilization
- `HEALTH_CHECK_RESULT`: Service availability

## Troubleshooting

### Common Log Patterns
```bash
# Agent failures
grep "ERROR" logs/salesforce_agent.log | tail -10

# Performance issues
jq 'select(.duration_ms > 2000)' logs/orchestrator.log

# Memory operations
grep "MEMORY" logs/memory_system.log

# Circuit breaker activity
grep "CIRCUIT" logs/circuit_breaker.log
```

### Debug Commands
```bash
# Live monitoring
tail -f logs/orchestrator.log | jq .

# Error aggregation
cat logs/*.log | jq 'select(.level=="ERROR") | .component' | sort | uniq -c

# Performance summary
cat logs/orchestrator.log | jq 'select(.duration_ms) | .duration_ms' | awk '{sum+=$1; count++} END {print "Avg:", sum/count "ms"}'
```

## Integration Points

### OpenTelemetry Export
```python
# Export to monitoring systems
def export_to_otel(log_entry):
    span = tracer.start_span(log_entry['operation_type'])
    span.set_attributes({
        'component': log_entry['component'],
        'duration_ms': log_entry.get('duration_ms', 0)
    })
    span.end()
```

### Alerting Rules
- Response time > 5 seconds
- Error rate > 5% in 5 minutes
- Circuit breaker open
- Memory usage > 80%
- Agent unavailable > 30 seconds