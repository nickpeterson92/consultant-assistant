"""Helper functions for SOQL query building."""

from typing import Any, Optional, List
from datetime import datetime, date


def escape_soql(value: Optional[str]) -> str:
    """Escape special characters to prevent SOQL injection.
    
    Args:
        value: String to escape
        
    Returns:
        Escaped string safe for SOQL
    """
    if value is None:
        return ''
    return str(value).replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')


def format_soql_value(value: Any) -> str:
    """Format a value for use in SOQL queries.
    
    Args:
        value: Value to format
        
    Returns:
        Formatted string for SOQL
    """
    if value is None:
        return 'null'
    elif isinstance(value, bool):
        return 'true' if value else 'false'
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, datetime):
        # Format: 2023-01-15T10:30:00Z
        return value.strftime('%Y-%m-%dT%H:%M:%SZ')
    elif isinstance(value, date):
        # Format: 2023-01-15
        return value.strftime('%Y-%m-%d')
    elif isinstance(value, (list, tuple)):
        # For IN clauses
        return ', '.join(format_soql_value(v) for v in value)
    else:
        # String values need quotes and escaping
        return f"'{escape_soql(str(value))}'"


def validate_field_name(field: str) -> bool:
    """Validate that a field name is safe for SOQL.
    
    Args:
        field: Field name to validate
        
    Returns:
        True if valid, False otherwise
    """
    # Basic validation - alphanumeric, underscore, and dot for relationships
    import re
    pattern = r'^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)*$'
    return bool(re.match(pattern, field))


def validate_object_name(object_name: str) -> bool:
    """Validate that an object name is safe for SOQL.
    
    Args:
        object_name: Object name to validate
        
    Returns:
        True if valid, False otherwise
    """
    # Object names should be alphanumeric with possible __c suffix for custom objects
    import re
    pattern = r'^[a-zA-Z][a-zA-Z0-9_]*(__c)?$'
    return bool(re.match(pattern, object_name))


