# Logging and Observability Documentation: A Comprehensive Guide for Junior Engineers

## Table of Contents
1. [Why Logging Matters - Real Horror Stories](#why-logging-matters)
2. [Structured vs Unstructured Logging](#structured-vs-unstructured)
3. [Setting Up Logging Step-by-Step](#setting-up-logging)
4. [What to Log and What Not to Log](#what-to-log)
5. [Log Levels Explained with Examples](#log-levels-explained)
6. [Building Dashboards and Alerts](#dashboards-and-alerts)
7. [Debugging Production Issues](#debugging-production)
8. [Performance Impact and Best Practices](#performance-impact)
9. [Common Mistakes to Avoid](#common-mistakes)

## Why Logging Matters - Real Horror Stories

### 🔥 Horror Story #1: The Midnight Mystery
*"It was 2 AM when my phone rang. Production was down. Users couldn't log in. Revenue was bleeding at $10K per minute. I SSH'd into the server, ran `tail -f app.log`, and saw... nothing. The last log entry was from 3 hours ago. We had no idea what was happening. After 4 hours of blind debugging and random restarts, we discovered a memory leak. If we had proper logging, we would have seen memory warnings hours before the crash."*

### 💸 Horror Story #2: The $100K Bug
*"A payment processing bug was silently failing for 2 weeks. Customers were charged but orders weren't created. When we finally discovered it, we had no logs to trace which payments failed. We had to manually reconcile 50,000 transactions. The audit took 3 weeks and cost over $100K in contractor fees. One simple log line could have saved us: `logger.error(f'Payment {payment_id} processed but order creation failed')`"*

### 🕵️ Horror Story #3: The Blame Game
*"A critical API integration failed during Black Friday. The vendor blamed us, we blamed them. Without request/response logs, we couldn't prove what data we sent. We lost the dispute and had to pay $50K in SLA penalties. Now we log EVERY external API call."*

### Why These Stories Matter
Logging isn't just about debugging - it's about:
- **Business Continuity**: Know what's happening before customers complain
- **Legal Protection**: Prove what your system did or didn't do
- **Performance Optimization**: Find bottlenecks before they become problems
- **Customer Trust**: Resolve issues quickly with confidence
- **Team Sanity**: Sleep better knowing you can debug anything

## Structured vs Unstructured Logging

### ❌ Unstructured Logging (The Old Way)
```python
# DON'T DO THIS - Unstructured logs are hard to parse and search
print(f"User {user_id} logged in at {datetime.now()}")
# Output: User 12345 logged in at 2024-01-15 10:30:45.123456

print("Error: " + str(e) + " for user " + user_id)
# Output: Error: Connection timeout for user 12345

logger.info("Processing order " + order_id + " with " + str(item_count) + " items")
# Output: Processing order ORD-789 with 5 items
```

**Problems with unstructured logs:**
- Can't search efficiently (try finding all errors for user 12345)
- Can't aggregate data (how many orders had >10 items?)
- Parsing is error-prone (what if the message format changes?)
- No standard fields (where's the timestamp? severity?)

### ✅ Structured Logging (The Modern Way)
```python
# DO THIS - Structured logs are machine-readable and searchable
import json
import logging
from datetime import datetime

# Configure structured logging
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add any extra fields
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        if hasattr(record, 'order_id'):
            log_data['order_id'] = record.order_id
            
        return json.dumps(log_data)

# Use structured logging
logger.info("User logged in", extra={"user_id": user_id, "ip_address": ip})
# Output: {"timestamp": "2024-01-15T10:30:45.123456", "level": "INFO", "message": "User logged in", "user_id": "12345", "ip_address": "192.168.1.1"}

logger.error("Order processing failed", extra={
    "order_id": order_id,
    "error_type": "payment_declined",
    "amount": 99.99,
    "retry_count": 3
})
# Output: {"timestamp": "2024-01-15T10:31:00.456789", "level": "ERROR", "message": "Order processing failed", "order_id": "ORD-789", "error_type": "payment_declined", "amount": 99.99, "retry_count": 3}
```

**Benefits of structured logs:**
- **Searchable**: Find all payment_declined errors: `jq 'select(.error_type=="payment_declined")' logs.json`
- **Aggregatable**: Count orders by amount range
- **Parseable**: Tools can automatically process logs
- **Consistent**: Every log has standard fields
- **Rich Context**: Include as many fields as needed

### Real-World Example: Debugging with Structured Logs
```python
# Scenario: Users report slow checkout. Let's trace the issue.

# With structured logging, you can:
# 1. Find all checkout operations over 5 seconds
cat logs.json | jq 'select(.operation=="checkout" and .duration_ms > 5000)'

# 2. Group slow checkouts by payment method
cat logs.json | jq 'select(.operation=="checkout" and .duration_ms > 5000) | .payment_method' | sort | uniq -c

# 3. Trace a specific user's journey
cat logs.json | jq 'select(.user_id=="12345")' | jq -s 'sort_by(.timestamp)'

# Output shows: Payment provider API calls taking 8+ seconds for PayPal!
```

## Setting Up Logging Step-by-Step

### Step 1: Basic Python Logging Setup
```python
# logging_setup.py - Start here!
import logging
import logging.handlers
import json
import os
from datetime import datetime
from pathlib import Path

# Create logs directory
Path("logs").mkdir(exist_ok=True)

# Step 1: Create a custom JSON formatter
class JsonFormatter(logging.Formatter):
    """Format logs as JSON for easy parsing"""
    
    def format(self, record):
        # Start with basic fields
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "thread_name": record.threadName,
            "process": record.process
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add custom fields from 'extra' parameter
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 
                          'funcName', 'levelname', 'levelno', 'lineno', 
                          'module', 'msecs', 'pathname', 'process', 
                          'processName', 'relativeCreated', 'thread', 
                          'threadName', 'exc_info', 'exc_text', 'stack_info']:
                log_data[key] = value
                
        return json.dumps(log_data)

# Step 2: Create logger configuration function
def setup_logging(app_name="myapp", log_level="INFO"):
    """Set up logging with both file and console output"""
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove default handlers
    root_logger.handlers = []
    
    # Create formatters
    json_formatter = JsonFormatter()
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        filename=f'logs/{app_name}.log',
        maxBytes=100_000_000,  # 100MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(json_formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler for development
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.WARNING)  # Only warnings+ to console
    root_logger.addHandler(console_handler)
    
    # Create app-specific logger
    app_logger = logging.getLogger(app_name)
    
    return app_logger

# Step 3: Create a context-aware logger wrapper
class ContextLogger:
    """Logger that maintains context across operations"""
    
    def __init__(self, logger, **default_context):
        self.logger = logger
        self.context = default_context
    
    def add_context(self, **kwargs):
        """Add persistent context fields"""
        self.context.update(kwargs)
    
    def _log(self, level, msg, **kwargs):
        """Internal log method with context"""
        extra = {**self.context, **kwargs}
        getattr(self.logger, level)(msg, extra=extra)
    
    def info(self, msg, **kwargs):
        self._log('info', msg, **kwargs)
    
    def error(self, msg, **kwargs):
        self._log('error', msg, **kwargs)
    
    def warning(self, msg, **kwargs):
        self._log('warning', msg, **kwargs)
    
    def debug(self, msg, **kwargs):
        self._log('debug', msg, **kwargs)

# Step 4: Usage example
if __name__ == "__main__":
    # Initialize logging
    base_logger = setup_logging("multi-agent-system", "INFO")
    
    # Create context-aware logger
    logger = ContextLogger(
        base_logger,
        environment="production",
        service="orchestrator",
        version="1.0.0"
    )
    
    # Add user context
    logger.add_context(user_id="user123", session_id="sess456")
    
    # Now all logs include this context
    logger.info("User logged in", ip_address="192.168.1.1")
    logger.error("Failed to process request", 
                error_code="TIMEOUT", 
                duration_ms=5000)
```

### Step 2: Setting Up for Our Multi-Agent System
```python
# src/utils/logging/setup.py
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import os

class MultiAgentLogger:
    """Specialized logger for multi-agent systems"""
    
    def __init__(self, component: str):
        self.component = component
        self.setup_component_logging()
    
    def setup_component_logging(self):
        """Set up logging for a specific component"""
        
        # Create component-specific log file
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Component logger
        self.logger = logging.getLogger(f"multi_agent.{self.component}")
        self.logger.setLevel(logging.DEBUG if os.getenv("DEBUG") else logging.INFO)
        
        # JSON formatter for structured logs
        formatter = JsonFormatter()
        
        # File handler for this component
        handler = logging.handlers.RotatingFileHandler(
            log_dir / f"{self.component}.log",
            maxBytes=50_000_000,
            backupCount=3
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        # Also log to main system log
        system_handler = logging.handlers.RotatingFileHandler(
            log_dir / "multi_agent.log",
            maxBytes=100_000_000,
            backupCount=5
        )
        system_handler.setFormatter(formatter)
        self.logger.addHandler(system_handler)
    
    def log_operation(self, 
                     operation: str,
                     status: str = "started",
                     **context):
        """Log a component operation with context"""
        
        log_data = {
            "component": self.component,
            "operation": operation,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            **context
        }
        
        if status == "error":
            self.logger.error(f"{operation} failed", extra=log_data)
        else:
            self.logger.info(f"{operation} {status}", extra=log_data)
    
    def log_a2a_communication(self,
                             direction: str,  # "sent" or "received"
                             task_id: str,
                             agent: str,
                             **details):
        """Log agent-to-agent communication"""
        
        self.log_operation(
            operation="a2a_communication",
            direction=direction,
            task_id=task_id,
            target_agent=agent,
            **details
        )
    
    def log_performance(self,
                       operation: str,
                       duration_ms: float,
                       **metrics):
        """Log performance metrics"""
        
        self.log_operation(
            operation=f"performance_{operation}",
            status="completed",
            duration_ms=duration_ms,
            **metrics
        )

# Usage in orchestrator
orchestrator_logger = MultiAgentLogger("orchestrator")

# Log user interaction
orchestrator_logger.log_operation(
    "user_message",
    status="received",
    user_id="user123",
    message_length=150
)

# Log tool selection
orchestrator_logger.log_operation(
    "tool_selection",
    status="completed",
    selected_tool="SalesforceAgentTool",
    confidence=0.95
)

# Log A2A communication
orchestrator_logger.log_a2a_communication(
    direction="sent",
    task_id="task-789",
    agent="salesforce",
    instruction="Get all accounts for Acme Corp"
)
```

### Step 3: Integration with LangGraph
```python
# src/orchestrator/logging_integration.py
from typing import Dict, Any
import time
import functools

def log_node_execution(logger: MultiAgentLogger):
    """Decorator to log LangGraph node execution"""
    
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
            start_time = time.time()
            node_name = func.__name__
            
            # Log node start
            logger.log_operation(
                f"node_{node_name}",
                status="started",
                message_count=len(state.get("messages", [])),
                user_id=state.get("user_id")
            )
            
            try:
                # Execute node
                result = await func(state)
                
                # Log success
                duration_ms = (time.time() - start_time) * 1000
                logger.log_performance(
                    f"node_{node_name}",
                    duration_ms=duration_ms,
                    status="success"
                )
                
                return result
                
            except Exception as e:
                # Log error
                logger.log_operation(
                    f"node_{node_name}",
                    status="error",
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
                raise
        
        return wrapper
    return decorator

# Apply to LangGraph nodes
@log_node_execution(orchestrator_logger)
async def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Process state through agent"""
    # Your node logic here
    pass
```

## What to Log and What Not to Log

### ✅ What TO Log

#### 1. **Business Events**
```python
# Log events that matter to the business
logger.info("Order placed", extra={
    "order_id": order.id,
    "user_id": user.id,
    "total_amount": order.total,
    "item_count": len(order.items),
    "payment_method": order.payment_method
})

logger.info("User registration completed", extra={
    "user_id": user.id,
    "registration_source": "mobile_app",
    "referral_code": user.referral_code
})
```

#### 2. **System State Changes**
```python
# Log when system state changes significantly
logger.info("Circuit breaker opened", extra={
    "service": "payment_gateway",
    "failure_count": 5,
    "last_error": "timeout"
})

logger.info("Cache invalidated", extra={
    "cache_key": "user_preferences_*",
    "reason": "bulk_update",
    "affected_users": 1523
})
```

#### 3. **External API Calls**
```python
# ALWAYS log external interactions
logger.info("API request", extra={
    "api": "salesforce",
    "endpoint": "/sobjects/Account",
    "method": "POST",
    "request_id": request_id
})

logger.info("API response", extra={
    "api": "salesforce",
    "request_id": request_id,
    "status_code": 201,
    "duration_ms": 234,
    "rate_limit_remaining": headers.get("X-Rate-Limit-Remaining")
})
```

#### 4. **Performance Metrics**
```python
# Log operations that could impact performance
with timer() as t:
    result = expensive_operation()
    
logger.info("Operation completed", extra={
    "operation": "data_aggregation",
    "duration_ms": t.elapsed_ms,
    "record_count": len(result),
    "memory_usage_mb": get_memory_usage()
})
```

#### 5. **Security Events**
```python
# Log authentication and authorization
logger.warning("Failed login attempt", extra={
    "username": username,
    "ip_address": request.remote_addr,
    "attempt_number": attempt_count,
    "user_agent": request.headers.get("User-Agent")
})

logger.info("Permission check", extra={
    "user_id": user.id,
    "resource": "financial_reports",
    "action": "read",
    "granted": False
})
```

### ❌ What NOT to Log

#### 1. **Sensitive Information**
```python
# NEVER log passwords, tokens, or PII
# ❌ BAD
logger.info(f"User login: username={username}, password={password}")
logger.info(f"API call with token: {api_token}")
logger.info(f"User SSN: {ssn}")

# ✅ GOOD
logger.info("User login attempt", extra={"username": username})
logger.info("API call authenticated", extra={"token_prefix": api_token[:4] + "..."})
logger.info("User verification", extra={"user_id": user.id, "verification_type": "ssn"})
```

#### 2. **High-Frequency Noise**
```python
# ❌ BAD - Don't log inside tight loops
for item in items:  # Could be thousands
    logger.debug(f"Processing item {item.id}")  # NO!
    process_item(item)

# ✅ GOOD - Batch logging
logger.info("Batch processing started", extra={"item_count": len(items)})
results = process_batch(items)
logger.info("Batch processing completed", extra={
    "item_count": len(items),
    "success_count": results.success_count,
    "failure_count": results.failure_count,
    "duration_ms": results.duration_ms
})
```

#### 3. **Entire Objects or Large Payloads**
```python
# ❌ BAD - Don't dump entire objects
logger.info(f"User object: {user.__dict__}")  # Could be huge!
logger.info(f"Response data: {json.dumps(response_data)}")  # Could be MB of data

# ✅ GOOD - Log relevant fields only
logger.info("User updated", extra={
    "user_id": user.id,
    "fields_changed": ["email", "phone"],
    "updated_by": admin.id
})

logger.info("API response received", extra={
    "status": response.status_code,
    "record_count": len(response.data.get("records", [])),
    "has_more": response.data.get("has_more", False)
})
```

#### 4. **Temporary Debugging Logs**
```python
# ❌ BAD - Don't leave debugging logs in production
logger.debug("HERE 1")  # Meaningless
logger.info(f"x = {x}")  # Variable dumps
print("Got here!")  # Console prints

# ✅ GOOD - Use meaningful debug logs or remove them
logger.debug("Entering payment validation", extra={
    "payment_method": payment.method,
    "amount": payment.amount
})
```

### Special Considerations for Multi-Agent Systems

```python
# Log agent interactions with context
logger.info("Agent task delegated", extra={
    "source_agent": "orchestrator",
    "target_agent": "salesforce",
    "task_id": task_id,
    "task_type": "data_retrieval",
    "expected_duration_ms": 5000
})

# Log memory operations
logger.info("Memory extraction completed", extra={
    "user_id": user_id,
    "entities_extracted": {
        "accounts": 5,
        "contacts": 12,
        "opportunities": 3
    },
    "extraction_duration_ms": 234
})

# Log circuit breaker events
logger.warning("Circuit breaker state change", extra={
    "service": "salesforce_agent",
    "previous_state": "closed",
    "new_state": "open",
    "failure_count": 5,
    "will_retry_at": retry_time.isoformat()
})
```

## Log Levels Explained with Examples

### 🔍 DEBUG - Development Details
**When to use**: Detailed information for diagnosing problems during development

```python
# Good DEBUG examples
logger.debug("SQL query executed", extra={
    "query": "SELECT * FROM users WHERE active = ?",
    "params": [True],
    "row_count": 150,
    "execution_time_ms": 23
})

logger.debug("Cache lookup", extra={
    "key": "user_preferences_123",
    "hit": True,
    "ttl_remaining": 3600
})

logger.debug("State transition", extra={
    "entity": "order",
    "entity_id": "ORD-123",
    "from_state": "pending",
    "to_state": "processing"
})

# When NOT to use DEBUG
# ❌ In production (unless debugging specific issues)
# ❌ For sensitive information
# ❌ Inside tight loops
```

### ℹ️ INFO - Normal Operations
**When to use**: General informational messages about normal application flow

```python
# Good INFO examples
logger.info("Server started", extra={
    "port": 8000,
    "environment": "production",
    "version": "1.2.3"
})

logger.info("Background job completed", extra={
    "job_type": "email_digest",
    "recipients_count": 1523,
    "duration_seconds": 45
})

logger.info("Feature flag evaluated", extra={
    "flag": "new_checkout_flow",
    "user_id": user_id,
    "result": True
})

# INFO is your default level - most business events go here
```

### ⚠️ WARNING - Potential Problems
**When to use**: Something unexpected happened but the application is still working

```python
# Good WARNING examples
logger.warning("API rate limit approaching", extra={
    "api": "salesforce",
    "calls_remaining": 50,
    "reset_time": reset_time.isoformat()
})

logger.warning("Deprecated function called", extra={
    "function": "get_user_by_email",
    "replacement": "get_user",
    "deprecation_date": "2024-06-01",
    "caller": inspect.stack()[1].function
})

logger.warning("Slow query detected", extra={
    "query_type": "user_search",
    "duration_ms": 5234,
    "threshold_ms": 1000
})

logger.warning("Memory usage high", extra={
    "current_mb": 1800,
    "threshold_mb": 2000,
    "percentage": 90
})
```

### 🚨 ERROR - Something Failed
**When to use**: An error occurred but the application can continue

```python
# Good ERROR examples
logger.error("Payment processing failed", extra={
    "order_id": order_id,
    "payment_method": "credit_card",
    "error_code": "insufficient_funds",
    "amount": 99.99,
    "retry_attempt": 2
})

logger.error("External API error", extra={
    "api": "email_service",
    "endpoint": "/send",
    "status_code": 503,
    "error_message": "Service temporarily unavailable",
    "will_retry": True
})

logger.error("Data validation failed", extra={
    "entity": "user_profile",
    "validation_errors": {
        "email": "invalid_format",
        "age": "must_be_positive"
    },
    "source": "api_request"
})

# Always include context for errors!
try:
    result = risky_operation()
except Exception as e:
    logger.error("Operation failed", extra={
        "operation": "data_import",
        "file": filename,
        "line_number": current_line,
        "error_type": type(e).__name__
    }, exc_info=True)  # Include stack trace
```

### 💀 CRITICAL - System is Unusable
**When to use**: The application is in an unusable state

```python
# Good CRITICAL examples
logger.critical("Database connection lost", extra={
    "database": "primary",
    "last_successful_query": last_query_time.isoformat(),
    "connection_attempts": 5,
    "action": "switching_to_readonly_replica"
})

logger.critical("Security breach detected", extra={
    "breach_type": "unauthorized_access",
    "affected_users": user_count,
    "ip_address": attacker_ip,
    "action_taken": "blocking_ip_range"
})

logger.critical("Disk space exhausted", extra={
    "mount_point": "/var/log",
    "used_percentage": 99.9,
    "available_mb": 10,
    "action": "emergency_cleanup_initiated"
})

# CRITICAL means "wake someone up NOW"
```

### Choosing the Right Level - Decision Tree
```python
def choose_log_level(event):
    """
    Decision tree for log levels:
    
    Is this a system failure that requires immediate action?
    └─ YES → CRITICAL
    └─ NO → Did something fail that shouldn't have?
            └─ YES → ERROR
            └─ NO → Is this potentially problematic?
                    └─ YES → WARNING
                    └─ NO → Is this routine information?
                            └─ YES → INFO
                            └─ NO → DEBUG (detailed diagnostic info)
    """
    pass
```

## Building Dashboards and Alerts

### Creating Your First Dashboard

#### Step 1: Log Aggregation with Simple Tools
```python
# dashboard_builder.py - Simple dashboard from logs
import json
from collections import defaultdict, Counter
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

class LogDashboard:
    """Build dashboards from JSON logs"""
    
    def __init__(self, log_files):
        self.log_files = log_files
        self.logs = self.load_logs()
    
    def load_logs(self):
        """Load and parse JSON logs"""
        logs = []
        for log_file in self.log_files:
            with open(log_file, 'r') as f:
                for line in f:
                    try:
                        logs.append(json.loads(line))
                    except:
                        pass
        return logs
    
    def error_rate_by_hour(self):
        """Calculate error rate per hour"""
        hourly_counts = defaultdict(lambda: {"total": 0, "errors": 0})
        
        for log in self.logs:
            timestamp = datetime.fromisoformat(log["timestamp"].rstrip("Z"))
            hour_key = timestamp.strftime("%Y-%m-%d %H:00")
            
            hourly_counts[hour_key]["total"] += 1
            if log["level"] == "ERROR":
                hourly_counts[hour_key]["errors"] += 1
        
        # Calculate rates
        hours = sorted(hourly_counts.keys())
        error_rates = []
        
        for hour in hours:
            counts = hourly_counts[hour]
            rate = (counts["errors"] / counts["total"]) * 100 if counts["total"] > 0 else 0
            error_rates.append(rate)
        
        # Plot
        plt.figure(figsize=(12, 6))
        plt.plot(range(len(hours)), error_rates, 'r-')
        plt.title("Error Rate by Hour")
        plt.ylabel("Error Rate (%)")
        plt.xlabel("Hour")
        plt.xticks(range(0, len(hours), 4), hours[::4], rotation=45)
        plt.tight_layout()
        plt.savefig("error_rate.png")
        
        return hours, error_rates
    
    def top_errors(self, n=10):
        """Find most common errors"""
        error_messages = []
        
        for log in self.logs:
            if log["level"] == "ERROR":
                # Combine message with error type for better grouping
                error_key = f"{log.get('error_type', 'unknown')}: {log['message']}"
                error_messages.append(error_key)
        
        return Counter(error_messages).most_common(n)
    
    def performance_percentiles(self):
        """Calculate performance percentiles"""
        durations = []
        
        for log in self.logs:
            if "duration_ms" in log:
                durations.append(log["duration_ms"])
        
        if not durations:
            return {}
        
        durations.sort()
        
        return {
            "p50": durations[len(durations) // 2],
            "p90": durations[int(len(durations) * 0.9)],
            "p95": durations[int(len(durations) * 0.95)],
            "p99": durations[int(len(durations) * 0.99)],
            "max": durations[-1]
        }

# Usage
dashboard = LogDashboard(["logs/orchestrator.log", "logs/salesforce_agent.log"])

# Generate insights
print("Top Errors:")
for error, count in dashboard.top_errors():
    print(f"  {error}: {count} occurrences")

print("\nPerformance Percentiles:")
for percentile, value in dashboard.performance_percentiles().items():
    print(f"  {percentile}: {value}ms")
```

#### Step 2: Real-Time Monitoring Script
```python
# realtime_monitor.py - Watch logs in real-time
import json
import time
from datetime import datetime
import subprocess
import sys

class RealtimeMonitor:
    """Monitor logs in real-time with alerts"""
    
    def __init__(self, log_file, alert_rules):
        self.log_file = log_file
        self.alert_rules = alert_rules
        self.stats = {
            "errors_last_minute": 0,
            "requests_last_minute": 0,
            "slow_requests": 0
        }
    
    def check_alerts(self, log_entry):
        """Check if log entry triggers any alerts"""
        
        # Error rate alert
        if log_entry["level"] == "ERROR":
            self.stats["errors_last_minute"] += 1
            if self.stats["errors_last_minute"] > self.alert_rules["max_errors_per_minute"]:
                self.send_alert(
                    "HIGH ERROR RATE",
                    f"Errors in last minute: {self.stats['errors_last_minute']}"
                )
        
        # Performance alert
        if "duration_ms" in log_entry:
            if log_entry["duration_ms"] > self.alert_rules["slow_request_threshold_ms"]:
                self.stats["slow_requests"] += 1
                self.send_alert(
                    "SLOW REQUEST",
                    f"Operation: {log_entry.get('operation')}, Duration: {log_entry['duration_ms']}ms"
                )
        
        # Custom alerts
        for rule in self.alert_rules.get("custom", []):
            if rule["field"] in log_entry and log_entry[rule["field"]] == rule["value"]:
                self.send_alert(rule["alert_name"], rule["message"])
    
    def send_alert(self, alert_type, message):
        """Send alert (implement your notification method)"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n🚨 [{timestamp}] {alert_type}: {message}")
        
        # Could also:
        # - Send to Slack
        # - Send email
        # - Page on-call engineer
        # - Create incident ticket
    
    def monitor(self):
        """Start monitoring logs"""
        print(f"Monitoring {self.log_file}...")
        print("Press Ctrl+C to stop\n")
        
        # Use tail -f to follow log file
        process = subprocess.Popen(
            ["tail", "-f", self.log_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        try:
            for line in process.stdout:
                try:
                    log_entry = json.loads(line.strip())
                    
                    # Display summary
                    level_emoji = {
                        "DEBUG": "🔍",
                        "INFO": "ℹ️",
                        "WARNING": "⚠️",
                        "ERROR": "❌",
                        "CRITICAL": "💀"
                    }
                    
                    emoji = level_emoji.get(log_entry["level"], "📝")
                    timestamp = datetime.fromisoformat(
                        log_entry["timestamp"].rstrip("Z")
                    ).strftime("%H:%M:%S")
                    
                    print(f"{emoji} [{timestamp}] {log_entry['message']}", end="")
                    
                    if "duration_ms" in log_entry:
                        print(f" ({log_entry['duration_ms']}ms)", end="")
                    
                    print()
                    
                    # Check alerts
                    self.check_alerts(log_entry)
                    
                except json.JSONDecodeError:
                    pass
                    
        except KeyboardInterrupt:
            print("\nMonitoring stopped.")
            process.terminate()

# Usage
alert_rules = {
    "max_errors_per_minute": 10,
    "slow_request_threshold_ms": 5000,
    "custom": [
        {
            "field": "error_type",
            "value": "payment_failed",
            "alert_name": "PAYMENT FAILURE",
            "message": "Payment processing error detected"
        }
    ]
}

monitor = RealtimeMonitor("logs/multi_agent.log", alert_rules)
monitor.monitor()
```

### Production-Ready Dashboards

#### Grafana Dashboard Example
```json
{
  "dashboard": {
    "title": "Multi-Agent System Monitoring",
    "panels": [
      {
        "title": "Request Rate",
        "query": "rate(http_requests_total[5m])",
        "visualization": "graph"
      },
      {
        "title": "Error Rate",
        "query": "rate(http_requests_total{status=~'5..'}[5m])",
        "visualization": "graph",
        "alert": {
          "condition": "above",
          "threshold": 0.05,
          "message": "Error rate above 5%"
        }
      },
      {
        "title": "Response Time Percentiles",
        "query": "histogram_quantile(0.95, http_request_duration_seconds_bucket)",
        "visualization": "heatmap"
      },
      {
        "title": "Agent Health",
        "query": "up{job='multi_agent'}",
        "visualization": "table"
      }
    ]
  }
}
```

#### Key Metrics to Dashboard
```python
# Essential metrics for multi-agent systems

BUSINESS_METRICS = {
    "user_sessions": "Count of active users",
    "tasks_completed": "Successfully completed agent tasks",
    "revenue_processed": "Dollar amount through the system",
    "customer_satisfaction": "Based on successful interactions"
}

TECHNICAL_METRICS = {
    "response_time": "End-to-end request latency",
    "error_rate": "Percentage of failed requests",
    "throughput": "Requests per second",
    "agent_availability": "Percentage of healthy agents",
    "queue_depth": "Pending tasks in the system"
}

RESOURCE_METRICS = {
    "cpu_usage": "CPU utilization by component",
    "memory_usage": "Memory consumption",
    "disk_io": "Read/write operations",
    "network_traffic": "Bandwidth usage",
    "token_usage": "LLM API consumption"
}

# Alert thresholds
ALERT_THRESHOLDS = {
    "error_rate": 0.05,  # 5%
    "response_time_p95": 5000,  # 5 seconds
    "cpu_usage": 80,  # 80%
    "memory_usage": 90,  # 90%
    "queue_depth": 1000,  # 1000 pending tasks
}
```

## Debugging Production Issues

### The Production Debugging Playbook

#### Step 1: Gather Context
```bash
# When you get paged at 3 AM, start here:

# 1. Check system health
curl http://localhost:8000/health

# 2. Get recent errors (last 5 minutes)
cat logs/multi_agent.log | \
  jq -r 'select(.timestamp > (now - 300 | strftime("%Y-%m-%dT%H:%M:%S"))) | 
         select(.level == "ERROR")'

# 3. Check error rate trend
cat logs/multi_agent.log | \
  jq -r 'select(.timestamp > (now - 3600 | strftime("%Y-%m-%dT%H:%M:%S"))) | 
         .timestamp[0:13] + ":00"' | \
  sort | uniq -c

# 4. Find specific user's journey
USER_ID="user123"
cat logs/*.log | \
  jq -r --arg uid "$USER_ID" 'select(.user_id == $uid)' | \
  jq -s 'sort_by(.timestamp)'
```

#### Step 2: Trace a Failed Request
```python
# trace_request.py - Trace a request through the system
import json
from datetime import datetime
from collections import defaultdict

def trace_request(trace_id, log_files):
    """Trace a request across all components"""
    
    events = []
    
    # Collect all events for this trace
    for log_file in log_files:
        with open(log_file, 'r') as f:
            for line in f:
                try:
                    log = json.loads(line)
                    if log.get("trace_id") == trace_id:
                        events.append(log)
                except:
                    pass
    
    # Sort by timestamp
    events.sort(key=lambda x: x["timestamp"])
    
    # Build trace timeline
    print(f"\nTrace Timeline for {trace_id}:")
    print("-" * 80)
    
    start_time = None
    for event in events:
        timestamp = datetime.fromisoformat(event["timestamp"].rstrip("Z"))
        
        if not start_time:
            start_time = timestamp
            elapsed = 0
        else:
            elapsed = (timestamp - start_time).total_seconds() * 1000
        
        level_color = {
            "INFO": "\033[0m",    # Normal
            "WARNING": "\033[93m", # Yellow
            "ERROR": "\033[91m"    # Red
        }
        
        color = level_color.get(event["level"], "\033[0m")
        
        print(f"{color}[+{elapsed:>6.0f}ms] {event['component']:>15} | "
              f"{event['level']:>7} | {event['message']}\033[0m")
        
        # Show important fields
        important_fields = ["error_type", "duration_ms", "status_code", "retry_count"]
        extras = {k: v for k, v in event.items() if k in important_fields}
        if extras:
            print(f"{'':>27} └─ {extras}")
    
    print("-" * 80)
    print(f"Total duration: {elapsed:.0f}ms")
    
    # Analyze the trace
    analyze_trace(events)

def analyze_trace(events):
    """Analyze trace for common issues"""
    
    errors = [e for e in events if e["level"] == "ERROR"]
    warnings = [e for e in events if e["level"] == "WARNING"]
    
    if errors:
        print(f"\n⚠️  Found {len(errors)} errors in trace:")
        for error in errors:
            print(f"  - {error['component']}: {error['message']}")
    
    # Check for performance issues
    slow_ops = [e for e in events if e.get("duration_ms", 0) > 1000]
    if slow_ops:
        print(f"\n🐌 Found {len(slow_ops)} slow operations:")
        for op in slow_ops:
            print(f"  - {op['operation']}: {op['duration_ms']}ms")
    
    # Check for retries
    retries = [e for e in events if "retry" in e.get("message", "").lower()]
    if retries:
        print(f"\n🔄 Found {len(retries)} retry attempts")

# Usage
trace_request("abc123-def456", [
    "logs/orchestrator.log",
    "logs/salesforce_agent.log",
    "logs/a2a_protocol.log"
])
```

#### Step 3: Common Production Issues and Solutions

##### Issue 1: Memory Leak
```python
# Symptoms in logs:
{
  "level": "WARNING",
  "message": "Memory usage high",
  "memory_usage_mb": 1800,
  "threshold_mb": 2000
}

# Debug approach:
# 1. Track memory growth over time
cat logs/performance.log | \
  jq -r 'select(.memory_usage_mb) | 
         [.timestamp, .memory_usage_mb] | @csv' > memory_trend.csv

# 2. Find memory spikes correlated with operations
cat logs/multi_agent.log | \
  jq -r 'select(.timestamp > "2024-01-15T10:00:00" and 
                .timestamp < "2024-01-15T11:00:00")'

# 3. Add memory profiling
import tracemalloc
tracemalloc.start()

# ... your operation ...

current, peak = tracemalloc.get_traced_memory()
logger.info("Memory usage", extra={
    "current_mb": current / 1024 / 1024,
    "peak_mb": peak / 1024 / 1024
})
```

##### Issue 2: Cascading Failures
```python
# Symptoms: One service failure causes system-wide outage
# Solution: Circuit breaker pattern with logging

class LoggingCircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60, logger=None):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.logger = logger
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"
    
    def call(self, func, *args, **kwargs):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.timeout:
                self.logger.info("Circuit breaker half-open", extra={
                    "service": func.__name__,
                    "downtime_seconds": time.time() - self.last_failure_time
                })
                self.state = "half-open"
            else:
                self.logger.warning("Circuit breaker still open", extra={
                    "service": func.__name__,
                    "remaining_timeout": self.timeout - (time.time() - self.last_failure_time)
                })
                raise Exception("Circuit breaker is open")
        
        try:
            result = func(*args, **kwargs)
            if self.state == "half-open":
                self.logger.info("Circuit breaker recovered", extra={
                    "service": func.__name__
                })
                self.reset()
            return result
            
        except Exception as e:
            self.failures += 1
            self.last_failure_time = time.time()
            
            self.logger.error("Circuit breaker failure", extra={
                "service": func.__name__,
                "failure_count": self.failures,
                "error": str(e)
            })
            
            if self.failures >= self.failure_threshold:
                self.state = "open"
                self.logger.critical("Circuit breaker opened", extra={
                    "service": func.__name__,
                    "failure_threshold": self.failure_threshold
                })
            
            raise
```

##### Issue 3: Debugging Distributed Timeouts
```bash
# Find all timeout errors across services
cat logs/*.log | jq -r 'select(.error_type == "timeout" or 
                               .message | contains("timeout"))'

# Trace timeout propagation
TRACE_ID=$(cat logs/*.log | \
  jq -r 'select(.error_type == "timeout") | .trace_id' | \
  head -1)

# See full request flow
./trace_request.py $TRACE_ID

# Common timeout causes:
# 1. Database locks
# 2. External API slowness
# 3. Resource contention
# 4. Network issues
```

### Production Debugging Checklist

```markdown
## Production Issue Checklist

### Immediate Actions (First 5 minutes)
- [ ] Check system health endpoint
- [ ] Identify error spike time
- [ ] Check recent deployments
- [ ] Verify external dependencies
- [ ] Page additional help if needed

### Investigation (Next 15 minutes)
- [ ] Collect error samples
- [ ] Identify affected users/components
- [ ] Check resource metrics (CPU/Memory/Disk)
- [ ] Review recent changes
- [ ] Check for patterns in errors

### Resolution
- [ ] Implement fix or workaround
- [ ] Verify fix with logs
- [ ] Monitor for recurrence
- [ ] Document root cause
- [ ] Create follow-up tickets

### Post-Incident
- [ ] Write incident report
- [ ] Update runbooks
- [ ] Add missing logs/metrics
- [ ] Schedule post-mortem
- [ ] Implement preventive measures
```

## Performance Impact and Best Practices

### Logging Performance Impact

#### Measuring Logging Overhead
```python
import time
import json
import logging

# Benchmark logging performance
def benchmark_logging():
    # Test different logging approaches
    iterations = 10000
    
    # Test 1: No logging (baseline)
    start = time.time()
    for i in range(iterations):
        result = expensive_operation(i)
    baseline_time = time.time() - start
    
    # Test 2: Simple logging
    logger = logging.getLogger("benchmark")
    start = time.time()
    for i in range(iterations):
        result = expensive_operation(i)
        logger.info(f"Operation {i} completed")
    simple_log_time = time.time() - start
    
    # Test 3: Structured logging
    start = time.time()
    for i in range(iterations):
        result = expensive_operation(i)
        logger.info("Operation completed", extra={
            "iteration": i,
            "result": result,
            "timestamp": time.time()
        })
    structured_log_time = time.time() - start
    
    # Test 4: Conditional logging
    start = time.time()
    for i in range(iterations):
        result = expensive_operation(i)
        if logger.isEnabledFor(logging.INFO):
            logger.info("Operation completed", extra={"iteration": i})
    conditional_log_time = time.time() - start
    
    print(f"Baseline (no logging): {baseline_time:.2f}s")
    print(f"Simple logging: {simple_log_time:.2f}s "
          f"(+{((simple_log_time/baseline_time - 1) * 100):.1f}%)")
    print(f"Structured logging: {structured_log_time:.2f}s "
          f"(+{((structured_log_time/baseline_time - 1) * 100):.1f}%)")
    print(f"Conditional logging: {conditional_log_time:.2f}s "
          f"(+{((conditional_log_time/baseline_time - 1) * 100):.1f}%)")
```

#### Async Logging for Performance
```python
import asyncio
import queue
import threading

class AsyncLogger:
    """High-performance async logger"""
    
    def __init__(self, logger):
        self.logger = logger
        self.queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker)
        self.worker_thread.daemon = True
        self.worker_thread.start()
    
    def _worker(self):
        """Background thread to write logs"""
        while True:
            try:
                record = self.queue.get()
                if record is None:  # Shutdown signal
                    break
                self.logger.handle(record)
            except Exception as e:
                print(f"Logging error: {e}")
    
    def log(self, level, msg, **kwargs):
        """Queue log message for async processing"""
        # Create log record without blocking
        record = self.logger.makeRecord(
            self.logger.name,
            getattr(logging, level.upper()),
            "(async)", 0, msg, (), None, extra=kwargs
        )
        self.queue.put(record)
    
    def shutdown(self):
        """Gracefully shutdown logger"""
        self.queue.put(None)
        self.worker_thread.join()

# Usage for high-throughput scenarios
async_logger = AsyncLogger(logging.getLogger("high_throughput"))

# Non-blocking log calls
for i in range(1000000):
    async_logger.log("info", "Processing item", item_id=i)
```

### Best Practices for Production Logging

#### 1. Use Sampling for High-Volume Events
```python
import random
import hashlib

class SamplingLogger:
    """Logger that samples high-volume events"""
    
    def __init__(self, logger, sample_rate=0.1):
        self.logger = logger
        self.sample_rate = sample_rate
    
    def should_sample(self, key=None):
        """Determine if event should be logged"""
        if key:
            # Consistent sampling for same key
            hash_value = int(hashlib.md5(key.encode()).hexdigest(), 16)
            return (hash_value % 100) < (self.sample_rate * 100)
        else:
            # Random sampling
            return random.random() < self.sample_rate
    
    def log_sampled(self, level, msg, sample_key=None, **kwargs):
        """Log with sampling"""
        if self.should_sample(sample_key):
            kwargs["sampled"] = True
            kwargs["sample_rate"] = self.sample_rate
            getattr(self.logger, level)(msg, extra=kwargs)

# Use sampling for high-volume events
sampler = SamplingLogger(logger, sample_rate=0.01)  # 1% sampling

# High-volume event (millions per day)
for user_id in user_ids:
    sampler.log_sampled(
        "info",
        "Page view",
        sample_key=user_id,  # Consistent sampling per user
        page="/home",
        user_id=user_id
    )
```

#### 2. Buffer and Batch Logs
```python
class BatchLogger:
    """Buffer logs and write in batches"""
    
    def __init__(self, logger, batch_size=100, flush_interval=5):
        self.logger = logger
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.buffer = []
        self.last_flush = time.time()
        self.lock = threading.Lock()
    
    def log(self, level, msg, **kwargs):
        """Add to buffer"""
        with self.lock:
            self.buffer.append({
                "timestamp": datetime.utcnow().isoformat(),
                "level": level,
                "message": msg,
                **kwargs
            })
            
            if (len(self.buffer) >= self.batch_size or 
                time.time() - self.last_flush > self.flush_interval):
                self.flush()
    
    def flush(self):
        """Write buffered logs"""
        if not self.buffer:
            return
        
        # Write as single batch entry
        self.logger.info("Batch log entry", extra={
            "batch_size": len(self.buffer),
            "events": self.buffer
        })
        
        self.buffer = []
        self.last_flush = time.time()
```

#### 3. Optimize Serialization
```python
import orjson  # Faster JSON library

class OptimizedJsonFormatter(logging.Formatter):
    """High-performance JSON formatter"""
    
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage()
        }
        
        # Add extra fields efficiently
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if key not in ["name", "msg", "args", "created", "filename",
                              "funcName", "levelname", "levelno", "lineno",
                              "module", "msecs", "pathname", "process",
                              "processName", "relativeCreated", "thread",
                              "threadName", "exc_info", "exc_text", "stack_info"]:
                    # Handle non-serializable objects
                    try:
                        json.dumps(value)  # Test serializability
                        log_data[key] = value
                    except:
                        log_data[key] = str(value)
        
        # Use faster JSON library
        return orjson.dumps(log_data).decode("utf-8")
```

### Logging Architecture Best Practices

#### 1. Centralized Configuration
```python
# logging_config.py
import os
import logging.config

def setup_logging():
    """Centralized logging configuration"""
    
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(timestamp)s %(level)s %(name)s %(message)s"
            },
            "simple": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "simple",
                "stream": "ext://sys.stdout"
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "json",
                "filename": "logs/app.log",
                "maxBytes": 104857600,  # 100MB
                "backupCount": 5
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "json",
                "filename": "logs/errors.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5
            }
        },
        "loggers": {
            "multi_agent": {
                "level": os.getenv("LOG_LEVEL", "INFO"),
                "handlers": ["console", "file", "error_file"],
                "propagate": False
            },
            "multi_agent.performance": {
                "level": "DEBUG",
                "handlers": ["file"],
                "propagate": False
            }
        },
        "root": {
            "level": "INFO",
            "handlers": ["console", "file"]
        }
    }
    
    logging.config.dictConfig(config)
```

#### 2. Correlation IDs Across Services
```python
import uuid
from contextvars import ContextVar

# Thread-safe context variable
correlation_id = ContextVar("correlation_id", default=None)

class CorrelationMiddleware:
    """Add correlation ID to all requests"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Get or create correlation ID
            headers = dict(scope["headers"])
            corr_id = headers.get(b"x-correlation-id", str(uuid.uuid4()).encode())
            
            # Set in context
            correlation_id.set(corr_id.decode())
            
            # Add to response headers
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    headers = message.setdefault("headers", [])
                    headers.append((b"x-correlation-id", corr_id))
                await send(message)
            
            await self.app(scope, receive, send_wrapper)
        else:
            await self.app(scope, receive, send)

# Use in logging
class CorrelationFilter(logging.Filter):
    """Add correlation ID to all log records"""
    
    def filter(self, record):
        record.correlation_id = correlation_id.get() or "no-correlation"
        return True
```

## Common Mistakes to Avoid

### 1. The "Logger Bomb" 💣
```python
# ❌ BAD: Creating logger in hot path
def process_item(item):
    logger = logging.getLogger(f"processor.{item.id}")  # New logger per item!
    logger.info(f"Processing {item.id}")
    # This creates thousands of logger objects!

# ✅ GOOD: Reuse loggers
logger = logging.getLogger("processor")

def process_item(item):
    logger.info("Processing item", extra={"item_id": item.id})
```

### 2. The "String Concatenation Trap" 🪤
```python
# ❌ BAD: Expensive string operations even when not logging
logger.debug(f"Processing {len(huge_list)} items: {huge_list}")  # Formats even if DEBUG is off!

# ✅ GOOD: Lazy evaluation
if logger.isEnabledFor(logging.DEBUG):
    logger.debug(f"Processing {len(huge_list)} items: {huge_list}")

# ✅ BETTER: Use lazy formatting
logger.debug("Processing %d items", len(huge_list))  # Only formats if needed
```

### 3. The "Exception Eater" 🍽️
```python
# ❌ BAD: Losing exception information
try:
    risky_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}")  # Stack trace lost!

# ✅ GOOD: Preserve stack traces
try:
    risky_operation()
except Exception as e:
    logger.error("Operation failed", exc_info=True)  # Full stack trace included
    # or
    logger.exception("Operation failed")  # Shorthand for exc_info=True
```

### 4. The "Sensitive Data Leak" 🔓
```python
# ❌ BAD: Logging sensitive information
logger.info(f"User login", extra={
    "username": username,
    "password": password,  # NEVER DO THIS
    "credit_card": card_number,  # OR THIS
    "ssn": social_security  # OR THIS
})

# ✅ GOOD: Sanitize sensitive data
logger.info("User login", extra={
    "username": username,
    "auth_method": "password",
    "card_last_four": card_number[-4:] if card_number else None,
    "has_ssn": bool(social_security)
})
```

### 5. The "Log File Explosion" 💥
```python
# ❌ BAD: No rotation = disk full
handler = logging.FileHandler("app.log")  # Grows forever!

# ✅ GOOD: Rotate logs
handler = logging.handlers.RotatingFileHandler(
    "app.log",
    maxBytes=100_000_000,  # 100MB
    backupCount=5  # Keep 5 old files
)

# ✅ BETTER: Time-based rotation
handler = logging.handlers.TimedRotatingFileHandler(
    "app.log",
    when="midnight",  # Rotate daily
    interval=1,
    backupCount=30  # Keep 30 days
)
```

### 6. The "Synchronous Bottleneck" 🚧
```python
# ❌ BAD: Blocking on slow log destinations
class SlowHandler(logging.Handler):
    def emit(self, record):
        # Synchronous network call
        requests.post("https://slow-log-api.com", 
                     json=self.format(record))  # Blocks!

# ✅ GOOD: Async or queued logging
import queue
import threading

class AsyncHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.queue = queue.Queue()
        self.worker = threading.Thread(target=self._worker)
        self.worker.start()
    
    def emit(self, record):
        self.queue.put(record)  # Non-blocking
    
    def _worker(self):
        while True:
            record = self.queue.get()
            # Send to slow destination in background
            self._send_log(record)
```

### 7. The "Context Loss" 😕
```python
# ❌ BAD: Losing context across function calls
def process_order(order_id):
    logger.info(f"Processing order {order_id}")
    validate_order(order_id)
    charge_payment(order_id)
    ship_order(order_id)

def validate_order(order_id):
    logger.info("Validating order")  # Which order??

# ✅ GOOD: Maintain context
import contextvars

order_context = contextvars.ContextVar("order_id")

def process_order(order_id):
    order_context.set(order_id)
    logger.info("Processing order", extra={"order_id": order_id})
    validate_order()
    charge_payment()
    ship_order()

def validate_order():
    order_id = order_context.get()
    logger.info("Validating order", extra={"order_id": order_id})
```

### 8. The "Metrics vs Logs Confusion" 📊
```python
# ❌ BAD: Using logs for metrics
for request in requests:
    logger.info("Request processed")  # Counting requests via logs?

# Later: grep "Request processed" app.log | wc -l  # Inefficient!

# ✅ GOOD: Use proper metrics
from prometheus_client import Counter

request_counter = Counter("requests_total", "Total requests processed")

for request in requests:
    request_counter.inc()
    # Log only interesting events
    if request.is_suspicious():
        logger.warning("Suspicious request", extra={"request_id": request.id})
```

### Summary: The Golden Rules of Logging

1. **Log at the right level** - Don't use ERROR for warnings
2. **Include context** - Always add relevant fields
3. **Be consistent** - Use the same field names everywhere
4. **Think about the reader** - Will someone understand this at 3 AM?
5. **Performance matters** - Don't let logging slow you down
6. **Security first** - Never log sensitive data
7. **Plan for scale** - Your logs will grow, be ready
8. **Test your logging** - It's code too, it needs testing

Remember: **Good logging is like good documentation - you'll thank yourself later!**

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