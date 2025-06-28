# Conditional Workflow Design Examples
# These remain as pure config objects (dicts) for external storage

CONDITIONAL_WORKFLOW_EXAMPLE = {
    "id": "sales-pipeline-health-check",
    "name": "Sales Pipeline Health Check with Conditionals",
    "description": "Check pipeline health with conditional branching",
    "version": "1.0",
    "steps": [
        {
            "id": "find-stale-opportunities",
            "name": "Find Stale Opportunities",
            "agent": "salesforce-agent",
            "prompt": "Find all opportunities closing this month with no activity in the last 14 days",
            "output_variable": "stale_opportunities",
            "on_complete": {
                "condition": {
                    "type": "is_empty",
                    "variable": "stale_opportunities"
                },
                "if_true": "check-all-opportunities",  # Jump to different step
                "if_false": "find-related-cases"       # Continue to next step
            }
        },
        {
            "id": "find-related-cases",
            "name": "Find Related Cases",
            "agent": "salesforce-agent",
            "prompt": "Find all open cases for the accounts in {stale_opportunities}",
            "output_variable": "related_cases",
            "on_complete": {
                "condition": {
                    "type": "count_greater_than",
                    "variable": "related_cases",
                    "value": 5
                },
                "if_true": "alert-high-case-volume",
                "if_false": "check-case-age"
            }
        },
        {
            "id": "check-all-opportunities",
            "name": "Check All Opportunities Instead",
            "agent": "salesforce-agent", 
            "prompt": "No stale opportunities found. Get all opportunities closing this quarter instead",
            "output_variable": "all_opportunities"
        },
        {
            "id": "alert-high-case-volume",
            "name": "Alert on High Case Volume",
            "agent": "notification-agent",
            "prompt": "Alert: Found {related_cases.count} open cases for stale opportunities",
            "skip_if": {
                "type": "is_empty",
                "variable": "related_cases"
            }
        },
        {
            "id": "check-case-age",
            "name": "Check Case Age",
            "agent": "salesforce-agent",
            "prompt": "Check age of cases in {related_cases}",
            "output_variable": "case_ages"
        }
    ]
}

# Condition Types for Config-Based Workflows
CONDITION_TYPES = {
    "is_empty": "Check if variable/result is empty",
    "is_not_empty": "Check if variable has content", 
    "count_greater_than": "Check if count > value",
    "count_less_than": "Check if count < value",
    "contains": "Check if result contains specific text",
    "equals": "Check if variable equals value",
    "response_contains": "Check if agent response contains text",
    "has_error": "Check if step resulted in error"
}

# Advanced conditional with multiple branches
MULTI_BRANCH_EXAMPLE = {
    "id": "smart-lead-router",
    "name": "Smart Lead Router",
    "steps": [
        {
            "id": "analyze-lead",
            "agent": "salesforce-agent",
            "prompt": "Analyze lead {lead_id} and determine quality score",
            "output_variable": "lead_analysis",
            "on_complete": {
                "type": "switch",  # Multiple conditions
                "conditions": [
                    {
                        "case": {"type": "contains", "variable": "lead_analysis", "value": "high-value"},
                        "goto": "assign-to-senior-rep"
                    },
                    {
                        "case": {"type": "contains", "variable": "lead_analysis", "value": "technical"},
                        "goto": "assign-to-technical-specialist"  
                    },
                    {
                        "case": {"type": "contains", "variable": "lead_analysis", "value": "low-engagement"},
                        "goto": "add-to-nurture-campaign"
                    }
                ],
                "default": "assign-to-general-queue"
            }
        }
    ]
}

# Loops and iterations (still config-based)
LOOP_WORKFLOW_EXAMPLE = {
    "id": "batch-processor",
    "steps": [
        {
            "id": "get-records",
            "agent": "salesforce-agent",
            "prompt": "Get all accounts needing review",
            "output_variable": "accounts_to_review"
        },
        {
            "id": "process-each-account",
            "type": "for_each",
            "iterate_over": "accounts_to_review",
            "iterator_variable": "current_account",
            "max_iterations": 10,  # Safety limit
            "steps": [
                {
                    "id": "check-account-health",
                    "agent": "salesforce-agent", 
                    "prompt": "Analyze health of {current_account}"
                }
            ]
        }
    ]
}

# Variable transformations (for config storage)
TRANSFORM_EXAMPLE = {
    "id": "data-enrichment",
    "steps": [
        {
            "id": "get-data",
            "agent": "salesforce-agent",
            "prompt": "Get opportunity data",
            "output_variable": "opp_data",
            "transform_output": {
                "type": "extract_ids",  # Built-in transformation
                "to_variable": "opportunity_ids"
            }
        },
        {
            "id": "use-transformed",
            "agent": "salesforce-agent",
            "prompt": "Get details for opportunities: {opportunity_ids}"
        }
    ]
}