# Multi-Agent Architecture

## Overview

Multi-agent orchestrator system using LangGraph for stateful conversation management and A2A protocol for inter-agent communication.

### Core Components

- **Orchestrator**: Central coordinator using LangGraph state machine
- **Specialized Agents**: Independent services for specific domains (Salesforce, Jira, ServiceNow)
- **A2A Protocol**: JSON-RPC 2.0 communication layer
- **Memory System**: SQLite-based persistence with conversation state
- **Service Discovery**: Dynamic agent registration and capability routing

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                              │
│                       (orchestrator.py CLI)                         │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ User Request
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR AGENT                             │
│                                                                     │
│  ┌────────────────┐  ┌──────────────┐  ┌────────────────────────┐   │
│  │  LangGraph     │  │    Agent     │  │   Conversation         │   │
│  │  State Machine │  │   Registry   │  │   Management           │   │
│  └────────────────┘  └──────────────┘  └────────────────────────┘   │
│                                                                     │
│  ┌────────────────┐  ┌──────────────┐  ┌────────────────────────┐   │
│  │    Memory      │  │   Service    │  │     Background         │   │
│  │  Management    │  │  Discovery   │  │     Processing         │   │
│  └────────────────┘  └──────────────┘  └────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
                        ┌───────────────┐
                        │ A2A Protocol  │
                        │ (JSON-RPC 2.0)│
                        └───────┬───────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
┌───────▼────────┐     ┌────────▼───────┐      ┌────────▼───────┐
│   Salesforce   │     │      Jira      │      │  ServiceNow    │
│     Agent      │     │     Agent      │      │    Agent       │
│  6 Unified     │     │  6 Unified     │      │  15 ITSM       │
│  Tools         │     │  Tools         │      │  Tools         │
└────────────────┘     └────────────────┘      └────────────────┘
```

### Request Flow

```
User Request → Orchestrator → Agent Selection → Task Creation
     │              │              │              │
     ▼              ▼              ▼              ▼
"Get contacts"  Parse Intent  Check Registry  Create A2A Task
     │              │              │              │
     ▼              ▼              ▼              ▼
A2A Protocol → Agent Process → Response Return → Memory Update
     │              │              │              │
     ▼              ▼              ▼              ▼
JSON-RPC Call   Query External   Format Results  Update State
```

## Core Components

### Agents
Independent programs with specific capabilities:
```python
class Agent:
    def __init__(self):
        self.name = "SalesforceAgent"
        self.capabilities = ["crm_operations", "contact_management"]
        self.tools = [GetContactTool(), CreateLeadTool()]
    
    async def process_task(self, task):
        # Execute business logic using tools
        return results
```

### Orchestrator
Central coordinator that:
- Parses natural language requests
- Routes to appropriate agents
- Manages conversation state
- Formats responses

### A2A Protocol
JSON-RPC 2.0 communication standard:
```json
{
    "jsonrpc": "2.0",
    "method": "process_task",
    "params": {
        "task": {
            "instruction": "Get contacts for Acme Corp",
            "context": {"user_id": "user123"}
        }
    },
    "id": 1
}
```

### State Management
LangGraph-based state persistence:
```python
state = {
    "messages": [conversation_history],
    "memory": {"accounts": [], "contacts": []},
    "user_id": "user123"
}
```

### LangGraph Workflow
```python
graph = StateGraph(State)
graph.add_node("understand_request", understand_node)
graph.add_node("call_agent", agent_node)
graph.add_node("format_response", response_node)
graph.add_edge("understand_request", "call_agent")
app = graph.compile()
```

## Implementation Examples

### Request Processing Flow
```python
# 1. User input
user_message = "Show me all opportunities for Acme Corp"

# 2. Intent recognition
intent = await llm.analyze(user_message)
# {"action": "retrieve", "entity": "opportunities", "filter": {"account": "Acme Corp"}}

# 3. Agent selection
agent = registry.find_agent_for_capability("opportunity_management")

# 4. Task creation and A2A call
task = A2ATask(instruction="Get opportunities for Acme Corp", context={"user_id": "123"})
response = await a2a_client.call_agent(agent_url, task)

