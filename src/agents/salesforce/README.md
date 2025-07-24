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

A specialized AI agent for Salesforce CRM operations, implementing 6 unified tools that replace the previous 15+ individual tools while providing enhanced functionality and better performance.

## Architecture

The Salesforce agent is built on:
- **LangGraph**: State machine orchestration with tool calling
- **A2A Protocol**: JSON-RPC 2.0 for agent communication
- **Unified Tools**: 6 comprehensive tools replacing 15+ legacy tools
- **Smart Features**: Auto ID detection, natural language queries, cross-object search

```mermaid
flowchart TB
    %% Define styles
    classDef agentClass fill:#1565c0,stroke:#0d47a1,stroke-width:4px,color:#ffffff,font-weight:bold
    classDef handlerClass fill:#2e7d32,stroke:#1b5e20,stroke-width:2px,color:#ffffff
    classDef toolClass fill:#ff6f00,stroke:#e65100,stroke-width:2px,color:#ffffff
    classDef builderClass fill:#6a1b9a,stroke:#4a0080,stroke-width:2px,color:#ffffff
    classDef apiClass fill:#00838f,stroke:#006064,stroke-width:2px,color:#ffffff
    classDef securityClass fill:#c62828,stroke:#8b0000,stroke-width:2px,color:#ffffff
    
    %% Main agent
    AGENT[☁️ SALESFORCE AGENT<br>━━━━━━━━━━━━━━━━━━<br>6 Unified Tools • Natural Language • Smart Detection]:::agentClass
    
    %% Top layer components
    subgraph handlers[" "]
        A2A[🌐 A2A Handler<br>━━━━━━━━━━━━<br>JSON-RPC 2.0<br>/a2a endpoint]:::handlerClass
        LG[📊 LangGraph<br>━━━━━━━━━━<br>State Mgmt<br>Memory]:::handlerClass
        SEC[🔒 Security Layer<br>━━━━━━━━━━━━━━<br>Input Validation<br>SOQL Injection Prev]:::securityClass
    end
    
    %% Unified tools layer
    subgraph tools["🛠️ UNIFIED TOOL EXECUTION LAYER"]
        subgraph row1[" "]
            GET[📥 SalesforceGet<br>━━━━━━━━━━━━━━<br>Record by ID<br>Auto-detection]:::toolClass
            SEARCH[🔍 SalesforceSearch<br>━━━━━━━━━━━━━━━━<br>Natural Language<br>& Structured]:::toolClass
            CREATE[➕ SalesforceCreate<br>━━━━━━━━━━━━━━━━<br>Any Object Type<br>Field Validation]:::toolClass
        end
        
        subgraph row2[" "]
            UPDATE[✏️ SalesforceUpdate<br>━━━━━━━━━━━━━━━━<br>Any Record<br>By ID/Criteria]:::toolClass
            SOSL[🌐 SalesforceSOSL<br>━━━━━━━━━━━━━━━<br>Cross-obj Search<br>Global Results]:::toolClass
            ANALYTICS[📊 SalesforceAnalytics<br>━━━━━━━━━━━━━━━━━━<br>Metrics & Aggreg<br>Business Intel]:::toolClass
        end
    end
    
    %% Query builder
    BUILDER[🔧 SOQL QUERY BUILDER<br>━━━━━━━━━━━━━━━━━━━━<br>Fluent Interface • Aggregate Functions • Security Features<br>Query Templates • Relationship Queries • Performance Opts<br>SOSL Support • Subquery Building • Error Handling]:::builderClass
    
    %% API layer
    API[☁️ SALESFORCE API LAYER<br>━━━━━━━━━━━━━━━━━━━━━<br>REST API Integration • Connection Management<br>Rate Limiting & Retries • Result Processing]:::apiClass
    
    %% Connections
    AGENT --> handlers
    A2A --> tools
    LG --> tools
    SEC --> tools
    
    GET --> BUILDER
    SEARCH --> BUILDER
    CREATE --> BUILDER
    UPDATE --> BUILDER
    SOSL --> BUILDER
    ANALYTICS --> BUILDER
    
    BUILDER --> API
    
    %% Style the subgraphs
    style handlers fill:rgba(33,150,243,0.1),stroke:#1565c0,stroke-width:2px
    style tools fill:rgba(255,111,0,0.1),stroke:#e65100,stroke-width:2px,stroke-dasharray: 5 5
    style row1 fill:none,stroke:none
    style row2 fill:none,stroke:none
```

## Tools Overview

### 1. SalesforceGet
**Purpose**: Direct record retrieval when you have the ID
```python
# Auto-detects object type from ID prefix
"get account 001bm00000SA8pSAAT"
"get 003bm000004Nn4IAAS"  # Automatically knows it's a Contact
```

**Features**:
- Auto-detection of object type from ID prefixes (001=Account, 003=Contact, etc.)
- Supports both 15 and 18 character IDs
- Field selection for performance optimization
- Uses REST API for single record retrieval (not SOQL)

### 2. SalesforceSearch
**Purpose**: Find records using natural language or SOQL
```python
# Natural language
"find all accounts in biotechnology industry"
"show me opportunities closing this month"

# Direct SOQL conditions
"search opportunities where Amount > 50000 AND StageName = 'Proposal'"
```

**Features**:
- Natural language to SOQL translation
- Smart field selection based on object type
- Automatic ordering (e.g., Opportunities by Amount DESC)
- Default limit of 50 records
- Validation of filterable fields

### 3. SalesforceCreate
**Purpose**: Create any Salesforce object
```python
"create a new lead for John Smith at TechCorp with email john@techcorp.com"
"create opportunity for Acme Corp worth $50,000 closing next month"
```

