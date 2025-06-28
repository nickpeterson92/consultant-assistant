# Workflow Templates Guide

This guide provides comprehensive documentation for creating, customizing, and deploying workflow templates in the multi-agent orchestration system. Workflow templates define reusable business processes that coordinate operations across Salesforce, Jira, and ServiceNow.

## Template Architecture

### Template Structure

Every workflow template follows a standardized structure:

```python
@dataclass
class WorkflowDefinition:
    id: str                          # Unique template identifier
    name: str                        # Human-readable name
    description: str                 # Purpose and functionality
    triggers: List[str]              # Natural language triggers
    steps: List[WorkflowStep]        # Execution sequence
    required_variables: List[str]    # Required input parameters
    metadata: Optional[Dict[str, Any]] = None  # Additional configuration
```

### Basic Template Example

```python
SIMPLE_WORKFLOW = WorkflowDefinition(
    id="simple_example",
    name="Simple Data Retrieval",
    description="Retrieve account data from Salesforce",
    triggers=["get account info", "find account details"],
    required_variables=["account_name"],
    steps=[
        WorkflowStep(
            id="get_account",
            type=StepType.ACTION,
            name="Retrieve account information",
            agent="salesforce-agent",
            instruction="Find account {account_name}",
            on_complete="end"
        )
    ]
)
```

## Available Templates

### 1. Deal Risk Assessment

**Purpose**: Identify at-risk opportunities and potential blockers across all systems.

```python
DEAL_RISK_ASSESSMENT = WorkflowDefinition(
    id="deal_risk_assessment",
    name="At-Risk Deal Assessment",
    description="Comprehensive analysis of deals at risk with multi-system blocker identification",
    triggers=[
        "check for at-risk deals",
        "identify risky opportunities", 
        "deal risk assessment",
        "find stale deals"
    ],
    steps=[
        # Step 1: Find stale opportunities
        WorkflowStep(
            id="find_opportunities",
            type=StepType.ACTION,
            name="Find at-risk opportunities",
            agent="salesforce-agent",
            instruction="Find all opportunities closing this month with no activity in the last 14 days",
            on_complete="process_each_opportunity"
        ),
        
        # Step 2: Parallel blocker analysis
        WorkflowStep(
            id="process_each_opportunity",
            type=StepType.PARALLEL,
            name="Analyze each opportunity for blockers",
            parallel_steps=["check_support_cases", "check_incidents", "check_jira_issues"],
            on_complete="compile_results"
        ),
        
        # Parallel Step 2a: Check Salesforce cases
        WorkflowStep(
            id="check_support_cases",
            type=StepType.ACTION,
            name="Check for open support cases",
            agent="salesforce-agent",
            instruction="Find all open cases for the account associated with opportunity {find_opportunities_result}",
        ),
        
        # Parallel Step 2b: Check ServiceNow incidents
        WorkflowStep(
            id="check_incidents",
            type=StepType.ACTION,
            name="Check for ServiceNow incidents",
            agent="servicenow-agent",
            instruction="Find all open incidents for the account from opportunity {find_opportunities_result}",
        ),
        
        # Parallel Step 2c: Check Jira issues
        WorkflowStep(
            id="check_jira_issues",
            type=StepType.ACTION,
            name="Check for open Jira issues",
            agent="jira-agent",
            instruction="Find all open issues related to the account from opportunity {find_opportunities_result}",
        ),
        
        # Step 3: Compile and analyze results
        WorkflowStep(
            id="compile_results",
            type=StepType.WAIT,
            name="Compile risk assessment results",
            metadata={
                "compile_fields": [
                    "find_opportunities_result",
                    "check_support_cases_result", 
                    "check_incidents_result",
                    "check_jira_issues_result"
                ],
                "summary_template": "Risk assessment complete for opportunities closing this month"
            }
        )
    ],
    metadata={
        "triggers": {
            "scheduled": {"cron": "0 9 * * 1-5", "timezone": "UTC"},
            "manual": True
        },
        "expected_duration": "2-5 minutes",
        "business_impact": "high"
    }
)
```

### 2. Incident to Resolution

