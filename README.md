# Consultant Assistant Multi-Agent System

## Overview
The **Consultant Assistant** is a sophisticated **multi-agent system** powered by **LangGraph** and **Google's Agent2Agent (A2A) protocol** designed to assist consultants in their daily workflows by integrating with various enterprise systems. The system uses specialized AI agents that communicate via JSON-RPC to provide seamless enterprise integration.

The assistant utilizes OpenAI's **AzureChatOpenAI**, coordinated through an **orchestrator agent** that routes requests to **specialized agents** for Salesforce, travel, expenses, HR, and document processing. The tool maintains memory using **SQLite** and provides structured interaction through LangGraph's **state management and workflow execution**.

---

## Current Architecture

### Multi-Agent System Design
This is a **production-ready multi-agent system** with the following components:

1. **Orchestrator Agent**: Routes requests to specialized agents via A2A protocol
2. **Specialized Agents**: Domain-specific LangGraph agents (Salesforce, Travel, Expense, etc.)
3. **A2A Communication**: JSON-RPC over HTTP for inter-agent communication
4. **Global State Management**: Coordinated memory and context across all agents
5. **Agent Registry**: Dynamic discovery and health monitoring of specialized agents

### Current Agents
- **Salesforce Agent**: Complete CRM operations (Leads, Accounts, Opportunities, Contacts, Cases, Tasks)
- **Future Agents**: Travel, Expense, HR, OCR (architecture ready for expansion)

---

## Installation & Setup

### Prerequisites
- Python 3.9+
- Salesforce account with API access
- Azure OpenAI setup

### Quick Start
1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd consultant-assistant
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   Create a `.env` file in the project root:
   ```env
   SFDC_USER=<your_salesforce_username>
   SFDC_PASS=<your_salesforce_password>
   SFDC_TOKEN=<your_salesforce_security_token>
   AZURE_OPENAI_ENDPOINT=<your_azure_openai_endpoint>
   AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=<your_deployment_name>
   AZURE_OPENAI_API_VERSION=<api_version>
   AZURE_OPENAI_API_KEY=<your_api_key>
   ```

4. **Start the system:**
   ```bash
   # Recommended: Start entire system
   python3 start_system.py
   
   # Alternative: Start components individually
   # Terminal 1 - Start Salesforce agent
   python3 salesforce_agent.py
   
   # Terminal 2 - Start orchestrator
   python3 orchestrator.py
   ```

5. **Debug mode:**
   ```bash
   python3 orchestrator.py -d
   python3 salesforce_agent.py -d --port 8001
   ```

---

## Project Structure

```
consultant-assistant/
├── start_system.py              # System startup script
├── orchestrator.py              # Orchestrator entry point  
├── salesforce_agent.py          # Salesforce agent entry point
├── agent_registry.json          # Agent configuration
├── system_config.json          # System configuration
├── requirements.txt             # Dependencies
├── CLAUDE.md                   # Development guide
│
├── src/
│   ├── orchestrator/           # Orchestrator agent
│   │   ├── main.py            # LangGraph orchestrator
│   │   ├── agent_registry.py  # Agent discovery & monitoring
│   │   ├── agent_caller_tools.py # A2A communication tools
│   │   └── enhanced_sys_msg.py # Multi-agent system prompts
│   │
│   ├── agents/                # Specialized agents
│   │   └── salesforce/        # Salesforce CRM agent
│   │       └── main.py        # Salesforce LangGraph workflow
│   │
│   ├── a2a/                   # Agent2Agent protocol
│   │   └── protocol.py        # JSON-RPC client/server
│   │
│   ├── tools/                 # Enterprise integration tools
│   │   └── salesforce_tools.py # Salesforce CRUD operations
│   │
│   └── utils/                 # Organized utility modules
│       ├── storage/           # SQLite adapters, memory schemas
│       ├── logging/           # Activity loggers, tracing
│       ├── caching/           # LLM response caching
│       ├── circuit_breaker.py # Resilience patterns
│       ├── config.py          # Configuration management
│       ├── helpers.py         # Message processing utilities
│       ├── input_validation.py # Security & validation
│       └── sys_msg.py         # Legacy system messages
│
└── logs/                      # Structured logging output
    ├── orchestrator.log
    ├── salesforce_agent.log
    ├── a2a_protocol.log
    ├── performance.log
    └── cost_tracking.log
```

---

## Usage

### CLI Interface
The system provides an interactive CLI through the orchestrator:

