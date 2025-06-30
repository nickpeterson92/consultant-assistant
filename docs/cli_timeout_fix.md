# CLI Timeout Fix for Workflow Operations

## Problem
When executing workflows that take longer than 60 seconds, the CLI client would timeout and automatically retry with stale context, causing duplicate workflow executions.

### Root Cause
1. Workflow execution took 61+ seconds
2. Socket read timeout was set to 60 seconds (even though total timeout was 120s)
3. When socket read timeout fired, client retried with the same `interrupted_workflow` context
4. Server processed both requests, executing the workflow twice

## Solution
1. **Increased socket read timeout**: Set to 120 seconds in system_config.json to match total timeout
2. **Clear stale context on ANY timeout**: If a timeout occurs (socket or total), clear `interrupted_workflow` from context to prevent duplicate executions

### Implementation Details
```json
// system_config.json
"a2a": {
  "timeout": 120,              // Total timeout
  "sock_read_timeout": 120,    // Socket read timeout (was 60)
  ...
}
```

```python
// orchestrator_cli.py - Timeout handler
except Exception as e:
    is_timeout = isinstance(e, asyncio.TimeoutError) or "timed out" in str(e).lower()
    
    if is_timeout and interrupted_workflow:
        logger.warning("Clearing interrupted workflow due to timeout", ...)
        interrupted_workflow = None
        context.pop('interrupted_workflow', None)
        print("Request timed out. Workflow context cleared.")
```

## Safety Analysis
Clearing `interrupted_workflow` on timeout is safe because:
- It only affects workflow state, not conversation history
- The server is the source of truth for workflow state
- If the workflow completed server-side, we don't need the stale context
- If the workflow is still waiting for input, the user will see the prompt again
- Other context (thread_id, source) remains intact

## Key Learning
The A2A client has multiple timeout settings:
- `timeout`: Total request timeout
- `sock_read_timeout`: Socket read timeout (must be >= total timeout)
- `connect_timeout`: Connection establishment timeout

The socket read timeout was triggering before the total timeout, causing premature retries.