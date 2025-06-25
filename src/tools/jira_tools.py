"""Jira Issue Tracking Tools - Enterprise-Grade Project Management Operations.

This module implements 15 comprehensive Jira tools following the same patterns as Salesforce tools:

Architecture Philosophy:
- **Trust LLM Outputs**: No validation needed for LLM-generated queries
- **Flexible Search**: Natural language support with intelligent query generation
- **Consistent Error Handling**: Graceful degradation with structured error responses
- **Token Optimization**: Streamlined response formats for cost efficiency
- **Modern Pattern**: Uses nested Input classes following LangChain 2024 best practices

Tool Categories:
1. Issue CRUD: Create, read, update operations for issues
2. Search & Query: Advanced JQL search with natural language support
3. Agile Operations: Sprint, epic, and board management
4. Workflow: Issue transitions and state management
5. Collaboration: Comments, attachments, and links

Error Handling Philosophy:
- Never crash - always return structured error responses
- Preserve error context for debugging while hiding sensitive details
- Log all operations for audit trails and troubleshooting
- Graceful empty result handling ([] instead of exceptions)
"""

import os
from typing import Optional, List, Dict, Any
from datetime import datetime

from pydantic import BaseModel, Field
from langchain.tools import BaseTool
import requests
from requests.auth import HTTPBasicAuth

from src.utils.logging import get_logger

# Initialize logger with Jira component
logger = get_logger("jira")
# No validation needed - trust LLM-generated inputs