```bash
=== Consultant Assistant Orchestrator ===
Multi-agent system ready. Available capabilities:
  • account_management
  • case_handling
  • contact_management
  • crm_operations
  • lead_management
  • opportunity_tracking
  • salesforce_operations
  • task_management

Type your request, or 'quit' to exit.

USER: get the genepoint account
```

### Example Interactions

**Retrieving Account Information:**
```
USER: get the genepoint account
ASSISTANT: Here are the details for the Genepoint account:
- Account ID: 001bm00000SA8pSAAT
- Name: GenePoint
```

**Getting All Related Records:**
```
USER: get all records for genepoint
ASSISTANT: Here are all the records related to GenePoint:

### Contacts
1. Edna Frank - Email: updated.test.contact@example.com
2. Frank Clark - Email: frank.clark@genepoint.com

### Opportunities  
1. GenePoint Standby Generator - Stage: Closed Won - Amount: $15,000,000.00
2. GenePoint Lab Generators - Stage: Closed Won - Amount: $200,000,000.00

### Cases
1. Generator assembly instructions unclear - Contact: Edna Frank
2. Maintenance guidelines for generator unclear - Contact: Edna Frank

### Tasks
1. Test Task - Contact: Edna Frank
2. Follow-up on New Solar Project - Contact: Edna Frank
```

**Updating Records:**
```
USER: update the last oppty and DOUBLE that bitch!!
ASSISTANT: The opportunity "Test Opportunity" for GenePoint has been successfully updated, and its amount has been doubled to $300,000.00.
```

---

## Key Features

### Enterprise Integration
- **Salesforce CRM**: Complete CRUD operations for all major objects
- **Smart Search**: Email, name, phone search across different record types
- **Relationship Management**: Automatic linking of related records
- **Error Handling**: Comprehensive validation and error recovery

### Multi-Agent Capabilities
- **Agent Discovery**: Automatic detection and registration of specialized agents
- **Health Monitoring**: Continuous health checks and circuit breaker patterns
- **Load Balancing**: Intelligent request routing across available agents
- **Fault Tolerance**: Graceful degradation when agents are unavailable

### Memory & Persistence
- **Conversation Memory**: Automatic summarization with configurable thresholds
- **Structured Memory**: TrustCall-based data extraction to SQLite
- **Cross-Agent Context**: Shared memory across all specialized agents
- **Async Storage**: Thread-safe storage adapters with connection pooling

### Performance & Reliability
- **LLM Caching**: Response caching to reduce API costs and latency
- **Circuit Breakers**: Prevent cascade failures in distributed system
- **Distributed Tracing**: Complete request tracing across agents
- **Cost Tracking**: Token usage monitoring and cost optimization

---

## Adding New Agents

To add a new specialized agent (e.g., Travel, Expense, HR):

1. **Create agent directory:**
   ```bash
   mkdir src/agents/travel
   ```

2. **Implement agent with A2A handler:**
   ```python
   # src/agents/travel/main.py
   from src.a2a import A2AServer, AgentCard
   # ... implement LangGraph workflow with A2A integration
   ```

3. **Create agent-specific tools:**
   ```python
   # src/tools/travel_tools.py
   # Follow Salesforce tools pattern
   ```

4. **Define agent capabilities:**
   ```json
   // agent_registry.json
   {
     "travel-agent": {
       "endpoint": "http://localhost:8002",
       "capabilities": ["flight_booking", "hotel_reservations"]
     }
   }
   ```

5. **Update system startup:**
   ```python
   # start_system.py - add new agent to startup sequence
   ```

---

## Future Vision

### Planned Agents
- **Travel Agent**: Egencia integration for flight/hotel booking
- **Expense Agent**: ChromeRiver integration for receipt processing
- **HR Agent**: Workday integration for feedback and HR tasks
- **OCR Agent**: Document processing and text extraction
- **Time Tracking Agent**: Automated work hour logging

### Advanced Features
- **Multi-User Support**: Tenant isolation and user management
- **Web Interface**: React-based UI for browser access
- **API Gateway**: RESTful API for external integrations
- **Enterprise SSO**: Integration with corporate identity systems
- **Advanced Analytics**: Usage analytics and performance metrics

---

## Contributing

Contributions are welcome! The multi-agent architecture makes it easy to add new capabilities:

1. Fork the repository
2. Create a feature branch for your new agent or enhancement
3. Follow the established patterns for A2A communication
4. Add comprehensive tests for your changes
5. Submit a pull request with detailed documentation

### Development Guidelines
- Follow the A2A protocol for all inter-agent communication
- Use the established logging and error handling patterns
- Implement circuit breakers for external service calls
- Add appropriate caching for expensive operations
- Document new capabilities in agent cards

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.