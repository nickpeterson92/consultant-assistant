"""Unified Jira tools for issue management and JQL queries."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import requests

from .base import (
    JiraReadTool,
    JiraWriteTool,
    JiraCollaborationTool,
    JiraAnalyticsTool
)


class JiraGet(JiraReadTool):
    """Get any Jira issue by key.
    
    Simple, direct issue retrieval with full context including
    comments, attachments, and relationships.
    """
    name: str = "jira_get"
    description: str = "Get a Jira issue by key"
    
    class Input(BaseModel):
        issue_key: str = Field(description="Jira issue key (e.g., PROJ-123)")
        include_comments: bool = Field(True, description="Include comments in response")
        include_attachments: bool = Field(True, description="Include attachments in response")
    
    args_schema: type = Input
    
    def _execute(self, issue_key: str, include_comments: bool = True, 
                 include_attachments: bool = True) -> Any:
        """Execute the get operation."""
        # Build expand parameter for additional data
        expand_parts = ["renderedFields"]
        if include_comments:
            expand_parts.append("comments")
        if include_attachments:
            expand_parts.append("attachments")
        
        expand = ",".join(expand_parts)
        
        response = self._make_request("GET", f"/issue/{issue_key}?expand={expand}")
        return response.json()


class JiraSearch(JiraReadTool):
    """Search Jira issues with JQL and natural language support.
    
    Handles everything from simple text searches to complex JQL queries.
    The LLM can pass natural language or structured JQL.
    """
    name: str = "jira_search"
    description: str = "Search Jira issues with flexible criteria"
    
    class Input(BaseModel):
        query: str = Field(description="JQL query or natural language search")
        max_results: int = Field(50, description="Maximum issues to return")
        start_at: int = Field(0, description="Starting index for pagination")
        fields: Optional[List[str]] = Field(None, description="Specific fields to return")
    
    args_schema: type = Input
    
    def _execute(self, query: str, max_results: int = 50, start_at: int = 0,
                 fields: Optional[List[str]] = None) -> Any:
        """Execute the search operation."""
        # Build JQL query
        jql_query = self._build_jql_query(query)
        self._log_jql(jql_query)
        
        # Default fields if not specified
        if not fields:
            fields = [
                "key", "summary", "status", "assignee", "reporter", 
                "created", "updated", "priority", "issuetype", "project"
            ]
        
        search_data = {
            "jql": jql_query,
            "startAt": start_at,
            "maxResults": max_results,
            "fields": fields
        }
        
        response = self._make_request("POST", "/search", json=search_data)
        return response.json()
    
    def _build_jql_query(self, query: str) -> str:
        """Build JQL query from natural language or validate existing JQL."""
        # Check if it looks like JQL (contains operators like =, !=, IN, etc.)
        jql_indicators = ['=', '!=', ' IN ', ' NOT IN ', ' ~ ', ' !~ ', 'ORDER BY', 'AND', 'OR']
        
        if any(indicator in query for indicator in jql_indicators):
            # Looks like JQL - return as-is but escaped
            return query
        else:
            # Natural language - convert to basic text search
            escaped_query = self._escape_jql(query)
            return f'text ~ "{escaped_query}"'


class JiraCreate(JiraWriteTool):
    """Create Jira issues and subtasks.
    
    Simple creation tool that works with any issue type.
    The LLM provides the issue data and this tool handles the creation.
    """
    name: str = "jira_create"
    description: str = "Create a new Jira issue or subtask"
    
    class Input(BaseModel):
        project_key: str = Field(description="Project key (e.g., PROJ)")
        issue_type: str = Field(description="Issue type (Bug, Story, Task, etc.)")
        summary: str = Field(description="Issue summary/title")
        description: Optional[str] = Field(None, description="Issue description")
        parent_key: Optional[str] = Field(None, description="Parent issue key for subtasks")
        assignee: Optional[str] = Field(None, description="Assignee username")
        priority: Optional[str] = Field(None, description="Priority name")
        labels: Optional[List[str]] = Field(None, description="Issue labels")
        components: Optional[List[str]] = Field(None, description="Component names")
        custom_fields: Optional[Dict[str, Any]] = Field(None, description="Custom field values")
    
    args_schema: type = Input
    
    def _execute(self, project_key: str, issue_type: str, summary: str,
                 description: Optional[str] = None, parent_key: Optional[str] = None,
                 assignee: Optional[str] = None, priority: Optional[str] = None,
                 labels: Optional[List[str]] = None, components: Optional[List[str]] = None,
                 custom_fields: Optional[Dict[str, Any]] = None) -> Any:
        """Execute the create operation."""
        # Build issue data
        issue_data = {
            "fields": {
                "project": {"key": project_key},
                "issuetype": {"name": issue_type},
                "summary": summary
            }
        }
        
        # Add optional fields
        if description:
            issue_data["fields"]["description"] = description
        
        if parent_key:
            issue_data["fields"]["parent"] = {"key": parent_key}
        
        if assignee:
            issue_data["fields"]["assignee"] = {"name": assignee}
        
        if priority:
            issue_data["fields"]["priority"] = {"name": priority}
        
        if labels:
            issue_data["fields"]["labels"] = labels
        
        if components:
            issue_data["fields"]["components"] = [{"name": comp} for comp in components]
        
        if custom_fields:
            issue_data["fields"].update(custom_fields)
        
        response = self._make_request("POST", "/issue", json=issue_data)
        result = response.json()
        
        # Return the created issue with full details
        if result.get("key"):
            return self._get_created_issue(result["key"])
        else:
            return result
    
    def _get_created_issue(self, issue_key: str) -> Dict[str, Any]:
        """Get full details of created issue."""
        response = self._make_request("GET", f"/issue/{issue_key}")
        return response.json()


class JiraUpdate(JiraWriteTool):
    """Update Jira issues including field updates, transitions, and assignments.
    
    Comprehensive update tool that handles all types of issue modifications.
    """
    name: str = "jira_update"
    description: str = "Update Jira issue fields, status, or assignment"
    
    class Input(BaseModel):
        issue_key: str = Field(description="Jira issue key to update")
        fields: Optional[Dict[str, Any]] = Field(None, description="Fields to update")
        transition_to: Optional[str] = Field(None, description="Status to transition to")
        assignee: Optional[str] = Field(None, description="New assignee username")
        comment: Optional[str] = Field(None, description="Comment to add with update")
    
    args_schema: type = Input
    
    def _execute(self, issue_key: str, fields: Optional[Dict[str, Any]] = None,
                 transition_to: Optional[str] = None, assignee: Optional[str] = None,
                 comment: Optional[str] = None) -> Any:
        """Execute the update operation."""
        results = []
        
        # Handle field updates
        if fields or assignee:
            update_data = {"fields": {}}
            
            if fields:
                update_data["fields"].update(fields)
            
            if assignee:
                update_data["fields"]["assignee"] = {"name": assignee}
            
            response = self._make_request("PUT", f"/issue/{issue_key}", json=update_data)
            results.append({"operation": "field_update", "status": "success"})
        
        # Handle status transition
        if transition_to:
            transition_result = self._transition_issue(issue_key, transition_to, comment)
            results.append(transition_result)
        elif comment:
            # Add comment without transition
            self._add_comment(issue_key, comment)
            results.append({"operation": "comment_added", "status": "success"})
        
        # Return updated issue
        response = self._make_request("GET", f"/issue/{issue_key}")
        updated_issue = response.json()
        updated_issue["update_results"] = results
        
        return updated_issue
    
    def _transition_issue(self, issue_key: str, status_name: str, comment: Optional[str] = None) -> Dict[str, Any]:
        """Transition issue to new status."""
        # Get available transitions
        response = self._make_request("GET", f"/issue/{issue_key}/transitions")
        transitions = response.json()["transitions"]
        
        # Find matching transition
        target_transition = None
        for transition in transitions:
            if transition["to"]["name"].lower() == status_name.lower():
                target_transition = transition
                break
        
        if not target_transition:
            return {
                "operation": "transition",
                "status": "error",
                "error": f"No transition available to status '{status_name}'"
            }
        
        # Build transition data
        transition_data = {
            "transition": {"id": target_transition["id"]}
        }
        
        if comment:
            transition_data["update"] = {
                "comment": [{"add": {"body": comment}}]
            }
        
        self._make_request("POST", f"/issue/{issue_key}/transitions", json=transition_data)
        
        return {
            "operation": "transition",
            "status": "success",
            "from": target_transition["name"],
            "to": status_name
        }
    
    def _add_comment(self, issue_key: str, comment: str):
        """Add comment to issue."""
        comment_data = {"body": comment}
        self._make_request("POST", f"/issue/{issue_key}/comment", json=comment_data)


class JiraCollaboration(JiraCollaborationTool):
    """Handle Jira collaboration features: comments, attachments, and issue links.
    
    Comprehensive collaboration tool for team interactions.
    """
    name: str = "jira_collaboration"
    description: str = "Add comments, attachments, or link issues"
    
    class Input(BaseModel):
        issue_key: str = Field(description="Jira issue key")
        action: str = Field(description="Action: 'comment', 'attach', or 'link'")
        content: Optional[str] = Field(None, description="Comment text or attachment path")
        link_to: Optional[str] = Field(None, description="Issue key to link to")
        link_type: Optional[str] = Field("relates to", description="Link type")
        visibility: Optional[str] = Field(None, description="Comment visibility group")
    
    args_schema: type = Input
    
    def _execute(self, issue_key: str, action: str, content: Optional[str] = None,
                 link_to: Optional[str] = None, link_type: str = "relates to",
                 visibility: Optional[str] = None) -> Any:
        """Execute the collaboration operation."""
        if action == "comment":
            return self._add_comment(issue_key, content, visibility)
        elif action == "link":
            return self._link_issues(issue_key, link_to, link_type)
        elif action == "attach":
            return {"error": "File attachments require multipart upload - use direct API"}
        else:
            return {"error": f"Unknown action: {action}"}
    
    def _add_comment(self, issue_key: str, comment_text: str, visibility: Optional[str] = None) -> Dict[str, Any]:
        """Add comment to issue."""
        comment_data = {"body": comment_text}
        
        if visibility:
            comment_data["visibility"] = {
                "type": "group",
                "value": visibility
            }
        
        response = self._make_request("POST", f"/issue/{issue_key}/comment", json=comment_data)
        return response.json()
    
    def _link_issues(self, from_key: str, to_key: str, link_type: str) -> Dict[str, Any]:
        """Create link between issues."""
        link_data = {
            "type": {"name": link_type},
            "inwardIssue": {"key": from_key},
            "outwardIssue": {"key": to_key}
        }
        
        response = self._make_request("POST", "/issueLink", json=link_data)
        return {"status": "success", "link_created": f"{from_key} {link_type} {to_key}"}


class JiraAnalytics(JiraAnalyticsTool):
    """Get Jira analytics and metrics.
    
    Provides issue history, worklog data, and project metrics.
    """
    name: str = "jira_analytics"
    description: str = "Get issue history, metrics, and analytics"
    
    class Input(BaseModel):
        issue_key: Optional[str] = Field(None, description="Issue key for history")
        project_key: Optional[str] = Field(None, description="Project key for metrics")
        metric_type: str = Field("history", description="Type: 'history', 'worklog', 'project_stats'")
        time_period: Optional[str] = Field(None, description="Time period filter")
    
    args_schema: type = Input
    
    def _execute(self, issue_key: Optional[str] = None, project_key: Optional[str] = None,
                 metric_type: str = "history", time_period: Optional[str] = None) -> Any:
        """Execute the analytics operation."""
        if metric_type == "history" and issue_key:
            return self._get_issue_history(issue_key)
        elif metric_type == "worklog" and issue_key:
            return self._get_worklog(issue_key)
        elif metric_type == "project_stats" and project_key:
            return self._get_project_stats(project_key, time_period)
        else:
            return {"error": "Invalid metric type or missing required parameters"}
    
    def _get_issue_history(self, issue_key: str) -> Dict[str, Any]:
        """Get issue change history."""
        response = self._make_request("GET", f"/issue/{issue_key}?expand=changelog")
        issue_data = response.json()
        
        return {
            "issue_key": issue_key,
            "change_history": issue_data.get("changelog", {}),
            "created": issue_data["fields"]["created"],
            "updated": issue_data["fields"]["updated"]
        }
    
    def _get_worklog(self, issue_key: str) -> Dict[str, Any]:
        """Get issue worklog entries."""
        response = self._make_request("GET", f"/issue/{issue_key}/worklog")
        return response.json()
    
    def _get_project_stats(self, project_key: str, time_period: Optional[str] = None) -> Dict[str, Any]:
        """Get project statistics."""
        # Build JQL for project stats
        jql = f"project = {project_key}"
        if time_period:
            jql += f" AND created >= {time_period}"
        
        self._log_jql(jql, "project_stats")
        
        # Get issue counts by status
        search_data = {
            "jql": jql,
            "maxResults": 0,  # We only want counts
            "fields": ["status"]
        }
        
        response = self._make_request("POST", "/search", json=search_data)
        search_result = response.json()
        
        return {
            "project_key": project_key,
            "total_issues": search_result["total"],
            "time_period": time_period,
            "query_used": jql
        }


class JiraProjectCreate(JiraWriteTool):
    """Create a new Jira project.
    
    Creates a project in Jira Cloud. Requires Administer Jira global permission.
    """
    name: str = "jira_project_create"
    description: str = "Create a new Jira project (requires admin permissions)"
    
    class Input(BaseModel):
        key: str = Field(description="Project key (2-10 uppercase letters, must be unique)")
        name: str = Field(description="Project name")
        project_type_key: str = Field("business", description="Project type: 'business' (Core), 'software' (Software), or 'service_desk' (Service Management)")
        description: Optional[str] = Field(None, description="Project description")
        lead_account_id: Optional[str] = Field(None, description="Account ID of project lead (if not provided, will use current user)")
        assignee_type: str = Field("PROJECT_LEAD", description="Default assignee: 'PROJECT_LEAD' or 'UNASSIGNED'")
    
    args_schema: type = Input
    
    def _execute(self, key: str, name: str, project_type_key: str = "business",
                 description: Optional[str] = None, lead_account_id: Optional[str] = None,
                 assignee_type: str = "PROJECT_LEAD") -> Any:
        """Execute the project creation."""
        # Validate project key format
        if not key or not key.isupper() or not key.isalpha() or len(key) < 2 or len(key) > 10:
            return {
                "error": "Invalid project key",
                "error_code": "INVALID_KEY",
                "details": "Project key must be 2-10 uppercase letters",
                "guidance": {
                    "reflection": "The project key format is invalid.",
                    "consider": "Project keys must be 2-10 uppercase letters (e.g., 'PROJ', 'ABC').",
                    "approach": "Use the first 3-5 letters of the project name in uppercase."
                }
            }
        
        # Build project data
        project_data = {
            "key": key,
            "name": name,
            "projectTypeKey": project_type_key,
            "assigneeType": assignee_type
        }
        
        if description:
            project_data["description"] = description
            
        if lead_account_id:
            project_data["leadAccountId"] = lead_account_id
        else:
            # Try to get current user as lead
            try:
                myself_response = self._make_request("GET", "/myself")
                current_user = myself_response.json()
                project_data["leadAccountId"] = current_user.get("accountId")
            except:
                # If we can't get current user, let Jira use defaults
                pass
        
        # Use v3 API for project creation
        url = f"{self.jira['base_url']}/rest/api/3/project"
        
        response = requests.post(
            url,
            auth=self.jira['auth'],
            headers=self.jira['headers'],
            json=project_data
        )
        
        if response.status_code == 201:
            # Successfully created
            return response.json()
        else:
            # Extract detailed error information
            error_details = response.text
            try:
                error_json = response.json()
                error_details = error_json
            except:
                pass
                
            if response.status_code == 400:
                # Extract specific field errors if available
                field_errors = {}
                if isinstance(error_details, dict) and "errors" in error_details:
                    field_errors = error_details["errors"]
                
                return {
                    "error": "Invalid project data",
                    "error_code": "BAD_REQUEST",
                    "details": error_details,
                    "field_errors": field_errors,
                    "guidance": {
                        "reflection": "The project data is invalid or incomplete.",
                        "consider": "Check if the project key already exists, or if the project type is available in your Jira instance.",
                        "approach": "Verify project key uniqueness and ensure you have the required Jira products installed for the project type."
                    }
                }
            elif response.status_code == 401:
                return {
                    "error": "Authentication failed",
                    "error_code": "UNAUTHORIZED",
                    "details": error_details,
                    "guidance": {
                        "reflection": "The credentials are invalid or missing.",
                        "consider": "Are the JIRA_USER and JIRA_API_TOKEN environment variables correctly set?",
                        "approach": "Verify your Jira credentials and API token permissions."
                    }
                }
            elif response.status_code == 403:
                return {
                    "error": "Permission denied",
                    "error_code": "FORBIDDEN", 
                    "details": error_details,
                    "guidance": {
                        "reflection": "You don't have permission to create projects.",
                        "consider": "Project creation requires 'Administer Jira' global permission.",
                        "approach": "Contact your Jira administrator to grant the necessary permissions."
                    }
                }
            else:
                # Let the base error handler deal with other cases
                response.raise_for_status()


# Export the new unified tools
UNIFIED_JIRA_TOOLS = [
    JiraGet(),
    JiraSearch(),
    JiraCreate(),
    JiraUpdate(),
    JiraCollaboration(),
    JiraAnalytics(),
    JiraProjectCreate()
]