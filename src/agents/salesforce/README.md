# Salesforce Agent - Enterprise CRM Automation 🚀

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2.69-green.svg)](https://github.com/langchain-ai/langgraph)
[![Salesforce API](https://img.shields.io/badge/Salesforce-REST%20API-orange.svg)](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/)
[![A2A Protocol](https://img.shields.io/badge/A2A%20Protocol-JSON--RPC%202.0-purple.svg)](https://github.com/google-a2a/A2A)

A specialized AI agent implementing Google's Agent-to-Agent (A2A) protocol for comprehensive Salesforce CRM automation. Features 20 enterprise-grade tools covering all major Salesforce objects with advanced analytics, SOQL injection prevention, and intelligent query optimization.

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Tool Catalog](#tool-catalog)
- [Advanced Analytics](#advanced-analytics)
- [Usage Examples](#usage-examples)
- [SOQL & SOSL Features](#soql--sosl-features)
- [Security Features](#security-features)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Performance Optimization](#performance-optimization)
- [Development Guide](#development-guide)

## Overview

The Salesforce Agent is a domain-specific AI agent that provides comprehensive CRM automation through:

- **20 Enterprise Tools**: Complete CRUD operations + advanced analytics across all major Salesforce objects
- **SOQL Query Builder**: Composable, secure query construction with automatic injection prevention
- **Advanced Analytics**: Pipeline analysis, performance metrics, cross-object search, and business intelligence
- **A2A Protocol**: Standards-compliant agent communication with the orchestrator
- **LangGraph Integration**: State-aware conversation flows with built-in memory
- **Security-First Design**: Input validation, parameterized queries, and audit logging

### Why a Specialized Salesforce Agent?

1. **Domain Expertise**: Deep knowledge of Salesforce object relationships and business processes
2. **Security Focus**: Built-in SOQL injection prevention and input validation
3. **Performance Optimization**: Query builder pattern reduces API calls and improves response times
4. **Flexible Search**: Natural language support with intelligent query generation
5. **Analytics Power**: Advanced aggregate functions and cross-object analysis capabilities

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
│  │                        TOOL EXECUTION LAYER                         │   │
│  │                                                                     │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │   │
│  │  │  CRUD Tools     │  │ Analytics Tools │  │  Search Tools       │  │   │
│  │  │  (15 tools)     │  │  (5 tools)      │  │  Cross-object SOSL  │  │   │
│  │  │ Basic Operations│  │  Aggregates     │  │  Global Search      │  │   │
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

### Core Components

#### 1. **A2A Protocol Handler** (`main.py:45-95`)
Standards-compliant implementation of Google's Agent2Agent protocol:
- JSON-RPC 2.0 message handling
- Task processing with state management
- Error handling and response formatting
- Health check endpoint (`/a2a/agent-card`)

#### 2. **Tool Execution Engine** (`salesforce_tools.py`)
Comprehensive tool suite with enterprise patterns:
- 15 CRUD tools for all major Salesforce objects
- 5 advanced analytics tools with aggregate functions
- Security-first design with input validation
- Consistent error handling and logging

#### 3. **SOQL Query Builder** (`soql_query_builder.py`)
Composable query construction system:
- Fluent interface for complex queries
- Automatic SOQL injection prevention
- Aggregate function support
- Relationship and subquery capabilities

## Tool Catalog

### CRUD Operations (15 Tools)

#### Lead Management
- **GetLeadTool**: `LOOKUP` - Individual lead records by ID, email, name, phone, or company
- **CreateLeadTool**: `CREATE` - New lead creation with validation and duplicate detection
- **UpdateLeadTool**: `UPDATE` - Lead information updates with audit trails

#### Account Management  
- **GetAccountTool**: `LOOKUP` - Account retrieval with flexible search patterns
- **CreateAccountTool**: `CREATE` - New account creation with relationship linking
- **UpdateAccountTool**: `UPDATE` - Account information management

#### Opportunity Pipeline
- **GetOpportunityTool**: `LOOKUP` - Individual opportunity records and pipeline tracking
- **CreateOpportunityTool**: `CREATE` - Deal creation with forecasting integration
- **UpdateOpportunityTool**: `UPDATE` - Stage progression and amount updates

#### Contact Management
- **GetContactTool**: `LOOKUP` - Contact records with account relationship mapping
- **CreateContactTool**: `CREATE` - Contact creation with automatic account linking
- **UpdateContactTool**: `UPDATE` - Contact information and relationship updates

#### Customer Service
- **GetCaseTool**: `LOOKUP` - Support ticket retrieval and analytics
- **CreateCaseTool**: `CREATE` - Case creation with SLA tracking
- **UpdateCaseTool**: `UPDATE` - Case resolution and status management

#### Activity Management
- **GetTaskTool**: `LOOKUP` - Task and activity coordination
- **CreateTaskTool**: `CREATE` - Task creation with assignment and follow-up
- **UpdateTaskTool**: `UPDATE` - Task completion and status updates

### Advanced Analytics (5 Tools)

#### **GetSalesPipelineTool** - `ANALYTICS`
Pipeline analysis with aggregate functions (COUNT, SUM, AVG)
```python
# Use cases:
"pipeline breakdown by stage"
"revenue totals by owner" 
"monthly pipeline trends"
"stage conversion analysis"
```

#### **GetTopPerformersTool** - `ANALYTICS`
Sales performance analytics with ranking and metrics
```python
# Metrics supported:
"revenue" - Total closed revenue
"deal_count" - Number of deals closed
"win_rate" - Percentage of opportunities won
"pipeline_value" - Total open pipeline
```

#### **GlobalSearchTool** - `SEARCH`
Cross-object SOSL search across multiple Salesforce objects
```python
# Search across:
["Account", "Contact", "Opportunity", "Lead", "Case", "Task"]
# Returns consolidated results with object type indicators
```

#### **GetAccountInsightsTool** - `ANALYTICS`
Comprehensive account analysis with subqueries
```python
# Provides:
- Account overview with industry/revenue data
- Related opportunities with pipeline summary
- Key contacts with activity tracking
- Open cases with priority classification
- Task summary with completion status
```

#### **GetBusinessMetricsTool** - `ANALYTICS`
Business intelligence and KPI calculations
```python
# Metrics available:
"revenue" - Closed revenue analysis
"leads" - Lead generation and conversion
"pipeline" - Open opportunity analysis
"cases" - Support ticket metrics
"activities" - Task and activity tracking

# Time periods:
"THIS_QUARTER", "THIS_YEAR", "LAST_MONTH", "LAST_90_DAYS"
```

## Advanced Analytics & Complex Query Examples

### 1. Sales Pipeline Analytics

#### Pipeline Breakdown by Stage
```bash
USER: Show me the sales pipeline grouped by stage with metrics
ASSISTANT: Here is the sales pipeline grouped by stage with metrics:

| Stage Name                | Opportunity Count | Total Amount    | Average Amount |
|---------------------------|-------------------|-----------------|----------------|
| Closed Won                | 18                | $4,250,000      | $236,111       |
| Negotiation/Review        | 12                | $3,650,000      | $304,167       |
| Proposal/Price Quote      | 15                | $3,200,000      | $213,333       |
| Prospecting               | 22                | $2,850,000      | $129,545       |
| Discovery                 | 8                 | $1,980,000      | $247,500       |
| Qualified                 | 14                | $1,750,000      | $125,000       |
| Needs Analysis            | 6                 | $950,000        | $158,333       |
| Value Proposition         | 4                 | $720,000        | $180,000       |
| Proposal Sent             | 3                 | $485,000        | $161,667       |
| Negotiation               | 2                 | $340,000        | $170,000       |
| New                       | 9                 | $285,000        | $31,667        |
| Id. Decision Makers       | 2                 | $125,000        | $62,500        |
| Qualification             | 1                 | $65,000         | $65,000        |

If you need further details or specific information, feel free to ask!
```
**SOQL Generated:**
```sql
SELECT StageName, COUNT(Id) OpportunityCount, 
       SUM(Amount) TotalAmount, AVG(Amount) AvgAmount 
FROM Opportunity 
GROUP BY StageName 
HAVING SUM(Amount) > 0 
ORDER BY SUM(Amount) DESC
```

#### Top Performing Sales Reps
```bash
USER: Who are our top 10 sales reps by closed revenue this year?
ASSISTANT: Here are your top performers by closed revenue:

1. **Sarah Johnson** - $1.2M revenue (15 deals won)
2. **Mike Chen** - $980K revenue (12 deals won)  
3. **Lisa Rodriguez** - $875K revenue (18 deals won)
4. **David Kim** - $720K revenue (9 deals won)
5. **Jennifer Walsh** - $650K revenue (11 deals won)
```
**SOQL Generated:**
```sql
SELECT OwnerId, Owner.Name, COUNT(Id) DealsWon, SUM(Amount) TotalRevenue 
FROM Opportunity 
WHERE IsClosed = true AND IsWon = true 
GROUP BY OwnerId, Owner.Name 
HAVING SUM(Amount) > 100000 
ORDER BY SUM(Amount) DESC LIMIT 10
```

### 2. Cross-Object Global Search with SOSL

#### Comprehensive Entity Search
```bash
USER: Find everything related to 'solar panel' across all Salesforce objects
ASSISTANT: Found 23 records related to 'solar panel':

**Accounts (3 found):**
- Solar Solutions Inc. - Technology - (555) 123-4567
- Green Energy Partners - Manufacturing - www.greenergy.com

**Contacts (8 found):**
- John Smith at Solar Solutions Inc. - VP Sales - john@solar.com
- Maria Garcia at Green Energy Partners - Engineer - maria@green.com

**Opportunities (5 found):**
- Solar Panel Installation - $250K - Proposal/Price Quote
- Residential Solar Project - $85K - Closed Won

**Leads (7 found):**
- Commercial Solar Inquiry - Acme Corp - New
- Rooftop Solar Lead - TechStart - Working
```
**SOSL Generated:**
```sosl
FIND {solar panel} IN ALL FIELDS 
RETURNING Account(Id, Name, Industry, Phone, Website LIMIT 20),
         Contact(Id, Name, Email, Phone, Title, Account.Name LIMIT 20),
         Opportunity(Id, Name, Amount, StageName, CloseDate, Account.Name 
                    WHERE Amount > 0 ORDER BY Amount DESC LIMIT 20),
         Lead(Id, Name, Company, Email, Phone, Status 
              WHERE Status IN ('New', 'Working', 'Qualified') LIMIT 20)
```

### 3. Account 360 Intelligence with Subqueries

#### Complete Account Analysis
```bash
USER: Give me a complete 360 view of the Acme Corp account
ASSISTANT: **Acme Corp - Complete Account Analysis**

**Account Overview:**
- Industry: Technology
- Annual Revenue: $50M
- Employees: 500
- Location: San Francisco, CA

**Pipeline Summary:**
- 3 open opportunities worth $750K total
- 8 contacts with active email addresses
- 2 open high-priority cases

**Top Opportunities:**
1. Enterprise Software License - $500K - Negotiation/Review
2. Consulting Services - $150K - Proposal/Price Quote  
3. Training Package - $100K - Qualification

**Key Contacts:**
- John CEO (CEO) - john@acme.com - Last activity: 2 days ago
- Sarah CTO (CTO) - sarah@acme.com - Last activity: 1 week ago

**Open Cases:**
- Software Integration Issue - High Priority
- License Configuration - Medium Priority
```
**SOQL with Subqueries:**
```sql
SELECT Id, Name, Industry, AnnualRevenue, NumberOfEmployees, Website, Phone,
       (SELECT Id, Name, Amount, StageName, CloseDate 
        FROM Opportunities ORDER BY Amount DESC LIMIT 10),
       (SELECT Id, Name, Title, Email, Phone 
        FROM Contacts WHERE Email != null 
        ORDER BY LastActivityDate DESC LIMIT 5),
       (SELECT Id, CaseNumber, Subject, Status, Priority 
        FROM Cases WHERE IsClosed = false ORDER BY Priority LIMIT 5)
FROM Account WHERE Name LIKE '%Acme Corp%'
```

### 4. Business Intelligence & KPI Analytics

#### Revenue Analysis by Industry  
```bash
USER: Show me revenue breakdown by industry for this quarter
ASSISTANT: **Q4 2024 Revenue by Industry:**

**Technology Sector:**
- 45 deals closed
- $8.2M total revenue  
- $182K average deal size

**Manufacturing:**
- 32 deals closed
- $6.1M total revenue
- $191K average deal size

**Healthcare:**
- 28 deals closed
- $4.8M total revenue
- $171K average deal size

**Financial Services:**
- 19 deals closed
- $3.2M total revenue
- $168K average deal size
```
**SOQL with Industry Grouping:**
```sql
SELECT Account.Industry, COUNT(Id) DealCount, 
       SUM(Amount) TotalRevenue, AVG(Amount) AvgDealSize 
FROM Opportunity 
WHERE IsClosed = true AND IsWon = true AND CloseDate = THIS_QUARTER 
GROUP BY Account.Industry
```

#### Lead Conversion Analysis  
```bash
USER: What's our lead conversion rate by lead source this year?
ASSISTANT: **2024 Lead Conversion Rates by Source:**

**Website Inquiries:**
- 145 total leads
- 32 converted (22.1% conversion rate)

**Trade Shows:**
- 89 total leads  
- 28 converted (31.5% conversion rate)

**Referrals:**
- 76 total leads
- 31 converted (40.8% conversion rate)

**Cold Outreach:**
- 234 total leads
- 18 converted (7.7% conversion rate)

**Best performing source: Referrals at 40.8% conversion rate**
```
**Implementation:**
- Executes multiple SOQL queries for total and converted leads
- Calculates conversion rates in post-processing
- Groups by LeadSource for comparative analysis

### 5. Advanced Filtering & Complex Conditions

#### Win Rate Analysis with Thresholds
```bash
USER: Show me win rates for reps with at least 10 closed deals
ASSISTANT: **Win Rate Analysis (Min. 10 closed deals):**

1. **Jennifer Walsh** - 78.6% win rate (11 won / 14 total)
2. **Sarah Johnson** - 75.0% win rate (15 won / 20 total)  
3. **Mike Chen** - 70.6% win rate (12 won / 17 total)
4. **David Kim** - 64.3% win rate (9 won / 14 total)
5. **Lisa Rodriguez** - 62.1% win rate (18 won / 29 total)
```
**Implementation:**
- Separate queries for total opportunities and won opportunities
- Post-processing calculation: WinRate = (WonDeals / TotalOpps) * 100
- Filtering by minimum deal thresholds

#### Pipeline with Multiple Filters
```bash
USER: Show me pipeline by owner for open deals over $25K in technology sector
ASSISTANT: **Technology Sector Pipeline (Open deals >$25K):**

**Sarah Johnson:**
- 8 opportunities
- $1.2M total pipeline
- $150K average deal size

**Mike Chen:**
- 6 opportunities  
- $890K total pipeline
- $148K average deal size

**Jennifer Walsh:**
- 5 opportunities
- $675K total pipeline
- $135K average deal size
```
**SOQL with Complex Filtering:**
```sql
SELECT OwnerId, Owner.Name, COUNT(Id) OpportunityCount, 
       SUM(Amount) TotalPipeline, AVG(Amount) AvgDealSize 
FROM Opportunity 
WHERE IsClosed = false 
  AND Amount >= 25000 
  AND Account.Industry = 'Technology' 
GROUP BY OwnerId, Owner.Name 
HAVING SUM(Amount) > 0 
ORDER BY SUM(Amount) DESC LIMIT 20
```

### 6. Time-Based Trending Analytics

#### Monthly Revenue Trends
```bash
USER: Show me monthly revenue trends for the last 12 months
ASSISTANT: **12-Month Revenue Trend:**

- **Jan 2024**: $1.2M (18 deals) 
- **Feb 2024**: $1.8M (22 deals) ↑50%
- **Mar 2024**: $2.1M (25 deals) ↑17%
- **Apr 2024**: $1.9M (24 deals) ↓10%
- **May 2024**: $2.4M (28 deals) ↑26%
- **Jun 2024**: $2.8M (32 deals) ↑17%

**Growth trend: +15% average monthly growth**
**Peak month: June 2024 ($2.8M)**
```
**SOQL with Calendar Functions:**
```sql
SELECT CALENDAR_MONTH(CloseDate) Month, CALENDAR_YEAR(CloseDate) Year,
       COUNT(Id) OpportunityCount, SUM(Amount) Revenue 
FROM Opportunity 
WHERE CloseDate >= LAST_N_MONTHS:12 
GROUP BY CALENDAR_MONTH(CloseDate), CALENDAR_YEAR(CloseDate) 
ORDER BY CALENDAR_YEAR(CloseDate), CALENDAR_MONTH(CloseDate)
```

## SOQL & SOSL Features Demonstrated

### Advanced SOQL Capabilities
- **Aggregate Functions**: COUNT(), SUM(), AVG(), MAX(), MIN()
- **Grouping**: GROUP BY with multiple fields
- **Filtering**: HAVING clauses for aggregate filtering  
- **Sorting**: ORDER BY with aggregate expressions
- **Date Functions**: CALENDAR_MONTH(), CALENDAR_YEAR()
- **Date Literals**: THIS_QUARTER, LAST_N_MONTHS:12, THIS_YEAR
- **Subqueries**: Related record retrieval in single API call
- **Relationship Queries**: Owner.Name, Account.Industry

### SOSL Global Search Features
- **Cross-object Search**: Multiple objects in single query
- **Field-specific Search**: IN EMAIL FIELDS, IN NAME FIELDS  
- **Conditional Filtering**: WHERE clauses in RETURNING
- **Result Ordering**: ORDER BY within object returns
- **Scope Control**: Limit results per object type

## Security Features

### SOQL Injection Prevention
```python
def escape_soql(value: Optional[str]) -> str:
    """Escape special characters to prevent SOQL injection"""
    if value is None:
        return ''
    return str(value).replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
```

### Input Validation
- **Pydantic Models**: Type validation for all tool inputs
- **Field Sanitization**: Automatic escaping of user inputs
- **Parameter Validation**: Required field checking and format validation
- **Error Sanitization**: Secure error reporting without sensitive data exposure

### Audit & Compliance
- **Activity Logging**: All operations logged with structured JSON
- **Parameter Tracking**: Complete audit trail of all tool executions
- **Error Monitoring**: Comprehensive error tracking and analysis
- **Performance Metrics**: Operation duration and resource usage tracking

## Configuration

### Environment Variables
```bash
# Salesforce Configuration (Required)
SFDC_USER=your@email.com
SFDC_PASS=your-password
SFDC_TOKEN=your-security-token

# Optional Agent Configuration
SALESFORCE_AGENT_PORT=8001
SALESFORCE_AGENT_HOST=localhost
DEBUG_MODE=true
```

### Agent Configuration (`agent_registry.json`)
```json
{
  "salesforce": {
    "host": "localhost",
    "port": 8001,
    "capabilities": [
      "salesforce_operations",
      "crm_management", 
      "sales_analytics",
      "customer_service",
      "data_analysis"
    ],
    "health_check_url": "http://localhost:8001/a2a/agent-card"
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
      "instruction": "get all records for GenePoint account"
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
    "artifacts": [
      {
        "type": "text",
        "content": "Account details and related records..."
      }
    ]
  },
  "id": "unique-request-id"
}
```

#### GET /a2a/agent-card
Returns agent capabilities and health status.

**Response:**
```json
{
  "name": "Salesforce Agent",
  "description": "Enterprise CRM automation with 20 specialized tools",
  "capabilities": [
    "CRUD operations for all major Salesforce objects",
    "Advanced analytics with aggregate functions",
    "Cross-object search with SOSL",
    "Pipeline analysis and performance metrics",
    "Account intelligence and business insights"
  ],
  "version": "1.0.0",
  "supported_objects": [
    "Account", "Contact", "Opportunity", "Lead", "Case", "Task"
  ]
}
```

### Tool Interface Patterns

#### CRUD Tool Pattern
```python
class GetAccountTool(BaseTool):
    name: str = "get_account_tool"
    description: str = "LOOKUP: Individual account records..."
    args_schema: type = GetAccountInput
    
    def _run(self, **kwargs) -> dict:
        # Input validation
        # SOQL query construction
        # Salesforce API call
        # Result processing
        # Error handling
        return results
```

#### Analytics Tool Pattern
```python
class GetSalesPipelineTool(BaseTool):
    name: str = "get_sales_pipeline_tool"
    description: str = "ANALYTICS: Sales pipeline analysis..."
    args_schema: type = GetSalesPipelineInput
    
    def _run(self, **kwargs) -> list:
        # Parameter validation
        # Aggregate query construction
        # Multiple query execution if needed
        # Data aggregation and calculation
        # Formatted result return
        return aggregated_results
```

## Performance Optimization

### Query Optimization Strategies

1. **Field Selection**: Only retrieve necessary fields to reduce API payload
2. **Query Limiting**: Use LIMIT clauses to prevent large result sets
3. **Index Utilization**: Query on indexed fields (Id, Name, Email) when possible
4. **Bulk Operations**: Batch related queries for efficiency
5. **Connection Reuse**: Maintain persistent connections to Salesforce

### Caching Strategies

```python
# Example: Connection caching
@lru_cache(maxsize=1)
def get_salesforce_connection():
    """Cached Salesforce connection for performance"""
    return Salesforce(
        username=os.environ['SFDC_USER'],
        password=os.environ['SFDC_PASS'],
        security_token=os.environ['SFDC_TOKEN']
    )
```

### Memory Management

- **Lazy Loading**: Load related records only when requested
- **Streaming Results**: Process large result sets in chunks
- **Memory Cleanup**: Automatic cleanup of large objects after processing
- **Connection Pooling**: Reuse connections across requests

## Development Guide

### Adding New Tools

1. **Define Input Schema**:
```python
class NewToolInput(BaseModel):
    field1: Optional[str] = None
    field2: Optional[int] = None
```

2. **Implement Tool Class**:
```python
class NewTool(BaseTool):
    name: str = "new_tool"
    description: str = "CATEGORY: Clear description of functionality"
    args_schema: type = NewToolInput
    
    def _run(self, **kwargs) -> dict:
        # Tool implementation
        pass
```

3. **Add to Tool Registry**: Update tool imports and registration

4. **Write Tests**: Create comprehensive test cases

5. **Update Documentation**: Add usage examples and API documentation

### Testing Strategy

```python
# Unit testing example
def test_get_account_tool():
    tool = GetAccountTool()
    result = tool._run(account_name="Test Account")
    assert isinstance(result, dict)
    assert "Id" in result or result == []
```

### Error Handling Patterns

```python
try:
    results = sf.query(query)
    return results['records']
except Exception as e:
    log_tool_activity("ToolName", "ERROR", error=str(e))
    return []  # Always return empty list, never error objects
```

### Logging Best Practices

```python
# Structured logging with context
log_tool_activity(
    tool_name="GetAccountTool",
    operation_type="RETRIEVE_ACCOUNT", 
    search_params={"account_name": account_name},
    query_used=query,
    result_count=len(results)
)
```

## Contributing

### Development Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Configure environment variables in `.env`
3. Run tests: `python -m pytest tests/`
4. Start agent: `python salesforce_agent.py -d`

### Code Standards
- Follow PEP 8 with 100-character line limit
- Use type hints for all public functions  
- Write comprehensive docstrings
- Focus comments on "why" not "what"
- Maintain security-first approach

### Pull Request Process
1. Create feature branch from main
2. Implement changes with tests
3. Update documentation
4. Submit PR with clear description
5. Address review feedback

---

## Support & Resources

- **Issue Tracking**: GitHub Issues for bug reports and feature requests
- **Documentation**: Comprehensive examples and API reference
- **Security**: SOQL injection prevention and input validation
- **Performance**: Query optimization and connection management

The Salesforce Agent represents the pinnacle of enterprise CRM automation, combining advanced AI capabilities with robust security and performance optimization for production-ready Salesforce integration.