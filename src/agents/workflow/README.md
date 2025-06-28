# Workflow Agent

The Workflow Agent is a sophisticated orchestration system that coordinates complex multi-step, multi-system operations across Salesforce, Jira, and ServiceNow. It operates as both a standalone agent and integrates seamlessly with the broader multi-agent orchestrator system.

## Quick Start

### Running the Workflow Agent

```bash
# As part of the full system
python3 start_system.py

# Standalone for development
python3 workflow_agent.py --port 8004
```

### Basic Usage

```bash
# Execute a workflow via the orchestrator
"Run a deal risk assessment"
"Execute weekly account health check"
"Start customer onboarding for ACME Corp"
```

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Orchestrator  │    │  Workflow Agent  │    │  Other Agents   │
│                 │────│                  │────│ (SF/JIRA/SN)    │
│ WorkflowTools   │    │  Engine + State  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Core Components

- **`main.py`**: LangGraph-based agent with A2A protocol integration
- **`engine.py`**: Workflow execution engine with state management
- **`models.py`**: Data models and type definitions
- **`templates.py`**: Pre-built workflow templates
- **`workflow_tools.py`**: Orchestrator integration tools

## Available Workflows

### 1. Deal Risk Assessment
- **Purpose**: Identify at-risk opportunities and blockers
- **Trigger**: `"check for at-risk deals"` or scheduled daily at 9am
- **Flow**: Find stale opportunities → Analyze blockers (parallel) → Report
- **Systems**: Salesforce + ServiceNow + Jira

### 2. Incident to Resolution
- **Purpose**: End-to-end incident management
- **Trigger**: `"create incident"` or event-driven (critical case)
- **Flow**: Analyze case → Create incident → Route bugs → Link systems → Monitor
- **Systems**: Salesforce → ServiceNow → Jira (conditional)

### 3. Customer 360 Report
- **Purpose**: Comprehensive customer data gathering
- **Trigger**: `"generate customer report for {account}"`
- **Flow**: Parallel data collection → Compile enterprise report
- **Systems**: Salesforce + Jira + ServiceNow (parallel)

### 4. Weekly Account Health Check
- **Purpose**: Proactive account monitoring
- **Trigger**: `"run account health check"` or scheduled Mondays at 8am
- **Flow**: Get accounts → Parallel metrics → Risk assessment → Actions
- **Systems**: All systems for comprehensive health metrics

### 5. New Customer Onboarding
- **Purpose**: Automated customer setup
- **Trigger**: Event-driven (opportunity closed won)
- **Flow**: Get opportunity → Create case → Parallel setup → Schedule kickoff
- **Systems**: Salesforce → Parallel (Jira + ServiceNow + Tasks)

## Key Features

### Advanced Workflow Engine
- **Multi-step execution**: ACTION, CONDITION, WAIT, PARALLEL, HUMAN, SWITCH, FOR_EACH
- **Conditional branching**: Multiple condition evaluation types
- **Parallel processing**: Concurrent step execution
- **State persistence**: Resume workflows after interruption
- **Error handling**: Retry logic with exponential backoff

### Smart Integration
- **A2A Protocol**: Seamless agent communication
- **Context propagation**: Maintains conversation state across agents
- **Intelligent routing**: LLM-powered workflow selection
- **Real-time monitoring**: Detailed execution tracking

### Business Intelligence
- **LLM-powered reporting**: Executive summaries and detailed analysis
- **Risk assessment**: Automated identification of issues and blockers
- **Action items**: Specific recommendations based on findings
- **Compliance**: Audit trail and execution history

## Configuration

### Environment Variables
```bash
# Inherited from orchestrator system
AZURE_OPENAI_ENDPOINT=<endpoint>
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=<deployment>
AZURE_OPENAI_API_VERSION=<version>
AZURE_OPENAI_API_KEY=<key>
```

### Agent Registry
The agent automatically registers with the orchestrator:
```json
{
  "name": "workflow-agent",
  "endpoint": "http://localhost:8004",
  "capabilities": [
    "Execute predefined workflow templates",
    "Handle asynchronous workflow execution",
    "Manage workflow state and resumption",
    "Coordinate multi-system operations",
    "Support human-in-the-loop workflows"
  ]
}
```

## Monitoring and Observability

### Logging
- **Component**: `workflow` (logs to `logs/workflow.log`)
- **Key events**: Workflow start/complete, step execution, agent calls
- **Metrics**: Duration, step count, success/failure rates

