"""New Customer Onboarding workflow template"""

from ..models import WorkflowDefinition, WorkflowStep, StepType
from ..config import SERVICENOW_TABLES
from .base import format_onboarding_tasks_instruction


def new_customer_onboarding() -> WorkflowDefinition:
    """Template: Automated new customer onboarding"""
    return WorkflowDefinition(
        id="new_customer_onboarding",
        name="New Customer Onboarding",
        description="Automated workflow for onboarding new customers",
        trigger={"type": "event", "event": "opportunity_closed_won"},
        variables={},
        steps={
            "find_account": WorkflowStep(
                id="find_account",
                type=StepType.ACTION,
                name="Find account by name",
                agent="salesforce-agent",
                instruction="Based on the context '{original_instruction}', search for the relevant account. Look for any company name mentioned (e.g., 'Express Logistics', 'Acme Corp', etc.). Use LIKE query with wildcards to find accounts. Return ALL matches with their ID, full name, and type. IMPORTANT: Clearly state how many accounts were found (e.g., 'I found 1 account' or 'I found 3 accounts').",
                next_step="check_account_matches",
                critical=True
            ),
            "check_account_matches": WorkflowStep(
                id="check_account_matches",
                type=StepType.CONDITION,
                name="Check if multiple accounts found",
                condition={
                    "type": "response_contains",
                    "value": "found"  # Look for pattern like "found 2" or "found 3"
                },
                true_next="check_if_multiple_accounts",
                false_next="find_opportunities"
            ),
            "check_if_multiple_accounts": WorkflowStep(
                id="check_if_multiple_accounts",
                type=StepType.CONDITION,
                name="Confirm multiple account matches",
                condition={
                    "operator": "not_contains",
                    "left": "$find_account_result",
                    "right": "found 1"  # If it says "found 1", it's single
                },
                true_next="select_account",
                false_next="find_opportunities"
            ),
            "select_account": WorkflowStep(
                id="select_account",
                type=StepType.HUMAN,
                name="Select correct account",
                description="Multiple accounts found. Please select the correct one.",
                next_step="find_opportunities",
                metadata={
                    "context_from": ["find_account"],
                    "prompt": "Please select which account to use for onboarding"
                }
            ),
            "find_opportunities": WorkflowStep(
                id="find_opportunities",
                type=StepType.ACTION,
                name="Find opportunities for account",
                agent="salesforce-agent",
                instruction="Based on the account search results in {find_account_result} and user selection '{select_account_response}' (if provided), identify the account ID. Then search for ALL opportunities associated with that account. Return all matches with their ID, full name, stage, and amount. IMPORTANT: Clearly state how many opportunities were found.",
                next_step="check_opportunity_matches",
                critical=True
            ),
            "check_opportunity_matches": WorkflowStep(
                id="check_opportunity_matches",
                type=StepType.CONDITION,
                name="Check if multiple opportunities found",
                condition={
                    "type": "response_contains",
                    "value": "found"
                },
                true_next="check_if_multiple_opportunities",
                false_next="update_opportunity_stage"
            ),
            "check_if_multiple_opportunities": WorkflowStep(
                id="check_if_multiple_opportunities",
                type=StepType.CONDITION,
                name="Confirm multiple opportunity matches",
                condition={
                    "operator": "not_contains",
                    "left": "$find_opportunities_result",
                    "right": "found 1"
                },
                true_next="select_opportunity",
                false_next="extract_single_opportunity_id"
            ),
            "select_opportunity": WorkflowStep(
                id="select_opportunity",
                type=StepType.HUMAN,
                name="Select correct opportunity",
                description="Multiple opportunities found. Please select the correct one.",
                next_step="extract_opportunity_id",
                metadata={
                    "context_from": ["find_opportunities"],
                    "prompt": "Please select which opportunity to use for onboarding"
                }
            ),
            "extract_single_opportunity_id": WorkflowStep(
                id="extract_single_opportunity_id",
                type=StepType.EXTRACT,
                name="Extract single opportunity ID",
                extract_from="find_opportunities_result",
                extract_prompt="Extract the opportunity ID from the data. Since only 1 opportunity was found, extract its ID (starts with 006). Return ONLY the opportunity ID, nothing else.",
                next_step="set_opportunity_id",
                critical=True
            ),
            "extract_opportunity_id": WorkflowStep(
                id="extract_opportunity_id",
                type=StepType.EXTRACT,
                name="Extract selected opportunity ID",
                extract_from="select_opportunity_response",
                extract_prompt="Extract the opportunity ID from the user's selection: '{select_opportunity_response}'. Look for patterns like 'ID: 006...' or just '006...'. If the user provided the full ID starting with 006, return ONLY that ID. If they said '2' or 'the second one', look at the list in this data: {find_opportunities_result} and return the ID of the second opportunity. Return ONLY the opportunity ID, nothing else.",
                next_step="set_opportunity_id",
                critical=True
            ),
            "set_opportunity_id": WorkflowStep(
                id="set_opportunity_id",
                type=StepType.EXTRACT,
                name="Set opportunity ID for update",
                extract_from="extract_single_opportunity_id_result",
                extract_prompt="Return the opportunity ID from either {extract_single_opportunity_id_result} or {extract_opportunity_id_result}. Return whichever one is not empty/null. Return ONLY the ID.",
                next_step="update_opportunity_stage",
                critical=True
            ),
            "update_opportunity_stage": WorkflowStep(
                id="update_opportunity_stage",
                type=StepType.ACTION,
                name="Update opportunity to Closed Won",
                agent="salesforce-agent",
                instruction="Update opportunity {set_opportunity_id_result} with StageName='Closed Won' and Probability=100",
                next_step="get_opportunity_details",
                critical=True
            ),
            "get_opportunity_details": WorkflowStep(
                id="get_opportunity_details",
                type=StepType.ACTION,
                name="Get opportunity and account details",
                agent="salesforce-agent",
                instruction="Get the full opportunity record for ID {set_opportunity_id_result} including its Account relationship. Use salesforce_get tool with object_type='Opportunity' and record_id='{set_opportunity_id_result}'. Return the opportunity name, opportunity ID, account ID, and account name.",
                next_step="extract_account_details",
                critical=True  # Must find account to proceed
            ),
            "extract_account_details": WorkflowStep(
                id="extract_account_details",
                type=StepType.EXTRACT,
                name="Extract all onboarding details",
                extract_from="get_opportunity_details_result",
                extract_prompt="Extract the account and opportunity information from this Salesforce data",
                extract_model="OnboardingDetails",
                next_step="create_onboarding_case",
                critical=True
            ),
            "create_onboarding_case": WorkflowStep(
                id="create_onboarding_case",
                type=StepType.ACTION,
                name="Create onboarding case",
                agent="salesforce-agent",
                instruction="Create a new Salesforce Case record with Subject='Customer Onboarding - {account_name}', Type='Other', Priority='High', Description='New customer onboarding initiated from closed won opportunity {opportunity_name}', AccountId='{account_id}'. Use the salesforce_create tool.",
                next_step="setup_systems",
                critical=True  # Must create case to track onboarding
            ),
            "setup_systems": WorkflowStep(
                id="setup_systems",
                type=StepType.PARALLEL,
                name="Setup customer in all systems",
                parallel_steps=[
                    "create_jira_project",
                    "setup_servicenow_account",
                    "create_onboarding_tasks"
                ],
                next_step="schedule_kickoff"
            ),
            "create_jira_project": WorkflowStep(
                id="create_jira_project",
                type=StepType.ACTION,
                name="Create Jira project",
                agent="jira-agent",
                instruction="Create a new Jira project with name '{account_name} Onboarding', project key should be first 3-5 letters of {account_name} in uppercase (no spaces or special chars), project type 'business', and description 'Customer onboarding project for {account_name}'"
            ),
            "setup_servicenow_account": WorkflowStep(
                id="setup_servicenow_account",
                type=StepType.ACTION,
                name="Setup ServiceNow account",
                agent="servicenow-agent",
                instruction=f"Create a new company record in ServiceNow {SERVICENOW_TABLES['company']} table with name '{{account_name}}', set as customer=true, vendor=false"
            ),
            "create_onboarding_tasks": WorkflowStep(
                id="create_onboarding_tasks",
                type=StepType.ACTION,
                name="Create onboarding tasks",
                agent="salesforce-agent",
                instruction=format_onboarding_tasks_instruction()
            ),
            "schedule_kickoff": WorkflowStep(
                id="schedule_kickoff",
                type=StepType.ACTION,
                name="Create kickoff meeting task",
                agent="salesforce-agent",
                instruction="Create a Salesforce Task with Subject='Schedule kickoff meeting - {account_name}', ActivityDate=tomorrow, Priority='High', WhatId='{opportunity_id}' (links to Opportunity which auto-populates Account), Status='Not Started'. Use the salesforce_create tool.",
                next_step="send_welcome_package"
            ),
            "send_welcome_package": WorkflowStep(
                id="send_welcome_package",
                type=StepType.WAIT,
                name="Complete onboarding setup",
                wait_for_event="onboarding_complete",
                metadata={
                    "compile_fields": [
                        "create_onboarding_case_result",
                        "create_jira_project_result",
                        "setup_servicenow_account_result",
                        "create_onboarding_tasks_result",
                        "schedule_kickoff_result"
                    ],
                    "summary_template": "Onboarding setup complete for new customer"
                }
            )
        }
    )