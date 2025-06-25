# A2A Protocol Documentation: A Practical Guide for Junior Engineers

## What is A2A Protocol and Why It Matters

### Introduction for Beginners

The Agent-to-Agent (A2A) Protocol is like a universal language that allows AI agents to talk to each other. Think of it as similar to how microservices communicate via REST APIs, but specifically designed for autonomous AI agents that need to collaborate on complex tasks.

**Real-world analogy**: Imagine a company where different departments (Sales, HR, Finance) need to work together. Each department has its own expertise, but they need a standard way to communicate. The A2A protocol is that communication standard for AI agents.

### Why A2A Protocol Matters

1. **Scalability**: Add new specialized agents without modifying existing ones
2. **Reliability**: Built-in error handling and recovery mechanisms
3. **Flexibility**: Agents can discover each other's capabilities dynamically
4. **Performance**: Connection pooling and efficient resource management
5. **Debugging**: Structured logging makes troubleshooting easier

### Core Concepts (Simple Explanations)

- **Agent**: A specialized AI service that does one thing well (e.g., Salesforce operations)
- **Task**: A unit of work sent from one agent to another
- **Artifact**: The result or output from completing a task
- **Agent Card**: Like a business card that describes what an agent can do
- **Circuit Breaker**: A safety mechanism that prevents system overload

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

## Step-by-Step Implementation Guide

### Step 1: Understanding the Basics

Before coding, understand these key files in our codebase:
- `src/a2a/protocol.py` - The core A2A implementation
- `src/agents/salesforce/main.py` - Example of an A2A-enabled agent
- `src/orchestrator/agent_caller_tools.py` - How to call A2A agents

### Step 2: Creating Your First A2A Agent

Here's a complete example of a minimal A2A agent:

```python
# my_first_agent.py
import asyncio
from typing import Dict, Any
from src.a2a.protocol import A2AServer, AgentCard

class SimpleAgentHandler:
    """Your agent's business logic goes here"""
    
    async def process_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming tasks from other agents"""
        
        # Extract task information
        task = params.get("task", {})
        instruction = task.get("instruction", "")
        
        # Log what we're doing (always log!)
        print(f"Received task: {instruction}")
        
        # Do your agent's work here
        if "hello" in instruction.lower():
            result = "Hello! I'm a simple A2A agent."
        else:
            result = f"I processed your request: {instruction}"
        
        # Return result as an artifact
        return {
            "artifacts": [{
                "id": f"result-{task.get('id', 'unknown')}",
                "task_id": task.get("id"),
                "content": result,
                "content_type": "text/plain"
            }],
            "status": "completed"
        }
    
    async def get_agent_card(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Describe what your agent can do"""
        return {
            "name": "simple-agent",
            "version": "1.0.0",
            "description": "A simple agent that responds to greetings",
            "capabilities": ["greeting", "echo"],
            "endpoints": {
                "process_task": "/a2a",
                "agent_card": "/a2a/agent-card"
            },
            "communication_modes": ["synchronous"]
        }

async def main():
    # Create your agent card
    agent_card = AgentCard(
        name="simple-agent",
        version="1.0.0",
        description="A simple greeting agent",
        capabilities=["greeting", "echo"],
        endpoints={"process_task": "/a2a", "agent_card": "/a2a/agent-card"},
        communication_modes=["synchronous"]
    )
    
    # Create handler
    handler = SimpleAgentHandler()
    
    # Create and configure server
    server = A2AServer(agent_card, "0.0.0.0", 8002)
    server.register_handler("process_task", handler.process_task)
    server.register_handler("get_agent_card", handler.get_agent_card)
    
    # Start the server
    print("Starting Simple A2A Agent on port 8002...")
    await server.start()

if __name__ == "__main__":
    asyncio.run(main())
```

### Step 3: Testing Your Agent Locally

First, start your agent:
```bash
python my_first_agent.py
```

Then test it with curl:
```bash
# Test the agent card endpoint
curl http://localhost:8002/a2a/agent-card

# Test task processing
curl -X POST http://localhost:8002/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "process_task",
    "params": {
      "task": {
        "id": "test-123",
        "instruction": "Say hello to the world"
      }
    },
    "id": "req-1"
  }'
```

### Step 4: Calling Your Agent from Another Agent

Here's how to call your agent from Python code:

```python
# client_example.py
import asyncio
import uuid
from src.a2a.protocol import A2AClient, A2ATask

async def call_my_agent():
    # Create A2A client
    async with A2AClient(timeout=30) as client:
        # Create a task
        task = A2ATask(
            id=str(uuid.uuid4()),
            instruction="Say hello to the world",
            context={"user": "junior_dev"},
            artifacts=[]  # No input artifacts for this simple task
        )
        
        try:
            # Call the agent
            result = await client.call_agent(
                agent_url="http://localhost:8002/a2a",
                task=task
            )
            
            # Process the response
            print(f"Task status: {result.get('status')}")
            for artifact in result.get('artifacts', []):
                print(f"Result: {artifact['content']}")
                
        except Exception as e:
            print(f"Error calling agent: {e}")

if __name__ == "__main__":
    asyncio.run(call_my_agent())
```

### Step 5: Integrating with the Orchestrator

To make your agent discoverable by the orchestrator:

1. Add your agent to `agent_registry.json`:
```json
{
  "agents": [
    {
      "name": "simple-agent",
      "host": "localhost",
      "port": 8002,
      "capabilities": ["greeting", "echo"],
      "health_check_endpoint": "/a2a/agent-card",
      "enabled": true
    }
  ]
}
```

2. Create a tool in the orchestrator to call your agent:
```python
# In src/orchestrator/agent_caller_tools.py
simple_agent_tool = ToolAssistantToolSpec(
    name="simple_agent",
    description="A simple agent for greetings and echoing",
    capabilities=["greeting", "echo"],
    agent_url="http://localhost:8002/a2a"
)
```

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

## Message Format Examples with Detailed Explanations

### Example 1: Basic Task Request

Here's what a complete A2A request looks like:

```json
{
  "jsonrpc": "2.0",                    // Always use JSON-RPC 2.0
  "method": "process_task",            // The method to call
  "params": {
    "task": {
      "id": "550e8400-e29b-41d4-a716-446655440000",  // Unique UUID
      "instruction": "Get all contacts for Acme Corp",
      "context": {
        "user_id": "user123",          // Who initiated this
        "session_id": "session456",    // For tracking
        "priority": "normal"           // Optional metadata
      },
      "state_snapshot": {              // Preserve conversation state
        "memory": {
          "accounts": ["Acme Corp"],
          "last_action": "viewed_accounts"
        }
      },
      "artifacts": []                  // Input from previous tasks
    }
  },
  "id": "request-001"                  // Request ID for matching response
}
```

**Key Points:**
- The `id` field in the task should be a UUID (use `uuid.uuid4()`)
- The `instruction` is natural language - write it like you're asking a human
- `context` carries metadata that might be useful for the agent
- `state_snapshot` preserves memory/conversation state between agents
- The outer `id` field is for matching requests with responses

### Example 2: Task with Input Artifacts

When chaining tasks, you pass outputs as inputs:

```json
{
  "jsonrpc": "2.0",
  "method": "process_task",
  "params": {
    "task": {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "instruction": "Create a summary report for these contacts",
      "context": {
        "user_id": "user123",
        "format": "markdown"           // Specify output format
      },
      "artifacts": [                   // Results from previous task
        {
          "id": "artifact-001",
          "task_id": "550e8400-e29b-41d4-a716-446655440000",
          "content": "[{\"name\": \"John Doe\", \"email\": \"john@acme.com\"}]",
          "content_type": "application/json",
          "metadata": {
            "source": "salesforce",
            "record_count": 1
          }
        }
      ]
    }
  },
  "id": "request-002"
}
```

**Key Points:**
- Artifacts contain the actual data from previous operations
- Always include `content_type` so the receiving agent knows how to parse
- Use `metadata` for additional context about the artifact

### Example 3: Successful Response

Here's what you get back from a successful task:

```json
{
  "jsonrpc": "2.0",
  "result": {
    "status": "completed",             // or "failed", "partial"
    "artifacts": [
      {
        "id": "result-660e8400-e29b-41d4-a716-446655440001",
        "task_id": "660e8400-e29b-41d4-a716-446655440001",
        "content": "# Contact Summary\n\n- John Doe (john@acme.com)",
        "content_type": "text/markdown",
        "metadata": {
          "generated_at": "2024-01-15T10:30:00Z",
          "word_count": 8
        }
      }
    ],
    "messages": [                      // Optional status messages
      {
        "role": "assistant",
        "content": "Successfully generated summary for 1 contact"
      }
    ]
  },
  "id": "request-002"
}
```

