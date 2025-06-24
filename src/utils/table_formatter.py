"""Table Formatting Utility for Console Output

This module provides utilities to format Salesforce data for beautiful console table display.
Implements truncation rules that "spark joy" while preserving critical information like IDs.

Key principles:
- IDs are NEVER truncated (needed for operations and memory)
- Names, emails, and descriptions are truncated for visual consistency
- Numbers, dates, and statuses are preserved in full
- Truncation happens at the data level for 100% compliance
"""

from typing import Dict, Any, List, Union, Optional
import json


class TableFormatter:
    """Formats data for console table display with smart truncation."""
    
    # Truncation limits based on field type
    TRUNCATION_RULES = {
        'name': 30,          # Names and titles
        'email': 25,         # Email addresses
        'description': 45,   # Long text fields
        'default': 50        # Fallback for other text fields
    }
    
    # Fields that should NEVER be truncated
    NEVER_TRUNCATE = {
        # IDs - Critical for operations
        'id', 'accountid', 'contactid', 'opportunityid', 'caseid', 'taskid', 'leadid',
        'account_id', 'contact_id', 'opportunity_id', 'case_id', 'task_id', 'lead_id',
        # Numbers and currency
        'amount', 'revenue', 'employees', 'probability', 'expectedrevenue',
        'annualrevenue', 'numberofemployees', 'annual_revenue', 'number_of_employees',
        # Dates
        'closedate', 'createddate', 'lastmodifieddate', 'lastactivitydate',
        'created_date', 'last_modified_date', 'close_date', 'created', 'modified',
        # Status fields
        'status', 'stage', 'stagename', 'rating', 'priority', 'type',
        # System fields that should be complete
        'phone', 'industry', 'billingcity', 'billingstate', 'website',
        'billing_city', 'billing_state'
    }
    
    @staticmethod
    def truncate_value(value: Any, field_name: str) -> Any:
        """Truncate a single value based on field type and rules.
        
        Args:
            value: The value to potentially truncate
            field_name: The field name (used to determine truncation rules)
            
        Returns:
            The value, truncated if applicable
        """
        # Don't truncate non-string values
        if not isinstance(value, str):
            return value
            
        # Check if field should never be truncated
        field_lower = field_name.lower()
        if field_lower in TableFormatter.NEVER_TRUNCATE:
            return value
            
        # Skip truncation for any field containing 'id'
        if 'id' in field_lower:
            return value
            
        # Determine truncation length
        if 'name' in field_lower or 'title' in field_lower:
            max_length = TableFormatter.TRUNCATION_RULES['name']
        elif 'email' in field_lower:
            max_length = TableFormatter.TRUNCATION_RULES['email']
        elif 'description' in field_lower or 'subject' in field_lower:
            max_length = TableFormatter.TRUNCATION_RULES['description']
        else:
            max_length = TableFormatter.TRUNCATION_RULES['default']
            
        # Apply truncation with word boundary awareness
        if len(value) > max_length:
            # Try to truncate at a word boundary
            truncated = value[:max_length - 3]
            last_space = truncated.rfind(' ')
            if last_space > max_length * 0.7:  # If space is reasonably close
                truncated = truncated[:last_space]
            return truncated + '...'
        return value
    
    @staticmethod
    def format_record(record: Dict[str, Any]) -> Dict[str, Any]:
        """Format a single record with truncation rules applied.
        
        Args:
            record: A dictionary representing a Salesforce record
            
        Returns:
            The record with truncation applied to appropriate fields
        """
        formatted = {}
        for key, value in record.items():
            formatted[key] = TableFormatter.truncate_value(value, key)
        return formatted
    
    @staticmethod
    def format_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format multiple records with truncation rules applied.
        
        Args:
            records: A list of dictionaries representing Salesforce records
            
        Returns:
            The records with truncation applied to appropriate fields
        """
        return [TableFormatter.format_record(record) for record in records]
    
    @staticmethod
    def format_for_tool_response(data: Any) -> Any:
        """Format data structure for tool response with smart truncation.
        
        This method handles various response formats from Salesforce tools:
        - Direct list: [...] (multiple records)
        - Direct dict: {...} (single record)
        - Empty list: [] (no records)
        - Error responses: {'error': '...'}
        
        Args:
            data: The response data from a Salesforce tool
            
        Returns:
            The formatted response with truncation applied
        """
        # Handle error responses - don't truncate
        if isinstance(data, dict) and 'error' in data:
            return data
            
        # Handle direct list of records
        if isinstance(data, list):
            return TableFormatter.format_records(data)
            
        # Handle direct dictionary (single record)
        if isinstance(data, dict):
            return TableFormatter.format_record(data)
            
        # Return unchanged for other types
        return data


# Convenience functions for direct use
def format_salesforce_response(data: Any) -> Any:
    """Convenience function to format Salesforce tool responses."""
    return TableFormatter.format_for_tool_response(data)


def truncate_field(value: Any, field_name: str) -> Any:
    """Convenience function to truncate a single field."""
    return TableFormatter.truncate_value(value, field_name)