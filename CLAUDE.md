# CLAUDE.md - AI Assistant Guide

## 📅 Current Context
- **Year**: 2025 (use for web searches)
- **Architecture**: Plan-and-Execute multi-agent orchestrator using LangGraph
- **UI**: Rich terminal interface with real-time updates via SSE

## 🏗️ System Architecture

```
USER → Textual CLI → ORCHESTRATOR (Plan & Execute) → A2A Protocol → AGENTS
                           ↓
                    Memory Graph (NetworkX)
```

## 🚀 Quick Start

```bash
# Complete system startup
python3 start_system.py

# In new terminal, launch UI
python3 orchestrator_cli_textual.py
```

## 📁 Project Structure

```
consultant-assistant/
├── orchestrator_cli_textual.py   # Rich terminal UI with split-screen
├── orchestrator.py               # Main A2A server entry
├── start_system.py              # System startup orchestration
├── salesforce_agent.py          # Salesforce agent entry
├── jira_agent.py                # Jira agent entry
├── servicenow_agent.py          # ServiceNow agent entry
├── src/
│   ├── orchestrator/
│   │   ├── plan_and_execute.py # Core workflow
│   │   ├── core/               # Core components
│   │   │   ├── agent_registry.py
│   │   │   ├── llm_handler.py
│   │   │   └── state.py
│   │   ├── observers/          # Event observers
│   │   │   ├── base.py
│   │   │   ├── sse_observer.py
│   │   │   ├── memory_observer.py
│   │   │   ├── interrupt_observer.py
│   │   │   └── registry.py
│   │   ├── workflow/           # Workflow components
│   │   │   ├── entity_extractor.py
│   │   │   ├── event_decorators.py
│   │   │   └── interrupt_handler.py
│   │   ├── tools/              # Orchestrator tools
│   │   │   ├── agent_caller_tools.py
│   │   │   ├── base.py
│   │   │   ├── human_input.py
│   │   │   └── web_search.py
│   │   └── a2a/                # A2A server
│   │       ├── server.py
│   │       └── handler.py
│   ├── agents/                 # Agent implementations
│   │   ├── salesforce/
│   │   │   ├── main.py
│   │   │   └── tools/
│   │   │       ├── base.py
│   │   │       └── unified.py
│   │   ├── jira/
│   │   │   ├── main.py
│   │   │   └── tools/
│   │   │       ├── base.py
│   │   │       └── unified.py
│   │   └── servicenow/
│   │       ├── main.py
│   │       └── tools/
│   │           ├── base.py
│   │           └── unified.py
│   ├── a2a/                    # A2A protocol
│   │   ├── protocol.py
│   │   └── circuit_breaker.py
│   ├── memory/                 # Memory system
│   │   ├── memory_manager.py
│   │   ├── memory_graph.py
│   │   ├── memory_node.py
│   │   ├── graph_algorithms.py
│   │   ├── semantic_embeddings.py
│   │   └── summary_generator.py
│   └── utils/                  # Utilities
│       ├── config/
│       │   ├── constants.py
│       │   └── unified_config.py
│       ├── storage/
│       │   ├── async_store_adapter.py
│       │   ├── async_sqlite.py
│       │   ├── memory_schemas.py
│       │   └── sqlite_store.py
│       ├── logging/
│       │   ├── framework.py
│       │   ├── logger.py
│       │   └── multi_file_logger.py
│       ├── ui/
│       │   ├── memory_graph_widget.py
│       │   ├── clean_graph_renderer.py
│       │   ├── advanced_graph_renderer.py
│       │   ├── animations.py
│       │   ├── colors.py
│       │   └── terminal.py
│       ├── agents/
│       │   └── message_processing/
│       │       ├── helpers.py
│       │       ├── serialization.py
│       │       └── unified_serialization.py
│       ├── message_serialization.py
│       ├── helpers.py
│       ├── tool_execution.py
│       ├── input_validation.py
│       ├── soql_query_builder.py
│       └── glide_query_builder.py
├── logs/                       # Multi-file logs
├── memory_store.db            # SQLite DB
├── system_config.json         # Config
├── agent_registry.json        # Agent registry
├── textual_styles.tcss        # UI styles
└── requirements.txt           # Dependencies
```

## 🛠️ Core Implementation Details

