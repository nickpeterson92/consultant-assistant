"""Cleaned up new_customer_onboarding workflow using structured extraction"""

from typing import Dict
from datetime import datetime, timedelta
from .models import WorkflowDefinition, WorkflowStep, StepType
from .config import BUSINESS_RULES, SERVICENOW_TABLES


class CleanWorkflowTemplates:
    """Refactored workflow templates with clean patterns"""
    
    @staticmethod
    def new_customer_onboarding() -> WorkflowDefinition:
        """Template: Automated new customer onboarding - CLEAN VERSION"""
        return WorkflowDefinition(
            id="new_customer_onboarding",
            name="New Customer Onboarding",
            description="Automated workflow for onboarding new customers",
            trigger={"type": "event", "event": "opportunity_closed_won"},
            variables={"account_name": "", "opportunity_id": ""},
            steps={
                # PHASE 1: Find and select account
                "find_account": WorkflowStep(
                    id="find_account",
                    type=StepType.ACTION,
                    name="Find account by name",
                    agent="salesforce-agent",
                    instruction="Search for accounts with name containing '{account_name}'. Use LIKE query with wildcards. Return ALL matches with their ID, full name, and type. IMPORTANT: Clearly state how many accounts were found.",
                    next_step="check_multiple_accounts",
                    critical=True
                ),
                
                "check_multiple_accounts": WorkflowStep(
                    id="check_multiple_accounts",
                    type=StepType.CONDITION,
                    name="Check if multiple accounts found",
                    condition={
                        "operator": "not_contains",
                        "left": "$find_account_result",
                        "right": "found 1"
                    },
                    true_next="select_account",
                    false_next="extract_account_id"
                ),
                
                "select_account": WorkflowStep(
                    id="select_account",
                    type=StepType.HUMAN,
                    name="Select correct account",
                    description="Multiple accounts found. Please select the correct one.",
                    next_step="extract_account_id",
                    metadata={
                        "context_from": ["find_account"],
                        "prompt": "Please select which account to use for onboarding"
                    }
                ),
                
                "extract_account_id": WorkflowStep(
                    id="extract_account_id",
                    type=StepType.EXTRACT,
                    name="Extract selected account ID",
                    extract_from="find_account_result",
                    extract_prompt="Extract the account ID from either the single account found or the user's selection. Return ONLY the Salesforce Account ID (starts with 001).",
                    next_step="find_opportunities",
                    critical=True
                ),
                
                # PHASE 2: Find and select opportunity
                "find_opportunities": WorkflowStep(
                    id="find_opportunities",
                    type=StepType.ACTION,
                    name="Find opportunities for account",
                    agent="salesforce-agent",
                    instruction="Search for ALL opportunities for account ID {extract_account_id_result}. Return all matches with their ID, name, stage, and amount. IMPORTANT: Clearly state how many opportunities were found.",
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
                    false_next="extract_opportunity_id"
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
                
                "extract_opportunity_id": WorkflowStep(
                    id="extract_opportunity_id",
                    type=StepType.EXTRACT,
                    name="Extract selected opportunity ID",
                    extract_from="find_opportunities_result",
                    extract_prompt="Extract the opportunity ID from either the single opportunity found or the user's selection. Return ONLY the Salesforce Opportunity ID (starts with 006).",
                    next_step="update_opportunity_stage",
                    critical=True
                ),
                
                # PHASE 3: Update opportunity and get full details
                "update_opportunity_stage": WorkflowStep(
                    id="update_opportunity_stage",
                    type=StepType.ACTION,
                    name="Update opportunity to Closed Won",
                    agent="salesforce-agent",
                    instruction="Update opportunity ID {extract_opportunity_id_result} to stage 'Closed Won' with Probability=100. Use the salesforce_update tool.",
                    next_step="get_opportunity_details",
                    critical=True
                ),
                
                "get_opportunity_details": WorkflowStep(
                    id="get_opportunity_details",
                    type=StepType.ACTION,
                    name="Get full opportunity and account details",
                    agent="salesforce-agent",
                    instruction="Get the full opportunity record for ID {extract_opportunity_id_result} including its Account relationship. Return the opportunity name, opportunity ID, account ID, and account name.",
                    next_step="extract_onboarding_details",
                    critical=True
                ),
                
                # PHASE 4: Extract all details at once using structured extraction
                "extract_onboarding_details": WorkflowStep(
                    id="extract_onboarding_details",
                    type=StepType.EXTRACT,
                    name="Extract all onboarding details",
                    extract_from="get_opportunity_details_result",
                    extract_prompt="Extract the account and opportunity information from this Salesforce data",
                    extract_model="OnboardingDetails",  # Uses TrustCall with our model
                    next_step="create_onboarding_case",
                    critical=True
                ),
                
                # PHASE 5: Create tracking case
                "create_onboarding_case": WorkflowStep(
                    id="create_onboarding_case",
                    type=StepType.ACTION,
                    name="Create onboarding case",
                    agent="salesforce-agent",
                    instruction="Create a new Salesforce Case with Subject='Customer Onboarding - {extract_onboarding_details_result.account_name}', Type='Other', Priority='High', Description='New customer onboarding initiated from closed won opportunity {extract_onboarding_details_result.opportunity_name}', AccountId='{extract_onboarding_details_result.account_id}'.",
                    next_step="setup_jira_project",
                    critical=True
                ),
                
                # PHASE 6: Setup systems sequentially (avoiding PARALLEL issues)
                "setup_jira_project": WorkflowStep(
                    id="setup_jira_project",
                    type=StepType.ACTION,
                    name="Create Jira project",
                    agent="jira-agent",
                    instruction="Create a new Jira project with name '{extract_onboarding_details_result.account_name} Onboarding', project key from first 3-5 letters of account name, type 'business'.",
                    next_step="setup_servicenow_company"
                ),
                
                "setup_servicenow_company": WorkflowStep(
                    id="setup_servicenow_company",
                    type=StepType.ACTION,
                    name="Setup ServiceNow company",
                    agent="servicenow-agent",
                    instruction=f"Create a new company record in ServiceNow {SERVICENOW_TABLES['company']} table with name '{{extract_onboarding_details_result.account_name}}', set as customer=true.",
                    next_step="create_onboarding_tasks"
                ),
                
                "create_onboarding_tasks": WorkflowStep(
                    id="create_onboarding_tasks",
                    type=StepType.ACTION,
                    name="Create onboarding tasks",
                    agent="salesforce-agent",
                    instruction=f"Create 4 Salesforce Tasks for opportunity {{{extract_onboarding_details_result.opportunity_id}}}: 1) Schedule kickoff call (+{BUSINESS_RULES['onboarding_task_offsets']['kickoff_call']}d), 2) Send welcome packet (+{BUSINESS_RULES['onboarding_task_offsets']['welcome_packet']}d), 3) Technical setup (+{BUSINESS_RULES['onboarding_task_offsets']['technical_setup']}d), 4) Training session (+{BUSINESS_RULES['onboarding_task_offsets']['training_session']}d). All with Status='Not Started', Priority='Normal'.",
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
                            "setup_jira_project_result",
                            "setup_servicenow_company_result",
                            "create_onboarding_tasks_result"
                        ],
                        "summary_template": "Onboarding complete for {extract_onboarding_details_result.account_name}"
                    }
                )
            }
        )