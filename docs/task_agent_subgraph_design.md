# Task Agent Subgraph Design

## Overview

This design document outlines the refactoring of the TaskAgentTool to operate as a proper subgraph node within the main orchestrator graph, using conditional routing based on state flags.

## Current Architecture Issues

1. **Separate Graph Instances**: TaskAgentTool creates its own plan-execute graph
2. **Complex State Management**: Manual coordination between two independent graphs
3. **Interrupt Handling**: Complex manual propagation of interrupts
4. **Nested Invocation**: Tool invokes entire graph within React agent node

## Proposed Architecture

### Graph Structure

```
Main Orchestrator Graph (StateGraph):
├── react_agent (node with tools including lightweight TaskAgentTool)
├── plan_execute_subgraph (plan-execute workflow as node)
└── conditional_edges:
    └── after react_agent:
        ├── if needs_plan_execute → plan_execute_subgraph
        ├── else → END
    └── after plan_execute_subgraph → END
```

### Key Components

#### 1. Extended Orchestrator State

```python
from typing import NotRequired
from langgraph.prebuilt.chat_agent_executor import AgentState

class OrchestratorState(AgentState):
    """Extended state for orchestrator with plan-execute routing."""
    # Existing fields
    summary: NotRequired[str]
    active_agents: NotRequired[List[str]]
    last_agent_interaction: NotRequired[Dict[str, Any]]
    thread_id: NotRequired[str]
    task_id: NotRequired[str]
    user_id: NotRequired[str]
    
    # New routing fields
    needs_plan_execute: bool = False
    plan_execute_task: str = ""
    plan_execute_context: Optional[str] = None
```

#### 2. Lightweight Task Agent Tool

```python
class TaskAgentTool(BaseTool):
    """Lightweight routing tool that flags complex tasks for plan-execute workflow."""
    
    name: str = "task_agent"
    description: str = """Use this tool for complex multi-step tasks that require:
    - Planning and coordination
    - Multiple agent interactions
    - Updates by name (not ID)
    - Workflows like onboarding
    """
    
    async def _arun(self, task: str, context: Optional[str] = None, 
                    state: Annotated[Dict[str, Any], InjectedState] = None) -> str:
        """Set flag for plan-execute routing."""
        logger.info("task_agent_routing", task=task[:100])
        
        # Return state updates that will trigger routing
        return {
            "needs_plan_execute": True,
            "plan_execute_task": task,
            "plan_execute_context": context
        }
```

#### 3. Plan-Execute Subgraph Node

```python
async def plan_execute_node(state: OrchestratorState) -> Dict[str, Any]:
    """Execute plan-execute workflow as a subgraph node."""
    # Get or create the subgraph (cached)
    subgraph = await get_plan_execute_subgraph()
    
    # Transform orchestrator state to plan-execute state
    plan_execute_state = {
        "input": state["plan_execute_task"],
        "plan": [],
        "past_steps": [],
        "response": "",
        "messages": state["messages"],
        "thread_id": state.get("thread_id", "default-thread"),
        "task_id": state.get("task_id", "default-task"),
        "user_id": state.get("user_id", "default-user"),
    }
    
    # Add context if available
    if state.get("plan_execute_context"):
        plan_execute_state["input"] += f"\n\nContext: {state['plan_execute_context']}"
    
    logger.info("plan_execute_node_invoking", task=state["plan_execute_task"][:100])
    
    # Invoke subgraph - interrupts propagate automatically
    result = await subgraph.ainvoke(plan_execute_state)
    
    # Extract response and update orchestrator state
    response = result.get("response", "Task completed.")
    
    # Return state updates
    return {
        "messages": [AIMessage(content=response)],
        "needs_plan_execute": False,  # Reset flag
        "plan_execute_task": "",
        "plan_execute_context": None
    }
```

#### 4. Routing Function

```python
def route_after_react_agent(state: OrchestratorState) -> str:
    """Route to plan-execute or end based on state flags."""
    if state.get("needs_plan_execute", False):
        logger.info("routing_to_plan_execute", task=state.get("plan_execute_task", "")[:100])
        return "plan_execute"
    return END
```

#### 5. Custom Orchestrator Graph Builder

```python
async def create_orchestrator_graph():
    """Create orchestrator graph with react agent and plan-execute subgraph."""
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver
    
    # Create state graph
    builder = StateGraph(OrchestratorState)
    
    # Add react agent node (mimics create_react_agent behavior)
    builder.add_node("react_agent", react_agent_node)
    
    # Add plan-execute subgraph node
    builder.add_node("plan_execute", plan_execute_node)
    
    # Define edges
    builder.add_edge(START, "react_agent")
    
    # Conditional routing after react agent
    builder.add_conditional_edges(
        "react_agent",
        route_after_react_agent,
        {
            "plan_execute": "plan_execute",
            END: END
        }
    )
    
    # Plan-execute always goes to END
    builder.add_edge("plan_execute", END)
    
    # Compile with checkpointer
    return builder.compile(checkpointer=MemorySaver())
```

