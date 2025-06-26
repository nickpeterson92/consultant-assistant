# ServiceNow Agent

Specialized AI agent for ServiceNow ITSM operations via A2A protocol.

## Overview

The ServiceNow agent provides comprehensive IT Service Management automation through 15 specialized tools that handle incidents, changes, problems, and CMDB operations with natural language processing.

## Architecture

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

## ITSM Process Flow

```
Request → Incident → Problem → Change → Resolution
   │         │          │        │         │
   ▼         ▼          ▼        ▼         ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│ Create │→│ Assign │→│ Analyze│→│ Deploy │→│ Close  │
│ Ticket │ │ & Work │ │ Root   │ │ Fix    │ │ & Doc  │
│        │ │        │ │ Cause  │ │        │ │        │
└────────┘ └────────┘ └────────┘ └────────┘ └────────┘

Natural Language Examples:
"create critical incident"     → CreateIncidentTool
"assign INC0010023 to john"    → UpdateIncidentTool
"find problems with email"     → GetProblemTool + Glide Query
"create change for deployment" → CreateChangeRequestTool
```

**Files:**
- **Entry**: `servicenow_agent.py` → `src/agents/servicenow/main.py`
- **Tools**: `src/tools/servicenow_tools.py` (15 specialized tools)
- **Query Builder**: `src/utils/glide_query_builder.py`

## Tools (15 Specialized Tools)

### Incident Management (3 tools)

#### GetIncidentTool
```python
# Search and retrieve incidents
get_incident(number="INC0010023")
get_incident(caller="john.smith", priority="1")
```

#### CreateIncidentTool
```python
# Create new incidents
create_incident(
    short_description="Database outage affecting users",
    priority="1",
    urgency="1",
    caller_id="john.smith"
)
```

#### UpdateIncidentTool
```python
# Update incident details
update_incident(
    number="INC0010023",
    state="6",  # Resolved
    close_notes="Database service restored"
)
```

### Change Management (3 tools)

#### GetChangeRequestTool
```python
# Search change requests
get_change_request(number="CHG0030045")
get_change_request(type="emergency", state="implement")
```

#### CreateChangeRequestTool
```python
# Create change requests
create_change_request(
    short_description="Deploy new API version",
    type="normal",
    risk="low",
    start_date="2024-01-15 02:00:00"
)
```

#### UpdateChangeRequestTool
```python
# Update change details
update_change_request(
    number="CHG0030045",
    state="implement",
    work_notes="Beginning deployment"
)
```

### Problem Management (3 tools)

#### GetProblemTool
```python
# Search problem records
get_problem(number="PRB0020067")
get_problem(short_description="email service", state="open")
```

#### CreateProblemTool
```python
# Create problem records
create_problem(
    short_description="Recurring login failures",
    problem_state="open",
    assigned_to="security-team"
)
```

#### UpdateProblemTool
```python
# Update problem details
update_problem(
    number="PRB0020067",
    state="resolved",
    resolution_code="fix_applied"
)
```

### Task Management (3 tools)

#### GetTaskTool
```python
# Search generic tasks
get_task(number="TASK0040089")
get_task(assigned_to="admin-team", state="open")
```

#### CreateTaskTool
```python
# Create new tasks
create_task(
    short_description="Update server certificates",
    assigned_to="security-team",
    due_date="2024-01-20"
)
```

#### UpdateTaskTool
```python
# Update task details
update_task(
    number="TASK0040089",
    state="completed",
    work_notes="Certificates updated successfully"
)
```

### User & CMDB (3 tools)

#### GetUserTool
```python
# Look up users
get_user(name="john.smith")
get_user(email="john@company.com")
```

#### GetCMDBItemTool
```python
# Retrieve configuration items
get_cmdb_item(name="PROD-WEB-01")
get_cmdb_item(ip_address="192.168.1.100")
```

#### SearchServiceNowTool
```python
# Global search across tables
search_servicenow(
    query="database outage",
    tables=["incident", "problem", "change_request"]
)
```

## Configuration

### Environment Variables
```bash
# Required
SNOW_INSTANCE=company.service-now.com
SNOW_USER=your-username
SNOW_PASS=your-password

# Optional
SERVICENOW_AGENT_PORT=8003
DEBUG_MODE=true
```

### Agent Registry Entry
```json
{
  "servicenow": {
    "host": "localhost",
    "port": 8003,
    "capabilities": [
      "incident_management", "change_management", "problem_management",
      "task_management", "user_lookup", "cmdb_operations"
    ]
  }
}
```

## Usage Examples

### Incident Management
```bash
# Get specific incident
"get incident INC0010023"
"show me INC0010045 with details"

# Search incidents
"find all critical incidents"
"incidents assigned to network team"
"open incidents from last week"
```

