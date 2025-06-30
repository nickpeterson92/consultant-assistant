"""Clean customer onboarding workflow with simplified variable handling"""

from .models import WorkflowDefinition, WorkflowStep, StepType
from .config import BUSINESS_RULES, SERVICENOW_TABLES


def new_customer_onboarding() -> WorkflowDefinition:
    """Clean version of customer onboarding workflow"""
    return WorkflowDefinition(
        id="new_customer_onboarding",
        name="New Customer Onboarding",
        description="Automated workflow for onboarding new customers",
        trigger={"type": "event", "event": "opportunity_closed_won"},
        variables={"account_name": "", "opportunity_id": ""},
        steps={
            # PHASE 1: Find and extract opportunity ID
            "find_opportunities": WorkflowStep(
                id="find_opportunities",
                type=StepType.ACTION,
                name="Find opportunities",
                agent="salesforce-agent",
                instruction="Search for opportunities with name containing '{opportunity_id}' OR opportunity ID '{opportunity_id}'. Return ALL matches with ID, name, stage, account name, and account ID.",
                next_step="check_multiple_opportunities",
                critical=True
            ),
            
            "check_multiple_opportunities": WorkflowStep(
                id="check_multiple_opportunities",
                type=StepType.CONDITION,
                name="Check if multiple opportunities found",
                condition={
                    "operator": "not_contains",
                    "left": "$find_opportunities_result",
                    "right": "found 1"
                },
                true_next="select_opportunity",
                false_next="extract_selected_opportunity_id"
            ),
            
            "select_opportunity": WorkflowStep(
                id="select_opportunity",
                type=StepType.HUMAN,
                name="Select correct opportunity",
                description="Multiple opportunities found. Please select the correct one.",
                next_step="extract_selected_opportunity_id",
                metadata={
                    "context_from": ["find_opportunities"],
                    "prompt": "Please select which opportunity to use for onboarding"
                }
            ),
            
            "extract_selected_opportunity_id": WorkflowStep(
                id="extract_selected_opportunity_id",
                type=StepType.EXTRACT,
                name="Extract opportunity ID",
                extract_from="find_opportunities_result",
                extract_prompt="Extract the opportunity ID. If user selected one, use their selection from '{select_opportunity_response}'. Otherwise extract the single opportunity ID. Return ONLY the ID starting with 006.",
                next_step="update_opportunity_stage",
                critical=True
            ),
            
            # PHASE 2: Update opportunity and get full details
            "update_opportunity_stage": WorkflowStep(
                id="update_opportunity_stage",
                type=StepType.ACTION,
                name="Update opportunity to Closed Won",
                agent="salesforce-agent",
                instruction="Update opportunity ID {extract_selected_opportunity_id_result} to stage 'Closed Won' with Probability=100.",
                next_step="get_opportunity_details",
                critical=True
            ),
            
            "get_opportunity_details": WorkflowStep(
                id="get_opportunity_details",
                type=StepType.ACTION,
                name="Get full opportunity and account details",
                agent="salesforce-agent",
                instruction="Get the full opportunity record for ID {extract_selected_opportunity_id_result} including its Account relationship. Return opportunity name, opportunity ID, account ID, and account name clearly labeled.",
                next_step="extract_onboarding_details",
                critical=True
            ),
            
            # PHASE 3: Extract all details using structured extraction
            "extract_onboarding_details": WorkflowStep(
                id="extract_onboarding_details",
                type=StepType.EXTRACT,
                name="Extract all onboarding details",
                extract_from="get_opportunity_details_result",
                extract_prompt="Extract the account and opportunity information",
                extract_model="OnboardingDetails",  # This flattens to account_id, account_name, etc.
                next_step="create_onboarding_case",
                critical=True
            ),
            
            # PHASE 4: Create tracking case
            "create_onboarding_case": WorkflowStep(
                id="create_onboarding_case",
                type=StepType.ACTION,
                name="Create onboarding case",
                agent="salesforce-agent",
                instruction="Create a new Salesforce Case with Subject='Customer Onboarding - {account_name}', Type='Other', Priority='High', Description='New customer onboarding initiated from closed won opportunity {opportunity_name}', AccountId='{account_id}'.",
                next_step="create_jira_project",
                critical=True
            ),
            
            # PHASE 5: Setup systems (sequential to avoid parallel extraction issues)
            "create_jira_project": WorkflowStep(
                id="create_jira_project",
                type=StepType.ACTION,
                name="Create Jira project",
                agent="jira-agent",
                instruction="Create a new Jira project with name '{account_name} Onboarding', project key from first 3-5 letters of account name (uppercase, no special chars), type 'business'.",
                next_step="setup_servicenow_company"
            ),
            
            "setup_servicenow_company": WorkflowStep(
                id="setup_servicenow_company",
                type=StepType.ACTION,
                name="Setup ServiceNow company",
                agent="servicenow-agent",
                instruction=f"Create a new company record in ServiceNow {SERVICENOW_TABLES['company']} table with name '{{account_name}}', set as customer=true.",
                next_step="create_onboarding_tasks"
            ),
            
            "create_onboarding_tasks": WorkflowStep(
                id="create_onboarding_tasks",
                type=StepType.ACTION,
                name="Create onboarding tasks",
                agent="salesforce-agent",
                instruction=(
                    f"Create the following Salesforce Tasks: "
                    f"1) Subject='Schedule kickoff call' with ActivityDate={BUSINESS_RULES['onboarding_task_offsets']['kickoff_call']} days from today, "
                    f"2) Subject='Send welcome packet' with ActivityDate={BUSINESS_RULES['onboarding_task_offsets']['welcome_packet']} day from today, "
                    f"3) Subject='Technical setup' with ActivityDate={BUSINESS_RULES['onboarding_task_offsets']['technical_setup']} days from today, "
                    f"4) Subject='Training session' with ActivityDate={BUSINESS_RULES['onboarding_task_offsets']['training_session']} days from today. "
                    "For ALL tasks set: WhatId='{opportunity_id}' (links to Opportunity), "
                    "Status='Not Started', Priority='Normal'. Use ActivityDate field NOT DueDate."
                ),
                next_step="schedule_kickoff_meeting"
            ),
            
            "schedule_kickoff_meeting": WorkflowStep(
                id="schedule_kickoff_meeting",
                type=StepType.ACTION,
                name="Create kickoff meeting task",
                agent="salesforce-agent",
                instruction="Create a Salesforce Task with Subject='Schedule kickoff meeting - {account_name}', ActivityDate=tomorrow, Priority='High', WhatId='{opportunity_id}', Status='Not Started'.",
                next_step="complete_onboarding"
            ),
            
            "complete_onboarding": WorkflowStep(
                id="complete_onboarding",
                type=StepType.WAIT,
                name="Complete onboarding setup",
                wait_for_event="onboarding_complete",
                metadata={
                    "compile_fields": [
                        "create_onboarding_case_result",
                        "create_jira_project_result",
                        "setup_servicenow_company_result",
                        "create_onboarding_tasks_result",
                        "schedule_kickoff_meeting_result"
                    ],
                    "summary_template": "Onboarding complete for {account_name}"
                }
            )
        }
    )