# 5. Agent processing
opportunities = await salesforce_client.query("SELECT Id, Name, Amount FROM Opportunity WHERE Account.Name = 'Acme Corp'")

# 6. Response formatting and memory update
formatted_response = format_opportunities(opportunities)
await memory_store.save(user_id, state["memory"])
```

### Adding a New Tool

```python
# 1. Create tool class
class SearchLeadsByIndustryTool(BaseTool):
    name = "search_leads_by_industry"
    description = "Search for leads in a specific industry"
    
    def _run(self, industry: str) -> List[Dict]:
        escaped_industry = industry.replace("'", "\\'")
        query = f"SELECT Id, Name, Company FROM Lead WHERE Industry = '{escaped_industry}'"
        results = sf_client.query(query)
        return [format_lead(record) for record in results['records']]

# 2. Add to agent
tools.append(SearchLeadsByIndustryTool())

# 3. Update capabilities
capabilities.append("lead_search_by_industry")

# 4. Test
def test_search_leads_by_industry():
    tool = SearchLeadsByIndustryTool()
    results = tool.run("Technology")
    assert isinstance(results, list)
```

### Debugging Agent Issues

```bash
# Check logs
tail -f logs/orchestrator.log | grep ERROR
tail -f logs/salesforce_agent.log
tail -f logs/a2a_protocol.log

# Check agent health
curl http://localhost:8001/health

# Manual task test
curl -X POST http://localhost:8001/a2a \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"process_task","params":{"task":{"instruction":"test"}},"id":1}'

# Check circuit breaker status
circuit_status = a2a_client.get_circuit_breaker_status("salesforce_agent")
```

## Best Practices

### System Startup
```bash
# Use system starter for proper order
python3 start_system.py

# Or start agents before orchestrator
python3 salesforce_agent.py --port 8001 &
python3 orchestrator.py
```

### Error Handling
```python
# Handle agent failures gracefully
try:
    result = await call_agent(agent_url, task)
    return result.get('data', fallback_response())
except AgentCallError as e:
    logger.error(f"Agent call failed: {e}")
    return error_response("Service temporarily unavailable")
```

### State Management
```python
# Prevent infinite loops
def update_state(state):
    state["counter"] += 1
    if state["counter"] >= MAX_ITERATIONS:
        return state
    return continue_processing(state) if needs_processing(state) else state
```

### Async Operations
```python
# Don't block the event loop
async def process_task(task):
    await asyncio.sleep(10)  # Non-blocking
    result = await slow_async_operation()
    return result
```

### Input Validation
```python
# Always validate and escape
from src.utils.input_validation import sanitize_soql_string
escaped_input = sanitize_soql_string(user_input)
query = f"SELECT * FROM Account WHERE Name = '{escaped_input}'"
```

### Memory Management
```python
# Implement memory limits
MAX_MESSAGES = 100
if len(state["messages"]) > MAX_MESSAGES:
    state["summary"] = summarize_old_messages(state["messages"][:-50])
    state["messages"] = state["messages"][-50:]
```

## Development Examples

### Health Check Implementation
```python
class BaseAgent:
    async def health_handler(self, request):
        return web.json_response({
            "status": "healthy",
            "agent": self.name,
            "uptime_seconds": time.time() - self.start_time,
            "requests_processed": self.request_count
        })
```

### Retry Logic with Exponential Backoff
```python
async def retry_with_backoff(func, max_attempts=3, base_delay=1.0):
    for attempt in range(max_attempts):
        try:
            return await func()
        except Exception as e:
            if attempt >= max_attempts - 1:
                raise e
            delay = min(base_delay * (2 ** attempt), 30.0)
            await asyncio.sleep(delay * (0.5 + random.random()))
