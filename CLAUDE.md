# CLAUDE.md

UPDATE CLAUDE.md PERIODICALLY

## 📅 Current Year

The current year is 2025. Use this year along with 2024 for web searching.

## 🏗️ System Architecture

Multi-agent orchestrator using LangGraph with specialized agents communicating via A2A protocol.

```
USER INTERFACE (orchestrator.py)
        │
ORCHESTRATOR AGENT (LangGraph + State Management)
        │
A2A Protocol Layer (JSON-RPC 2.0)
        │
SALESFORCE AGENT + JIRA AGENT + SERVICE NOW AGENT (+ Future Agents)
```

## 🚀 Quick Start

```bash
# Complete system startup
python3 start_system.py

# Debug mode
python3 start_system.py

# Individual components (dev only)
python3 salesforce_agent.py --port 8001
python3 orchestrator.py
```

### Environment Setup (.env)
```bash
# Azure OpenAI (Required)
AZURE_OPENAI_ENDPOINT=<endpoint>
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=<deployment>
AZURE_OPENAI_API_VERSION=<version>
AZURE_OPENAI_API_KEY=<key>

# Salesforce (Required)
SFDC_USER=<username>
SFDC_PASS=<password>
SFDC_TOKEN=<token>

# Optional
DEBUG_MODE=true
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=4000
```

## 📁 Key File Structure

```
├── orchestrator.py              # Main entry
├── salesforce_agent.py          # SF agent entry
├── start_system.py              # System starter
├── src/
│   ├── orchestrator/
│   │   ├── main.py             # LangGraph orchestrator (1,086 lines)
│   │   ├── agent_caller_tools.py
│   │   └── agent_registry.py
│   ├── agents/salesforce/
│   │   └── main.py             # SF LangGraph agent
│   ├── a2a/
│   │   ├── protocol.py         # A2A protocol (for network calls)
│   │   └── circuit_breaker.py  # Resilience for A2A
│   ├── tools/
│   │   └── salesforce_tools.py # 15 CRUD tools (1,343 lines)
│   └── utils/
│       ├── config/             # Simplified config
│       ├── storage/            # Simple async SQLite adapter
│       ├── logging/            # Targeted logging system
│       ├── sys_msg.py          # System prompts
│       └── helpers.py
├── memory_store.db             # SQLite storage
└── logs/                       # JSON logs
```

## 🛠️ Core Tools

### Salesforce Tools (15 total)
- **Lead**: GetLeadTool, CreateLeadTool, UpdateLeadTool
- **Account**: GetAccountTool, CreateAccountTool, UpdateAccountTool
- **Opportunity**: GetOpportunityTool, CreateOpportunityTool, UpdateOpportunityTool
- **Contact**: GetContactTool, CreateContactTool, UpdateContactTool
- **Case**: GetCaseTool, CreateCaseTool, UpdateCaseTool
- **Task**: GetTaskTool, CreateTaskTool, UpdateTaskTool

### Orchestrator Tools
- **SalesforceAgentTool**: Routes CRM operations to SF agent
- **GenericAgentTool**: Future agent routing
- **AgentRegistryTool**: System health monitoring

## 💾 Memory Architecture

### SQLite Storage (Simplified)
- **AsyncStoreAdapter**: Simple thread pool executor wrapping SQLite
- **No circuit breakers**: SQLite handles concurrency internally
- **No connection pooling**: SQLite's built-in handling is sufficient
- **167 lines** vs previous 536 lines (69% reduction)

### Schema
```sql
CREATE TABLE store (
    namespace TEXT,    -- ("memory", user_id)
    key TEXT,          -- Object type
    value TEXT,        -- JSON Pydantic models
    PRIMARY KEY (namespace, key)
);
```

### Memory Models
- SimpleMemory (container)
- SimpleAccount, SimpleContact, SimpleOpportunity
- SimpleCase, SimpleTask, SimpleLead

