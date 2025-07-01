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
from src.utils.logging import get_logger

logger = get_logger("servicenow")


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
        """Handle errors with consistent format and structured guidance."""
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
                "error": "Authentication failed",
                "error_code": "UNAUTHORIZED",
                "details": str(error)
            }
        elif "403" in error_str or "Forbidden" in error_str:
            # Extract table name from error
            import re
            table_match = re.search(r"table/(\w+)|Table '(\w+)'", error_str)
            table_name = table_match.group(1) or table_match.group(2) if table_match else None
            
            # Special guidance for company tables (actionable)
            if table_name and ('company' in table_name.lower() or 'vendor' in table_name.lower()):
                return {
                    "success": False,
                    "error": "Permission denied for company table",
                    "error_code": "FORBIDDEN_COMPANY_TABLE",
                    "details": str(error),
                    "table": table_name,
                    "guidance": {
                        "reflection": f"Access denied to table '{table_name}'.",
                        "consider": "Common company tables: 'core_company', 'customer_account', 'ast_vendor'.",
                        "approach": "Try a different table name like 'customer_account' or 'core_company'."
                    }
                }
            else:
                return {
                    "success": False,
                    "error": "Permission denied",
                    "error_code": "FORBIDDEN",
                    "details": str(error)
                }
        elif "404" in error_str or "Not Found" in error_str:
            # Try to extract table or record info
            import re
            table_match = re.search(r"table/(\w+)|Table '(\w+)'", error_str)
            table_name = table_match.group(1) or table_match.group(2) if table_match else "unknown"
            
            return {
                "success": False,
                "error": "Resource not found",
                "error_code": "NOT_FOUND",
                "details": str(error),
                "guidance": {
                    "reflection": "The requested resource doesn't exist.",
                    "consider": "Common tables: incident, change_request, problem, sc_task, sc_request.",
                    "approach": "Try a different table name or verify the record ID format."
                }
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
                "error": "Invalid request",
                "error_code": "BAD_REQUEST",
                "details": str(error),
                "guidance": {
                    "reflection": f"The request format or parameters are invalid{f' for field {field_name}' if field_name else ''}.",
                    "consider": "Are all required fields provided? Is the query syntax correct?",
                    "approach": "Check field names and query operators. ServiceNow uses specific field naming conventions."
                }
            }
        else:
            return {
                "success": False,
                "error": "Operation failed",
                "error_code": "UNKNOWN_ERROR",
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
    
    def _format_result(self, result: Any) -> Dict[str, Any]:
        """Wrap result with success indicator and data."""
        return {
            "success": True,
            "data": result,
            "operation": self.name
        }
    
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
        
        # Check status before raising to capture response body
        if not response.ok:
            try:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', str(response.text))
                error_detail = error_data.get('error', {}).get('detail', '')
            except:
                error_message = response.text[:500] if response.text else f"{response.status_code} {response.reason}"
                error_detail = ""
            
            # Log the full error details
            logger.error("servicenow_api_error",
                component="servicenow",
                tool_name=self.name if hasattr(self, 'name') else 'unknown',
                status_code=response.status_code,
                url=url,
                error_message=error_message,
                error_detail=error_detail
            )
            
            # Include response body in the exception message
            if error_detail:
                response.reason = f"{response.reason} - {error_message}: {error_detail}"
            else:
                response.reason = f"{response.reason} - {error_message}"
        
        response.raise_for_status()
        
        # Check for common non-JSON responses
        content_type = response.headers.get('Content-Type', '')
        if not content_type.startswith('application/json'):
            # Check for hibernated instance (common with dev instances)
            if 'text/html' in content_type and ('Instance Hibernating' in response.text or 'hibernat' in response.text.lower()):
                logger.error("servicenow_instance_hibernated",
                    component="servicenow",
                    tool_name=self.name if hasattr(self, 'name') else 'unknown',
                    instance=self.servicenow['base_url'].split('/')[2],
                    response_preview=response.text[:300]
                )
                raise ValueError(
                    "ServiceNow instance is hibernated."
                )
            else:
                # Other non-JSON response
                logger.error("servicenow_unexpected_content_type",
                    component="servicenow",
                    tool_name=self.name if hasattr(self, 'name') else 'unknown',
                    content_type=content_type,
                    status_code=response.status_code,
                    response_preview=response.text[:200] if response.text else 'empty'
                )
                raise ValueError(
                    f"ServiceNow returned {content_type} instead of JSON. Status: {response.status_code}."
                )
        
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
    
    def _build_query_params(self, query: Optional[str] = None, fields: Optional[List[str]] = None, 
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
            
            # Check if response is JSON
            try:
                result = response.json()
            except requests.exceptions.JSONDecodeError:
                logger.warning("nlq_api_non_json_response",
                    component="servicenow",
                    tool_name=self.name,
                    response_text=response.text[:200],
                    status_code=response.status_code
                )
                return {"success": False}
            
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
    
    def _build_aggregate_query(self, table_name: str, group_by: Optional[str] = None,
                              count: bool = True, conditions: Optional[str] = None) -> str:
        """Build aggregate query for stats API."""
        query_parts = []
        
        if group_by:
            query_parts.append(f"GROUPBY{group_by}")
            
        if count:
            query_parts.append("COUNT")
            
        if conditions:
            query_parts.append(conditions)
            
        return '^'.join(query_parts) if query_parts else ""