"""Deal Risk Assessment workflow template"""

from ..models import WorkflowDefinition, WorkflowStep, StepType


def deal_risk_assessment() -> WorkflowDefinition:
    """Template: Assess and act on at-risk deals"""
    return WorkflowDefinition(
        id="deal_risk_assessment",
        name="At-Risk Deal Assessment",
        description="Identify opportunities at risk of not closing and create action plans",
        trigger={"type": "scheduled", "cron": "0 9 * * *"},  # Daily at 9am
        steps={
            "find_opportunities": WorkflowStep(
                id="find_opportunities",
                type=StepType.ACTION,
                name="Find at-risk opportunities",
                agent="salesforce-agent",
                instruction="Find all opportunities closing this month with no activity in the last 14 days",
                on_complete={
                    "condition": {
                        "type": "is_empty",
                        "variable": "find_opportunities_result"
                    },
                    "if_true": "check_all_opportunities",
                    "if_false": "process_each_opportunity"
                }
            ),
            "check_all_opportunities": WorkflowStep(
                id="check_all_opportunities",
                type=StepType.ACTION,
                name="Check all opportunities instead",
                agent="salesforce-agent",
                instruction="No at-risk opportunities found. Get all opportunities closing this quarter with amount > 100000 to review pipeline health",
                next_step="analyze_pipeline_health"
            ),
            "analyze_pipeline_health": WorkflowStep(
                id="analyze_pipeline_health",
                type=StepType.ACTION,
                name="Analyze overall pipeline health",
                agent="salesforce-agent",
                instruction="Analyze the pipeline health metrics for opportunities: {check_all_opportunities_result}",
                next_step="compile_results"
            ),
            "process_each_opportunity": WorkflowStep(
                id="process_each_opportunity",
                type=StepType.PARALLEL,
                name="Analyze each opportunity for blockers",
                parallel_steps=[
                    "check_support_cases",
                    "check_incidents", 
                    "check_jira_issues"
                ],
                next_step="compile_results"
            ),
            "check_support_cases": WorkflowStep(
                id="check_support_cases",
                type=StepType.ACTION,
                name="Check for open support cases",
                agent="salesforce-agent",
                instruction="Find all open cases for the account associated with opportunity {find_opportunities_result}"
            ),
            "check_incidents": WorkflowStep(
                id="check_incidents",
                type=StepType.ACTION,
                name="Check for ServiceNow incidents",
                agent="servicenow-agent",
                instruction="Find all open incidents for the account from opportunity {find_opportunities_result}"
            ),
            "check_jira_issues": WorkflowStep(
                id="check_jira_issues",
                type=StepType.ACTION,
                name="Check for open Jira issues",
                agent="jira-agent",
                instruction="Find all open issues related to the account from opportunity {find_opportunities_result}"
            ),
            "compile_results": WorkflowStep(
                id="compile_results",
                type=StepType.WAIT,  # Use WAIT step to compile results
                name="Compile risk assessment results",
                wait_for_event="compile_complete",  # This will store results and end workflow
                metadata={
                    "compile_fields": [
                        "find_opportunities_result",
                        "check_all_opportunities_result",
                        "analyze_pipeline_health_result",
                        "check_support_cases_result", 
                        "check_incidents_result",
                        "check_jira_issues_result"
                    ],
                    "summary_template": "Risk Assessment Complete: Analyzed opportunities and pipeline health with associated issues."
                }
            )
        }
    )