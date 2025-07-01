"""Unified tools package for all integrations."""

# Salesforce tools
from .salesforce import (
    SalesforceGet,
    SalesforceSearch,
    SalesforceCreate,
    SalesforceUpdate,
    SalesforceSOSL,
    SalesforceAnalytics,
    UNIFIED_SALESFORCE_TOOLS
)

# Jira tools  
from .jira import (
    JiraGet,
    JiraSearch,
    JiraCreate,
    JiraUpdate,
    JiraCollaboration,
    JiraAnalytics,
    UNIFIED_JIRA_TOOLS
)

# ServiceNow tools
from .servicenow import (
    ServiceNowGet,
    ServiceNowSearch,
    ServiceNowCreate,
    ServiceNowUpdate,
    ServiceNowWorkflow,
    ServiceNowAnalytics,
    UNIFIED_SERVICENOW_TOOLS
)

# Utility tools (for orchestrator only)
from .utility import WebSearchTool

# Define utility tools list
UTILITY_TOOLS = [WebSearchTool]

# Combined exports (agent tools only, not utility tools)
ALL_UNIFIED_TOOLS = (
    UNIFIED_SALESFORCE_TOOLS +
    UNIFIED_JIRA_TOOLS +
    UNIFIED_SERVICENOW_TOOLS
)

__all__ = [
    # Salesforce
    'SalesforceGet',
    'SalesforceSearch',
    'SalesforceCreate',
    'SalesforceUpdate',
    'SalesforceSOSL',
    'SalesforceAnalytics',
    'UNIFIED_SALESFORCE_TOOLS',
    # Jira
    'JiraGet',
    'JiraSearch',
    'JiraCreate',
    'JiraUpdate',
    'JiraCollaboration',
    'JiraAnalytics',
    'UNIFIED_JIRA_TOOLS',
    # ServiceNow
    'ServiceNowGet',
    'ServiceNowSearch',
    'ServiceNowCreate',
    'ServiceNowUpdate',
    'ServiceNowWorkflow',
    'ServiceNowAnalytics',
    'UNIFIED_SERVICENOW_TOOLS',
    # Utility
    'WebSearchTool',
    'UTILITY_TOOLS',
    # Combined
    'ALL_UNIFIED_TOOLS'
]