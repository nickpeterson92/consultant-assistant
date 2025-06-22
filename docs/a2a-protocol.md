# A2A Protocol Documentation

## Overview

The Agent-to-Agent (A2A) Protocol is an enterprise-grade communication framework that enables reliable, scalable inter-agent communication in distributed multi-agent systems. Built on JSON-RPC 2.0 over HTTP, it provides a standardized way for autonomous agents to collaborate while maintaining loose coupling and fault tolerance.

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        A2A Protocol Stack                       │
├─────────────────────────────────────────────────────────────────┤
│ Application Layer    │ AgentCard, Task, Artifact, Message       │
├─────────────────────────────────────────────────────────────────┤
│ Protocol Layer       │ JSON-RPC 2.0 Request/Response            │
├─────────────────────────────────────────────────────────────────┤
│ Resilience Layer     │ Circuit Breaker, Retry Logic             │
├─────────────────────────────────────────────────────────────────┤
│ Connection Layer     │ Connection Pool, Session Management      │
├─────────────────────────────────────────────────────────────────┤
│ Transport Layer      │ HTTP/HTTPS with aiohttp                  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Loose Coupling**: Agents discover capabilities dynamically without hardcoded dependencies
2. **Fault Tolerance**: Circuit breakers and retry logic handle network failures gracefully
3. **Performance**: Connection pooling reduces latency for high-frequency communication
4. **Observability**: Structured logging enables distributed tracing and debugging
5. **Standards Compliance**: JSON-RPC 2.0 ensures interoperability

## Data Models

### AgentCard
```python
@dataclass
class AgentCard:
    name: str                           # Unique agent identifier
    version: str                        # Semantic version (e.g., "1.0.0")
    description: str                    # Human-readable purpose
    capabilities: List[str]             # e.g., ["salesforce_operations", "crm_management"]
    endpoints: Dict[str, str]           # API endpoints mapping
    communication_modes: List[str]      # e.g., ["synchronous", "streaming"]
    metadata: Optional[Dict[str, Any]]  # Additional configuration
```

**Purpose**: Self-describing manifest for service discovery and capability-based routing.

### A2ATask
```python
@dataclass
class A2ATask:
    id: str                             # Unique task identifier (UUID)
    instruction: str                    # Natural language task description
    context: Dict[str, Any]             # Execution context and parameters
    state_snapshot: Optional[Dict]      # Conversation/memory state
    artifacts: List[A2AArtifact]        # Input artifacts from previous tasks
    metadata: Optional[Dict[str, Any]]  # Task-specific metadata
```

**Purpose**: Represents a unit of work delegated from one agent to another.

### A2AArtifact
```python
@dataclass
class A2AArtifact:
    id: str                             # Unique artifact identifier
    task_id: str                        # Associated task ID
    content: str                        # Artifact content (text, JSON, etc.)
    content_type: str                   # MIME type (e.g., "text/plain")
    metadata: Optional[Dict[str, Any]]  # Additional properties
```

**Purpose**: Immutable outputs produced by agents during task execution.

### A2AMessage
```python
@dataclass
class A2AMessage:
    role: str                           # "user", "assistant", "system"
    content: str                        # Message content
    metadata: Optional[Dict[str, Any]]  # Additional context
```

**Purpose**: Conversation messages for maintaining context across agents.

## Client Implementation

### A2AClient Features

1. **Connection Pooling**
   ```python
   # Pool configuration prevents connection exhaustion
   connector = aiohttp.TCPConnector(
       limit=50,                    # Total pool size
       limit_per_host=20,          # Per-host connections
       ttl_dns_cache=300,          # DNS cache TTL
       keepalive_timeout=30,       # Keep-alive duration
       enable_cleanup_closed=True   # Automatic cleanup
   )
   ```

2. **Circuit Breaker Integration**
   ```python
   # Prevents cascading failures
   circuit_breaker = CircuitBreaker(
       failure_threshold=5,         # Failures before opening
       timeout=60,                 # Open circuit duration
       half_open_max_calls=3       # Test calls when recovering
   )
   ```

3. **Retry Logic**
   ```python
   # Exponential backoff with jitter
   retry_config = RetryConfig(
       max_attempts=3,
       base_delay=1.0,
       max_delay=30.0,
       exponential_base=2
   )
   ```

