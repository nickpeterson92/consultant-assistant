# 🧭 Codebase Exploration Guide

This guide will help you understand the multi-agent orchestrator system from the ground up, with hands-on experiments and tests at each level.

## 📚 Table of Contents
1. [System Overview](#system-overview)
2. [Core Concepts](#core-concepts)
3. [Exploration Path](#exploration-path)
4. [Testing & Experiments](#testing--experiments)
5. [Deep Dive Areas](#deep-dive-areas)

## 🏗️ System Overview

### Current Architecture (2025)
```
┌─────────────────────────────────────────┐
│         User Interface Layer            │
│      (orchestrator.py CLI)              │
├─────────────────────────────────────────┤
│       Orchestrator Agent Layer          │
│  (LangGraph + Modular Components)       │
│  ├─ Graph Builder                       │
│  ├─ Conversation Handler                │
│  ├─ LLM Handler                         │
│  ├─ Background Tasks                    │
│  └─ State Management                    │
├─────────────────────────────────────────┤
│        A2A Protocol Layer               │
│     (Agent Communication)               │
├─────────────────────────────────────────┤
│      Specialized Agents Layer           │
│   (Salesforce, Jira, ServiceNow)        │
├─────────────────────────────────────────┤
│       Unified Tool Layer                │
│  ├─ Salesforce Unified                  │
│  ├─ Jira Unified                        │
│  └─ ServiceNow Unified                  │
├─────────────────────────────────────────┤
│      Infrastructure Layer               │
│ (Storage, Logging, Config, Utils)       │
└─────────────────────────────────────────┘
```

## 🔑 Core Concepts

### 1. **LangGraph State Management**
- How conversation state flows through the system
- Message preservation and summarization
- Background operations

### 2. **A2A Protocol**
- JSON-RPC 2.0 based communication
- Agent discovery and health checks
- Task distribution

### 3. **Tool Abstraction**
- How tools are defined and registered
- Tool execution and error handling
- Result formatting

### 4. **Memory & Storage**
- Thread-based conversation persistence
- Structured data extraction
- SQLite async adapter

## 🛤️ Exploration Path

### Stage 1: Entry Points & Flow
Start here to understand how requests flow through the system.

```bash
# 1. Trace a simple request
echo "get account Genepoint" | python3 orchestrator.py

# Watch the logs in real-time
tail -f logs/orchestrator.log | jq '.'
```

**Key files to examine:**
- `orchestrator.py` - Entry point
- `src/orchestrator/main.py` - Core orchestrator logic (legacy)
- `src/orchestrator/graph_builder.py` - New modular graph construction
- `src/orchestrator/conversation_handler.py` - Message processing
- `src/orchestrator/llm_handler.py` - LLM interaction layer
- `src/utils/helpers.py` - UI helpers

### Stage 2: Modular State Management
Understand the new modular state system.

```python
# Test script: explore_state_system.py
import json
from src.orchestrator.state import OrchestratorState
from src.orchestrator.conversation_handler import ConversationHandler

# Explore the new state structure
handler = ConversationHandler()
initial_state = handler.create_initial_state()
print("Initial state structure:", json.dumps(initial_state, indent=2, default=str))

# Test state transformations
updated_state = handler.add_user_message(initial_state, "test message")
print("After adding message:", updated_state["messages"][-1])
```

**Key concepts:**
- `OrchestratorState` in `src/orchestrator/state.py`
- Modular conversation handling
- Separated state management from graph logic

### Stage 3: Agent Communication
Understand the A2A protocol in action.

```python
# Test script: test_a2a.py
import asyncio
from src.a2a import A2AClient, A2ATask

async def test_agent_communication():
    async with A2AClient() as client:
        # Check agent health
        card = await client.get_agent_card("http://localhost:8001/a2a")
        print(f"Agent: {card.name}")
        print(f"Capabilities: {card.capabilities}")
        
        # Send a task
        task = A2ATask(
            id="test-123",
            instruction="get account Genepoint",
            context={"user": "test"}
        )
        result = await client.process_task("http://localhost:8001/a2a", task)
        print(f"Result: {result}")

asyncio.run(test_agent_communication())
```

### Stage 4: Unified Tool System
Understand the new unified tool architecture.

```python
# Test script: test_unified_tools.py
from src.tools.salesforce_unified import SalesforceGet, SalesforceSearch

# Test unified GET tool
get_tool = SalesforceGet()
result = get_tool._execute(record_id="001bm00000SA8pSAAT")
print(f"Get result: {result}")

# Test unified SEARCH tool
search_tool = SalesforceSearch()
result = search_tool._execute(query="biotechnology", object_type="Account")
print(f"Search result: {result}")
```

### Stage 5: Memory & Storage
Explore the persistence layer.

```python
# Test script: explore_memory.py
import asyncio
from src.utils.storage import get_async_store_adapter

async def explore_storage():
    store = get_async_store_adapter()
    
    # List all namespaces
    all_data = await store.list_all()
    for namespace, items in all_data.items():
        print(f"\nNamespace: {namespace}")
        for key, value in items.items():
            print(f"  {key}: {len(str(value))} bytes")

asyncio.run(explore_storage())
```

## 🧪 Testing & Experiments

### Experiment 1: Request Routing
Test how the orchestrator decides which agent to use.

```bash
# These should route to Salesforce agent
echo "get all accounts" | python3 orchestrator.py
echo "create a new lead" | python3 orchestrator.py

# These should route to Jira agent  
echo "list my jira issues" | python3 orchestrator.py
echo "create a bug in project ABC" | python3 orchestrator.py

# Watch the routing decisions in logs
grep "CAPABILITY_QUERY" logs/system.log | tail -10 | jq '.'
```

### Experiment 2: Memory Extraction
See how structured data is extracted from conversations.

```bash
# Have a conversation that mentions specific entities
python3 orchestrator.py
# > get the genepoint account
# > update the phone to 555-1234
# > add a note about the meeting

# Check what was extracted
sqlite3 memory_store.db "SELECT * FROM store WHERE namespace='(''memory'', ''user-1'')'"
```

### Experiment 3: Error Handling
Test resilience patterns.

```bash
# Kill an agent while running
pkill -f "salesforce_agent"

# Try to use it
echo "get all accounts" | python3 orchestrator.py

# Watch circuit breaker in action
grep "CIRCUIT_BREAKER" logs/a2a_protocol.log | tail -10
```

### Experiment 4: Performance Profiling
Understand where time is spent.

```python
# Test script: profile_request.py
import time
import asyncio
from src.orchestrator.main import orchestrator_graph

async def profile_request():
    start = time.time()
    
    state = {
        "messages": [{"role": "user", "content": "get all accounts"},{"role": "assistant", "content": "get all accounts"},{"role": "tool", "content": "get all accounts"}],
        "summary": "No summary available",
        "memory": {},
        "events": []
    }
    
    # Time each step
    config = {"configurable": {"thread_id": "profile-test"}}
    
    async for event in orchestrator_graph.astream_events(state, config, version="v2"):
        print(f"{time.time() - start:.3f}s: {event['event']}: {event['name']}")

asyncio.run(profile_request())
```

## 🔍 Deep Dive Areas

### 1. Modular LangGraph Architecture
**Key files:**
- `src/orchestrator/graph_builder.py` - New modular graph construction
- `src/orchestrator/main.py` - Legacy orchestrator (being phased out)
- `src/orchestrator/state.py` - State type definitions
- `src/orchestrator/conversation_handler.py` - Message processing

**Experiments:**
```python
# Explore the new modular graph builder
from src.orchestrator.graph_builder import GraphBuilder

builder = GraphBuilder()
graph = builder.build_graph()
print("Graph nodes:", graph.get_graph().nodes())
print("Graph edges:", graph.get_graph().edges())

# Visualize the graph structure
print(graph.get_graph().draw_mermaid())
```

### 2. A2A Protocol Implementation
**Key files:**
- `src/a2a/protocol.py` - Core protocol
- `src/a2a/circuit_breaker.py` - Resilience

**Experiments:**
```bash
# Manual A2A request
curl -X POST http://localhost:8001/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "get_agent_card",
    "params": {},
    "id": 1
  }'
```

### 3. Unified Tool Architecture
**Key files:**
- `src/tools/salesforce_unified.py` - Unified Salesforce tools
- `src/tools/jira_unified.py` - Unified Jira tools
- `src/tools/servicenow_unified.py` - Unified ServiceNow tools
- `src/tools/salesforce_base.py` - Base tool classes
- `src/orchestrator/agent_caller_tools.py` - Agent communication tools

**New patterns to study:**
- Base class hierarchy (Read/Write/Analytics)
- Unified tool interfaces
- Automatic object type detection
- Query builder integration
- Cross-object search capabilities

### 4. Logging Architecture
**Key files:**
- `src/utils/logging/multi_file_logger.py`
- Log routing by component

**Experiments:**
```python
# Trace log flow
from src.utils.logging import get_logger

logger = get_logger("test_component")
logger.info("test_message", 
    component="test_component",
    operation="test_op",
    key1="value1"
)

# Check which file it went to
```

### 5. Configuration System
**Key files:**
- `system_config.json` - System settings
- `src/utils/config/` - Config loading

**Experiments:**
```python
# See all config values
from src.utils.config import get_system_config, get_llm_config
import json

config = get_system_config()
print(json.dumps(config.model_dump(), indent=2))
```

## 🎯 Advanced Explorations

### 1. Create a New Unified Tool
Best way to understand the system is to extend it.

```python
# Create src/tools/weather_unified.py
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from src.tools.salesforce_base import SalesforceReadTool

class WeatherGet(SalesforceReadTool):
    """Get weather information for a city."""
    name: str = "weather_get"
    description: str = "Get current weather for a city"
    
    class Input(BaseModel):
        city: str = Field(description="City name")
        units: Optional[str] = Field("metric", description="Temperature units")
    
    args_schema: type = Input
    
    def _execute(self, city: str, units: Optional[str] = "metric") -> Any:
        # Implementation here
        return {
            "city": city,
            "temperature": "22°C" if units == "metric" else "72°F",
            "condition": "Sunny"
        }
```

### 2. Extend an Existing Agent
```bash
# Add weather capability to an existing agent
# Edit src/agents/salesforce/main.py to include weather tools
# Update agent capabilities in agent_registry.json
```

### 3. Implement Custom Memory
Extend the memory system to track custom entities.

### 4. Build a New UI
Create a web interface that connects to the orchestrator via the A2A protocol.

## 📊 Monitoring & Debugging

### Log Analysis Commands
```bash
# Most common errors
jq -r 'select(.level=="ERROR") | .message' logs/errors.log | sort | uniq -c

# Request flow for a thread
THREAD_ID="orchestrator-xxxxx"
grep "$THREAD_ID" logs/*.log | sort -k1

# Performance metrics
jq -r 'select(.operation=="invoke_llm") | .duration_seconds' logs/orchestrator.log | awk '{sum+=$1} END {print "Avg LLM latency:", sum/NR}'

# Agent health over time
jq -r 'select(.message=="health_check_all_complete") | "\(.timestamp) \(.online_count)/\(.total_agents)"' logs/orchestrator.log
```

### SQLite Exploration
```sql
-- See all conversations
sqlite3 memory_store.db "SELECT key, length(value) as size FROM store WHERE key LIKE 'state_%' ORDER BY size DESC"

-- Extract a specific conversation
sqlite3 memory_store.db "SELECT value FROM store WHERE key='state_orchestrator-xxxxx'" | jq '.'
```

## 🚀 Next Steps

1. **Explore the unified tool system**: Compare old vs new tool implementations
2. **Test the modular orchestrator**: Understand the new component separation
3. **Implement a feature end-to-end**: Add a new unified tool to an existing agent
4. **Debug the new architecture**: Use logs to trace requests through modular components
5. **Optimize performance**: Profile the new modular system vs legacy
6. **Extend the system**: Add ServiceNow unified tools or new agent capabilities

## 📋 2025 Architecture Updates

### Key Changes to Explore:
- **Modular Orchestrator**: Split into separate handler classes
- **Unified Tools**: Consolidated tool interfaces with base classes
- **Enhanced Query Builders**: SOQL and GlideRecord query builders
- **Improved Error Handling**: Better circuit breaker and retry logic
- **Component Separation**: Clear boundaries between orchestrator components

Remember: The best way to understand is to break things and fix them!