```

### Custom Memory Store
```python
class FileMemoryStore:
    async def save(self, user_id: str, key: str, value: Any):
        file_path = f"{self.base_path}/{user_id}/{key}.json"
        data = {"value": value, "timestamp": datetime.now().isoformat()}
        async with aiofiles.open(file_path, 'w') as f:
            await f.write(json.dumps(data))
    
    async def load(self, user_id: str, key: str):
        file_path = f"{self.base_path}/{user_id}/{key}.json"
        if os.path.exists(file_path):
            async with aiofiles.open(file_path, 'r') as f:
                data = json.loads(await f.read())
                return data["value"]
        return None
```

### Rate Limiter
```python
class RateLimiter:
    def __init__(self, rate=10, per=60.0):
        self.rate = rate
        self.per = per
        self.buckets = defaultdict(lambda: {'tokens': rate, 'last_update': time.time()})
    
    async def check_rate_limit(self, key: str) -> bool:
        bucket = self.buckets[key]
        now = time.time()
        time_passed = now - bucket['last_update']
        bucket['tokens'] = min(self.rate, bucket['tokens'] + (time_passed * self.rate / self.per))
        bucket['last_update'] = now
        
        if bucket['tokens'] >= 1:
            bucket['tokens'] -= 1
            return True
        return False
```

## Architecture Components

### File Structure
```
orchestrator/
├── main.py                 # LangGraph workflow definition
├── agent_caller_tools.py   # Agent communication
├── agent_registry.py       # Service discovery
└── state.py               # State definitions

agents/
├── salesforce/main.py     # Salesforce agent
├── jira/main.py          # Jira agent
└── servicenow/main.py    # ServiceNow agent

tools/
├── salesforce_unified.py  # 6 unified CRM tools
├── jira_unified.py        # 6 unified issue tools
└── servicenow_tools.py    # 15 specialized ITSM tools
```

### Data Flow
```python
# LangGraph workflow
async def orchestrator_workflow(state):
    state = await understand_node(state)     # Parse request
    state = await planning_node(state)       # Select agent
    state = await execution_node(state)      # Execute via A2A
    state = await response_node(state)       # Format response
    return state

# Agent processing
async def agent_process_task(task):
    validated = validate_task(task)
    result = await execute_business_logic(validated)
    return A2AResult(artifacts=[format_result(result)])
```

### Concurrency Model
```python
# Parallel task execution with semaphore
async def execute_parallel_tasks(tasks):
    semaphore = asyncio.Semaphore(10)  # Max 10 concurrent
    
    async def bounded_task(task):
        async with semaphore:
            return await execute_task(task)
    
    results = await asyncio.gather(*[bounded_task(task) for task in tasks], return_exceptions=True)
    return [handle_result(task, result) for task, result in zip(tasks, results)]
```

### Memory Architecture
```python
class MemoryManager:
    def __init__(self):
        self.short_term = {}  # Current conversation
        self.long_term = {}   # Persistent storage
    
    async def update_memory(self, state):
        # Update short-term (last 10 messages)
        self.short_term[state["user_id"]] = {"messages": state["messages"][-10:]}
        
        # Extract entities to long-term
        extracted = await extract_entities(state["messages"])
        await self.persist_to_long_term(state["user_id"], extracted)
```

## Development Setup

### Environment Setup
```bash
# Clone and setup
git clone https://github.com/your-org/multi-agent-orchestrator.git
cd multi-agent-orchestrator
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with credentials

# Run tests
pytest
pytest --cov=src --cov-report=html
```

### Creating a New Agent
```python
# 1. Create agent structure
class WeatherAgent:
    def __init__(self, port=8002):
        self.name = "weather_agent"
        self.tools = [GetWeatherTool(), GetForecastTool()]
    
    async def process_task(self, task: A2ATask) -> A2AResult:
        if "weather" in task.instruction:
            location = self.extract_location(task.instruction)
            weather = self.tools[0].run(location)
            return A2AResult(artifacts=[{"type": "weather_data", "data": weather}])
        return A2AResult(error="Cannot handle request")
    
    def get_agent_card(self) -> AgentCard:
        return AgentCard(
            name=self.name,
            capabilities=["current_weather", "weather_forecast"],
            endpoints={"a2a": f"http://localhost:{self.port}/a2a"}
        )

