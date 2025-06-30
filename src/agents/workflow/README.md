# Workflow Agent

The Workflow Agent is a sophisticated orchestration system that coordinates complex multi-step, multi-system operations across Salesforce, Jira, and ServiceNow. It uses native LangGraph compilation for workflow execution and integrates seamlessly with the broader multi-agent orchestrator system.

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
│ WorkflowTools   │    │  Compiled Graphs │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Core Components

- **`main.py`**: Simplified A2A handler using compiled workflows
- **`compiler.py`**: Converts declarative templates to LangGraph graphs
- **`workflow_manager.py`**: Manages compiled workflow graphs
- **`models.py`**: Data models and type definitions
- **`templates.py`**: Pre-built workflow templates

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
- **Purpose**: Automated customer setup with human-in-the-loop
- **Trigger**: `"onboard {opportunity/customer}"`
- **Flow**: Find opportunity → Human selection (if multiple) → Close opportunity → Create case → Parallel setup → Schedule kickoff
- **Systems**: Salesforce → Parallel (Jira + ServiceNow + Tasks)
- **Human Steps**: Opportunity selection when multiple matches found

## Key Features

### Native LangGraph Compilation
- **Direct compilation**: Declarative templates compile to LangGraph StateGraphs
- **Built-in checkpointing**: State persistence via MemorySaver
- **Native interrupts**: Human-in-the-loop using LangGraph's interrupt feature
- **Efficient execution**: No intermediate execution layer

### Advanced Workflow Steps
- **ACTION**: Call another agent via A2A
- **CONDITION**: Conditional branching with multiple operators
- **HUMAN**: Native interrupt-based human interaction
- **PARALLEL**: Concurrent step execution (future enhancement)
- **WAIT**: Event-based waiting
- **SWITCH**: Multi-way branching
- **FOR_EACH**: Iteration over collections

### Smart Integration
- **A2A Protocol**: Direct agent communication
- **Context propagation**: Maintains state across agent calls
- **Intelligent routing**: Keyword and LLM-based workflow selection
- **Real-time monitoring**: Detailed execution tracking

### Business Intelligence
- **LLM-powered reporting**: Executive summaries and detailed analysis
- **Compiled results**: Step results aggregated for final reporting
- **Risk assessment**: Automated identification of issues
- **Action items**: Specific recommendations based on findings

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
    "Native LangGraph human-in-the-loop support",
    "Automatic state persistence and recovery",
    "Parallel and conditional execution",
    "Cross-system orchestration"
  ]
}
```

## Monitoring and Observability

### Logging
- **Component**: `workflow` (logs to `logs/workflow.log`)
- **Key events**: Workflow compilation, execution, interrupts, agent calls
- **Metrics**: Duration, step count, success/failure rates

### Status Monitoring
```bash
# Check workflow status
curl http://localhost:8004/a2a/agent-card

# Via orchestrator tools
"Check workflow status"
"List available workflows"
```

## Development

### Creating New Workflows

1. **Define Template** (`templates.py`):
```python
@staticmethod
def custom_workflow() -> WorkflowDefinition:
    return WorkflowDefinition(
        id="custom_workflow",
        name="Custom Business Process",
        description="Description of the workflow",
        trigger={"type": "manual"},
        steps={
            # Define workflow steps
        }
    )
```

2. **Add to Template Registry**:
```python
@classmethod
def get_all_templates(cls) -> Dict[str, WorkflowDefinition]:
    return {
        # ... existing templates
        "custom_workflow": cls.custom_workflow(),
    }
```

3. **Test Execution**:
```bash
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
    next_step="process_result"
)
```

**CONDITION**: Branching logic
```python
WorkflowStep(
    id="check_result",
    type=StepType.CONDITION,
    name="Check if data found",
    condition={
        "operator": "exists",
        "left": "$find_result"
    },
    true_next="process_data",
    false_next="handle_no_data"
)
```

**HUMAN**: Human interaction with interrupt
```python
WorkflowStep(
    id="select_option",
    type=StepType.HUMAN,
    name="User selection required",
    description="Please select from the options",
    next_step="process_selection"
)
```

### Variable Substitution

Variables can be referenced using `{variable_name}` syntax:
- `{opportunity_name}`: From workflow variables
- `{find_opportunity_result}`: From step results
- `{user_opportunity_selection}`: From human inputs

## API Reference

### A2A Endpoints

- **POST `/a2a`**: Execute workflow
  - **Request**: `{"instruction": "workflow description", "context": {...}}`
  - **Response**: Workflow result or interrupt request

- **GET `/a2a/agent-card`**: Get agent capabilities
  - **Response**: Agent metadata and available workflows

### Integration with Orchestrator

The workflow agent integrates via orchestrator tools:

1. **WorkflowExecutionTool**: Smart workflow routing and execution
2. **WorkflowStatusTool**: Monitor workflow status
3. **WorkflowListTool**: Discover available workflow templates

## Security and Best Practices

### State Management
- **LangGraph Checkpointing**: Built-in state persistence
- **Thread Isolation**: Each workflow runs in separate thread
- **Automatic Recovery**: Resume from interrupts seamlessly

### Error Handling
- **GraphInterrupt**: Properly handled for human-in-the-loop
- **Critical Steps**: Marked steps that must succeed
- **Graceful Degradation**: Non-critical failures logged but continue

### Performance
- **Pre-compilation**: All workflows compiled at startup
- **Efficient State**: Minimal state updates between steps
- **Direct Execution**: No intermediate execution layers

## Troubleshooting

### Common Issues

**Workflow Not Starting**
```bash
# Check agent health
curl http://localhost:8004/a2a/agent-card

# Check compilation logs
tail -f logs/workflow.log | grep "compiling_workflow"
```

**Human Input Not Working**
```bash
# Check for GraphInterrupt handling
tail -f logs/workflow.log | grep "interrupted"

# Verify thread state
tail -f logs/workflow.log | grep "thread_id"
```

**Agent Communication Failures**
```bash
# Check A2A calls
tail -f logs/workflow.log | grep "agent_call"

# Verify agent ports
tail -f logs/a2a_protocol.log
```

### Debug Mode

```bash
# Enable debug logging
export DEBUG_MODE=true

# Watch workflow execution
tail -f logs/workflow.log | jq -r '[.timestamp,.step_id,.message] | @csv'
```

## Architecture Benefits

### Why Compiler-Based Approach?

1. **Native LangGraph**: Uses LangGraph as designed, not building on top
2. **Declarative Templates**: Easy to understand and modify workflows
3. **Type Safety**: Compile-time validation of workflow structure
4. **Performance**: Pre-compiled graphs execute efficiently
5. **Maintainability**: Clear separation of definition and execution

### Future Enhancements

- True parallel execution in PARALLEL steps
- Dynamic workflow generation from natural language
- Workflow versioning and migration
- Visual workflow designer integration
- Advanced condition evaluation with expressions

## Related Documentation

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [A2A Protocol Specification](../../docs/protocols/a2a-protocol.md)
- [Multi-Agent Architecture](../../docs/architecture/multi-agent-architecture.md)