### Making A2A Calls

```python
# Initialize client with timeout
async with A2AClient(timeout=30) as client:
    # Create task
    task = A2ATask(
        id=str(uuid.uuid4()),
        instruction="Get all contacts for Acme Corp account",
        context={"user_id": "user123"},
        state_snapshot={"memory": current_memory}
    )
    
    # Call agent
    result = await client.call_agent(
        agent_url="http://localhost:8001/a2a",
        task=task
    )
    
    # Process artifacts
    for artifact in result.artifacts:
        print(f"Result: {artifact.content}")
```

## Server Implementation

### A2AServer Architecture

The server provides a framework for agents to handle incoming A2A requests:

1. **Request Routing**: Maps JSON-RPC methods to handler functions
2. **Input Validation**: Ensures requests conform to protocol specification
3. **Error Handling**: Standardized error responses for debugging
4. **Async Processing**: Non-blocking request handling for scalability

### Creating an A2A Agent

```python
class MyAgentHandler:
    async def process_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        task_data = params.get("task", {})
        instruction = task_data.get("instruction", "")
        
        # Process the task
        result = await self.execute_task(instruction)
        
        # Return artifacts
        return {
            "artifacts": [{
                "id": f"result-{task_data.get('id')}",
                "task_id": task_data.get("id"),
                "content": result,
                "content_type": "text/plain"
            }],
            "status": "completed"
        }
    
    async def get_agent_card(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "name": "my-agent",
            "version": "1.0.0",
            "description": "My specialized agent",
            "capabilities": ["my_capability"],
            "endpoints": {
                "process_task": "/a2a",
                "agent_card": "/a2a/agent-card"
            },
            "communication_modes": ["synchronous"]
        }

# Start server
server = A2AServer(agent_card, "0.0.0.0", 8001)
server.register_handler("process_task", handler.process_task)
server.register_handler("get_agent_card", handler.get_agent_card)
await server.start()
```

## Protocol Flow

### Task Execution Flow

```
Orchestrator                    A2A Protocol                    Specialized Agent
     │                               │                                  │
     ├──CREATE TASK─────────────────>│                                  │
     │                               │                                  │
     ├──POST /a2a───────────────────>│                                  │
     │  {method: "process_task",     │                                  │
     │   params: {task: {...}}}      │                                  │
     │                               ├──VALIDATE REQUEST───────────────>│
     │                               │                                  │
     │                               │<─────PROCESS TASK────────────────┤
     │                               │                                  │
     │<──RETURN ARTIFACTS────────────┤<─────RETURN RESULT───────────────┤
     │  {result: {artifacts: [...]}} │                                  │
     │                               │                                  │
```

### Service Discovery Flow

```
Orchestrator                    A2A Protocol                    Agent Registry
     │                               │                                  │
     ├──GET /a2a/agent-card─────────>│                                  │
     │                               │                                  │
     │<──RETURN CAPABILITIES─────────┤                                  │
     │  {name, capabilities, ...}    │                                  │
     │                               │                                  │
     ├──REGISTER AGENT─────────────────────────────────────────────────>│
     │                               │                                  │
```

## Connection Pool Management

### Pool Key Design

The connection pool uses composite keys to prevent timeout mismatches:

```python
# Include timeout in pool key to avoid sharing sessions
pool_key = f"{base_url}_timeout_{timeout}"
```

This prevents health check connections (10s timeout) from being reused for regular requests (30s timeout).

### Resource Management

1. **Connection Limits**: Prevents resource exhaustion
2. **DNS Caching**: Reduces lookup overhead
3. **Keep-Alive**: Maintains persistent connections
4. **Automatic Cleanup**: Removes stale connections

## Error Handling

### Standard Error Responses

```python
# JSON-RPC 2.0 error format
{
    "jsonrpc": "2.0",
    "error": {
        "code": -32603,
        "message": "Internal error",
        "data": {
            "exception": "ConnectionTimeout",
            "details": "Request timed out after 30s"
        }
    },
    "id": "request-123"
}
```

### Error Categories

1. **Transport Errors**: Network failures, timeouts
2. **Protocol Errors**: Invalid JSON-RPC format
3. **Application Errors**: Task processing failures
4. **Validation Errors**: Invalid input parameters

