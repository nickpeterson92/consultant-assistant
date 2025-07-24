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
from src.utils.logging.framework import SmartLogger, log_execution

logger = SmartLogger("jira")


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
        """Handle errors with standardized response format and structured guidance."""
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
                "data": {
                    "error": "Authentication failed",
                    "error_code": "UNAUTHORIZED",
                    "details": str(error),
                    "guidance": {
                        "reflection": "The credentials are invalid or missing.",
                        "consider": "Are the JIRA_USER and JIRA_API_TOKEN environment variables correctly set?",
                        "approach": "Verify your Jira credentials and API token permissions."
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
                        "consider": "Does your user account have the necessary permissions for this operation?",
                        "approach": "Check with your Jira administrator about required permissions."
                    }
                },
                "operation": self.name
            }
        elif "404" in error_str or "Not Found" in error_str:
            return {
                "success": False,
                "data": {
                    "error": "Resource not found",
                    "error_code": "NOT_FOUND",
                    "details": str(error),
                    "guidance": {
                        "reflection": "The requested resource doesn't exist.",
                        "consider": "Is the issue key, project key, or resource ID correct?",
                        "approach": "Verify the identifier and try searching for the resource first."
                    }
                },
                "operation": self.name
            }
        elif "400" in error_str or "Bad Request" in error_str:
            # Try to extract more specific error details
            import re
            field_match = re.search(r"Field '(\w+)'|field '(\w+)'", error_str)
            field_match.group(1) or field_match.group(2) if field_match else "unknown"
            
            return {
                "success": False,
                "data": {
                    "error": "Invalid request",
                    "error_code": "BAD_REQUEST",
                    "details": str(error),
                    "guidance": {
                        "reflection": "The request format or parameters are invalid.",
                        "consider": "Are all required fields provided? Is the field format correct?",
                        "approach": "Review the field requirements and data types for this operation."
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
    
    @log_execution("jira", "tool_execute", include_args=True, include_result=True)
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
        """Make HTTP request to Jira API."""
        url = f"{self.jira['base_url']}/rest/api/2{endpoint}"
        
        response = requests.request(
            method=method,
            url=url,
            auth=self.jira['auth'],
            headers=self.jira['headers'],
            **kwargs
        )
        
        # Check for errors and include response body in exception
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            # Try to get error details from response
            try:
                error_details = response.json()
                error_msg = f"{str(e)} - {error_details}"
            except (ValueError, TypeError, AttributeError):
                error_msg = str(e)
            raise requests.HTTPError(error_msg, response=response)
        
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