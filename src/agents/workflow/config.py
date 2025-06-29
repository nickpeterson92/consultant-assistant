"""Workflow Agent Configuration"""

# Agent network configuration
AGENT_PORTS = {
    "salesforce-agent": 8001,
    "jira-agent": 8002,
    "servicenow-agent": 8003
}

# Workflow execution defaults
WORKFLOW_DEFAULTS = {
    "recursion_limit": 10,
    "history_window": 5,
    "default_timeout": 86400,  # 24 hours
    "max_parallel_steps": 10
}

# Business rules and thresholds
BUSINESS_RULES = {
    "key_account_revenue_threshold": 1000000,
    "health_score_risk_threshold": 70,
    "onboarding_task_offsets": {
        "welcome_packet": 1,
        "kickoff_call": 2,
        "technical_setup": 5,
        "training_session": 7
    }
}

# Workflow routing patterns
WORKFLOW_ROUTING_RULES = [
    (r"risk.*(?:deal|opportunity)", "deal_risk_assessment"),
    (r"incident.*resolution", "incident_to_resolution"),
    (r"360|everything about", "customer_360_report"),
    (r"health check", "weekly_account_health_check"),
    (r"onboard(?:ing)?", "new_customer_onboarding")
]

# ServiceNow table names (may vary by instance)
SERVICENOW_TABLES = {
    "company": "core_company",
    "incident": "incident",
    "change": "change_request",
    "problem": "problem"
}