**Key Points:**
- The response `id` must match the request `id`
- `status` indicates if the task completed successfully
- Multiple artifacts can be returned
- `messages` provide human-readable status updates

### Example 4: Error Response

When things go wrong, you get structured errors:

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32603,                    // Standard JSON-RPC error code
    "message": "Internal error",       // Human-readable message
    "data": {                          // Additional error details
      "exception": "ConnectionError",
      "details": "Unable to connect to Salesforce API",
      "task_id": "660e8400-e29b-41d4-a716-446655440001",
      "timestamp": "2024-01-15T10:30:00Z"
    }
  },
  "id": "request-002"
}
```

**Standard Error Codes:**
- `-32700`: Parse error (invalid JSON)
- `-32600`: Invalid request
- `-32601`: Method not found
- `-32602`: Invalid params
- `-32603`: Internal error

### Example 5: Agent Card Response

When you query an agent's capabilities:

```json
{
  "jsonrpc": "2.0",
  "result": {
    "name": "salesforce-agent",
    "version": "1.2.0",
    "description": "Handles all Salesforce CRM operations",
    "capabilities": [
      "salesforce_operations",
      "lead_management",
      "account_management",
      "opportunity_tracking"
    ],
    "endpoints": {
      "process_task": "/a2a",
      "agent_card": "/a2a/agent-card",
      "health": "/health"              // Optional health check
    },
    "communication_modes": ["synchronous"],
    "metadata": {
      "max_batch_size": 100,           // Agent-specific limits
      "supported_objects": ["Lead", "Account", "Contact", "Opportunity"],
      "rate_limit": "1000/hour"
    }
  },
  "id": "card-request-001"
}
```

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

## Common Implementation Mistakes

### Mistake 1: Forgetting to Use UUIDs for Task IDs

❌ **Wrong:**
```python
task = A2ATask(
    id="task-1",  # This is not unique!
    instruction="Do something"
)
```

✅ **Correct:**
```python
import uuid
task = A2ATask(
    id=str(uuid.uuid4()),  # Globally unique identifier
    instruction="Do something"
)
```

**Why it matters:** Non-unique IDs cause confusion when tracking tasks across distributed systems.

### Mistake 2: Not Handling Connection Timeouts Properly

❌ **Wrong:**
```python
# Using default timeout for everything
client = A2AClient()  # No timeout specified!
```

✅ **Correct:**
```python
# Specify appropriate timeouts
client = A2AClient(timeout=30)  # 30 seconds for normal operations
health_client = A2AClient(timeout=10)  # 10 seconds for health checks
```

**Why it matters:** Different operations need different timeouts. Health checks should fail fast, while complex operations may need more time.

### Mistake 3: Ignoring Circuit Breaker States

❌ **Wrong:**
```python
# Just keep retrying forever
while True:
    try:
        result = await client.call_agent(url, task)
        break
    except Exception:
        continue  # This will hammer a dead service!
```

✅ **Correct:**
```python
# Respect circuit breaker
try:
    result = await client.call_agent(url, task)
except CircuitBreakerOpen:
    # Try a different agent or fail gracefully
    logger.warning(f"Agent {url} is unavailable")
    return fallback_response()
```

**Why it matters:** Circuit breakers prevent cascading failures. When they're open, the service is down - stop trying!

### Mistake 4: Not Preserving State Between Agents

❌ **Wrong:**
```python
task = A2ATask(
    id=str(uuid.uuid4()),
    instruction="Continue our previous conversation",
    # No state_snapshot - agent has no context!
)
```

✅ **Correct:**
```python
task = A2ATask(
    id=str(uuid.uuid4()),
    instruction="Continue our previous conversation",
    state_snapshot={
        "conversation_history": previous_messages,
        "user_context": user_data,
        "memory": extracted_facts
    }
)
```

**Why it matters:** Agents are stateless. Without state_snapshot, they can't maintain context.

### Mistake 5: Poor Error Messages

❌ **Wrong:**
```python
except Exception as e:
    return {"error": "Something went wrong"}  # Not helpful!
