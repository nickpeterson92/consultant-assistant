"""Weekly Account Health Check workflow template"""

from ..models import WorkflowDefinition, WorkflowStep, StepType
from ..config import BUSINESS_RULES


def weekly_account_health_check() -> WorkflowDefinition:
    """Template: Weekly health check for key accounts"""
    return WorkflowDefinition(
        id="weekly_account_health_check",
        name="Weekly Account Health Check",
        description="Analyze health metrics for key accounts and alert on issues",
        trigger={"type": "scheduled", "cron": "0 8 * * MON"},  # Mondays at 8am
        steps={
            "get_key_accounts": WorkflowStep(
                id="get_key_accounts",
                type=StepType.ACTION,
                name="Get key accounts",
                agent="salesforce-agent",
                instruction=f"Find all accounts with annual revenue greater than ${BUSINESS_RULES['key_account_revenue_threshold']:,} or marked as strategic",
                on_complete={
                    "condition": {
                        "type": "is_empty",
                        "variable": "get_key_accounts_result"
                    },
                    "if_true": "get_all_active_accounts",
                    "if_false": "analyze_each_account"
                }
            ),
            "get_all_active_accounts": WorkflowStep(
                id="get_all_active_accounts",
                type=StepType.ACTION,
                name="Get all active accounts instead",
                agent="salesforce-agent",
                instruction="No key accounts found. Get all active accounts with any recent activity in the last 30 days",
                next_step="analyze_each_account"
            ),
            "analyze_each_account": WorkflowStep(
                id="analyze_each_account",
                type=StepType.PARALLEL,
                name="Gather health metrics from each system",
                parallel_steps=[
                    "get_salesforce_metrics",
                    "get_servicenow_metrics",
                    "get_jira_metrics"
                ],
                next_step="compile_health_metrics"
            ),
            "get_salesforce_metrics": WorkflowStep(
                id="get_salesforce_metrics",
                type=StepType.ACTION,
                name="Get Salesforce health metrics",
                agent="salesforce-agent",
                instruction="For each account in {get_key_accounts_result}, get open case count and opportunity activity metrics"
            ),
            "get_servicenow_metrics": WorkflowStep(
                id="get_servicenow_metrics",
                type=StepType.ACTION,
                name="Get ServiceNow metrics",
                agent="servicenow-agent",
                instruction="For each account in {get_key_accounts_result}, get incident count and support ticket metrics"
            ),
            "get_jira_metrics": WorkflowStep(
                id="get_jira_metrics",
                type=StepType.ACTION,
                name="Get Jira metrics",
                agent="jira-agent",
                instruction="For each account in {get_key_accounts_result}, get open issue count"
            ),
            "compile_health_metrics": WorkflowStep(
                id="compile_health_metrics",
                type=StepType.WAIT,
                name="Compile health metrics",
                wait_for_event="metrics_compiled",
                metadata={
                    "compile_fields": [
                        "get_salesforce_metrics_result",
                        "get_servicenow_metrics_result",
                        "get_jira_metrics_result"
                    ],
                    "summary_template": "Health metrics compiled for accounts"
                },
                next_step="identify_at_risk"
            ),
            "identify_at_risk": WorkflowStep(
                id="identify_at_risk",
                type=StepType.CONDITION,
                name="Check for at-risk accounts",
                condition={
                    "operator": "less_than",
                    "left": "$compile_health_metrics_result.min_health_score",
                    "right": BUSINESS_RULES["health_score_risk_threshold"]
                },
                true_next="create_action_items",
                false_next="send_summary"
            ),
            "create_action_items": WorkflowStep(
                id="create_action_items",
                type=StepType.ACTION,
                name="Create action items",
                agent="salesforce-agent",
                instruction="Create tasks for account managers for each at-risk account with specific action items",
                next_step="send_alerts"
            ),
            "send_alerts": WorkflowStep(
                id="send_alerts",
                type=StepType.ACTION,
                name="Create alert tasks",
                agent="salesforce-agent",
                instruction="Create high-priority tasks for account managers of at-risk accounts with alert details",
                next_step="send_summary"
            ),
            "send_summary": WorkflowStep(
                id="send_summary",
                type=StepType.WAIT,
                name="Compile weekly health check results",
                wait_for_event="health_check_complete",
                metadata={
                    "compile_fields": [
                        "get_key_accounts_result",
                        "get_all_active_accounts_result",
                        "get_salesforce_metrics_result",
                        "get_servicenow_metrics_result",
                        "get_jira_metrics_result",
                        "create_action_items_result"
                    ],
                    "summary_template": "Weekly account health check complete. Analyzed key accounts."
                }
            )
        }
    )