# Workflow State Persistence Issue in A2A Mode

## Problem Summary
When using the orchestrator in A2A mode via `orchestrator_cli.py`, the workflow human-in-the-loop feature doesn't work properly. The workflow correctly pauses and requests human input, but when the user responds, the orchestrator doesn't detect the workflow_waiting state and starts a new workflow instead of resuming.

## Root Cause
The issue is in how LangGraph handles state updates from tool Commands in A2A mode:

1. **Tool Execution Flow**: WorkflowAgentTool returns a `Command` object with state updates including `workflow_waiting`
2. **State Update**: The tool node processes the Command and updates the graph state
3. **A2A Handler Issue**: The A2A handler's `graph.ainvoke()` returns the final state, but the `workflow_waiting` field is present in the result
4. **State Persistence**: LangGraph's checkpointer saves messages but custom state fields like `workflow_waiting` need explicit handling

## Current Flow (Broken)
1. User: "onboard Express Logistics"
2. Orchestrator → WorkflowAgentTool → Workflow Agent
3. Workflow Agent returns: `WORKFLOW_HUMAN_INPUT_REQUIRED:{...}`
4. WorkflowAgentTool returns: `Command(update={"workflow_waiting": {...}})`
5. Tool node applies state updates including `workflow_waiting`
6. **Issue**: A2A handler returns only the response content, not the workflow_waiting state
7. User sees the selection prompt but workflow_waiting state isn't communicated back
8. User: "the second one"
9. Orchestrator's conversation handler doesn't see workflow_waiting state, starts new workflow

## Implemented Partial Fix
1. Added `workflow_waiting: Optional[Dict[str, Any]]` to `OrchestratorState` TypedDict
2. A2A handler now checks for `workflow_waiting` in the graph result
3. A2A handler includes `workflow_waiting` in the response if present
4. Added extensive debug logging

## Still Missing
1. The orchestrator CLI client needs to track workflow_waiting state across calls
2. The conversation handler's workflow detection logic needs to work with the restored state
3. State persistence between A2A calls needs proper thread state management

## Temporary Workaround
Use the orchestrator in direct CLI mode (`python3 orchestrator.py`) instead of A2A mode for workflows requiring human input. In direct CLI mode, the state is maintained within the same process and workflow human-in-the-loop works correctly.

## Proper Fix (TODO)
1. Ensure LangGraph checkpointer saves the full state including custom fields
2. A2A handler should use `graph.aupdate_state()` to properly persist state changes
3. Implement proper state restoration on subsequent A2A calls
4. Test the full flow with human-in-the-loop workflows