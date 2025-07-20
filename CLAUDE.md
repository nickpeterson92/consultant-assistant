# CLAUDE.md

You (Claude) should check this CLAUDE.md file periodically and update it with new, helpful information you learn while building features, debugging and troubleshooting.

## 📅 Current Year

The current year is 2025. Use this year along with 2024 for web searching.

## ASSUMPTIONS

Are often wrong! If you have an assumption - challenge and try to confirm it before hacking in changes!

## 🏗️ System Architecture

Multi-agent orchestrator using LangGraph with specialized agents communicating via A2A protocol.

```
CLI CLIENT (orchestrator_cli_textual.py)
        │
A2A PROTOCOL (JSON-RPC 2.0)
        │  
ORCHESTRATOR SERVER (Pure Plan-and-Execute LangGraph)
        │
A2A Protocol Layer (JSON-RPC 2.0)
        │
SALESFORCE AGENT + JIRA AGENT + SERVICE NOW AGENT
```

## 🎯 State Management Changes (January 2025)

### Simplified Trigger System
We've replaced the complex event system with a simple counter-based approach:

**Old System (REMOVED):**
- Event objects with timestamps, types, details
- EventAnalyzer for complex logic
- 250+ lines of code, 25-50KB state storage

**New System (SIMPLE):**
- Simple counters: `tool_calls_since_memory`, `agent_calls_since_memory`
- SimpleTriggerState: just timestamp + message_count
- ~79 lines total, <1KB state storage
- Functions: `should_trigger_summary()`, `should_trigger_memory_update()`

### Why We Changed
- Events were storing 50 events × 500-1000 chars each = 25-50KB
- Complex event analysis wasn't being used
- Simple counters achieve the same goal with 98% less code

### How Triggers Work Now
```python
# Summary triggers when:
- 5+ user messages since last summary
- OR 300+ seconds since last summary (if messages exist)

# Memory triggers when:
- 3+ tool calls since last memory update
- OR 2+ agent calls since last memory update
```

## 🚀 Quick Start

```bash
# Complete system startup (A2A mode - the only mode)
python3 start_system.py              # Terminal 1: Start all agents + orchestrator A2A server
python3 orchestrator_cli_textual.py  # Terminal 2: Textual TUI interface

# Individual components (dev only)
python3 salesforce_agent.py --port 8001
python3 jira_agent.py --port 8002
python3 servicenow_agent.py --port 8003
# Plan-and-execute functionality built into orchestrator
python3 orchestrator.py              # A2A server mode (only mode, default port 8000)
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
├── orchestrator.py              # Main orchestrator A2A server entry
├── orchestrator_cli_textual.py  # Textual TUI client
├── salesforce_agent.py          # SF agent entry
├── jira_agent.py               # Jira agent entry
├── servicenow_agent.py         # ServiceNow agent entry
├── start_system.py              # System starter
├── src/
│   ├── orchestrator/
│   │   ├── a2a_main.py         # A2A server interface
│   │   ├── a2a_handler.py      # A2A request processing
│   │   ├── plan_execute_graph.py # LangGraph plan-and-execute pattern
│   │   ├── plan_execute_state.py # State schema with layered architecture
│   │   ├── simple_layered_state.py # AgentVisibleState implementation
│   │   ├── conversation_handler.py # Message processing & summarization
│   │   ├── llm_handler.py      # Azure OpenAI integration & plan modification
│   │   ├── agent_registry.py   # Service discovery & health monitoring
│   │   ├── agent_caller_tools.py # Agent delegation tools
│   │   ├── state.py            # Legacy state definitions
│   │   └── types.py            # Type definitions
│   ├── agents/
│   │   ├── salesforce/
│   │   │   └── main.py         # SF LangGraph agent
│   │   ├── jira/
│   │   │   └── main.py         # Jira LangGraph agent
│   │   └── servicenow/
│   │       └── main.py         # ServiceNow LangGraph agent
│   ├── a2a/
│   │   ├── protocol.py         # A2A protocol (for network calls)
│   │   └── circuit_breaker.py  # Resilience for A2A
│   ├── tools/
│   │   ├── salesforce/
│   │   │   └── unified.py      # 6 unified Salesforce tools
│   │   ├── jira/
│   │   │   └── unified.py      # 11 unified Jira tools
│   │   ├── servicenow/
│   │   │   └── unified.py      # 6 unified ServiceNow tools
│   │   └── utility/
│   │       └── web_search.py   # Web search tool
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
├── logs/                       # JSON logs by component
└── test_orchestrator_a2a.py    # A2A interface test script
```

## 🛠️ Core Tools

