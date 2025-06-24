# CLAUDE.md

Concise guidance for Claude Code when working with this multi-agent orchestrator system.

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
│   │   ├── main.py             # LangGraph orchestrator
│   │   ├── agent_caller_tools.py
│   │   └── agent_registry.py
│   ├── agents/salesforce/
│   │   └── main.py             # SF LangGraph agent
│   ├── a2a/
│   │   ├── protocol.py         # A2A implementation
│   │   └── circuit_breaker.py
│   ├── tools/
│   │   └── salesforce_tools.py # 15 CRUD tools
│   └── utils/
│       ├── config/             # Config management
│       ├── storage/            # Memory persistence
│       ├── logging/            # Structured logging
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

### SQLite Schema
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

## 🐛 Common Issues

### Connection Timeouts
- **Solution**: Check circuit breaker status and connection pool

### Memory Extraction Failures
- **Solution**: Verify imports in memory processing functions

## 📚 Key Architecture Decisions

1. **Loose Coupling**: Tools as interface contracts
2. **Resilience**: Circuit breaker + retry patterns
3. **Memory**: TrustCall + Pydantic validation
4. **A2A Protocol**: JSON-RPC 2.0 standard
5. **LangGraph**: State management with checkpointing
6. **Thread Persistence**: Full state storage
7. **BaseAgentTool**: DRY pattern for agents
8. **Constants**: Centralized in `constants.py`