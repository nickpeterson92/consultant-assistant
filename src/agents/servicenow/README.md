```
███████╗███████╗██████╗ ██╗   ██╗██╗ ██████╗███████╗███╗   ██╗ ██████╗ ██╗    ██╗
██╔════╝██╔════╝██╔══██╗██║   ██║██║██╔════╝██╔════╝████╗  ██║██╔═══██╗██║    ██║
███████╗█████╗  ██████╔╝██║   ██║██║██║     █████╗  ██╔██╗ ██║██║   ██║██║ █╗ ██║
╚════██║██╔══╝  ██╔══██╗╚██╗ ██╔╝██║██║     ██╔══╝  ██║╚██╗██║██║   ██║██║███╗██║
███████║███████╗██║  ██║ ╚████╔╝ ██║╚██████╗███████╗██║ ╚████║╚██████╔╝╚███╔███╔╝
╚══════╝╚══════╝╚═╝  ╚═╝  ╚═══╝  ╚═╝ ╚═════╝╚══════╝╚═╝  ╚═══╝ ╚═════╝  ╚══╝╚══╝ 

 █████╗  ██████╗ ███████╗███╗   ██╗████████╗
██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   
██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   
██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   
╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   
```

<div align="center">
  <h3>🛠️ Enterprise ITSM Automation with AI Intelligence 🛠️</h3>
  
  [![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
  [![LangGraph](https://img.shields.io/badge/LangGraph-0.2.69-green.svg)](https://github.com/langchain-ai/langgraph)
  [![ServiceNow API](https://img.shields.io/badge/ServiceNow-Table%20API-red.svg)](https://developer.servicenow.com/dev.do)
  [![A2A Protocol](https://img.shields.io/badge/A2A%20Protocol-JSON--RPC%202.0-purple.svg)](https://github.com/google-a2a/A2A)
</div>

---

# ServiceNow Agent

A specialized AI agent for ServiceNow ITSM operations, implementing 6 unified tools that provide comprehensive IT Service Management capabilities with Natural Language Query (NLQ) support.

## Architecture

The ServiceNow agent is built on:
- **LangGraph**: State machine orchestration with tool calling
- **A2A Protocol**: JSON-RPC 2.0 for agent communication
- **Unified Tools**: 6 comprehensive tools covering all ITSM operations
- **Smart Features**: NLQ support, auto table detection, workflow management

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           SERVICENOW AGENT                                 │
│  ┌──────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐    │
│  │   A2A Handler    │  │   LangGraph     │  │   Security Layer        │    │
│  │   JSON-RPC 2.0   │  │   State Mgmt    │  │   Input Validation      │    │
│  │   (/a2a endpoint)│  │   Memory        │  │  Glide Query Builder    │    │
│  └──────────────────┘  └─────────────────┘  └─────────────────────────┘    │
│                                   │                                        │
│  ┌────────────────────────────────┴────────────────────────────────────┐   │
│  │                    SPECIALIZED TOOL EXECUTION LAYER                 │   │
│  │                                                                     │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │   │
│  │  │ Incident Mgmt   │  │ Change Request  │  │ Problem Management  │  │   │
│  │  │ (3 tools)       │  │ (3 tools)       │  │ (3 tools)           │  │   │
│  │  │ Get,Create,Updt │  │ Get,Create,Updt │  │ Get,Create,Update   │  │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │   │
│  │                                                                     │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │   │
│  │  │ Task Management │  │ User & CMDB     │  │ Global Search       │  │   │
│  │  │ (3 tools)       │  │ (2 tools)       │  │ (1 tool)            │  │   │
│  │  │ Get,Create,Updt │  │ Users, CIs      │  │ Cross-table Search  │  │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                        │
│  ┌────────────────────────────────┴────────────────────────────────────┐   │
│  │                       GLIDE QUERY BUILDER                           │   │
│  │                                                                     │   │
│  │  • Natural Language Processing  • Query Templates    • Security     │   │
│  │  • Field Value Mapping         • Operator Support   • Validation    │   │
│  │  • Table-specific Queries      • Error Handling     • Performance   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                        │
│  ┌────────────────────────────────┴────────────────────────────────────┐   │
│  │                       SERVICENOW API LAYER                          │   │
│  │                                                                     │   │
│  │  • REST API Integration                                             │   │
│  │  • Table API Endpoints                                              │   │
│  │  • Authentication & Sessions                                        │   │
│  │  • Rate Limiting & Retries                                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
```

## Tools Overview

### 1. ServiceNowGet
**Purpose**: Direct record retrieval by sys_id or number
```python
# Auto-detects table from number prefix
"get INC0010023"  # Automatically knows it's an incident
"get CHG0030045"  # Automatically knows it's a change request
"get PRB0007001"  # Automatically knows it's a problem

# Direct sys_id retrieval
"get incident sys_id a9e30c7dc0a80166145e7a95ca9619be"
```

**Features**:
- Auto-detection of table from number prefixes (INC→incident, CHG→change_request, etc.)
- Supports both sys_id and number lookups
- Dot-walking support for related fields (e.g., caller_id.name)
- Field selection for performance optimization

### 2. ServiceNowSearch
**Purpose**: Search records with natural language or encoded queries
```python
# Natural language (uses NLQ API)
"find all critical incidents from last week"
"show me changes scheduled for this weekend"
"list problems affecting email service"

# Encoded queries (Glide syntax)
"search incidents where priority=1^state!=6"
"find change_requests where risk=high^planned_start>javascript:gs.beginningOfWeek()"
```

**Features**:
- Natural Language Query (NLQ) API integration
- Fallback to encoded query guidance if NLQ fails
- Dot-walking support (caller_id.name, assigned_to.department)
- Configurable ordering and limits
- Default field selection based on table type

### 3. ServiceNowCreate
**Purpose**: Create records in any ServiceNow table
```python
"create high priority incident for database outage affecting production"
"create change request for server upgrade next Saturday"
"create problem record for recurring login failures"
```

**Features**:
- Automatic validation of required fields by table type
- Smart defaults for common fields
- Returns key identifying fields (sys_id, number, short_description)
- Clear error messages for missing required fields

### 4. ServiceNowUpdate
**Purpose**: Update records following ServiceNow best practices
```python
# Update by number (recommended)
"update INC0010023 set state to In Progress and assign to john.smith"

# Update by sys_id
"update incident sys_id abc123 set priority to Critical"

# Bulk updates with where clause
"update all incidents where category=network AND state=new set assignment_group=network_team"
```

**Features**:
- Supports sys_id, number, or where clause updates
- Uses PATCH method for partial updates (ServiceNow best practice)
- Number lookups resolve to sys_id first (performance optimization)
- Bulk update capability with encoded queries
- Returns updated record details

### 5. ServiceNowWorkflow
**Purpose**: Handle workflow operations like approvals and state transitions
```python
# Approvals
"approve change CHG0030045 with comment 'Approved for weekend maintenance'"
"reject change CHG0030046 with reason 'Insufficient testing'"

# Assignments
"assign INC0010023 to john.smith in network team"

# State transitions
"transition incident INC0010024 to Resolved with work notes 'Issue fixed by restart'"
```

**Features**:
- Specialized workflow actions: approve, reject, assign, transition
- State validation with proper value mapping
- Automatic work notes and approval history
- Assignment group support
- Comments and work notes integration

### 6. ServiceNowAnalytics
**Purpose**: Get metrics and analytics from ServiceNow data
```python
# Simple counts
"count of critical incidents this month"
"total number of open changes"

# Breakdowns
"incident breakdown by priority"
"change requests by risk level last quarter"

# Trend analysis
"incident trend over last 30 days"
"problem ticket volume by category"
```

**Features**:
- Metric types: count, breakdown, trend
- Time period filters (last 7/30/90 days)
- Group by analysis for any field
- Aggregate API support for performance
- Headers parsing for accurate counts

## Configuration

### Environment Variables
```bash
# Required
SNOW_INSTANCE=your-instance.service-now.com
SNOW_USER=your-username
SNOW_PASS=your-password

# Azure OpenAI (Required)
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-4o-mini
AZURE_OPENAI_API_KEY=your-key
```

### A2A Configuration
- **Default Port**: 8003
- **Host**: 0.0.0.0 (configurable)
- **Protocol**: JSON-RPC 2.0
- **Endpoints**:
  - `POST /a2a` - Process tasks
  - `GET /a2a/agent-card` - Get capabilities

## Usage Examples

### Incident Management
```bash
# Get specific incident
"get incident INC0010023"

# Search incidents
"find all critical incidents assigned to me"
"show unresolved incidents created today"
"list incidents for email service"

# Create incident
"create critical incident: Database connection timeout in production"

# Update incident
"update INC0010023 set priority to High and assign to DBA team"
"resolve INC0010024 with resolution 'Restarted service'"
```

### Change Management
```bash
# Get change
"get change CHG0030045"

# Search changes
"find emergency changes for this week"
"list changes in Scheduled state"

# Create change
"create standard change for monthly patching"

# Workflow
"approve CHG0030045 for implementation"
```

### Problem Management
```bash
# Search problems
"find all problems related to authentication"
"show problems created by major incidents"

# Create problem
"create problem for recurring disk space issues"

# Update problem
"update PRB0007001 add known error 'Check log rotation settings'"
```

### Analytics & Reporting
```bash
# Incident metrics
"incident count by priority this month"
"average resolution time for critical incidents"
"incident volume trend last 30 days"

# Change metrics
"change success rate by type"
"emergency changes last quarter"

# Problem metrics
"problems by category"
"problem tickets without known errors"
```

## Technical Details

### State Management
The agent uses LangGraph's state schema:
```python
class ServiceNowAgentState(TypedDict):
    messages: Annotated[List[Any], operator.add]
    current_task: str
    tool_results: List[Dict[str, Any]]
    error: str
    task_context: Dict[str, Any]
    external_context: Dict[str, Any]
```

### Table Detection
Automatic table detection from number prefixes:
```python
{
    'INC': 'incident',
    'CHG': 'change_request',
    'PRB': 'problem',
    'RITM': 'sc_req_item',
    'TASK': 'task',
    'REQ': 'sc_request',
    'STASK': 'sc_task'
}
```

### Field Defaults
Smart field selection based on table type:
- **Incidents**: number, short_description, state, priority, assigned_to, caller_id
- **Changes**: number, short_description, state, risk, type, assigned_to
- **Problems**: number, short_description, state, priority, assigned_to

### State Mappings
Proper state value mappings for transitions:
- **Incidents**: New=1, In Progress=2, On Hold=3, Resolved=6, Closed=7
- **Changes**: New=-5, Scheduled=-4, Implement=-3, Review=-2, Closed=0
- **Problems**: New=1, In Progress=2, Pending=3, Resolved=4, Closed=5

## Natural Language Query (NLQ)

The agent supports ServiceNow's NLQ API for intuitive searches:

### How it works
1. Natural language query is sent to NLQ API
2. ServiceNow returns encoded query
3. Agent executes search with encoded query
4. If NLQ fails, agent provides guidance for structured query

### Examples
```bash
# NLQ converts these:
"critical incidents from last week" 
→ "priority=1^sys_created_on>=javascript:gs.beginningOfLastWeek()"

"changes for this weekend"
→ "type=standard^planned_start>=javascript:gs.beginningOfWeekend()"

"my open incidents"
→ "assigned_to=javascript:gs.getUserID()^state!=6^state!=7"
```

## Security Features

- **GlideQueryBuilder**: Prevents injection attacks
- **Input validation**: All inputs sanitized
- **Credential security**: No credentials in logs
- **Field validation**: Ensures proper data types
- **API limits**: Respects ServiceNow rate limits

## Logging

Logs are written to `logs/servicenow.log` with structured JSON format:
```json
{
  "timestamp": "2025-07-23T10:30:00Z",
  "level": "INFO",
  "component": "servicenow",
  "tool_name": "servicenow_search",
  "operation": "nlq_query",
  "natural_query": "critical incidents from last week",
  "encoded_query": "priority=1^sys_created_on>=javascript:gs.beginningOfLastWeek()"
}
```

### Key Log Events
- `tool_call` - Tool invocation with arguments
- `tool_result` - Successful execution
- `tool_error` - Execution failures
- `nlq_query` - Natural language processing
- `encoded_query` - Generated Glide queries

## Common Issues

### NLQ Not Understood
If you see "Natural language query not understood":
- Be more specific with criteria
- Use table-specific terms (incident, change, problem)
- Fall back to structured queries

### Authentication Failures
Ensure:
- Instance URL is correct (no https://)
- Username/password are valid
- User has necessary roles

### Missing Required Fields
Each table has different requirements:
- **Incidents**: short_description, caller_id
- **Changes**: short_description, type
- **Problems**: short_description

## Best Practices

1. **Use number for updates** - More user-friendly than sys_id
2. **Leverage NLQ** - Let ServiceNow parse natural language
3. **Specify fields** - Reduce payload size
4. **Use analytics for counts** - More efficient than search
5. **Check produces_user_data** - For UI integration
6. **Handle dot-walking** - Access related record fields

## Architecture Decisions

- **6 Unified Tools**: Comprehensive coverage with less complexity
- **NLQ Integration**: Natural language first approach
- **Auto-detection**: Smart inference from record numbers
- **Best Practices**: Follow ServiceNow Table API guidelines
- **Workflow Focus**: Specialized tool for approvals/transitions