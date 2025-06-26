# ServiceNow Agent

A specialized LangGraph agent for ServiceNow IT Service Management (ITSM) operations.

## Overview

The ServiceNow Agent provides natural language interfaces to ServiceNow's core ITSM functionality, enabling users to manage incidents, changes, problems, tasks, and CMDB items through conversational interactions.

## Features

### 15 Specialized Tools

#### Incident Management (3 tools)
- **GetIncidentTool**: Search and retrieve incidents by number, description, caller, or assignment group
- **CreateIncidentTool**: Create new incidents with automatic priority and urgency mapping
- **UpdateIncidentTool**: Update incident state, assignment, priority, and other fields

#### Change Request Management (3 tools)
- **GetChangeRequestTool**: Search change requests by number, type, state, or assignment group
- **CreateChangeRequestTool**: Create change requests with risk assessment and approval routing
- **UpdateChangeRequestTool**: Update change state, implementation details, and approvals

#### Problem Management (3 tools)
- **GetProblemTool**: Search problems by number, description, or assignment group
- **CreateProblemTool**: Create problem records for root cause analysis
- **UpdateProblemTool**: Update problem state, workarounds, and resolution details

#### Task Management (3 tools)
- **GetTaskTool**: Search generic tasks by number, description, or assignment
- **CreateTaskTool**: Create new tasks with proper categorization
- **UpdateTaskTool**: Update task state, assignment, and completion details

#### User & CMDB Tools (3 tools)
- **GetUserTool**: Look up users by name, email, or employee ID
- **GetCMDBItemTool**: Retrieve configuration items by name, class, or attributes
- **SearchServiceNowTool**: Global search across multiple ServiceNow tables

### Key Capabilities

- **Natural Language Processing**: Understands queries like "show me critical incidents from last week"
- **Glide Query Builder**: Secure, composable query construction preventing injection attacks
- **Smart Field Mapping**: Automatically maps human-readable values to ServiceNow field values
- **A2A Protocol Integration**: Seamless communication with the orchestrator
- **Structured Logging**: Multi-file logging with component separation
- **Memory Support**: Stores and recalls important ITSM records

## Architecture

```
ServiceNow Agent
├── Entry Point (servicenow_agent.py)
├── LangGraph Agent (main.py)
│   ├── State Management
│   ├── Tool Execution
│   └── A2A Integration
├── ServiceNow Tools (servicenow_tools.py)
│   ├── ServiceNowClient (API wrapper)
│   └── 15 Specialized Tools
└── GlideQueryBuilder (glide_query_builder.py)
    ├── Query Templates
    ├── Operator Support
    └── Security Features
```

## Configuration

Required environment variables:
```bash
# ServiceNow Instance Configuration
SNOW_INSTANCE=your-instance.service-now.com
SNOW_USER=your-username
SNOW_PASS=your-password
```

## Usage Examples

### Natural Language Queries
```
"get incident INC0010023"
"show me all critical incidents assigned to the network team"
"create a high priority incident for database outage"
"update change CHG0030045 to implement state"
"find all problems related to email service"
```

### Tool Selection Guide
The agent automatically selects the appropriate tool based on:
- Entity type mentioned (incident, change, problem, task, user, CI)
- Action verb (get, create, update, search, find)
- Field references (priority, state, assignment group)

## Security Features

- **Query Injection Prevention**: All queries built through GlideQueryBuilder
- **Input Sanitization**: Automatic escaping of special characters
- **API Authentication**: Secure HTTP Basic Auth with ServiceNow
- **Field Validation**: Ensures only valid fields are queried/updated

## Integration with Orchestrator

The ServiceNow agent integrates with the orchestrator through:
1. A2A protocol for task delegation
2. Standardized response format
3. Memory extraction for important records
4. Natural language understanding shared with other agents

## Performance Considerations

- **Field Selection**: Only retrieves necessary fields to minimize payload
- **Query Optimization**: Uses indexed fields when possible
- **Connection Pooling**: Reuses HTTP connections for efficiency
- **Result Limiting**: Default limits prevent overwhelming responses

## Common Patterns

### Creating Incidents from Monitoring Alerts
```python
"create incident: CPU usage critical on PROD-WEB-01, affecting online store"
```

### Change Request Workflow
```python
"get change requests scheduled for this weekend"
"update CHG0030045 to review state with notes about testing completion"
```

### Problem Investigation
```python
"find all problems related to recurring login failures"
"create problem for investigating daily 3am performance degradation"
```

## Troubleshooting

### Common Issues

1. **Authentication Failures**
   - Verify SNOW_USER and SNOW_PASS are correct
   - Check if user has necessary ServiceNow roles

2. **Query Errors**
   - Review generated Glide queries in logs
   - Ensure field names match ServiceNow schema

3. **Connection Issues**
   - Verify SNOW_INSTANCE URL is accessible
   - Check network connectivity and firewall rules

## Future Enhancements

- Workflow automation support
- Service Catalog integration
- Advanced analytics and reporting
- Change Advisory Board (CAB) automation
- Incident correlation and pattern detection