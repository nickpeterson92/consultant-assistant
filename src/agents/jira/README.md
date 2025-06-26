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
</div>

---

# Jira Agent

Specialized AI agent for Jira issue tracking and project management via A2A protocol.

## Quick Start

```bash
# Set environment variables
export JIRA_BASE_URL="https://company.atlassian.net"
export JIRA_USER="your@email.com"
export JIRA_API_TOKEN="your-api-token"

# Run agent
python3 jira_agent.py [-d|--debug] [--port 8002]
```

## Tools (6 Unified Tools)

- **JiraGet**: Retrieve issues by key
- **JiraSearch**: JQL and natural language search
- **JiraCreate**: Create issues and subtasks
- **JiraUpdate**: Update fields and transitions
- **JiraCollaboration**: Comments, links, attachments
- **JiraAnalytics**: Project metrics and reporting

## Examples

```bash
# Issue management
"get issue PROJ-123"
"find open bugs in MOBILE project"
"assign PROJ-456 to john.smith"

# Analytics
"current sprint progress"
"velocity for last 5 sprints"
"my team's workload"
```

## A2A Endpoints

- **POST** `/a2a` - Task processing (JSON-RPC 2.0)
- **GET** `/a2a/agent-card` - Agent capabilities

## Files

- `main.py` - LangGraph agent implementation
- `../tools/jira_unified.py` - 6 unified tools
- `../tools/jira_base.py` - Base tool classes

See `/docs/components/jira-agent.md` for complete documentation.