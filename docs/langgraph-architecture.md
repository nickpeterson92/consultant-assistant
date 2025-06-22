# LangGraph Architecture Documentation

## Overview

LangGraph is the state management and orchestration framework that powers our multi-agent system. It provides a graph-based approach to building stateful, multi-actor applications with built-in checkpointing, human-in-the-loop capabilities, and production-ready features. Our implementation leverages LangGraph 0.4.8's advanced capabilities for enterprise-grade agent coordination.

## Core Concepts

### State Graphs

LangGraph models agent workflows as directed graphs where:
- **Nodes** represent computational steps (functions)
- **Edges** define control flow between nodes
- **State** is immutable and flows through the graph
- **Conditional edges** enable dynamic routing

```python
# Graph structure in our orchestrator
graph_builder = StateGraph(OrchestratorState)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("tools", tool_node)
graph_builder.add_conditional_edges("chatbot", tools_condition)
```

### State Management

Our orchestrator uses a sophisticated state schema:

```python
class OrchestratorState(TypedDict):
    messages: Annotated[list, add_messages]      # Conversation history
    summary: str                                 # Conversation summary
    memory: SimpleMemory                         # Structured CRM data
    events: List[OrchestratorEvent]             # System events
    user_id: str                                # User identifier
    memory_init_done: bool                      # Initialization flag
```

The `add_messages` reducer intelligently handles:
- Message deduplication
- RemoveMessage directives for token management
- ID-based message updates

## Architecture Patterns

### Multi-Actor Design

```
┌─────────────────────────────────────────────────────────┐
│                    Orchestrator Graph                   │
├─────────────────────────────────────────────────────────┤
│  ┌─────────┐     ┌─────────┐     ┌──────────────────┐   │
│  │ Chatbot │────>│  Tools  │────>│ Background Tasks │   │
│  └────┬────┘     └────┬────┘     └──────────────────┘   │
│       │               │                                 │
│       └───────────────┘                                 │
│              │                                          │
│              ▼                                          │
│         ┌─────────┐                                     │
│         │   END   │                                     │
│         └─────────┘                                     │
└─────────────────────────────────────────────────────────┘
```

### Checkpointing System

LangGraph provides automatic state persistence:

```python
# Memory-based checkpointer for development
checkpointer = MemorySaver()

# Compile with checkpointing
app = graph_builder.compile(checkpointer=checkpointer)

# State is automatically saved at each step
result = await app.ainvoke(
    {"messages": [HumanMessage(content="Hello")]},
    config={"configurable": {"thread_id": "user123"}}
)
```

## Key Components

### 1. Chatbot Node

The main conversation handler that:
- Processes user messages
- Maintains conversation context
- Triggers tool calls
- Manages token limits through summarization

```python
async def chatbot(state: OrchestratorState, config: RunnableConfig):
    # Smart message preservation for token management
    preserved_messages = smart_preserve_messages(
        state["messages"], 
        preserve_count=10,
        max_tokens=3000
    )
    
    # LLM invocation with tools
    response = llm_with_tools.invoke(messages)
    
    # Cost tracking
    log_cost_activity("ORCHESTRATOR_LLM_CALL", estimated_tokens)
    
    return {"messages": response}
```

### 2. Tool System

Tools are integrated using LangGraph's ToolNode:

```python
# Define tools
tools = [
    SalesforceAgentTool(),
    GenericAgentTool(), 
    AgentRegistryTool()
]

# Create tool node
tool_node = ToolNode(tools=tools)

# Tools are automatically executed based on LLM decisions
```

### 3. Background Tasks

LangGraph's `Send` API enables parallel processing:

```python
# Trigger parallel background tasks
return [
    Send("summarize_conversation", {"messages": messages}),
    Send("update_memory", {"messages": messages, "memory": memory})
]
```

### 4. Conditional Routing

Dynamic graph traversal based on state:

```python
def tools_condition(state: OrchestratorState):
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None
    
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    return END
```

## State Flow

### Message Processing Pipeline