**Features**:
- Automatic required field validation
- Data preparation and formatting
- Returns full created record details
- Error handling with clear messages

### 4. SalesforceUpdate
**Purpose**: Modify existing records
```python
# Update by ID
"update opportunity 006XX123 set stage to Closed Won"

# Update by search criteria
"update all opportunities for Acme where Amount > 100000 set Discount to 10%"
```

**Features**:
- Update by ID, record number, or WHERE clause
- Bulk update support
- Data validation and preparation
- Returns updated record details

### 5. SalesforceSOSL
**Purpose**: Search across multiple object types simultaneously
```python
"find anything related to john@example.com"
"search for 'annual contract' across all objects"
```

**Features**:
- Cross-object search using Salesforce Object Search Language
- Default searches: Account, Contact, Lead, Opportunity, Case
- Configurable fields per object type
- Results organized by object type

### 6. SalesforceAnalytics
**Purpose**: Aggregations and metrics
```python
"show total pipeline by stage"
"average deal size by owner this quarter"
"count of cases by priority last month"
```

**Features**:
- Aggregate functions: COUNT, SUM, AVG, MIN, MAX
- Group by any field
- Time period filters (THIS_MONTH, LAST_QUARTER, etc.)
- Support for complex WHERE conditions

## Configuration

### Environment Variables
```bash
# Required
SFDC_USER=your@email.com
SFDC_PASS=your-password
SFDC_TOKEN=your-security-token

# Azure OpenAI (Required)
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-4o-mini
AZURE_OPENAI_API_KEY=your-key
```

### A2A Configuration
- **Default Port**: 8001
- **Host**: 0.0.0.0 (configurable)
- **Protocol**: JSON-RPC 2.0
- **Endpoints**:
  - `POST /a2a` - Process tasks
  - `GET /a2a/agent-card` - Get capabilities

## Usage Examples

### Basic Operations
```bash
# Retrieve
"get the GenePoint account"
"get opportunity 006XX000123ABC"

# Search
"find all high-value opportunities"
"list contacts at Acme Corp"

# Create
"create lead Sarah Johnson from TechStart"
"create case for billing issue high priority"

# Update
"update the Acme opportunity to Closed Won"
"mark all old leads as disqualified"
```

### Advanced Queries
```bash
# Analytics
"show pipeline breakdown by stage and owner"
"total revenue closed last quarter by region"
"average time to close by lead source"

# Complex searches
"find opportunities worth over $100k closing this quarter"
"show accounts with no activity in 90 days"

# Cross-object
"find everything related to merger announcement"
```

## Technical Details

### State Management
The agent uses LangGraph's state schema:
```python
class SalesforceState(TypedDict):
    messages: Annotated[list, add_messages]
    task_context: Dict[str, Any]
    external_context: Dict[str, Any]
```

### Tool Features
- **produces_user_data**: Flag indicating if tool output needs user review
- **Automatic validation**: Required fields, data types, field permissions
- **Smart defaults**: Appropriate fields selected based on object type
- **Error standardization**: Consistent error format across all tools

### Performance Optimizations
- Connection pooling with 50 total connections
- REST API for single record operations (avoid SOQL)
- Field selection to reduce payload size
- Query optimization with SOQLQueryBuilder
- Background cleanup of idle connections

### Security Features
- SOQL injection prevention via SOQLQueryBuilder
- Input validation and sanitization
- Secure credential management
- No raw query execution
- Field-level permission checking

## Logging

Logs are written to `logs/salesforce.log` with structured JSON format:
```json
{
  "timestamp": "2025-07-23T10:30:00Z",
  "level": "INFO",
  "component": "salesforce",
  "tool_name": "salesforce_search",
  "operation": "query_built",
  "query": "SELECT Id, Name FROM Account WHERE Industry = 'Technology'"
}
```

### Key Log Events
- `tool_call` - Tool invocation with arguments
- `tool_result` - Successful tool execution
- `tool_error` - Tool execution failures
- `soql_query` - Generated SOQL queries
- `salesforce_connection` - Connection events

## Development

### Adding New Features
1. Extend base tool classes in `tools/base.py`
2. Implement tool in `tools/unified.py`
3. Add to `UNIFIED_SALESFORCE_TOOLS` export
4. Update capability list in agent card

### Testing
```bash
# Direct agent testing
python3 salesforce_agent.py --port 8001

# Test specific tool via A2A
curl -X POST http://localhost:8001/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "process_task",
    "params": {
      "task": {
        "id": "test-001",
        "instruction": "get the GenePoint account"
      }
    },
    "id": "test-001"
  }'
```

## Common Issues

### Storage Limit Exceeded
In development environments, you may see:
```
"STORAGE_LIMIT_EXCEEDED: storage limit of 110000"
```
This is expected in free developer orgs and validates error handling.

### GraphRecursionError
If you see recursion limit errors:
- Simplify your query
- Be more specific in search criteria
- Use direct IDs when available

### Authentication Failures
Ensure:
- Security token is appended to password
- IP restrictions are configured
- OAuth permissions are granted

## Best Practices

1. **Use specific object types** in searches when known
2. **Leverage ID auto-detection** for get operations
3. **Batch updates** using WHERE clauses for efficiency
4. **Select only needed fields** to reduce payload size
5. **Use analytics tools** for aggregations, not search
6. **Check produces_user_data** flag for UI integration

## Architecture Decisions

- **6 Unified Tools**: Reduced from 15+ for better maintainability
- **Natural Language**: LLM-friendly tool descriptions
- **Auto-detection**: Smart inference reduces user input needs
- **Error Clarity**: Actionable error messages for the LLM
- **Performance First**: REST API for singles, SOQL for bulk