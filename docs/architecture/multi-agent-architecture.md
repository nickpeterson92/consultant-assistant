# Multi-Agent System Architecture Documentation

## 📚 Table of Contents

1. [Introduction for Junior Engineers](#introduction-for-junior-engineers)
2. [What is a Multi-Agent System?](#what-is-a-multi-agent-system)
3. [System Overview with Detailed Diagrams](#system-overview-with-detailed-diagrams)
4. [Core Concepts Explained](#core-concepts-explained)
5. [Step-by-Step Walkthroughs](#step-by-step-walkthroughs)
6. [Common Pitfalls and How to Avoid Them](#common-pitfalls-and-how-to-avoid-them)
7. [Practical Examples](#practical-examples)
8. [Architecture Deep Dive](#architecture-deep-dive)
9. [Development Guide](#development-guide)
10. [Testing and Debugging](#testing-and-debugging)
11. [Code Metrics and Performance](#code-metrics-and-performance)
12. [Glossary of Terms](#glossary-of-terms)
13. [FAQ for Junior Engineers](#faq-for-junior-engineers)

---

## Introduction for Junior Engineers

Welcome! This guide will help you understand and contribute to our multi-agent orchestrator system. Don't worry if some concepts seem complex at first - we'll break everything down step by step.

### What You'll Learn

- How AI agents work together like a team
- How to add new features to existing agents
- How to debug when things go wrong
- How to write tests for agent interactions
- Best practices that will make you a better engineer

### Prerequisites

Before diving in, you should be comfortable with:
- Python basics (functions, classes, async/await)
- HTTP and REST APIs
- Basic command line usage
- Git version control

If you're not familiar with these, check out our [Prerequisites Guide](prerequisites.md) first.

---

## What is a Multi-Agent System?

### The Restaurant Analogy

Imagine a restaurant:
- **Host (Orchestrator)**: Greets customers, understands what they want, assigns the right staff
- **Waiter (Salesforce Agent)**: Specializes in taking orders (CRM operations)
- **Chef (Future Cooking Agent)**: Specializes in preparing food
- **Cashier (Future Finance Agent)**: Handles payments

Each person (agent) has specific skills, but they work together to serve the customer!

### In Technical Terms

A multi-agent system consists of:
1. **Multiple autonomous programs (agents)** that can work independently
2. **A coordinator (orchestrator)** that manages communication
3. **Standard protocols** for agents to talk to each other
4. **Shared memory** to remember important information

### Why Use Multiple Agents?

**Benefits:**
- **Specialization**: Each agent is an expert in one area
- **Scalability**: Add more agents as needed without changing existing ones
- **Reliability**: If one agent fails, others continue working
- **Maintainability**: Easier to update one agent without affecting others

**Real Example:**
```python
# Instead of one massive program doing everything:
def handle_all_requests(request):
    if request.type == "salesforce":
        # 1000 lines of Salesforce code
    elif request.type == "travel":
        # 1000 lines of travel code
    # ... becomes unmaintainable!

# We have specialized agents:
class SalesforceAgent:
    def handle_crm_request(self, request):
        # Focused, maintainable code

class TravelAgent:
    def handle_travel_request(self, request):
        # Separate, testable code
```

---

## System Overview with Detailed Diagrams

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Interface Layer                        │
│                                                                     │
│  What it does: Accepts user input through CLI, API, or future web   │
│  Example: "Show me all contacts for Acme Corp"                      │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ User Request
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Orchestrator Agent                             │
│                                                                     │
│  What it does: The "brain" that understands requests and delegates  │
│                                                                     │
│  ┌────────────────┐  ┌──────────────┐  ┌────────────────────────┐   │
│  │  LangGraph     │  │    Agent     │  │   Conversation         │   │
│  │  State Machine │  │   Registry   │  │   Management           │   │
│  │                │  │              │  │                        │   │
│  │  Manages flow  │  │  Knows which │  │  Remembers what you    │   │
│  │  of operations │  │  agents exist│  │  talked about          │   │
│  └────────────────┘  └──────────────┘  └────────────────────────┘   │
│                                                                     │
│  ┌────────────────┐  ┌──────────────┐  ┌────────────────────────┐   │
│  │    Memory      │  │   Service    │  │     Background         │   │
│  │  Management    │  │  Discovery   │  │     Processing         │   │
│  │                │  │              │  │                        │   │
│  │  Stores data   │  │  Finds agents│  │  Runs periodic tasks   │   │
│  │  from chats    │  │  at runtime  │  │  like memory cleanup   │   │
│  └────────────────┘  └──────────────┘  └────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ Decides which agent to use
                                ▼
                        ┌───────────────┐
                        │ A2A Protocol  │
                        │ (JSON-RPC 2.0)│
                        │               │
                        │ Standardized  │
                        │ communication │
                        └───────┬───────┘
                                │ Sends task to agent
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
┌───────▼────────┐     ┌────────▼───────┐      ┌────────▼───────┐
│   Salesforce   │     │   Travel       │      │   Finance      │
│     Agent      │     │   Agent        │      │   Agent        │
│                │     │   (Future)     │      │   (Future)     │
│  Handles CRM   │     │  Books trips   │      │  Processes     │
│  operations    │     │                │      │  expenses      │
└────────────────┘     └────────────────┘      └────────────────┘
```

### Request Flow - Step by Step

Let's trace a request through the system:

```
1. User Input: "Get all contacts for Acme Corp"
       │
       ▼
2. Orchestrator Receives Request
   - Parses natural language
   - Identifies intent: "retrieve contacts"
   - Identifies entity: "Acme Corp"
       │
       ▼
3. Agent Selection
   - Checks registry: "Which agent handles contacts?"
   - Finds: SalesforceAgent has "contact_management" capability
       │
       ▼
4. Task Creation
   - Creates A2A task with:
     • Instruction: "Get contacts for account: Acme Corp"
     • Context: User ID, session info
     • Memory: Previous interactions
       │
       ▼
5. A2A Protocol Call
   - Sends HTTP POST to Salesforce Agent
   - Includes task in JSON-RPC format
       │
       ▼
6. Salesforce Agent Processing
   - Receives task
   - Queries Salesforce API
   - Formats results
       │
       ▼
7. Response Return
   - Agent sends results back
   - Orchestrator receives data
       │
       ▼
8. Memory Update
   - Stores contact info in memory
   - Updates conversation history
       │
       ▼
9. User Response
   - Formats data for display
   - Returns to user: "Found 3 contacts for Acme Corp..."
```

---

## Core Concepts Explained

### 1. Agents

**What is an Agent?**
An agent is an independent program that:
- Has specific capabilities (like "I can handle Salesforce")
- Can receive tasks and return results
- Operates autonomously (doesn't need constant supervision)

**Agent Anatomy:**
```python
class Agent:
    def __init__(self):
        self.name = "SalesforceAgent"
        self.capabilities = ["crm_operations", "contact_management"]
        self.tools = [GetContactTool(), CreateLeadTool(), ...]
    
    async def process_task(self, task):
        # 1. Understand what's being asked
        # 2. Use appropriate tools
        # 3. Return results
        pass
    
    def get_capabilities(self):
        # Tell others what I can do
        return self.capabilities
```

### 2. Orchestrator

**What is the Orchestrator?**
Think of it as the project manager that:
- Talks to users in natural language
- Breaks down complex requests
- Assigns work to the right agents
- Combines results into coherent responses

**Key Responsibilities:**
```python
class Orchestrator:
    async def handle_user_request(self, request):
        # 1. Understand intent
        intent = self.parse_request(request)
        
        # 2. Find capable agent
        agent = self.registry.find_agent_for_capability(intent.capability)
        
        # 3. Delegate work
        result = await self.delegate_to_agent(agent, intent)
        
        # 4. Return formatted response
        return self.format_response(result)
```

### 3. A2A Protocol

**What is A2A (Agent-to-Agent) Protocol?**
It's like a common language that all agents speak. Just like HTTP is a standard for web communication, A2A is our standard for agent communication.

**Key Components:**
```python
# Standard message format
{
    "jsonrpc": "2.0",
    "method": "process_task",
    "params": {
        "task_id": "unique-id-123",
        "instruction": "Get all contacts for Acme Corp",
        "context": {
            "user_id": "user123",
            "session_id": "session456"
        }
    },
    "id": 1
}
```

### 4. State Management

**What is State?**
State is all the information the system needs to remember:
- Current conversation messages
- User preferences
- Retrieved data (like Salesforce records)
- System events

**State Flow:**
```python
# State is like a notebook that gets passed around
state = {
    "messages": ["User: Get contacts", "Assistant: Finding contacts..."],
    "memory": {
        "accounts": [{"name": "Acme Corp", "id": "001"}],
        "contacts": []  # Will be filled by agent
    },
    "user_id": "user123"
}

# Each component updates relevant parts
state = orchestrator.process(state)
state = agent.add_results(state)
state = memory_manager.persist(state)
```

### 5. LangGraph

**What is LangGraph?**
LangGraph is a framework for building stateful AI applications. Think of it as a way to create workflows where each step can make decisions.

**Simple Example:**
```python
# Define a workflow graph
graph = StateGraph(State)

# Add nodes (steps in the workflow)
graph.add_node("understand_request", understand_request_node)
graph.add_node("call_agent", call_agent_node)
graph.add_node("format_response", format_response_node)

# Define flow
graph.add_edge("understand_request", "call_agent")
graph.add_edge("call_agent", "format_response")

# Compile and run
app = graph.compile()
result = await app.ainvoke(initial_state)
```

---

## Step-by-Step Walkthroughs

### Walkthrough 1: Processing Your First Request

Let's walk through what happens when a user asks: "Show me all opportunities for Acme Corp"

**Step 1: User Input**
```bash
$ python orchestrator.py
> Show me all opportunities for Acme Corp
```

**Step 2: Orchestrator Receives Message**
```python
# In orchestrator/main.py
async def handle_message(state: OrchestratorState) -> OrchestratorState:
    # Get the latest user message
    user_message = state["messages"][-1].content
    # user_message = "Show me all opportunities for Acme Corp"
```

**Step 3: Intent Recognition**
```python
# The LLM analyzes the request
intent = await llm.analyze(user_message)
# Result: {
#   "action": "retrieve",
#   "entity": "opportunities",
#   "filter": {"account_name": "Acme Corp"}
# }
```

**Step 4: Agent Selection**
```python
# Find agent that handles opportunities
agent = registry.find_agent_for_capability("opportunity_management")
# Result: SalesforceAgent at http://localhost:8001
```

**Step 5: Task Creation**
```python
# Create task for the agent
task = A2ATask(
    instruction="Get all opportunities for account: Acme Corp",
    context={
        "user_id": state["user_id"],
        "request_id": generate_id()
    }
)
```

**Step 6: A2A Call**
```python
# Send task to agent
response = await a2a_client.call_agent(
    agent_url="http://localhost:8001",
    task=task
)
```

**Step 7: Agent Processing**
```python
# In salesforce_agent/main.py
async def process_task(task: A2ATask) -> A2AResult:
    # 1. Parse instruction
    # 2. Call Salesforce API
    opportunities = await salesforce_client.query(
        "SELECT Id, Name, Amount, StageName "
        "FROM Opportunity "
        "WHERE Account.Name = 'Acme Corp'"
    )
    # 3. Return results
    return A2AResult(artifacts=[opportunities])
```

**Step 8: Response Formatting**
```python
# Back in orchestrator
formatted = f"Found {len(opportunities)} opportunities for Acme Corp:\n"
for opp in opportunities:
    formatted += f"- {opp.name}: ${opp.amount} ({opp.stage})\n"
```

**Step 9: Memory Update**
```python
# Store in memory for future reference
state["memory"]["opportunities"].extend(opportunities)
await memory_store.save(state["user_id"], state["memory"])
```

**Step 10: User Sees Result**
```
Found 3 opportunities for Acme Corp:
- Acme Corp - Enterprise Deal: $50,000 (Negotiation)
- Acme Corp - Renewal: $25,000 (Closed Won)
- Acme Corp - Expansion: $75,000 (Proposal)
```

### Walkthrough 2: Adding a New Tool to an Agent

Let's add a new tool to search for leads by industry.

**Step 1: Create the Tool Class**
```python
# In src/tools/salesforce_tools.py

class SearchLeadsByIndustryTool(BaseTool):
    """Tool to search for leads by industry."""
    
    name: str = "search_leads_by_industry"
    description: str = "Search for leads in a specific industry"
    
    def _run(self, industry: str) -> List[Dict]:
        """Search for leads by industry.
        
        Args:
            industry: The industry to search for (e.g., "Technology", "Healthcare")
            
        Returns:
            List of leads in that industry
        """
        try:
            # Input validation
            if not industry or not isinstance(industry, str):
                raise ValueError("Industry must be a non-empty string")
            
            # Build SOQL query with proper escaping
            escaped_industry = industry.replace("'", "\\'")
            query = f"""
                SELECT Id, Name, Company, Email, Industry, Status
                FROM Lead
                WHERE Industry = '{escaped_industry}'
                LIMIT 100
            """
            
            # Execute query
            sf_client = SalesforceClient()
            results = sf_client.query(query)
            
            # Format results
            leads = []
            for record in results['records']:
                leads.append({
                    'id': record['Id'],
                    'name': record['Name'],
                    'company': record['Company'],
                    'email': record['Email'],
                    'industry': record['Industry'],
                    'status': record['Status']
                })
            
            return leads
            
        except Exception as e:
            logger.error(f"Error searching leads by industry: {e}")
            raise ToolException(f"Failed to search leads: {str(e)}")
```

**Step 2: Add Tool to Agent**
```python
# In src/agents/salesforce/main.py

# Import the new tool
from src.tools.salesforce_tools import SearchLeadsByIndustryTool

# Add to agent's tool list
tools = [
    GetAccountTool(),
    GetContactTool(),
    GetOpportunityTool(),
    # ... existing tools ...
    SearchLeadsByIndustryTool()  # Add our new tool
]
```

**Step 3: Update Agent Capabilities**
```python
# In agent_registry.json
{
    "agents": [
        {
            "name": "salesforce_agent",
            "capabilities": [
                "account_management",
                "contact_management",
                "opportunity_tracking",
                "lead_search_by_industry"  // Add new capability
            ]
        }
    ]
}
```

**Step 4: Test the New Tool**
```python
# In tests/test_salesforce_tools.py

def test_search_leads_by_industry():
    tool = SearchLeadsByIndustryTool()
    
    # Test valid search
    results = tool.run("Technology")
    assert isinstance(results, list)
    assert all('industry' in lead for lead in results)
    
    # Test empty industry
    with pytest.raises(ValueError):
        tool.run("")
    
    # Test SQL injection protection
    results = tool.run("Tech'; DROP TABLE Lead; --")
    # Should safely escape and not break
```

**Step 5: Use the Tool**
```bash
$ python orchestrator.py
> Find all leads in the Technology industry

Finding leads in Technology industry...
Found 15 leads:
- John Smith (TechCorp) - john@techcorp.com
- Jane Doe (StartupXYZ) - jane@startup.xyz
...
```

### Walkthrough 3: Debugging a Failed Agent Call

When things go wrong, here's how to debug:

**Step 1: Check the Logs**
```bash
# Check orchestrator logs
tail -f logs/orchestrator.log | grep ERROR

# Check specific agent logs
tail -f logs/salesforce_agent.log

# Check A2A protocol logs
tail -f logs/a2a_protocol.log
```

**Step 2: Understand the Error**
```json
{
    "timestamp": "2024-01-15T10:30:45Z",
    "level": "ERROR",
    "component": "orchestrator",
    "error": "Agent call failed",
    "details": {
        "agent": "salesforce_agent",
        "error_type": "ConnectionTimeout",
        "url": "http://localhost:8001/a2a",
        "timeout": 30
    }
}
```

**Step 3: Check Agent Health**
```python
# Quick health check script
import aiohttp
import asyncio

async def check_agent_health():
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                "http://localhost:8001/health",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    print("Agent is healthy")
                else:
                    print(f"Agent unhealthy: {response.status}")
        except Exception as e:
            print(f"Agent unreachable: {e}")

asyncio.run(check_agent_health())
```

**Step 4: Check Circuit Breaker Status**
```python
# In the orchestrator
circuit_status = a2a_client.get_circuit_breaker_status("salesforce_agent")
print(f"Circuit breaker state: {circuit_status.state}")
print(f"Failure count: {circuit_status.failure_count}")
print(f"Last failure: {circuit_status.last_failure_time}")
```

**Step 5: Manual Task Test**
```python
# Test the agent directly
import json
import requests

task = {
    "jsonrpc": "2.0",
    "method": "process_task",
    "params": {
        "task": {
            "instruction": "Get account named Test",
            "context": {"user_id": "test"}
        }
    },
    "id": 1
}

response = requests.post(
    "http://localhost:8001/a2a",
    json=task,
    timeout=30
)

print(json.dumps(response.json(), indent=2))
```

---

## Common Pitfalls and How to Avoid Them

### Pitfall 1: Forgetting to Start Agents Before Orchestrator

**❌ Wrong Way:**
```bash
# Starting orchestrator first
$ python orchestrator.py
Error: No agents available in registry
```

**✅ Right Way:**
```bash
# Start agents first
$ python salesforce_agent.py --port 8001 &
$ python orchestrator.py

# Or use the system starter
$ python start_system.py
```

**Why it matters:** The orchestrator needs to discover agents at startup. If no agents are running, it has nothing to delegate to.

### Pitfall 2: Not Handling Agent Failures Gracefully

**❌ Wrong Way:**
```python
# This will crash if agent is down
result = await call_agent(agent_url, task)
return result['data']  # KeyError if agent failed
```

**✅ Right Way:**
```python
try:
    result = await call_agent(agent_url, task)
    if result and 'data' in result:
        return result['data']
    else:
        logger.warning("Agent returned empty result")
        return fallback_response()
except AgentCallError as e:
    logger.error(f"Agent call failed: {e}")
    return error_response(f"Service temporarily unavailable")
```

### Pitfall 3: Creating Infinite Loops in State Updates

**❌ Wrong Way:**
```python
# This creates an infinite loop
def update_state(state):
    state["counter"] += 1
    # No exit condition!
    return update_state(state)
```

**✅ Right Way:**
```python
def update_state(state):
    state["counter"] += 1
    
    # Always have an exit condition
    if state["counter"] >= MAX_ITERATIONS:
        state["status"] = "completed"
        return state
    
    # Continue only if needed
    if needs_more_processing(state):
        return continue_processing(state)
    
    return state
```

### Pitfall 4: Blocking the Event Loop

**❌ Wrong Way:**
```python
# This blocks the entire system
def process_task(task):
    time.sleep(10)  # Blocks event loop!
    result = slow_sync_operation()
    return result
```

**✅ Right Way:**
```python
# Use async operations
async def process_task(task):
    await asyncio.sleep(10)  # Non-blocking
    result = await slow_async_operation()
    return result

# Or run sync operations in executor
async def process_task_with_sync(task):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,  # Use default executor
        slow_sync_operation,
        task
    )
    return result
```

### Pitfall 5: Not Validating User Input

**❌ Wrong Way:**
```python
# Dangerous - could lead to injection attacks
query = f"SELECT * FROM Account WHERE Name = '{user_input}'"
```

**✅ Right Way:**
```python
# Always validate and escape input
from src.utils.input_validation import sanitize_soql_string

if not user_input or len(user_input) > 100:
    raise ValueError("Invalid input")

escaped_input = sanitize_soql_string(user_input)
query = f"SELECT * FROM Account WHERE Name = '{escaped_input}'"
```

### Pitfall 6: Ignoring Memory Limits

**❌ Wrong Way:**
```python
# This could consume all memory
state["messages"].append(new_message)  # Grows forever!
```

**✅ Right Way:**
```python
# Implement memory management
MAX_MESSAGES = 100

state["messages"].append(new_message)

# Prune old messages
if len(state["messages"]) > MAX_MESSAGES:
    # Keep recent messages and summary
    state["summary"] = summarize_old_messages(state["messages"][:-50])
    state["messages"] = state["messages"][-50:]
```

### Pitfall 7: Not Using Connection Pooling

**❌ Wrong Way:**
```python
# Creates new connection for each request
async def call_agent(url, task):
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=task) as response:
            return await response.json()
```

**✅ Right Way:**
```python
# Reuse connections
class A2AClient:
    def __init__(self):
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(
                limit=50,
                limit_per_host=20
            )
        )
        return self
    
    async def call_agent(self, url, task):
        async with self.session.post(url, json=task) as response:
            return await response.json()
```

### Pitfall 8: Poor Error Messages

**❌ Wrong Way:**
```python
except Exception:
    return "Error occurred"  # Not helpful!
```

**✅ Right Way:**
```python
except ValidationError as e:
    return f"Invalid input: {e.field} must be {e.requirement}"
except AgentTimeoutError as e:
    return f"Service is taking longer than expected. Please try again."
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    return "An unexpected error occurred. Our team has been notified."
```

---

## Practical Examples

### Example 1: Building a Simple Health Check Endpoint

```python
# In src/agents/base_agent.py

from aiohttp import web
import time

class BaseAgent:
    def __init__(self, name: str, port: int):
        self.name = name
        self.port = port
        self.start_time = time.time()
        self.request_count = 0
        
    async def health_handler(self, request):
        """Health check endpoint for monitoring."""
        uptime = time.time() - self.start_time
        
        health_data = {
            "status": "healthy",
            "agent": self.name,
            "uptime_seconds": uptime,
            "requests_processed": self.request_count,
            "version": "1.0.0"
        }
        
        return web.json_response(health_data)
    
    def setup_routes(self, app):
        """Add routes to the web app."""
        app.router.add_get('/health', self.health_handler)
```

### Example 2: Implementing Retry Logic

```python
# In src/utils/retry.py

import asyncio
import random
from typing import TypeVar, Callable, Optional

T = TypeVar('T')

async def retry_with_backoff(
    func: Callable[..., T],
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True
) -> T:
    """
    Retry a function with exponential backoff.
    
    Args:
        func: Function to retry
        max_attempts: Maximum number of attempts
        base_delay: Initial delay between retries
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff
        jitter: Add randomness to prevent thundering herd
    
    Example:
        result = await retry_with_backoff(
            lambda: call_external_api(data),
            max_attempts=5
        )
    """
    attempt = 0
    
    while attempt < max_attempts:
        try:
            return await func()
        except Exception as e:
            attempt += 1
            
            if attempt >= max_attempts:
                raise e
            
            # Calculate delay with exponential backoff
            delay = min(
                base_delay * (exponential_base ** (attempt - 1)),
                max_delay
            )
            
            # Add jitter to prevent synchronized retries
            if jitter:
                delay = delay * (0.5 + random.random())
            
            print(f"Attempt {attempt} failed, retrying in {delay:.2f}s")
            await asyncio.sleep(delay)
```

### Example 3: Creating a Custom Memory Store

```python
# In src/utils/storage/custom_memory.py

from typing import Dict, Any, Optional
import json
import aiofiles
from datetime import datetime

class FileMemoryStore:
    """Simple file-based memory store for development."""
    
    def __init__(self, base_path: str = "./memory"):
        self.base_path = base_path
        
    async def save(self, user_id: str, key: str, value: Any) -> None:
        """Save data to file."""
        file_path = f"{self.base_path}/{user_id}/{key}.json"
        
        # Create directory if needed
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Add metadata
        data = {
            "value": value,
            "timestamp": datetime.now().isoformat(),
            "version": 1
        }
        
        # Write atomically
        temp_path = f"{file_path}.tmp"
        async with aiofiles.open(temp_path, 'w') as f:
            await f.write(json.dumps(data, indent=2))
        
        # Atomic rename
        os.rename(temp_path, file_path)
    
    async def load(self, user_id: str, key: str) -> Optional[Any]:
        """Load data from file."""
        file_path = f"{self.base_path}/{user_id}/{key}.json"
        
        if not os.path.exists(file_path):
            return None
        
        async with aiofiles.open(file_path, 'r') as f:
            data = json.loads(await f.read())
            return data["value"]
    
    async def delete(self, user_id: str, key: str) -> None:
        """Delete data file."""
        file_path = f"{self.base_path}/{user_id}/{key}.json"
        
        if os.path.exists(file_path):
            os.remove(file_path)
```

### Example 4: Building a Rate Limiter

```python
# In src/utils/rate_limiter.py

from collections import defaultdict
import time
import asyncio

class RateLimiter:
    """Simple rate limiter using token bucket algorithm."""
    
    def __init__(self, rate: int = 10, per: float = 60.0):
        """
        Args:
            rate: Number of allowed requests
            per: Time window in seconds
        """
        self.rate = rate
        self.per = per
        self.buckets = defaultdict(lambda: {
            'tokens': rate,
            'last_update': time.time()
        })
    
    async def check_rate_limit(self, key: str) -> bool:
        """Check if request is allowed."""
        bucket = self.buckets[key]
        now = time.time()
        
        # Refill tokens based on time passed
        time_passed = now - bucket['last_update']
        bucket['tokens'] = min(
            self.rate,
            bucket['tokens'] + (time_passed * self.rate / self.per)
        )
        bucket['last_update'] = now
        
        # Check if we have tokens
        if bucket['tokens'] >= 1:
            bucket['tokens'] -= 1
            return True
        
        return False
    
    async def wait_if_needed(self, key: str) -> None:
        """Wait until rate limit allows request."""
        while not await self.check_rate_limit(key):
            # Calculate wait time
            bucket = self.buckets[key]
            tokens_needed = 1 - bucket['tokens']
            wait_time = tokens_needed * self.per / self.rate
            
            await asyncio.sleep(wait_time)

# Usage example
rate_limiter = RateLimiter(rate=10, per=60)  # 10 requests per minute

async def make_api_call(user_id: str):
    await rate_limiter.wait_if_needed(user_id)
    # Now safe to make API call
    return await actual_api_call()
```

---

## Architecture Deep Dive

### Component Architecture

#### 1. Orchestrator Components

```python
# Core orchestrator structure
orchestrator/
├── main.py                 # LangGraph workflow definition
├── nodes/                  # Workflow nodes
│   ├── understand.py      # NLU node
│   ├── plan.py           # Planning node
│   ├── execute.py        # Execution node
│   └── respond.py        # Response node
├── tools/                  # Available tools
│   ├── agent_tools.py    # Agent communication
│   └── memory_tools.py   # Memory operations
└── state/                  # State management
    ├── models.py         # State definitions
    └── persistence.py    # State storage
```

#### 2. Agent Components

```python
# Standard agent structure
agent/
├── main.py                # Agent entry point
├── handler.py             # A2A request handler
├── tools/                 # Agent-specific tools
│   ├── __init__.py
│   └── domain_tools.py
├── models/                # Data models
│   └── domain_models.py
└── clients/               # External service clients
    └── api_client.py
```

### Data Flow Architecture

```python
# 1. Request enters system
user_request = "Get all contacts for Acme"

# 2. Orchestrator processes
state = {
    "messages": [HumanMessage(content=user_request)],
    "user_id": "user123",
    "memory": load_memory("user123")
}

# 3. LangGraph workflow executes
async def orchestrator_workflow(state):
    # Understand intent
    state = await understand_node(state)
    
    # Plan approach
    state = await planning_node(state)
    
    # Execute via agents
    state = await execution_node(state)
    
    # Format response
    state = await response_node(state)
    
    return state

# 4. Agent processes task
async def agent_process_task(task):
    # Validate task
    validated = validate_task(task)
    
    # Execute business logic
    result = await execute_business_logic(validated)
    
    # Return structured result
    return A2AResult(
        artifacts=[format_result(result)],
        metadata={"execution_time": elapsed}
    )

# 5. Results flow back
final_state = await orchestrator_workflow(initial_state)
response = final_state["messages"][-1].content
```

### Concurrency Model

```python
# Parallel agent execution
async def execute_parallel_tasks(tasks: List[Task]) -> List[Result]:
    """Execute multiple agent tasks concurrently."""
    
    # Create semaphore to limit concurrency
    semaphore = asyncio.Semaphore(10)  # Max 10 concurrent
    
    async def bounded_task(task):
        async with semaphore:
            return await execute_task(task)
    
    # Execute all tasks concurrently
    results = await asyncio.gather(
        *[bounded_task(task) for task in tasks],
        return_exceptions=True
    )
    
    # Handle results and exceptions
    processed_results = []
    for task, result in zip(tasks, results):
        if isinstance(result, Exception):
            logger.error(f"Task {task.id} failed: {result}")
            processed_results.append(error_result(task, result))
        else:
            processed_results.append(result)
    
    return processed_results
```

### Memory Management Architecture

```python
# Hierarchical memory system
class MemoryManager:
    def __init__(self):
        self.short_term = {}  # Current conversation
        self.long_term = {}   # Persistent storage
        self.working = {}     # Active processing
    
    async def update_memory(self, state: Dict) -> None:
        """Update all memory layers."""
        # Update short-term (conversation)
        self.short_term[state["user_id"]] = {
            "messages": state["messages"][-10:],  # Last 10
            "context": state.get("context", {})
        }
        
        # Extract to long-term
        extracted = await self.extract_important_info(state)
        await self.persist_to_long_term(state["user_id"], extracted)
        
        # Clear working memory
        self.working.pop(state["user_id"], None)
    
    async def extract_important_info(self, state: Dict) -> Dict:
        """Extract structured data from conversations."""
        # Use LLM to extract entities
        entities = await extract_entities(state["messages"])
        
        # Organize by type
        return {
            "accounts": entities.get("accounts", []),
            "contacts": entities.get("contacts", []),
            "tasks": entities.get("tasks", []),
            "preferences": entities.get("preferences", {})
        }
```

---

## Development Guide

### Setting Up Your Development Environment

#### Step 1: Clone and Setup

```bash
# Clone the repository
git clone https://github.com/your-org/multi-agent-orchestrator.git
cd multi-agent-orchestrator

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

#### Step 2: Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your credentials
# AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
# AZURE_OPENAI_API_KEY=your-api-key
# SFDC_USER=your-salesforce-username
# SFDC_PASS=your-salesforce-password
# SFDC_TOKEN=your-salesforce-token
```

#### Step 3: Run Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_orchestrator.py

# Run with coverage
pytest --cov=src --cov-report=html

# Run integration tests
pytest tests/integration/ -m integration
```

### Creating a New Agent

#### Step 1: Create Agent Structure

```bash
# Create new agent directory
mkdir -p src/agents/weather
cd src/agents/weather

# Create required files
touch __init__.py
touch main.py
touch tools.py
touch models.py
```

#### Step 2: Implement Agent

```python
# In src/agents/weather/main.py

from typing import Dict, Any
import asyncio
from aiohttp import web

from src.a2a.protocol import A2ATask, A2AResult, AgentCard
from src.agents.weather.tools import GetWeatherTool, GetForecastTool

class WeatherAgent:
    """Agent for weather information."""
    
    def __init__(self, port: int = 8002):
        self.port = port
        self.name = "weather_agent"
        self.tools = [GetWeatherTool(), GetForecastTool()]
        
    async def process_task(self, task: A2ATask) -> A2AResult:
        """Process weather-related tasks."""
        instruction = task.instruction.lower()
        
        if "weather" in instruction or "temperature" in instruction:
            # Extract location
            location = self.extract_location(instruction)
            
            # Get weather
            weather = self.tools[0].run(location)
            
            return A2AResult(
                artifacts=[{
                    "type": "weather_data",
                    "data": weather
                }]
            )
        
        elif "forecast" in instruction:
            location = self.extract_location(instruction)
            days = self.extract_days(instruction) or 5
            
            forecast = self.tools[1].run(location, days)
            
            return A2AResult(
                artifacts=[{
                    "type": "forecast_data",
                    "data": forecast
                }]
            )
        
        else:
            return A2AResult(
                error="Cannot handle this type of request"
            )
    
    def get_agent_card(self) -> AgentCard:
        """Return agent capabilities."""
        return AgentCard(
            name=self.name,
            description="Provides weather information and forecasts",
            capabilities=[
                "current_weather",
                "weather_forecast",
                "temperature_info"
            ],
            endpoints={
                "a2a": f"http://localhost:{self.port}/a2a",
                "health": f"http://localhost:{self.port}/health"
            }
        )
    
    async def start(self):
        """Start the agent server."""
        app = web.Application()
        
        # Add routes
        app.router.add_post('/a2a', self.handle_a2a_request)
        app.router.add_get('/a2a/agent-card', self.handle_agent_card)
        app.router.add_get('/health', self.handle_health)
        
        # Start server
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', self.port)
        await site.start()
        
        print(f"Weather agent running on port {self.port}")
        
        # Keep running
        await asyncio.Event().wait()
```

#### Step 3: Register Agent

```python
# In agent_registry.json
{
    "agents": [
        {
            "name": "weather_agent",
            "endpoint": "http://localhost:8002",
            "capabilities": [
                "current_weather",
                "weather_forecast"
            ],
            "health_check_interval": 30
        }
    ]
}
```

### Best Practices for Development

#### 1. Code Organization

```python
# Good: Separate concerns
src/
├── agents/           # Agent implementations
├── orchestrator/     # Orchestrator logic
├── utils/           # Shared utilities
├── models/          # Data models
└── clients/         # External clients

# Bad: Everything in one file
main.py  # 5000 lines of mixed code
```

#### 2. Error Handling

```python
# Good: Specific error handling
try:
    result = await call_external_api()
except APIAuthenticationError:
    # Handle auth issues
    await refresh_credentials()
    result = await call_external_api()  # Retry
except APIRateLimitError as e:
    # Handle rate limits
    wait_time = e.retry_after
    await asyncio.sleep(wait_time)
    result = await call_external_api()
except Exception as e:
    # Log unexpected errors
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise

# Bad: Catch-all exception handling
try:
    result = await call_external_api()
except:
    return None  # Swallowing errors
```

#### 3. Testing Patterns

```python
# Good: Comprehensive test coverage
class TestWeatherAgent:
    @pytest.fixture
    async def agent(self):
        """Create test agent."""
        agent = WeatherAgent(port=9999)
        yield agent
        # Cleanup if needed
    
    async def test_get_weather_success(self, agent, mock_api):
        """Test successful weather retrieval."""
        # Arrange
        mock_api.get_weather.return_value = {
            "temp": 72,
            "condition": "sunny"
        }
        
        task = A2ATask(
            instruction="What's the weather in NYC?"
        )
        
        # Act
        result = await agent.process_task(task)
        
        # Assert
        assert result.artifacts[0]["data"]["temp"] == 72
        assert not result.error
    
    async def test_invalid_location(self, agent):
        """Test handling of invalid location."""
        task = A2ATask(
            instruction="Weather in XYZ123"
        )
        
        result = await agent.process_task(task)
        
        assert result.error is not None
        assert "invalid location" in result.error.lower()
```

#### 4. Documentation

```python
# Good: Clear documentation
async def process_complex_request(
    request: str,
    context: Dict[str, Any],
    options: ProcessingOptions = None
) -> ProcessingResult:
    """
    Process a complex user request with context.
    
    This function handles multi-step requests that may require
    coordination between multiple agents. It maintains context
    throughout the processing pipeline.
    
    Args:
        request: The user's natural language request
        context: Current conversation context including:
            - user_id: Unique user identifier
            - session_id: Current session ID
            - memory: User's stored memory
        options: Optional processing configuration:
            - timeout: Maximum processing time (default: 30s)
            - max_agents: Maximum agents to involve (default: 3)
            - priority: Request priority level
    
    Returns:
        ProcessingResult containing:
            - response: Natural language response
            - artifacts: Any data retrieved
            - metadata: Processing metadata
    
    Raises:
        ValidationError: If request format is invalid
        TimeoutError: If processing exceeds timeout
        AgentError: If all agents fail
    
    Example:
        >>> result = await process_complex_request(
        ...     "Book a flight and hotel in NYC",
        ...     {"user_id": "123", "memory": {}},
        ...     ProcessingOptions(timeout=60)
        ... )
        >>> print(result.response)
        "I've found 3 flights and 5 hotels in NYC..."
    """
    # Implementation...
```

---

## Testing and Debugging

### Unit Testing Strategies

#### Testing Async Code

```python
# In tests/test_async_operations.py

import pytest
import asyncio
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_async_agent_call():
    """Test async agent communication."""
    # Create mock agent client
    mock_client = AsyncMock()
    mock_client.call_agent.return_value = {
        "result": "success",
        "data": {"count": 5}
    }
    
    # Test the call
    with patch('src.orchestrator.client', mock_client):
        result = await orchestrator.delegate_to_agent(
            "salesforce_agent",
            "get accounts"
        )
    
    # Verify
    assert result["data"]["count"] == 5
    mock_client.call_agent.assert_called_once()
```

#### Testing State Management

```python
# In tests/test_state_management.py

def test_state_update_preserves_history():
    """Test that state updates maintain history."""
    initial_state = {
        "messages": [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!")
        ],
        "memory": {},
        "user_id": "test123"
    }
    
    # Update state
    new_state = update_state(
        initial_state,
        new_message=HumanMessage(content="Get accounts")
    )
    
    # Verify history preserved
    assert len(new_state["messages"]) == 3
    assert new_state["messages"][0].content == "Hello"
    assert new_state["messages"][-1].content == "Get accounts"
```

### Integration Testing

#### Testing Agent Integration

```python
# In tests/integration/test_agent_integration.py

@pytest.mark.integration
async def test_orchestrator_agent_integration():
    """Test full orchestrator to agent flow."""
    # Start test agent
    test_agent = TestSalesforceAgent(port=9001)
    agent_task = asyncio.create_task(test_agent.start())
    
    # Wait for agent to be ready
    await wait_for_agent_ready("http://localhost:9001")
    
    try:
        # Create orchestrator with test config
        orchestrator = Orchestrator(
            agent_registry={"salesforce": "http://localhost:9001"}
        )
        
        # Send request
        result = await orchestrator.process_request(
            "Get all accounts"
        )
        
        # Verify result
        assert "accounts" in result
        assert len(result["accounts"]) > 0
        
    finally:
        # Cleanup
        agent_task.cancel()
```

### Debugging Techniques

#### 1. Debug Logging

```python
# In src/utils/debug.py

import functools
import time
import json

def debug_trace(func):
    """Decorator for detailed function tracing."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        func_name = func.__name__
        
        # Log entry
        logger.debug(f"→ Entering {func_name}")
        logger.debug(f"  Args: {args}")
        logger.debug(f"  Kwargs: {kwargs}")
        
        try:
            # Execute function
            result = await func(*args, **kwargs)
            
            # Log success
            elapsed = time.time() - start_time
            logger.debug(f"← Exiting {func_name} (success)")
            logger.debug(f"  Elapsed: {elapsed:.3f}s")
            logger.debug(f"  Result: {result}")
            
            return result
            
        except Exception as e:
            # Log failure
            elapsed = time.time() - start_time
            logger.error(f"← Exiting {func_name} (error)")
            logger.error(f"  Elapsed: {elapsed:.3f}s")
            logger.error(f"  Error: {e}")
            raise
    
    return wrapper

# Usage
@debug_trace
async def complex_operation(data):
    # This will be traced automatically
    return await process_data(data)
```

#### 2. State Inspection

```python
# In src/utils/inspection.py

class StateInspector:
    """Tool for debugging state issues."""
    
    @staticmethod
    def print_state_summary(state: Dict):
        """Print readable state summary."""
        print("\n=== State Summary ===")
        print(f"User ID: {state.get('user_id', 'Unknown')}")
        print(f"Messages: {len(state.get('messages', []))}")
        
        if state.get('messages'):
            print("\nRecent messages:")
            for msg in state['messages'][-3:]:
                role = "Human" if isinstance(msg, HumanMessage) else "AI"
                print(f"  [{role}] {msg.content[:50]}...")
        
        print(f"\nMemory items: {len(state.get('memory', {}))}")
        for key, value in state.get('memory', {}).items():
            print(f"  - {key}: {len(value)} items")
    
    @staticmethod
    def validate_state_transitions(old_state: Dict, new_state: Dict):
        """Validate state transition is valid."""
        issues = []
        
        # Check required fields
        for field in ['user_id', 'messages']:
            if field not in new_state:
                issues.append(f"Missing required field: {field}")
        
        # Check message ordering
        if 'messages' in old_state and 'messages' in new_state:
            old_count = len(old_state['messages'])
            new_count = len(new_state['messages'])
            
            if new_count < old_count:
                issues.append("Messages were removed (not allowed)")
        
        return issues
```

#### 3. Performance Profiling

```python
# In src/utils/profiling.py

from contextlib import asynccontextmanager
import cProfile
import pstats
import io

@asynccontextmanager
async def profile_async(name: str):
    """Profile async code execution."""
    profiler = cProfile.Profile()
    profiler.enable()
    
    try:
        yield
    finally:
        profiler.disable()
        
        # Generate report
        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.sort_stats('cumulative')
        stats.print_stats(20)  # Top 20 functions
        
        print(f"\n=== Profile: {name} ===")
        print(stream.getvalue())

# Usage
async def slow_operation():
    async with profile_async("slow_operation"):
        result = await complex_calculation()
        return result
```

### Common Debugging Scenarios

#### Scenario 1: Agent Not Responding

```python
# Debug script: check_agent_connectivity.py

import aiohttp
import asyncio
import sys

async def diagnose_agent(url: str):
    """Diagnose agent connectivity issues."""
    print(f"Diagnosing agent at {url}")
    
    # 1. Check basic connectivity
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{url}/health",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                print(f"✓ Health check: {response.status}")
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return
    
    # 2. Check A2A endpoint
    try:
        test_task = {
            "jsonrpc": "2.0",
            "method": "process_task",
            "params": {
                "task": {
                    "instruction": "test",
                    "context": {}
                }
            },
            "id": 1
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{url}/a2a",
                json=test_task,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                result = await response.json()
                print(f"✓ A2A endpoint: {response.status}")
                print(f"  Response: {result}")
    except Exception as e:
        print(f"✗ A2A endpoint failed: {e}")
    
    # 3. Check agent card
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{url}/a2a/agent-card",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                card = await response.json()
                print(f"✓ Agent card: {card.get('name')}")
                print(f"  Capabilities: {card.get('capabilities')}")
    except Exception as e:
        print(f"✗ Agent card failed: {e}")

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"
    asyncio.run(diagnose_agent(url))
```

#### Scenario 2: Memory Corruption

```python
# Debug script: check_memory_integrity.py

import json
from datetime import datetime

def check_memory_integrity(memory_file: str):
    """Check memory file for corruption."""
    print(f"Checking memory file: {memory_file}")
    
    try:
        with open(memory_file, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"✗ JSON parsing failed: {e}")
        # Try to recover
        with open(memory_file, 'r') as f:
            content = f.read()
            print(f"File content preview: {content[:200]}...")
        return
    
    # Validate structure
    issues = []
    
    if 'memories' not in data:
        issues.append("Missing 'memories' key")
    
    if 'metadata' not in data:
        issues.append("Missing 'metadata' key")
    
    # Check data types
    for memory in data.get('memories', []):
        if not isinstance(memory.get('id'), str):
            issues.append(f"Invalid ID type: {memory.get('id')}")
        
        if 'timestamp' in memory:
            try:
                datetime.fromisoformat(memory['timestamp'])
            except:
                issues.append(f"Invalid timestamp: {memory['timestamp']}")
    
    if issues:
        print("✗ Integrity issues found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("✓ Memory file is valid")
        print(f"  Total memories: {len(data.get('memories', []))}")

if __name__ == "__main__":
    check_memory_integrity("./memory_store.db")
```

---

## Code Metrics and Performance

### System Complexity Analysis

Understanding the balance between infrastructure and business logic is crucial for maintaining a healthy codebase.

#### Current Metrics (Post-Simplification)

**Infrastructure to Business Logic Ratio: 0.72:1**
- **Business Logic**: 4,183 lines (58.2%)
- **Infrastructure**: 3,009 lines (41.8%)

This represents a **58.9% improvement** from the previous 1.75:1 ratio, meaning we now have more business logic than infrastructure code.

#### Component Breakdown

**Business Logic Components (4,183 lines)**
- **Salesforce Tools**: 1,343 lines (32.1%) - Core CRM operations
- **Orchestrator Core**: 1,086 lines (26.0%) - LangGraph orchestration
- **SOQL Builder**: 386 lines (9.2%) - Query construction
- **Agent Tools**: 341 lines (8.2%) - Communication tools
- **Agent Registry**: 295 lines (7.1%) - Discovery system
- **Input Validation**: 286 lines (6.8%) - Business rules
- **Salesforce Agent**: 245 lines (5.9%) - CRM agent
- **Other**: 201 lines (4.7%) - Helpers, messages

**Infrastructure Components (3,009 lines)**
- **Logging**: 770 lines (25.6%) - Targeted logging system
- **Storage**: 413 lines (13.7%) - Simplified SQLite adapter
- **Protocol**: 544 lines (18.1%) - A2A protocol
- **Configuration**: 340 lines (11.3%) - Central config
- **Resilience**: 197 lines (6.5%) - Circuit breakers
- **Other**: 353 lines (11.7%) - Utilities

#### Recent Simplifications

1. **AsyncStoreAdapter**: 536 → 167 lines (69% reduction)
   - Removed unnecessary circuit breaker for local SQLite
   - Removed custom connection pooling
   - Removed metrics tracking
   - Kept only essential async wrapping

2. **SecurityConfig**: 17 → 9 lines (47% reduction)
   - Removed unused rate limiting
   - Removed unused file type restrictions
   - Kept only implemented features

**Total Code Removed**: ~377 lines of unnecessary abstractions

### Performance Characteristics

#### Response Time Targets
- **Simple queries** (e.g., "get account"): < 500ms
- **Complex operations** (e.g., "get all records"): < 2s
- **Memory operations**: < 50ms (local SQLite)
- **A2A communication**: < 100ms overhead

#### Concurrency Limits
- **Thread pool**: 4 workers (sufficient for 2-5 agents)
- **A2A connections**: 50 total, 20 per host
- **Concurrent tool calls**: Up to 8 per agent

#### Memory Usage
- **Base footprint**: ~100MB
- **Per conversation**: ~5MB (with full state)
- **SQLite cache**: Managed by SQLite (typically < 50MB)

### Architectural Principles Applied

1. **YAGNI (You Aren't Gonna Need It)**
   - Removed speculative features
   - Simplified abstractions
   - Focused on actual requirements

2. **KISS (Keep It Simple, Stupid)**
   - Simple AsyncStoreAdapter without over-engineering
   - Direct SQLite usage for local storage
   - Clear separation of concerns

3. **DRY (Don't Repeat Yourself)**
   - BaseAgentTool for common functionality
   - Centralized constants
   - Shared utilities

---

## Glossary of Terms

### A

**Agent**: An autonomous program that can perform specific tasks independently. Like a specialist on a team.

**A2A (Agent-to-Agent) Protocol**: The standardized way agents communicate with each other, similar to how HTTP is a standard for web communication.

**Async/Await**: Python's way of handling operations that take time (like network requests) without blocking other operations.

**Artifact**: A piece of data or result produced by an agent, like a list of contacts or a weather report.

### C

**Capability**: A specific skill or function an agent can perform, like "contact_management" or "weather_forecast".

**Circuit Breaker**: A pattern that prevents cascading failures by "breaking" the connection to a failing service temporarily.

**Checkpointing**: Saving the current state of a conversation so it can be resumed later.

**Connection Pooling**: Reusing network connections instead of creating new ones for each request, improving performance.

### D

**Delegation**: When the orchestrator assigns a task to a specific agent based on capabilities.

### E

**Event Loop**: Python's mechanism for handling multiple async operations concurrently.

**Endpoint**: A specific URL where an agent listens for requests, like `http://localhost:8001/a2a`.

### H

**Health Check**: A simple request to verify an agent is running and responsive.

### J

**JSON-RPC**: A standard protocol for remote procedure calls using JSON format.

**Jitter**: Random variation added to retry delays to prevent synchronized retries.

### L

**LangGraph**: A framework for building stateful AI applications with workflows.

**LLM (Large Language Model)**: The AI model (like GPT-4) that powers natural language understanding.

### M

**Memory Store**: Where the system saves information between conversations.

**Microservice**: A small, independent service that does one thing well (agents are microservices).

### O

**Orchestrator**: The central coordinator that manages user interactions and delegates to agents.

### R

**Registry**: A directory of available agents and their capabilities.

**Resilience**: The system's ability to handle failures gracefully.

**Retry Logic**: Automatically trying again when a request fails.

### S

**State**: All the information about a conversation, including messages, memory, and context.

**Stateless**: When a component doesn't store information between requests (agents are stateless).

**SOQL**: Salesforce Object Query Language, used to query Salesforce data.

### T

**Task**: A unit of work sent from the orchestrator to an agent.

**Timeout**: Maximum time to wait for an operation before considering it failed.

**Thread-Safe**: Code that works correctly when multiple operations happen at the same time.

### V

**Validation**: Checking that data meets expected format and constraints before processing.

---

## FAQ for Junior Engineers

### Q: How do I know which agent handles a request?

**A:** The orchestrator uses the agent registry to match capabilities. Each agent advertises what it can do:

```python
# Agent says: "I can do these things"
capabilities = ["weather_forecast", "current_weather"]

# Orchestrator checks: "Who can handle weather?"
agent = registry.find_agent_with_capability("weather_forecast")
```

### Q: What happens if an agent crashes?

**A:** Several safety mechanisms kick in:
1. **Circuit Breaker**: Stops sending requests to the crashed agent
2. **Retry Logic**: Tries a few times with delays
3. **Graceful Degradation**: System continues with reduced functionality
4. **Health Checks**: Detects when agent recovers

### Q: How do I add a new capability to an existing agent?

**A:** Follow these steps:
1. Add new tool to the agent
2. Update agent's capability list
3. Update agent registry
4. Test the new capability
5. Deploy the updated agent

Example:
```python
# 1. Add tool
class NewTool(BaseTool):
    name = "new_capability"
    # ... implementation

# 2. Add to agent
self.tools.append(NewTool())
self.capabilities.append("new_capability")
```

### Q: How do I debug when messages aren't flowing correctly?

**A:** Check these in order:
1. **Logs**: Look for errors in orchestrator and agent logs
2. **State**: Print state at each step to see where it changes
3. **Network**: Verify agents are reachable
4. **Format**: Ensure messages match expected format

### Q: What's the difference between sync and async functions?

**A:** 
- **Sync**: Blocks until complete, one thing at a time
- **Async**: Can pause and let other things run

```python
# Sync - blocks everything
def get_data():
    result = slow_database_query()  # Everything waits
    return result

# Async - doesn't block
async def get_data():
    result = await slow_database_query()  # Other code can run
    return result
```

### Q: How do I test agent interactions?

**A:** Use mocks to simulate agent responses:

```python
# Mock the agent
mock_agent = Mock()
mock_agent.process_task.return_value = {"data": "test"}

# Test orchestrator with mock
orchestrator = Orchestrator(agents={"test": mock_agent})
result = await orchestrator.process("test request")
assert result == expected
```

### Q: When should I create a new agent vs adding to existing?

**A:** Create a new agent when:
- Different domain (weather vs CRM)
- Different external service
- Need independent scaling
- Different team owns it

Add to existing when:
- Same domain knowledge
- Shares same external APIs
- Closely related functionality

### Q: How do I handle sensitive data?

**A:** Follow these practices:
1. Never log sensitive data
2. Use environment variables for credentials
3. Validate and sanitize all inputs
4. Encrypt data in transit and at rest

Example:
```python
# Bad
logger.info(f"User password: {password}")

# Good
logger.info("User authentication attempted")
```

### Q: What's the best way to learn this system?

**A:** Recommended learning path:
1. Run the system locally and try simple requests
2. Read through one agent completely (start with Salesforce)
3. Add a simple tool to an existing agent
4. Write tests for your tool
5. Try debugging a failed request
6. Build a simple new agent

### Q: How do I know if my code is "production ready"?

**A:** Check these criteria:
- ✓ Has error handling for all external calls
- ✓ Includes comprehensive tests
- ✓ Follows team coding standards
- ✓ Has proper logging (not too much, not too little)
- ✓ Handles edge cases gracefully
- ✓ Documentation explains "why" not just "what"
- ✓ Performance is acceptable under load
- ✓ Security vulnerabilities addressed

---

## Summary

This multi-agent system is designed to be:
- **Modular**: Each piece does one thing well
- **Scalable**: Can grow with your needs
- **Resilient**: Handles failures gracefully
- **Maintainable**: Easy to understand and modify

As a junior engineer, focus on:
1. Understanding the flow of data
2. Learning one component deeply before moving to others
3. Writing tests for everything you build
4. Asking questions when things aren't clear

Remember: Every senior engineer was once a junior. The key is to keep learning, stay curious, and don't be afraid to make mistakes (in development, not production!).

Happy coding! 🚀