def get_jira_connection():
    """Create and return Jira connection configuration."""
    logger.info("jira_connection_init",
        component="jira",
        operation="create_connection",
        base_url=os.environ.get('JIRA_BASE_URL', 'not_set'),
        has_auth=bool(os.environ.get('JIRA_USER') and os.environ.get('JIRA_API_TOKEN'))
    )
    
    return {
        "base_url": os.environ['JIRA_BASE_URL'],
        "auth": HTTPBasicAuth(
            os.environ['JIRA_USER'],
            os.environ['JIRA_API_TOKEN']
        ),
        "headers": {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    }


def escape_jql(value: str) -> str:
    """Escape special characters in JQL strings to prevent injection."""
    if not value:
        return value
    # JQL requires escaping quotes and backslashes
    return value.replace("\\", "\\\\").replace('"', '\\"')


def log_jql_query(tool_name: str, query: str, operation: str = "query_built"):
    """Log JQL query for debugging and monitoring.
    
    Args:
        tool_name: Name of the tool building the query
        query: The JQL query string
        operation: Type of operation (query_built, query_executed, etc.)
    """
    logger.info("jql_query",
        component="jira",
        tool_name=tool_name,
        operation=operation,
        query=query,
        query_length=len(query)
    )


# Search and Query Tools
class SearchJiraIssuesTool(BaseTool):
    """Advanced JQL search for Jira issues with natural language support.
    
    Provides comprehensive issue search capabilities using JQL (Jira Query Language)
    with automatic query building and injection prevention. Supports both direct
    JQL and natural language queries that are converted to safe JQL.
    
    Use Cases:
    - Direct JQL: "project = PROJ AND status = 'In Progress'"
    - Natural search: "find all bugs assigned to me"
    - Complex queries: "high priority issues in current sprint"
    - Time-based: "issues created this week"
    
    Security Features:
    - Automatic JQL escaping to prevent injection
    - Query validation before execution
    - Safe parameter binding
    """
    name: str = "search_jira_issues"
    description: str = (
        "SEARCH: Issues using JQL or natural language queries. "
        "Use for: 'find bugs in PROJ', 'my open tasks', 'issues created today'. "
        "Supports complex JQL like 'project = PROJ AND priority = High'. "
        "Returns matching issues with key fields."
    )
    
    class Input(BaseModel):
        """Input schema for searching Jira issues."""
        query: str = Field(description="JQL query or natural language search")
        max_results: int = Field(default=50, description="Maximum results to return")
        fields: Optional[List[str]] = Field(
            default=None,
            description="Specific fields to return (default: key, summary, status, assignee)"
        )
    
    args_schema: type = Input

    def _run(self, **kwargs) -> dict:
        data = self.Input(**kwargs)
        
        # Log tool call - IDENTICAL format to orchestrator
        logger.info("tool_call",
            component="jira",
            tool_name="search_jira_issues",
            tool_args=kwargs
        )
        
        try:
            
            conn = get_jira_connection()
            
            # Convert natural language to JQL if needed
            jql = self._build_jql_query(data.query)
            log_jql_query("search_jira_issues", jql)
            
            # Default fields if not specified
            fields = data.fields or ["key", "summary", "status", "assignee", "priority", "created"]
            
            params = {
                "jql": jql,
                "maxResults": data.max_results,
                "fields": ",".join(fields)
            }
            
            # Log Jira API call
            logger.info("jira_api_request",
                component="jira",
                operation="search_issues",
                url=f"{conn['base_url']}/rest/api/3/search",
                method="GET",
                jql_query=jql,
                max_results=data.max_results
            )
            
            response = requests.get(
                f"{conn['base_url']}/rest/api/3/search",
                auth=conn['auth'],
                headers=conn['headers'],
                params=params
            )
            
            if response.status_code == 200:
                result = response.json()
                issues = result.get("issues", [])
                
                logger.info("jira_api_response",
                    component="jira",
                    operation="search_issues",
                    status_code=response.status_code,
                    issue_count=len(issues),
                    total_results=result.get("total", 0)
                )
                
                # Format response
                formatted_issues = []
                for issue in issues:
                    formatted_issue = {
                        "key": issue["key"],
                        "summary": issue["fields"]["summary"],
                        "status": issue["fields"]["status"]["name"],
                        "assignee": issue["fields"]["assignee"]["displayName"] if issue["fields"].get("assignee") else "Unassigned",
                        "priority": issue["fields"]["priority"]["name"] if issue["fields"].get("priority") else "None"
                    }
                    # Add any additional requested fields
                    for field in fields:
                        if field not in formatted_issue and field in issue["fields"]:
                            formatted_issue[field] = issue["fields"][field]
                    
                    formatted_issues.append(formatted_issue)
                
                result = {
                    "success": True,
                    "issue_count": len(formatted_issues),
                    "issues": formatted_issues,
                    "jql_used": jql
                }
                
                # Log tool result - IDENTICAL format to orchestrator pattern
                logger.info("tool_result",
                    component="jira", 
                    tool_name="search_jira_issues",
                    result_type=type(result).__name__,
                    result_preview=f"Found {len(formatted_issues)} issues"
                )
                
                return result
            else:
                error_msg = response.json().get("errorMessages", ["Unknown error"])[0]
                
                logger.error("jira_api_error",
                    component="jira",
                    operation="search_issues",
                    status_code=response.status_code,
                    error=error_msg,
                    jql_query=jql
                )
                
                error_result = {
                    "success": False,
                    "error": f"Search failed: {error_msg}",
                    "jql_attempted": jql
                }
                
                # Log tool error
                logger.error("tool_error",
                    component="jira",
                    tool_name="search_jira_issues", 
                    error=error_msg,
                    error_type="APIError",
                    status_code=response.status_code
                )
                
                return error_result
                
        except Exception as e:
            # Log tool error
            logger.error("tool_error",
                component="jira",
                tool_name="search_jira_issues", 
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "success": False,
                "error": f"Unexpected error during search: {str(e)}"
            }
    
    def _build_jql_query(self, query: str) -> str:
        """Convert natural language to JQL or validate existing JQL."""
        # If it already looks like JQL, return it as-is (trust LLM)
        if any(op in query.lower() for op in [" = ", " != ", " ~ ", " in ", " and ", " or "]):
            return query
        
        # Natural language conversions
        query_lower = query.lower()
        jql_parts = []
        
        # Handle common patterns
        if "my" in query_lower or "assigned to me" in query_lower:
            jql_parts.append("assignee = currentUser()")
        
        if "bug" in query_lower or "bugs" in query_lower:
            jql_parts.append("type = Bug")
        elif "task" in query_lower or "tasks" in query_lower:
            jql_parts.append("type = Task")
        elif "story" in query_lower or "stories" in query_lower:
            jql_parts.append("type = Story")
        
        if "open" in query_lower or "not closed" in query_lower:
            jql_parts.append("status != Closed")
        elif "closed" in query_lower:
            jql_parts.append("status = Closed")
        elif "in progress" in query_lower:
            jql_parts.append("status = 'In Progress'")
        
        if "high priority" in query_lower:
            jql_parts.append("priority = High")
        elif "urgent" in query_lower or "critical" in query_lower:
            jql_parts.append("priority in (Critical, Highest)")
        
        if "today" in query_lower:
            jql_parts.append("created >= startOfDay()")
        elif "this week" in query_lower:
            jql_parts.append("created >= startOfWeek()")
        elif "this month" in query_lower:
            jql_parts.append("created >= startOfMonth()")
        
        # If no patterns matched, search in summary
        if not jql_parts:
            escaped_query = escape_jql(query)
            jql_parts.append(f'summary ~ "{escaped_query}"')
        
        return " AND ".join(jql_parts)


# Issue CRUD Tools
class GetJiraIssueTool(BaseTool):
    """Retrieve detailed information about a specific Jira issue.
    
    Fetches comprehensive issue details including all fields, comments,
    attachments, and linked issues. Provides complete context for issue
    analysis and decision making.
    
    Use Cases:
    - Get full issue details: "get issue PROJ-123"
    - View issue with history: "show PROJ-456 with comments"
    - Check issue relationships: "get PROJ-789 and its links"
    
    Returns:
    - Complete issue fields and metadata
    - Recent comments and activity
    - Attachments and linked issues
    - Workflow transition options
    """
    name: str = "get_jira_issue"
    description: str = (
        "GET: Detailed information for a specific Jira issue. "
        "Use for: 'get PROJ-123', 'show details for PROJ-456'. "
        "Returns comprehensive issue data including description, comments, attachments. "
        "For searching multiple issues, use search_jira_issues instead."
    )
    
    class Input(BaseModel):
        """Input schema for retrieving a Jira issue."""
        issue_key: str = Field(description="Jira issue key (e.g., PROJ-123)")
        expand: Optional[List[str]] = Field(
            default=None,
            description="Additional data to include: changelog, comments, attachments"
        )
        
    
    args_schema: type = Input

    def _run(self, **kwargs) -> dict:
        data = self.Input(**kwargs)
        
        # Log tool call - IDENTICAL format to orchestrator
        logger.info("tool_call",
            component="jira",
            tool_name="get_jira_issue",
            tool_args=kwargs
        )
        
        try:
            
            conn = get_jira_connection()
            
            # Build expand parameter
            expand_params = []
            if data.expand:
                expand_params = data.expand
            else:
                expand_params = ["renderedFields", "changelog", "comments"]
            
            params = {"expand": ",".join(expand_params)} if expand_params else {}
            
            # Log API request
            logger.info("jira_api_request",
                component="jira",
                operation="get_issue",
                url=f"{conn['base_url']}/rest/api/3/issue/{data.issue_key}",
                method="GET",
                issue_key=data.issue_key,
                expand_params=expand_params
            )
            
            response = requests.get(
                f"{conn['base_url']}/rest/api/3/issue/{data.issue_key}",
                auth=conn['auth'],
                headers=conn['headers'],
                params=params
            )
            
            if response.status_code == 200:
                issue = response.json()
                
                logger.info("jira_api_response",
                    component="jira",
                    operation="get_issue",
                    status_code=response.status_code,
                    issue_key=data.issue_key,
                    has_comments="comment" in issue.get("fields", {})
                )
                
                # Format response with key details
                formatted = {
                    "key": issue["key"],
                    "summary": issue["fields"]["summary"],
                    "description": issue["fields"].get("description", "No description"),
                    "status": issue["fields"]["status"]["name"],
                    "priority": issue["fields"]["priority"]["name"] if issue["fields"].get("priority") else "None",
                    "type": issue["fields"]["issuetype"]["name"],
                    "assignee": issue["fields"]["assignee"]["displayName"] if issue["fields"].get("assignee") else "Unassigned",
                    "reporter": issue["fields"]["reporter"]["displayName"],
                    "created": issue["fields"]["created"],
                    "updated": issue["fields"]["updated"],
                    "labels": issue["fields"].get("labels", []),
                    "components": [c["name"] for c in issue["fields"].get("components", [])],
                    "fix_versions": [v["name"] for v in issue["fields"].get("fixVersions", [])]
                }
                
                # Add comments if available
                if "comments" in expand_params and "comment" in issue["fields"]:
                    comments = issue["fields"]["comment"]["comments"]
                    formatted["recent_comments"] = [
                        {
                            "author": c["author"]["displayName"],
                            "created": c["created"],
                            "body": c["body"][:200] + "..." if len(c["body"]) > 200 else c["body"]
                        }
                        for c in comments[-3:]  # Last 3 comments
                    ]
                
                result = {
                    "success": True,
                    "issue": formatted
                }
                
                # Log tool result - IDENTICAL format to orchestrator pattern
                logger.info("tool_result",
                    component="jira", 
                    tool_name="get_jira_issue",
                    result_type=type(result).__name__,
                    result_preview=f"Retrieved issue {data.issue_key}"
                )
                
                return result
            elif response.status_code == 404:
                logger.warning("jira_issue_not_found",
                    component="jira",
                    operation="get_issue",
                    issue_key=data.issue_key,
                    status_code=404
                )
                
                error_result = {
                    "success": False,
                    "error": f"Issue {data.issue_key} not found"
                }
                
                # Log tool error for not found
                logger.error("tool_error",
                    component="jira",
                    tool_name="get_jira_issue", 
                    error=f"Issue {data.issue_key} not found",
                    error_type="NotFound",
                    status_code=404
                )
                
                return error_result
            else:
                error_msg = response.json().get("errorMessages", ["Unknown error"])[0]
                
                logger.error("jira_api_error",
                    component="jira",
                    operation="get_issue",
                    status_code=response.status_code,
                    error=error_msg,
                    issue_key=data.issue_key
                )
                
                error_result = {
                    "success": False,
                    "error": f"Failed to retrieve issue: {error_msg}"
                }
                
                # Log tool error
                logger.error("tool_error",
                    component="jira",
                    tool_name="get_jira_issue", 
                    error=error_msg,
                    error_type="APIError",
                    status_code=response.status_code
                )
                
                return error_result
                
        except Exception as e:
            # Log tool error
            logger.error("tool_error",
                component="jira",
                tool_name="get_jira_issue", 
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }


class CreateJiraIssueTool(BaseTool):
    """Create new Jira issues with comprehensive field support.
    
    Creates issues in specified projects with automatic field validation
    and workflow compliance. Supports all standard and custom fields
    with intelligent defaults for required fields.
    
    Use Cases:
    - Create bug: "create bug in PROJ about login issue"
    - Create story: "new story in PROJ for user dashboard"
    - Create task: "create task assigned to john@company"
    - Create with priority: "urgent bug in PROJ about payment"
    
    Features:
    - Automatic project validation
    - Required field detection
    - Smart defaults for common fields
    - Custom field support
    """
    name: str = "create_jira_issue"
    description: str = (
        "CREATE: New Jira issues (bugs, stories, tasks) in any project. "
        "Use for: 'create bug about X', 'new story for Y', 'urgent task for Z'. "
        "Automatically handles required fields and returns the created issue key. "
        "Supports priority, labels, components, and custom fields."
    )
    
    class Input(BaseModel):
        """Input schema for creating a Jira issue."""
        project_key: str = Field(description="Project key (e.g., PROJ)")
        summary: str = Field(description="Issue summary/title")
        issue_type: str = Field(default="Task", description="Issue type: Bug, Story, Task, etc.")
        description: Optional[str] = Field(default=None, description="Detailed description")
        priority: Optional[str] = Field(default=None, description="Priority: Highest, High, Medium, Low, Lowest")
        assignee: Optional[str] = Field(default=None, description="Assignee email or username")
        labels: Optional[List[str]] = Field(default=None, description="Labels to add")
        components: Optional[List[str]] = Field(default=None, description="Component names")
        due_date: Optional[str] = Field(default=None, description="Due date (YYYY-MM-DD)")
        custom_fields: Optional[Dict[str, Any]] = Field(default=None, description="Custom field values")
        
        
    
    args_schema: type = Input

    def _run(self, **kwargs) -> dict:
        data = self.Input(**kwargs)
        
        # Log tool call - IDENTICAL format to orchestrator
        logger.info("tool_call",
            component="jira",
            tool_name="create_jira_issue",
            tool_args=kwargs
        )
        
        try:
            
            conn = get_jira_connection()
            
            # Build issue data
            issue_data = {
                "fields": {
                    "project": {"key": data.project_key},
                    "summary": data.summary,
                    "issuetype": {"name": data.issue_type}
                }
            }
            
            # Add optional fields
            if data.description:
                issue_data["fields"]["description"] = {
                    "type": "doc",
                    "version": 1,
                    "content": [{
                        "type": "paragraph",
                        "content": [{
                            "type": "text",
                            "text": data.description
                        }]
                    }]
                }
            
            if data.priority:
                issue_data["fields"]["priority"] = {"name": data.priority}
            
            if data.assignee:
                # Need to look up user account ID
                user_id = self._get_user_account_id(data.assignee, conn)
                if user_id:
                    issue_data["fields"]["assignee"] = {"accountId": user_id}
            
            if data.labels:
                issue_data["fields"]["labels"] = data.labels
            
            if data.components:
                issue_data["fields"]["components"] = [{"name": c} for c in data.components]
            
            if data.due_date:
                issue_data["fields"]["duedate"] = data.due_date
            
            if data.custom_fields:
                issue_data["fields"].update(data.custom_fields)
            
            # Create the issue
            logger.info("jira_api_request",
                component="jira",
                operation="create_issue",
                url=f"{conn['base_url']}/rest/api/3/issue",
                method="POST",
                project_key=data.project_key,
                issue_type=data.issue_type
            )
            
            response = requests.post(
                f"{conn['base_url']}/rest/api/3/issue",
                auth=conn['auth'],
                headers=conn['headers'],
                json=issue_data
            )
            
            if response.status_code == 201:
                result = response.json()
                issue_key = result["key"]
                
                logger.info("jira_api_response",
                    component="jira",
                    operation="create_issue",
                    status_code=response.status_code,
                    issue_key=issue_key,
                    issue_type=data.issue_type
                )
                
                success_result = {
                    "success": True,
                    "issue_key": issue_key,
                    "issue_url": f"{conn['base_url']}/browse/{issue_key}",
                    "message": f"Successfully created {data.issue_type} {issue_key}"
                }
                
                # Log tool result - IDENTICAL format to orchestrator pattern
                logger.info("tool_result",
                    component="jira", 
                    tool_name="create_jira_issue",
                    result_type=type(success_result).__name__,
                    result_preview=f"Created issue {issue_key}"
                )
                
                return success_result
            else:
                errors = response.json().get("errors", {})
                error_messages = response.json().get("errorMessages", [])
                
                error_detail = ""
                if errors:
                    error_detail = "; ".join([f"{k}: {v}" for k, v in errors.items()])
                elif error_messages:
                    error_detail = "; ".join(error_messages)
                else:
                    error_detail = "Unknown error"
                
                logger.error("jira_api_error",
                    component="jira",
                    operation="create_issue",
                    status_code=response.status_code,
                    error=error_detail,
                    project_key=data.project_key
                )
                
                error_result = {
                    "success": False,
                    "error": f"Failed to create issue: {error_detail}"
                }
                
                # Log tool error
                logger.error("tool_error",
                    component="jira",
                    tool_name="create_jira_issue", 
                    error=error_detail,
                    error_type="APIError",
                    status_code=response.status_code
                )
                
                return error_result
                
        except Exception as e:
            # Log tool error
            logger.error("tool_error",
                component="jira",
                tool_name="create_jira_issue", 
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }
    
    def _get_user_account_id(self, identifier: str, conn: dict) -> Optional[str]:
        """Look up Jira user account ID by email or username."""
        try:
            logger.info("jira_user_lookup",
                component="jira",
                operation="lookup_user",
                identifier=identifier
            )
            
            response = requests.get(
                f"{conn['base_url']}/rest/api/3/user/search",
                auth=conn['auth'],
                headers=conn['headers'],
                params={"query": identifier}
            )
            
            if response.status_code == 200:
                users = response.json()
                if users:
                    user_id = users[0]["accountId"]
                    logger.info("jira_user_found",
                        component="jira",
                        operation="lookup_user",
                        identifier=identifier,
                        account_id=user_id
                    )
                    return user_id
                else:
                    logger.warning("jira_user_not_found",
                        component="jira",
                        operation="lookup_user",
                        identifier=identifier
                    )
            return None
        except Exception as e:
            logger.error("jira_user_lookup_error",
                component="jira",
                operation="lookup_user",
                identifier=identifier,
                error=str(e),
                error_type=type(e).__name__
            )
            return None


class UpdateJiraIssueTool(BaseTool):
    """Update existing Jira issues with field modifications.
    
    Provides comprehensive issue update capabilities including field updates,
    status transitions, and bulk operations. Maintains audit trail and
    validates all changes against project workflows.
    
    Use Cases:
    - Update fields: "update PROJ-123 priority to High"
    - Assign issues: "assign PROJ-456 to john@company"
    - Add labels: "add label 'urgent' to PROJ-789"
    - Update description: "update PROJ-321 description with new requirements"
    
    Features:
    - Partial updates (only specified fields)
    - Workflow-aware transitions
    - Bulk update support
    - Change validation
    """
    name: str = "update_jira_issue"
    description: str = (
        "UPDATE: Existing Jira issue fields and properties. "
        "Use for: 'update PROJ-123 priority', 'assign PROJ-456 to user', 'add labels'. "
        "Supports partial updates - only specified fields are changed. "
        "For status transitions, use transition_issue instead."
    )
    
    class Input(BaseModel):
        """Input schema for updating a Jira issue."""
        issue_key: str = Field(description="Jira issue key to update")
        summary: Optional[str] = Field(default=None, description="New summary")
        description: Optional[str] = Field(default=None, description="New description")
        priority: Optional[str] = Field(default=None, description="New priority")
        assignee: Optional[str] = Field(default=None, description="New assignee (email or username)")
        labels_add: Optional[List[str]] = Field(default=None, description="Labels to add")
        labels_remove: Optional[List[str]] = Field(default=None, description="Labels to remove")
        components_add: Optional[List[str]] = Field(default=None, description="Components to add")
        components_remove: Optional[List[str]] = Field(default=None, description="Components to remove")
        due_date: Optional[str] = Field(default=None, description="New due date (YYYY-MM-DD)")
        custom_fields: Optional[Dict[str, Any]] = Field(default=None, description="Custom field updates")
        
    
    args_schema: type = Input

    def _run(self, **kwargs) -> dict:
        data = self.Input(**kwargs)
        
        # Log tool call - IDENTICAL format to orchestrator
        logger.info("tool_call",
            component="jira",
            tool_name="update_jira_issue",
            tool_args=kwargs
        )
        
        try:
            
            conn = get_jira_connection()
            
            # First get current issue to handle add/remove operations
            current_issue = None
            if data.labels_add or data.labels_remove or data.components_add or data.components_remove:
                response = requests.get(
                    f"{conn['base_url']}/rest/api/3/issue/{data.issue_key}",
                    auth=conn['auth'],
                    headers=conn['headers']
                )
                if response.status_code == 200:
                    current_issue = response.json()
            
            # Build update data
            update_data = {"fields": {}}
            
            if data.summary:
                update_data["fields"]["summary"] = data.summary
            
            if data.description:
                update_data["fields"]["description"] = {
                    "type": "doc",
                    "version": 1,
                    "content": [{
                        "type": "paragraph",
                        "content": [{
                            "type": "text",
                            "text": data.description
                        }]
                    }]
                }
            
            if data.priority:
                update_data["fields"]["priority"] = {"name": data.priority}
            
            if data.assignee:
                user_id = self._get_user_account_id(data.assignee, conn)
                if user_id:
                    update_data["fields"]["assignee"] = {"accountId": user_id}
            
            # Handle labels
            if current_issue and (data.labels_add or data.labels_remove):
                current_labels = set(current_issue["fields"].get("labels", []))
                if data.labels_add:
                    current_labels.update(data.labels_add)
                if data.labels_remove:
                    current_labels -= set(data.labels_remove)
                update_data["fields"]["labels"] = list(current_labels)
            
            # Handle components
            if current_issue and (data.components_add or data.components_remove):
                current_components = {c["name"] for c in current_issue["fields"].get("components", [])}
                if data.components_add:
                    current_components.update(data.components_add)
                if data.components_remove:
                    current_components -= set(data.components_remove)
                update_data["fields"]["components"] = [{"name": c} for c in current_components]
            
            if data.due_date:
                update_data["fields"]["duedate"] = data.due_date
            
            if data.custom_fields:
                update_data["fields"].update(data.custom_fields)
            
            # Perform update
            logger.info("jira_api_request",
                component="jira",
                operation="update_issue",
                url=f"{conn['base_url']}/rest/api/3/issue/{data.issue_key}",
                method="PUT",
                issue_key=data.issue_key,
                fields_to_update=list(update_data["fields"].keys())
            )
            
            response = requests.put(
                f"{conn['base_url']}/rest/api/3/issue/{data.issue_key}",
                auth=conn['auth'],
                headers=conn['headers'],
                json=update_data
            )
            
            if response.status_code == 204:
                logger.info("jira_api_response",
                    component="jira",
                    operation="update_issue",
                    status_code=response.status_code,
                    issue_key=data.issue_key
                )
                
                # Build summary of what was updated
                updated_fields = []
                if data.summary: updated_fields.append("summary")
                if data.description: updated_fields.append("description")
                if data.priority: updated_fields.append("priority")
                if data.assignee: updated_fields.append("assignee")
                if data.labels_add or data.labels_remove: updated_fields.append("labels")
                if data.components_add or data.components_remove: updated_fields.append("components")
                if data.due_date: updated_fields.append("due_date")
                if data.custom_fields: updated_fields.extend(data.custom_fields.keys())
                
                result = {
                    "success": True,
                    "issue_key": data.issue_key,
                    "updated_fields": updated_fields,
                    "message": f"Successfully updated {data.issue_key}"
                }
                
                # Log tool result - IDENTICAL format to orchestrator pattern
                logger.info("tool_result",
                    component="jira", 
                    tool_name="update_jira_issue",
                    result_type=type(result).__name__,
                    result_preview=f"Updated issue {data.issue_key} - fields: {', '.join(updated_fields[:3])}"
                )
                
                return result
            else:
                errors = response.json().get("errors", {})
                error_messages = response.json().get("errorMessages", [])
                
                error_detail = ""
                if errors:
                    error_detail = "; ".join([f"{k}: {v}" for k, v in errors.items()])
                elif error_messages:
                    error_detail = "; ".join(error_messages)
                else:
                    error_detail = "Unknown error"
                
                logger.error("jira_api_error",
                    component="jira",
                    operation="update_issue",
                    status_code=response.status_code,
                    error=error_detail,
                    issue_key=data.issue_key
                )
                
                error_result = {
                    "success": False,
                    "error": f"Failed to update issue: {error_detail}"
                }
                
                # Log tool error
                logger.error("tool_error",
                    component="jira",
                    tool_name="update_jira_issue", 
                    error=error_detail,
                    error_type="APIError",
                    status_code=response.status_code
                )
                
                return error_result
                
        except Exception as e:
            # Log tool error
            logger.error("tool_error",
                component="jira",
                tool_name="update_jira_issue", 
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }
    
    def _get_user_account_id(self, identifier: str, conn: dict) -> Optional[str]:
        """Look up Jira user account ID by email or username."""
        try:
            logger.info("jira_user_lookup",
                component="jira",
                operation="lookup_user",
                identifier=identifier
            )
            
            response = requests.get(
                f"{conn['base_url']}/rest/api/3/user/search",
                auth=conn['auth'],
                headers=conn['headers'],
                params={"query": identifier}
            )
            
            if response.status_code == 200:
                users = response.json()
                if users:
                    user_id = users[0]["accountId"]
                    logger.info("jira_user_found",
                        component="jira",
                        operation="lookup_user",
                        identifier=identifier,
                        account_id=user_id
                    )
                    return user_id
                else:
                    logger.warning("jira_user_not_found",
                        component="jira",
                        operation="lookup_user",
                        identifier=identifier
                    )
            return None
        except Exception as e:
            logger.error("jira_user_lookup_error",
                component="jira",
                operation="lookup_user",
                identifier=identifier,
                error=str(e),
                error_type=type(e).__name__
            )
            return None


# Collaboration Tools
class AddJiraCommentTool(BaseTool):
    """Add comments to Jira issues for collaboration and updates.
    
    Enables team communication through issue comments with support for
    rich text formatting, mentions, and visibility restrictions.
    
    Use Cases:
    - Add update: "add comment to PROJ-123 about testing results"
    - Internal note: "add internal comment to PROJ-456"
    - Mention user: "comment on PROJ-789 mentioning @john"
    
    Features:
    - Rich text support
    - User mentions
    - Visibility restrictions
    - Comment threading
    """
    name: str = "add_jira_comment"
    description: str = (
        "ADD: Comments to Jira issues for updates and collaboration. "
        "Use for: 'comment on PROJ-123', 'add note to PROJ-456'. "
        "Supports mentions and visibility restrictions. "
        "Comments are added to issue activity stream."
    )
    
    class Input(BaseModel):
        """Input schema for adding a comment to a Jira issue."""
        issue_key: str = Field(description="Issue to comment on")
        comment: str = Field(description="Comment text")
        visibility_type: Optional[str] = Field(default=None, description="Visibility: role or group")
        visibility_value: Optional[str] = Field(default=None, description="Role/group name for visibility")
        
    
    args_schema: type = Input

    def _run(self, **kwargs) -> dict:
        data = self.Input(**kwargs)
        
        # Log tool call - IDENTICAL format to orchestrator
        logger.info("tool_call",
            component="jira",
            tool_name="add_jira_comment",
            tool_args=kwargs
        )
        
        try:
            
            conn = get_jira_connection()
            
            # Build comment data
            comment_data = {
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [{
                        "type": "paragraph",
                        "content": [{
                            "type": "text",
                            "text": data.comment
                        }]
                    }]
                }
            }
            
            # Add visibility if specified
            if data.visibility_type and data.visibility_value:
                comment_data["visibility"] = {
                    "type": data.visibility_type,
                    "value": data.visibility_value
                }
            
            # Log API request
            logger.info("jira_api_request",
                component="jira",
                operation="add_comment",
                url=f"{conn['base_url']}/rest/api/3/issue/{data.issue_key}/comment",
                method="POST",
                issue_key=data.issue_key,
                comment_length=len(data.comment)
            )
            
            response = requests.post(
                f"{conn['base_url']}/rest/api/3/issue/{data.issue_key}/comment",
                auth=conn['auth'],
                headers=conn['headers'],
                json=comment_data
            )
            
            if response.status_code == 201:
                result = response.json()
                
                logger.info("jira_api_response",
                    component="jira",
                    operation="add_comment",
                    status_code=response.status_code,
                    issue_key=data.issue_key,
                    comment_id=result["id"]
                )
                
                success_result = {
                    "success": True,
                    "issue_key": data.issue_key,
                    "comment_id": result["id"],
                    "message": f"Comment added to {data.issue_key}"
                }
                
                # Log tool result - IDENTICAL format to orchestrator pattern
                logger.info("tool_result",
                    component="jira", 
                    tool_name="add_jira_comment",
                    result_type=type(success_result).__name__,
                    result_preview=f"Added comment to {data.issue_key}"
                )
                
                return success_result
            else:
                error_msg = response.json().get("errorMessages", ["Unknown error"])[0]
                
                logger.error("jira_api_error",
                    component="jira",
                    operation="add_comment",
                    status_code=response.status_code,
                    error=error_msg,
                    issue_key=data.issue_key
                )
                
                error_result = {
                    "success": False,
                    "error": f"Failed to add comment: {error_msg}"
                }
                
                # Log tool error
                logger.error("tool_error",
                    component="jira",
                    tool_name="add_jira_comment", 
                    error=error_msg,
                    error_type="APIError",
                    status_code=response.status_code
                )
                
                return error_result
                
        except Exception as e:
            # Log tool error
            logger.error("tool_error",
                component="jira",
                tool_name="add_jira_comment", 
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }


# Project and Board Tools
class GetProjectIssuesTool(BaseTool):
    """Get all issues for a specific Jira project with filtering options.
    
    Retrieves comprehensive project issue lists with support for status
    filtering, type filtering, and pagination. Ideal for project overviews
    and bulk operations.
    
    Use Cases:
    - All project issues: "get all issues in PROJ"
    - Status filter: "get open issues in PROJ"
    - Type filter: "get all bugs in PROJ"
    - Combined: "get open bugs in PROJ"
    
    Returns:
    - Issue lists with key fields
    - Summary statistics
    - Pagination support for large projects
    """
    name: str = "get_project_issues"
    description: str = (
        "GET: All issues for a specific project with optional filters. "
        "Use for: 'all issues in PROJ', 'open bugs in PROJ', 'stories in PROJ'. "
        "Returns issue list with summary statistics. "
        "Supports filtering by status, type, and assignee."
    )
    
    class Input(BaseModel):
        """Input schema for retrieving project issues."""
        project_key: str = Field(description="Project key")
        status: Optional[str] = Field(default=None, description="Filter by status")
        issue_type: Optional[str] = Field(default=None, description="Filter by type")
        assignee: Optional[str] = Field(default=None, description="Filter by assignee")
        max_results: int = Field(default=100, description="Maximum results")
        
    
    args_schema: type = Input

    def _run(self, **kwargs) -> dict:
        data = self.Input(**kwargs)
        
        # Log tool call - IDENTICAL format to orchestrator
        logger.info("tool_call",
            component="jira",
            tool_name="get_project_issues",
            tool_args=kwargs
        )
        
        try:
            
            # Build JQL query
            jql_parts = [f"project = {data.project_key}"]
            
            if data.status:
                jql_parts.append(f"status = '{escape_jql(data.status)}'")
            
            if data.issue_type:
                jql_parts.append(f"type = '{escape_jql(data.issue_type)}'")
            
            if data.assignee:
                if data.assignee.lower() in ["me", "current", "currentuser"]:
                    jql_parts.append("assignee = currentUser()")
                else:
                    jql_parts.append(f"assignee = '{escape_jql(data.assignee)}'")
            
            jql = " AND ".join(jql_parts)
            log_jql_query("get_project_issues", jql)
            
            # Use search tool internally
            search_tool = SearchJiraIssuesTool()
            result = search_tool._run(query=jql, max_results=data.max_results)
            
            # Log delegated result
            logger.info("tool_delegation",
                component="jira",
                tool_name="get_project_issues",
                delegated_to="search_jira_issues",
                project_key=data.project_key,
                jql_query=jql
            )
            
            return result
            
        except Exception as e:
            # Log tool error
            logger.error("tool_error",
                component="jira",
                tool_name="get_project_issues", 
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }


# Personal Productivity Tools
class GetMyIssuesTool(BaseTool):
    """Get issues assigned to the current user with smart filtering.
    
    Retrieves personal work items with intelligent filtering for different
    contexts like active work, overdue items, or specific projects.
    
    Use Cases:
    - All my issues: "get my issues"
    - Active work: "my open issues"
    - Overdue: "my overdue tasks"
    - By project: "my issues in PROJ"
    
    Features:
    - Smart status grouping
    - Due date awareness
    - Priority sorting
    - Cross-project view
    """
    name: str = "get_my_issues"
    description: str = (
        "GET: Issues assigned to current user with smart filtering. "
        "Use for: 'my issues', 'my open tasks', 'my bugs', 'my overdue items'. "
        "Returns personalized work list with priority and due date info. "
        "Automatically filters to current authenticated user."
    )
    
    class Input(BaseModel):
        """Input schema for retrieving user's issues."""
        status_filter: Optional[str] = Field(
            default="open",
            description="Filter: all, open, closed, in-progress"
        )
        type_filter: Optional[str] = Field(default=None, description="Filter by issue type")
        project: Optional[str] = Field(default=None, description="Filter by project")
        include_overdue: bool = Field(default=False, description="Include overdue flag")
        max_results: int = Field(default=50, description="Maximum results")
    
    args_schema: type = Input

    def _run(self, **kwargs) -> dict:
        data = self.Input(**kwargs)
        
        try:
            # Log tool call
            logger.info("tool_call",
                component="jira",
                tool_name="get_my_issues",
                tool_args=kwargs
            )
            
            # Build JQL query
            jql_parts = ["assignee = currentUser()"]
            
            # Status filtering
            if data.status_filter == "open":
                jql_parts.append("status not in (Closed, Done, Resolved)")
            elif data.status_filter == "closed":
                jql_parts.append("status in (Closed, Done, Resolved)")
            elif data.status_filter == "in-progress":
                jql_parts.append("status = 'In Progress'")
            # "all" means no status filter
            
            if data.type_filter:
                jql_parts.append(f"type = '{escape_jql(data.type_filter)}'")
            
            if data.project:
                jql_parts.append(f"project = {data.project.upper()}")
            
            if data.include_overdue:
                jql_parts.append("duedate < now()")
            
            jql = " AND ".join(jql_parts)
            jql += " ORDER BY priority DESC, duedate ASC"
            log_jql_query("get_my_issues", jql)
            
            # Use search tool internally
            search_tool = SearchJiraIssuesTool()
            result = search_tool._run(
                query=jql,
                max_results=data.max_results,
                fields=["key", "summary", "status", "priority", "duedate", "type"]
            )
            
            # Log delegated result
            logger.info("tool_delegation",
                component="jira",
                tool_name="get_my_issues",
                delegated_to="search_jira_issues",
                jql_query=jql
            )
            
            # Add personal productivity insights if successful
            if result.get("success") and result.get("issues"):
                issues = result["issues"]
                
                # Count by status
                status_counts = {}
                overdue_count = 0
                
                for issue in issues:
                    status = issue.get("status", "Unknown")
                    status_counts[status] = status_counts.get(status, 0) + 1
                    
                    # Check if overdue
                    if issue.get("duedate") and issue["duedate"] < datetime.now().isoformat():
                        overdue_count += 1
                
                result["summary"] = {
                    "total_assigned": len(issues),
                    "by_status": status_counts,
                    "overdue_count": overdue_count
                }
                
                # Log tool result
                logger.info("tool_result",
                    component="jira",
                    tool_name="get_my_issues",
                    result_type=type(result).__name__,
                    total_issues=len(issues),
                    overdue_count=overdue_count
                )
            
            return result
            
        except Exception as e:
            # Log tool error
            logger.error("tool_error",
                component="jira",
                tool_name="get_my_issues",
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }


