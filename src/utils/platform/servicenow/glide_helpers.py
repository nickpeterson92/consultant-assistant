"""Helper functions for ServiceNow GlideRecord query building."""

from typing import Any, List, Dict, Optional
from datetime import datetime, date
import urllib.parse


def escape_glide_value(value: str) -> str:
    """Escape values for ServiceNow encoded queries.
    
    ServiceNow uses URL-like encoding for special characters in queries.
    
    Args:
        value: Value to escape
        
    Returns:
        Escaped value safe for encoded queries
    """
    # ServiceNow special characters that need escaping
    # ^ is used for AND, so it needs to be encoded
    # = is used for operators, so it needs to be encoded in values
    value = str(value)
    value = value.replace('^', '%5E')
    value = value.replace('=', '%3D')
    value = value.replace(',', '%2C')  # Used in IN clauses
    return value


def format_glide_datetime(dt: datetime) -> str:
    """Format datetime for ServiceNow queries.
    
    Args:
        dt: Datetime to format
        
    Returns:
        Formatted datetime string
    """
    # ServiceNow format: YYYY-MM-DD HH:MM:SS
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def format_glide_date(d: date) -> str:
    """Format date for ServiceNow queries.
    
    Args:
        d: Date to format
        
    Returns:
        Formatted date string
    """
    # ServiceNow format: YYYY-MM-DD
    return d.strftime('%Y-%m-%d')


def parse_dot_walk(field_path: str) -> List[str]:
    """Parse a dot-walked field path.
    
    Args:
        field_path: Dot-walked path like 'caller_id.department.name'
        
    Returns:
        List of field components
    """
    return field_path.split('.')


def validate_table_name(table: str) -> bool:
    """Validate ServiceNow table name.
    
    Args:
        table: Table name to validate
        
    Returns:
        True if valid
    """
    # ServiceNow tables are usually lowercase with underscores
    # Custom tables start with u_ or x_
    import re
    pattern = r'^[a-z][a-z0-9_]*$|^[ux]_[a-z0-9_]+$'
    return bool(re.match(pattern, table))


def build_reference_query(table: str, display_field: str = 'name', search_term: str = '') -> str:
    """Build a query for reference field lookups.
    
    Args:
        table: Table to query
        display_field: Field to search in
        search_term: Search term
        
    Returns:
        Encoded query string
    """
    if search_term:
        return f"{display_field}LIKE{escape_glide_value(search_term)}"
    return ""


def parse_encoded_query(query: str) -> List[Dict[str, Any]]:
    """Parse an encoded query string into components.
    
    Args:
        query: Encoded query string
        
    Returns:
        List of query components
    """
    conditions = []
    parts = query.split('^')
    
    for part in parts:
        if not part:
            continue
            
        # Handle OR operator
        if part == 'OR':
            conditions.append({'type': 'operator', 'value': 'OR'})
            continue
        
        # Parse conditions (field + operator + value)
        # Common patterns: field=value, fieldLIKEvalue, fieldISEMPTY
        import re
        
        # Try different operator patterns
        patterns = [
            (r'(.+?)(ISEMPTY|ISNOTEMPTY|ANYTHING)$', lambda m: (m.group(1), m.group(2), None)),
            (r'(.+?)(=|!=|>|<|>=|<=)(.+)', lambda m: (m.group(1), m.group(2), m.group(3))),
            (r'(.+?)(LIKE|NOTLIKE|STARTSWITH|ENDSWITH|IN|NOTIN|ON|NOTON|BEFORE|AFTER)(.+)', 
             lambda m: (m.group(1), m.group(2), m.group(3)))
        ]
        
        for pattern, extractor in patterns:
            match = re.match(pattern, part)
            if match:
                field, operator, value = extractor(match)
                conditions.append({
                    'type': 'condition',
                    'field': field,
                    'operator': operator,
                    'value': value
                })
                break
    
    return conditions


def get_common_fields(table: str) -> List[str]:
    """Get common fields for a ServiceNow table.
    
    Args:
        table: Table name
        
    Returns:
        List of common field names
    """
    # Common fields across all tables
    common = ['sys_id', 'sys_created_on', 'sys_created_by', 'sys_updated_on', 'sys_updated_by']
    
    # Table-specific common fields
    table_fields = {
        'incident': ['number', 'short_description', 'description', 'priority', 'state', 
                    'assigned_to', 'assignment_group', 'caller_id', 'category', 'subcategory'],
        'problem': ['number', 'short_description', 'description', 'priority', 'state',
                   'assigned_to', 'assignment_group', 'category'],
        'change_request': ['number', 'short_description', 'description', 'priority', 'state',
                          'assigned_to', 'assignment_group', 'type', 'risk', 'impact'],
        'sc_request': ['number', 'short_description', 'description', 'state', 'assigned_to',
                      'requested_for', 'request_state'],
        'sc_req_item': ['number', 'short_description', 'description', 'state', 'assigned_to',
                       'requested_for', 'request', 'cat_item'],
        'sys_user': ['user_name', 'email', 'first_name', 'last_name', 'active', 'department',
                    'manager', 'location', 'title']
    }
    
    return common + table_fields.get(table, [])