### Thread Persistence
- Full state stored as `state_{thread_id}`
- Message serialization via `_serialize_messages()`

## 🔄 A2A Protocol

- **Standard**: JSON-RPC 2.0 over HTTP
- **Endpoints**: POST /a2a, GET /a2a/agent-card
- **Connection Pool**: 50 total, 20 per host
- **Circuit Breaker**: 5 failures threshold, 60s timeout
- **Retry**: 3 attempts with exponential backoff

## 🎯 Usage Examples

```bash
# Account operations
"get the Genepoint account"
"get all records for Genepoint"

# CRUD operations
"create new lead for John Smith at TechCorp"
"update opportunity ABC123 to Closed Won"

# System admin
"check agent status"
"list available agents"
```

## 🏆 Design Principles

### DRY (Don't Repeat Yourself)
- **Extract common functionality** into base classes (e.g., `BaseAgentTool`)
- **Centralize constants** in one location (`constants.py`)
- **Reuse existing utilities** before creating new ones
- **Share code** between similar components via inheritance or composition

### KISS (Keep It Simple, Stupid)
- **Prefer simple solutions** over clever ones
- **Avoid over-engineering** - start simple, iterate if needed
- **Write readable code** that junior developers can understand
- **Question complexity** - if it feels complicated, it probably is

### YAGNI (You Aren't Gonna Need It)
- **Don't add features** until they're actually needed
- **Remove speculative code** that isn't currently used
- **Avoid premature optimization** without evidence
- **Delete dead code** aggressively

### PEP8 Formatting and Commenting
- **Adhere** to it!

## 🚨 Common Gotchas (Read This First!)

### Two Types of Interrupts
**HumanInputTool Interrupts** (Model-initiated):
- Model calls HumanInputTool when it needs clarification
- Raises standard GraphInterrupt with question as value
- Handled by LangGraph's built-in interrupt mechanism
- Resume with: `Command(resume=user_response)`

**Escape Key Interrupts** (User-initiated):
- User presses Escape key in Textual UI during execution
- Sets `user_interrupted` flag in state via WebSocket
- plan_and_execute checks flag and raises GraphInterrupt with special marker
- Distinguishable by: `interrupt_value.get("type") == "user_escape"`
- Resume with modified plan after user edits

### Message Serialization 
**Problem**: LangChain messages break when saved directly to storage
```python
# ❌ WRONG - will crash on restore
state_to_save = {"messages": messages}

# ✅ RIGHT - always serialize first
from src.utils.message_serialization import serialize_messages
state_to_save = {"messages": serialize_messages(messages)}
```

### Thread State Keys
- States stored as `state_{thread_id}` in `("memory", user_id)` namespace
- Always check `global_memory_store` is not None before use

### Async/Sync Context Mixing
- Background tasks need `asyncio.run()` in thread contexts
- See `_run_background_summary()` for correct pattern

### Import Circular Dependencies
- Utils should NEVER import from orchestrator/agents
- Use lazy initialization (see `ensure_loggers_initialized()`)

### Memory Namespace Format
```python
# ❌ WRONG
namespace = "memory"

# ✅ RIGHT - always tuple
namespace = ("memory", user_id)
```

## 📚 Key Architecture Decisions

1. **Loose Coupling**: Tools as interface contracts
2. **Resilience**: Circuit breaker for network calls only (A2A)
3. **Memory**: Simple async SQLite adapter
4. **A2A Protocol**: JSON-RPC 2.0 standard
5. **LangGraph**: State management with checkpointing
6. **Thread Persistence**: Full state storage
7. **BaseAgentTool**: DRY pattern for agents
8. **Constants**: Centralized in `constants.py`
9. **YAGNI Applied**: Removed speculative features

## 📊 Multi-File Logging System

