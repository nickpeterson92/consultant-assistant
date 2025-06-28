# Jira Agent

Specialized AI agent for Jira issue tracking and project management via A2A protocol.

## Overview

The Jira agent provides comprehensive project management automation through 6 unified tools that handle issue lifecycle, JQL queries, and agile workflows with natural language processing.

## Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              JIRA AGENT                                    │
│  ┌──────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐    │
│  │   A2A Handler    │  │   LangGraph     │  │   Security Layer        │    │
│  │   JSON-RPC 2.0   │  │   State Mgmt    │  │   Input Validation      │    │
│  │   (/a2a endpoint)│  │   Memory        │  │   JQL Injection Prev    │    │
│  └──────────────────┘  └─────────────────┘  └─────────────────────────┘    │
│                                   │                                        │
│  ┌────────────────────────────────┴────────────────────────────────────┐   │
│  │                      UNIFIED TOOL EXECUTION LAYER                   │   │
│  │                                                                     │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │   │
│  │  │    JiraGet      │  │   JiraSearch    │  │    JiraCreate       │  │   │
│  │  │ Issue by Key    │  │  JQL & Natural  │  │ Issues & Subtasks   │  │   │
│  │  │ Full Context    │  │   Language      │  │ Field Validation    │  │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │   │
│  │                                                                     │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │   │
│  │  │   JiraUpdate    │  │JiraCollaboration│  │   JiraAnalytics     │  │   │
│  │  │ Fields & Trans  │  │Comments, Links  │  │ Project Metrics     │  │   │
│  │  │ Workflow Mgmt   │  │  Attachments    │  │ Sprint Analysis     │  │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                        │
│  ┌────────────────────────────────┴────────────────────────────────────┐   │
│  │                         JQL QUERY ENGINE                            │   │
│  │                                                                     │   │
│  │  • Natural Language Processing  • Query Optimization  • Security    │   │
│  │  • Context-Aware Translation   • Result Formatting   • Caching      │   │
│  │  • Advanced JQL Functions      • Bulk Operations    • Error Handle  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                        │
│  ┌────────────────────────────────┴────────────────────────────────────┐   │
│  │                          JIRA API LAYER                             │   │
│  │                                                                     │   │
│  │  • REST API v3 Integration                                          │   │
│  │  • Async Request Handling                                           │   │
│  │  • Rate Limiting & Retries                                          │   │
│  │  • Webhook Support                                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
```

## Issue Lifecycle Flow

```
Issue Creation → Development → Testing → Deployment → Closure
     │               │           │           │          │
     ▼               ▼           ▼           ▼          ▼
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌────────┐   ┌────────┐
│   Open   │ → │In Progress│ → │  Review  │ → │ Deploy │ → │ Closed │
│          │   │          │   │          │   │        │   │        │
│ JiraCreate   │JiraUpdate│   │JiraCollab│   │JiraUpdt│   │JiraUpdt│
│          │   │(assign)  │   │(comment) │   │(deploy)│   │(close) │
└──────────┘   └──────────┘   └──────────┘   └────────┘   └────────┘

Natural Language Examples:
"create bug for login issue"     → JiraCreate
"assign PROJ-123 to john.smith"  → JiraUpdate  
"add comment to PROJ-456"        → JiraCollaboration
"move PROJ-789 to done"          → JiraUpdate (transition)
```

**Files:**
- **Entry**: `jira_agent.py` → `src/agents/jira/main.py`
- **Tools**: `src/tools/jira_unified.py`
- **Base Classes**: `src/tools/jira_base.py`

## Tools

### Core Operations

#### JiraGet
```python
# Get issue by key with full context
jira_get(issue_key="PROJ-123")
jira_get(issue_key="PROJ-456", include_comments=False)
```

#### JiraSearch
```python
# JQL and natural language search
jira_search(jql="project = PROJ AND status = Open")
jira_search(
    query="high priority bugs assigned to john",
    project="PROJ"
)
```

#### JiraCreate
```python
# Create issues and subtasks
jira_create(
    project="PROJ",
    issue_type="Bug",
    summary="Login fails on mobile",
    description="Users cannot log in on mobile app",
    priority="High"
)
```

#### JiraUpdate
```python
# Update issue fields and transitions
jira_update(
    issue_key="PROJ-123",
    fields={"status": "In Progress", "assignee": "john.smith"}
)
```

#### JiraCollaboration
```python
# Comments, links, and attachments
jira_collaboration(
    issue_key="PROJ-123",
    action="add_comment",
    content="Updated implementation approach"
)
```

#### JiraAnalytics
```python
# Project metrics and reporting
jira_analytics(
    project="PROJ",
    metric_type="velocity",
    time_period="last_5_sprints"
)
```

## Configuration

### Environment Variables
```bash
# Required
JIRA_BASE_URL=https://company.atlassian.net
JIRA_USER=your@email.com
JIRA_API_TOKEN=your-api-token

