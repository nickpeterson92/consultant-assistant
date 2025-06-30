"""Workflow Utilities"""

import re
from typing import Dict, Any


def safe_variable_substitution(text: str, variables: Dict[str, Any]) -> str:
    """Safely substitute variables without regex injection
    
    Args:
        text: Text containing {variable} placeholders
        variables: Dictionary of variable values
        
    Returns:
        Text with variables substituted
    """
    if not text or not variables:
        return text or ""
    
    result = text
    for key, value in variables.items():
        # Use simple string replacement instead of regex
        placeholder = f"{{{key}}}"
        # Convert value to string and escape any special characters
        safe_value = str(value).replace("\\", "\\\\").replace("$", "\\$")
        result = result.replace(placeholder, safe_value)
    
    return result


def extract_variable_names(text: str) -> list:
    """Extract variable names from a template string
    
    Args:
        text: Text containing {variable} placeholders
        
    Returns:
        List of variable names found
    """
    if not text:
        return []
    
    # Use regex to find all {variable} patterns
    pattern = r'\{(\w+)\}'
    matches = re.findall(pattern, text)
    return list(set(matches))  # Remove duplicates


def validate_workflow_variables(template: str, available_vars: Dict[str, Any]) -> list:
    """Validate that all variables in a template are available
    
    Args:
        template: Template string with variables
        available_vars: Dictionary of available variables
        
    Returns:
        List of missing variable names
    """
    required_vars = extract_variable_names(template)
    missing = [var for var in required_vars if var not in available_vars]
    return missing