**Purpose**: End-to-end incident management with automatic system linking.

```python
INCIDENT_TO_RESOLUTION = WorkflowDefinition(
    id="incident_to_resolution",
    name="Incident to Resolution Workflow",
    description="Complete incident lifecycle from Salesforce case to ServiceNow incident with optional Jira bug creation",
    triggers=[
        "create incident from case",
        "escalate to incident management",
        "start incident workflow"
    ],
    required_variables=["case_id"],
    steps=[
        # Step 1: Analyze the case
        WorkflowStep(
            id="analyze_case",
            type=StepType.ACTION,
            name="Analyze Salesforce case details",
            agent="salesforce-agent", 
            instruction="Get detailed information for case {case_id} including priority, description, and account",
            on_complete="create_incident"
        ),
        
        # Step 2: Create ServiceNow incident
        WorkflowStep(
            id="create_incident",
            type=StepType.ACTION,
            name="Create ServiceNow incident",
            agent="servicenow-agent",
            instruction="Create a new incident based on case details: {analyze_case_result}",
            on_complete="check_bug_needed"
        ),
        
        # Step 3: Conditional bug creation
        WorkflowStep(
            id="check_bug_needed",
            type=StepType.CONDITION,
            name="Determine if bug creation is needed", 
            condition={
                "type": "response_contains",
                "variable": "analyze_case_result",
                "value": "bug"
            },
            on_complete={
                "if_true": "create_jira_bug",
                "if_false": "link_systems"
            }
        ),
        
        # Step 4a: Create Jira bug (conditional)
        WorkflowStep(
            id="create_jira_bug",
            type=StepType.ACTION,
            name="Create Jira bug ticket",
            agent="jira-agent",
            instruction="Create a bug ticket linked to incident: {create_incident_result}",
            on_complete="link_systems"
        ),
        
        # Step 4b: Link all systems
        WorkflowStep(
            id="link_systems",
            type=StepType.ACTION,
            name="Update case with incident and bug links",
            agent="salesforce-agent",
            instruction="Update case {case_id} with incident number {create_incident_result} and bug {create_jira_bug_result}",
            on_complete="monitor_resolution"
        ),
        
        # Step 5: Set up monitoring
        WorkflowStep(
            id="monitor_resolution",
            type=StepType.ACTION,
            name="Set up resolution monitoring",
            agent="servicenow-agent", 
            instruction="Set up monitoring for incident resolution and escalation procedures",
        )
    ],
    metadata={
        "triggers": {
            "event": {"type": "case_priority_critical"},
            "manual": True
        },
        "expected_duration": "3-7 minutes",
        "business_impact": "critical"
    }
)
```

### 3. Customer 360 Report

**Purpose**: Comprehensive customer data aggregation across all systems.

```python
CUSTOMER_360_REPORT = WorkflowDefinition(
    id="customer_360_report", 
    name="Customer 360 Comprehensive Report",
    description="Generate comprehensive customer view aggregating data from Salesforce, Jira, and ServiceNow",
    triggers=[
        "generate customer report",
        "customer 360 view", 
        "comprehensive account analysis"
    ],
    required_variables=["account_name"],
    steps=[
        # Step 1: Parallel data collection
        WorkflowStep(
            id="gather_all_data",
            type=StepType.PARALLEL,
            name="Gather comprehensive customer data",
            parallel_steps=["get_salesforce_data", "get_jira_data", "get_servicenow_data"],
            on_complete="generate_report"
        ),
        
        # Parallel Step 1a: Salesforce data
        WorkflowStep(
            id="get_salesforce_data",
            type=StepType.ACTION,
            name="Gather Salesforce customer data",
            agent="salesforce-agent",
            instruction="Get comprehensive data for account {account_name}: opportunities, cases, contacts, tasks, and recent activity"
        ),
        
        # Parallel Step 1b: Jira data
        WorkflowStep(
            id="get_jira_data", 
            type=StepType.ACTION,
            name="Gather Jira project data",
            agent="jira-agent",
            instruction="Find all Jira projects, issues, and activity related to {account_name}"
        ),
        
        # Parallel Step 1c: ServiceNow data
        WorkflowStep(
            id="get_servicenow_data",
            type=StepType.ACTION,
            name="Gather ServiceNow service data", 
            agent="servicenow-agent",
            instruction="Find all incidents, changes, and service requests for {account_name}"
        ),
        
        # Step 2: Generate comprehensive report
        WorkflowStep(
            id="generate_report",
            type=StepType.WAIT,
            name="Generate Customer 360 Report",
            metadata={
                "compile_fields": ["get_salesforce_data_result", "get_jira_data_result", "get_servicenow_data_result"],
                "summary_template": "Customer 360 Report for {account_name}",
                "report_type": "executive_summary"
            }
        )
    ],
    metadata={
        "triggers": {"manual": True},
        "expected_duration": "2-4 minutes", 
        "business_impact": "medium"
    }
)
```

