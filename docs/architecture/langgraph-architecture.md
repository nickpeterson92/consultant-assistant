# LangGraph Architecture Documentation for Junior Engineers

## Table of Contents
1. [What is LangGraph?](#what-is-langgraph)
2. [Why We Use LangGraph](#why-we-use-langgraph)
3. [Core Concepts Explained](#core-concepts-explained)
4. [Building Your First LangGraph Application](#building-your-first-langgraph-application)
5. [Common Patterns and Best Practices](#common-patterns-and-best-practices)
6. [Debugging LangGraph Applications](#debugging-langgraph-applications)
7. [Testing Strategies](#testing-strategies)
8. [Performance Optimization Tips](#performance-optimization-tips)
9. [Real Examples from Our Codebase](#real-examples-from-our-codebase)
10. [Troubleshooting Guide](#troubleshooting-guide)

## What is LangGraph?

LangGraph is a Python library for building stateful, multi-actor applications with Large Language Models (LLMs). Think of it as a framework that helps you create AI agents that can:
- Remember previous conversations
- Make decisions about what to do next
- Call tools and APIs
- Work together with other agents
- Save and restore their state

### Simple Analogy
Imagine you're building a customer service chatbot. Without LangGraph, it's like having a receptionist who forgets everything after each sentence. With LangGraph, you have a receptionist who:
- Remembers the entire conversation
- Can look up information in different systems
- Knows when to transfer you to a specialist
- Can pick up where they left off if disconnected

## Why We Use LangGraph

### 1. **State Management Made Easy**
```python
# Without LangGraph - Manual state tracking
conversation_history = []
user_data = {}
current_task = None

def handle_message(message):
    conversation_history.append(message)
    # Complex logic to manage state...
    
# With LangGraph - Automatic state management
class ChatState(TypedDict):
    messages: List[BaseMessage]
    user_data: dict
    current_task: str
```

### 2. **Built-in Checkpointing**
LangGraph automatically saves your application state, so you can:
- Resume conversations after crashes
- Debug by replaying past interactions
- Implement undo/redo functionality

### 3. **Visual Flow Control**
Instead of nested if/else statements, you design your logic as a graph:
```python
# Traditional approach - Hard to follow
if user_wants_salesforce:
    if has_permissions:
        if data_exists:
            return fetch_data()
        else:
            return "No data found"
    else:
        return "No permissions"
        
# LangGraph approach - Clear flow
graph.add_node("check_intent", check_user_intent)
graph.add_node("check_permissions", verify_permissions)
graph.add_node("fetch_data", get_salesforce_data)
graph.add_edge("check_intent", "check_permissions")
graph.add_edge("check_permissions", "fetch_data")
```

## Core Concepts Explained

### 1. **Nodes** - The Building Blocks
A node is just a function that does something with state:

```python
# A simple node function
def greet_user(state: dict) -> dict:
    """This node greets the user"""
    user_name = state.get("user_name", "friend")
    greeting = f"Hello, {user_name}!"
    
    # Return what we want to update in the state
    return {"messages": [greeting]}

# Adding the node to a graph
graph = StateGraph(dict)
graph.add_node("greeter", greet_user)  # Give it a name and the function
```

### 2. **Edges** - Connecting Nodes
Edges tell LangGraph which node to run next:

```python
# Simple edge - Always go from A to B
graph.add_edge("greeter", "helper")  # After greeting, always go to helper

# Conditional edge - Choose based on state
def routing_function(state: dict) -> str:
    """Decide where to go next based on state"""
    if state.get("needs_help"):
        return "helper"
    else:
        return "goodbye"

graph.add_conditional_edges(
    "greeter",           # From this node
    routing_function,    # Use this function to decide
    {                    # Possible destinations
        "helper": "helper_node",
        "goodbye": "goodbye_node"
    }
)
```

### 3. **State** - The Application's Memory
State is the data that flows through your graph:

```python
# Define your state structure
class MyAppState(TypedDict):
    messages: List[str]          # Chat history
    user_name: str              # User's name
    task_complete: bool         # Is the task done?
    error: Optional[str]        # Any errors?

# State flows through nodes
def process_request(state: MyAppState) -> dict:
    # Read from state
    messages = state["messages"]
    
    # Do something
    response = f"Processing {len(messages)} messages"
    
    # Return updates to state
    return {
        "messages": messages + [response],
        "task_complete": True
    }
```

### 4. **Checkpointing** - Save and Resume
Checkpointing saves your state automatically:

```python
# Set up checkpointing
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()  # In-memory for development
graph = graph.compile(checkpointer=checkpointer)

# Run with a thread ID to enable checkpointing
result = graph.invoke(
    {"messages": ["Hello"]},
    config={"configurable": {"thread_id": "user123"}}
)

# Later, resume the same conversation
result = graph.invoke(
    {"messages": ["What did I just say?"]},
    config={"configurable": {"thread_id": "user123"}}  # Same thread ID
)
```

## Building Your First LangGraph Application

Let's build a simple customer service bot step by step.

### Step 1: Set Up Your Environment

```bash
# Install required packages
pip install langgraph langchain langchain-openai python-dotenv

# Create your project structure
mkdir my_first_langgraph_app
cd my_first_langgraph_app
touch app.py .env
```

### Step 2: Create a .env File

```bash
# .env file
OPENAI_API_KEY=your_api_key_here
```

### Step 3: Import Required Libraries

```python
# app.py
from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from dotenv import load_dotenv
import operator

# Load environment variables
load_dotenv()
```

### Step 4: Define Your State

```python
# This is what your app will remember
class CustomerServiceState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]  # Chat history
    current_issue: str                                    # What the customer needs
    issue_resolved: bool                                  # Is the issue resolved?
    customer_satisfaction: int                            # 1-5 rating
```

The `Annotated[List[BaseMessage], operator.add]` means when we return messages, they'll be added to the existing list rather than replacing it.

### Step 5: Create Node Functions

```python
# Initialize the LLM
llm = ChatOpenAI(temperature=0.7)

def understand_issue(state: CustomerServiceState) -> dict:
    """First node - Understand what the customer needs"""
    messages = state.get("messages", [])
    
    if not messages:
        return {"messages": [AIMessage(content="Hello! How can I help you today?")]}
    
    # Use LLM to understand the issue
    prompt = f"Based on this conversation, what is the main issue? {messages[-1].content}"
    response = llm.invoke([HumanMessage(content=prompt)])
    
    # Extract the issue (in real app, you'd parse this better)
    issue = response.content
    
    return {
        "current_issue": issue,
        "messages": [AIMessage(content=f"I understand you need help with: {issue}")]
    }

def provide_solution(state: CustomerServiceState) -> dict:
    """Second node - Provide a solution"""
    issue = state.get("current_issue", "general inquiry")
    
    # Simple solution logic (in real app, this would be more complex)
    solutions = {
        "password": "You can reset your password by clicking 'Forgot Password' on the login page.",
        "billing": "I can help you review your billing. Your current balance is $0.",
        "technical": "Let me help you troubleshoot. First, try restarting your device."
    }
    
    # Find matching solution or provide general help
    solution = "I'll connect you with a specialist who can help."
    for key, value in solutions.items():
        if key in issue.lower():
            solution = value
            break
    
    return {
        "messages": [AIMessage(content=solution)],
        "issue_resolved": True
    }

def check_satisfaction(state: CustomerServiceState) -> dict:
    """Final node - Check if customer is satisfied"""
    return {
        "messages": [AIMessage(content="Was I able to help you today? (yes/no)")],
        "customer_satisfaction": 5  # Default to satisfied
    }
```

### Step 6: Build the Graph

```python
def should_check_satisfaction(state: CustomerServiceState) -> str:
    """Routing function - Decide what to do next"""
    if state.get("issue_resolved", False):
        return "check_satisfaction"
    else:
        return "provide_solution"

# Create the graph
def build_customer_service_bot():
    # Initialize the graph with our state
    graph = StateGraph(CustomerServiceState)
    
    # Add nodes
    graph.add_node("understand", understand_issue)
    graph.add_node("solve", provide_solution)
    graph.add_node("feedback", check_satisfaction)
    
    # Add edges
    graph.add_edge("understand", "solve")
    graph.add_conditional_edges(
        "solve",
        should_check_satisfaction,
        {
            "check_satisfaction": "feedback",
            "provide_solution": "solve"  # Loop back if not resolved
        }
    )
    graph.add_edge("feedback", END)
    
    # Set the entry point
    graph.set_entry_point("understand")
    
    # Compile with checkpointing
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)
```

### Step 7: Run Your Application

```python
def main():
    # Build the bot
    bot = build_customer_service_bot()
    
    # Test conversation
    thread_id = "customer_123"
    
    # First message
    result1 = bot.invoke(
        {"messages": [HumanMessage(content="I forgot my password")]},
        config={"configurable": {"thread_id": thread_id}}
    )
    print("Bot:", result1["messages"][-1].content)
    
    # Follow-up message (bot remembers context)
    result2 = bot.invoke(
        {"messages": [HumanMessage(content="Thanks, that worked!")]},
        config={"configurable": {"thread_id": thread_id}}
    )
    print("Bot:", result2["messages"][-1].content)

if __name__ == "__main__":
    main()
```

### Step 8: Run and Test

```bash
python app.py
```

## Common Patterns and Best Practices

### 1. **The Supervisor Pattern**
Used when you have multiple specialized agents:

```python
class SupervisorState(TypedDict):
    messages: List[BaseMessage]
    next_agent: str

def supervisor(state: SupervisorState) -> dict:
    """Decide which agent should handle the request"""
    last_message = state["messages"][-1].content
    
    # Route to appropriate agent
    if "sales" in last_message.lower():
        return {"next_agent": "sales_agent"}
    elif "technical" in last_message.lower():
        return {"next_agent": "tech_agent"}
    else:
        return {"next_agent": "general_agent"}

# Build graph with multiple paths
graph = StateGraph(SupervisorState)
graph.add_node("supervisor", supervisor)
graph.add_node("sales_agent", handle_sales_query)
graph.add_node("tech_agent", handle_tech_query)
graph.add_node("general_agent", handle_general_query)

# Conditional routing based on supervisor decision
graph.add_conditional_edges(
    "supervisor",
    lambda x: x["next_agent"],
    {
        "sales_agent": "sales_agent",
        "tech_agent": "tech_agent",
        "general_agent": "general_agent"
    }
)
```

### 2. **The Human-in-the-Loop Pattern**
For when you need human approval:

```python
def needs_human_approval(state: dict) -> dict:
    """Check if this action needs approval"""
    if state.get("total_cost", 0) > 1000:
        return {"needs_approval": True, "status": "pending_approval"}
    return {"needs_approval": False}

# Build graph with interruption
graph = StateGraph(dict)
graph.add_node("calculate_cost", calculate_total_cost)
graph.add_node("check_approval", needs_human_approval)
graph.add_node("process_order", complete_order)

# Compile with interruption point
app = graph.compile(
    checkpointer=checkpointer,
    interrupt_before=["process_order"]  # Stop here if needed
)

# Run and check if interrupted
result = app.invoke({"order_items": [...], "total_cost": 1500})
if result.get("needs_approval"):
    print("Order requires approval. Waiting for human input...")
    # Later, after approval
    app.invoke(None, config, {"approved": True})
```

### 3. **The Retry Pattern**
For handling failures gracefully:

```python
def api_call_with_retry(state: dict) -> dict:
    """Node that retries on failure"""
    max_attempts = state.get("retry_count", 3)
    current_attempt = state.get("current_attempt", 0)
    
    try:
        # Your API call here
        result = make_external_api_call()
        return {"api_result": result, "success": True}
    except Exception as e:
        if current_attempt < max_attempts:
            return {
                "current_attempt": current_attempt + 1,
                "error": str(e),
                "should_retry": True
            }
        else:
            return {
                "error": f"Failed after {max_attempts} attempts: {e}",
                "should_retry": False
            }

# Add retry logic in routing
def should_retry(state: dict) -> str:
    if state.get("should_retry", False):
        return "retry"
    elif state.get("success", False):
        return "continue"
    else:
        return "error_handler"
```

### 4. **The Parallel Processing Pattern**
For handling multiple tasks simultaneously:

```python
from langgraph.types import Send

def dispatch_parallel_tasks(state: dict) -> List[Send]:
    """Send multiple tasks to run in parallel"""
    customer_id = state["customer_id"]
    
    return [
        Send("fetch_order_history", {"customer_id": customer_id}),
        Send("fetch_support_tickets", {"customer_id": customer_id}),
        Send("fetch_preferences", {"customer_id": customer_id})
    ]

def aggregate_results(state: dict) -> dict:
    """Combine results from parallel tasks"""
    return {
        "customer_profile": {
            "orders": state.get("order_history", []),
            "tickets": state.get("support_tickets", []),
            "preferences": state.get("preferences", {})
        }
    }
```

## Debugging LangGraph Applications

### 1. **Enable Debug Mode**

```python
# Turn on debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Run with debug config
result = app.invoke(
    input_state,
    config={
        "configurable": {"thread_id": "debug_session"},
        "debug": True
    }
)
```

### 2. **Visualize Your Graph**

```python
# Print graph structure
print(app.get_graph().draw_ascii())

# Output:
#      ┌─────────┐
#      │ __start__│
#      └────┬────┘
#           │
#      ┌────▼────┐
#      │understand│
#      └────┬────┘
#           │
#      ┌────▼────┐
#      │  solve  │
#      └────┬────┘
#           │
#      ┌────▼────┐
#      │feedback │
#      └────┬────┘
#           │
#      ┌────▼────┐
#      │ __end__ │
#      └─────────┘
```

### 3. **Add Logging to Nodes**

```python
import logging

logger = logging.getLogger(__name__)

def debug_node(state: dict) -> dict:
    """Node with comprehensive logging"""
    logger.info(f"Entering debug_node with state keys: {state.keys()}")
    logger.debug(f"Full state: {state}")
    
    try:
        # Your logic here
        result = process_something(state)
        logger.info(f"Successfully processed, returning: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in debug_node: {e}", exc_info=True)
        return {"error": str(e)}
```

### 4. **Use State Inspection**

```python
# Create a debug wrapper
def debug_wrapper(func):
    def wrapper(state, config):
        print(f"\n=== Entering {func.__name__} ===")
        print(f"State keys: {state.keys()}")
        print(f"Messages: {len(state.get('messages', []))}")
        
        result = func(state, config)
        
        print(f"=== Exiting {func.__name__} ===")
        print(f"Returning: {result.keys() if result else 'None'}")
        
        return result
    return wrapper

# Apply to your nodes
@debug_wrapper
def my_node(state, config):
    # Your logic here
    pass
```

### 5. **Checkpoint Inspection**

```python
# Look at saved checkpoints
async def inspect_checkpoints(thread_id: str):
    """Examine conversation history"""
    checkpoints = []
    async for checkpoint in checkpointer.alist(
        {"configurable": {"thread_id": thread_id}}
    ):
        checkpoints.append(checkpoint)
        print(f"Checkpoint at step {checkpoint.metadata['step']}:")
        print(f"  State keys: {checkpoint.state.keys()}")
        print(f"  Messages: {len(checkpoint.state.get('messages', []))}")
    
    return checkpoints

# Time travel debugging
def replay_from_checkpoint(checkpoint_config):
    """Replay from a specific point"""
    result = app.invoke(None, checkpoint_config)
    return result
```

## Testing Strategies

### 1. **Unit Testing Individual Nodes**

```python
import pytest
from unittest.mock import Mock, patch

def test_understand_issue_node():
    """Test the understand_issue node in isolation"""
    # Arrange
    state = {
        "messages": [HumanMessage(content="I can't log in")]
    }
    
    # Act
    result = understand_issue(state)
    
    # Assert
    assert "current_issue" in result
    assert "messages" in result
    assert len(result["messages"]) == 1
    assert "login" in result["current_issue"].lower()

def test_provide_solution_with_mock():
    """Test with mocked dependencies"""
    with patch('your_module.external_api_call') as mock_api:
        # Arrange
        mock_api.return_value = {"solution": "Reset password"}
        state = {"current_issue": "login problem"}
        
        # Act
        result = provide_solution(state)
        
        # Assert
        assert result["issue_resolved"] == True
        mock_api.assert_called_once()
```

### 2. **Integration Testing the Full Graph**

```python
import asyncio

class TestCustomerServiceBot:
    @pytest.fixture
    def bot(self):
        """Create a bot instance for testing"""
        return build_customer_service_bot()
    
    def test_full_conversation_flow(self, bot):
        """Test complete conversation"""
        thread_id = "test_thread"
        
        # First interaction
        result1 = bot.invoke(
            {"messages": [HumanMessage(content="Password help")]},
            {"configurable": {"thread_id": thread_id}}
        )
        
        assert len(result1["messages"]) >= 2  # User + AI messages
        assert result1.get("current_issue") is not None
        
        # Follow-up
        result2 = bot.invoke(
            {"messages": [HumanMessage(content="Thanks!")]},
            {"configurable": {"thread_id": thread_id}}
        )
        
        assert result2.get("issue_resolved") == True

    @pytest.mark.asyncio
    async def test_parallel_execution(self, bot):
        """Test parallel node execution"""
        # Test that parallel sends work correctly
        result = await bot.ainvoke(
            {"customer_id": "123"},
            {"configurable": {"thread_id": "parallel_test"}}
        )
        
        assert "customer_profile" in result
        assert all(key in result["customer_profile"] 
                  for key in ["orders", "tickets", "preferences"])
```

### 3. **Testing State Transitions**

```python
def test_state_transitions():
    """Test all possible paths through the graph"""
    bot = build_customer_service_bot()
    
    # Test path 1: understand -> solve -> feedback -> end
    state1 = {"messages": [HumanMessage(content="Simple question")]}
    
    # Test path 2: understand -> solve -> solve (retry) -> feedback
    state2 = {"messages": [HumanMessage(content="Complex issue")]}
    
    # Test error path
    state3 = {"messages": [HumanMessage(content="Trigger error")]}
    
    # Run all paths and verify outcomes
    for state in [state1, state2, state3]:
        result = bot.invoke(state)
        assert "messages" in result
        assert len(result["messages"]) > len(state["messages"])
```

### 4. **Performance Testing**

```python
import time
import statistics

def test_performance(bot):
    """Measure response times"""
    response_times = []
    
    for i in range(100):
        start = time.time()
        bot.invoke({
            "messages": [HumanMessage(content=f"Test message {i}")]
        })
        response_times.append(time.time() - start)
    
    avg_time = statistics.mean(response_times)
    p95_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile
    
    assert avg_time < 1.0  # Average under 1 second
    assert p95_time < 2.0  # 95% under 2 seconds
```

## Performance Optimization Tips

### 1. **Optimize State Size**

```python
# Bad - Storing everything
class BadState(TypedDict):
    all_messages_ever: List[BaseMessage]  # Grows infinitely
    entire_user_history: dict            # Too much data
    
# Good - Store only what's needed
class GoodState(TypedDict):
    recent_messages: Annotated[List[BaseMessage], operator.add]
    current_task: str
    summary: str  # Compressed history

def compress_messages(state: dict) -> dict:
    """Periodically compress old messages"""
    messages = state["recent_messages"]
    
    if len(messages) > 20:
        # Keep last 5, summarize the rest
        summary = summarize_messages(messages[:-5])
        return {
            "recent_messages": messages[-5:],
            "summary": state.get("summary", "") + "\n" + summary
        }
    return {}
```

### 2. **Use Async Operations**

```python
# Slow - Sequential operations
def slow_node(state: dict) -> dict:
    result1 = fetch_data_1()  # 1 second
    result2 = fetch_data_2()  # 1 second
    result3 = fetch_data_3()  # 1 second
    # Total: 3 seconds

# Fast - Parallel async operations
async def fast_node(state: dict) -> dict:
    results = await asyncio.gather(
        fetch_data_1_async(),
        fetch_data_2_async(),
        fetch_data_3_async()
    )
    # Total: ~1 second
    return {"results": results}
```

### 3. **Cache Expensive Operations**

```python
from functools import lru_cache
import hashlib

# Cache LLM calls for identical inputs
@lru_cache(maxsize=100)
def cached_llm_call(prompt_hash: str) -> str:
    """Cache LLM responses for identical prompts"""
    # This will only call LLM once per unique prompt
    return llm.invoke(prompt_hash)

def smart_llm_node(state: dict) -> dict:
    prompt = create_prompt(state)
    prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
    
    # Use cached result if available
    response = cached_llm_call(prompt_hash)
    return {"response": response}
```

### 4. **Optimize Tool Calls**

```python
# Bad - Multiple individual tool calls
def inefficient_node(state: dict) -> dict:
    account = get_account(state["account_id"])
    contacts = get_contacts(state["account_id"])
    opportunities = get_opportunities(state["account_id"])
    
# Good - Batch tool call
def efficient_node(state: dict) -> dict:
    # Single tool that fetches all related data
    account_data = get_account_with_relations(
        state["account_id"],
        include=["contacts", "opportunities"]
    )
```

### 5. **Minimize State Updates**

```python
# Bad - Update state multiple times
def chatty_node(state: dict) -> dict:
    return {"status": "starting"}
    # ... some work ...
    return {"status": "processing"}
    # ... more work ...
    return {"status": "done", "result": result}

# Good - Update once at the end
def efficient_node(state: dict) -> dict:
    # Do all work
    result = do_all_processing()
    
    # Single state update
    return {
        "status": "done",
        "result": result
    }
```

## Real Examples from Our Codebase

### Example 1: Orchestrator Memory Management

```python
# From src/orchestrator/main.py
async def update_memory(state: UpdateMemoryState, config: RunnableConfig) -> dict:
    """Background task to extract and update memory from conversation"""
    store = config["configurable"]["store"]
    user_id = config["configurable"]["user_id"]
    
    # Smart extraction - only process new messages
    last_processed_index = state.get("last_memory_update_index", 0)
    messages_to_process = state["messages"][last_processed_index:]
    
    if not messages_to_process:
        return {}  # Nothing to process
    
    # Use TrustCall for structured extraction
    extractor = create_extractor(
        llm,
        tools=[SimpleMemoryExtractor],
        tool_choice="SimpleMemoryExtractor"
    )
    
    try:
        # Extract structured data
        extraction_result = await extractor.ainvoke({
            "messages": format_messages_for_extraction(messages_to_process)
        })
        
        # Merge with existing memory
        existing_memory = state.get("memory", SimpleMemory())
        updated_memory = merge_memories(existing_memory, extraction_result)
        
        # Persist to storage
        await store.aput(
            namespace=("memory", user_id),
            key="SimpleMemory",
            value=updated_memory
        )
        
        return {
            "memory": updated_memory,
            "last_memory_update_index": len(state["messages"])
        }
        
    except Exception as e:
        logger.error(f"Memory update failed: {e}")
        return {}  # Don't crash the whole graph
```

### Example 2: Agent Communication with Circuit Breaker

```python
# From src/a2a/protocol.py
class A2AProtocol:
    def __init__(self):
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            timeout=60,
            half_open_max_calls=3
        )
        
        # Connection pooling for performance
        self.connector = aiohttp.TCPConnector(
            limit=50,
            limit_per_host=20,
            ttl_dns_cache=300
        )
    
    async def send_task(self, agent_url: str, task: A2ATask) -> Any:
        """Send task to agent with resilience patterns"""
        
        @self.circuit_breaker
        async def _send():
            async with aiohttp.ClientSession(connector=self.connector) as session:
                async with session.post(
                    f"{agent_url}/a2a",
                    json=create_jsonrpc_request("process_task", task.to_rpc()),
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        raise A2AError(f"Agent returned {response.status}")
                    
                    result = await response.json()
                    if "error" in result:
                        raise A2AError(result["error"]["message"])
                    
                    return result["result"]
        
        try:
            return await _send()
        except CircuitBreakerOpen:
            logger.warning(f"Circuit breaker open for {agent_url}")
            # Fallback logic
            return {"error": "Agent temporarily unavailable"}
```

### Example 3: Tool Selection with Detailed Descriptions

```python
# From src/orchestrator/agent_caller_tools.py
class SalesforceAgentTool(BaseTool):
    """Tool for interacting with Salesforce CRM"""
    
    name: str = "salesforce_agent"
    description: str = """Use this tool for ANY Salesforce CRM operations:

    Examples of when to use this tool:
    - "Get the Genepoint account" 
    - "Show me all contacts for Acme Corp"
    - "Create a new lead for John Smith"
    - "Update opportunity XYZ to Closed Won"
    - "Find all open cases"
    
    The tool will return formatted, human-readable results.
    """
    
    def _run(self, instruction: str) -> str:
        """Synchronous version for backwards compatibility"""
        import asyncio
        return asyncio.run(self._arun(instruction))
    
    async def _arun(self, instruction: str) -> str:
        """Send instruction to Salesforce agent"""
        try:
            # Get agent details from registry
            agent = find_agent_by_capability("salesforce_operations")
            if not agent:
                return "Salesforce agent is not available"
            
            # Create task with context preservation
            task = A2ATask(
                id=str(uuid.uuid4()),
                instruction=instruction,
                context={"source": "orchestrator"},
                metadata={"timestamp": datetime.now().isoformat()}
            )
            
            # Send via A2A protocol
            protocol = A2AProtocol()
            result = await protocol.send_task(agent.endpoint, task)
            
            # Format response for user
            return format_agent_response(result)
            
        except Exception as e:
            logger.error(f"Salesforce agent error: {e}")
            return f"I encountered an error accessing Salesforce: {str(e)}"
```

### Example 4: Conditional Routing with State

```python
# From src/orchestrator/main.py
def tools_condition(state: OrchestratorState) -> Literal["tools", "__end__"]:
    """Decide whether to run tools or end"""
    messages = state.get("messages", [])
    
    if not messages:
        return "__end__"
    
    last_message = messages[-1]
    
    # Check if LLM called tools
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        logger.info(f"Routing to tools - {len(last_message.tool_calls)} calls")
        return "tools"
    
    # Check for special cases that need tools
    if isinstance(last_message, HumanMessage):
        content = last_message.content.lower()
        
        # Pattern matching for tool triggers
        tool_triggers = [
            "get", "fetch", "show", "find", "create", 
            "update", "delete", "list", "search"
        ]
        
        if any(trigger in content for trigger in tool_triggers):
            logger.info("Detected tool trigger in user message")
            return "tools"
    
    return "__end__"
```

## Troubleshooting Guide

### Problem 1: "My node isn't being called"

**Symptoms**: A node you added doesn't execute

**Common Causes**:
1. No edge leading to the node
2. Conditional edge logic returning wrong value
3. Graph ending before reaching the node

**Solution**:
```python
# Debug your graph structure
print(app.get_graph().draw_ascii())

# Add logging to conditional edges
def my_condition(state):
    result = "node_a" if state["some_value"] else "node_b"
    print(f"Condition returning: {result}")
    return result

# Verify edges are added
graph.add_edge("start", "my_node")  # Make sure this exists
```

### Problem 2: "State isn't updating correctly"

**Symptoms**: State changes aren't persisting between nodes

**Common Causes**:
1. Returning None from node
2. Using wrong key names
3. Modifying state directly instead of returning updates

**Solution**:
```python
# Wrong - Modifying state directly
def bad_node(state: dict) -> dict:
    state["value"] = "new"  # This won't work!
    return {}

# Right - Return updates
def good_node(state: dict) -> dict:
    return {"value": "new"}  # This will update state

# Right - With reducer for lists
class MyState(TypedDict):
    messages: Annotated[List[str], operator.add]

def append_node(state: MyState) -> dict:
    return {"messages": ["new message"]}  # Will be appended
```

### Problem 3: "Getting recursion limit errors"

**Symptoms**: `RecursionError` or hitting recursion limits

**Common Causes**:
1. Infinite loops in conditional edges
2. Nodes calling each other indefinitely
3. Recursion limit too low

**Solution**:
```python
# Add loop detection
def safe_routing(state: dict) -> str:
    loop_count = state.get("loop_count", 0)
    
    if loop_count > 5:
        logger.warning("Loop detected, breaking out")
        return "__end__"
    
    # Your routing logic
    if should_retry(state):
        return "retry"
    else:
        return "continue"

# Increase recursion limit if needed
config = {
    "recursion_limit": 50,  # Default is 25
    "configurable": {"thread_id": "test"}
}
```

### Problem 4: "Memory/checkpointing issues"

**Symptoms**: State not persisting, can't resume conversations

**Common Causes**:
1. Not using thread_id
2. Checkpointer not configured
3. State too large to serialize

**Solution**:
```python
# Always use thread_id
config = {"configurable": {"thread_id": "user_123"}}

# Verify checkpointer is set up
checkpointer = MemorySaver()
app = graph.compile(checkpointer=checkpointer)

# Handle serialization issues
class MyState(TypedDict):
    data: dict  # JSON-serializable
    # Avoid: custom objects, lambdas, file handles

# For large state, use external storage
async def store_large_data(state: dict) -> dict:
    large_data = state.get("large_data")
    if large_data:
        # Store externally
        data_id = await store.save(large_data)
        return {"large_data_id": data_id}  # Store reference only
```

### Problem 5: "Async errors"

**Symptoms**: `RuntimeError: This event loop is already running`

**Common Causes**:
1. Mixing sync and async incorrectly
2. Not using proper async context

**Solution**:
```python
# For Jupyter notebooks
import nest_asyncio
nest_asyncio.apply()

# Use async properly
async def main():
    app = build_graph()
    result = await app.ainvoke({"messages": []})
    return result

# Run correctly
import asyncio
asyncio.run(main())

# Or use sync version
result = app.invoke({"messages": []})
```

## Summary

LangGraph is a powerful framework that makes building stateful AI applications much easier. Remember these key points:

1. **Think in Graphs**: Design your logic as nodes and edges
2. **State is King**: Carefully design your state structure
3. **Use Checkpointing**: Enable conversation persistence
4. **Test Everything**: Unit test nodes, integration test flows
5. **Monitor Performance**: Use async, cache, and optimize state
6. **Handle Errors**: Plan for failures with proper error handling

Start simple with basic graphs, then gradually add complexity as you get comfortable. The examples in our codebase show production-ready patterns you can learn from and adapt.

Happy coding with LangGraph!