```
    ███╗██╗██████╗  █████╗      █████╗  ██████╗ ███████╗███╗   ██╗████████╗
    ╚═██║██║██╔══██╗██╔══██╗    ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
      ██║██║██████╔╝███████║    ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   
      ██║██║██╔══██╗██╔══██║    ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   
   ██████║██║██║  ██║██║  ██║    ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   
   ╚═══╝╚══╝╚═╝  ╚═╝╚═╝  ╚═╝    ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   
```

<div align="center">
  <h3>🎯 Enterprise Agile Project Management with AI Intelligence 🎯</h3>
  
  [![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
  [![LangGraph](https://img.shields.io/badge/LangGraph-0.2.69-green.svg)](https://github.com/langchain-ai/langgraph)
  [![Jira API](https://img.shields.io/badge/Jira-REST%20API%20v3-blue.svg)](https://developer.atlassian.com/cloud/jira/platform/rest/v3/)
  [![A2A Protocol](https://img.shields.io/badge/A2A%20Protocol-JSON--RPC%202.0-purple.svg)](https://github.com/google-a2a/A2A)
</div>

---

# Jira Agent

A specialized AI agent for Jira project management, implementing 11 comprehensive tools that provide complete issue tracking, agile workflow management, and project analytics capabilities.

## Architecture

The Jira agent is built on:
- **LangGraph**: State machine orchestration with tool calling
- **A2A Protocol**: JSON-RPC 2.0 for agent communication  
- **Unified Tools**: 11 tools covering all Jira operations
- **Smart Features**: JQL search, sprint management, project creation, resource discovery

```mermaid
flowchart TB
    %% Define styles
    classDef agentClass fill:#2196f3,stroke:#0d47a1,stroke-width:4px,color:#ffffff,font-weight:bold
    classDef handlerClass fill:#4caf50,stroke:#2e7d32,stroke-width:2px,color:#ffffff
    classDef toolClass fill:#ff9800,stroke:#e65100,stroke-width:2px,color:#ffffff
    classDef apiClass fill:#00bcd4,stroke:#006064,stroke-width:2px,color:#ffffff
    classDef securityClass fill:#f44336,stroke:#b71c1c,stroke-width:2px,color:#ffffff
    
    %% Main agent
    AGENT[📋 JIRA AGENT<br/>━━━━━━━━━━━━━<br/>11 Tools • JQL Search • Sprint Mgmt • Analytics]:::agentClass
    
    %% Top layer components
    subgraph handlers[" "]
        A2A[🌐 A2A Handler<br/>━━━━━━━━━━━━<br/>JSON-RPC 2.0<br/>/a2a endpoint]:::handlerClass
        LG[📊 LangGraph<br/>━━━━━━━━━━<br/>State Mgmt<br/>Memory]:::handlerClass
        SEC[🔒 Security Layer<br/>━━━━━━━━━━━━━━<br/>Input Validation<br/>JQL Query Building]:::securityClass
    end
    
    %% Unified tools layer
    subgraph tools["🛠️ UNIFIED TOOL EXECUTION LAYER"]
        subgraph row1[" "]
            GET[📥 JiraGet<br/>━━━━━━━━━<br/>Issue by Key<br/>Full Details]:::toolClass
            SEARCH[🔍 JiraSearch<br/>━━━━━━━━━━━<br/>JQL & Natural<br/>Language Search]:::toolClass
            CREATE[➕ JiraCreate<br/>━━━━━━━━━━━<br/>Issues & Subtasks<br/>All Issue Types]:::toolClass
        end
        
        subgraph row2[" "]
            UPDATE[✏️ JiraUpdate<br/>━━━━━━━━━━━<br/>Fields & Status<br/>Bulk Updates]:::toolClass
            COLLAB[💬 JiraCollaboration<br/>━━━━━━━━━━━━━━━━<br/>Comments & Links<br/>Team Features]:::toolClass
            ANALYTICS[📊 JiraAnalytics<br/>━━━━━━━━━━━━━<br/>History & Metrics<br/>Project Stats]:::toolClass
        end
        
        subgraph row3[" "]
            PROJ[🗂️ JiraProjectCreate<br/>━━━━━━━━━━━━━━━<br/>New Projects<br/>With Lead]:::toolClass
            GETRES[📄 JiraGetResource<br/>━━━━━━━━━━━━━━<br/>Get Any Resource<br/>Universal Getter]:::toolClass
            LISTRES[📋 JiraListResources<br/>━━━━━━━━━━━━━━━━<br/>List & Search<br/>Universal Listing]:::toolClass
        end
        
        subgraph row4[" "]
            UPDATERES[🔧 JiraUpdateResource<br/>━━━━━━━━━━━━━━━━━<br/>Update Any Resource<br/>Project/Board]:::toolClass
            SPRINT[🏃 JiraSprintOps<br/>━━━━━━━━━━━━━<br/>Sprint Management<br/>Full Lifecycle]:::toolClass
        end
    end
    
    %% API layer
    API[🌐 JIRA API LAYER<br/>━━━━━━━━━━━━━━<br/>REST API v3 Integration • Agile API Support<br/>User Account ID Handling • Rate Limiting<br/>JQL Query Processing • Pagination Support]:::apiClass
    
    %% Connections
    AGENT --> handlers
    A2A --> tools
    LG --> tools
    SEC --> tools
    
    GET --> API
    SEARCH --> API
    CREATE --> API
    UPDATE --> API
    COLLAB --> API
    ANALYTICS --> API
    PROJ --> API
    GETRES --> API
    LISTRES --> API
    UPDATERES --> API
    SPRINT --> API
    
    %% Style the subgraphs
    style handlers fill:rgba(33,150,243,0.1),stroke:#2196f3,stroke-width:2px
    style tools fill:rgba(255,152,0,0.1),stroke:#ff9800,stroke-width:2px,stroke-dasharray: 5 5
    style row1 fill:none,stroke:none
    style row2 fill:none,stroke:none
    style row3 fill:none,stroke:none
    style row4 fill:none,stroke:none
```

## Tools Overview

### 1. JiraGet
**Purpose**: Direct issue retrieval when you have the key
```python
# Get issue with all details
"get issue PROJ-123"
"get PROJ-456 with comments and attachments"
```

**Features**:
- Full issue details including description, status, assignee
- Optional comments and attachments inclusion
- Rendered fields for rich text content
- All issue relationships and links

### 2. JiraSearch  
**Purpose**: Search issues with JQL or natural language
```python
# Natural language
"find all bugs assigned to me"
"show high priority issues in current sprint"

# Direct JQL
"search with project = PROJ AND status = Open"
"find issues where assignee = currentUser() AND updated > -7d"
```

**Features**:
- Natural language to JQL conversion
- Direct JQL query support
- Field selection for performance
- Pagination for large result sets
- Default fields optimized for issue tracking

### 3. JiraCreate
**Purpose**: Create issues and subtasks
```python
"create bug in PROJ: Login button not working"
"create story in PROJ: Implement user authentication"
"create subtask under PROJ-123: Write unit tests"
```

**Features**:
- Support for all issue types (Bug, Story, Task, Epic, etc.)
- Subtask creation with parent linking
- Custom field support
- Label and component assignment
- Returns created issue with full details

**Important Note**: Assignee requires account ID, not username. Use `jira_list_resources` with `resource_type='users'` to find valid account IDs.

### 4. JiraUpdate
**Purpose**: Update issues including fields, status, and assignments
```python
# Update fields
"update PROJ-123 set priority to High"
"assign PROJ-456 to john.smith@company.com"

# Status transitions
"transition PROJ-789 to In Progress"
"resolve PROJ-101 with comment 'Fixed in version 2.0'"
```

**Features**:
- Field updates (summary, description, priority, etc.)
- Status transitions with available transition detection
- Assignment changes (requires account ID)
- Comment addition with updates
- Bulk field updates in single operation

**Important Note**: Assignee requires account ID. Use `jira_list_resources` to find users first.

### 5. JiraCollaboration
**Purpose**: Handle team collaboration features
```python
# Comments
"add comment to PROJ-123: Great work on this!"
"comment on PROJ-456 visible to developers group"

# Issue linking
"link PROJ-123 to PROJ-456 as blocks"
"link PROJ-789 relates to PROJ-101"
```

**Features**:
- Comment addition with optional visibility restrictions
- Issue linking with various relationship types
- Attachment support (via direct API)
- Group visibility for sensitive comments

### 6. JiraProjectCreate
**Purpose**: Create new Jira projects
```python
"create project KEY=NEWPROJ name='New Project' lead=john.smith@company.com"
"create software project TEAM with Scrum template"
```

**Features**:
- Project creation with required lead assignment
- Project type support (software, service_desk, business)
- Template selection for quick setup
- Description and metadata configuration

**Important Note**: Project lead is REQUIRED. Use `jira_list_resources` with `resource_type='users'` to find valid account IDs first.

### 7. JiraGetResource
**Purpose**: Get any non-issue Jira resource
```python
# Projects
"get project PROJ details"

# Users
"get user with account ID 5b109f2e9729b51b54dc274d"

# Boards and Sprints
"get board 123"
"get sprint 456"
```

**Features**:
- Universal getter for all resource types
- Supports: project, user, board, sprint, component, version
- Returns full resource details
- Handles different ID formats per resource type

### 8. JiraListResources
**Purpose**: List or search Jira resources
```python
# Projects
"list all projects"
"search projects containing 'mobile'"

# Users
"search users named john"
"list all active users"

# Boards and Sprints
"list boards for project PROJ"
"list sprints for board 123"
```

**Features**:
- Universal listing for all resource collections
- Search capability for projects and users
- Pagination support for large collections
- Formatted user results with account IDs
- Project-specific filtering for boards/components

### 9. JiraUpdateResource
**Purpose**: Update non-issue resources
```python
# Update project
"update project PROJ set description='Updated project description'"

# Update board
"update board 123 name='Sprint Board 2025'"

# Update version
"update version 456 set released=true"
```

**Features**:
- Updates for: project, board, sprint, component, version
- Different update patterns per resource type
- Returns updated resource details
- Validation of update fields

### 10. JiraSprintOperations
**Purpose**: Manage agile sprints
```python
# Sprint lifecycle
"create sprint 'Sprint 45' for board 123"
"start sprint 456"
"complete sprint 456"

# Sprint planning
"move issues PROJ-123,PROJ-456 to sprint 789"
```

**Features**:
- Sprint creation with board association
- Sprint lifecycle management (start/complete)
- Bulk issue movement between sprints
- Automatic date calculation for sprint duration
- Sprint state validation

### 11. JiraAnalytics
**Purpose**: Get analytics and metrics
```python
# Issue analytics
"get history for PROJ-123"
"show worklog for PROJ-456"

# Project metrics
"get project stats for PROJ"
"show PROJ metrics for last 30 days"
```

**Features**:
- Issue change history with full changelog
- Worklog tracking and time entries
- Project-level statistics
- Time period filtering
- JQL-based metric queries

## Configuration

### Environment Variables
```bash
# Required
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_USER=your@email.com
JIRA_API_TOKEN=your-api-token

# Azure OpenAI (Required)
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-4o-mini
AZURE_OPENAI_API_KEY=your-key
```

### A2A Configuration
- **Default Port**: 8002
- **Host**: 0.0.0.0 (configurable)
- **Protocol**: JSON-RPC 2.0
- **Endpoints**:
  - `POST /a2a` - Process tasks
  - `GET /a2a/agent-card` - Get capabilities

## Usage Examples

### Issue Management
```bash
# Get issue
"get PROJ-123"

# Search issues
"find all open bugs in PROJ"
"search for issues assigned to me in current sprint"
"list high priority issues updated this week"

# Create issue
"create bug in PROJ: Payment gateway timeout"

# Update issue
"update PROJ-123 priority to Critical"
"transition PROJ-456 to Done with comment 'Deployed to production'"
```

### Sprint Management
```bash
# Sprint operations
"create new sprint for board 123"
"start sprint 456"
"move PROJ-123 and PROJ-456 to sprint 789"
"complete sprint 456"

# Sprint queries
"list active sprints for board 123"
"show issues in sprint 456"
```

### Project Administration
```bash
# Project management
"create project KEY=MOBILE name='Mobile App' lead=jane.doe@company.com"
"update project MOBILE description"
"list all projects"

# User discovery
"search users named john"
"find user jane.doe@company.com"
"list all active users"
```

### Analytics & Reporting
```bash
# Issue metrics
"show history for PROJ-123"
"get worklog entries for PROJ-456"

# Project analytics
"project stats for PROJ"
"PROJ metrics for last quarter"
"count of issues by status in PROJ"
```

## Technical Details

### State Management
The agent uses LangGraph's state schema:
```python
class JiraAgentState(TypedDict):
    messages: Annotated[List[Any], operator.add]
    current_task: str
    tool_results: List[Dict[str, Any]]
    error: str
    task_context: Dict[str, Any]
    external_context: Dict[str, Any]
```

### JQL Support
The agent intelligently handles:
- Natural language to JQL conversion
- Direct JQL query validation
- Special character escaping
- Field name validation
- Time-based queries with relative dates

### User Management
Important considerations:
- Jira Cloud uses Account IDs, not usernames
- Always search users first to get valid account IDs
- Email addresses map to account IDs via user search
- Assignee fields require `{"accountId": "id"}` format

### API Integration
- Uses Jira REST API v3
- Handles both Jira Software and Jira Cloud
- Supports Agile API endpoints for sprint/board operations
- Automatic pagination for large result sets
- Rate limit aware with proper error handling

## Logging

Logs are written to `logs/jira.log` with structured JSON format:
```json
{
  "timestamp": "2025-07-23T10:30:00Z",
  "level": "INFO",
  "component": "jira",
  "tool_name": "jira_search",
  "operation": "jql_query",
  "query": "project = PROJ AND status = Open"
}
```

### Key Log Events
- `tool_call` - Tool invocation with arguments
- `tool_result` - Successful execution
- `tool_error` - Execution failures
- `jql_query` - Generated JQL queries
- `api_request` - Jira API calls

## Common Issues

### Account ID Confusion
Most common error - trying to use username instead of account ID:
```bash
# Wrong
"assign PROJ-123 to john.smith"

# Right - first find the user
"search users named john smith"
# Then use the returned accountId
"assign PROJ-123 to 5b109f2e9729b51b54dc274d"
```

### Permission Errors
Ensure your API token has permissions for:
- Browse projects
- Create issues
- Transition issues
- Administer projects (for project creation)

### JQL Syntax
The agent handles basic natural language, but complex queries need JQL:
```bash
# Natural language (basic)
"find my open bugs"

# JQL (complex)
"search with assignee = currentUser() AND issuetype = Bug AND status != Closed ORDER BY priority DESC"
```

### API Limits
- Search results default to 50 (configurable)
- Large result sets automatically paginated
- Changelog expansions can be large - use selectively

## Best Practices

1. **User Assignment**: Always search users first to get account IDs
2. **Specific Searches**: Use project keys and issue types for better results  
3. **Sprint Planning**: Create sprints before trying to move issues
4. **Field Updates**: Batch multiple field updates in single call
5. **JQL Queries**: Let the agent handle natural language when possible
6. **Comments**: Add comments during transitions for audit trail
7. **Error Handling**: Check tool results for partial successes

## Architecture Decisions

- **11 Comprehensive Tools**: Complete coverage of Jira operations
- **Account ID Focus**: Proper handling of Jira Cloud user model
- **JQL Intelligence**: Natural language with fallback to structured queries
- **Resource Flexibility**: Single tools for diverse resource types
- **Sprint Integration**: Full agile workflow support
- **Analytics Built-in**: Metrics without external reporting tools