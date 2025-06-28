# CLAUDE.md

You (Claude) should check this CLAUDE.md file periodically and update it with new, helpful information you learn while building features, debugging and troubleshooting.

## 📅 Current Year

The current year is 2025. Use this year along with 2024 for web searching.

## ASSUMPTIONS

Are often wrong! If you have an assumption - challenge and try to confirm it before hacking in changes!

## 🏗️ System Architecture

Multi-agent orchestrator using LangGraph with specialized agents communicating via A2A protocol.

```
USER INTERFACE (orchestrator.py)
        │
ORCHESTRATOR AGENT (LangGraph + State Management)
        │
A2A Protocol Layer (JSON-RPC 2.0)
        │
SALESFORCE AGENT + JIRA AGENT + SERVICE NOW AGENT + WORKFLOW AGENT
```

## 🚀 Quick Start

```bash
# Complete system startup
python3 start_system.py

# Debug mode
python3 start_system.py

# Individual components (dev only)
python3 salesforce_agent.py --port 8001
python3 jira_agent.py --port 8002
python3 servicenow_agent.py --port 8003
python3 workflow_agent.py --port 8004
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
LLM_RECURSION_LIMIT=15
```

## 📁 Key File Structure

```
├── orchestrator.py              # Main entry
├── salesforce_agent.py          # SF agent entry
├── jira_agent.py               # Jira agent entry
├── servicenow_agent.py         # ServiceNow agent entry
├── workflow_agent.py           # Workflow agent entry
├── start_system.py              # System starter
├── src/
│   ├── orchestrator/
│   │   ├── main.py             # CLI interface & main loop
│   │   ├── graph_builder.py    # LangGraph orchestration
│   │   ├── conversation_handler.py # Message processing
│   │   ├── agent_caller_tools.py   # Agent communication
│   │   └── agent_registry.py   # Agent discovery
│   ├── agents/
│   │   ├── salesforce/
│   │   │   └── main.py         # SF LangGraph agent
│   │   ├── jira/
│   │   │   └── main.py         # Jira LangGraph agent
│   │   ├── servicenow/
│   │   │   └── main.py         # ServiceNow LangGraph agent
│   │   └── workflow/
│   │       ├── main.py         # Workflow LangGraph agent
│   │       ├── engine.py       # Workflow execution engine
│   │       ├── models.py       # Workflow data models
│   │       └── templates.py    # Pre-built workflow templates
│   ├── a2a/
│   │   ├── protocol.py         # A2A protocol (for network calls)
│   │   └── circuit_breaker.py  # Resilience for A2A
│   ├── tools/
│   │   ├── salesforce/
│   │   │   └── unified.py      # 6 unified Salesforce tools
│   │   ├── jira/
│   │   │   └── unified.py      # 6 unified Jira tools
│   │   ├── servicenow/
│   │   │   └── unified.py      # 6 unified ServiceNow tools
│   │   └── workflow_tools.py    # 3 workflow orchestration tools
│   └── utils/
│       ├── config/             # Configuration management
│       │   ├── config.py       # Main config system
│       │   └── constants.py    # Centralized constants
│       ├── storage/            # Simple async SQLite adapter
│       ├── logging/            # Multi-file logging system
│       │   └── multi_file_logger.py
│       ├── agents/             # Agent-specific utilities
│       │   └── prompts.py      # System prompts (split from sys_msg.py)
│       ├── ui/                 # UI utilities (split from ux.py)
│       │   ├── banners.py      # Banner display
│       │   ├── typing_effect.py # Animated typing
│       │   └── formatting.py   # Console formatting
│       ├── platform/           # Platform-specific utilities
│       │   ├── query/          # Query builders
│       │   │   └── base_builder.py  # Base query builder
│       │   ├── salesforce/
│       │   │   └── soql_builder.py  # SOQL query builder
│       │   └── servicenow/
│       │       └── glide_builder.py # Glide query builder
│       └── helpers.py          # General utilities
├── memory_store.db             # SQLite storage
└── logs/                       # JSON logs by component
```

## 🛠️ Core Tools

### Salesforce Tools (6 unified)
- **GetSalesforceTool**: Get records by ID or search criteria
- **CreateSalesforceTool**: Create new records (Lead, Account, Opportunity, etc.)
- **UpdateSalesforceTool**: Update existing records
- **SalesforceSearchTool**: SOQL/SOSL search across all objects
- **SalesforceAnalyticsTool**: Pipeline analytics and aggregations
- **SalesforceCollaborationTool**: Activity and note management

### Jira Tools (6 unified)
- **GetJiraTool**: Get issues by key or ID
- **CreateJiraTool**: Create new issues (bug, story, task, epic)
- **UpdateJiraTool**: Update issue fields and transitions
- **JiraSearchTool**: JQL search with natural language support
- **JiraAnalyticsTool**: Sprint metrics and team analytics
- **JiraCollaborationTool**: Comments and collaboration features

### ServiceNow Tools (6 unified)
- **GetServiceNowTool**: Get records by sys_id or number
- **CreateServiceNowTool**: Create incidents, changes, problems
- **UpdateServiceNowTool**: Update ITSM records
- **ServiceNowSearchTool**: GlideQuery search across tables
- **ServiceNowAnalyticsTool**: ITSM metrics and reporting
- **ServiceNowWorkflowTool**: Process automation and approvals

### Workflow Tools (3 orchestration)
- **WorkflowExecutionTool**: Smart workflow routing and execution
- **WorkflowStatusTool**: Monitor running workflow status
- **WorkflowListTool**: Discover available workflow templates

