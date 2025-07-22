"""Base classes for utility tools following established patterns.

This module provides the foundation for orchestrator utility tools with:
- Consistent logging patterns
- Structured error handling with guidance
- State-aware context extraction
- Common utility methods
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from langchain.tools import BaseTool
from src.utils.logging.framework import SmartLogger, log_execution

logger = SmartLogger("utility")


class BaseUtilityTool(BaseTool, ABC):
    """Base class for orchestrator utility tools.
    
    Provides:
    - Automatic logging for tool calls
    - Consistent error handling with guidance
    - State-aware context extraction
    - Result formatting
    """
    
    def __init__(self):
        super().__init__()
    
    def _log_call(self, **kwargs):
        """Log tool call with consistent format."""
        logger.info(f"Tool call: {self.name}",
            component="utility",
            tool_name=self.name,
            operation="tool_call",
            tool_args=kwargs
        )
    
    def _log_result(self, result: Any):
        """Log tool result with consistent format."""
        logger.info(f"Tool result: {self.name}",
            component="utility",
            tool_name=self.name,
            operation="tool_result",
            result_type=type(result).__name__,
            result_preview=str(result)[:200] if result else "None"
        )
    
    def _log_error(self, error: Exception):
        """Log tool error with consistent format."""
        logger.error(f"Tool error in {self.name}: {str(error)}",
            component="utility",
            tool_name=self.name,
            operation="tool_error",
            error=str(error),
            error_type=type(error).__name__
        )
    
    def _handle_error(self, error: Exception) -> Dict[str, Any]:
        """Convert exception to user-friendly error response with guidance."""
        self._log_error(error)
        
        error_str = str(error)
        
        # API key errors
        if "api key" in error_str.lower() or "unauthorized" in error_str.lower():
            return {
                "success": False,
                "data": {
                    "error": "API authentication failed",
                    "error_code": "UNAUTHORIZED",
                    "details": str(error),
                    "guidance": {
                        "reflection": "The API key is invalid or missing.",
                        "consider": "Is the TAVILY_API_KEY environment variable set correctly?",
                        "approach": "Verify your API credentials and try again."
                    }
                },
                "operation": self.name
            }
        
        # Rate limit errors
        elif "rate limit" in error_str.lower() or "429" in error_str:
            return {
                "success": False,
                "data": {
                    "error": "Rate limit exceeded",
                    "error_code": "RATE_LIMIT",
                    "details": str(error),
                    "guidance": {
                        "reflection": "Too many requests have been made to the API.",
                        "consider": "Have you been making many rapid searches?",
                        "approach": "Wait a moment before trying again, or reduce search frequency."
                    }
                },
                "operation": self.name
            }
        
        # Network errors
        elif "connection" in error_str.lower() or "timeout" in error_str.lower():
            return {
                "success": False,
                "data": {
                    "error": "Network connection failed",
                    "error_code": "NETWORK_ERROR",
                    "details": str(error),
                    "guidance": {
                        "reflection": "Unable to connect to the search service.",
                        "consider": "Is there a network connectivity issue?",
                        "approach": "Check your internet connection and try again."
                    }
                },
                "operation": self.name
            }
        
        # Generic errors
        else:
            return {
                "success": False,
                "data": {
                    "error": "Operation failed",
                    "error_code": "UNKNOWN_ERROR",
                    "details": str(error),
                    "guidance": {
                        "reflection": "An unexpected error occurred.",
                        "consider": "Is the input data valid and complete?",
                        "approach": "Review the error details and adjust your request."
                    }
                },
                "operation": self.name
            }
    
    def _extract_entities_from_state(self, state: Optional[Dict[str, Any]]) -> List[str]:
        """Extract entity names from recent tool results in state.
        
        Looks for company names, person names, and other entities
        from recent Salesforce/Jira/ServiceNow results.
        """
        entities = []
        
        if not state:
            return entities
        
        # Look for structured tool data in recent messages
        messages = state.get("messages", [])
        for msg in messages[-10:]:  # Last 10 messages
            if hasattr(msg, "content") and "[STRUCTURED_TOOL_DATA]" in str(msg.content):
                # Extract entities from structured data
                content = str(msg.content)
                # Simple extraction - can be enhanced with NER
                if "Name" in content:
                    import re
                    name_matches = re.findall(r'"Name":\s*"([^"]+)"', content)
                    entities.extend(name_matches)
                if "Company" in content:
                    company_matches = re.findall(r'"Company":\s*"([^"]+)"', content)
                    entities.extend(company_matches)
        
        # Also check memory
        memory = state.get("memory", {})
        if isinstance(memory, dict):
            for key, value in memory.items():
                if "Account" in key and isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict) and "name" in item:
                            entities.append(item["name"])
        
        # Deduplicate
        return list(set(entities))
    
    def _extract_context_from_messages(self, state: Optional[Dict[str, Any]], 
                                     count: int = 5) -> str:
        """Extract relevant context from recent messages."""
        if not state or "messages" not in state:
            return ""
        
        messages = state.get("messages", [])
        context_parts = []
        
        for msg in messages[-count:]:
            if hasattr(msg, "content"):
                content = str(msg.content)
                # Skip very long messages
                if len(content) < 500:
                    context_parts.append(content)
        
        return " ".join(context_parts)
    
    @log_execution("utility", "tool_execute", include_args=True, include_result=True)
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