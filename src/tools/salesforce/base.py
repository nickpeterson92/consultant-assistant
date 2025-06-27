"""Base classes for Salesforce tools following 2024 best practices.

This module provides the foundation for all Salesforce tools with:
- Singleton connection management
- Consistent logging patterns
- Centralized error handling
- Response formatting
- Common query patterns

Following SOLID principles:
- Single Responsibility: Each base class handles one aspect
- Open/Closed: Extended through inheritance, not modification
- DRY: All common functionality centralized
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, ClassVar

from langchain.tools import BaseTool
from simple_salesforce import Salesforce

from src.utils.logging import get_logger
from src.utils.soql_query_builder import SOQLQueryBuilder, SOQLOperator
from src.utils.table_formatter import format_salesforce_response

# Initialize logger
logger = get_logger("salesforce")


class SalesforceConnectionManager:
    """Singleton connection manager for Salesforce.
    
    Ensures we only create one connection per process and reuse it.
    Handles connection lifecycle and error recovery.
    """
    _instance = None
    _connection = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @property
    def connection(self) -> Salesforce:
        """Get or create Salesforce connection."""
        if self._connection is None:
            import os
            self._connection = Salesforce(
                username=os.environ['SFDC_USER'],
                password=os.environ['SFDC_PASS'],
                security_token=os.environ['SFDC_TOKEN']
            )
            logger.info("salesforce_connection_created",
                component="salesforce",
                operation="connection_manager"
            )
        return self._connection
    
    def reset(self):
        """Reset connection (useful for error recovery)."""
        self._connection = None


class BaseSalesforceTool(BaseTool, ABC):
    """Base class for all Salesforce tools.
    
    Provides:
    - Automatic connection management
    - Consistent logging
    - Error handling
    - Response formatting
    """
    
    # Fields that cannot be filtered in SOQL WHERE clauses
    NON_FILTERABLE_FIELDS: ClassVar[Dict[str, List[str]]] = {
        'Account': [],
        'Contact': [],
        'Lead': [],
        'Opportunity': ['Description'],  # Long Text Area
        'Case': ['Description'],  # Long Text Area
        'Task': ['Description'],  # Long Text Area
        'User': []
    }
    
    def __init__(self):
        super().__init__()
        self._connection_manager = SalesforceConnectionManager()
    
    @property
    def sf(self) -> Salesforce:
        """Get Salesforce connection."""
        return self._connection_manager.connection
    
    def _log_call(self, **kwargs):
        """Log tool call with consistent format."""
        logger.info("tool_call",
            component="salesforce",
            tool_name=self.name,
            tool_args=kwargs
        )
    
    def _log_result(self, result: Any):
        """Log tool result with consistent format."""
        logger.info("tool_result",
            component="salesforce",
            tool_name=self.name,
            result_type=type(result).__name__,
            result_preview=str(result)[:200] if result else "None"
        )
    
    def _log_error(self, error: Exception):
        """Log tool error with consistent format."""
        logger.error("tool_error",
            component="salesforce",
            tool_name=self.name,
            error=str(error),
            error_type=type(error).__name__
        )
    
    def _validate_filter_fields(self, object_type: str, filter_clause: str) -> Optional[str]:
        """Check if filter contains non-filterable fields.
        
        Returns error message if invalid fields found, None if valid.
        """
        if object_type not in self.NON_FILTERABLE_FIELDS:
            return None
            
        non_filterable = self.NON_FILTERABLE_FIELDS[object_type]
        for field in non_filterable:
            if field.lower() in filter_clause.lower():
                return f"Field '{field}' cannot be filtered in {object_type} queries. Consider using SOSL search instead."
        
        return None
    
    def _handle_error(self, error: Exception) -> Dict[str, Any]:
        """Convert exception to user-friendly error response."""
        self._log_error(error)
        
        # Extract error code if available
        error_code = None
        if hasattr(error, 'content') and isinstance(error.content, list) and error.content:
            error_code = error.content[0].get('errorCode', '')
        
        # Simple, focused error responses
        if error_code == 'INVALID_FIELD':
            # Extract field name from error message if possible
            import re
            field_match = re.search(r"relationship '(\w+)'|column '(\w+)'", str(error))
            field_name = field_match.group(1) or field_match.group(2) if field_match else "unknown"
            
            return {
                "error": "Invalid field in query",
                "error_code": "INVALID_FIELD",
                "details": str(error),
                "guidance": {
                    "reflection": f"The field '{field_name}' doesn't exist on this object.",
                    "consider": "What type of data are you looking for? Different objects use different field names for similar concepts.",
                    "approach": "Think about the object's purpose and what fields it might have."
                }
            }
        elif error_code == 'MALFORMED_QUERY':
            return {
                "error": "Malformed SOQL query", 
                "error_code": "MALFORMED_QUERY",
                "details": str(error),
                "guidance": {
                    "reflection": "The query syntax is incorrect.",
                    "consider": "Check for extra characters, unmatched brackets, or invalid SOQL syntax.",
                    "approach": "Simplify the query or ensure parameters contain only the intended values."
                }
            }
        elif error_code == 'INVALID_TYPE':
            return {"error": "Invalid object type", "details": str(error)}
        elif error_code == 'INSUFFICIENT_ACCESS':
            return {"error": "Insufficient access rights"}
        else:
            return {"error": f"Operation failed: {str(error)}"}
    
    def _run(self, **kwargs) -> Any:
        """Execute tool with automatic logging and error handling."""
        self._log_call(**kwargs)
        
        try:
            result = self._execute(**kwargs)
            formatted_result = self._format_result(result)
            self._log_result(formatted_result)
            return formatted_result
        except Exception as e:
            return self._handle_error(e)
    
    @abstractmethod
    def _execute(self, **kwargs) -> Any:
        """Execute the tool's main logic. Must be implemented by subclasses."""
        pass
    
    def _format_result(self, result: Any) -> Any:
        """Format result using standard formatter."""
        if isinstance(result, dict) and "error" in result:
            return result
        return format_salesforce_response(result)