### Log Files by Component
```bash
logs/
├── orchestrator.log      # Orchestrator operations, LLM calls, user interactions, utility tools (web search)
├── salesforce.log        # Both SF agent AND tool operations in one place
├── jira.log              # Jira agent and tool operations
├── servicenow.log        # ServiceNow agent and tool operations
├── a2a_protocol.log      # Network calls, circuit breakers, retries
├── storage.log           # SQLite operations, memory persistence
├── system.log            # Startup/shutdown, config loads, health checks
└── errors.log            # ALL errors across components (for quick debugging)
```

### Quick Debugging Commands
```bash
# Watch Salesforce operations (agent + tools)
tail -f logs/salesforce.log | grep -E "(tool_call|tool_result|tool_error)"

# Track a request across all components
grep "task_id:abc123" logs/*.log | sort

# Monitor errors in real-time
tail -f logs/errors.log

# See A2A circuit breaker issues
tail -f logs/a2a_protocol.log | grep -E "(CIRCUIT_BREAKER|retry|timeout)"

# Check tool execution flow
tail -f logs/salesforce.log | jq -r 'select(.tool_name) | [.timestamp,.tool_name,.message] | @csv'

# Watch web search operations
tail -f logs/orchestrator.log | grep -E "(web_search|tavily)"

# Monitor web search errors specifically
tail -f logs/errors.log | grep -E "(web_search|TAVILY)"
```

### Component Mappings
- `component="orchestrator"` → orchestrator.log
- `component="utility"` → orchestrator.log (web search and other utility tools)
- `component="salesforce"` → salesforce.log (includes both agent & tools)
- `component="jira"` → jira.log
- `component="servicenow"` → servicenow.log
- `component="a2a"` → a2a_protocol.log
- `component="storage"` or `component="async_store_adapter_sync"` → storage.log
- `component="system"` or `component="config"` → system.log

### Key Log Messages to Watch
- **Tool issues**: Look for `tool_error` in salesforce.log
- **Agent offline**: Check `health_check_failed` in orchestrator.log
- **Memory errors**: Search `sqlite_error` in storage.log
- **Network issues**: Find `a2a_network_error` in a2a_protocol.log
- **Web search errors**: Look for `web_search_error` or `tavily_` in orchestrator.log
- **All critical errors**: Always check errors.log first!

## 🎯 Quick Task Reference

### Adding a New Constant
```python
# 1. Add to src/utils/config/constants.py
NEW_CONSTANT = "value"

# 2. Import and use
from src.utils.config import NEW_CONSTANT
```

### Debugging State Issues
```bash
# Check running components
curl http://localhost:8000/agent-status

# View thread state in SQLite
sqlite3 memory_store.db "SELECT * FROM store WHERE key LIKE 'state_%'"

# Monitor A2A issues
tail -f logs/a2a_protocol.log | grep CIRCUIT_BREAKER
```

### Common Patterns
- **BaseAgentTool**: All agents inherit for DRY context extraction
- **A2A Pool**: 50 total connections, 20 per host, supports 8+ concurrent calls
- **Memory Triggers**: 3 tool calls, 2 agent calls, or 180 seconds
- **Config Hierarchy**: system_config.json → env vars → code defaults

### Files That Matter Most
1. `orchestrator/main.py` - Core LangGraph logic
2. `agent_caller_tools.py` - How agents communicate
3. `constants.py` - All hardcoded values
4. `message_serialization.py` - Critical for state persistence

## 🧪 Direct Agent Testing Cheat Sheet

### Quick Agent Testing (Without Orchestrator)

#### Salesforce Agent Testing
```bash
# Start Salesforce agent directly
python3 salesforce_agent.py --port 8001 &

# Test endpoint availability
curl http://localhost:8001/a2a/agent-card

# Direct tool testing via A2A protocol
curl -X POST http://localhost:8001/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "process_task",
    "params": {
      "task_id": "test-001",
      "instruction": "YOUR_TEST_INSTRUCTION",
      "context": {}
    },
    "id": "test-001"
  }'
```

### 📋 Comprehensive Testing Principles