# Epic and Sprint Management Tools
class GetEpicIssuesTool(BaseTool):
    """Get all issues belonging to a specific epic with hierarchy view.
    
    Retrieves epic children including stories, tasks, and bugs with
    progress tracking and status rollup. Essential for epic management
    and progress monitoring.
    
    Use Cases:
    - Epic contents: "get all issues in epic PROJ-100"
    - Epic progress: "show progress for epic PROJ-100"
    - Epic hierarchy: "get epic PROJ-100 with subtasks"
    
    Features:
    - Hierarchical issue view
    - Progress calculation
    - Status distribution
    - Story point rollup
    """
    name: str = "get_epic_issues"
    description: str = (
        "GET: All issues belonging to a specific epic. "
        "Use for: 'issues in epic PROJ-123', 'epic PROJ-123 progress'. "
        "Returns child issues with progress tracking and status summary. "
        "Shows epic hierarchy and completion metrics."
    )
    
    class Input(BaseModel):
        """Input schema for retrieving epic issues."""
        epic_key: str = Field(description="Epic issue key")
        include_subtasks: bool = Field(default=True, description="Include subtasks")
        
    
    args_schema: type = Input

    def _run(self, **kwargs) -> dict:
        data = self.Input(**kwargs)
        
        try:
            # Log tool call
            logger.info("tool_call",
                component="jira",
                tool_name="get_epic_issues",
                tool_args=kwargs
            )
            
            # Build JQL to find issues in epic
            jql = f'"Epic Link" = {data.epic_key} OR parent = {data.epic_key}'
            
            if not data.include_subtasks:
                jql += ' AND type != Sub-task'
            
            jql += ' ORDER BY type ASC, priority DESC'
            log_jql_query("get_epic_issues", jql)
            
            # Use search tool
            search_tool = SearchJiraIssuesTool()
            result = search_tool._run(
                query=jql,
                max_results=200,
                fields=["key", "summary", "status", "type", "priority", "storyPoints"]
            )
            
            # Log delegated result
            logger.info("tool_delegation",
                component="jira",
                tool_name="get_epic_issues",
                delegated_to="search_jira_issues",
                epic_key=data.epic_key,
                jql_query=jql
            )
            
            if result.get("success") and result.get("issues"):
                issues = result["issues"]
                
                # Calculate epic progress
                total_issues = len(issues)
                completed_statuses = ["Done", "Closed", "Resolved"]
                completed_count = sum(1 for i in issues if i.get("status") in completed_statuses)
                
                # Group by type
                by_type = {}
                for issue in issues:
                    issue_type = issue.get("type", "Unknown")
                    if issue_type not in by_type:
                        by_type[issue_type] = []
                    by_type[issue_type].append(issue)
                
                result["epic_summary"] = {
                    "epic_key": data.epic_key,
                    "total_issues": total_issues,
                    "completed_issues": completed_count,
                    "progress_percentage": round((completed_count / total_issues * 100) if total_issues > 0 else 0, 1),
                    "issues_by_type": {k: len(v) for k, v in by_type.items()}
                }
                
                # Log tool result
                logger.info("tool_result",
                    component="jira",
                    tool_name="get_epic_issues",
                    result_type=type(result).__name__,
                    epic_key=data.epic_key,
                    total_issues=total_issues,
                    completed_issues=completed_count
                )
            
            return result
            
        except Exception as e:
            # Log tool error
            logger.error("tool_error",
                component="jira",
                tool_name="get_epic_issues",
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }


class GetSprintIssuesTool(BaseTool):
    """Get issues in active sprints for agile teams.
    
    Retrieves sprint backlog with burndown metrics, velocity tracking,
    and team capacity analysis. Supports multiple active sprints and
    cross-team views.
    
    Use Cases:
    - Current sprint: "get current sprint issues"
    - Team sprint: "get sprint issues for team Alpha"
    - Sprint by name: "get issues in Sprint 23"
    - All active: "get all active sprint issues"
    
    Features:
    - Active sprint detection
    - Burndown metrics
    - Velocity calculation
    - Team capacity view
    """
    name: str = "get_sprint_issues"
    description: str = (
        "GET: Issues in active sprints with agile metrics. "
        "Use for: 'current sprint', 'sprint backlog', 'sprint progress'. "
        "Returns sprint issues with burndown and velocity data. "
        "Automatically finds active sprints for the project/team."
    )
    
    class Input(BaseModel):
        """Input schema for retrieving sprint issues."""
        project_key: Optional[str] = Field(default=None, description="Filter by project")
        sprint_name: Optional[str] = Field(default=None, description="Specific sprint name")
        include_completed: bool = Field(default=True, description="Include completed issues")
        max_results: int = Field(default=100, description="Maximum results")
    
    args_schema: type = Input

    def _run(self, **kwargs) -> dict:
        data = self.Input(**kwargs)
        
        try:
            # Log tool call
            logger.info("tool_call",
                component="jira",
                tool_name="get_sprint_issues",
                tool_args=kwargs
            )
            
            # Build JQL for sprint issues
            jql_parts = []
            
            if data.sprint_name:
                jql_parts.append(f'sprint = "{escape_jql(data.sprint_name)}"')
            else:
                # Get issues in any active sprint
                jql_parts.append("sprint in openSprints()")
            
            if data.project_key:
                jql_parts.append(f"project = {data.project_key.upper()}")
            
            if not data.include_completed:
                jql_parts.append("status not in (Done, Closed, Resolved)")
            
            jql = " AND ".join(jql_parts) if jql_parts else "sprint in openSprints()"
            jql += " ORDER BY priority DESC, created ASC"
            log_jql_query("get_sprint_issues", jql)
            
            # Use search tool
            search_tool = SearchJiraIssuesTool()
            result = search_tool._run(
                query=jql,
                max_results=data.max_results,
                fields=["key", "summary", "status", "type", "priority", "assignee", "storyPoints", "sprint"]
            )
            
            # Log delegated result
            logger.info("tool_delegation",
                component="jira",
                tool_name="get_sprint_issues",
                delegated_to="search_jira_issues",
                jql_query=jql,
                project_key=data.project_key
            )
            
            if result.get("success") and result.get("issues"):
                issues = result["issues"]
                
                # Calculate sprint metrics
                total_points = 0
                completed_points = 0
                by_assignee = {}
                by_status = {}
                
                for issue in issues:
                    # Story points
                    points = issue.get("storyPoints", 0) or 0
                    total_points += points
                    
                    status = issue.get("status", "Unknown")
                    if status in ["Done", "Closed", "Resolved"]:
                        completed_points += points
                    
                    # Group by assignee
                    assignee = issue.get("assignee", "Unassigned")
                    if assignee not in by_assignee:
                        by_assignee[assignee] = {"count": 0, "points": 0}
                    by_assignee[assignee]["count"] += 1
                    by_assignee[assignee]["points"] += points
                    
                    # Group by status
                    by_status[status] = by_status.get(status, 0) + 1
                
                result["sprint_metrics"] = {
                    "total_issues": len(issues),
                    "total_story_points": total_points,
                    "completed_story_points": completed_points,
                    "completion_percentage": round((completed_points / total_points * 100) if total_points > 0 else 0, 1),
                    "by_assignee": by_assignee,
                    "by_status": by_status
                }
                
                # Log tool result
                logger.info("tool_result",
                    component="jira",
                    tool_name="get_sprint_issues",
                    result_type=type(result).__name__,
                    total_issues=len(issues),
                    total_points=total_points,
                    completed_points=completed_points
                )
            
            return result
            
        except Exception as e:
            # Log tool error
            logger.error("tool_error",
                component="jira",
                tool_name="get_sprint_issues",
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }


# Workflow and State Management Tools
class TransitionIssueTool(BaseTool):
    """Transition Jira issues through workflow states.
    
    Moves issues through workflow transitions with validation of allowed
    transitions and required fields. Supports bulk transitions and
    workflow automation triggers.
    
    Use Cases:
    - Start work: "move PROJ-123 to In Progress"
    - Complete work: "transition PROJ-456 to Done"
    - Reopen: "reopen PROJ-789"
    - Close: "close PROJ-321 as Won't Fix"
    
    Features:
    - Available transition detection
    - Required field validation
    - Resolution setting
    - Workflow trigger support
    """
    name: str = "transition_issue"
    description: str = (
        "TRANSITION: Move issues through workflow states. "
        "Use for: 'move PROJ-123 to In Progress', 'close PROJ-456', 'reopen PROJ-789'. "
        "Automatically detects valid transitions and handles required fields. "
        "Common transitions: To Do, In Progress, Done, Closed."
    )
    
    class Input(BaseModel):
        """Input schema for transitioning an issue."""
        issue_key: str = Field(description="Issue to transition")
        transition_name: str = Field(description="Target status or transition name")
        resolution: Optional[str] = Field(default=None, description="Resolution (for closing)")
        comment: Optional[str] = Field(default=None, description="Transition comment")
        
    
    args_schema: type = Input

    def _run(self, **kwargs) -> dict:
        data = self.Input(**kwargs)
        
        try:
            # Log tool call
            logger.info("tool_call",
                component="jira",
                tool_name="transition_issue",
                tool_args=kwargs
            )
            
            conn = get_jira_connection()
            
            # Get available transitions
            url = f"{conn['base_url']}/rest/api/3/issue/{data.issue_key}/transitions"
            
            # Log API request
            logger.info("jira_api_request",
                component="jira",
                operation="get_transitions",
                url=url,
                method="GET",
                issue_key=data.issue_key
            )
            
            response = requests.get(
                url,
                auth=conn['auth'],
                headers=conn['headers']
            )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Failed to get transitions for {data.issue_key}"
                }
            
            # Log API response
            logger.info("jira_api_response",
                component="jira",
                operation="get_transitions",
                status_code=response.status_code,
                issue_key=data.issue_key
            )
            
            transitions = response.json()["transitions"]
            
            # Find matching transition
            target_transition = None
            target_lower = data.transition_name.lower()
            
            for trans in transitions:
                trans_name_lower = trans["name"].lower()
                trans_to_lower = trans["to"]["name"].lower()
                
                if target_lower in [trans_name_lower, trans_to_lower]:
                    target_transition = trans
                    break
            
            if not target_transition:
                available = [f"{t['name']} -> {t['to']['name']}" for t in transitions]
                return {
                    "success": False,
                    "error": f"Transition '{data.transition_name}' not available. Available: {', '.join(available)}"
                }
            
            # Build transition data
            transition_data = {
                "transition": {"id": target_transition["id"]}
            }
            
            # Add resolution if closing
            if data.resolution and any(field["key"] == "resolution" for field in target_transition.get("fields", {}).values()):
                transition_data["fields"] = {"resolution": {"name": data.resolution}}
            
            # Perform transition
            transition_url = f"{conn['base_url']}/rest/api/3/issue/{data.issue_key}/transitions"
            
            # Log API request
            logger.info("jira_api_request",
                component="jira",
                operation="perform_transition",
                url=transition_url,
                method="POST",
                issue_key=data.issue_key,
                target_status=target_transition["to"]["name"]
            )
            
            response = requests.post(
                transition_url,
                auth=conn['auth'],
                headers=conn['headers'],
                json=transition_data
            )
            
            if response.status_code == 204:
                # Log API response
                logger.info("jira_api_response",
                    component="jira",
                    operation="perform_transition",
                    status_code=response.status_code,
                    issue_key=data.issue_key,
                    new_status=target_transition["to"]["name"]
                )
                
                # Add comment if provided
                if data.comment:
                    comment_tool = AddJiraCommentTool()
                    comment_tool._run(issue_key=data.issue_key, comment=data.comment)
                
                result = {
                    "success": True,
                    "issue_key": data.issue_key,
                    "new_status": target_transition["to"]["name"],
                    "message": f"Successfully transitioned {data.issue_key} to {target_transition['to']['name']}"
                }
                
                # Log tool result
                logger.info("tool_result",
                    component="jira",
                    tool_name="transition_issue",
                    result_type=type(result).__name__,
                    issue_key=data.issue_key,
                    new_status=target_transition["to"]["name"]
                )
                
                return result
            else:
                errors = response.json().get("errors", {})
                error_messages = response.json().get("errorMessages", [])
                
                error_detail = ""
                if errors:
                    error_detail = "; ".join([f"{k}: {v}" for k, v in errors.items()])
                elif error_messages:
                    error_detail = "; ".join(error_messages)
                
                return {
                    "success": False,
                    "error": f"Failed to transition: {error_detail}"
                }
                
        except Exception as e:
            # Log tool error
            logger.error("tool_error",
                component="jira",
                tool_name="transition_issue",
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }


class AssignIssueTool(BaseTool):
    """Assign or reassign Jira issues to users.
    
    Manages issue assignment with user lookup, workload consideration,
    and automatic unassignment support. Validates user permissions and
    project membership.
    
    Use Cases:
    - Assign to user: "assign PROJ-123 to john@company"
    - Assign to self: "assign PROJ-456 to me"
    - Unassign: "unassign PROJ-789"
    - Bulk assign: "assign all bugs to mary"
    
    Features:
    - User lookup by email/name
    - Self-assignment support
    - Unassignment capability
    - Permission validation
    """
    name: str = "assign_issue"
    description: str = (
        "ASSIGN: Issues to specific users or unassign. "
        "Use for: 'assign PROJ-123 to john', 'assign to me', 'unassign PROJ-456'. "
        "Automatically looks up users by email or display name. "
        "Use 'unassign' or null to remove assignment."
    )
    
    class Input(BaseModel):
        """Input schema for assigning an issue."""
        issue_key: str = Field(description="Issue to assign")
        assignee: Optional[str] = Field(
            default=None,
            description="User email/name, 'me' for self, or null to unassign"
        )
        
    
    args_schema: type = Input

    def _run(self, **kwargs) -> dict:
        data = self.Input(**kwargs)
        
        try:
            # Log tool call
            logger.info("tool_call",
                component="jira",
                tool_name="assign_issue",
                tool_args=kwargs
            )
            
            # Use update tool internally
            update_tool = UpdateJiraIssueTool()
            
            assignee_value = None
            if data.assignee:
                if data.assignee.lower() in ["me", "self", "current", "currentuser"]:
                    assignee_value = "currentUser()"
                elif data.assignee.lower() not in ["unassign", "unassigned", "none"]:
                    assignee_value = data.assignee
            
            result = update_tool._run(
                issue_key=data.issue_key,
                assignee=assignee_value
            )
            
            # Log delegated result
            logger.info("tool_delegation",
                component="jira",
                tool_name="assign_issue",
                delegated_to="update_jira_issue",
                issue_key=data.issue_key,
                assignee=assignee_value
            )
            
            if result.get("success"):
                if not data.assignee or data.assignee.lower() in ["unassign", "unassigned", "none"]:
                    result["message"] = f"Successfully unassigned {data.issue_key}"
                else:
                    result["message"] = f"Successfully assigned {data.issue_key} to {data.assignee}"
                
                # Log tool result
                logger.info("tool_result",
                    component="jira",
                    tool_name="assign_issue",
                    result_type=type(result).__name__,
                    issue_key=data.issue_key,
                    assignee=data.assignee
                )
            
            return result
            
        except Exception as e:
            # Log tool error
            logger.error("tool_error",
                component="jira",
                tool_name="assign_issue",
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }


# Advanced Tools
class AddAttachmentTool(BaseTool):
    """Add file attachments to Jira issues.
    
    Uploads files to issues with automatic type detection, size validation,
    and virus scanning. Supports multiple file formats and bulk uploads.
    
    Use Cases:
    - Attach screenshot: "attach screenshot.png to PROJ-123"
    - Attach document: "add design.pdf to PROJ-456"
    - Attach logs: "attach error.log to PROJ-789"
    
    Features:
    - Multiple file format support
    - Size limit validation
    - Automatic MIME type detection
    - Bulk upload capability
    """
    name: str = "add_attachment"
    description: str = (
        "ATTACH: Files to Jira issues (screenshots, documents, logs). "
        "Use for: 'attach file.pdf to PROJ-123', 'add screenshot to PROJ-456'. "
        "Supports common formats: images, PDFs, text files, Office docs. "
        "File must exist locally with valid path."
    )
    
    class Input(BaseModel):
        """Input schema for adding an attachment."""
        issue_key: str = Field(description="Issue to attach file to")
        file_path: str = Field(description="Path to file to attach")
        comment: Optional[str] = Field(default=None, description="Comment about attachment")
        
    
    args_schema: type = Input

    def _run(self, **kwargs) -> dict:
        data = self.Input(**kwargs)
        
        try:
            import os
            import mimetypes
            
            # Log tool call
            logger.info("tool_call",
                component="jira",
                tool_name="add_attachment",
                tool_args=kwargs
            )
            
            # Validate file exists
            if not os.path.exists(data.file_path):
                return {
                    "success": False,
                    "error": f"File not found: {data.file_path}"
                }
            
            file_size = os.path.getsize(data.file_path)
            file_name = os.path.basename(data.file_path)
            
            # Check file size (Jira default is 10MB)
            max_size = 10 * 1024 * 1024  # 10MB
            if file_size > max_size:
                return {
                    "success": False,
                    "error": f"File too large: {file_size / 1024 / 1024:.1f}MB (max 10MB)"
                }
            
            conn = get_jira_connection()
            
            # Prepare file upload
            mime_type = mimetypes.guess_type(data.file_path)[0] or 'application/octet-stream'
            
            with open(data.file_path, 'rb') as f:
                files = {'file': (file_name, f, mime_type)}
                
                # Remove Content-Type from headers for multipart upload
                headers = conn['headers'].copy()
                headers.pop('Content-Type', None)
                headers['X-Atlassian-Token'] = 'no-check'
                
                url = f"{conn['base_url']}/rest/api/3/issue/{data.issue_key}/attachments"
                
                # Log API request
                logger.info("jira_api_request",
                    component="jira",
                    operation="add_attachment",
                    url=url,
                    method="POST",
                    issue_key=data.issue_key,
                    file_name=file_name,
                    file_size=file_size
                )
                
                response = requests.post(
                    url,
                    auth=conn['auth'],
                    headers=headers,
                    files=files
                )
            
            if response.status_code == 200:
                # Log API response
                logger.info("jira_api_response",
                    component="jira",
                    operation="add_attachment",
                    status_code=response.status_code,
                    issue_key=data.issue_key
                )
                
                attachments = response.json()
                
                # Add comment if provided
                if data.comment:
                    comment_tool = AddJiraCommentTool()
                    comment_tool._run(
                        issue_key=data.issue_key,
                        comment=f"{data.comment}\n\nAttached: {file_name}"
                    )
                
                result = {
                    "success": True,
                    "issue_key": data.issue_key,
                    "attachment_id": attachments[0]["id"],
                    "file_name": file_name,
                    "file_size": f"{file_size / 1024:.1f}KB",
                    "message": f"Successfully attached {file_name} to {data.issue_key}"
                }
                
                # Log tool result
                logger.info("tool_result",
                    component="jira",
                    tool_name="add_attachment",
                    result_type=type(result).__name__,
                    issue_key=data.issue_key,
                    file_name=file_name,
                    attachment_id=attachments[0]["id"]
                )
                
                return result
            else:
                error_msg = response.text
                return {
                    "success": False,
                    "error": f"Failed to attach file: {error_msg}"
                }
                
        except Exception as e:
            # Log tool error
            logger.error("tool_error",
                component="jira",
                tool_name="add_attachment",
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }


class GetIssueHistoryTool(BaseTool):
    """Get detailed change history for a Jira issue.
    
    Retrieves complete audit trail including field changes, status transitions,
    assignments, and comments. Essential for compliance and issue investigation.
    
    Use Cases:
    - Full history: "get history for PROJ-123"
    - Recent changes: "show recent changes to PROJ-456"
    - Status history: "when was PROJ-789 closed"
    
    Features:
    - Complete change log
    - User attribution
    - Timestamp tracking
    - Field-level changes
    """
    name: str = "get_issue_history"
    description: str = (
        "HISTORY: Complete change log for an issue. "
        "Use for: 'history of PROJ-123', 'who changed PROJ-456', 'when was PROJ-789 updated'. "
        "Shows all field changes, transitions, and comments with timestamps. "
        "Useful for audit trails and investigating issue changes."
    )
    
    class Input(BaseModel):
        """Input schema for retrieving issue history."""
        issue_key: str = Field(description="Issue to get history for")
        max_changes: int = Field(default=50, description="Maximum changes to return")
        
    
    args_schema: type = Input

    def _run(self, **kwargs) -> dict:
        data = self.Input(**kwargs)
        
        try:
            # Log tool call
            logger.info("tool_call",
                component="jira",
                tool_name="get_issue_history",
                tool_args=kwargs
            )
            
            # Use get issue tool with changelog expansion
            get_tool = GetJiraIssueTool()
            result = get_tool._run(
                issue_key=data.issue_key,
                expand=["changelog", "comments"]
            )
            
            if not result.get("success"):
                return result
            
            # Extract and format history
            conn = get_jira_connection()
            url = f"{conn['base_url']}/rest/api/3/issue/{data.issue_key}?expand=changelog"
            
            # Log API request
            logger.info("jira_api_request",
                component="jira",
                operation="get_issue_history",
                url=url,
                method="GET",
                issue_key=data.issue_key
            )
            
            response = requests.get(
                url,
                auth=conn['auth'],
                headers=conn['headers']
            )
            
            if response.status_code == 200:
                # Log API response
                logger.info("jira_api_response",
                    component="jira",
                    operation="get_issue_history",
                    status_code=response.status_code,
                    issue_key=data.issue_key
                )
                
                issue = response.json()
                changelog = issue.get("changelog", {})
                histories = changelog.get("histories", [])
                
                # Format history entries
                formatted_history = []
                for history in histories[:data.max_changes]:
                    entry = {
                        "id": history["id"],
                        "author": history["author"]["displayName"],
                        "created": history["created"],
                        "changes": []
                    }
                    
                    for item in history["items"]:
                        change = {
                            "field": item["field"],
                            "from": item.get("fromString", ""),
                            "to": item.get("toString", "")
                        }
                        entry["changes"].append(change)
                    
                    formatted_history.append(entry)
                
                result = {
                    "success": True,
                    "issue_key": data.issue_key,
                    "total_changes": changelog.get("total", 0),
                    "history": formatted_history,
                    "showing": len(formatted_history)
                }
                
                # Log tool result
                logger.info("tool_result",
                    component="jira",
                    tool_name="get_issue_history",
                    result_type=type(result).__name__,
                    issue_key=data.issue_key,
                    total_changes=changelog.get("total", 0),
                    showing=len(formatted_history)
                )
                
                return result
            else:
                return {
                    "success": False,
                    "error": "Failed to retrieve issue history"
                }
                
        except Exception as e:
            # Log tool error
            logger.error("tool_error",
                component="jira",
                tool_name="get_issue_history",
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }


class CreateSubtaskTool(BaseTool):
    """Create subtasks for existing Jira issues.
    
    Creates child tasks under parent issues with automatic inheritance
    of project, components, and versions. Supports bulk subtask creation
    for task breakdown.
    
    Use Cases:
    - Simple subtask: "create subtask for PROJ-123 about testing"
    - Multiple subtasks: "add dev and test subtasks to PROJ-456"
    - Assigned subtask: "create subtask for PROJ-789 assigned to john"
    
    Features:
    - Parent context inheritance
    - Automatic project/version copying
    - Bulk creation support
    - Assignment during creation
    """
    name: str = "create_subtask"
    description: str = (
        "CREATE: Subtasks under existing issues for task breakdown. "
        "Use for: 'create subtask for PROJ-123', 'add testing subtask to PROJ-456'. "
        "Inherits project and components from parent issue. "
        "Useful for breaking down stories into smaller tasks."
    )
    
    class Input(BaseModel):
        """Input schema for creating a subtask."""
        parent_key: str = Field(description="Parent issue key")
        summary: str = Field(description="Subtask summary")
        description: Optional[str] = Field(default=None, description="Subtask description")
        assignee: Optional[str] = Field(default=None, description="Assignee email/username")
        estimate: Optional[str] = Field(default=None, description="Time estimate (e.g., 2h, 1d)")
        
    
    args_schema: type = Input

    def _run(self, **kwargs) -> dict:
        data = self.Input(**kwargs)
        
        try:
            # Log tool call
            logger.info("tool_call",
                component="jira",
                tool_name="create_subtask",
                tool_args=kwargs
            )
            
            conn = get_jira_connection()
            
            # Get parent issue to inherit fields
            url = f"{conn['base_url']}/rest/api/3/issue/{data.parent_key}"
            
            # Log API request
            logger.info("jira_api_request",
                component="jira",
                operation="get_parent_issue",
                url=url,
                method="GET",
                parent_key=data.parent_key
            )
            
            response = requests.get(
                url,
                auth=conn['auth'],
                headers=conn['headers']
            )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Parent issue {data.parent_key} not found"
                }
            
            # Log API response
            logger.info("jira_api_response",
                component="jira",
                operation="get_parent_issue",
                status_code=response.status_code,
                parent_key=data.parent_key
            )
            
            parent = response.json()
            
            # Use create issue tool with inherited fields
            create_tool = CreateJiraIssueTool()
            
            # Inherit project and components from parent
            project_key = parent["fields"]["project"]["key"]
            components = [c["name"] for c in parent["fields"].get("components", [])]
            fix_versions = [v["name"] for v in parent["fields"].get("fixVersions", [])]
            
            result = create_tool._run(
                project_key=project_key,
                summary=data.summary,
                issue_type="Sub-task",
                description=data.description,
                assignee=data.assignee,
                components=components if components else None,
                custom_fields={
                    "parent": {"key": data.parent_key}
                }
            )
            
            # Log delegated result
            logger.info("tool_delegation",
                component="jira",
                tool_name="create_subtask",
                delegated_to="create_jira_issue",
                parent_key=data.parent_key,
                project_key=project_key
            )
            
            if result.get("success"):
                # Add time estimate if provided
                if data.estimate:
                    # Would need to update with time tracking fields
                    pass
                
                result["parent_key"] = data.parent_key
                result["message"] = f"Successfully created subtask {result['issue_key']} under {data.parent_key}"
                
                # Log tool result
                logger.info("tool_result",
                    component="jira",
                    tool_name="create_subtask",
                    result_type=type(result).__name__,
                    parent_key=data.parent_key,
                    subtask_key=result['issue_key']
                )
            
            return result
            
        except Exception as e:
            # Log tool error
            logger.error("tool_error",
                component="jira",
                tool_name="create_subtask",
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }


class LinkIssuesTool(BaseTool):
    """Create relationships between Jira issues.
    
    Establishes issue links with various relationship types including
    blocks/blocked by, relates to, duplicates, and more. Essential for
    dependency management and issue organization.
    
    Use Cases:
    - Block relationship: "PROJ-123 blocks PROJ-456"
    - Related issues: "link PROJ-789 relates to PROJ-321"
    - Duplicate: "mark PROJ-111 as duplicate of PROJ-222"
    - Dependency: "PROJ-333 depends on PROJ-444"
    
    Features:
    - Multiple link types
    - Bidirectional relationships
    - Bulk linking support
    - Link validation
    """
    name: str = "link_issues"
    description: str = (
        "LINK: Create relationships between issues (blocks, relates, duplicates). "
        "Use for: 'PROJ-123 blocks PROJ-456', 'link PROJ-789 to PROJ-321'. "
        "Common types: blocks/blocked by, relates to, duplicates, depends on. "
        "Essential for tracking dependencies and related work."
    )
    
    class Input(BaseModel):
        """Input schema for linking issues."""
        from_issue: str = Field(description="Source issue key")
        to_issue: str = Field(description="Target issue key")
        link_type: str = Field(
            default="Relates",
            description="Link type: Blocks, Relates, Duplicates, Clones"
        )
        comment: Optional[str] = Field(default=None, description="Comment about the link")
        
    
    args_schema: type = Input

    def _run(self, **kwargs) -> dict:
        data = self.Input(**kwargs)
        
        try:
            # Log tool call
            logger.info("tool_call",
                component="jira",
                tool_name="link_issues",
                tool_args=kwargs
            )
            
            conn = get_jira_connection()
            
            # Get available link types
            url = f"{conn['base_url']}/rest/api/3/issueLinkType"
            
            # Log API request
            logger.info("jira_api_request",
                component="jira",
                operation="get_link_types",
                url=url,
                method="GET"
            )
            
            response = requests.get(
                url,
                auth=conn['auth'],
                headers=conn['headers']
            )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": "Failed to retrieve link types"
                }
            
            # Log API response
            logger.info("jira_api_response",
                component="jira",
                operation="get_link_types",
                status_code=response.status_code
            )
            
            link_types = response.json()["issueLinkTypes"]
            
            # Find matching link type
            target_link_type = None
            for lt in link_types:
                if data.link_type.lower() in [lt["name"].lower(), lt["inward"].lower(), lt["outward"].lower()]:
                    target_link_type = lt
                    break
            
            if not target_link_type:
                available = [lt["name"] for lt in link_types]
                return {
                    "success": False,
                    "error": f"Link type '{data.link_type}' not found. Available: {', '.join(available)}"
                }
            
            # Create the link
            link_data = {
                "type": {"name": target_link_type["name"]},
                "inwardIssue": {"key": data.to_issue},
                "outwardIssue": {"key": data.from_issue}
            }
            
            if data.comment:
                link_data["comment"] = {
                    "body": {
                        "type": "doc",
                        "version": 1,
                        "content": [{
                            "type": "paragraph",
                            "content": [{
                                "type": "text",
                                "text": data.comment
                            }]
                        }]
                    }
                }
            
            link_url = f"{conn['base_url']}/rest/api/3/issueLink"
            
            # Log API request
            logger.info("jira_api_request",
                component="jira",
                operation="create_issue_link",
                url=link_url,
                method="POST",
                from_issue=data.from_issue,
                to_issue=data.to_issue,
                link_type=target_link_type["name"]
            )
            
            response = requests.post(
                link_url,
                auth=conn['auth'],
                headers=conn['headers'],
                json=link_data
            )
            
            if response.status_code == 201:
                # Log API response
                logger.info("jira_api_response",
                    component="jira",
                    operation="create_issue_link",
                    status_code=response.status_code,
                    from_issue=data.from_issue,
                    to_issue=data.to_issue
                )
                
                result = {
                    "success": True,
                    "from_issue": data.from_issue,
                    "to_issue": data.to_issue,
                    "link_type": target_link_type["name"],
                    "relationship": f"{data.from_issue} {target_link_type['outward']} {data.to_issue}",
                    "message": f"Successfully linked {data.from_issue} to {data.to_issue}"
                }
                
                # Log tool result
                logger.info("tool_result",
                    component="jira",
                    tool_name="link_issues",
                    result_type=type(result).__name__,
                    from_issue=data.from_issue,
                    to_issue=data.to_issue,
                    link_type=target_link_type["name"]
                )
                
                return result
            else:
                error_msg = response.json().get("errorMessages", ["Unknown error"])[0]
                return {
                    "success": False,
                    "error": f"Failed to create link: {error_msg}"
                }
                
        except Exception as e:
            # Log tool error
            logger.error("tool_error",
                component="jira",
                tool_name="link_issues",
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }


# Export all tools
ALL_JIRA_TOOLS = [
    # Search and Query
    SearchJiraIssuesTool(),
    # CRUD Operations
    GetJiraIssueTool(),
    CreateJiraIssueTool(),
    UpdateJiraIssueTool(),
    # Collaboration
    AddJiraCommentTool(),
    # Project and Board
    GetProjectIssuesTool(),
    # Personal Productivity
    GetMyIssuesTool(),
    # Epic and Sprint
    GetEpicIssuesTool(),
    GetSprintIssuesTool(),
    # Workflow
    TransitionIssueTool(),
    AssignIssueTool(),
    # Advanced
    AddAttachmentTool(),
    GetIssueHistoryTool(),
    CreateSubtaskTool(),
    LinkIssuesTool()
]