```

✅ **Correct:**
```python
except ValidationError as e:
    return {
        "jsonrpc": "2.0",
        "error": {
            "code": -32602,
            "message": "Invalid parameters",
            "data": {
                "field": e.field_name,
                "reason": str(e),
                "expected": e.expected_type,
                "received": e.received_value
            }
        },
        "id": request_id
    }
```

**Why it matters:** Good error messages make debugging much easier across distributed systems.

### Mistake 6: Blocking the Event Loop

❌ **Wrong:**
```python
async def process_task(self, params):
    # This blocks the entire event loop!
    result = requests.get("http://slow-api.com")  
    return {"result": result.text}
```

✅ **Correct:**
```python
async def process_task(self, params):
    # Use async libraries
    async with aiohttp.ClientSession() as session:
        async with session.get("http://slow-api.com") as response:
            result = await response.text()
    return {"result": result}
```

**Why it matters:** Blocking operations kill performance in async systems.

### Mistake 7: Not Validating Input

❌ **Wrong:**
```python
async def process_task(self, params):
    task = params["task"]  # KeyError if 'task' missing!
    instruction = task["instruction"]  # Another potential KeyError!
```

✅ **Correct:**
```python
async def process_task(self, params):
    # Validate first
    if not params or "task" not in params:
        raise ValidationError("Missing 'task' parameter")
    
    task = params["task"]
    instruction = task.get("instruction", "")
    
    if not instruction:
        raise ValidationError("Task instruction cannot be empty")
```

**Why it matters:** Invalid input is the #1 cause of agent failures. Always validate!

### Mistake 8: Memory Leaks in Connection Pools

❌ **Wrong:**
```python
# Creating new clients without cleanup
async def call_many_agents():
    for i in range(1000):
        client = A2AClient()  # New connection pool each time!
        await client.call_agent(...)
        # No cleanup!
```

✅ **Correct:**
```python
# Reuse clients or ensure cleanup
async def call_many_agents():
    async with A2AClient() as client:  # Auto cleanup
        for i in range(1000):
            await client.call_agent(...)
```

**Why it matters:** Connection pools consume memory and file descriptors. Always clean up!

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

## Testing A2A Endpoints

### Unit Testing Your Agent

Here's a complete test suite for an A2A agent:

```python
# test_my_agent.py
import pytest
import asyncio
import json
from unittest.mock import Mock, patch
from my_agent import SimpleAgentHandler

class TestSimpleAgent:
    @pytest.fixture
    def handler(self):
        return SimpleAgentHandler()
    
    @pytest.mark.asyncio
    async def test_process_task_hello(self, handler):
        """Test that hello messages get special response"""
        params = {
            "task": {
                "id": "test-123",
                "instruction": "Say hello to the test suite",
                "context": {"test": True}
            }
        }
        
        result = await handler.process_task(params)
        
        # Verify response structure
        assert result["status"] == "completed"
        assert len(result["artifacts"]) == 1
        assert "Hello!" in result["artifacts"][0]["content"]
    
    @pytest.mark.asyncio
    async def test_process_task_echo(self, handler):
        """Test echo functionality"""
        params = {
            "task": {
                "id": "test-456",
                "instruction": "Echo this message"
            }
        }
        
        result = await handler.process_task(params)
        
        assert result["status"] == "completed"
        assert "Echo this message" in result["artifacts"][0]["content"]
    
    @pytest.mark.asyncio
    async def test_missing_task_parameter(self, handler):
        """Test error handling for missing parameters"""
        params = {}  # Missing 'task'
        
        with pytest.raises(KeyError):
            await handler.process_task(params)
    
    @pytest.mark.asyncio
    async def test_agent_card(self, handler):
        """Test agent card returns correct capabilities"""
        result = await handler.get_agent_card({})
        
        assert result["name"] == "simple-agent"
        assert "greeting" in result["capabilities"]
        assert result["version"] == "1.0.0"
```

### Integration Testing with Real HTTP Calls

```python
# test_integration.py
import aiohttp
import asyncio
import pytest
from src.a2a.protocol import A2AClient, A2ATask

