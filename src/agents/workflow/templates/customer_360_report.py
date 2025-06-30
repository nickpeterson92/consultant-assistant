"""Customer 360 Report workflow template"""

from ..models import WorkflowDefinition, WorkflowStep, StepType


def customer_360_report() -> WorkflowDefinition:
    """Template: Generate comprehensive customer 360 view"""
    return WorkflowDefinition(
        id="customer_360_report",
        name="Customer 360 Report Generation",
        description="Gather all information about a customer across systems",
        trigger={"type": "manual"},
        variables={"account_name": ""},
        steps={
            "validate_input": WorkflowStep(
                id="validate_input",
                type=StepType.CONDITION,
                name="Check if account name provided",
                condition={
                    "operator": "exists",
                    "left": "$account_name"
                },
                true_next="gather_data",
                false_next="end"
            ),
            "gather_data": WorkflowStep(
                id="gather_data",
                type=StepType.PARALLEL,
                name="Gather data from all systems",
                parallel_steps=[
                    "get_salesforce_data",
                    "get_jira_data",
                    "get_servicenow_data"
                ],
                next_step="generate_report"
            ),
            "get_salesforce_data": WorkflowStep(
                id="get_salesforce_data",
                type=StepType.ACTION,
                name="Get Salesforce data",
                agent="salesforce-agent",
                instruction="Get all records (account, contacts, opportunities, cases) for {account_name}",
                on_complete={
                    "condition": {
                        "type": "response_contains",
                        "value": "enterprise"
                    },
                    "if_true": "get_enterprise_metrics",
                    "if_false": None  # Continue to parallel steps
                }
            ),
            "get_enterprise_metrics": WorkflowStep(
                id="get_enterprise_metrics",
                type=StepType.ACTION,
                name="Get additional enterprise metrics",
                agent="salesforce-agent",
                instruction="Get detailed enterprise metrics including contract values, SLAs, and executive contacts for {account_name}",
                skip_if={
                    "type": "is_empty",
                    "variable": "get_salesforce_data_result"
                }
            ),
            "get_jira_data": WorkflowStep(
                id="get_jira_data",
                type=StepType.ACTION,
                name="Get Jira data",
                agent="jira-agent",
                instruction="Find all issues and projects related to {account_name}"
            ),
            "get_servicenow_data": WorkflowStep(
                id="get_servicenow_data",
                type=StepType.ACTION,
                name="Get ServiceNow data",
                agent="servicenow-agent",
                instruction="Find all incidents, changes, and requests for {account_name}"
            ),
            "generate_report": WorkflowStep(
                id="generate_report",
                type=StepType.WAIT,
                name="Compile 360 report data",
                wait_for_event="report_compile_complete",
                metadata={
                    "compile_fields": [
                        "get_salesforce_data_result",
                        "get_jira_data_result", 
                        "get_servicenow_data_result"
                    ],
                    "summary_template": "Customer 360 data compilation complete for {account_name}"
                }
            )
        }
    )