### 4. Weekly Account Health Check

**Purpose**: Proactive monitoring of key account health metrics.

```python
WEEKLY_ACCOUNT_HEALTH_CHECK = WorkflowDefinition(
    id="weekly_account_health_check",
    name="Weekly Account Health Assessment", 
    description="Proactive assessment of account health across all systems with risk identification",
    triggers=[
        "run account health check",
        "weekly account review",
        "check account health"
    ],
    steps=[
        # Step 1: Get key accounts
        WorkflowStep(
            id="get_key_accounts",
            type=StepType.ACTION,
            name="Identify key accounts for health check",
            agent="salesforce-agent",
            instruction="Find all enterprise accounts with annual revenue > $1M or strategic importance",
            on_complete="assess_each_account"
        ),
        
        # Step 2: Process each account
        WorkflowStep(
            id="assess_each_account",
            type=StepType.FOR_EACH,
            name="Assess health of each key account",
            collection_variable="get_key_accounts_result",
            item_variable="current_account",
            iteration_step_id="account_health_check",
            on_complete="identify_risks"
        ),
        
        # Step 2a: Individual account health check  
        WorkflowStep(
            id="account_health_check",
            type=StepType.PARALLEL,
            name="Comprehensive account health assessment",
            parallel_steps=["check_opportunity_health", "check_service_health", "check_project_health"]
        ),
        
        # Parallel health checks
        WorkflowStep(
            id="check_opportunity_health",
            type=StepType.ACTION,
            name="Check opportunity pipeline health",
            agent="salesforce-agent",
            instruction="Analyze opportunity health for {current_account}: pipeline value, close rates, activity levels"
        ),
        
        WorkflowStep(
            id="check_service_health", 
            type=StepType.ACTION,
            name="Check service delivery health",
            agent="servicenow-agent", 
            instruction="Analyze service metrics for {current_account}: incident frequency, resolution times, satisfaction"
        ),
        
        WorkflowStep(
            id="check_project_health",
            type=StepType.ACTION,
            name="Check project delivery health",
            agent="jira-agent",
            instruction="Analyze project health for {current_account}: delivery timelines, velocity, blockers"
        ),
        
        # Step 3: Risk identification
        WorkflowStep(
            id="identify_risks",
            type=StepType.CONDITION,
            name="Identify accounts requiring attention",
            condition={
                "type": "response_contains",
                "variable": "assess_each_account_results", 
                "value": "risk"
            },
            on_complete={
                "if_true": "create_action_items", 
                "if_false": "generate_summary"
            }
        ),
        
        # Step 4a: Create action items for at-risk accounts
        WorkflowStep(
            id="create_action_items",
            type=StepType.ACTION,
            name="Create action items for at-risk accounts",
            agent="salesforce-agent",
            instruction="Create tasks and alerts for accounts requiring immediate attention based on health assessment",
            on_complete="generate_summary"
        ),
        
        # Step 4b: Generate executive summary
        WorkflowStep(
            id="generate_summary",
            type=StepType.WAIT,
            name="Generate weekly health report",
            metadata={
                "compile_fields": ["assess_each_account_results", "create_action_items_result"],
                "summary_template": "Weekly Account Health Report - {current_date}",
                "report_type": "executive_dashboard"
            }
        )
    ],
    metadata={
        "triggers": {
            "scheduled": {"cron": "0 8 * * 1", "timezone": "UTC"},  # Mondays at 8 AM
            "manual": True
        },
        "expected_duration": "5-10 minutes",
        "business_impact": "high"
    }
)
```