class TestA2AIntegration:
    @pytest.fixture
    async def client(self):
        client = A2AClient(timeout=30)
        yield client
        await client.close()
    
    @pytest.mark.asyncio
    async def test_real_agent_call(self, client):
        """Test calling a real running agent"""
        # Make sure your agent is running on port 8002!
        task = A2ATask(
            id="integration-test-001",
            instruction="Hello from integration test",
            context={"test_run": True}
        )
        
        try:
            result = await client.call_agent(
                "http://localhost:8002/a2a",
                task
            )
            
            assert result["status"] == "completed"
            assert len(result.get("artifacts", [])) > 0
            
        except aiohttp.ClientConnectorError:
            pytest.skip("Agent not running on port 8002")
    
    @pytest.mark.asyncio
    async def test_agent_discovery(self, client):
        """Test agent card endpoint"""
        try:
            agent_card = await client.get_agent_card(
                "http://localhost:8002/a2a/agent-card"
            )
            
            assert agent_card["name"] == "simple-agent"
            assert "capabilities" in agent_card
            
        except aiohttp.ClientConnectorError:
            pytest.skip("Agent not running")
```

### Load Testing Your Agent

```python
# load_test.py
import asyncio
import time
import statistics
from src.a2a.protocol import A2AClient, A2ATask

async def single_request(client, agent_url, request_num):
    """Make a single request and return timing"""
    start = time.time()
    
    task = A2ATask(
        id=f"load-test-{request_num}",
        instruction=f"Load test request {request_num}"
    )
    
    try:
        result = await client.call_agent(agent_url, task)
        duration = time.time() - start
        return {"success": True, "duration": duration}
    except Exception as e:
        duration = time.time() - start
        return {"success": False, "duration": duration, "error": str(e)}

async def load_test(agent_url, num_requests=100, concurrent=10):
    """Run load test against an agent"""
    async with A2AClient(timeout=30) as client:
        # Create batches of concurrent requests
        results = []
        
        for batch_start in range(0, num_requests, concurrent):
            batch_tasks = []
            
            for i in range(batch_start, min(batch_start + concurrent, num_requests)):
                batch_tasks.append(single_request(client, agent_url, i))
            
            batch_results = await asyncio.gather(*batch_tasks)
            results.extend(batch_results)
        
        # Analyze results
        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]
        durations = [r["duration"] for r in successful]
        
        print(f"\nLoad Test Results:")
        print(f"Total Requests: {num_requests}")
        print(f"Successful: {len(successful)}")
        print(f"Failed: {len(failed)}")
        
        if durations:
            print(f"Average Duration: {statistics.mean(durations):.3f}s")
            print(f"Min Duration: {min(durations):.3f}s")
            print(f"Max Duration: {max(durations):.3f}s")
            print(f"Median Duration: {statistics.median(durations):.3f}s")

if __name__ == "__main__":
    asyncio.run(load_test("http://localhost:8002/a2a"))
```

### Testing with Mock Agents

```python
# mock_agent.py
from aiohttp import web
import json

async def mock_process_task(request):
    """Mock agent that always returns success"""
    data = await request.json()
    
    return web.json_response({
        "jsonrpc": "2.0",
        "result": {
            "status": "completed",
            "artifacts": [{
                "id": "mock-result",
                "task_id": data["params"]["task"]["id"],
                "content": "Mock response",
                "content_type": "text/plain"
            }]
        },
        "id": data.get("id")
    })

# Create a simple mock agent for testing
app = web.Application()
app.router.add_post('/a2a', mock_process_task)

if __name__ == "__main__":
    web.run_app(app, port=9999)
```

## Debugging A2A Communication Issues

### Step-by-Step Debugging Guide

#### 1. Enable Debug Logging

First, enable comprehensive logging to see what's happening:

```python
# In your agent startup
import logging
import colorlog

# Configure colored logging for better visibility
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

logger = logging.getLogger('a2a')
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)
```

#### 2. Use Network Debugging Tools

**Option A: tcpdump/Wireshark**
```bash
# Capture A2A traffic on port 8002
sudo tcpdump -i lo0 -w a2a_traffic.pcap port 8002

# Then open in Wireshark for analysis
```

**Option B: mitmproxy for HTTP debugging**
```bash
# Install mitmproxy
pip install mitmproxy

# Run proxy
mitmproxy -p 8888

# Configure your A2A client to use proxy
client = A2AClient(proxy="http://localhost:8888")
```

#### 3. Add Request/Response Logging

```python
# debug_client.py
import json
from src.a2a.protocol import A2AClient

