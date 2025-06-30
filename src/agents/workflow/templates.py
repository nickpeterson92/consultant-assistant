"""Pre-built workflow templates for common business processes"""

from typing import Dict
from datetime import datetime, timedelta
from .models import WorkflowDefinition, WorkflowStep, StepType
from .config import BUSINESS_RULES, SERVICENOW_TABLES


class WorkflowTemplates:
    """Library of reusable workflow templates"""
    
    @staticmethod
    def _format_onboarding_tasks_instruction() -> str:
        """Format the onboarding tasks instruction with configurable offsets"""
        offsets = BUSINESS_RULES["onboarding_task_offsets"]
        return (
            f"Create the following Salesforce Tasks: "
            f"1) Subject='Schedule kickoff call' with ActivityDate={offsets['kickoff_call']} days from today, "
            f"2) Subject='Send welcome packet' with ActivityDate={offsets['welcome_packet']} day from today, "
            f"3) Subject='Technical setup' with ActivityDate={offsets['technical_setup']} days from today, "
            f"4) Subject='Training session' with ActivityDate={offsets['training_session']} days from today. "
            "For ALL tasks set: WhatId='{opportunity_id}' (links to Opportunity which auto-populates Account), "
            "Status='Not Started', Priority='Normal'. Use ActivityDate field NOT DueDate. "
            "Use the salesforce_create tool for each task."
        )
    
    @staticmethod
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
    
    @staticmethod
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
    
    @staticmethod
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
    
    @staticmethod
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
    
    @staticmethod
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
                    instruction=WorkflowTemplates._format_onboarding_tasks_instruction()
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
    
    @classmethod
    def get_all_templates(cls) -> Dict[str, WorkflowDefinition]:
        """Get all available workflow templates"""
        return {
            "deal_risk_assessment": cls.deal_risk_assessment(),
            "incident_to_resolution": cls.incident_to_resolution(),
            "customer_360_report": cls.customer_360_report(),
            "weekly_account_health_check": cls.weekly_account_health_check(),
            "new_customer_onboarding": cls.new_customer_onboarding()
        }