1. **User Input** → HumanMessage added to state
2. **Chatbot Node** → Processes messages, may call tools
3. **Tool Execution** → If tools called, execute and return results
4. **Response** → AIMessage with results back to user
5. **Background Tasks** → Parallel summary/memory updates

### Memory Management

Our system implements a sophisticated memory extraction pipeline:

```python
async def update_memory(state: UpdateMemoryState, config: RunnableConfig):
    # Extract structured data using TrustCall
    extractor = create_extractor(
        llm,
        tools=[SimpleMemoryExtractor],
        tool_choice="SimpleMemoryExtractor"
    )
    
    # Process messages for CRM data
    extraction_result = await extractor.ainvoke({
        "messages": messages_for_extraction
    })
    
    # Persist to storage
    await store.aput(
        namespace=("memory", user_id),
        key="SimpleMemory", 
        value=updated_memory
    )
```

## Production Features

### 1. Human-in-the-Loop

LangGraph supports intervention points:

```python
# Interrupt before tool execution
app = graph_builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["tools"]
)

# Resume after human review
await app.ainvoke(None, config, interrupt_after=["tools"])
```

### 2. Streaming Support

Real-time response streaming:

```python
async for chunk in app.astream(input_state, config):
    if "chatbot" in chunk:
        print(chunk["chatbot"]["messages"][-1].content)
```

### 3. Time Travel Debugging

Navigate through execution history:

```python
# Get all checkpoints
checkpoints = [c async for c in checkpointer.alist(config)]

# Replay from specific checkpoint
await app.ainvoke(None, checkpoints[2].config)
```

### 4. Subgraph Architecture

Modular graph composition:

```python
# Salesforce agent as subgraph
salesforce_graph = StateGraph(SalesforceState)
salesforce_graph.add_node("conversation", salesforce_chatbot)
salesforce_graph.add_node("tools", tool_node)

# Can be invoked independently or as part of larger graph
```

## Configuration

### Thread Management

Each conversation has a unique thread:

```python
config = {
    "configurable": {
        "thread_id": f"user-{user_id}",  # User-specific threads
        "user_id": user_id,               # Custom user tracking
        "checkpoint_ns": "orchestrator"    # Namespace for checkpoints
    },
    "recursion_limit": 50,                # Max graph traversals
    "debug": True                         # Enable debug logging
}
```

### Recursion Limits

Prevent infinite loops:

```python
# Orchestrator: Higher limit for complex interactions
"recursion_limit": 50

# Agents: Lower limit for focused tasks  
"recursion_limit": 25
```

## Best Practices

### 1. State Design

- **Keep state minimal**: Only essential data
- **Use reducers**: For complex state updates
- **Immutable updates**: Never modify state directly
- **Type safety**: Use TypedDict for schemas

### 2. Node Design

- **Single responsibility**: Each node does one thing
- **Idempotent**: Nodes should be re-runnable
- **Error handling**: Graceful failure recovery
- **Async first**: Use async/await throughout

### 3. Tool Integration

- **Clear descriptions**: Help LLM select correctly
- **Validation**: Check inputs before execution
- **Structured output**: Return consistent formats
- **Error messages**: Informative failure responses

### 4. Memory Efficiency

- **Message pruning**: Remove old messages
- **Summarization**: Compress conversation history
- **Selective persistence**: Only save important data
- **Background processing**: Don't block main flow

## Performance Optimization

### 1. Parallel Execution

```python
# Use Send for concurrent operations
return [
    Send("process_a", state_a),
    Send("process_b", state_b),
    Send("process_c", state_c)
]
```

### 2. Conditional Loading

```python
# Load memory only when needed
if not state.get("memory_init_done"):
    memory = await load_memory(user_id)
    return {"memory": memory, "memory_init_done": True}
```

### 3. Smart Message Management

```python
# Preserve only essential messages
preserved = smart_preserve_messages(
    messages,
    preserve_count=10,      # Keep last 10
    max_tokens=3000,       # Token limit
    always_preserve_system=True
)
```

