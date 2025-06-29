"""Pre-built workflow templates for common business processes"""

from typing import Dict
from datetime import datetime, timedelta
from .models import WorkflowDefinition, WorkflowStep, StepType


class WorkflowTemplates:
    """Library of reusable workflow templates"""
    
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
                    instruction="Find all accounts with annual revenue greater than $1M or marked as strategic",
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
                        "right": 70
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
            variables={"opportunity_name": "", "account_name": ""},
            steps={
                "find_opportunity": WorkflowStep(
                    id="find_opportunity",
                    type=StepType.ACTION,
                    name="Find opportunity by name",
                    agent="salesforce-agent",
                    instruction="Search for opportunities with name containing '{opportunity_name}'. Use LIKE query with wildcards. Return ALL matches with their ID, full name, stage, and amount. IMPORTANT: Clearly state how many opportunities were found (e.g., 'I found 1 opportunity' or 'I found 3 opportunities').",
                    next_step="check_opportunity_matches",
                    critical=True
                ),
                "check_opportunity_matches": WorkflowStep(
                    id="check_opportunity_matches",
                    type=StepType.CONDITION,
                    name="Check if multiple opportunities found",
                    condition={
                        "type": "response_contains",
                        "value": "found"  # Look for pattern like "found 2" or "found 3"
                    },
                    true_next="check_if_multiple",
                    false_next="check_opportunity_stage"
                ),
                "check_if_multiple": WorkflowStep(
                    id="check_if_multiple",
                    type=StepType.CONDITION,
                    name="Confirm multiple matches",
                    condition={
                        "operator": "not_contains",
                        "left": "$find_opportunity_result",
                        "right": "found 1"  # If it says "found 1", it's single
                    },
                    true_next="select_opportunity",
                    false_next="check_opportunity_stage"
                ),
                "select_opportunity": WorkflowStep(
                    id="select_opportunity",
                    type=StepType.HUMAN,
                    name="Select correct opportunity",
                    description="Multiple opportunities found. Please select the correct one.",
                    next_step="check_opportunity_stage"
                ),
                "check_opportunity_stage": WorkflowStep(
                    id="check_opportunity_stage",
                    type=StepType.ACTION,
                    name="Check opportunity stage",
                    agent="salesforce-agent",
                    instruction="The user was asked to select an opportunity and responded with: '{user_opportunity_selection}'. The available opportunities were: {available_opportunities}. Based on the user's response, determine which opportunity they selected and get its current stage. The user might have said 'the first one', 'option 2', used the opportunity name, or provided an ID. Return the opportunity ID, name, current stage, and amount. DO NOT update the stage yet.",
                    next_step="check_if_closed_won",
                    critical=True
                ),
                "check_if_closed_won": WorkflowStep(
                    id="check_if_closed_won",
                    type=StepType.CONDITION,
                    name="Check if already Closed Won",
                    condition={
                        "operator": "contains",
                        "left": "$check_opportunity_stage_result",
                        "right": "Closed Won"
                    },
                    true_next="get_account_name",  # Already closed, proceed
                    false_next="confirm_close_opportunity"  # Need to close it
                ),
                "confirm_close_opportunity": WorkflowStep(
                    id="confirm_close_opportunity",
                    type=StepType.HUMAN,
                    name="Confirm opportunity closure",
                    description="The opportunity is not yet 'Closed Won'. Do you want to update it to 'Closed Won' status?",
                    metadata={
                        "opportunity_details": "{check_opportunity_stage_result}"
                    },
                    next_step="close_opportunity"
                ),
                "close_opportunity": WorkflowStep(
                    id="close_opportunity",
                    type=StepType.ACTION,
                    name="Update opportunity to Closed Won if approved",
                    agent="salesforce-agent",
                    instruction="The user was asked if they want to close the opportunity and responded: '{user_close_confirmation}'. If they approved (look for yes, ok, sure, approve, close it, go ahead), update the opportunity from {check_opportunity_stage_result} to 'Closed Won' stage with Probability=100. If they declined (no, skip, don't, cancel), respond that you're skipping the closure.",
                    next_step="get_account_name",
                    critical=True
                ),
                "get_account_name": WorkflowStep(
                    id="get_account_name",
                    type=StepType.ACTION,
                    name="Get account details from opportunity",
                    agent="salesforce-agent",
                    instruction="Get the opportunity details from the opportunity in {check_opportunity_stage_result}. Extract the Account ID, Account Name, and Opportunity ID. Return ONLY these three values in a structured format: account_id: [ID], account_name: [NAME], opportunity_id: [ID].",
                    next_step="create_onboarding_case",
                    critical=True  # Must find account to proceed
                ),
                "create_onboarding_case": WorkflowStep(
                    id="create_onboarding_case",
                    type=StepType.ACTION,
                    name="Create onboarding case",
                    agent="salesforce-agent",
                    instruction="Extract the account_name from the previous step result and create a new Salesforce Case record with these exact field values: Subject='Customer Onboarding - [ACCOUNT_NAME]', Type='Other', Priority='High', Description='New customer onboarding initiated from closed won opportunity {opportunity_name}', AccountId='[ACCOUNT_ID from previous result]'. IMPORTANT: Make sure to set the AccountId field to properly link this Case to the Account. Use the salesforce_create tool.",
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
                    instruction="Extract ONLY the account name from the get_account_name step result (not the full response). Create a new Jira project with name '[ACCOUNT_NAME] Onboarding', project key should be first 3-5 letters of account name in uppercase, project type 'business', and description 'Customer onboarding project for [ACCOUNT_NAME]'"
                ),
                "setup_servicenow_account": WorkflowStep(
                    id="setup_servicenow_account",
                    type=StepType.ACTION,
                    name="Setup ServiceNow account",
                    agent="servicenow-agent",
                    instruction="Extract ONLY the account name from the get_account_name step result. Create a new company record in ServiceNow core_company table with name '[ACCOUNT_NAME]', set as customer=true, vendor=false"
                ),
                "create_onboarding_tasks": WorkflowStep(
                    id="create_onboarding_tasks",
                    type=StepType.ACTION,
                    name="Create onboarding tasks",
                    agent="salesforce-agent",
                    instruction="Extract the opportunity_id from the get_account_name step result. Create the following Salesforce Tasks: 1) Subject='Schedule kickoff call' with ActivityDate=2 days from today, 2) Subject='Send welcome packet' with ActivityDate=1 day from today, 3) Subject='Technical setup' with ActivityDate=5 days from today, 4) Subject='Training session' with ActivityDate=7 days from today. For ALL tasks set: WhatId='[OPPORTUNITY_ID]' (links to Opportunity which auto-populates Account), Status='Not Started', Priority='Normal'. Use ActivityDate field NOT DueDate. Use the salesforce_create tool for each task."
                ),
                "schedule_kickoff": WorkflowStep(
                    id="schedule_kickoff",
                    type=StepType.ACTION,
                    name="Create kickoff meeting task",
                    agent="salesforce-agent",
                    instruction="Extract the account_name and opportunity_id from the get_account_name step result. Create a Salesforce Task with Subject='Schedule kickoff meeting - [ACCOUNT_NAME]', ActivityDate=tomorrow, Priority='High', WhatId='[OPPORTUNITY_ID]' (links to Opportunity which auto-populates Account), Status='Not Started'. Use the salesforce_create tool.",
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