## Resilience Patterns

### Circuit Breaker States

```
CLOSED (Normal Operation)
    │
    ├── Failures >= Threshold
    ▼
OPEN (Fail Fast)
    │
    ├── Timeout Elapsed
    ▼
HALF_OPEN (Testing Recovery)
    │
    ├── Success: → CLOSED
    └── Failure: → OPEN
```

### Retry Strategy

1. **Exponential Backoff**: Delays double with each retry
2. **Jitter**: Random variation prevents thundering herd
3. **Max Attempts**: Prevents infinite retry loops
4. **Selective Retry**: Only retries on transient errors

## Observability

### Structured Logging

All A2A operations generate structured logs:

```json
{
    "timestamp": "2024-01-15T10:30:45.123Z",
    "operation": "A2A_TASK_START",
    "task_id": "abc-123",
    "agent_url": "http://localhost:8001/a2a",
    "timeout": 30,
    "instruction_preview": "Get all contacts for..."
}
```

### Key Metrics

1. **Request Duration**: End-to-end latency tracking
2. **Success Rate**: Percentage of successful calls
3. **Circuit Breaker Status**: Current state per endpoint
4. **Connection Pool Stats**: Active/idle connections
5. **Retry Attempts**: Frequency of retries needed

## Best Practices

### For A2A Clients

1. **Use Connection Pooling**: Reuse connections for efficiency
2. **Set Appropriate Timeouts**: Balance responsiveness vs. tolerance
3. **Handle Errors Gracefully**: Implement fallback strategies
4. **Log Context**: Include task IDs for tracing
5. **Monitor Circuit Breakers**: Alert on repeated failures

### For A2A Servers

1. **Validate Input**: Never trust incoming data
2. **Return Structured Errors**: Aid debugging
3. **Implement Health Checks**: Support monitoring
4. **Use Async Processing**: Maximize throughput
5. **Version Your API**: Support backward compatibility

### For System Design

1. **Design for Failure**: Assume network issues will occur
2. **Keep Agents Stateless**: Simplify scaling and recovery
3. **Use Capability Discovery**: Enable dynamic routing
4. **Monitor Everything**: Observability is crucial
5. **Test Resilience**: Simulate failures regularly

## Configuration

### Environment Variables

```bash
# A2A Client Settings
A2A_TIMEOUT=30                    # Default request timeout
A2A_RETRY_ATTEMPTS=3              # Maximum retry attempts
A2A_CIRCUIT_BREAKER_THRESHOLD=5   # Failures before opening

# Connection Pool Settings
A2A_POOL_SIZE=50                  # Total connections
A2A_POOL_SIZE_PER_HOST=20        # Per-host limit
A2A_KEEPALIVE_TIMEOUT=30         # Keep-alive duration
```

### System Configuration

```json
{
  "a2a": {
    "timeout": 30,
    "health_check_timeout": 10,
    "retry_attempts": 3,
    "retry_delay": 1.0,
    "circuit_breaker_threshold": 5,
    "connection_pool_size": 50,
    "connection_pool_size_per_host": 20
  }
}
```

## Troubleshooting

### Common Issues

1. **10-Second Timeouts on 30-Second Requests**
   - **Cause**: Connection pool key doesn't include timeout
   - **Solution**: Ensure pool keys include timeout value

2. **Circuit Breaker Always Open**
   - **Cause**: Persistent failures or too low threshold
   - **Solution**: Check endpoint health, adjust threshold

3. **Connection Pool Exhaustion**
   - **Cause**: Too many concurrent requests
   - **Solution**: Increase pool size or implement queuing

4. **JSON-RPC Parse Errors**
   - **Cause**: Malformed request/response
   - **Solution**: Validate JSON structure, check content-type

5. **Task Context Loss**
   - **Cause**: Missing state_snapshot in task
   - **Solution**: Include necessary context in task creation

## Future Enhancements

1. **Streaming Support**: Server-sent events for long-running tasks
2. **Binary Artifacts**: Support for non-text content
3. **Request Prioritization**: QoS for critical tasks
4. **Distributed Tracing**: OpenTelemetry integration
5. **gRPC Transport**: Alternative to HTTP for performance