### Salesforce Tools (6 unified)
- **GetSalesforceTool**: Get records by ID or search criteria
- **CreateSalesforceTool**: Create new records (Lead, Account, Opportunity, etc.)
- **UpdateSalesforceTool**: Update existing records
- **SalesforceSearchTool**: SOQL/SOSL search across all objects
- **SalesforceAnalyticsTool**: Pipeline analytics and aggregations
- **SalesforceCollaborationTool**: Activity and note management

### Jira Tools (11 unified)
- **GetJiraTool**: Get issues by key or ID
- **CreateJiraTool**: Create new issues (bug, story, task, epic)
- **UpdateJiraTool**: Update issue fields and transitions
- **JiraSearchTool**: JQL search with natural language support
- **JiraAnalyticsTool**: Sprint metrics and team analytics
- **JiraCollaborationTool**: Comments and collaboration features
- **JiraGetResource**: Get projects, users, boards, sprints
- **JiraListResources**: List all resource types
- **JiraUpdateResource**: Update projects, boards, sprints
- **JiraSprintOperations**: Sprint management

### ServiceNow Tools (6 unified)
- **GetServiceNowTool**: Get records by sys_id or number
- **CreateServiceNowTool**: Create incidents, changes, problems
- **UpdateServiceNowTool**: Update ITSM records
- **ServiceNowSearchTool**: GlideQuery search across tables
- **ServiceNowAnalyticsTool**: ITSM metrics and reporting
- **ServiceNowWorkflowTool**: Process automation and approvals

### Orchestrator Tools
- **SalesforceAgentTool**: Routes CRM operations to SF agent
- **JiraAgentTool**: Routes issue management to Jira agent
- **ServiceNowAgentTool**: Routes ITSM operations to ServiceNow agent
- **AgentRegistryTool**: System health monitoring
- **WebSearchTool**: External information gathering

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

### 🔄 Plan-and-Execute Orchestration

### Why Plan-and-Execute Pattern?
The orchestrator implements LangGraph's plan-and-execute pattern for complex multi-step workflows:
- **Dynamic Planning**: LLM generates execution plans for complex tasks
- **Task Context Injection**: Each agent receives structured context about their role
- **Skip Navigation**: Users can skip to specific steps or skip multiple steps
- **Real-time Modification**: Plans can be modified during execution

### Plan Generation Process
1. **User Request**: Complex multi-step request received
2. **Plan Creation**: LLM creates structured ExecutionPlan with tasks
3. **Task Execution**: Orchestrator delegates each task to appropriate agent
4. **Plan Modification**: User can skip steps or provide feedback
5. **Plan Summary**: Final results aggregated and presented

### Plan Modification Types
- **skip_to_step**: Jump to specific step in current plan
- **skip_steps**: Skip multiple specific steps in current plan  
- **conversation_only**: Just talking, no plan changes needed

### Example Business Processes
```bash
# Complex workflows handled by plan-and-execute
"find all critical incidents and create jira tickets"
"check account health for our top 5 opportunities"
"update express logistics opportunity and create case"
"analyze deal risk across all our open opportunities"
```

## 🎯 Usage Examples

### Interactive CLI Mode
```bash
# Account operations
"get the Genepoint account"
"get all records for Genepoint"

# CRUD operations
"create new lead for John Smith at TechCorp"
"update opportunity ABC123 to Closed Won"

# Plan-and-execute operations
"find all critical incidents and create jira tickets"
"check account health for our top 5 opportunities"

# System admin
"check agent status"
"list available agents"
```

### A2A Mode (Network Interface)
```bash
# Start orchestrator A2A server
python3 orchestrator.py

# Or start entire system 
python3 start_system.py --orchestrator-port 8000

# Test A2A interface
python3 test_orchestrator_a2a.py

# Call orchestrator from another agent/system
curl -X POST http://localhost:8000/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "process_task",
    "params": {
      "task": {
        "id": "test-001",
        "instruction": "Get the GenePoint account from Salesforce",
        "context": {}
      }
    },
    "id": "test-001"
  }'
```

## 🏆 Design Principles

### TYPE SAFETY
- **WE DO IT HERE**
- **Ensure** all structs have proper type definitions
- **Ensure** all returns respect the caller's expected type
- **Ensure** all access to fields within objects are safe
- **Periodically** run mypy and other tooling to sniff out type safety smells

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

### State Synchronization (Critical!)
**Problem**: System agents (Jira, Salesforce, ServiceNow) were not receiving orchestrator state
**Solution**: All agents now merge `state_snapshot` into their context

```python
# All system agents now do this:
state_snapshot = task_data.get("state_snapshot", {})
merged_context = {
    **context,
    "orchestrator_state": state_snapshot  # Contains messages, memory, etc.
}
```

**Impact**: Agents can now see:
- Recent conversation history (`messages`)
- Memory data (accounts, contacts, etc.)
- Conversation summaries
- Any orchestrator state that provides context

