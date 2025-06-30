# Workflow Human-in-the-Loop Implementation Using LangGraph Interrupt

## Overview
Replace our custom `workflow_waiting` state management with LangGraph's native `interrupt` function, which is designed specifically for human-in-the-loop workflows.

## Why This Is The Right Solution

1. **Native Support**: LangGraph's interrupt is designed for exactly this use case
2. **Works in A2A Mode**: Interrupt properly persists state across calls
3. **Resource Efficient**: Paused threads don't consume resources
4. **Clean Architecture**: No custom state fields or workarounds needed
5. **Future Proof**: This is LangGraph's recommended approach as of v0.2.31+

## Implementation Plan

### Step 1: Update Workflow Engine to Use Interrupt
Instead of raising `HumanInputRequiredException`, use the `interrupt` function:

```python
# In src/agents/workflow/engine.py
from langgraph.types import interrupt

async def _handle_human_step(self, step: WorkflowStep, context: Dict[str, Any]) -> Any:
    """Handle human interaction step using LangGraph interrupt."""
    
    # Prepare interaction data
    interaction_data = {
        "step_id": step.id,
        "step_name": step.name,
        "description": step.metadata.get("description", "Human input required"),
        "workflow_id": self.workflow_id,
        "workflow_name": self.workflow_name,
        "context": context
    }
    
    # Use interrupt to pause execution
    human_response = interrupt(interaction_data)
    
    # When resumed, human_response will contain the user's input
    return human_response
```

### Step 2: Update Workflow A2A Handler
The workflow agent's A2A handler needs to detect interrupted state:

```python
# In src/agents/workflow/main.py
result = await workflow_graph.ainvoke(initial_state, config)

# Check if workflow was interrupted for human input
if result.get("__interrupt__"):
    # Return interrupt data to orchestrator
    return {
        "artifacts": [{
            "content": f"WORKFLOW_INTERRUPTED:{json.dumps(result['__interrupt__'])}",
            "content_type": "text/plain"
        }],
        "status": "interrupted"
    }
```

### Step 3: Update Orchestrator to Handle Interrupts
The orchestrator needs to detect interrupted workflows and resume them:

```python
# In src/orchestrator/agent_caller_tools.py (WorkflowAgentTool)
if response_content.startswith("WORKFLOW_INTERRUPTED:"):
    # Extract interrupt data
    interrupt_data = json.loads(response_content.replace("WORKFLOW_INTERRUPTED:", ""))
    
    # Return formatted message to user
    message = format_human_input_request(interrupt_data)
    
    # Mark thread as interrupted (LangGraph handles this)
    return Command(
        update={
            "messages": [ToolMessage(content=message, tool_call_id=tool_call_id)]
        }
    )
```

### Step 4: Handle Resume in A2A Handler
When user responds, detect if we're resuming an interrupted workflow:

```python
# In src/orchestrator/a2a_handler.py
# Check if thread is interrupted
state = await self.graph.aget_state(config)
if state and state.tasks and any(task.interrupts for task in state.tasks):
    # This is a resume - use Command with resume
    from langgraph.types import Command
    result = await self.graph.ainvoke(
        Command(resume=instruction),  # User's response becomes the resume value
        config
    )
else:
    # Normal invocation
    result = await self.graph.ainvoke(initial_state, config)
```

### Step 5: Remove Custom workflow_waiting Code
Clean up all the custom workflow_waiting state management:
- Remove from OrchestratorState TypedDict
- Remove from conversation_handler.py
- Remove from WorkflowAgentTool Command updates
- Remove persistence attempts in A2A handler

## Benefits of This Approach

1. **Simplicity**: Uses LangGraph's built-in functionality
2. **Reliability**: Interrupt is battle-tested in production
3. **Compatibility**: Works seamlessly in both CLI and A2A modes
4. **Maintainability**: Less custom code to maintain
5. **Performance**: Interrupted threads don't consume resources

## Success Criteria

1. Workflow pauses when human input is needed
2. User sees the formatted request for input
3. User's response resumes the workflow from where it paused
4. Works identically in CLI and A2A modes
5. No custom state management needed

## Implementation Order (YAGNI)

1. Start with minimal changes to workflow engine (Step 1)
2. Update workflow A2A handler to return interrupt status (Step 2)
3. Update orchestrator to handle interrupts (Step 3)
4. Add resume logic to A2A handler (Step 4)
5. Clean up old code only after new implementation works (Step 5)