class DebugA2AClient(A2AClient):
    """A2A Client with detailed logging"""
    
    async def call_agent(self, agent_url, task):
        # Log the request
        print("\n=== A2A REQUEST ===")
        print(f"URL: {agent_url}")
        print(f"Task ID: {task.id}")
        print(f"Instruction: {task.instruction}")
        print(f"Context: {json.dumps(task.context, indent=2)}")
        
        try:
            # Make the actual call
            result = await super().call_agent(agent_url, task)
            
            # Log the response
            print("\n=== A2A RESPONSE ===")
            print(f"Status: {result.get('status')}")
            print(f"Artifacts: {len(result.get('artifacts', []))}")
            for artifact in result.get('artifacts', []):
                print(f"  - {artifact['id']}: {artifact['content'][:100]}...")
            
            return result
            
        except Exception as e:
            print(f"\n=== A2A ERROR ===")
            print(f"Exception: {type(e).__name__}")
            print(f"Details: {str(e)}")
            raise
```

#### 4. Common Debugging Scenarios

**Scenario 1: "Connection Refused" Errors**
```python
# debug_connection.py
import aiohttp
import asyncio

async def debug_connection(url):
    """Test basic connectivity"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{url}/a2a/agent-card") as resp:
                print(f"Status: {resp.status}")
                print(f"Headers: {dict(resp.headers)}")
                data = await resp.json()
                print(f"Agent: {data.get('name')}")
    except aiohttp.ClientConnectorError as e:
        print(f"Connection failed: {e}")
        print("Check if agent is running and port is correct")

asyncio.run(debug_connection("http://localhost:8002"))
```

**Scenario 2: "Timeout" Issues**
```python
# debug_timeout.py
async def debug_timeouts():
    """Test different timeout scenarios"""
    
    # Test health check (should be fast)
    start = time.time()
    try:
        async with A2AClient(timeout=5) as client:
            await client.get_agent_card("http://localhost:8002/a2a/agent-card")
        print(f"Health check took: {time.time() - start:.2f}s")
    except asyncio.TimeoutError:
        print("Health check timed out - agent may be overloaded")
    
    # Test actual task (may be slower)
    start = time.time()
    try:
        async with A2AClient(timeout=30) as client:
            task = A2ATask(id="timeout-test", instruction="Complex task")
            await client.call_agent("http://localhost:8002/a2a", task)
        print(f"Task took: {time.time() - start:.2f}s")
    except asyncio.TimeoutError:
        print("Task timed out - consider increasing timeout")
```

**Scenario 3: "Circuit Breaker Open" Errors**
```python
# debug_circuit_breaker.py
from src.utils.circuit_breaker import CircuitBreaker

# Check circuit breaker state
cb = CircuitBreaker(failure_threshold=5, timeout=60)
print(f"Circuit Breaker State: {cb.state}")
print(f"Failure Count: {cb.failure_count}")
print(f"Last Failure: {cb.last_failure_time}")

# Force reset if needed (for debugging only!)
cb.reset()
```

#### 5. Performance Profiling

```python
# profile_agent.py
import cProfile
import pstats
import asyncio

async def profile_agent_calls():
    """Profile A2A calls to find bottlenecks"""
    client = A2AClient()
    
    for i in range(10):
        task = A2ATask(id=f"profile-{i}", instruction="Test")
        await client.call_agent("http://localhost:8002/a2a", task)

# Run profiler
profiler = cProfile.Profile()
profiler.enable()

asyncio.run(profile_agent_calls())

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 time-consuming functions
```

### Debug Checklist

When debugging A2A issues, go through this checklist:

1. ✓ **Is the agent running?** Check with `ps aux | grep python`
2. ✓ **Is the port open?** Check with `lsof -i :8002`
3. ✓ **Can you reach the health endpoint?** Try `curl http://localhost:8002/a2a/agent-card`
4. ✓ **Are there any firewalls blocking?** Check system firewall rules
5. ✓ **Is the JSON valid?** Use `jq` to validate: `echo $REQUEST | jq .`
6. ✓ **Are timeouts appropriate?** Health=10s, Normal=30s, Complex=60s+
7. ✓ **Is the circuit breaker open?** Check logs for circuit breaker messages
8. ✓ **Are connection pools exhausted?** Look for "Too many connections" errors
9. ✓ **Is the agent overloaded?** Check CPU/memory with `top` or `htop`
10. ✓ **Are there any unhandled exceptions?** Check agent logs for stack traces

## Future Enhancements

1. **Streaming Support**: Server-sent events for long-running tasks
2. **Binary Artifacts**: Support for non-text content
3. **Request Prioritization**: QoS for critical tasks
4. **Distributed Tracing**: OpenTelemetry integration
5. **gRPC Transport**: Alternative to HTTP for performance

## Quick Reference for Junior Engineers

### Minimal Working Agent (Copy-Paste Ready)

```python
#!/usr/bin/env python3
import asyncio
from typing import Dict, Any
from src.a2a.protocol import A2AServer, AgentCard

class MinimalAgent:
    async def process_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        task = params.get("task", {})
        result = f"Processed: {task.get('instruction', 'no instruction')}"
        
        return {
            "status": "completed",
            "artifacts": [{
                "id": f"result-{task.get('id')}",
                "task_id": task.get("id"),
                "content": result,
                "content_type": "text/plain"
            }]
        }
    
    async def get_agent_card(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "name": "minimal-agent",
            "version": "1.0.0",
            "description": "A minimal A2A agent",
            "capabilities": ["basic"],
            "endpoints": {"process_task": "/a2a", "agent_card": "/a2a/agent-card"},
            "communication_modes": ["synchronous"]
        }

if __name__ == "__main__":
    agent_card = AgentCard(
        name="minimal-agent", version="1.0.0", description="Minimal agent",
        capabilities=["basic"], endpoints={"process_task": "/a2a", "agent_card": "/a2a/agent-card"},
        communication_modes=["synchronous"]
    )
    
    handler = MinimalAgent()
    server = A2AServer(agent_card, "0.0.0.0", 8003)
    server.register_handler("process_task", handler.process_task)
    server.register_handler("get_agent_card", handler.get_agent_card)
    
    print("Starting Minimal Agent on port 8003...")
    asyncio.run(server.start())
```

### Quick Test Commands

```bash
# Test if agent is alive
curl http://localhost:8003/a2a/agent-card

# Send a test task
curl -X POST http://localhost:8003/a2a \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"process_task","params":{"task":{"id":"test-1","instruction":"Hello Agent"}},"id":"1"}'

# Pretty print the response
curl -s http://localhost:8003/a2a/agent-card | python -m json.tool
```

### Common Patterns Cheat Sheet

```python
# Pattern 1: Validate input
if "task" not in params:
    raise ValueError("Missing task parameter")

# Pattern 2: Extract safely
instruction = params.get("task", {}).get("instruction", "")

# Pattern 3: Always return artifacts list
return {
    "status": "completed",
    "artifacts": [...]  # Even if empty!
}

# Pattern 4: Include task_id in artifacts
"task_id": params.get("task", {}).get("id")

# Pattern 5: Use proper content types
"content_type": "application/json"  # for JSON
"content_type": "text/plain"        # for text
"content_type": "text/markdown"     # for markdown

# Pattern 6: Handle errors gracefully
try:
    # your code
except Exception as e:
    return {
        "status": "failed",
        "error": str(e),
        "artifacts": []
    }
```

### Troubleshooting Quick Fixes

```bash
# Problem: Port already in use
lsof -i :8003  # Find what's using it
kill -9 <PID>  # Kill the process

# Problem: Can't import A2A modules
export PYTHONPATH=$PYTHONPATH:/path/to/project

# Problem: Agent not responding
# Check if it's actually running
ps aux | grep minimal-agent

# Problem: JSON parsing errors
# Validate your JSON
echo '{"your":"json"}' | jq .

# Problem: Circuit breaker stuck open
# Check logs for the issue, then restart agent
```

### Remember These Key Points

1. **Always use UUIDs** for task IDs: `str(uuid.uuid4())`
2. **Always return artifacts** even if empty: `"artifacts": []`
3. **Always include content_type** in artifacts
4. **Always use async/await** - never block the event loop
5. **Always validate input** - don't trust incoming data
6. **Always log errors** - future you will thank you
7. **Always test locally** before integrating
8. **Always clean up resources** - use context managers
9. **Always handle timeouts** - network calls can fail
10. **Always document your agent's capabilities** clearly

---

*This guide was designed to help junior engineers quickly understand and implement A2A agents. For more details, refer to the sections above or check the example implementations in `src/agents/`.*