### Change Management
```bash
# Change requests
"get change CHG0030045"
"changes scheduled for this weekend"
"emergency changes in progress"
```

### Problem Management
```bash
# Problem records
"find problems related to email service"
"problems created this month"
"known errors affecting production"
```

### ITSM Analytics
```bash
# Metrics and reporting
"incident volume by priority"
"average resolution time for P1 incidents"
"change success rate this quarter"
```

## A2A Protocol

### Task Processing Endpoint
**POST** `/a2a`

```json
{
  "jsonrpc": "2.0",
  "method": "process_task",
  "params": {
    "task": {
      "instruction": "find all critical incidents assigned to network team"
    }
  },
  "id": "req-123"
}
```

### Agent Card Endpoint
**GET** `/a2a/agent-card`

```json
{
  "name": "ServiceNow Agent",
  "version": "1.0.0",
  "description": "ServiceNow ITSM operations with 15 specialized tools",
  "capabilities": [
    "incident_management", "change_management", "problem_management",
    "task_management", "user_lookup", "cmdb_operations"
  ]
}
```

## Glide Query Building

### Natural Language Processing
The agent converts natural language to GlideRecord queries:
- "critical incidents" → `priority=1^incident_state!=6`
- "assigned to me" → `assigned_to=javascript:gs.getUserID()`
- "created this week" → `sys_created_on>=javascript:gs.beginningOfThisWeek()`
- "high priority changes" → `priority=2^type=normal`

### Advanced Query Examples
```javascript
// Multi-criteria search
priority=1^state!=6^assignment_group.name=Network Team

// Time-based queries
sys_created_on>=javascript:gs.beginningOfLastWeek()^sys_created_on<=javascript:gs.endOfLastWeek()

// Related record queries
caller_id.department.name=IT^priority<=2

// Change calendar queries
start_date>=javascript:gs.beginningOfThisWeek()^start_date<=javascript:gs.endOfThisWeek()
```

## ITSM Table Relationships

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                         SERVICENOW TABLE STRUCTURE                            │
│                                                                               │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐    │
│  │    Users        │    │   Incidents     │    │   Change Requests       │    │
│  │   sys_user      │ ←→ │   incident      │ ←→ │   change_request        │    │
│  │                 │    │                 │    │                         │    │
│  └─────────────────┘    └─────────────────┘    └─────────────────────────┘    │
│           │                       │                        │                  │
│           ▼                       ▼                        ▼                  │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐    │
│  │ Assignment      │    │    Problems     │    │       Tasks             │    │
│  │   Groups        │ ←→ │   problem       │ ←→ │       task              │    │
│  │                 │    │                 │    │                         │    │
│  └─────────────────┘    └─────────────────┘    └─────────────────────────┘    │
│           │                       │                        │                  │
│           ▼                       ▼                        ▼                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                          CMDB (Configuration Items)                     │  │
│  │                                                                         │  │
│  │  • Servers • Applications • Databases • Network Equipment               │  │
│  │  • Service Dependencies • Change Impact Analysis                        │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────────┘
```

## Security Features

### Input Validation
- GlideRecord injection prevention through parameterization
- User and group permission validation
- Field validation against ServiceNow schema

### Error Handling
- Structured error responses
- No sensitive data in error messages
- Comprehensive audit logging

## Development

### Running the Agent
```bash
# Standalone
python3 servicenow_agent.py [-d|--debug] [--port 8003]

# Full system
python3 start_system.py
```

### Testing Connectivity
```bash
# Health check
curl http://localhost:8003/a2a/agent-card

# Search test
curl -X POST http://localhost:8003/a2a \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"process_task","params":{"task":{"instruction":"test connection"}},"id":"1"}'
```

### Adding New Functionality
1. Create new tool in `servicenow_tools.py`
2. Follow the existing pattern (Get/Create/Update)
3. Add Glide query building support
4. Register tool in `ALL_SERVICENOW_TOOLS`

## Common Patterns

### Table Auto-Detection
```python
# Agent automatically detects table from record number
"INC0010023" → incident table
"CHG0030045" → change_request table
"PRB0020067" → problem table
"TASK0040089" → task table
```

### State Mappings
```python
# Human-readable to ServiceNow values
"open" → "1"
"in progress" → "2" 
"resolved" → "6"
"closed" → "7"
```

### Priority/Urgency Logic
```python
# Auto-calculation based on business rules
urgency=1 + impact=1 → priority=1 (Critical)
urgency=2 + impact=2 → priority=3 (Moderate)
```

## Troubleshooting

### Common Issues
- **401 Unauthorized**: Check username and password
- **403 Forbidden**: Verify user has required ServiceNow roles
- **Agent not responding**: Check port 8003 availability

### Debug Logging
Enable with `-d` flag for detailed logs:
- Glide queries and results
- API request/response details
- Tool execution traces