### Status Monitoring
```bash
# Check workflow status
curl http://localhost:8004/a2a/agent-card

# Via orchestrator tools
"Check workflow status for ID wf_123"
"List available workflows"
```

## Development

### Creating New Workflows

1. **Define Template** (`templates.py`):
```python
CUSTOM_WORKFLOW = WorkflowDefinition(
    id="custom_workflow",
    name="Custom Business Process",
    description="Description of the workflow",
    triggers=["custom trigger phrase"],
    steps=[
        # Define workflow steps
    ]
)
```

2. **Add to Templates**:
```python
WORKFLOW_TEMPLATES = {
    # ... existing templates
    "custom_workflow": CUSTOM_WORKFLOW,
}
```

3. **Test Execution**:
```python
# Test via orchestrator
"Execute custom business process"
```

### Step Types

**ACTION**: Call another agent
```python
WorkflowStep(
    id="call_salesforce",
    type=StepType.ACTION,
    name="Get account data",
    agent="salesforce-agent",
    instruction="Find account {account_name}",
    on_complete="next_step"
)
```

**CONDITION**: Branching logic
```python
WorkflowStep(
    id="check_result",
    type=StepType.CONDITION,
    name="Check if data found",
    condition={
        "type": "count_greater_than",
        "variable": "salesforce_result",
        "value": 0
    },
    on_complete={
        "if_true": "process_data",
        "if_false": "handle_no_data"
    }
)
```

**PARALLEL**: Concurrent execution
```python
WorkflowStep(
    id="gather_data",
    type=StepType.PARALLEL,
    name="Gather data from all systems",
    parallel_steps=["get_salesforce", "get_jira", "get_servicenow"],
    on_complete="compile_results"
)
```

### Testing

```bash
# Run workflow tests
python3 test_workflows.py

# Test specific workflow
python3 -c "
from src.agents.workflow.engine import WorkflowEngine
from src.agents.workflow.templates import DEAL_RISK_ASSESSMENT
engine = WorkflowEngine()
await engine.execute_workflow(DEAL_RISK_ASSESSMENT, {})
"
```

## API Reference

### A2A Endpoints

- **POST `/a2a`**: Execute workflow
  - **Request**: `{"instruction": "workflow description", "context": {...}}`
  - **Response**: Workflow execution result or status

- **GET `/a2a/agent-card`**: Get agent capabilities
  - **Response**: Agent metadata and available workflows

### Integration with Orchestrator

The workflow agent integrates via three orchestrator tools:

1. **WorkflowExecutionTool**: Intelligent workflow routing and execution
2. **WorkflowStatusTool**: Monitor running workflows by ID
3. **WorkflowListTool**: Discover available workflow templates

## Security and Best Practices

### State Management
- **Persistence**: All workflow state stored in SQLite with encryption
- **Isolation**: Each workflow instance runs in isolated context
- **Cleanup**: Automatic cleanup of completed workflows after 30 days

### Error Handling
- **Retry Logic**: Exponential backoff for transient failures
- **Circuit Breaker**: Protection against cascading failures
- **Graceful Degradation**: Partial execution with clear error reporting

### Performance
- **Concurrent Execution**: Parallel steps for independent operations
- **Resource Limits**: Maximum execution time and step count per workflow
- **Memory Management**: Efficient state serialization and cleanup

## Troubleshooting

### Common Issues

**Workflow Not Starting**
```bash
# Check agent health
curl http://localhost:8004/a2a/agent-card

# Check logs
tail -f logs/workflow.log
```

**Agent Communication Failures**
```bash
# Verify agent registry
curl http://localhost:8000/agent-status

# Check A2A protocol logs
tail -f logs/a2a_protocol.log
```

**State Persistence Issues**
```bash
# Check SQLite database
sqlite3 memory_store.db "SELECT * FROM store WHERE namespace LIKE 'workflow%'"

# Check storage logs
tail -f logs/storage.log
```

### Debug Mode

```python
# Enable detailed logging
import logging
logging.getLogger('workflow').setLevel(logging.DEBUG)

# Run with debug output
python3 workflow_agent.py --port 8004 --debug
```

## Related Documentation

- [Workflow Engine Architecture](../../docs/components/workflow-engine.md)
- [Workflow Templates Guide](../../docs/guides/workflow-templates.md)
- [A2A Protocol Specification](../../docs/protocols/a2a-protocol.md)
- [Multi-Agent Architecture](../../docs/architecture/multi-agent-architecture.md)