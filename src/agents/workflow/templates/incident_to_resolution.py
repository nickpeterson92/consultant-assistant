"""Incident to Resolution workflow template"""

from ..models import WorkflowDefinition, WorkflowStep, StepType


def incident_to_resolution() -> WorkflowDefinition:
    """Template: Full incident lifecycle management"""
    return WorkflowDefinition(
        id="incident_to_resolution",
        name="Incident to Resolution Pipeline",
        description="Manage incident from customer report through resolution and follow-up",
        trigger={"type": "event", "event": "new_critical_case"},
        steps={
            "analyze_case": WorkflowStep(
                id="analyze_case",
                type=StepType.ACTION,
                name="Analyze customer case",
                agent="salesforce-agent",
                instruction="Get full details for case {case_id} including account information",
                next_step="create_incident"
            ),
            "create_incident": WorkflowStep(
                id="create_incident",
                type=StepType.ACTION,
                name="Create ServiceNow incident",
                agent="servicenow-agent",
                instruction="Create a high priority incident for customer {analyze_case_result.account_name} with description: {analyze_case_result.description}",
                next_step="check_if_bug"
            ),
            "check_if_bug": WorkflowStep(
                id="check_if_bug",
                type=StepType.CONDITION,
                name="Determine if this is a bug",
                condition={
                    "operator": "contains",
                    "left": "$analyze_case_result.description",
                    "right": "error"
                },
                true_next="create_jira_bug",
                false_next="assign_to_support"
            ),
            "create_jira_bug": WorkflowStep(
                id="create_jira_bug",
                type=StepType.ACTION,
                name="Create Jira bug ticket",
                agent="jira-agent",
                instruction="Create a bug ticket with title: {analyze_case_result.subject} and description from the incident",
                next_step="link_systems"
            ),
            "assign_to_support": WorkflowStep(
                id="assign_to_support",
                type=StepType.ACTION,
                name="Assign to support team",
                agent="servicenow-agent",
                instruction="Assign incident {create_incident_result.number} to the support team",
                next_step="monitor_resolution"
            ),
            "link_systems": WorkflowStep(
                id="link_systems",
                type=StepType.PARALLEL,
                name="Link records across systems",
                parallel_steps=[
                    "update_case_with_incident",
                    "update_incident_with_jira"
                ],
                next_step="monitor_resolution"
            ),
            "update_case_with_incident": WorkflowStep(
                id="update_case_with_incident",
                name="Update case with incident",
                type=StepType.ACTION,
                agent="salesforce-agent",
                instruction="Update case {case_id} with ServiceNow incident number {create_incident_result.number}"
            ),
            "update_incident_with_jira": WorkflowStep(
                id="update_incident_with_jira",
                name="Update incident with Jira",
                type=StepType.ACTION,
                agent="servicenow-agent",
                instruction="Update incident {create_incident_result.number} with Jira ticket {create_jira_bug_result.key}"
            ),
            "monitor_resolution": WorkflowStep(
                id="monitor_resolution",
                type=StepType.WAIT,
                name="Wait for incident resolution",
                wait_for_event="incident_resolved",
                timeout=86400,  # 24 hours
                next_step="update_customer"
            ),
            "update_customer": WorkflowStep(
                id="update_customer",
                type=StepType.ACTION,
                name="Update customer with resolution",
                agent="salesforce-agent",
                instruction="Update case {case_id} with resolution details and close the case"
            )
        }
    )