**Example**: Jira agent can now see that "NTP project was just created" from orchestrator state

### Context Window Management (NEW!)
**Problem**: Agents hitting 130k+ token limits with large conversations
**Solution**: Smart message trimming with LangChain's official utilities

```python
# Orchestrator: 80k token limit
# System agents: 70k token limit
from src.utils.agents.message_processing import trim_messages_for_context

trimmed_messages = trim_messages_for_context(
    messages,
    max_tokens=70000,
    keep_system=False,
    keep_first_n=2,
    keep_last_n=15,
    use_smart_trimming=True
)
```

**Features**:
- Preserves tool calls and their results together
- Keeps most recent messages for context
- Logs token usage for monitoring
- Applied to all agents (Salesforce, Jira, ServiceNow)

## 📚 Key Architecture Decisions

1. **Loose Coupling**: Tools as interface contracts
2. **Resilience**: Circuit breaker for network calls only (A2A)
3. **Memory**: Simple async SQLite adapter
4. **A2A Protocol**: JSON-RPC 2.0 standard
5. **LangGraph**: State management with checkpointing
6. **Thread Persistence**: Full state storage
7. **BaseAgentTool**: DRY pattern for agents
8. **Constants**: Centralized in `constants.py`
9. **YAGNI Applied**: Removed speculative features (events system)
10. **Global Recursion Limit**: 15 iterations max for all agents (configurable)
11. **Modular Code Organization**: Split large files (sys_msg.py, ux.py) into focused modules
12. **Query Builder Pattern**: Base query builder with platform-specific implementations
13. **Simple Triggers**: Replaced event system with counters (98% less code)
14. **State Synchronization**: All agents receive orchestrator context
15. **Smart Context Management**: Token-aware message trimming

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

## 🔄 Current Session Context (Updated 2025-07-20)

### Recent Major Updates: Implementation Review & Documentation Cleanup

**Completed Work**: Comprehensive review and cleanup of system documentation
- **Issue**: CLAUDE.md and README.md contained references to non-existent workflow agent
- **Root Cause**: Documentation was describing planned workflow agent that was never implemented
- **Reality Check**: Confirmed actual implementation is pure plan-and-execute orchestrator

**Key Findings from Implementation Review**:
1. **No Workflow Agent**: The workflow agent directory and tools don't exist in codebase
2. **Plan-and-Execute Only**: Orchestrator handles complex workflows via built-in plan-and-execute pattern
3. **Textual UI Only**: No separate Rich CLI exists, only `orchestrator_cli_textual.py`
4. **11 Jira Tools**: Actual count is 11 unified tools, not 6 or 10
5. **Simplified State**: AgentVisibleState with no memory complexity works as documented

**Documentation Updates Completed**:
- ✅ **README.md**: Updated architecture diagram, removed workflow agent, fixed CLI references
- ✅ **CLAUDE.md**: Removed workflow agent sections, updated file structure, corrected tool counts
- ✅ **System Architecture**: Now accurately reflects plan-and-execute with A2A agents
- ✅ **Quick Start**: Fixed CLI command (`orchestrator_cli_textual.py`)
- ✅ **Project Structure**: Updated to match actual file structure

### Previous Work: Textual UI Fixes (COMPLETED)
**Problem**: User reported textual CLI interface issues:
- Can't see typed input until hitting enter
- Assistant responses not displaying in conversation area
- Getting A2AClient errors about missing 'send_message' method
- **NEW**: Plan display goes from 5 steps to 2 when interrupts happen, instead of showing original plan with skipped steps marked

**Root Causes Identified**:
1. **A2AClient Missing Method**: `orchestrator_cli_textual.py` was calling non-existent `send_message()` method
2. **Missing Event Handler**: Textual client wasn't handling `summary_generated` events (how orchestrator sends final responses)
3. **Input Visibility**: CSS styling made input field hard to see
4. **Terminal Corruption**: App didn't properly restore terminal settings on exit
5. **Plan Display Bug**: `plan_updated` events from replan node only contained `task_id` and `timestamp` - no plan data. Textual client had no handler for these events.

**Fixes Applied**:
- ✅ **Fixed A2AClient**: Replaced `send_message()` with proper SSE streaming like Rich version
- ✅ **Added Event Handler**: Added `summary_generated` event handler in `process_sse_event()` method
- ✅ **Enhanced CSS**: Updated `textual_styles.tcss` with better input field visibility
- ✅ **Added Terminal Cleanup**: Added signal handlers and proper cleanup in `main()` function
- ✅ **Comprehensive Logging**: Added debug logging for input changes, message processing, SSE events
- ✅ **Fixed Plan Display**: Enhanced `plan_updated` events to include plan data and added handler in textual client

