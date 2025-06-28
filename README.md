```
███████╗███╗   ██╗████████╗███████╗██████╗ ██████╗ ██████╗ ██╗███████╗███████╗
██╔════╝████╗  ██║╚══██╔══╝██╔════╝██╔══██╗██╔══██╗██╔══██╗██║██╔════╝██╔════╝
█████╗  ██╔██╗ ██║   ██║   █████╗  ██████╔╝██████╔╝██████╔╝██║███████╗█████╗  
██╔══╝  ██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗██╔═══╝ ██╔══██╗██║╚════██║██╔══╝  
███████╗██║ ╚████║   ██║   ███████╗██║  ██║██║     ██║  ██║██║███████║███████╗
╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝╚═╝╚══════╝╚══════╝

 █████╗ ███████╗███████╗██╗███████╗████████╗ █████╗ ███╗   ██╗████████╗
██╔══██╗██╔════╝██╔════╝██║██╔════╝╚══██╔══╝██╔══██╗████╗  ██║╚══██╔══╝
███████║███████╗███████╗██║███████╗   ██║   ███████║██╔██╗ ██║   ██║   
██╔══██║╚════██║╚════██║██║╚════██║   ██║   ██╔══██║██║╚██╗██║   ██║   
██║  ██║███████║███████║██║███████║   ██║   ██║  ██║██║ ╚████║   ██║   
╚═╝  ╚═╝╚══════╝╚══════╝╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   
```

