# Salesforce Agent

Specialized AI agent for Salesforce CRM operations using the A2A protocol and unified tool architecture.

## Overview

The Salesforce agent provides comprehensive CRM automation through 6 unified tools that handle all major Salesforce objects with natural language processing and SOQL injection prevention.

## Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           SALESFORCE AGENT                                 │
│  ┌──────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐    │
│  │   A2A Handler    │  │   LangGraph     │  │   Security Layer        │    │
│  │   JSON-RPC 2.0   │  │   State Mgmt    │  │   Input Validation      │    │
│  │   (/a2a endpoint)│  │   Memory        │  │   SOQL Injection Prev   │    │
│  └──────────────────┘  └─────────────────┘  └─────────────────────────┘    │
│                                   │                                        │
│  ┌────────────────────────────────┴────────────────────────────────────┐   │
│  │                      UNIFIED TOOL EXECUTION LAYER                   │   │
│  │                                                                     │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │   │
│  │  │ SalesforceGet   │  │SalesforceSearch │  │ SalesforceCreate    │  │   │
│  │  │ Record by ID    │  │Natural Language │  │ Any Object Type     │  │   │
│  │  │ Auto-detection  │  │ & Structured    │  │ Field Validation    │  │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │   │
│  │                                                                     │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │   │
│  │  │SalesforceUpdate │  │ SalesforceSOSL  │  │SalesforceAnalytics  │  │   │
│  │  │ Any Record      │  │Cross-obj Search │  │ Metrics & Aggreg    │  │   │
│  │  │ By ID/Criteria  │  │ Global Results  │  │ Business Intel      │  │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                        │
│  ┌────────────────────────────────┴────────────────────────────────────┐   │
│  │                       SOQL QUERY BUILDER                            │   │
│  │                                                                     │   │
│  │  • Fluent Interface     • Aggregate Functions  • Security Features  │   │
│  │  • Query Templates      • Relationship Queries • Performance Opts   │   │
│  │  • SOSL Support        • Subquery Building    • Error Handling      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                        │
│  ┌────────────────────────────────┴────────────────────────────────────┐   │
│  │                        SALESFORCE API LAYER                         │   │
│  │                                                                     │   │
│  │  • REST API Integration                                             │   │
│  │  • Connection Management                                            │   │
│  │  • Rate Limiting & Retries                                          │   │
│  │  • Result Processing                                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
```

## Tool Flow Diagram

```
User Request → Tool Selection → SOQL Generation → Salesforce API → Response

Example: "get the Acme Corp account"
    │
    ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Natural Language│ →  │ SalesforceSearch │ →  │ SOQL Builder    │
│ "Acme Corp"     │    │ Tool Selected    │    │ WHERE Name LIKE │
└─────────────────┘    └──────────────────┘    └─────────────────┘
    │                           │                       │
    ▼                           ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Input Validation│ →  │ Query Execution  │ →  │ Result Process  │
│ Escape Chars    │    │ sf.query(soql)   │    │ Format & Return │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

**Files:**
- **Entry**: `salesforce_agent.py` → `src/agents/salesforce/main.py`
- **Tools**: `src/tools/salesforce_unified.py`
- **Base Classes**: `src/tools/salesforce_base.py`
- **Query Builder**: `src/utils/soql_query_builder.py`

## Tools

### Core CRUD Operations

#### SalesforceGet
```python
# Get any record by ID with auto-detection
salesforce_get(record_id="001XX000ABC123")
salesforce_get(record_id="003XX000DEF456", object_type="Contact")
```

#### SalesforceSearch  
```python
# Natural language or structured search
salesforce_search(
    object_type="Opportunity", 
    filter="Amount > 50000 AND StageName = 'Closed Won'"
)
salesforce_search(
    object_type="Lead",
    filter="leads created this week"
)
```

#### SalesforceCreate
```python
# Create any object type
salesforce_create(
    object_type="Lead",
    data={
        "FirstName": "John",
        "LastName": "Smith", 
        "Company": "Acme Corp",
        "Email": "john@acme.com"
    }
)
```

#### SalesforceUpdate
```python
# Update by ID or criteria
salesforce_update(
    object_type="Opportunity",
    record_id="006XX000123",
    data={"StageName": "[new_stage]", "Amount": 75000}
)
```

