```
     ██╗██╗██████╗  █████╗      █████╗  ██████╗ ███████╗███╗   ██╗████████╗
     ██║██║██╔══██╗██╔══██╗    ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
     ██║██║██████╔╝███████║    ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   
██   ██║██║██╔══██╗██╔══██║    ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   
╚█████╔╝██║██║  ██║██║  ██║    ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   
 ╚════╝ ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝    ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   
```

<div align="center">
  <h3>🎯 Agile Project Management with AI-Powered Automation 🎯</h3>
  
  [![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
  [![LangGraph](https://img.shields.io/badge/LangGraph-0.2.69-green.svg)](https://github.com/langchain-ai/langgraph)
  [![Jira API](https://img.shields.io/badge/Jira-REST%20API%20v3-blue.svg)](https://developer.atlassian.com/cloud/jira/platform/rest/v3/)
  [![A2A Protocol](https://img.shields.io/badge/A2A%20Protocol-JSON--RPC%202.0-purple.svg)](https://github.com/google-a2a/A2A)
  
  <p><em>A specialized AI agent implementing Google's Agent-to-Agent (A2A) protocol for comprehensive Jira project management automation. Features 15 enterprise-grade tools covering issue tracking, agile workflows, sprint management, and project analytics with advanced JQL support and intelligent query optimization.</em></p>
</div>

---

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Tool Catalog](#tool-catalog)
- [Advanced JQL & Analytics](#advanced-jql--analytics)
- [Usage Examples](#usage-examples)
- [Security Features](#security-features)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Performance Optimization](#performance-optimization)
- [Development Guide](#development-guide)

## Overview

The Jira Agent is a domain-specific AI agent that provides comprehensive project management automation through:

- **15 Enterprise Tools**: Complete issue lifecycle management with advanced agile workflows
- **JQL Query Builder**: Secure, composable query construction with automatic injection prevention
- **Advanced Analytics**: Sprint velocity, burndown charts, epic tracking, and project insights
- **A2A Protocol**: Standards-compliant agent communication with the orchestrator
- **LangGraph Integration**: State-aware conversation flows with built-in memory
- **Security-First Design**: Input validation, parameterized queries, and audit logging

### Why a Specialized Jira Agent?

1. **Domain Expertise**: Deep knowledge of Jira workflows, issue types, and agile methodologies
2. **Security Focus**: Built-in JQL injection prevention and input validation
3. **Performance Optimization**: Intelligent query batching and result caching
4. **Flexible Search**: Natural language to JQL translation with context awareness
5. **Agile Analytics**: Sprint metrics, velocity calculations, and burndown analysis

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
│  │                        TOOL EXECUTION LAYER                         │   │
│  │                                                                     │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │   │
│  │  │  Issue Tools    │  │  Sprint Tools   │  │  Analytics Tools    │  │   │
│  │  │  (10 tools)     │  │  (3 tools)      │  │  (2 tools)          │  │   │
│  │  │ CRUD + Workflow │  │  Agile Mgmt     │  │  Project Insights   │  │   │
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

### Core Components

#### 1. **A2A Protocol Handler** (`main.py`)
Standards-compliant implementation of Google's Agent2Agent protocol:
- JSON-RPC 2.0 message handling
- Task processing with state management  
- Error handling and response formatting
- Health check endpoint (`/a2a/agent-card`)

#### 2. **Tool Execution Engine** (`jira_tools.py`)
Comprehensive tool suite with enterprise patterns:
- 10 issue management tools for complete lifecycle control
- 3 sprint management tools for agile workflows
- 2 advanced analytics tools for project insights
- Consistent error handling and structured logging

#### 3. **JQL Query Engine**
Intelligent query construction and optimization:
- Natural language to JQL translation
- Automatic injection prevention
- Context-aware query building
- Result formatting and aggregation

## Tool Catalog

### Issue Management (10 Tools)

#### Core Issue Operations
- **SearchJiraIssuesTool**: `SEARCH` - Advanced JQL search with natural language support
- **GetJiraIssueTool**: `LOOKUP` - Individual issue retrieval with full details
- **CreateJiraIssueTool**: `CREATE` - Issue creation with field validation
- **UpdateJiraIssueTool**: `UPDATE` - Issue field updates with change tracking
- **AddJiraCommentTool**: `COMMENT` - Comment addition with formatting support

#### Workflow & Organization  
- **TransitionIssueTool**: `WORKFLOW` - Issue state transitions with validation
- **AssignIssueTool**: `ASSIGN` - Issue assignment with user validation
- **CreateSubtaskTool**: `CREATE` - Subtask creation with parent linking
- **LinkIssuesTool**: `LINK` - Issue relationship management

#### Advanced Operations
- **GetIssueHistoryTool**: `AUDIT` - Complete issue change history
- **AddAttachmentTool**: `ATTACH` - File attachment support
- **GetProjectIssuesTool**: `PROJECT` - Project-wide issue retrieval
- **GetMyIssuesTool**: `PERSONAL` - Current user's assigned issues
- **GetEpicIssuesTool**: `EPIC` - Epic hierarchy and child issues

### Sprint Management (3 Tools)

#### **GetSprintIssuesTool** - `SPRINT`
Active sprint tracking and burndown analysis
```python
# Use cases:
"current sprint for project ABC"
"sprint burndown data"
"velocity calculations"
```

#### **GetProjectBacklogTool** - `BACKLOG`
Backlog management and prioritization
```python
# Features:
- Unassigned issue tracking
- Priority-based sorting
- Epic grouping
- Estimation rollup
```

#### **GetSprintMetricsTool** - `ANALYTICS`
Sprint performance and team velocity
```python
# Metrics:
- Story points completed
- Velocity trends
- Burndown charts
- Sprint health indicators
```

## Advanced JQL & Analytics

### 1. Complex JQL Search Examples

#### Multi-Criteria Issue Search
```bash
USER: Find all high priority bugs in the IM project that are unassigned and created this week
ASSISTANT: Found 3 high priority unassigned bugs created this week:

| Key    | Summary                          | Priority | Created    | Reporter      |
|--------|----------------------------------|----------|------------|---------------|
| IM-234 | Login authentication fails       | High     | 2 days ago | Sarah Chen    |
| IM-237 | Data export crashes on large sets| High     | Yesterday  | Mike Johnson  |
| IM-241 | API timeout on bulk operations   | High     | Today      | Lisa Park     |
```
**JQL Generated:**
```jql
project = IM AND issuetype = Bug AND priority = High 
AND assignee is EMPTY AND created >= startOfWeek()
ORDER BY created DESC
```

#### Sprint Progress Analysis
```bash
USER: Show me the current sprint progress for the CLOUD project
ASSISTANT: **CLOUD Project - Sprint 23 Progress**

**Sprint Overview:**
- Sprint Name: CLOUD Sprint 23
- Start Date: Oct 14, 2024
- End Date: Oct 28, 2024
- Days Remaining: 5

**Progress Metrics:**
- Total Issues: 24
- Completed: 15 (62.5%)
- In Progress: 6 (25%)
- To Do: 3 (12.5%)

**Story Points:**
- Total Committed: 89 points
- Completed: 56 points (62.9%)
- Remaining: 33 points

**Key Issues In Progress:**
1. CLOUD-456: Implement OAuth2 authentication (8 points)
2. CLOUD-461: Database migration script (5 points)
3. CLOUD-463: Performance optimization (13 points)
```
**JQL Generated:**
```jql
project = CLOUD AND sprint in openSprints() 
ORDER BY status ASC, priority DESC
```

### 2. Epic and Feature Tracking

#### Epic Hierarchy Analysis
```bash
USER: Show me all epics in the PLATFORM project with their child issues
ASSISTANT: **PLATFORM Project Epic Overview**

**Epic: User Management System (PLATFORM-100)**
- Status: In Progress
- Progress: 65% complete (13/20 stories)
- Story Points: 120 total, 78 completed

Child Issues:
- ✅ PLATFORM-101: User registration flow (8 pts)
- ✅ PLATFORM-102: Password reset functionality (5 pts)
- 🔄 PLATFORM-103: Role-based permissions (13 pts)
- ⏸️ PLATFORM-104: SSO integration (21 pts)

**Epic: API Gateway (PLATFORM-200)**
- Status: To Do
- Progress: 0% complete (0/15 stories)
- Story Points: 89 total

**Epic: Monitoring Dashboard (PLATFORM-300)**
- Status: Done
- Progress: 100% complete (18/18 stories)
- Story Points: 144 completed
```
**JQL with Hierarchy:**
```jql
project = PLATFORM AND issuetype = Epic
UNION
"Epic Link" in (PLATFORM-100, PLATFORM-200, PLATFORM-300)
ORDER BY "Epic Link", status
```

### 3. Team Performance Analytics

#### Developer Workload Analysis
```bash
USER: Show me workload distribution for my development team
ASSISTANT: **Development Team Workload Analysis**

**Current Sprint Assignments:**

**Sarah Chen**
- 4 issues assigned (21 story points)
- 2 in progress, 2 to do
- Capacity: 85% utilized

**Mike Johnson**
- 3 issues assigned (13 story points)
- 3 in progress, 0 to do
- Capacity: 54% utilized

**Lisa Park**
- 5 issues assigned (18 story points)
- 1 in progress, 4 to do
- Capacity: 75% utilized

**David Kim**
- 2 issues assigned (8 story points)
- 1 in progress, 1 to do
- Capacity: 33% utilized

**Unassigned in Sprint:** 3 issues (13 points)
```
**Multiple JQL Queries:**
```jql
assignee = "sarah.chen" AND sprint in openSprints()
assignee = "mike.johnson" AND sprint in openSprints()
-- Additional queries for each team member
```

### 4. Project Health Metrics

#### Bug Trend Analysis
```bash
USER: Analyze bug trends for the last 3 months
ASSISTANT: **3-Month Bug Trend Analysis**

**Monthly Breakdown:**
- **August 2024**: 45 created, 38 resolved (Net: +7)
- **September 2024**: 52 created, 49 resolved (Net: +3)
- **October 2024**: 31 created, 42 resolved (Net: -11)

**Severity Distribution:**
- Critical: 8 open (down from 15 last month)
- High: 24 open (down from 31 last month)
- Medium: 47 open (stable)
- Low: 36 open (up from 28 last month)

**Resolution Time:**
- Critical: Avg 1.2 days
- High: Avg 3.5 days
- Medium: Avg 8.7 days
- Low: Avg 15.3 days

**Top Bug Categories:**
1. UI/UX Issues (32%)
2. API Errors (28%)
3. Performance (21%)
4. Data Integrity (19%)
```

### 5. Agile Metrics and Reporting

#### Sprint Velocity Tracking
```bash
USER: Show velocity trends for the last 5 sprints
ASSISTANT: **5-Sprint Velocity Analysis**

**Sprint Velocity Trend:**
- Sprint 19: 67 points completed
- Sprint 20: 72 points completed ↑7%
- Sprint 21: 78 points completed ↑8%
- Sprint 22: 71 points completed ↓9%
- Sprint 23: 76 points (projected)

**Average Velocity:** 72.8 points/sprint
**Trend:** Stable with slight upward trajectory

**Commitment vs Completion:**
- Average Commitment: 82 points
- Average Completion: 72.8 points
- Completion Rate: 88.8%
```

## Security Features

### JQL Injection Prevention
```python
def sanitize_jql_value(value: str) -> str:
    """Sanitize user input for safe JQL queries"""
    # Escape special characters
    value = value.replace('"', '\\"')
    value = value.replace("'", "\\'")
    value = value.replace("\\", "\\\\")
    return f'"{value}"'
```

### Input Validation
- **Field Validation**: Allowed fields and values checked against Jira schema
- **User Verification**: Assignee validation before assignment
- **Project Access**: Permission checking for project operations
- **Transition Rules**: Workflow transition validation

### Audit & Compliance
- **Change Tracking**: All modifications logged with user and timestamp
- **Query Logging**: Complete JQL query history for analysis
- **Error Tracking**: Detailed error logs for troubleshooting
- **Performance Monitoring**: API call metrics and response times

## Configuration

### Environment Variables
```bash
# Jira Configuration (Required)
JIRA_URL=https://your-domain.atlassian.net
JIRA_USERNAME=your@email.com
JIRA_API_TOKEN=your-api-token

# Optional Agent Configuration
JIRA_AGENT_PORT=8002
JIRA_AGENT_HOST=localhost
DEBUG_MODE=true
MAX_RESULTS=100
```

### Agent Configuration (`agent_registry.json`)
```json
{
  "jira-agent": {
    "name": "jira-agent",
    "endpoint": "http://localhost:8002",
    "agent_card": {
      "name": "jira-agent",
      "version": "1.0.0",
      "description": "Specialized agent for Jira issue tracking and project management",
      "capabilities": [
        "jira_operations",
        "issue_management",
        "jql_search",
        "epic_tracking",
        "sprint_management",
        "agile_workflows",
        "project_analytics"
      ],
      "metadata": {
        "framework": "langgraph",
        "tools_count": 15
      }
    }
  }
}
```

## API Reference

### A2A Endpoints

#### POST /a2a
Main task processing endpoint implementing JSON-RPC 2.0 protocol.

**Request Format:**
```json
{
  "jsonrpc": "2.0",
  "method": "process_task",
  "params": {
    "task": {
      "instruction": "find all bugs in the IM project"
    }
  },
  "id": "unique-request-id"
}
```

**Response Format:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "response": "Found 3 bugs in the IM project...",
    "tool_results": [...],
    "metadata": {
      "issues_found": 3,
      "jql_query": "project = IM AND issuetype = Bug"
    }
  },
  "id": "unique-request-id"
}
```

#### GET /a2a/agent-card
Returns agent capabilities and health status.

**Response:**
```json
{
  "name": "Jira Agent",
  "description": "Enterprise project management automation with 15 specialized tools",
  "capabilities": [
    "Issue lifecycle management",
    "Advanced JQL search",
    "Sprint and backlog management",
    "Epic hierarchy tracking",
    "Agile metrics and analytics"
  ],
  "version": "1.0.0",
  "supported_issue_types": [
    "Bug", "Story", "Task", "Epic", "Sub-task"
  ]
}
```

## Performance Optimization

### Query Optimization Strategies

1. **JQL Optimization**: Use indexed fields (key, project, assignee) in WHERE clauses
2. **Pagination**: Automatic result pagination for large datasets
3. **Field Selection**: Only request necessary fields via `fields` parameter
4. **Batch Operations**: Combine multiple operations when possible
5. **Caching**: Smart caching of project metadata and user information

### Async Operations
```python
async def batch_get_issues(issue_keys: List[str]) -> List[dict]:
    """Efficiently fetch multiple issues in parallel"""
    tasks = [get_issue(key) for key in issue_keys]
    return await asyncio.gather(*tasks)
```

### Rate Limiting
- Respects Jira API rate limits
- Automatic retry with exponential backoff
- Request queuing during high load
- Metrics tracking for optimization

## Development Guide

### Adding New Tools

1. **Define Input Schema**:
```python
class NewJiraToolInput(BaseModel):
    project_key: str
    additional_params: Optional[dict] = None
```

2. **Implement Tool Class**:
```python
class NewJiraTool(BaseTool):
    name: str = "new_jira_tool"
    description: str = "CATEGORY: Tool purpose and usage"
    args_schema: type = NewJiraToolInput
    
    def _run(self, **kwargs) -> dict:
        # Implementation
        return results
```

3. **Add to Tool List**: Update `get_tools()` in `jira_tools.py`

4. **Test Coverage**: Write comprehensive tests

5. **Documentation**: Update README with examples

### Testing Strategy

```python
# Unit test example
def test_search_issues():
    tool = SearchJiraIssuesTool()
    result = tool._run(
        jql_query="project = TEST AND status = Open"
    )
    assert isinstance(result, list)
    assert all("key" in issue for issue in result)
```

### Error Handling Patterns

```python
try:
    response = jira_client.search_issues(jql_query)
    return format_results(response)
except JIRAError as e:
    logger.error("jira_api_error", 
        operation="search_issues",
        error=str(e),
        jql=jql_query
    )
    return {"error": "Failed to search issues", "details": str(e)}
```

## Contributing

### Development Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Configure Jira credentials in `.env`
3. Run tests: `python -m pytest tests/`
4. Start agent: `python jira_agent.py -d`

### Code Standards
- Follow PEP 8 with 100-character line limit
- Use type hints for all functions
- Write descriptive docstrings
- Include usage examples in comments
- Maintain security-first approach

### Pull Request Process
1. Create feature branch from main
2. Implement with comprehensive tests
3. Update documentation
4. Submit PR with clear description
5. Address review feedback

---

## Support & Resources

- **Issue Tracking**: GitHub Issues for bugs and features
- **Documentation**: Comprehensive API and usage examples
- **Security**: JQL injection prevention and validation
- **Performance**: Query optimization and caching strategies

The Jira Agent represents enterprise-grade project management automation, combining AI capabilities with robust security and performance optimization for production-ready Atlassian Jira integration.