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
  [![ServiceNow API](https://img.shields.io/badge/ServiceNow-REST%20API-red.svg)](https://developer.servicenow.com/dev.do)
  [![A2A Protocol](https://img.shields.io/badge/A2A%20Protocol-JSON--RPC%202.0-purple.svg)](https://github.com/google-a2a/A2A)
</div>

---

# ServiceNow Agent

Specialized AI agent for ServiceNow ITSM operations via A2A protocol.

## Quick Start

```bash
# Set environment variables
export SNOW_INSTANCE="company.service-now.com"
export SNOW_USER="your-username"
export SNOW_PASS="your-password"

# Run agent
python3 servicenow_agent.py [-d|--debug] [--port 8003]
```

## Tools (15 Specialized Tools)

### Incident Management (3 tools)
- **GetIncidentTool**: Search and retrieve incidents
- **CreateIncidentTool**: Create new incidents  
- **UpdateIncidentTool**: Update incident fields

### Change Management (3 tools)
- **GetChangeRequestTool**: Search change requests
- **CreateChangeRequestTool**: Create change requests
- **UpdateChangeRequestTool**: Update change details

### Problem Management (3 tools)
- **GetProblemTool**: Search problem records
- **CreateProblemTool**: Create problem records
- **UpdateProblemTool**: Update problem details

### Task Management (3 tools)
- **GetTaskTool**: Search generic tasks
- **CreateTaskTool**: Create new tasks
- **UpdateTaskTool**: Update task information

### User & CMDB (3 tools)
- **GetUserTool**: Look up users by name/email
- **GetCMDBItemTool**: Retrieve configuration items
- **SearchServiceNowTool**: Global search across tables

## Examples

```bash
# Incident management
"get incident INC0010023"
"create critical incident for database outage"
"find incidents assigned to network team"

# Change management
"get change CHG0030045"
"changes scheduled for this weekend"

# Problem management
"find problems related to email service"
"create problem for recurring login failures"

# Analytics
"incident volume by priority this month"
"average resolution time for P1 incidents"
```

## A2A Endpoints

- **POST** `/a2a` - Task processing (JSON-RPC 2.0)
- **GET** `/a2a/agent-card` - Agent capabilities

## Files

- `main.py` - LangGraph agent implementation
- `../tools/servicenow_tools.py` - 15 specialized tools
- `../utils/glide_query_builder.py` - Query builder with injection prevention

## Query Features

- **Natural Language**: "critical incidents from last week"
- **Glide Queries**: `priority=1^state!=6^sys_created_on>=javascript:gs.beginningOfLastWeek()`
- **Smart Mapping**: "high priority" → `priority=2`
- **Security**: Automatic input sanitization and validation

See `/docs/components/servicenow-agent.md` for complete documentation.