#### 1. **CRUD Coverage** - Test All Operations
```bash
# GET: Retrieve existing records
"instruction": "get account 001bm00000SA8pSAAT"

# SEARCH: Find records with criteria  
"instruction": "search for accounts in biotechnology industry"

# CREATE: Add new records (expect storage limit errors in dev)
"instruction": "create a new contact for Mike Davis at GenePoint with email mike@genepoint.com"

# UPDATE: Modify existing records
"instruction": "update the GenePoint account website to www.updated-site.com"

# ANALYTICS: Aggregate queries
"instruction": "show me opportunity analytics - total revenue by stage"

# SOSL: Cross-object search
"instruction": "find anything related to GenePoint across all Salesforce objects"
```

#### 2. **Error Handling Testing**
```bash
# Invalid ID format
"instruction": "get account invalid-id-123"

# Non-existent records  
"instruction": "get account 001000000000000AAA"

# Storage limits (expected in dev environments)
"instruction": "create a new lead for Test User at Test Company"

# Permission errors
"instruction": "delete account 001bm00000SA8pSAAT"
```

#### 3. **Edge Cases & Data Validation**
```bash
# Empty/minimal data
"instruction": "create a contact with just a name"

# Special characters
"instruction": "search for accounts with name containing apostrophe's"

# Large result sets
"instruction": "search for all opportunities"

# Complex queries
"instruction": "find all accounts created this year with revenue over 1 million"
```

#### 4. **Performance & Reliability Testing**
```bash
# Multiple concurrent requests (run in parallel)
for i in {1..5}; do
  curl -X POST http://localhost:8001/a2a \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"method\":\"process_task\",\"params\":{\"task_id\":\"test-$i\",\"instruction\":\"get account 001bm00000SA8pSAAT\",\"context\":{}},\"id\":\"test-$i\"}" &
done
wait
```

#### 5. **Logging & Debugging Verification**
```bash
# Monitor tool calls and results
tail -f logs/salesforce.log | grep -E "(tool_call|tool_result|tool_error)"

# Check SOQL query generation
tail -f logs/salesforce.log | grep "soql_query"

# Watch for connection issues
tail -f logs/salesforce.log | grep "salesforce_connection"
```

### 🎯 Testing Completion Checklist

**✅ Core Functionality**
- [ ] GET: Retrieve records by ID
- [ ] SEARCH: Query with filters and natural language
- [ ] CREATE: Add new records (handle storage limits gracefully)
- [ ] UPDATE: Modify existing records  
- [ ] ANALYTICS: Aggregate functions and grouping
- [ ] SOSL: Cross-object search

**✅ Error Scenarios**
- [ ] Invalid IDs return proper error messages
- [ ] Non-existent records handled gracefully
- [ ] Storage limit errors reported clearly
- [ ] Network timeouts handled appropriately

**✅ Edge Cases**
- [ ] Empty queries return appropriate responses
- [ ] Large result sets paginated or limited properly
- [ ] Special characters escaped correctly
- [ ] Complex queries parsed accurately

**✅ Technical Validation**
- [ ] All queries use SOQLQueryBuilder (no raw `SELECT *`)
- [ ] Proper JSON-RPC 2.0 response format
- [ ] Consistent error handling across tools
- [ ] Logging includes all required fields

### 🔧 Quick Fixes & Common Issues

**Agent Won't Start**: Check port availability
```bash
lsof -i :8001  # Check if port is in use
pkill -f "salesforce_agent"  # Kill existing processes
```

**Empty Instructions**: Verify JSON formatting
```bash
echo '{"jsonrpc":"2.0","method":"process_task","params":{"task_id":"test","instruction":"test message","context":{}},"id":"test"}' | python -m json.tool
```

**SELECT * Errors**: Tools should use REST API for record retrieval
- Create/Update tools use `sobject.get(id)` not SOQL queries
- Search tools use SOQLQueryBuilder with specific fields

**Storage Limits**: Expected in dev environments
- CREATE operations will fail with `STORAGE_LIMIT_EXCEEDED`
- This is normal and validates error handling