**Files Modified**:
- `orchestrator_cli_textual.py`: Main fixes for SSE streaming, event handling, terminal cleanup, plan_updated handler
- `textual_styles.tcss`: Enhanced CSS for input visibility
- `src/orchestrator/a2a_handler.py`: Enhanced plan_updated events to include plan data

**Current Status**: 
- All fixes implemented and saved
- Plan display bug fixed - now includes plan data in plan_updated events
- Ready for comprehensive testing

**Next Steps**:
1. Test `python3 orchestrator_cli_textual.py` 
2. Verify input is visible while typing
3. Confirm assistant responses appear in conversation area
4. **Test interrupt functionality**: Create plan, interrupt, continue - verify plan shows original tasks with skipped steps marked
5. Check terminal doesn't break on exit

**Key Technical Details**:
- Orchestrator sends responses via `summary_generated` events, not `response` events
- SSE streaming endpoint: `http://localhost:8000/a2a/stream`
- Debug logs show textual_client receiving events but weren't being processed
- Terminal issues caused by Textual's raw mode not being properly restored
- **Plan Display**: `plan_updated` events now include full plan data like `plan_modified` events do

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

### ServiceNow Company Table Names
**Problem**: Different ServiceNow instances use different table names for company records
- **Errors**: 403 Forbidden for `core_company`, 400 Bad Request for `cmn_company` and `customer_account`
- **Root Cause**: Table names vary by instance configuration and installed plugins
- **Solution**: Use `core_company` as the standard table name in workflows
- **Note**: No longer applicable - workflow agent removed from system

### A2A Parameter Handling
**Problem**: ServiceNow agent expecting `"task"` wrapper but A2A sends parameters directly
- **Root Cause**: Inconsistent parameter handling between agents
- **Fix**: Add fallback: `task_data = params.get("task", params)`
- **Location**: `src/agents/servicenow/main.py:137`

### Orchestrator A2A Mode vs Interactive Mode
**Problem**: Using A2A protocol for CLI client but getting single-task behavior
- **Root Cause**: A2A system message was designed for single-task operations, not conversations
- **Solution**: A2A handler checks `context.source == "cli_client"` to determine mode
- **Interactive CLI**: Uses regular orchestrator system message for full conversational features
- **True A2A calls**: Uses A2A system message for focused, single-task execution
- **Key**: The CLI client sets `"source": "cli_client"` in the context to trigger interactive mode

### Environment Variable Escaping
**Problem**: Passwords with special characters (`!$@#`) causing authentication failures
- **Root Cause**: Python environment variable handling needs proper escaping
- **Fix**: Use `os.environ.get()` directly, avoid shell interpretation
- **Test**: Verify with curl command line vs Python requests

### State Persistence
**Problem**: LangChain messages break when saved directly to storage
- **Root Cause**: Message objects not JSON serializable
- **Fix**: Always use `serialize_messages()` before storage
- **Pattern**: `state_to_save = {"messages": serialize_messages(messages)}`

### Memory Namespace Format
**Problem**: Memory operations failing with string namespace
- **Root Cause**: Memory expects tuple namespace format
- **Fix**: Use `("memory", user_id)` not `"memory"`
- **Pattern**: Always use tuple format for namespaces

### Plan Interruption and Resume
**How it works**: Plan execution can be interrupted and resumed using LangGraph's interrupt mechanism
- **Plan Execution Side**: 
  - User can interrupt plans with Ctrl+C during execution
  - Execution pauses, preserves state
  - Can resume with modified plans or skip steps
- **Orchestrator Side**:
  - Handles plan interruption gracefully
  - Preserves completed tasks and current state
  - Supports plan modification during resume
- **Key Files**:
  - `src/orchestrator/plan_execute_graph.py` - Plan execution with interrupt support
  - `src/orchestrator/conversation_handler.py` - Resume logic
  - `src/orchestrator/a2a_handler.py` - Plan state management

### Plan Display During Interrupts (FIXED)
**Problem**: Plan display goes from 5 steps to 2 when interrupts happen, instead of showing original plan with skipped steps marked
- **Root Cause**: `plan_updated` events from replan node only contained `task_id` and `timestamp` - no plan data
- **Impact**: Textual client had no handler for `plan_updated` events, so plan display wasn't updated after interrupts
- **Solution**: Enhanced `plan_updated` events to include full plan data (plan, current_task_index, skipped_task_indices)
- **Files Fixed**: 
  - `src/orchestrator/a2a_handler.py:1053-1069` - Enhanced plan_updated event data
  - `orchestrator_cli_textual.py:536-566` - Added plan_updated event handler
- **Testing**: Create plan, interrupt with Ctrl+C, continue - verify plan shows original tasks with skipped steps marked

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