"""Base classes for unified ServiceNow tools following 2024 best practices.

This module provides the foundation for all ServiceNow tools with:
- Singleton connection management
- Consistent error handling
- DRY patterns for common operations
- Proper logging and monitoring
"""

import os
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, List
import requests
from requests.auth import HTTPBasicAuth

from langchain.tools import BaseTool
from src.utils.logging.framework import SmartLogger, log_execution

logger = SmartLogger("servicenow")


class ServiceNowConnectionManager:
    """Singleton connection manager for ServiceNow."""
    _instance = None
    _connection = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @property
    def connection(self) -> Dict[str, Any]:
        """Get ServiceNow connection configuration."""
        if self._connection is None:
            self._connection = self._create_connection()
        return self._connection
    
    def _create_connection(self) -> Dict[str, Any]:
        """Create ServiceNow connection configuration."""
        instance = os.environ.get('SERVICENOW_INSTANCE', '').rstrip('/')
        if not instance:
            raise ValueError("SERVICENOW_INSTANCE environment variable not set")
            
        logger.info("servicenow_connection_created",
            component="servicenow",
            operation="connection_manager",
            instance=instance,
            has_auth=bool(os.environ.get('SERVICENOW_USER') and os.environ.get('SERVICENOW_PASSWORD'))
        )
        
        # Handle instance URL properly - it might already include .service-now.com
        if not instance.startswith('http'):
            if '.service-now.com' not in instance:
                instance = f"https://{instance}.service-now.com"
            else:
                instance = f"https://{instance}"
        
        return {
            "base_url": f"{instance}/api/now",
            "auth": HTTPBasicAuth(
                os.environ['SERVICENOW_USER'],
                os.environ['SERVICENOW_PASSWORD']
            ),
            "headers": {
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        }


class BaseServiceNowTool(BaseTool, ABC):
    """Base class for all ServiceNow tools."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._connection_manager = ServiceNowConnectionManager()
    
    @property
    def servicenow(self) -> Dict[str, Any]:
        """Get ServiceNow connection."""
        return self._connection_manager.connection
    
    def _log_call(self, **kwargs):
        """Log tool call with consistent format."""
        logger.info("tool_call",
            component="servicenow",
            tool_name=self.name,
            tool_args=kwargs
        )
    
    def _log_result(self, result: Any):
        """Log tool result with consistent format."""
        logger.info("tool_result",
            component="servicenow",
            tool_name=self.name,
            result_type=type(result).__name__,
            result_preview=str(result)[:200] if result else "None"
        )
    
    def _log_query(self, query: str, operation: str = "query_built"):
        """Log Glide query for debugging."""
        logger.info("glide_query",
            component="servicenow",
            tool_name=self.name,
            operation=operation,
            query=query,
            query_length=len(query)
        )
    
    def _handle_error(self, error: Exception) -> Dict[str, Any]:
        """Handle errors with standardized response format and structured guidance."""
        logger.error("tool_error",
            component="servicenow",
            tool_name=self.name,
            error=str(error),
            error_type=type(error).__name__
        )
        
        error_str = str(error)
        if "401" in error_str or "Unauthorized" in error_str:
            return {
                "success": False,
                "data": {
                    "error": "Authentication failed",
                    "error_code": "UNAUTHORIZED",
                    "details": str(error),
                    "guidance": {
                        "reflection": "The credentials are invalid or missing.",
                        "consider": "Are the SERVICENOW_USER and SERVICENOW_PASSWORD environment variables correctly set?",
                        "approach": "Verify your ServiceNow credentials and instance configuration."
                    }
                },
                "operation": self.name
            }
        elif "403" in error_str or "Forbidden" in error_str:
            return {
                "success": False,
                "data": {
                    "error": "Permission denied",
                    "error_code": "FORBIDDEN",
                    "details": str(error),
                    "guidance": {
                        "reflection": "You don't have permission to perform this action.",
                        "consider": "Does your user account have the necessary roles and permissions?",
                        "approach": "Check with your ServiceNow administrator about required roles."
                    }
                },
                "operation": self.name
            }
        elif "404" in error_str or "Not Found" in error_str:
            # Try to extract table or record info
            import re
            table_match = re.search(r"table/(\w+)|Table '(\w+)'", error_str)
            table_match.group(1) or table_match.group(2) if table_match else "unknown"
            
            return {
                "success": False,
                "data": {
                    "error": "Resource not found",
                    "error_code": "NOT_FOUND",
                    "details": str(error),
                    "guidance": {
                        "reflection": "The requested resource doesn't exist.",
                        "consider": "Is the table name correct? ServiceNow tables often have prefixes like 'incident', 'change_request', etc.",
                        "approach": "Verify the table name and record ID. Common tables: incident, change_request, problem, sc_task."
                    }
                },
                "operation": self.name
            }
        elif "400" in error_str or "Bad Request" in error_str:
            # Try to extract field information
            import re
            field_match = re.search(r"field '(\w+)'|Field '(\w+)'|property '(\w+)'", error_str)
            field_name = None
            if field_match:
                field_name = field_match.group(1) or field_match.group(2) or field_match.group(3)
            
            return {
                "success": False,
                "data": {
                    "error": "Invalid request",
                    "error_code": "BAD_REQUEST",
                    "details": str(error),
                    "guidance": {
                        "reflection": f"The request format or parameters are invalid{f' for field {field_name}' if field_name else ''}.",
                        "consider": "Are all required fields provided? Is the query syntax correct?",
                        "approach": "Check field names and query operators. ServiceNow uses specific field naming conventions."
                    }
                },
                "operation": self.name
            }
        else:
            return {
                "success": False,
                "data": {
                    "error": "Operation failed",
                    "error_code": "UNKNOWN_ERROR",
                    "details": str(error)
                },
                "operation": self.name
            }
    
    @log_execution("servicenow", "tool_execute", include_args=True, include_result=True)
    def _run(self, **kwargs) -> Any:
        """Execute tool with automatic logging and error handling."""
        self._log_call(**kwargs)
        
        try:
            result = self._execute(**kwargs)
            self._log_result(result)
            
            # Wrap successful result in standardized format
            return {
                "success": True,
                "data": result,
                "operation": self.name
            }
        except Exception as e:
            return self._handle_error(e)
    
    @abstractmethod
    def _execute(self, **kwargs) -> Any:
        """Execute the tool's main logic. Must be implemented by subclasses."""
        pass
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make HTTP request to ServiceNow API."""
        url = f"{self.servicenow['base_url']}{endpoint}"
        
        response = requests.request(
            method=method,
            url=url,
            auth=self.servicenow['auth'],
            headers=self.servicenow['headers'],
            **kwargs
        )
        response.raise_for_status()
        return response
    
    def _detect_table_from_number(self, number: str) -> Optional[str]:
        """Detect ServiceNow table from record number prefix."""
        prefix_map = {
            'INC': 'incident',
            'PRB': 'problem',
            'CHG': 'change_request',
            'TASK': 'task',
            'REQ': 'sc_request',
            'RITM': 'sc_req_item',
            'KB': 'kb_knowledge'
        }
        
        for prefix, table in prefix_map.items():
            if number.upper().startswith(prefix):
                return table
        return None
    
    def _get_default_fields(self, table_name: str) -> List[str]:
        """Get default fields for a table."""
        defaults = {
            'incident': ['number', 'short_description', 'description', 'state', 
                        'priority', 'assigned_to', 'caller_id', 'category'],
            'change_request': ['number', 'short_description', 'description', 'state',
                              'priority', 'assigned_to', 'type', 'risk'],
            'problem': ['number', 'short_description', 'description', 'state',
                       'priority', 'assigned_to', 'known_error', 'root_cause'],
            'task': ['number', 'short_description', 'description', 'state',
                    'priority', 'assigned_to', 'work_notes'],
            'sys_user': ['user_name', 'name', 'email', 'department', 'title'],
            'cmdb_ci': ['name', 'sys_class_name', 'operational_status', 'install_status']
        }
        return defaults.get(table_name, ['number', 'short_description', 'state'])


class ServiceNowReadTool(BaseServiceNowTool):
    """Base class for ServiceNow read operations."""
    
    def _build_query_params(self, query: str = None, fields: List[str] = None, 
                           limit: int = 100, offset: int = 0, 
                           display_value: str = "all") -> Dict[str, str]:
        """Build query parameters for API request.
        
        Args:
            query: Encoded query string
            fields: List of fields to return (supports dot-walking)
            limit: Maximum records to return (max 10000)
            offset: Starting record offset
            display_value: Reference field display (true/false/all)
                - true: Display values only
                - false: Sys_ids only  
                - all: Both display values and sys_ids (best for dot-walking)
        """
        params = {}
        
        if query:
            params['sysparm_query'] = query
        
        if fields:
            # Validate dot-walking depth
            validated_fields = self._validate_dot_walking(fields)
            params['sysparm_fields'] = ','.join(validated_fields)
            
        params['sysparm_limit'] = str(min(limit, 10000))  # ServiceNow max
        params['sysparm_offset'] = str(offset)
        params['sysparm_display_value'] = display_value
        
        return params
    
    def _validate_dot_walking(self, fields: List[str]) -> List[str]:
        """Validate dot-walking depth and warn if excessive."""
        validated = []
        for field in fields:
            depth = field.count('.')
            if depth > 3:
                logger.warning("excessive_dot_walking",
                    component="servicenow",
                    tool_name=self.name,
                    field=field,
                    depth=depth,
                    details="Dot-walking beyond 3 levels may impact performance"
                )
            validated.append(field)
        return validated
    
    def _is_encoded_query(self, query: str) -> bool:
        """Check if query is already in encoded format."""
        # Common encoded query indicators
        encoded_indicators = ['^', '=', '!=', 'LIKE', 'IN', 'BETWEEN', 
                             'ISEMPTY', 'ISNOTEMPTY', 'ORDERBY', 'GROUPBY']
        return any(indicator in query for indicator in encoded_indicators)
    
    def _execute_nlq_query(self, natural_language: str, table_name: str) -> Dict[str, Any]:
        """Execute natural language query using ServiceNow's NLQ API.
        
        Returns dict with either:
        - success=True and encoded_query
        - success=False with guidance for LLM
        """
        try:
            # ServiceNow NLQ endpoint (may vary by version)
            nlq_endpoint = "/api/now/nlq/search"
            
            nlq_payload = {
                "query": natural_language,
                "table": table_name
            }
            
            response = self._make_request("POST", nlq_endpoint, json=nlq_payload)
            result = response.json()
            
            if result.get("result", {}).get("query"):
                encoded_query = result["result"]["query"]
                logger.info("nlq_conversion_success",
                    component="servicenow", 
                    tool_name=self.name,
                    natural_query=natural_language[:100],
                    encoded_query=encoded_query
                )
                return {
                    "success": True,
                    "encoded_query": encoded_query
                }
            else:
                logger.info("nlq_interpretation_failed",
                    component="servicenow",
                    tool_name=self.name,
                    natural_query=natural_language[:100]
                )
                return {"success": False}
                
        except Exception as e:
            logger.warning("nlq_api_unavailable",
                component="servicenow",
                tool_name=self.name,
                error=str(e),
                details="NLQ API not available or error occurred"
            )
            return {"success": False}


class ServiceNowWriteTool(BaseServiceNowTool):
    """Base class for ServiceNow write operations."""
    
    def _validate_required_fields(self, table_name: str, data: Dict[str, Any]) -> None:
        """Validate required fields for a table."""
        required_fields = {
            'incident': ['short_description'],
            'change_request': ['short_description', 'type'],
            'problem': ['short_description'],
            'task': ['short_description']
        }
        
        table_required = required_fields.get(table_name, [])
        missing = [field for field in table_required if not data.get(field)]
        
        if missing:
            raise ValueError(f"Missing required fields for {table_name}: {', '.join(missing)}")


class ServiceNowWorkflowTool(BaseServiceNowTool):
    """Base class for ServiceNow workflow operations."""
    
    def _get_valid_states(self, table_name: str) -> Dict[str, str]:
        """Get valid state values for a table."""
        states = {
            'incident': {
                'new': '1',
                'in_progress': '2',
                'on_hold': '3',
                'resolved': '6',
                'closed': '7',
                'canceled': '8'
            },
            'change_request': {
                'new': '-5',
                'assess': '-4',
                'authorize': '-3',
                'scheduled': '-2',
                'implement': '-1',
                'review': '0',
                'closed': '3',
                'canceled': '4'
            },
            'problem': {
                'new': '1',
                'known_error': '2',
                'pending_change': '3',
                'resolved': '4',
                'closed': '5'
            }
        }
        return states.get(table_name, {})


class ServiceNowAnalyticsTool(BaseServiceNowTool):
    """Base class for ServiceNow analytics operations."""
    
    def _build_aggregate_query(self, table_name: str, group_by: str = None,
                              count: bool = True, conditions: str = None) -> str:
        """Build aggregate query for stats API."""
        query_parts = []
        
        if group_by:
            query_parts.append(f"GROUPBY{group_by}")
            
        if count:
            query_parts.append("COUNT")
            
        if conditions:
            query_parts.append(conditions)
            
        return '^'.join(query_parts) if query_parts else ""