# Optional
JIRA_AGENT_PORT=8002
DEBUG_MODE=true
```

### Agent Registry Entry
```json
{
  "jira": {
    "host": "localhost",
    "port": 8002,
    "capabilities": [
      "jira_get", "jira_search", "jira_create",
      "jira_update", "jira_collaboration", "jira_analytics"
    ]
  }
}
```

## Usage Examples

### Issue Management
```bash
# Get specific issue
"get issue PROJ-123"
"show me PROJ-456 with comments"

# Search issues
"find all open bugs in PROJ"
"high priority issues assigned to me"
"stories in current sprint"
```

### Project Analytics
```bash
# Sprint metrics
"current sprint progress for PROJ"
"velocity for last 5 sprints"

# Team analysis  
"my team's workload distribution"
"bugs created vs resolved this month"
```

### Workflow Operations
```bash
# Issue updates
"assign PROJ-123 to john.smith"
"move PROJ-456 to in progress"
"add comment to PROJ-789: Fixed in latest build"
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
      "instruction": "find all open bugs in the MOBILE project"
    }
  },
  "id": "req-123"
}
```

### Agent Card Endpoint
**GET** `/a2a/agent-card`

```json
{
  "name": "Jira Agent",
  "version": "1.0.0",
  "description": "Jira issue tracking with unified tools",
  "capabilities": [
    "jira_get", "jira_search", "jira_create",
    "jira_update", "jira_collaboration", "jira_analytics"
  ]
}
```

## JQL Query Building

### Natural Language Processing
The agent converts natural language to JQL:
- "high priority bugs" → `priority = High AND issuetype = Bug`
- "assigned to me" → `assignee = currentUser()`
- "created this week" → `created >= startOfWeek()`
- "in current sprint" → `sprint in openSprints()`

### Advanced JQL Examples
```jql
# Multi-criteria search
project = PROJ AND status != Done AND assignee in membersOf("dev-team")

# Sprint analysis
project = PROJ AND sprint in openSprints() ORDER BY priority DESC

# Epic tracking
"Epic Link" = PROJ-100 AND status != Done

# Time-based queries
created >= startOfMonth() AND resolved >= startOfMonth()
```

## Sprint Analytics

```
Sprint Velocity Tracking:
┌─────────────────────────────────────────────────────────────────────────────┐
│                            SPRINT METRICS                                   │
│                                                                             │
│  Sprint 19  Sprint 20  Sprint 21  Sprint 22  Sprint 23                      │
│     67        72        78        71        76  (Story Points)              │
│     ██        ███       ████      ███       ███▌                            │
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐  │
│  │   Completed     │    │   In Progress   │    │    Planned              │  │
│  │   Story Points  │    │   Issues        │    │    for Next Sprint      │  │
│  │   Running Avg   │    │   Risk Analysis │    │    Capacity Planning    │  │
│  └─────────────────┘    └─────────────────┘    └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Security Features

### Input Validation
- JQL injection prevention through parameterization
- User and project permission validation
- Field validation against Jira schema

### Error Handling
- Structured error responses
- No sensitive data in error messages
- Comprehensive audit logging

## Development

### Running the Agent
```bash
# Standalone
python3 jira_agent.py [-d|--debug] [--port 8002]

# Full system
python3 start_system.py
```

### Testing Connectivity
```bash
# Health check
curl http://localhost:8002/a2a/agent-card

# Search test
curl -X POST http://localhost:8002/a2a \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"process_task","params":{"task":{"instruction":"list projects"}},"id":"1"}'
```

### Adding New Functionality
1. Extend unified tools in `jira_unified.py`
2. Add new methods to base classes in `jira_base.py`
3. Update agent capabilities in agent card
4. Test with various JQL patterns

## Common Patterns

### Issue Key Validation
```python
# Agent validates issue key format (PROJECT-NUMBER)
import re
issue_key_pattern = r'^[A-Z][A-Z0-9]*-\d+$'
```

### JQL Escaping
```python
# Automatic escaping for user input
def escape_jql_value(value: str) -> str:
    return value.replace('"', '\\"').replace("'", "\\'")
```

### Batch Operations
- Multiple issue retrieval in parallel
- Bulk field updates when supported
- Efficient comment and attachment handling

## Troubleshooting

### Common Issues
- **403 Forbidden**: Check API token permissions
- **Agent not responding**: Verify port 8002 availability
- **Invalid JQL**: Check field names and project permissions

### Debug Logging
Enable with `-d` flag for detailed logs:
- JQL queries and results
- API request/response details
- Tool execution traces