### 5. New Customer Onboarding

**Purpose**: Automated customer onboarding process coordination.

```python
NEW_CUSTOMER_ONBOARDING = WorkflowDefinition(
    id="new_customer_onboarding",
    name="New Customer Onboarding Process",
    description="Automated onboarding workflow triggered by closed-won opportunities",
    triggers=[
        "start customer onboarding",
        "new customer setup", 
        "onboard new client"
    ],
    required_variables=["opportunity_id"], 
    steps=[
        # Step 1: Get opportunity details
        WorkflowStep(
            id="get_opportunity_details",
            type=StepType.ACTION,
            name="Retrieve opportunity and account details",
            agent="salesforce-agent",
            instruction="Get complete details for opportunity {opportunity_id} including account, contacts, and contract details",
            on_complete="create_onboarding_case"
        ),
        
        # Step 2: Create onboarding case
        WorkflowStep(
            id="create_onboarding_case",
            type=StepType.ACTION,
            name="Create customer onboarding case",
            agent="salesforce-agent", 
            instruction="Create an onboarding case for the new customer based on opportunity details: {get_opportunity_details_result}",
            on_complete="setup_systems"
        ),
        
        # Step 3: Parallel system setup
        WorkflowStep(
            id="setup_systems",
            type=StepType.PARALLEL,
            name="Set up customer in all systems",
            parallel_steps=["setup_jira_project", "setup_service_account", "create_onboarding_tasks"],
            on_complete="schedule_kickoff"
        ),
        
        # Parallel Step 3a: Jira project setup
        WorkflowStep(
            id="setup_jira_project",
            type=StepType.ACTION,
            name="Create customer project in Jira",
            agent="jira-agent",
            instruction="Create a new project for customer onboarding based on details: {get_opportunity_details_result}"
        ),
        
        # Parallel Step 3b: ServiceNow account setup  
        WorkflowStep(
            id="setup_service_account",
            type=StepType.ACTION,
            name="Set up service management account",
            agent="servicenow-agent",
            instruction="Create service account and entitlements for new customer: {get_opportunity_details_result}"
        ),
        
        # Parallel Step 3c: Onboarding task creation
        WorkflowStep(
            id="create_onboarding_tasks",
            type=StepType.ACTION,
            name="Create onboarding task checklist",
            agent="salesforce-agent",
            instruction="Create comprehensive onboarding task list for account managers and customer success team"
        ),
        
        # Step 4: Schedule kickoff meeting
        WorkflowStep(
            id="schedule_kickoff",
            type=StepType.ACTION,
            name="Schedule customer kickoff meeting",
            agent="salesforce-agent",
            instruction="Schedule kickoff meeting and send calendar invites to all stakeholders including customer contacts from {get_opportunity_details_result}"
        ),
        
        # Step 5: Summary and handoff
        WorkflowStep(
            id="complete_onboarding_setup",
            type=StepType.WAIT,
            name="Complete onboarding setup",
            metadata={
                "compile_fields": [
                    "create_onboarding_case_result",
                    "setup_jira_project_result", 
                    "setup_service_account_result",
                    "create_onboarding_tasks_result",
                    "schedule_kickoff_result"
                ],
                "summary_template": "Customer onboarding initiated for {opportunity.account.name}",
                "report_type": "onboarding_summary"
            }
        )
    ],
    metadata={
        "triggers": {
            "event": {"type": "opportunity_closed_won"},
            "manual": True
        },
        "expected_duration": "3-6 minutes",
        "business_impact": "high"
    }
)
```

## Step Types Reference

### ACTION Steps

Execute operations via agent communication:

```python
WorkflowStep(
    id="unique_step_id",
    type=StepType.ACTION,
    name="Human readable step name",
    agent="target-agent-name",              # Agent to call
    instruction="Instruction with {variables}",  # Task description
    timeout=30,                             # Optional timeout (seconds)
    retry_count=3,                          # Optional retry attempts  
    critical=True,                          # Optional: workflow fails if this fails
    on_complete="next_step_id"              # Next step or conditional routing
)
```

### CONDITION Steps

Implement branching logic:

```python
WorkflowStep(
    id="condition_step",
    type=StepType.CONDITION,
    name="Check some condition",
    condition={
        "type": "condition_type",           # See condition types below
        "variable": "variable_name",        # Variable to evaluate
        "value": "comparison_value"         # Target value (if needed)
    },
    on_complete={
        "if_true": "true_branch_step",
        "if_false": "false_branch_step"
    }
)
```

**Available Condition Types:**
- `count_greater_than`: Check if collection size > value
- `response_contains`: Check if response contains text
- `has_error`: Check if variable contains error
- `is_empty`: Check if variable is empty/null
- `value_equals`: Check if variable equals specific value

### PARALLEL Steps

Execute multiple steps concurrently:

```python
WorkflowStep(
    id="parallel_step",
    type=StepType.PARALLEL,
    name="Execute multiple operations",
    parallel_steps=[                       # List of step IDs to run in parallel
        "step_1_id",
        "step_2_id", 
        "step_3_id"
    ],
    on_complete="next_step_id"
)
```

### WAIT Steps

Handle compilation and delays:

```python
# Result compilation
WorkflowStep(
    id="compile_step",
    type=StepType.WAIT,
    name="Compile results",
    metadata={
        "compile_fields": ["step1_result", "step2_result"],  # Variables to compile
        "summary_template": "Summary for {variable}",        # Optional template
        "report_type": "executive_summary"                   # Report format
    },
    on_complete="next_step"
)

# Timed delay
WorkflowStep(
    id="delay_step", 
    type=StepType.WAIT,
    name="Wait for processing",
    duration=30,                           # Seconds to wait
    on_complete="next_step"
)
```

### FOR_EACH Steps

Iterate over collections:

```python
WorkflowStep(
    id="iteration_step",
    type=StepType.FOR_EACH,
    name="Process each item",
    collection_variable="items_list",      # Variable containing collection
    item_variable="current_item",          # Variable name for each item
    iteration_step_id="process_item",      # Step to execute for each item
    max_iterations=50,                     # Safety limit
    on_complete="next_step"
)
```

### HUMAN Steps

Human intervention points:

```python
WorkflowStep(
    id="approval_step",
    type=StepType.HUMAN,
    name="Manager approval required", 
    instruction="Please review and approve: {data_to_review}",
    timeout=3600,                          # Timeout for human response
    on_complete="approval_received"
)
```

### SWITCH Steps

Multi-way branching:

```python
WorkflowStep(
    id="switch_step",
    type=StepType.SWITCH,
    name="Route based on priority",
    switch_variable="priority_level",
    cases={
        "high": "urgent_handling",
        "medium": "standard_handling", 
        "low": "batch_processing"
    },
    default_case="standard_handling"
)
```

## Variable Management

### Variable Naming Conventions

- **Input variables**: `account_name`, `case_id`, `priority_level`
- **Step results**: `{step_id}_result` (automatically created)
- **Compiled results**: `{step_id}_compiled` (for WAIT steps with compilation)
- **Error markers**: `{step_id}_error` (for failed non-critical steps)

### Variable Substitution

Templates support sophisticated variable substitution:

```python
# Simple substitution
"Find account {account_name}"

# Nested object access  
"Process opportunity {opportunity.account.name}"

# Error-safe substitution (returns error message if variable missing)
"Update case {case_id} with details {step_result}"

# Conditional substitution
"Priority is {priority_level if priority_level else 'not set'}"
```

### Special Variables

- `orchestrator_state_snapshot`: Contains orchestrator conversation context
- `workflow_id`: Current workflow instance ID
- `workflow_name`: Current workflow name
- `current_date`: Current date/time
- `user_context`: User information and permissions

## Triggers and Scheduling

### Manual Triggers

Natural language phrases that activate workflows:

