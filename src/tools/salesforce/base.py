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
from simple_salesforce.api import Salesforce

from src.utils.logging.framework import SmartLogger
from src.utils.platform.salesforce import SOQLQueryBuilder, SOQLOperator
# Removed table formatter - no longer truncating responses

# Initialize SmartLogger
logger = SmartLogger("salesforce")


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
                        tool_name=self.name,
            tool_args=kwargs
        )
    
    def _log_result(self, result: Any):
        """Log tool result with consistent format."""
        logger.info("tool_result",
                        tool_name=self.name,
            result_type=type(result).__name__,
            result_preview=str(result)[:200] if result else "None"
        )
    
    def _log_error(self, error: Exception):
        """Log tool error with consistent format."""
        logger.error("tool_error",
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
        """Convert exception to user-friendly error response with success=False."""
        self._log_error(error)
        
        # Extract error code if available
        error_code = None
        if hasattr(error, 'content') and isinstance(getattr(error, 'content', None), list) and getattr(error, 'content', []):
            error_code = getattr(error, 'content')[0].get('errorCode', '')
        
        # Simple, focused error responses
        if error_code == 'INVALID_FIELD':
            # Extract field name from error message if possible
            import re
            field_match = re.search(r"relationship '(\w+)'|column '(\w+)'", str(error))
            field_name = field_match.group(1) or field_match.group(2) if field_match else "unknown"
            
            return {
                "success": False,
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
            error_str = str(error)
            # Check for the specific DESC ASC issue
            if 'DESC ASC' in error_str or 'ASC DESC' in error_str:
                return {
                    "success": False,
                    "error": "Invalid ORDER BY clause with conflicting sort directions",
                    "error_code": "MALFORMED_QUERY",
                    "details": error_str,
                    "guidance": {
                        "reflection": "The ORDER BY clause contains both DESC and ASC which is invalid SOQL syntax.",
                        "consider": "Use either 'ORDER BY field DESC' OR 'ORDER BY field ASC', not both.",
                        "approach": "Specify only one sort direction. For most recent records use DESC, for oldest use ASC.",
                        "example": "Instead of 'CloseDate DESC ASC', use just 'CloseDate DESC'"
                    }
                }
            else:
                return {
                    "success": False,
                    "error": "Malformed SOQL query", 
                    "error_code": "MALFORMED_QUERY",
                    "details": error_str,
                    "guidance": {
                        "reflection": "The query syntax is incorrect.",
                        "consider": "Check for extra characters, unmatched brackets, or invalid SOQL syntax.",
                        "approach": "Simplify the query or ensure parameters contain only the intended values."
                    }
                }
        elif error_code == 'INVALID_TYPE':
            # Extract object type from error if possible
            import re
            type_match = re.search(r"type '(\w+)'|object '(\w+)'", str(error))
            obj_type = type_match.group(1) or type_match.group(2) if type_match else "unknown"
            
            return {
                "success": False,
                "error": "Invalid object type",
                "error_code": "INVALID_TYPE",
                "details": str(error),
                "guidance": {
                    "reflection": f"The object type '{obj_type}' is not recognized in Salesforce.",
                    "consider": "Common objects: Account, Contact, Lead, Opportunity, Case, Task. Custom objects need '__c' suffix.",
                    "approach": "Try a different object type or verify the exact name."
                }
            }
        elif error_code == 'INSUFFICIENT_ACCESS':
            return {
                "success": False,
                "error": "Insufficient access rights",
                "error_code": "INSUFFICIENT_ACCESS",
                "details": str(error)
            }
        elif error_code == 'STORAGE_LIMIT_EXCEEDED':
            return {
                "success": False,
                "error": "Storage limit exceeded", 
                "error_code": "STORAGE_LIMIT_EXCEEDED",
                "details": str(error),
                "guidance": {
                    "reflection": "The Salesforce org has exceeded its storage limits.",
                    "consider": "This often happens in developer orgs with limited storage.",
                    "approach": "Try searching or updating existing records instead of creating new ones."
                }
            }
        elif error_code == 'DUPLICATE_VALUE':
            # Extract field info from error
            import re
            field_match = re.search(r"duplicate value found: (\w+)", str(error))
            field_name = field_match.group(1) if field_match else "unknown field"
            
            return {
                "success": False,
                "error": "Duplicate value found",
                "error_code": "DUPLICATE_VALUE",
                "details": str(error),
                "guidance": {
                    "reflection": f"A record with this {field_name} already exists.",
                    "consider": "This field must be unique across all records.",
                    "approach": "Try searching for the existing record or use a different value."
                }
            }
        elif error_code == 'FIELD_CUSTOM_VALIDATION_EXCEPTION':
            return {
                "success": False,
                "error": "Validation rule failed",
                "error_code": "FIELD_CUSTOM_VALIDATION_EXCEPTION",
                "details": str(error),
                "guidance": {
                    "reflection": "A custom validation rule prevented this operation.",
                    "consider": "Check the error message for specific requirements.",
                    "approach": "Adjust your data to meet the validation requirements."
                }
            }
        elif error_code == 'REQUIRED_FIELD_MISSING':
            # Extract field names from error
            import re
            fields = re.findall(r"Required fields are missing: \[(.*?)\]", str(error))
            missing_fields = fields[0] if fields else "unknown"
            
            return {
                "success": False,
                "error": "Required field missing",
                "error_code": "REQUIRED_FIELD_MISSING",
                "details": str(error),
                "guidance": {
                    "reflection": f"Required fields are missing: {missing_fields}",
                    "consider": "These fields must be provided for this object type.",
                    "approach": "Include all required fields in your request."
                }
            }
        elif error_code == 'INVALID_SESSION_ID':
            return {
                "success": False,
                "error": "Session expired",
                "error_code": "INVALID_SESSION_ID",
                "details": str(error)
            }
        else:
            # Generic error - minimal details
            return {
                "success": False,
                "error": "Operation failed",
                "error_code": error_code or "UNKNOWN_ERROR",
                "details": str(error)
            }
    
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
    
    def _format_result(self, result: Any) -> Dict[str, Any]:
        """Wrap result with success indicator and data."""
        # Always return a dictionary with success field
        return {
            "success": True,
            "data": result,
            "operation": self.name
        }


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
        builder = SOQLQueryBuilder().from_object(object_type)
        query_lower = query.lower()
        
        # Time-based filters
        if 'today' in query_lower:
            builder.where('CreatedDate', SOQLOperator.EQUALS, 'TODAY')  # type: ignore[arg-type]
        elif 'yesterday' in query_lower:
            builder.where('CreatedDate', SOQLOperator.EQUALS, 'YESTERDAY')  # type: ignore[arg-type]
        elif 'this week' in query_lower:
            builder.where('CreatedDate', SOQLOperator.EQUALS, 'THIS_WEEK')  # type: ignore[arg-type]
        elif 'last week' in query_lower:
            builder.where('CreatedDate', SOQLOperator.EQUALS, 'LAST_WEEK')  # type: ignore[arg-type]
        elif 'this month' in query_lower:
            builder.where('CreatedDate', SOQLOperator.EQUALS, 'THIS_MONTH')  # type: ignore[arg-type]
        elif 'last month' in query_lower:
            builder.where('CreatedDate', SOQLOperator.EQUALS, 'LAST_MONTH')  # type: ignore[arg-type]
        
        # Status filters
        if 'closed' in query_lower and object_type in ['Opportunity', 'Case']:
            if 'not closed' in query_lower or 'open' in query_lower:
                builder.where('IsClosed', SOQLOperator.EQUALS, False)  # type: ignore[arg-type]
            else:
                builder.where('IsClosed', SOQLOperator.EQUALS, True)  # type: ignore[arg-type]
        
        # Amount filters for Opportunity
        if object_type == 'Opportunity':
            if 'high value' in query_lower or 'over 100k' in query_lower:
                builder.where('Amount', SOQLOperator.GREATER_THAN, 100000)  # type: ignore[arg-type]
            elif 'over 50k' in query_lower:
                builder.where('Amount', SOQLOperator.GREATER_THAN, 50000)  # type: ignore[arg-type]
        
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
                             metrics: Optional[List[str]] = None) -> str:
        """Build aggregate SOQL query."""
        builder = SOQLQueryBuilder().from_object(object_type)
        
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
            builder.select(group_by)
            builder.group_by(group_by)
        
        return builder.build()