### Plan-and-Execute Workflow
- Based on LangGraph canonical tutorial
- **Planner**: Generates multi-step plans
- **Executor**: Runs steps with context injection
- **Replanner**: Adjusts based on results/interrupts
- **Past Steps Culling**: Keeps last 30 when exceeding 50

### Memory Graph
- **NetworkX** graph with nodes and relationships
- **Node Types**: entities, actions, search results, plans
- **Edge Types**: led_to, relates_to, depends_on, produces
- **Entity Extraction**: Pattern-based ID detection
- **Retrieval**: Relevance + recency scoring

### Interrupt System
- **User Escape (ESC)**: Modify plan mid-execution
- **Agent Interrupts**: HumanInputTool for clarification
- **Priority**: User interrupts take precedence
- **State Management**: InterruptObserver tracks state

### A2A Protocol
- **JSON-RPC 2.0** over HTTP
- **Endpoints**: 
  - POST /a2a (task processing)
  - GET /a2a/agent-card (capabilities)
  - GET /a2a/stream (SSE events)
  - WS /ws (WebSocket for interrupts)
- **Connection Pool**: 20 total, 20 per host (supports 8+ concurrent)
- **Circuit Breaker**: 5 failures → 30s timeout
- **Retry**: 3 attempts with exponential backoff

## 🧠 Core Intelligence Features

### Plan-and-Execute Workflow
```
START → planner → execute_step → replan_step → END
                         ↑              ↓
                         └──────────────┘
                        (cycles until complete)
```

**Key Components:**
- **planner**: Generates initial multi-step plan from user request
- **execute_step**: Executes current step with memory context + entity extraction
- **replan_step**: Decides to continue, modify plan, or complete
- **should_end**: Routes to END when response is ready

### Memory Graph Intelligence
- **PageRank**: Identifies important nodes (frequently referenced memories)
- **Community Detection**: Clusters related entities using Louvain algorithm
- **Semantic Search**: Embedding-based retrieval with cosine similarity
- **Time Decay**: Relevance decreases by 0.1 per hour (configurable)
- **Relationship Types**: led_to, relates_to, belongs_to, produces, depends_on

### Interrupt Architecture
```
User Interrupts (ESC key):
  1. User presses ESC → UI sets flag
  2. execute_step checks flag → raises GraphInterrupt
  3. Modal appears for plan modification
  4. Resume with should_force_replan=True

Agent Interrupts (HumanInputTool):
  1. Agent needs clarification
  2. Raises GraphInterrupt with question
  3. UI shows question to user
  4. Resume with answer (no replanning)
```

## 💡 Key Patterns

### Message Serialization (Critical!)
```python
# ❌ WRONG - will crash on restore
state_to_save = {"messages": messages}

# ✅ RIGHT - always serialize first
from src.utils.message_serialization import serialize_messages
state_to_save = {"messages": serialize_messages(messages)}
```

### State Updates in LangGraph
```python
# ❌ WRONG - modifying state directly
state["field"] = value

# ✅ RIGHT - return updates
return {"field": value}
```

### Memory Namespace
```python
# Always use tuple format
namespace = ("memory", user_id)
```

## 🔍 Debugging Commands

```bash
# Watch Salesforce operations
tail -f logs/salesforce.log | grep -E "(tool_call|tool_result)"

# Monitor errors
tail -f logs/errors.log

# Check memory operations
tail -f logs/orchestrator.log | grep "memory_"

# Watch SSE events
tail -f logs/orchestrator.log | grep "sse_"

# Track interrupt handling
tail -f logs/orchestrator.log | grep -E "(interrupt|escape|human_input)"
```

## 🎯 Common Tasks

### Testing Agents Directly
```bash
# Start individual agent
python3 salesforce_agent.py --port 8001

# Test via curl
curl -X POST http://localhost:8001/a2a \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"process_task","params":{"task_id":"test","instruction":"get GenePoint account"},"id":"test"}'
```

### Adding Constants
```python
# Add to src/utils/config/constants.py
NEW_CONSTANT = "value"

# Import and use
from src.utils.config import NEW_CONSTANT
```

## ⚠️ Common Issues

1. **Duplicate spinner widget**: Check for existing spinner before creating
2. **Dictionary iteration error**: Return state updates, don't modify directly
3. **Import errors after reorg**: Update paths to use new structure
4. **Memory not showing**: Check event emission and graph relationships
5. **Interrupt not working**: Ensure Command object includes state updates

