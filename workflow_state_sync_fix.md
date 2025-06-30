# Workflow State Synchronization Fix

## Problem Summary
When workflows completed, the orchestrator cleared the `interrupted_workflow` state internally, but the CLI client retained stale workflow context, causing duplicate workflow executions on subsequent messages.

## Root Cause
1. The A2A handler only included metadata when `interrupted_workflow` was truthy
2. When workflows completed and state was cleared to `None`, no metadata was sent
3. The CLI client had no way to know the workflow had completed

## Solution Implemented

### 1. Enhanced A2A Handler (`src/orchestrator/a2a_handler.py`)
- Always includes workflow state in metadata, even when `None`
- Introduced extensible `state_sync` metadata structure for future state synchronization needs
- Logs both workflow interruption and completion events

### 2. Updated CLI Client (`orchestrator_cli.py`)
- Properly handles state synchronization metadata from server
- Supports both new `state_sync` format and legacy format for backward compatibility
- Clears local workflow state when server indicates completion

### 3. Key Changes

#### A2A Handler
```python
# Build state synchronization metadata for client
state_sync = {}

# Always include workflow state in metadata
if "interrupted_workflow" in result:
    state_sync["interrupted_workflow"] = interrupted_workflow
    
# Only add metadata if there's state to sync
if state_sync:
    response["metadata"] = {"state_sync": state_sync}
```

#### CLI Client
```python
# Handle state synchronization from server
if 'state_sync' in metadata:
    state_sync = metadata['state_sync']
    if 'interrupted_workflow' in state_sync:
        interrupted_workflow = state_sync['interrupted_workflow']
```

## Benefits
1. **Fixes duplicate workflow execution** - CLI client properly clears workflow state
2. **Extensible design** - Easy to add more state synchronization fields in the future
3. **Backward compatible** - Supports legacy metadata format
4. **Better logging** - Clear logs for both workflow interruption and completion

## Future Extensions
The state_sync pattern can be extended for:
- Active background tasks
- Conversation mode changes
- Memory updates
- Agent availability changes

Simply add new fields to `state_sync` in the A2A handler and corresponding handling in the CLI client.