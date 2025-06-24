# CLAUDE.md

Essential guidance for Claude Code when working with this multi-agent orchestrator system. No fluff, just what you need to know.

## 🏗️ System Architecture

Multi-agent orchestrator using LangGraph with specialized agents communicating via A2A protocol.

```
USER INTERFACE (orchestrator.py)
        │
ORCHESTRATOR AGENT (LangGraph + State Management)
        │
A2A Protocol Layer (JSON-RPC 2.0)
        │
SALESFORCE AGENT (+ Future Agents)
```

## 🚀 Quick Start

```bash
# Complete system startup
python3 start_system.py

# Debug mode
python3 start_system.py -d

# Individual components (dev only)
python3 salesforce_agent.py -d --port 8001
python3 orchestrator.py -d
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

## 🚨 Common Gotchas (Read This First!)

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

## 📊 Code Metrics

### Infrastructure to Business Logic Ratio: 0.72:1
- **Business Logic**: 4,183 lines (58.2%)
- **Infrastructure**: 3,009 lines (41.8%)
- **Improvement**: 58.9% reduction from previous 1.75:1 ratio

### Simplified Components
- **AsyncStoreAdapter**: 536 → 167 lines (69% reduction)
- **SecurityConfig**: Removed unused rate limiting and file restrictions
- **Total Removed**: ~377 lines of unnecessary abstractions

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