```
███████╗ █████╗ ██╗     ███████╗███████╗███████╗ ██████╗ ██████╗  ██████╗███████╗
██╔════╝██╔══██╗██║     ██╔════╝██╔════╝██╔════╝██╔═══██╗██╔══██╗██╔════╝██╔════╝
███████╗███████║██║     █████╗  ███████╗█████╗  ██║   ██║██████╔╝██║     █████╗  
╚════██║██╔══██║██║     ██╔══╝  ╚════██║██╔══╝  ██║   ██║██╔══██╗██║     ██╔══╝  
███████║██║  ██║███████╗███████╗███████║██║     ╚██████╔╝██║  ██║╚██████╗███████╗
╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝╚══════╝

 █████╗  ██████╗ ███████╗███╗   ██╗████████╗
██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   
██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   
██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   
╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   
```

<div align="center">
  <h3>⚡ Enterprise CRM Automation with AI Intelligence ⚡</h3>
  
  [![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
  [![LangGraph](https://img.shields.io/badge/LangGraph-0.2.69-green.svg)](https://github.com/langchain-ai/langgraph)
  [![Salesforce API](https://img.shields.io/badge/Salesforce-REST%20API-orange.svg)](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/)
  [![A2A Protocol](https://img.shields.io/badge/A2A%20Protocol-JSON--RPC%202.0-purple.svg)](https://github.com/google-a2a/A2A)
</div>

---

# Salesforce Agent

Specialized AI agent for Salesforce CRM operations via A2A protocol.

## Quick Start

```bash
# Set environment variables
export SFDC_USER="your@email.com"
export SFDC_PASS="your-password"  
export SFDC_TOKEN="your-security-token"

# Run agent
python3 salesforce_agent.py [-d|--debug] [--port 8001]
```

## Tools (6 Unified Tools)

- **SalesforceGet**: Retrieve records by ID
- **SalesforceSearch**: Natural language search  
- **SalesforceCreate**: Create any object type
- **SalesforceUpdate**: Update records
- **SalesforceSOSL**: Cross-object search
- **SalesforceAnalytics**: Metrics and aggregations

## Examples

```bash
# Basic retrieval
"get account 001XX000ABC123"
"find the Acme Corp account"

# Analytics
"pipeline breakdown by stage"
"revenue by owner this quarter"

# Cross-object search
"find everything for john@acme.com"
```

## A2A Endpoints

- **POST** `/a2a` - Task processing (JSON-RPC 2.0)
- **GET** `/a2a/agent-card` - Agent capabilities

## Files

- `main.py` - LangGraph agent implementation
- `../tools/salesforce_unified.py` - 6 unified tools
- `../tools/salesforce_base.py` - Base tool classes

See `/docs/components/salesforce-agent.md` for complete documentation.