#### SalesforceSOSL
```python
# Cross-object search
salesforce_sosl(
    search_term="john@acme.com",
    object_types=["Account", "Contact", "Lead", "Opportunity"]
)
```

#### SalesforceAnalytics
```python
# Aggregations and metrics
salesforce_analytics(
    object_type="Opportunity",
    metrics=["COUNT(Id)", "SUM(Amount)", "AVG(Amount)"],
    group_by="StageName"
)
```

## Configuration

### Environment Variables
```bash
# Required
SFDC_USER=your@email.com
SFDC_PASS=your-password  
SFDC_TOKEN=your-security-token

# Optional
SALESFORCE_AGENT_PORT=8001
DEBUG_MODE=true
```

### Agent Registry Entry
```json
{
  "salesforce": {
    "host": "localhost",
    "port": 8001,
    "capabilities": [
      "salesforce_get", "salesforce_search", "salesforce_create",
      "salesforce_update", "salesforce_sosl", "salesforce_analytics"
    ]
  }
}
```

## Usage Examples

### Individual Record Retrieval
```bash
# By ID (auto-detects object type)
"get account 001XX000ABC123"

# By search criteria  
"find the Acme Corp account"
"get contact with email john@acme.com"
```

### Search Operations
```bash
# Natural language
"opportunities closed this quarter over $50k"
"leads created last week by Sarah Johnson"

# Structured queries
"accounts in technology industry with revenue > 10M"
"cases with high priority and open status"
```

### Analytics Queries
```bash
# Pipeline analysis
"show pipeline breakdown by stage"
"revenue by owner this quarter"

# Business metrics  
"lead conversion rates by source"
"top performing sales reps"
```

### Cross-Object Search
```bash
# Find everything related to entity
"find all records for john@acme.com"
"everything related to solar panel"
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
      "instruction": "get the Acme Corp account with all opportunities"
    }
  },
  "id": "req-123"
}
```

### Agent Card Endpoint  
**GET** `/a2a/agent-card`

```json
{
  "name": "Salesforce Agent",
  "version": "1.0.0", 
  "description": "Salesforce CRM operations with unified tools",
  "capabilities": [
    "salesforce_get", "salesforce_search", "salesforce_create",
    "salesforce_update", "salesforce_sosl", "salesforce_analytics"
  ]
}
```

## Security Features

### SOQL Injection Prevention
- Automatic parameter escaping
- Parameterized query construction
- Input validation with Pydantic models

### Error Handling
- Structured error responses
- No sensitive data in error messages
- Comprehensive logging for debugging

## Development

### Running the Agent
```bash
# Standalone
python3 salesforce_agent.py [-d|--debug] [--port 8001]

# Full system
python3 start_system.py
```

### Testing Connectivity
```bash
# Health check
curl http://localhost:8001/a2a/agent-card

# Tool execution
curl -X POST http://localhost:8001/a2a \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"process_task","params":{"task":{"instruction":"test connection"}},"id":"1"}'
```

### Adding New Functionality
1. Extend existing unified tools in `salesforce_unified.py`
2. Add new methods to base classes in `salesforce_base.py`  
3. Update SOQL query builder if needed
4. Register new capabilities in agent card

## Common Patterns

### ID Auto-Detection
```python
# Agent automatically detects object type from ID prefix
id_prefixes = {
    '001': 'Account',    '003': 'Contact',
    '00Q': 'Lead',       '006': 'Opportunity', 
    '500': 'Case',       '00T': 'Task'
}
```

### Natural Language Processing
The agent interprets natural language queries and converts them to appropriate SOQL:
- "this week" → `CreatedDate = THIS_WEEK`
- "over $50k" → `Amount > 50000`
- "high priority" → `Priority = 'High'`

### Error Recovery
- Connection failures trigger automatic retry
- Invalid queries return helpful error messages
- Missing data returns empty results rather than errors

## Troubleshooting

### Common Issues
- **401 Unauthorized**: Check username, password, and security token
- **Agent not responding**: Verify port 8001 is available
- **Empty results**: Check SOQL query syntax and field permissions

### Debug Logging
Enable with `-d` flag for detailed logs:
- Tool execution in `logs/salesforce.log`
- A2A communication in `logs/a2a_protocol.log`
- SOQL queries and results in debug output