class SalesforceReadTool(BaseSalesforceTool):
    """Base class for Salesforce read operations (GET, SEARCH)."""
    
    def _build_field_list(self, object_type: str, requested_fields: Optional[List[str]] = None) -> List[str]:
        """Build appropriate field list for object type."""
        # Default field sets by object type
        default_fields = {
            'Account': ['Id', 'Name', 'Type', 'Industry', 'AnnualRevenue', 'Website'],
            'Contact': ['Id', 'Name', 'Email', 'Phone', 'Title', 'Account.Name'],
            'Lead': ['Id', 'Name', 'Company', 'Email', 'Phone', 'Status'],
            'Opportunity': ['Id', 'Name', 'Amount', 'StageName', 'CloseDate', 'Account.Name'],
            'Case': ['Id', 'CaseNumber', 'Subject', 'Status', 'Priority', 'Account.Name'],
            'Task': ['Id', 'Subject', 'Status', 'Priority', 'ActivityDate', 'Who.Name']
        }
        
        if requested_fields:
            return requested_fields
        
        return default_fields.get(object_type, ['Id', 'Name'])
    
    def _parse_natural_language_query(self, query: str, object_type: str) -> SOQLQueryBuilder:
        """Parse natural language into SOQL query builder."""
        builder = SOQLQueryBuilder(object_type)
        query_lower = query.lower()
        
        # Time-based filters
        if 'today' in query_lower:
            builder.where('CreatedDate', SOQLOperator.EQUALS, 'TODAY')
        elif 'yesterday' in query_lower:
            builder.where('CreatedDate', SOQLOperator.EQUALS, 'YESTERDAY')
        elif 'this week' in query_lower:
            builder.where('CreatedDate', SOQLOperator.EQUALS, 'THIS_WEEK')
        elif 'last week' in query_lower:
            builder.where('CreatedDate', SOQLOperator.EQUALS, 'LAST_WEEK')
        elif 'this month' in query_lower:
            builder.where('CreatedDate', SOQLOperator.EQUALS, 'THIS_MONTH')
        elif 'last month' in query_lower:
            builder.where('CreatedDate', SOQLOperator.EQUALS, 'LAST_MONTH')
        
        # Status filters
        if 'closed' in query_lower and object_type in ['Opportunity', 'Case']:
            if 'not closed' in query_lower or 'open' in query_lower:
                builder.where('IsClosed', SOQLOperator.EQUALS, False)
            else:
                builder.where('IsClosed', SOQLOperator.EQUALS, True)
        
        # Amount filters for Opportunity
        if object_type == 'Opportunity':
            if 'high value' in query_lower or 'over 100k' in query_lower:
                builder.where('Amount', SOQLOperator.GREATER_THAN, 100000)
            elif 'over 50k' in query_lower:
                builder.where('Amount', SOQLOperator.GREATER_THAN, 50000)
        
        return builder


class SalesforceWriteTool(BaseSalesforceTool):
    """Base class for Salesforce write operations (CREATE, UPDATE)."""
    
    def _validate_required_fields(self, object_type: str, data: Dict[str, Any]) -> Optional[str]:
        """Validate required fields are present."""
        required_fields = {
            'Lead': ['LastName', 'Company'],
            'Contact': ['LastName'],
            'Opportunity': ['Name', 'StageName', 'CloseDate'],
            'Case': ['Subject'],
            'Task': ['Subject']
        }
        
        if object_type in required_fields:
            missing = [field for field in required_fields[object_type] if field not in data]
            if missing:
                return f"Missing required fields for {object_type}: {', '.join(missing)}"
        
        return None
    
    def _prepare_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare data for Salesforce API."""
        # Remove None values
        cleaned = {k: v for k, v in data.items() if v is not None}
        
        # Handle special field conversions
        if 'CloseDate' in cleaned and isinstance(cleaned['CloseDate'], str):
            # Ensure date format is YYYY-MM-DD
            from datetime import datetime
            try:
                # Try parsing common formats
                for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y']:
                    try:
                        dt = datetime.strptime(cleaned['CloseDate'], fmt)
                        cleaned['CloseDate'] = dt.strftime('%Y-%m-%d')
                        break
                    except:
                        continue
            except:
                pass  # Keep original if parsing fails
        
        return cleaned


class SalesforceAnalyticsTool(BaseSalesforceTool):
    """Base class for Salesforce analytics operations."""
    
    def _build_aggregate_query(self, object_type: str, 
                             group_by: Optional[str] = None,
                             metrics: List[str] = None) -> str:
        """Build aggregate SOQL query."""
        builder = SOQLQueryBuilder(object_type)
        
        # Default metrics if not specified
        if not metrics:
            metrics = ['COUNT(Id)']
        
        # Add SELECT clauses
        for metric in metrics:
            if 'COUNT' in metric:
                builder.select_count('Id', 'record_count')
            elif 'SUM' in metric:
                field = metric.replace('SUM(', '').replace(')', '')
                builder.select_sum(field, f'total_{field.lower()}')
            elif 'AVG' in metric:
                field = metric.replace('AVG(', '').replace(')', '')
                builder.select_avg(field, f'avg_{field.lower()}')
        
        # Add GROUP BY if specified
        if group_by:
            builder.select([group_by])
            builder.group_by([group_by])
        
        return builder.build()