## Error Handling

### 1. Node-Level Recovery

```python
async def safe_node(state, config):
    try:
        return await risky_operation(state)
    except SpecificError as e:
        logger.error(f"Operation failed: {e}")
        return {"error": str(e), "status": "failed"}
```

### 2. Graph-Level Fallbacks

```python
# Add error handling edges
graph_builder.add_conditional_edges(
    "risky_node",
    lambda s: "error_handler" if s.get("error") else "next_node"
)
```

### 3. Checkpoint Recovery

```python
# Restore from last good state
try:
    result = await app.ainvoke(state, config)
except Exception:
    # Get last checkpoint
    checkpoint = await checkpointer.aget(config)
    # Retry from checkpoint
    result = await app.ainvoke(checkpoint.state, config)
```

## Testing Strategies

### 1. Unit Testing Nodes

```python
async def test_chatbot_node():
    state = {
        "messages": [HumanMessage(content="test")],
        "memory": SimpleMemory()
    }
    result = await chatbot(state, RunnableConfig())
    assert "messages" in result
```

### 2. Integration Testing Graphs

```python
async def test_full_flow():
    app = build_orchestrator_graph()
    result = await app.ainvoke(
        {"messages": [HumanMessage(content="Get accounts")]},
        {"configurable": {"thread_id": "test"}}
    )
    assert len(result["messages"]) > 1
```

### 3. State Machine Testing

```python
# Test all possible paths
paths = [
    ["chatbot", "tools", "chatbot", END],
    ["chatbot", END],
    ["chatbot", "background_tasks", END]
]
```

## Migration Guide

### From 0.2.x to 0.4.x

1. **Remove compatibility layers**
   ```python
   # Old
   from src.utils.langgraph_compat import ToolNode
   
   # New
   from langgraph.prebuilt import ToolNode
   ```

2. **Update recursion limits**
   ```python
   # 0.4.x has better recursion handling
   config["recursion_limit"] = 50  # Can be higher
   ```

3. **Use built-in features**
   ```python
   # 0.4.x has native Send API
   from langgraph.types import Send
   ```

## Common Patterns

### 1. Agent Delegation

```python
async def delegate_to_agent(state, config):
    # Select agent based on capability
    agent = find_best_agent(state["task"])
    
    # Call via A2A
    result = await client.call_agent(
        agent.endpoint,
        create_task(state)
    )
    
    return {"messages": [AIMessage(content=result)]}
```

### 2. Conditional Tool Usage

```python
def should_use_tools(state):
    # Complex routing logic
    if requires_salesforce(state):
        return "salesforce_tools"
    elif requires_search(state):
        return "search_tools"
    return "chatbot"
```

### 3. State Aggregation

```python
async def aggregate_results(state, config):
    # Collect results from multiple sources
    results = await asyncio.gather(
        fetch_salesforce_data(state),
        fetch_external_data(state),
        fetch_memory_data(state)
    )
    
    return {"aggregated_data": merge_results(results)}
```

## Troubleshooting

### Common Issues

1. **Infinite Loops**
   - Check conditional edges logic
   - Verify recursion limits
   - Add loop detection in nodes

2. **State Size Growth**
   - Implement message pruning
   - Use RemoveMessage directives
   - Limit event history

3. **Tool Selection Errors**
   - Improve tool descriptions
   - Add explicit examples
   - Use tool_choice parameter

4. **Memory Leaks**
   - Clear large objects after use
   - Use weak references where appropriate
   - Monitor checkpoint size

5. **Async Context Errors**
   - Ensure proper async/await usage
   - Avoid blocking operations
   - Use asyncio primitives correctly

## Future Enhancements

1. **Streaming Improvements**: Better token-by-token streaming
2. **Graph Visualization**: Real-time execution visualization  
3. **Distributed Execution**: Multi-machine graph processing
4. **Advanced Checkpointing**: Incremental state saves
5. **Plugin System**: Dynamic node registration