### Orchestrator Tools
- **SalesforceAgentTool**: Routes CRM operations to SF agent
- **JiraAgentTool**: Routes issue management to Jira agent
- **ServiceNowAgentTool**: Routes ITSM operations to ServiceNow agent
- **WorkflowAgentTool**: Routes complex workflows to workflow agent
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

## 🔄 Workflow Agent

### Available Workflows (5 templates)
- **deal_risk_assessment**: Find at-risk opportunities + blockers across systems
- **incident_to_resolution**: End-to-end incident management with system linking  
- **customer_360_report**: Comprehensive customer data aggregation
- **weekly_account_health_check**: Proactive account monitoring
- **new_customer_onboarding**: Automated customer setup process

### Key Features
- **Multi-step execution**: ACTION, CONDITION, PARALLEL, WAIT, FOR_EACH steps
- **Cross-system coordination**: Salesforce + Jira + ServiceNow integration
- **State persistence**: Resume workflows after interruption
- **LLM-powered reporting**: Business intelligence and executive summaries

### Quick Start
```bash
# Run workflows via natural language
"check for at-risk deals"
"start customer onboarding for ACME Corp"
"generate customer report for GenePoint"
"run weekly account health check"
```

## 🎯 Usage Examples

```bash
# Account operations
"get the Genepoint account"
"get all records for Genepoint"

# CRUD operations
"create new lead for John Smith at TechCorp"
"update opportunity ABC123 to Closed Won"

# Workflow operations
"check for at-risk deals"
"start customer onboarding"

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
10. **Global Recursion Limit**: 15 iterations max for all agents (configurable)
11. **Modular Code Organization**: Split large files (sys_msg.py, ux.py) into focused modules
12. **Query Builder Pattern**: Base query builder with platform-specific implementations

## 📊 Multi-File Logging System

### Log Files by Component
```bash
logs/
├── orchestrator.log      # Orchestrator operations, LLM calls, user interactions, utility tools (web search)
├── salesforce.log        # Both SF agent AND tool operations in one place
├── jira.log              # Jira agent and tool operations
├── servicenow.log        # ServiceNow agent and tool operations
├── workflow.log          # Workflow agent execution, step tracking, business reports
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

# Monitor workflow execution
tail -f logs/workflow.log | grep -E "(workflow_started|workflow_completed|workflow_step)"

# Monitor web search errors specifically
tail -f logs/errors.log | grep -E "(web_search|TAVILY)"
```

### Component Mappings
- `component="orchestrator"` → orchestrator.log
- `component="utility"` → orchestrator.log (web search and other utility tools)
- `component="salesforce"` → salesforce.log (includes both agent & tools)
- `component="jira"` → jira.log
- `component="servicenow"` → servicenow.log
- `component="workflow"` → workflow.log
- `component="a2a"` → a2a_protocol.log
- `component="storage"` or `component="async_store_adapter_sync"` → storage.log
- `component="system"` or `component="config"` → system.log

### Key Log Messages to Watch
- **Tool issues**: Look for `tool_error` in salesforce.log
- **Agent offline**: Check `health_check_failed` in orchestrator.log
- **Memory errors**: Search `sqlite_error` in storage.log
- **Workflow issues**: Check `workflow_error` or `workflow_step_failed` in workflow.log
- **Network issues**: Find `a2a_network_error` in a2a_protocol.log
- **Web search errors**: Look for `web_search_error` or `tavily_` in orchestrator.log
- **All critical errors**: Always check errors.log first!

## 🚨 Common Gotchas & Troubleshooting

### Salesforce Name Searches
**Problem**: Exact match queries fail when names don't match perfectly
- Example: Searching for "Express Logistics" misses "Express Logistics SLA"
- Agent often uses `Name = 'value'` and `limit=1`, missing partial matches

**Solution** (Implemented):
- Salesforce agent now uses LIKE queries with wildcards by default
- Default limit increased from 1 to 10 for better match handling
- When multiple matches found, agent lists all options for clarification
- Workflow includes human-in-the-loop step for disambiguation

**Pattern**:
```
User: "Find Express Logistics opportunity"
Agent: Name LIKE '%Express Logistics%' with limit=10
Result: Shows all matches (Express Logistics SLA, Express Logistics Inc, etc.)
```

### ServiceNow API Issues
**Problem**: `'str' object has no attribute 'get'` in analytics tools
- **Root Cause**: ServiceNow Aggregate API returns `{"result": [...]}` where result is an array
- **Fix**: Use `data.get('result', [])` then iterate through list items with `groupby_fields` array
- **Location**: `src/tools/servicenow/unified.py:542`

### A2A Parameter Handling
**Problem**: ServiceNow agent expecting `"task"` wrapper but A2A sends parameters directly
- **Root Cause**: Inconsistent parameter handling between agents
- **Fix**: Add fallback: `task_data = params.get("task", params)`
- **Location**: `src/agents/servicenow/main.py:137`

### Environment Variable Escaping
**Problem**: Passwords with special characters (`!$@#`) causing authentication failures
- **Root Cause**: Python environment variable handling needs proper escaping
- **Fix**: Use `os.environ.get()` directly, avoid shell interpretation
- **Test**: Verify with curl command line vs Python requests

### Workflow State Persistence
**Problem**: LangChain messages break when saved directly to storage
- **Root Cause**: Message objects not JSON serializable
- **Fix**: Always use `serialize_messages()` before storage
- **Pattern**: `state_to_save = {"messages": serialize_messages(messages)}`

### Memory Namespace Format
**Problem**: Memory operations failing with string namespace
- **Root Cause**: Memory expects tuple namespace format
- **Fix**: Use `("memory", user_id)` not `"memory"`
- **Pattern**: Always use tuple format for namespaces

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