<div align="center">
  <h3>🚀 Multi-Agent Orchestrator for Enterprise AI Operations 🚀</h3>
  
  [![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
  [![LangGraph](https://img.shields.io/badge/LangGraph-0.2.69-green.svg)](https://github.com/langchain-ai/langgraph)
  [![A2A Protocol](https://img.shields.io/badge/A2A%20Protocol-JSON--RPC%202.0-orange.svg)](https://github.com/google-a2a/A2A)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  
  <p><em>A production-grade, multi-agent AI system implementing Agent-to-Agent (A2A) protocol for enterprise automation, featuring resilient distributed architecture, intelligent orchestration, and seamless integration with Salesforce, Jira, and ServiceNow.</em></p>
</div>

---

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

The Enterprise Multi-Agent Assistant represents the cutting edge of AI agent orchestration, combining:

- **A2A Protocol**: Industry-standard agent communication using JSON-RPC 2.0
- **LangGraph Integration**: State-of-the-art conversation orchestration with built-in persistence
- **Enterprise Resilience**: Circuit breakers, connection pooling, and graceful degradation
- **Intelligent Memory**: Context-aware data persistence with automated summarization
- **Cost Optimization**: Aggressive summarization and memory-first retrieval strategies

### Why This Architecture?

Traditional single-agent systems hit scalability walls. This architecture solves enterprise challenges:

1. **Specialization at Scale**: Each agent focuses on its domain (CRM, ITSM, project management, etc.)
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
│  │  State Machine  │  │  Service Discovery│  │  Auto Summarization     │   │
│  └─────────────────┘  └───────────────────┘  └─────────────────────────┘   │
│                          Coordination & Intelligence                       │
└────────────────────────────────────┬───────────────────────────────────────┘
                                     │
                        ┌────────────┴────────────┐
                        │   A2A Protocol Layer    │
                        │  JSON-RPC 2.0 + HTTP    │
                        │  Circuit Breakers       │
                        │  Connection Pooling     │
                        └────────────┬────────────┘
                                     │
 ┌───────────────────────────┬────────────────────────────┬──────────────────────┐
 │                           │                            │                      │
 ▼                           ▼                            ▼                      ▼
┌────────────────────┐ ┌────────────────────┐ ┌────────────────────┐ ┌────────────────────┐
│ SALESFORCE AGENT   │ │   JIRA AGENT       │ │ SERVICENOW AGENT   │ │  WORKFLOW AGENT    │
│ - 6 Unified Tools  │ │ - 6 Unified Tools  │ │ - 6 Unified Tools  │ │ - 5 Workflow Types │
│ - SOQL Builder     │ │ - JQL Search       │ │ - Incident Mgmt    │ │ - Multi-step Exec  │
│ - Lead Management  │ │ - Sprint Mgmt      │ │ - Change Mgmt      │ │ - Parallel Process │
│ - Opportunity Mgmt │ │ - Epic Tracking    │ │ - Problem Mgmt     │ │ - Cross-system     │
│ - LangGraph State  │ │ - LangGraph State  │ │ - CMDB Operations  │ │ - Business Reports │
└────────────────────┘ └────────────────────┘ └────────────────────┘ └────────────────────┘
```

### Core Components

#### 1. **Orchestrator** (`src/orchestrator/main.py`)
The central nervous system implementing:
- LangGraph state machine for conversation flow
- Intelligent agent selection based on capabilities
- Background tasks for non-blocking operations (3 tool calls, 2 agent calls, or 180 seconds)
- Smart message preservation during summarization
- Memory-first retrieval to minimize API calls

#### 2. **A2A Protocol** (`src/a2a/protocol.py`)
Enterprise-grade implementation of Agent-to-Agent standard:
- **Connection Pooling**: 50+ concurrent connections with per-host limits
- **Circuit Breakers**: Netflix-style failure protection
- **Retry Logic**: Exponential backoff with jitter
- **Async Architecture**: Non-blocking I/O for maximum throughput
- **Standards Compliance**: Full JSON-RPC 2.0 implementation

#### 3. **Agent Registry** (`src/orchestrator/agent_registry.py`)
Service discovery inspired by Consul/Kubernetes:
- Dynamic agent registration and health monitoring
- Capability-based routing for intelligent task distribution
- Concurrent health checks with circuit breaker integration
- Real-time availability tracking with graceful degradation

#### 4. **Specialized Agents**

**Salesforce Agent** (`src/agents/salesforce/main.py`)
- 6 unified tools covering all major CRM operations
- Advanced analytics with SOQL aggregations
- Security-first design with SOQL injection prevention
- Auto-detection of object types from ID prefixes

**Jira Agent** (`src/agents/jira/main.py`)
- 6 unified tools for complete issue lifecycle management
- JQL search with natural language support
- Sprint and epic management capabilities
- Agile workflow automation

**ServiceNow Agent** (`src/agents/servicenow/main.py`)
- 6 unified ITSM tools across key operational categories
- Incident, change, and problem management
- CMDB integration for configuration items
- GlideQuery builder for secure, complex queries

**Workflow Agent** (`src/agents/workflow/main.py`)
- 5 pre-built business workflow templates
- Advanced multi-step execution engine with parallel processing
- Cross-system orchestration (Salesforce + Jira + ServiceNow)
- LLM-powered business intelligence and reporting

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
- **AsyncStoreAdapter**: Simplified SQLite storage (167 lines - 69% reduction)
- **Thread Persistence**: Full state snapshots with serialized messages
- **Memory-First Retrieval**: Check memory before making API calls
- **Namespace Isolation**: User-specific memory boundaries

### 📊 Observability
- **Structured JSON Logging**: Machine-readable logs for all components
- **Multi-File Logging**: Component-separated logs for focused debugging
- **Performance Metrics**: Operation duration and throughput analysis
- **Cost Analytics**: Token usage tracking per operation

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
> get all records for GenePoint account      # Salesforce
> show me all critical incidents             # ServiceNow
> find all open bugs in project PROJ-123    # Jira
> create a change request for server upgrade # ServiceNow
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
- `pydantic==2.6.4` - Data validation

See `requirements.txt` for complete list.

## Configuration

### Environment Variables (.env)

```bash
# Azure OpenAI Configuration (Required)
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-4o-mini
AZURE_OPENAI_API_VERSION=2024-06-01
AZURE_OPENAI_API_KEY=your-api-key

# Salesforce Configuration
SFDC_USER=your@email.com
SFDC_PASS=your-password
SFDC_TOKEN=your-security-token

# Jira Configuration
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_USER=your@email.com
JIRA_API_TOKEN=your-api-token

# ServiceNow Configuration
SNOW_INSTANCE=your-instance.service-now.com
SNOW_USER=your-username
SNOW_PASS=your-password

# Optional Configuration
DEBUG_MODE=true
ENVIRONMENT=development
LLM_RECURSION_LIMIT=15  # Max iterations for agent loops
```

### System Configuration (system_config.json)

The system uses a hierarchical configuration with intelligent defaults:

```json
{
  "conversation": {
    "typing_effect_enabled": true,          // Animated UI effects
    "animated_capabilities_enabled": true   // Banner animations
  },
  "a2a": {
    "connection_pool_size": 50,             // Total connection limit
    "circuit_breaker_threshold": 5,         // Failures before circuit opens
    "timeout": 30                           // Request timeout in seconds
  },
  "llm": {
    "temperature": 0.1,                     // Conservative temperature
    "max_tokens": 4000,                     // Response token limit
    "recursion_limit": 15                   // Max iterations for agent loops
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

### ServiceNow ITSM Operations
```
USER: show me all critical incidents
ASSISTANT: Found 2 critical incidents:

| Number      | Short Description        | State       | Priority    | Assigned To  |
|-------------|-------------------------|-------------|-------------|--------------|
| INC0010023  | Email server down       | In Progress | 1 - Critical| john.smith   |
| INC0010024  | Database connection fail| New         | 1 - Critical| Unassigned   |
```

### Cross-Platform Workflow
```
USER: create a Jira ticket for the email server incident
ASSISTANT: Created Jira issue INFRA-456 linked to ServiceNow incident INC0010023. 
The issue has been assigned to the Infrastructure team with high priority.
```

### Business Process Automation
```
USER: check for at-risk deals
ASSISTANT: 🔄 Executing At-Risk Deal Assessment workflow...

# Workflow Execution Report: Deal Risk Assessment

## 1. Executive Summary
The execution of the "deal_risk_assessment" workflow yielded no opportunities closing this month with no recent activity. However, the system discovered 54 open incidents that could potentially impact customer relationships.

## 2. Key Findings
- **Opportunities Analyzed**: 0 opportunities closing this month
- **ServiceNow Incidents**: 54 open incidents (mostly email server issues)
- **Jira Issues**: No critical issues found
- **Salesforce Cases**: No account-related cases found

## 3. Risk Assessment
- **Overall Risk Level**: LOW
- **Immediate Action Required**: None for sales pipeline
- **Service Risk**: MEDIUM (due to open incidents)

## 4. Recommended Actions
1. Monitor email server incidents for customer impact
2. Continue regular pipeline health checks
3. Review incident resolution processes

Workflow completed in 14.7 seconds across all systems.
```

### Customer Onboarding Automation
```
USER: start customer onboarding for ACME Corp
ASSISTANT: 🚀 Initiating New Customer Onboarding workflow...

✅ Customer onboarding setup completed for ACME Corp:
- Salesforce onboarding case created: CS-001234
- Jira project provisioned: ACME-ONBOARD
- ServiceNow service account configured
- Kickoff meeting scheduled for next Tuesday
- All stakeholders notified

Total setup time: 4 minutes 32 seconds
```

## Advanced Capabilities

### Salesforce CRM Integration
The system features a specialized Salesforce agent with 6 unified tools covering:

- **CRUD Operations**: Complete management of Accounts, Contacts, Opportunities, Leads, Cases, and Tasks
- **Advanced Analytics**: Pipeline analysis, performance metrics, and business intelligence
- **Cross-Object Search**: SOSL-powered global search across all Salesforce objects
- **Security-First Design**: SOQL injection prevention and comprehensive input validation

For detailed Salesforce capabilities, examples, and API reference, see the [Salesforce Agent README](src/agents/salesforce/README.md).

### Jira Project Management Integration
The system features a specialized Jira agent with 6 unified tools covering:

- **Issue Management**: Create, read, update, and transition issues across all types (bug, story, task, epic)
- **Advanced Search**: JQL-powered queries for complex filtering and reporting
- **Agile Workflows**: Sprint tracking, epic management, kanban/scrum board operations
- **Project Analytics**: Team velocity, burndown charts, cycle time analysis
- **Security-First Design**: JQL injection prevention and comprehensive input validation

For detailed Jira capabilities, examples, and API reference, see the [Jira Agent README](src/agents/jira/README.md).

### ServiceNow ITSM Integration
The system features a specialized ServiceNow agent with 15 specialized tools covering:

- **Incident Management**: Create, track, and resolve IT service disruptions
- **Change Management**: Plan and execute infrastructure changes with approval workflows
- **Problem Management**: Root cause analysis and permanent fix tracking
- **CMDB Operations**: Configuration item discovery and relationship mapping
- **GlideQuery Builder**: Secure, complex query construction with injection prevention

For detailed ServiceNow capabilities, examples, and API reference, see the [ServiceNow Agent README](src/agents/servicenow/README.md).

### Workflow-Based Business Process Automation
The system features a sophisticated workflow agent with 5 pre-built business processes:

- **Deal Risk Assessment**: Identify at-risk opportunities and blockers across all systems
- **Incident to Resolution**: End-to-end incident management with automatic system linking
- **Customer 360 Report**: Comprehensive customer data aggregation and business intelligence
- **Weekly Account Health Check**: Proactive monitoring of key account health metrics
- **New Customer Onboarding**: Automated customer setup and stakeholder coordination

**Advanced Workflow Features**:
- Multi-step execution with conditional branching
- Parallel processing for independent operations
- Cross-system state management and context propagation
- LLM-powered business intelligence and executive reporting
- Human-in-the-loop approval workflows
- Error handling with retry logic and graceful degradation

For detailed workflow capabilities, template creation, and API reference, see the [Workflow Agent README](src/agents/workflow/README.md).

### Multi-Agent Extensibility
The architecture supports adding new specialized agents for:
- Travel management and expense processing
- HR operations and employee onboarding
- Document processing with OCR capabilities
- Financial reporting and approval workflows

## Development

### Project Structure

```
consultant-assistant/
├── src/
│   ├── orchestrator/             # Central coordination
│   │   ├── main.py              # CLI interface & main loop
│   │   ├── graph_builder.py     # LangGraph workflow construction
│   │   ├── state.py             # State schema
│   │   ├── conversation_handler.py # Message processing
│   │   ├── background_tasks.py  # Async operations
│   │   ├── llm_handler.py       # Azure OpenAI integration
│   │   ├── agent_registry.py    # Service discovery
│   │   └── agent_caller_tools.py # A2A delegation
│   ├── agents/                  # Specialized agents
│   │   ├── salesforce/          # CRM agent
│   │   ├── jira/               # Issue tracking agent
│   │   ├── servicenow/         # ITSM agent
│   │   └── workflow/           # Business process orchestration agent
│   ├── a2a/                     # Protocol layer
│   │   ├── protocol.py          # A2A implementation
│   │   └── circuit_breaker.py   # Resilience patterns
│   ├── tools/                   # Agent capabilities
│   │   ├── salesforce/          # Unified CRM tools
│   │   ├── jira/               # Unified issue tracking tools
│   │   ├── servicenow/         # Unified ITSM tools
│   │   └── workflow_tools.py    # Workflow orchestration tools
│   └── utils/                   # Shared utilities
│       ├── config/              # Configuration management
│       │   ├── config.py        # Main config system
│       │   └── constants.py     # Centralized constants
│       ├── storage/             # SQLite adapter
│       ├── logging/             # Multi-file logging
│       │   └── multi_file_logger.py
│       ├── agents/              # Agent-specific utilities
│       │   └── prompts.py       # System prompts
│       ├── ui/                  # UI utilities
│       │   ├── banners.py       # Banner display
│       │   ├── typing_effect.py # Animated typing
│       │   └── formatting.py    # Console formatting
│       ├── platform/            # Platform-specific utilities
│       │   ├── query/           # Query builders
│       │   │   └── base_builder.py # Base query builder
│       │   ├── salesforce/
│       │   │   └── soql_builder.py # SOQL query builder
│       │   └── servicenow/
│       │       └── glide_builder.py # Glide query builder
│       └── message_serialization.py # LangChain serialization
├── logs/                        # Component-separated logs
├── memory_store.db             # SQLite persistence
└── system_config.json          # System configuration
```

### Adding New Agents

1. Create agent module in `src/agents/your_agent/`
2. Implement A2A server with agent card
3. Define specialized tools
4. Register in `agent_registry.json`
5. Add orchestrator tool wrapper

See [Component Documentation](docs/components/) for details.

### Code Style

- Follow PEP 8 with 100-character line limit
- Use type hints for all public functions
- Write concise docstrings focusing on purpose
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
  "timestamp": "2025-06-26T23:45:00.123Z",
  "component": "orchestrator",
  "operation_type": "A2A_TASK_COMPLETE",
  "task_id": "abc123",
  "duration_ms": 1234,
  "agent": "salesforce"
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
pip install -r requirements.txt

# Run pre-commit hooks (if available)
pre-commit install
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

This system implements enterprise patterns and standards from:
- Agent-to-Agent (A2A) Protocol for agent interoperability
- Netflix's circuit breaker pattern for resilience
- LangChain/LangGraph for agent orchestration
- OpenAI/Azure for LLM capabilities

Special thanks to the open-source community for the foundational libraries that make this system possible.

## Support

For issues and feature requests, please use the GitHub issue tracker.

For enterprise support inquiries, contact: enterprise@your-company.com