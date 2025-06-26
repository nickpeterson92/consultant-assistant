# Orchestrator

The orchestrator is the central coordination hub for the multi-agent system, implemented using LangGraph for stateful conversation management and agent routing.

## Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              ORCHESTRATOR                                  │
│  ┌──────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐    │
│  │   CLI Interface  │  │   LangGraph     │  │   Memory System         │    │
│  │   User Input     │  │   State Mgmt    │  │   SQLite Storage        │    │
│  │   Animated UI    │  │   Conversation  │  │   Thread Persistence    │    │
│  └──────────────────┘  └─────────────────┘  └─────────────────────────┘    │
│                                   │                                        │
│  ┌────────────────────────────────┴────────────────────────────────────┐   │
│  │                        AGENT ROUTING LAYER                          │   │
│  │                                                                     │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │   │
│  │  │ SalesforceAgent │  │   JiraAgent     │  │  ServiceNowAgent    │  │   │
│  │  │    Port 8001    │  │   Port 8002     │  │    Port 8003        │  │   │
│  │  │   CRM Tools     │  │  Issue Tracking │  │   ITSM Tools        │  │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                        │
│  ┌────────────────────────────────┴────────────────────────────────────┐   │
│  │                         A2A PROTOCOL LAYER                          │   │
│  │                                                                     │   │
│  │  • JSON-RPC 2.0 Communication    • Circuit Breakers & Retries       │   │
│  │  • Connection Pooling            • Service Discovery                │   │
│  │  • Agent Health Monitoring       • Load Balancing                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
```

## User Request Flow

```
User Input → Orchestrator → Specialized Agents → Response
     │             │               │               │
     │             │               │               │
     ▼             ▼               ▼               ▼
 "Get Acme    LangGraph       A2A Protocol    Salesforce
  account"    determines   →   delegates to  →   Agent
              agent type       agent via           │
                              JSON-RPC 2.0        │
                                   │              ▼
                                   │        Execute tools
                                   │        Return results
                                   │              │
                                   ▼              ▼
                              Format response ← Process data
                              Add to memory   ← Structure output
                                   │              │
                                   ▼              │
                              Display to user ←───┘
```

## Core Components

### Main Entry Point
- **File**: `src/orchestrator/main.py`
- **Purpose**: CLI interface, conversation loop, system initialization
- **Key Functions**:
  - `initialize_orchestrator()`: Discover and register agents
  - `main()`: Interactive conversation loop with animated UI

### Graph Builder
- **File**: `src/orchestrator/graph_builder.py`  
- **Purpose**: LangGraph workflow definition and agent tool registration
- **Key Components**:
  - `build_orchestrator_graph()`: Constructs the LangGraph workflow
  - `orchestrator_graph`: Executable graph instance
  - Agent tool registration (Salesforce, Jira, ServiceNow)

### State Management
- **File**: `src/orchestrator/state.py`
- **Purpose**: LangGraph state schema and message handling
- **Schema**: Messages, user context, conversation metadata

### Background Tasks
- **File**: `src/orchestrator/background_tasks.py`
- **Purpose**: Memory summarization, performance tracking
- **Triggers**: Every 3 tool calls, 2 agent calls, or 180 seconds

### Conversation Handler
- **File**: `src/orchestrator/conversation_handler.py`
- **Purpose**: Message processing, memory injection, response formatting

### LLM Handler
- **File**: `src/orchestrator/llm_handler.py`
- **Purpose**: Azure OpenAI integration, model configuration

## Agent Integration

The orchestrator communicates with specialized agents via:
- **Agent Caller Tools**: `src/orchestrator/agent_caller_tools.py`
- **A2A Protocol**: JSON-RPC 2.0 over HTTP
- **Agent Registry**: Service discovery and health monitoring

### Available Agents
- **SalesforceAgentTool**: CRM operations (port 8001)
- **JiraAgentTool**: Issue tracking (port 8002)  
- **ServiceNowAgentTool**: ITSM operations (port 8003)

## Memory System

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             MEMORY ARCHITECTURE                             │
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐  │
│  │  Short-term     │    │   Long-term     │    │   Entity Tracking       │  │
│  │  Recent msgs    │    │   Summaries     │    │   Accounts, Contacts    │  │
│  │  (last 10-15)   │    │   Background    │    │   Issues, Changes       │  │
│  └─────────────────┘    └─────────────────┘    └─────────────────────────┘  │
│           │                       │                        │               │
│           ▼                       ▼                        ▼               │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                        SQLITE STORAGE                                   │  │
│  │                                                                         │  │
│  │  • AsyncStoreAdapter (167 lines - simplified)                          │  │
│  │  • Thread-specific state snapshots                                     │  │
│  │  • Serialized LangChain messages                                       │  │
│  │  • User-scoped memory namespaces                                       │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

- **Storage**: SQLite via `AsyncStoreAdapter`
- **Scope**: User-scoped with thread-specific conversations
- **Persistence**: Full state snapshots, serialized messages
- **Triggers**: Automatic summarization based on activity thresholds

## Configuration

Key settings in `system_config.json`:
```json
{
  "conversation": {
    "typing_effect_enabled": true,
    "animated_capabilities_enabled": true
  },
  "llm": {
    "temperature": 0.1,
    "max_tokens": 4000
  }
}
```

## Development

### Running the Orchestrator
```bash
python3 orchestrator.py [-d|--debug]
python3 start_system.py  # Full system startup
```

### Adding New Agents
1. Create agent tool in `agent_caller_tools.py`
2. Register tool in `graph_builder.py`
3. Add agent entry to registry
4. Update port constants in `config/constants.py`

### Testing Agent Communication
```python
# Test A2A connectivity
curl http://localhost:8001/a2a/agent-card  # Salesforce
curl http://localhost:8002/a2a/agent-card  # Jira
curl http://localhost:8003/a2a/agent-card  # ServiceNow
```

## Common Patterns

### User Request Flow
1. User input → `conversation_handler.py`
2. Memory injection → Recent context added
3. LLM processing → Agent tool selection
4. A2A delegation → Specialized agent execution
5. Response formatting → User-friendly output

### Memory Management
- **Short-term**: Recent messages (last 10-15)
- **Long-term**: Summarized conversation history
- **Entity tracking**: People, accounts, opportunities, issues

### Error Handling
- A2A circuit breakers for agent failures
- Graceful degradation when agents unavailable
- User-friendly error messages with retry suggestions

## Troubleshooting

### Common Issues
- **Agent not responding**: Check agent ports with `netstat -ln | grep 800[1-3]`
- **Memory errors**: Verify SQLite database permissions
- **LLM failures**: Check Azure OpenAI configuration and quotas

### Debug Logging
Enable with `-d` flag:
- A2A communication in `logs/a2a_protocol.log`
- Memory operations in `logs/storage.log`
- General orchestrator activity in `logs/orchestrator.log`