#### 6. React Agent Node Implementation

```python
async def react_agent_node(state: OrchestratorState) -> Dict[str, Any]:
    """React agent node that handles tool calls and responses."""
    # Get LLM and tools
    llm = get_orchestrator_llm()
    tools = get_orchestrator_tools()  # Includes lightweight TaskAgentTool
    
    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(tools)
    
    # Get the last message to process
    messages = state["messages"]
    
    # Check if we're resuming from a tool call
    last_message = messages[-1] if messages else None
    
    if isinstance(last_message, ToolMessage):
        # We just executed a tool, generate response
        response = await llm.ainvoke(messages)
        return {"messages": [response]}
    
    # Otherwise, process the current message
    response = await llm_with_tools.ainvoke(messages)
    
    # If there are tool calls, execute them
    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_messages = []
        state_updates = {}
        
        for tool_call in response.tool_calls:
            # Get the tool
            tool = next((t for t in tools if t.name == tool_call["name"]), None)
            if not tool:
                continue
            
            # Execute tool
            try:
                result = await tool.ainvoke(tool_call["args"], state=state)
                
                # Check if tool returned state updates (like TaskAgentTool)
                if isinstance(result, dict) and "needs_plan_execute" in result:
                    state_updates.update(result)
                    # Add a tool message indicating routing
                    tool_messages.append(ToolMessage(
                        content="Routing to plan-execute workflow...",
                        tool_call_id=tool_call["id"]
                    ))
                else:
                    # Normal tool result
                    tool_messages.append(ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call["id"]
                    ))
            except Exception as e:
                tool_messages.append(ToolMessage(
                    content=f"Error: {str(e)}",
                    tool_call_id=tool_call["id"]
                ))
        
        # Return messages and any state updates
        return {
            "messages": [response] + tool_messages,
            **state_updates
        }
    
    # No tool calls, just return the response
    return {"messages": [response]}
```

## Implementation Steps

### Phase 1: Create Plan-Execute Subgraph
1. Modify `create_plan_execute_graph()` to compile without checkpointer
2. Create caching mechanism for subgraph instance
3. Test subgraph works correctly when invoked directly

### Phase 2: Implement Lightweight TaskAgentTool
1. Replace current implementation with routing-only version
2. Return state updates instead of invoking graph
3. Test tool returns correct state flags

### Phase 3: Build Custom Orchestrator Graph
1. Extend OrchestratorState with routing fields
2. Implement react_agent_node with tool execution
3. Implement plan_execute_node with state transformation
4. Add conditional routing logic
5. Wire everything together in graph builder

### Phase 4: Integration
1. Update A2A handler to use new orchestrator graph
2. Test interrupt propagation works correctly
3. Verify state persistence across nodes
4. Test complex multi-step workflows

## Benefits

1. **Unified Graph**: Single graph with proper state management
2. **Automatic Interrupt Handling**: LangGraph handles propagation
3. **Better Observability**: Can stream subgraph events with `subgraphs=True`
4. **Cleaner Architecture**: Clear separation between routing and execution
5. **Proper State Management**: Parent checkpointer manages all state

## Testing Strategy

### Test Cases

1. **Simple Query**: "What are the open opportunities?" → Should use direct agent
2. **Complex Task**: "Onboard Acme Corp" → Should route to plan-execute
3. **Interrupt Flow**: Task requiring human input → Should propagate correctly
4. **State Persistence**: Resume after interrupt → Should maintain context
5. **Error Handling**: Invalid task → Should handle gracefully

### Validation Points

- TaskAgentTool correctly sets routing flags
- Conditional edge routes to plan-execute when flag is set
- Plan-execute subgraph executes correctly
- State transformations work both directions
- Interrupts propagate from subgraph to parent
- Final response reaches user correctly

## Migration Notes

- Current TaskAgentTool usage remains the same from LLM perspective
- No changes to prompt or tool descriptions needed
- Existing checkpointed states may need migration
- Consider feature flag for gradual rollout

## Future Enhancements

1. Add more conditional routing options (e.g., direct to specific agents)
2. Implement parallel execution paths
3. Add observability hooks for monitoring
4. Consider caching plan-execute results
5. Add metrics for routing decisions