```python
triggers=[
    "check for at-risk deals",           # Primary trigger
    "identify risky opportunities",      # Alternative phrasing
    "deal risk assessment",              # Formal name
    "find stale deals"                   # Casual phrasing
]
```

### Scheduled Triggers

Cron-based scheduling for automated execution:

```python
metadata={
    "triggers": {
        "scheduled": {
            "cron": "0 9 * * 1-5",       # 9 AM weekdays
            "timezone": "UTC"
        },
        "manual": True                    # Also allow manual triggering
    }
}
```

### Event Triggers

Reactive triggers based on system events:

```python
metadata={
    "triggers": {
        "event": {
            "type": "opportunity_closed_won",
            "conditions": {
                "amount": {"greater_than": 100000}
            }
        }
    }
}
```

## Best Practices

### Template Design

1. **Single Responsibility**: Each workflow should have one clear business purpose
2. **Idempotent Steps**: Design steps to be safely retryable
3. **Error Boundaries**: Use critical flags to control failure behavior
4. **Resource Limits**: Respect timeout and iteration constraints

### Step Organization

1. **Sequential Logic**: Use clear step sequencing for dependent operations
2. **Parallel Optimization**: Leverage parallel steps for independent operations  
3. **Conditional Branching**: Use conditions to handle different scenarios
4. **Error Handling**: Plan for both expected and unexpected failures

### Variable Management

1. **Clear Naming**: Use descriptive variable names
2. **Data Validation**: Validate inputs at workflow start
3. **Memory Efficiency**: Avoid storing large datasets in variables
4. **Context Preservation**: Maintain necessary context across steps

### Testing and Validation

1. **Unit Testing**: Test individual steps in isolation
2. **Integration Testing**: Test complete workflow execution
3. **Error Scenarios**: Test failure conditions and recovery
4. **Performance Testing**: Validate execution time and resource usage

## Deployment Process

### 1. Template Development

```python
# 1. Define the workflow template
NEW_WORKFLOW = WorkflowDefinition(
    id="new_workflow",
    # ... define all properties
)

# 2. Add to template registry
WORKFLOW_TEMPLATES = {
    # ... existing templates
    "new_workflow": NEW_WORKFLOW,
}
```

### 2. Testing

```python
# Test template validation
from src.agents.workflow.engine import WorkflowEngine

engine = WorkflowEngine(store_adapter)
validation_result = engine.validate_workflow(NEW_WORKFLOW)

# Test execution
test_variables = {"test_input": "test_value"}
result = await engine.execute_workflow(NEW_WORKFLOW, test_variables)
```

### 3. Registration

Templates are automatically discovered and registered when the workflow agent starts. No additional registration step required.

### 4. Monitoring

Monitor new workflow performance through:
- Execution logs in `logs/workflow.log`
- Success/failure rates
- Average execution time
- Resource usage patterns

## Troubleshooting

### Common Issues

**Template Not Found**
```python
# Check template registration
from src.agents.workflow.templates import WORKFLOW_TEMPLATES
print(list(WORKFLOW_TEMPLATES.keys()))
```

**Variable Substitution Errors**
```python
# Check variable names and nesting
# Ensure variables exist before substitution
# Use error-safe substitution patterns
```

**Step Execution Failures**
```python
# Check agent availability
# Verify instruction formatting
# Review timeout settings
# Check error logs for specific failures
```

**Performance Issues**
```python
# Optimize parallel execution
# Reduce variable storage size
# Implement appropriate timeouts
# Monitor resource usage
```

### Debug Tools

```python
# Enable debug logging
import logging
logging.getLogger('workflow').setLevel(logging.DEBUG)

# Check workflow status
engine.get_workflow_status(instance_id)

# Review execution history
instance = await engine.load_instance(instance_id)
print(instance.step_history)
```

## Related Documentation

- [Workflow Engine Architecture](../components/workflow-engine.md)
- [Workflow Agent README](../../src/agents/workflow/README.md)
- [A2A Protocol](../protocols/a2a-protocol.md)
- [Multi-Agent Architecture](../architecture/multi-agent-architecture.md)