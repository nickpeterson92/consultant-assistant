"""Base classes for unified Jira tools following 2024 best practices.

This module provides the foundation for all Jira tools with:
- Singleton connection management
- Consistent error handling
- DRY patterns for common operations
- Proper logging and monitoring
"""

import os
from abc import ABC, abstractmethod
from typing import Any, Dict
import requests
from requests.auth import HTTPBasicAuth

from langchain.tools import BaseTool
from src.utils.logging import get_logger

logger = get_logger("jira")


class JiraConnectionManager:
    """Singleton connection manager for Jira."""
    _instance = None
    _connection = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @property
    def connection(self) -> Dict[str, Any]:
        """Get Jira connection configuration."""
        if self._connection is None:
            self._connection = self._create_connection()
        return self._connection
    
    def _create_connection(self) -> Dict[str, Any]:
        """Create Jira connection configuration."""
        logger.info("jira_connection_created",
            component="jira",
            operation="connection_manager",
            base_url=os.environ.get('JIRA_BASE_URL', 'not_set'),
            has_auth=bool(os.environ.get('JIRA_USER') and os.environ.get('JIRA_API_TOKEN'))
        )
        
        return {
            "base_url": os.environ['JIRA_BASE_URL'].rstrip('/'),
            "auth": HTTPBasicAuth(
                os.environ['JIRA_USER'],
                os.environ['JIRA_API_TOKEN']
            ),
            "headers": {
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        }


class BaseJiraTool(BaseTool, ABC):
    """Base class for all Jira tools."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._connection_manager = JiraConnectionManager()
    
    @property
    def jira(self) -> Dict[str, Any]:
        """Get Jira connection."""
        return self._connection_manager.connection
    
    def _log_call(self, **kwargs):
        """Log tool call with consistent format."""
        logger.info("tool_call",
            component="jira",
            tool_name=self.name,
            tool_args=kwargs
        )
    
    def _log_result(self, result: Any):
        """Log tool result with consistent format."""
        logger.info("tool_result",
            component="jira",
            tool_name=self.name,
            result_type=type(result).__name__,
            result_preview=str(result)[:200] if result else "None"
        )
    
    def _handle_error(self, error: Exception) -> Dict[str, Any]:
        """Handle errors with consistent format and structured guidance."""
        logger.error("tool_error",
            component="jira",
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
            return {
                "success": False,
                "error": "Permission denied",
                "error_code": "FORBIDDEN",
                "details": str(error)
            }
        elif "404" in error_str or "Not Found" in error_str:
            return {
                "success": False,
                "error": "Resource not found",
                "error_code": "NOT_FOUND",
                "details": str(error),
                "guidance": {
                    "reflection": "The requested resource doesn't exist.",
                    "consider": "Check if the issue key or project key is correct.",
                    "approach": "Try searching for the resource first or verify the identifier format."
                }
            }
        elif "400" in error_str or "Bad Request" in error_str:
            # Try to extract more specific error details
            import re
            field_match = re.search(r"Field '(\w+)'|field '(\w+)'", error_str)
            field_name = field_match.group(1) or field_match.group(2) if field_match else "unknown"
            
            return {
                "success": False,
                "error": "Invalid request",
                "error_code": "BAD_REQUEST",
                "details": str(error),
                "guidance": {
                    "reflection": "The request format or parameters are invalid.",
                    "consider": "Check required fields and data formats.",
                    "approach": "Review the error details and adjust your request."
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
        """Make HTTP request to Jira API."""
        url = f"{self.jira['base_url']}/rest/api/2{endpoint}"
        
        response = requests.request(
            method=method,
            url=url,
            auth=self.jira['auth'],
            headers=self.jira['headers'],
            **kwargs
        )
        
        # Check status before raising to capture response body
        if not response.ok:
            try:
                error_data = response.json()
                # Jira returns errors in different formats
                if 'errorMessages' in error_data:
                    error_message = '; '.join(error_data['errorMessages'])
                elif 'errors' in error_data:
                    error_message = '; '.join(f"{k}: {v}" for k, v in error_data['errors'].items())
                else:
                    error_message = str(error_data)
            except:
                error_message = response.text[:500] if response.text else f"{response.status_code} {response.reason}"
            
            # Log the full error details
            logger.error("jira_api_error",
                component="jira",
                tool_name=self.name if hasattr(self, 'name') else 'unknown',
                status_code=response.status_code,
                url=url,
                error_message=error_message
            )
            
            # Include response body in the exception message
            response.reason = f"{response.reason} - {error_message}"
        
        response.raise_for_status()
        return response
    
    def _escape_jql(self, value: str) -> str:
        """Escape special characters in JQL strings."""
        if not value:
            return value
        return value.replace("\\", "\\\\").replace('"', '\\"')
    
    def _log_jql(self, query: str, operation: str = "query_built"):
        """Log JQL query for debugging."""
        logger.info("jql_query",
            component="jira",
            tool_name=self.name,
            operation=operation,
            query=query,
            query_length=len(query)
        )


class JiraReadTool(BaseJiraTool):
    """Base class for Jira read operations."""
    pass


class JiraWriteTool(BaseJiraTool):
    """Base class for Jira write operations."""
    pass


class JiraCollaborationTool(BaseJiraTool):
    """Base class for Jira collaboration operations."""
    pass


class JiraAnalyticsTool(BaseJiraTool):
    """Base class for Jira analytics operations."""
    pass