## 🏆 Design Principles

- **DRY**: Extract common functionality (BaseAgentTool pattern)
- **KISS**: Prefer simple solutions over clever ones
- **YAGNI**: Don't add features until needed
- **PEP8**: Follow Python style guide

## 📊 Tool Summary

### Salesforce Agent (6 Unified Tools)
- **SalesforceGet**: Retrieve any record by ID (auto-detects object type)
- **SalesforceSearch**: Natural language search with SOQL generation
- **SalesforceCreate**: Create any object type with validation
- **SalesforceUpdate**: Update by ID or WHERE condition
- **SalesforceSOSL**: Cross-object search (when object type unknown)
- **SalesforceAnalytics**: Aggregations (COUNT, SUM, AVG, MIN, MAX)

### Jira Agent (11 Tools)
- **JiraGet**: Get issue by key with comments/attachments
- **JiraSearch**: Natural language or JQL search
- **JiraCreate**: Create issues/subtasks (requires account ID for assignee)
- **JiraUpdate**: Update fields, transitions, assignments
- **JiraCollaboration**: Comments, attachments, issue links
- **JiraAnalytics**: Issue history, worklog, project stats
- **JiraProjectCreate**: Create projects (requires lead account ID)
- **JiraGetResource**: Get projects, users, boards, sprints
- **JiraListResources**: List/search all resource types
- **JiraUpdateResource**: Update non-issue resources
- **JiraSprintOperations**: Create, start, complete sprints

### ServiceNow Agent (6 Unified Tools)
- **ServiceNowGet**: Auto-detect table from number (INC, CHG, PRB)
- **ServiceNowSearch**: Natural Language Query (NLQ) support
- **ServiceNowCreate**: Create with automatic field validation
- **ServiceNowUpdate**: Update by sys_id, number, or bulk
- **ServiceNowWorkflow**: Approvals, assignments, state transitions
- **ServiceNowAnalytics**: Count, breakdown, trend analysis

### Orchestrator Tools
- **SalesforceAgentTool**: Routes CRM operations to SF agent
- **JiraAgentTool**: Routes project management to Jira agent
- **ServiceNowAgentTool**: Routes ITSM operations to SN agent
- **WebSearchTool**: Tavily-powered web search
- **AgentRegistryTool**: System health monitoring
- **HumanInputTool**: Agent clarification requests

### Utility
- Web search (Tavily), Human input

## 🔧 Configuration

```bash
# Required environment variables
AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME
AZURE_OPENAI_API_KEY
SFDC_USER/PASS/TOKEN
# Optional: JIRA/ServiceNow credentials, TAVILY_API_KEY
```

## 📝 Important Notes

1. **Always check `global_memory_store`** is not None before use
2. **Thread states** stored as `state_{thread_id}` in `("memory", user_id)`
3. **Background tasks** need `asyncio.run()` in thread contexts
4. **SSE events** must be JSON serializable
5. **Circuit breaker** only for network calls (A2A), not SQLite

## 🧪 Quick Testing Reference

### Test CRUD Operations
```bash
# GET: "get account 001bm00000SA8pSAAT"
# SEARCH: "search for accounts in biotechnology"
# CREATE: "create contact Mike Davis at GenePoint"
# UPDATE: "update GenePoint website to www.new.com"
# ANALYTICS: "show opportunity revenue by stage"
```

### Monitor Key Operations
```bash
# Real-time errors
tail -f logs/errors.log

# Memory graph updates
tail -f logs/orchestrator.log | grep "memory_node_stored"

# Plan execution
tail -f logs/orchestrator.log | grep -E "(plan_step|execute_step)"

# Interrupt flow
tail -f logs/orchestrator.log | grep -E "(interrupt_detected|resume_from_interrupt)"
```

## 🚨 Files That Matter Most

1. `src/orchestrator/plan_and_execute.py` - Core workflow implementation
2. `src/memory/memory_graph.py` - Conversational memory system  
3. `src/orchestrator/workflow/interrupt_handler.py` - Interrupt management
4. `orchestrator_cli_textual.py` - UI implementation
5. `src/utils/message_serialization.py` - Critical for state persistence