# 2. Register in agent_registry.json
{
    "agents": [{
        "name": "weather_agent",
        "endpoint": "http://localhost:8002",
        "capabilities": ["current_weather", "weather_forecast"]
    }]
}
```

### Development Best Practices
- **Code Organization**: Separate agents, orchestrator, utils, models
- **Error Handling**: Specific exception handling with retries
- **Testing**: Comprehensive test coverage with mocks
- **Documentation**: Clear docstrings with Args/Returns/Examples

## Testing & Debugging

### Testing Patterns
```python
# Async testing
@pytest.mark.asyncio
async def test_async_agent_call():
    mock_client = AsyncMock()
    mock_client.call_agent.return_value = {"result": "success", "data": {"count": 5}}
    
    with patch('src.orchestrator.client', mock_client):
        result = await orchestrator.delegate_to_agent("salesforce_agent", "get accounts")
    
    assert result["data"]["count"] == 5

# State testing
def test_state_update_preserves_history():
    initial_state = {"messages": [HumanMessage("Hello")], "user_id": "test123"}
    new_state = update_state(initial_state, new_message=HumanMessage("Get accounts"))
    assert len(new_state["messages"]) == 2

# Integration testing
@pytest.mark.integration
async def test_orchestrator_agent_integration():
    test_agent = TestSalesforceAgent(port=9001)
    orchestrator = Orchestrator(agent_registry={"salesforce": "http://localhost:9001"})
    result = await orchestrator.process_request("Get all accounts")
    assert "accounts" in result
```

### Debugging Tools
```python
# Debug tracing
@debug_trace
async def complex_operation(data):
    return await process_data(data)  # Automatically traced

# State inspection
StateInspector.print_state_summary(state)
issues = StateInspector.validate_state_transitions(old_state, new_state)

# Performance profiling
async with profile_async("operation_name"):
    result = await complex_calculation()
```

### Common Debugging Scenarios
```bash
# Agent connectivity
curl http://localhost:8001/health
curl -X POST http://localhost:8001/a2a -d '{"jsonrpc":"2.0","method":"process_task","params":{"task":{"instruction":"test"}},"id":1}'

# Memory integrity
python check_memory_integrity.py ./memory_store.db

# Circuit breaker status
circuit_status = a2a_client.get_circuit_breaker_status("salesforce_agent")
```

## Performance Metrics

### Code Metrics (Post-Simplification)
- **Infrastructure to Business Logic Ratio**: 0.72:1 (58.9% improvement)
- **Business Logic**: 4,183 lines (58.2%)
- **Infrastructure**: 3,009 lines (41.8%)

### Key Simplifications
- **AsyncStoreAdapter**: 536 → 167 lines (69% reduction)
- **SecurityConfig**: 17 → 9 lines (47% reduction)
- **Total Removed**: ~377 lines of unnecessary abstractions

### Performance Targets
- **Simple queries**: < 500ms
- **Complex operations**: < 2s  
- **Memory operations**: < 50ms (SQLite)
- **A2A overhead**: < 100ms

### Concurrency Limits
- **Thread pool**: 4 workers
- **A2A connections**: 50 total, 20 per host
- **Concurrent tool calls**: Up to 8 per agent

### Memory Usage
- **Base footprint**: ~100MB
- **Per conversation**: ~5MB
- **SQLite cache**: < 50MB

## Architecture Principles

- **YAGNI**: Removed speculative features, focused on actual requirements
- **KISS**: Simple AsyncStoreAdapter, direct SQLite usage, clear separation
- **DRY**: BaseAgentTool for common functionality, centralized constants

## Summary

Multi-agent system with:
- **Orchestrator**: LangGraph state machine for conversation management
- **Specialized Agents**: Salesforce (6 tools), Jira (6 tools), ServiceNow (15 tools)
- **A2A Protocol**: JSON-RPC 2.0 communication with circuit breakers
- **Memory System**: SQLite persistence with conversation state
- **Service Discovery**: Dynamic agent registration and capability routing

Design focuses on modularity, scalability, resilience, and maintainability.