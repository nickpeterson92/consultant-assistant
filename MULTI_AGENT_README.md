# Multi-Agent System Setup & Testing

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Environment Setup
Create a `.env` file in the project root:
```bash
AZURE_OPENAI_ENDPOINT=<your_azure_openai_endpoint>
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=<your_deployment_name>
AZURE_OPENAI_API_VERSION=<api_version>
AZURE_OPENAI_API_KEY=<your_api_key>
SFDC_USER=<your_salesforce_username>
SFDC_PASS=<your_salesforce_password>
SFDC_TOKEN=<your_salesforce_security_token>
```

### 3. Test the System
```bash
# Test without running agents (will show expected network errors)
python3 test_multi_agent.py
```

### 4. Run the Multi-Agent System

#### Option A: All-in-one startup
```bash
python3 start_system.py
```

#### Option B: Manual startup (better for debugging)
```bash
# Terminal 1 - Start Salesforce Agent
python3 salesforce_agent.py

# Terminal 2 - Start Orchestrator (wait for agent to be ready)
python3 orchestrator.py

# Terminal 3 - Test individual agent directly
python3 test_multi_agent.py
```

## Architecture Overview

### Components
1. **Orchestrator Agent** (`orchestrator.py`)
   - Routes user requests to specialized agents
   - Maintains global conversation state
   - Uses Agent2Agent (A2A) protocol for communication

2. **Salesforce Specialized Agent** (`salesforce_agent.py`)
   - Handles all Salesforce CRM operations
   - Runs on port 8001 by default
   - Provides A2A server endpoint

3. **Agent Registry** 
   - Discovers and monitors agent health
   - Configured in `agent_registry.json`

### Communication Flow
```
User Input → Orchestrator → Agent Registry → A2A Protocol → Specialized Agent → Response
```

## Testing & Debugging

### Debug Mode
```bash
# Debug orchestrator
python3 orchestrator.py -d

# Debug Salesforce agent
python3 salesforce_agent.py -d

# Debug with different port
python3 salesforce_agent.py -d --port 8002
```

### Manual Testing
```bash
# Test agent registry
python3 -c "
from src.orchestrator.agent_registry import AgentRegistry
registry = AgentRegistry()
print('Agents:', [a.name for a in registry.list_agents()])
"

# Test A2A communication (requires running agent)
python3 -c "
import asyncio
from src.a2a import A2AClient
async def test():
    async with A2AClient() as client:
        card = await client.get_agent_card('http://localhost:8001/a2a')
        print('Agent:', card['name'])
asyncio.run(test())
"
```

## Current Status

✅ **Working Components:**
- A2A Protocol implementation
- Agent Registry with discovery
- Orchestrator LangGraph coordination  
- Salesforce Agent with full tool integration
- Multi-agent state management
- Configuration and startup scripts

✅ **Tested:**
- Agent registry loading and discovery
- Tool initialization and validation
- CLI argument parsing
- Agent startup processes

⚠️ **Requires Testing with Live Environment:**
- End-to-end A2A communication with running agents
- Salesforce API integration in multi-agent context
- State synchronization between orchestrator and agents
- Error handling and recovery

## Adding New Agents

To add a new specialized agent (e.g., Travel Agent):

1. **Create agent structure:**
```bash
mkdir -p src/agents/travel
```

2. **Implement agent following Salesforce pattern:**
   - `src/agents/travel/main.py` - LangGraph workflow + A2A handler
   - `src/agents/travel/tools/` - Travel-specific tools
   - Agent card definition with capabilities

3. **Register agent:**
   - Add to `agent_registry.json`
   - Update `start_system.py`
   - Create startup script (e.g., `travel_agent.py`)

4. **Update orchestrator:**
   - No changes needed - automatically discovers via registry

## Dependencies Fixed

- ✅ Pydantic field annotations for tools
- ✅ Module import path resolution  
- ✅ A2A protocol HTTP server dependencies
- ✅ LangGraph tool integration patterns

The system is now ready for live testing with proper environment configuration!