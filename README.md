# Enterprise Multi-Agent Consultant Assistant 🤖

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2.69-green.svg)](https://github.com/langchain-ai/langgraph)
[![A2A Protocol](https://img.shields.io/badge/A2A%20Protocol-JSON--RPC%202.0-orange.svg)](https://github.com/google-a2a/A2A)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-grade, multi-agent AI system implementing Google's Agent-to-Agent (A2A) protocol for enterprise CRM automation, featuring resilient distributed architecture, intelligent orchestration, and seamless Salesforce integration.

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [System Requirements](#system-requirements)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Development](#development)
- [Production Deployment](#production-deployment)
- [Monitoring & Observability](#monitoring--observability)
- [Contributing](#contributing)
- [License](#license)

## Overview

The Enterprise Multi-Agent Consultant Assistant represents the cutting edge of AI agent orchestration, combining:

- **Google A2A Protocol**: Industry-standard agent communication using JSON-RPC 2.0
- **LangGraph Integration**: State-of-the-art conversation orchestration with built-in persistence
- **Enterprise Resilience**: Circuit breakers, connection pooling, and graceful degradation
- **Intelligent Memory**: Context-aware data persistence with TrustCall extraction
- **Cost Optimization**: Aggressive summarization and memory-first retrieval strategies

### Why This Architecture?

Traditional single-agent systems hit scalability walls. This architecture solves enterprise challenges:

1. **Specialization at Scale**: Each agent focuses on its domain (CRM, travel, HR, etc.)
2. **Resilient Communication**: Network failures don't cascade through the system
3. **Dynamic Discovery**: Agents can join/leave without system reconfiguration
4. **Memory Efficiency**: Structured extraction prevents context explosion
5. **Cost Control**: Token usage optimization through intelligent summarization

## Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                                │
│                           (orchestrator.py CLI)                            │
└────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                             ORCHESTRATOR AGENT                             │
│  ┌─────────────────┐  ┌───────────────────┐  ┌─────────────────────────┐   │
│  │  LangGraph      │  │  Agent Registry   │  │  Memory & State Mgmt    │   │
│  │  State Machine  │  │  Service Discovery|  │  TrustCall Extraction   │   │
│  └─────────────────┘  └───────────────────┘  └─────────────────────────┘   │
│                          Coordination & Intelligence                       │
└────────────────────────────────────────┬───────────────────────────────────┘
                                         │
                            ┌────────────┴────────────┐
                            │   A2A Protocol Layer    │
                            │  JSON-RPC 2.0 + HTTP    │
                            │  Circuit Breakers       │
                            │  Connection Pooling     │
                            └────────────┬────────────┘
                                         │
                    ┌────────────────────┴─────────────────────┐
                    ▼                                          ▼
┌─────────────────────────────────┐    ┌──────────────────────────────┐
│     SALESFORCE AGENT            │    │    EXTENSIBLE AGENTS         │
│  - 15 Specialized CRM Tools     │    │  - Travel Management         │
│  - SOQL Injection Prevention    │    │  - Expense Processing        │
│  - Flexible Search Patterns     │    │  - HR Operations             │
│  - LangGraph Integration        │    │  - Document Processing       │
└─────────────────────────────────┘    └──────────────────────────────┘
```

### Core Components

#### 1. **Orchestrator** (`src/orchestrator/main.py`)
The central nervous system implementing:
- LangGraph state machine for conversation flow
- Intelligent agent selection based on capabilities
- Fire-and-forget background tasks for non-blocking operations
- Smart message preservation during summarization
- Memory-first retrieval to minimize API calls

#### 2. **A2A Protocol** (`src/a2a/protocol.py`)
Enterprise-grade implementation of Google's Agent2Agent standard:
- **Connection Pooling**: 50+ concurrent connections with per-host limits
- **Circuit Breakers**: Netflix-style failure protection
- **Retry Logic**: Exponential backoff with jitter
- **Async Architecture**: Non-blocking I/O for maximum throughput
- **Standards Compliance**: Full JSON-RPC 2.0 with SSE support

#### 3. **Agent Registry** (`src/orchestrator/agent_registry.py`)
Service discovery inspired by Consul/Kubernetes:
- Dynamic agent registration and health monitoring
- Capability-based routing for intelligent task distribution
- Concurrent health checks with circuit breaker integration
- Real-time availability tracking with graceful degradation

#### 4. **Salesforce Agent** (`src/agents/salesforce/main.py`)
Domain-specific CRM automation:
- 15 comprehensive tools covering all major Salesforce objects
- Security-first design with SOQL injection prevention
- Flexible search patterns (ID, email, name, fuzzy matching)
- Token-optimized responses for cost efficiency

## Key Features

### 🛡️ Enterprise Security
- **Input Validation**: Comprehensive sanitization at all entry points
- **SOQL Injection Prevention**: Parameterized queries with character escaping
- **Authentication**: Environment-based credential management
- **Error Sanitization**: No sensitive data in error responses

### 🔄 Resilience Patterns
- **Circuit Breakers**: Prevent cascading failures (5 failures → 60s cooldown)
- **Connection Pooling**: Reuse expensive TLS connections
- **Graceful Degradation**: System continues with reduced functionality
- **Timeout Management**: Multi-level timeouts prevent hanging

### 🧠 Intelligent Memory
- **TrustCall Extraction**: Structured data extraction with Pydantic validation
- **Deduplication**: Automatic merging of duplicate records
- **Memory-First Retrieval**: Check memory before making API calls
- **Namespace Isolation**: User-specific memory boundaries

### 📊 Observability
- **Structured JSON Logging**: Machine-readable logs for all components
- **Distributed Tracing**: Cross-component operation tracking
- **Cost Analytics**: Token usage and cost estimation per operation
- **Performance Metrics**: Operation duration and throughput analysis

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/your-org/consultant-assistant.git
cd consultant-assistant

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 4. Start the system
python3 start_system.py

# 5. Interact via CLI
# In the orchestrator terminal:
> get all records for GenePoint account
> update opportunity for Express Logistics
> show me all Lundgren contacts
```

## System Requirements

- **Python**: 3.11+ (async/await support required)
- **Memory**: 2GB RAM minimum, 4GB recommended
- **Storage**: 500MB for logs and SQLite database
- **Network**: Stable internet for API calls
- **OS**: Linux, macOS, or Windows with WSL

### Python Dependencies

Core framework stack:
- `langchain==0.3.17` - Agent framework
- `langgraph==0.2.69` - State machine orchestration
- `langchain-openai==0.3.3` - LLM integration
- `trustcall==0.0.34` - Structured extraction

See `requirements.txt` for complete list.

## Configuration

### Environment Variables (.env)

```bash
# Azure OpenAI Configuration (Required)
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-4o-mini
AZURE_OPENAI_API_VERSION=2024-06-01
AZURE_OPENAI_API_KEY=your-api-key

# Salesforce Configuration (Required)
SFDC_USER=your@email.com
SFDC_PASS=your-password
SFDC_TOKEN=your-security-token

# Optional Configuration
DEBUG_MODE=true
ENVIRONMENT=development
```

### System Configuration (system_config.json)

The system uses a hierarchical configuration with intelligent defaults:

```json
{
  "conversation": {
    "summary_threshold": 5,           // Messages before summarization
    "memory_update_turn_threshold": 3 // Turns before memory extraction
  },
  "a2a": {
    "connection_pool_size": 20,       // Per-host connection limit
    "circuit_breaker_threshold": 5,   // Failures before circuit opens
    "timeout": 30                     // Request timeout in seconds
  }
}
```

Configuration precedence: Runtime → Environment → JSON → Defaults

## Usage Examples

### Basic Account Retrieval
```
USER: get the genepoint account
ASSISTANT: Here are the details for the Genepoint account:
- Account ID: 001bm00000SA8pSAAT
- Name: GenePoint
```

### Comprehensive Data Retrieval
```
USER: get all records for Express Logistics
ASSISTANT: Here are all records for Express Logistics and Transport:

Account: Express Logistics and Transport (ID: 001bm00000SA8pOAAT)

Contacts:
- Babara Levy (003bm000004Nn4IAAS)
- Josh Davis (003bm000004Nn4JAAS)

Opportunities:
- Standby Generator - $20.7T - Proposal/Price Quote
- Portable Truck Generators - Closed Won
- SLA - $650K - Closed Won

Cases:
- Malfunctioning Generator
- Easy installation process

Tasks:
- Send Edible Arrangement to Edna Frank
- Send Edible Arrangement to Frank Clark
```

### Intelligent Updates
```
USER: update the last opportunity for Lundgren, double the opportunity value
ASSISTANT: I've successfully updated the opportunity "Website Buildout" for Lundgren Karate and Chemistry Academy. The amount has been doubled from $100,000.00 to $200,000.00.
```

## Advanced Analytics & Complex Query Examples

### 1. Sales Pipeline Analytics with Aggregate Functions

#### Pipeline Analysis by Stage
```
USER: Show me the sales pipeline grouped by stage with metrics
ASSISTANT: Here's your sales pipeline breakdown by stage:

**Prospecting Stage:**
- 15 opportunities
- Total Pipeline: $2.4M
- Average Deal Size: $160K

**Proposal/Price Quote:**
- 8 opportunities  
- Total Pipeline: $3.2M
- Average Deal Size: $400K

**Closed Won:**
- 12 opportunities
- Total Revenue: $1.8M
- Average Deal Size: $150K
```
**Uses:** `GetSalesPipelineTool` with SOQL aggregate functions:
```sql
SELECT StageName, COUNT(Id) OpportunityCount, 
       SUM(Amount) TotalAmount, AVG(Amount) AvgAmount 
FROM Opportunity 
GROUP BY StageName 
HAVING SUM(Amount) > 0 
ORDER BY SUM(Amount) DESC
```

#### Top Performing Sales Reps
```
USER: Who are our top 10 sales reps by closed revenue this year?
ASSISTANT: Here are your top performers by closed revenue:

1. **Sarah Johnson** - $1.2M revenue (15 deals won)
2. **Mike Chen** - $980K revenue (12 deals won)  
3. **Lisa Rodriguez** - $875K revenue (18 deals won)
4. **David Kim** - $720K revenue (9 deals won)
5. **Jennifer Walsh** - $650K revenue (11 deals won)
```
**Uses:** `GetTopPerformersTool` with complex grouping:
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
```
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
**Uses:** `GlobalSearchTool` with SOSL (Salesforce Object Search Language):
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
```
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
**Uses:** `GetAccountInsightsTool` with subqueries for comprehensive data:
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
```
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
**Uses:** `GetBusinessMetricsTool` with industry grouping:
```sql
SELECT Account.Industry, COUNT(Id) DealCount, 
       SUM(Amount) TotalRevenue, AVG(Amount) AvgDealSize 
FROM Opportunity 
WHERE IsClosed = true AND IsWon = true AND CloseDate = THIS_QUARTER 
GROUP BY Account.Industry
```

#### Lead Conversion Analysis  
```
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
**Uses:** `GetBusinessMetricsTool` with conversion calculations:
- Executes multiple queries for total and converted leads
- Calculates conversion rates in post-processing
- Groups by LeadSource for comparative analysis

### 5. Advanced Filtering & Complex Conditions

#### Win Rate Analysis with Thresholds
```
USER: Show me win rates for reps with at least 10 closed deals
ASSISTANT: **Win Rate Analysis (Min. 10 closed deals):**

1. **Jennifer Walsh** - 78.6% win rate (11 won / 14 total)
2. **Sarah Johnson** - 75.0% win rate (15 won / 20 total)  
3. **Mike Chen** - 70.6% win rate (12 won / 17 total)
4. **David Kim** - 64.3% win rate (9 won / 14 total)
5. **Lisa Rodriguez** - 62.1% win rate (18 won / 29 total)
```
**Uses:** `GetTopPerformersTool` with win_rate metric:
- Separate queries for total opportunities and won opportunities
- Post-processing calculation: WinRate = (WonDeals / TotalOpps) * 100
- Filtering by minimum deal thresholds

#### Pipeline with Multiple Filters
```
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
**SOQL with complex filtering:**
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
```
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
**Uses:** Time-based grouping with CALENDAR functions:
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

## Development

### Project Structure

```
consultant-assistant/
├── src/
│   ├── orchestrator/          # Central coordination
│   │   ├── main.py           # LangGraph implementation
│   │   ├── agent_registry.py # Service discovery
│   │   └── enhanced_sys_msg.py # Prompt engineering
│   ├── agents/               # Specialized agents
│   │   └── salesforce/       # CRM agent
│   ├── a2a/                  # Protocol layer
│   │   └── protocol.py       # A2A implementation
│   ├── tools/                # Agent capabilities
│   │   └── salesforce_tools.py # 15 CRM tools
│   └── utils/                # Shared utilities
│       ├── config.py         # Configuration management
│       ├── circuit_breaker.py # Resilience patterns
│       └── logging/          # Structured logging
├── logs/                     # Component-separated logs
├── memory_store.db          # SQLite persistence
└── system_config.json       # System configuration
```

### Adding New Agents

1. Create agent module in `src/agents/your_agent/`
2. Implement A2A server with agent card
3. Define specialized tools
4. Register in `agent_registry.json`
5. Add orchestrator tool wrapper

See [Agent Development Guide](docs/dev/new-agent.md) for details.

### Code Style

- Follow PEP 8 with 100-character line limit
- Use type hints for all public functions
- Write docstrings for all modules, classes, and functions
- Focus comments on "why" not "what"

## Production Deployment

### Docker Deployment

```bash
# Build images
docker-compose build

# Run services
docker-compose up -d

# Scale agents
docker-compose scale salesforce-agent=3
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orchestrator
spec:
  replicas: 3
  selector:
    matchLabels:
      app: orchestrator
  template:
    spec:
      containers:
      - name: orchestrator
        image: consultant-assistant:latest
        env:
        - name: AZURE_OPENAI_ENDPOINT
          valueFrom:
            secretKeyRef:
              name: azure-credentials
              key: endpoint
```

### Performance Tuning

- **Connection Pools**: Tune based on concurrent users
- **Summary Threshold**: Lower for better context, higher for cost
- **Circuit Breakers**: Adjust based on network reliability
- **Memory Cache**: Consider Redis for distributed deployments

## Monitoring & Observability

### Log Analysis

All components generate structured JSON logs:

```json
{
  "timestamp": "2025-06-21T23:45:00.123Z",
  "operation_type": "A2A_TASK_COMPLETE",
  "task_id": "abc123",
  "duration_ms": 1234,
  "token_usage": 456,
  "estimated_cost": "$0.0012"
}
```

### Metrics to Monitor

1. **System Health**
   - Agent availability percentage
   - Circuit breaker status
   - Connection pool utilization

2. **Performance**
   - P95 response times
   - Token usage per operation
   - Summary/memory trigger rates

3. **Business Metrics**
   - CRM operations per hour
   - Success/failure rates
   - Cost per conversation

### Integration with APM Tools

The system supports OpenTelemetry for integration with:
- Datadog
- New Relic
- Prometheus/Grafana
- CloudWatch

## Contributing

We welcome contributions! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dev dependencies
pip install -r requirements-dev.txt

# Run pre-commit hooks
pre-commit install
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

This system implements enterprise patterns and standards from:
- Google's A2A Protocol for agent interoperability
- Netflix's circuit breaker pattern for resilience
- LangChain/LangGraph for agent orchestration
- OpenAI/Azure for LLM capabilities

Special thanks to the open-source community for the foundational libraries that make this system possible.

## Support

For issues and feature requests, please use the GitHub issue tracker.

For enterprise support inquiries, contact: enterprise@your-company.com