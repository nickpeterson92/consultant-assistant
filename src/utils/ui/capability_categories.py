"""Capability categorization and display for the orchestrator."""

from typing import List, Dict, Tuple, Any

# Define capability categories with their icons and display names
CAPABILITY_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "CRM & Sales": {
        "icon": "▣",
        "capabilities": [
            "account_management",
            "contact_management", 
            "lead_management",
            "opportunity_tracking",
            "crm_operations",
            "salesforce_operations"
        ]
    },
    "IT Service Management": {
        "icon": "⚡",
        "capabilities": [
            "incident_management",
            "change_management",
            "problem_management",
            "cmdb_operations",
            "itsm_workflows",
            "encoded_queries",
            "servicenow_operations"
        ]
    },
    "Project Management": {
        "icon": "◆",
        "capabilities": [
            "jira_operations",
            "issue_management",
            "jql_search",
            "epic_tracking",
            "sprint_management",
            "agile_workflows",
            "project_analytics"
        ]
    },
    "Analytics & Reporting": {
        "icon": "▲",
        "capabilities": [
            "sales_analytics",
            "pipeline_analysis",
            "business_metrics",
            "aggregate_reporting"
        ]
    },
    "Operations & Workflows": {
        "icon": "●",
        "capabilities": [
            "case_handling",
            "task_management",
            "global_search",
            "user_management"
        ]
    }
}


def categorize_capabilities(capabilities_list: List[str]) -> Dict[str, List[str]]:
    """Categorize a flat list of capabilities into groups.
    
    Args:
        capabilities_list: Flat list of capability names
        
    Returns:
        Dictionary mapping category names to lists of capabilities
    """
    categorized = {}
    uncategorized = []
    
    # Normalize capability names to lowercase for matching
    normalized_caps = {cap.lower(): cap for cap in capabilities_list}
    
    for category, info in CAPABILITY_CATEGORIES.items():
        category_caps = []
        for cap_pattern in info["capabilities"]:
            # Find matching capabilities (case-insensitive)
            for norm_cap, orig_cap in normalized_caps.items():
                if cap_pattern.lower() == norm_cap:
                    category_caps.append(orig_cap)
        
        if category_caps:
            categorized[category] = category_caps
    
    # Find any uncategorized capabilities
    all_categorized: set[str] = set()
    for caps in categorized.values():
        all_categorized.update(cap.lower() for cap in caps)
    
    for cap in capabilities_list:
        if cap.lower() not in all_categorized:
            uncategorized.append(cap)
    
    if uncategorized:
        categorized["Other"] = uncategorized
    
    return categorized


def format_capability_name(capability: str) -> str:
    """Format capability name for display.
    
    Args:
        capability: Raw capability name (e.g., 'account_management')
        
    Returns:
        Formatted name (e.g., 'Account Management')
    """
    # Replace underscores with spaces and title case
    return capability.replace('_', ' ').title()


def get_category_icon(category: str) -> str:
    """Get the icon for a category.
    
    Args:
        category: Category name
        
    Returns:
        Icon character or default
    """
    return CAPABILITY_CATEGORIES.get(category, {}).get("icon", "•")