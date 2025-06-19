# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Multi-Agent System (Current Architecture)
```bash
# Install dependencies (project root)
pip install -r requirements.txt

# Option 1: Start entire system (recommended)
python3 start_system.py

# Option 2: Start components individually
# Terminal 1 - Start Salesforce agent
python3 salesforce_agent.py

# Terminal 2 - Start orchestrator (after agents are running)
python3 orchestrator.py

# Debug mode for any component
python3 orchestrator.py -d
python3 salesforce_agent.py -d --port 8001
```

### Legacy Single-Agent System (Deprecated)
```bash
# Navigate to agent directory
cd src/agent

# Run the original monolithic agent
python main.py

# Run with debug mode
python main.py -d
```

### Environment Setup
Create a `.env` file in the project root with:
```
AZURE_OPENAI_ENDPOINT=<your_azure_openai_endpoint>
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=<your_deployment_name>
AZURE_OPENAI_API_VERSION=<api_version>
AZURE_OPENAI_API_KEY=<your_api_key>
SFDC_USER=<your_salesforce_username>
SFDC_PASS=<your_salesforce_password>
SFDC_TOKEN=<your_salesforce_security_token>
```

### LangGraph Development
```bash
# Run with LangGraph CLI (if available)
langgraph dev

# The graph is defined in langgraph.json pointing to src/agent/main.py:graph
```

## Architecture Overview

### Multi-Agent System Design (Current)
This is a **multi-agent system** using Google's Agent2Agent (A2A) protocol with LangGraph orchestration. The architecture provides scalable enterprise system integration:

1. **Orchestrator Agent**: Routes requests to specialized agents via A2A protocol
2. **Specialized Agents**: Domain-specific LangGraph agents (Salesforce, Travel, Expense, etc.)
3. **A2A Communication**: JSON-RPC over HTTP for inter-agent communication
4. **Global State Management**: Coordinated memory and context across all agents
5. **Agent Registry**: Dynamic discovery and health monitoring of specialized agents

### Legacy Single-Agent Design (Deprecated)
The original **LangGraph-based conversational AI agent** with direct tool integration:

1. **LangGraph State Machine**: Orchestrates conversation flow with conditional routing
2. **Tool System**: Modular enterprise integrations using LangChain BaseTool pattern
3. **Memory Management**: Multi-tiered persistence (session state, conversation summaries, structured records)
4. **Streaming Interface**: Real-time CLI responses with animated output

### Multi-Agent Architecture Components

#### Orchestrator Agent (`src/orchestrator/`)
- **Main LangGraph** (`main.py`): Coordinates user requests and agent responses
- **Agent Registry** (`agent_registry.py`): Discovers, registers, and monitors specialized agents
- **State Manager** (`state_manager.py`): Global memory coordination across agents
- **Agent Caller Tools** (`agent_caller_tools.py`): A2A protocol communication tools

#### Specialized Agents (`src/agents/`)
- **Salesforce Agent** (`salesforce/main.py`): Complete CRM operations
- **Future Agents**: Travel, Expense, HR, OCR (architecture ready for expansion)

#### A2A Protocol Layer (`src/a2a/`)
- **Protocol Implementation** (`protocol.py`): JSON-RPC client/server with A2A message types
- **Agent Cards**: Capability description and endpoint discovery
- **Task Management**: Stateful collaboration entities with artifacts and state updates

#### Multi-Agent Data Flow
User Input → Orchestrator → Agent Registry → A2A Task → Specialized Agent → LangGraph Workflow → A2A Response → Orchestrator → User Response

#### Legacy Components (Single-Agent)
- **Session State**: `StateManager` singleton for cross-conversation persistence
- **Conversation Memory**: Automatic summarization after 6+ messages to manage context  
- **Structured Memory**: TrustCall-based data extraction to SQLite after 6+ turns

### Tool Architecture
Tools follow a consistent pattern in `tools/` directory:
- **Salesforce Tools**: Complete CRUD operations for all major objects (Leads, Accounts, Opportunities, Contacts, Cases, Tasks)
- **OCR Tools**: Document processing for future expense management
- **Extensible Design**: New enterprise systems can be added following the same BaseTool pattern

### Memory & Persistence
- **SQLite Store**: Custom BaseStore implementation (`store/sqlite_store.py`) with namespace-based organization
- **Pydantic Models**: Structured schemas (`store/memory_schemas.py`) for Salesforce data relationships
- **State Schemas**: TypedDict definitions (`utils/states.py`) for LangGraph state management

## Key Implementation Details

### Salesforce Integration
The `tools/salesforce_tools.py` (957 lines) provides comprehensive CRUD operations:
- Each object type (Lead, Account, etc.) has Get/Create/Update tools
- Smart search capabilities (email, name, phone for different objects)
- Relationship management (linking Contacts to Accounts, etc.)
- Comprehensive error handling and validation

### Message Processing
The `utils/helpers.py` handles format conversion between:
- LangChain message objects
- Dictionary representations
- CLI display formatting with animated typing effect

### System Messages & Prompts
The `utils/sys_msg.py` contains carefully crafted prompts:
- **Chatbot System Message**: Main conversational AI instructions with memory context
- **Summary System Message**: Conversation compression instructions
- **TrustCall Instruction**: Structured data extraction prompt

## Working with This Codebase

### Adding New Specialized Agents (Current Multi-Agent System)
1. Create new agent directory in `src/agents/` (e.g., `travel/`, `expense/`)
2. Implement agent `main.py` with LangGraph workflow and A2A handler
3. Create agent-specific tools following the Salesforce pattern
4. Define agent card with capabilities and endpoints
5. Add agent to `agent_registry.json` configuration
6. Update `start_system.py` to include the new agent

### Legacy Enterprise Integration (Single-Agent System)
1. Create new tool file in `tools/` following the Salesforce pattern
2. Add Pydantic models to `store/memory_schemas.py` for data persistence
3. Update `main.py` to include new tools in the tools list
4. Extend TrustCall schema if structured memory is needed

### Modifying Conversation Flow
- LangGraph workflow is defined in `main.py:build_graph()`
- Conditional edges determine routing between nodes
- State updates happen through return dictionaries from node functions

### Memory System Modifications
- Session state via `StateManager` singleton
- Conversation summaries trigger at message count thresholds
- Structured memory extraction uses TrustCall with defined schemas

### Debugging
- Use `-d` flag for comprehensive event logging
- Debug mode shows state transitions, memory contents, and tool executions
- Check `memory_store.db` SQLite file for persistent memory contents

## Database Schema
The SQLite store uses a namespace/key pattern:
- Namespace: `("memory", user_id)`
- Key: Object type (e.g., "AccountList")
- Value: JSON-serialized Pydantic model

Records maintain Salesforce relationships and are automatically updated through conversation processing.