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
    
    args_schema: type = Input  # pyright: ignore[reportIncompatibleVariableOverride]
    
    def _execute(self, **kwargs) -> Any:
        """Execute the get operation."""
        issue_key = kwargs['issue_key']
        include_comments = kwargs.get('include_comments', True)
        include_attachments = kwargs.get('include_attachments', True)
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
    
    args_schema: type = Input  # pyright: ignore[reportIncompatibleVariableOverride]
    
    def _execute(self, **kwargs) -> Any:
        """Execute the search operation."""
        query = kwargs['query']
        max_results = kwargs.get('max_results', 50)
        start_at = kwargs.get('start_at', 0)
        fields = kwargs.get('fields', None)
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
    
    args_schema: type = Input  # pyright: ignore[reportIncompatibleVariableOverride]
    
    def _execute(self, **kwargs) -> Any:
        """Execute the create operation."""
        project_key = kwargs['project_key']
        issue_type = kwargs['issue_type']
        summary = kwargs['summary']
        description = kwargs.get('description', None)
        parent_key = kwargs.get('parent_key', None)
        assignee = kwargs.get('assignee', None)
        priority = kwargs.get('priority', None)
        labels = kwargs.get('labels', None)
        components = kwargs.get('components', None)
        custom_fields = kwargs.get('custom_fields', None)
        # Build issue data
        issue_data: Dict[str, Any] = {
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
    
    args_schema: type = Input  # pyright: ignore[reportIncompatibleVariableOverride]
    
    def _execute(self, **kwargs) -> Any:
        """Execute the update operation."""
        issue_key = kwargs['issue_key']
        fields = kwargs.get('fields', None)
        transition_to = kwargs.get('transition_to', None)
        assignee = kwargs.get('assignee', None)
        comment = kwargs.get('comment', None)
        results = []
        
        # Handle field updates
        if fields or assignee:
            update_data: Dict[str, Any] = {"fields": {}}
            
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
    
    args_schema: type = Input  # pyright: ignore[reportIncompatibleVariableOverride]
    
    def _execute(self, **kwargs) -> Any:
        """Execute the collaboration operation."""
        issue_key = kwargs['issue_key']
        action = kwargs['action']
        content = kwargs.get('content', None)
        link_to = kwargs.get('link_to', None)
        link_type = kwargs.get('link_type', "relates to")
        visibility = kwargs.get('visibility', None)
        if action == "comment":
            if content is None:
                return {"success": False, "error": "Content is required for comment action"}
            return self._add_comment(issue_key, content, visibility)
        elif action == "link":
            if link_to is None:
                return {"success": False, "error": "link_to is required for link action"}
            return self._link_issues(issue_key, link_to, link_type)
        elif action == "attach":
            return {"success": False, "error": "File attachments require multipart upload - use direct API"}
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
    
    def _add_comment(self, issue_key: str, comment_text: str, visibility: Optional[str] = None) -> Dict[str, Any]:
        """Add comment to issue."""
        comment_data: Dict[str, Any] = {"body": comment_text}
        
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
    
    args_schema: type = Input  # pyright: ignore[reportIncompatibleVariableOverride]
    
    def _execute(self, **kwargs) -> Any:
        """Execute the analytics operation."""
        issue_key = kwargs.get('issue_key', None)
        project_key = kwargs.get('project_key', None)
        metric_type = kwargs.get('metric_type', "history")
        time_period = kwargs.get('time_period', None)
        if metric_type == "history" and issue_key:
            return self._get_issue_history(issue_key)
        elif metric_type == "worklog" and issue_key:
            return self._get_worklog(issue_key)
        elif metric_type == "project_stats" and project_key:
            return self._get_project_stats(project_key, time_period)
        else:
            return {"success": False, "error": "Invalid metric type or missing required parameters"}
    
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
    
    args_schema: type = Input  # pyright: ignore[reportIncompatibleVariableOverride]
    
    def _execute(self, **kwargs) -> Any:
        """Execute the project creation."""
        key = kwargs['key']
        name = kwargs['name']
        project_type_key = kwargs.get('project_type_key', "business")
        description = kwargs.get('description', None)
        lead_account_id = kwargs.get('lead_account_id', None)
        assignee_type = kwargs.get('assignee_type', "PROJECT_LEAD")
        # Validate project key format
        if not key or not key.isupper() or not key.isalpha() or len(key) < 2 or len(key) > 10:
            return {
                "success": False,
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
                field_errors: Dict[str, Any] = {}
                if isinstance(error_details, dict) and "errors" in error_details:
                    field_errors = error_details["errors"]
                
                return {
                    "success": False,
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
                    "success": False,
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
                    "success": False,
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


class JiraGetResource(JiraReadTool):
    """Get any Jira resource by type and identifier.
    
    Universal getter for projects, users, boards, sprints, and other Jira objects.
    Handles the most common non-issue resources in Jira.
    """
    name: str = "jira_get_resource"
    description: str = "Get Jira resources like projects, users, boards, or sprints"
    
    class Input(BaseModel):
        resource_type: str = Field(
            description="Type of resource: 'project', 'user', 'board', 'sprint', 'component', 'version'"
        )
        identifier: str = Field(
            description="Resource identifier (key, ID, username, etc.)"
        )
        expand: Optional[str] = Field(
            None,
            description="Additional data to include (resource-specific)"
        )
    
    args_schema: type = Input  # pyright: ignore[reportIncompatibleVariableOverride]
    
    def _execute(self, **kwargs) -> Any:
        """Execute the resource retrieval based on type."""
        resource_type = kwargs['resource_type'].lower()
        identifier = kwargs['identifier']
        expand = kwargs.get('expand')
        
        if resource_type == 'project':
            return self._get_project(identifier, expand)
        elif resource_type == 'user':
            return self._get_user(identifier)
        elif resource_type == 'board':
            return self._get_board(identifier)
        elif resource_type == 'sprint':
            return self._get_sprint(identifier)
        elif resource_type == 'component':
            return self._get_component(identifier)
        elif resource_type == 'version':
            return self._get_version(identifier)
        else:
            return {
                "success": False,
                "error": f"Unsupported resource type: {resource_type}",
                "supported_types": ["project", "user", "board", "sprint", "component", "version"]
            }
    
    def _get_project(self, key_or_id: str, expand: Optional[str] = None) -> Dict[str, Any]:
        """Get project details."""
        url = f"/project/{key_or_id}"
        if expand:
            url += f"?expand={expand}"
        response = self._make_request("GET", url)
        return response.json()
    
    def _get_user(self, account_id_or_username: str) -> Dict[str, Any]:
        """Get user details."""
        # Try account ID first (Cloud)
        try:
            response = self._make_request("GET", f"/user?accountId={account_id_or_username}")
            return response.json()
        except:
            # Fall back to username (Server/DC)
            response = self._make_request("GET", f"/user?username={account_id_or_username}")
            return response.json()
    
    def _get_board(self, board_id: str) -> Dict[str, Any]:
        """Get board details."""
        # Note: This uses the Agile API endpoint
        response = self._make_request("GET", f"/agile/1.0/board/{board_id}")
        return response.json()
    
    def _get_sprint(self, sprint_id: str) -> Dict[str, Any]:
        """Get sprint details."""
        # Note: This uses the Agile API endpoint
        response = self._make_request("GET", f"/agile/1.0/sprint/{sprint_id}")
        return response.json()
    
    def _get_component(self, component_id: str) -> Dict[str, Any]:
        """Get component details."""
        response = self._make_request("GET", f"/component/{component_id}")
        return response.json()
    
    def _get_version(self, version_id: str) -> Dict[str, Any]:
        """Get version details."""
        response = self._make_request("GET", f"/version/{version_id}")
        return response.json()


class JiraListResources(JiraReadTool):
    """List or search for Jira resources.
    
    Universal listing tool for projects, users, boards, sprints, and other collections.
    """
    name: str = "jira_list_resources"
    description: str = "List Jira resources like all projects, users, boards, or sprints"
    
    class Input(BaseModel):
        resource_type: str = Field(
            description="Type of resource: 'projects', 'users', 'boards', 'sprints', 'components', 'versions'"
        )
        project_key: Optional[str] = Field(
            None,
            description="Project key (required for components, versions, boards)"
        )
        board_id: Optional[str] = Field(
            None,
            description="Board ID (required for listing sprints)"
        )
        query: Optional[str] = Field(
            None,
            description="Search query (for users, projects)"
        )
        max_results: int = Field(50, description="Maximum results to return")
        start_at: int = Field(0, description="Starting index for pagination")
    
    args_schema: type = Input  # pyright: ignore[reportIncompatibleVariableOverride]
    
    def _execute(self, **kwargs) -> Any:
        """Execute the resource listing based on type."""
        resource_type = kwargs['resource_type'].lower()
        
        if resource_type == 'projects':
            return self._list_projects(kwargs.get('query'), kwargs.get('max_results', 50))
        elif resource_type == 'users':
            return self._search_users(kwargs.get('query', ''), kwargs.get('max_results', 50))
        elif resource_type == 'boards':
            return self._list_boards(kwargs.get('project_key'), kwargs.get('max_results', 50), kwargs.get('start_at', 0))
        elif resource_type == 'sprints':
            board_id = kwargs.get('board_id')
            if not board_id:
                return {"success": False, "error": "board_id is required for listing sprints"}
            return self._list_sprints(board_id, kwargs.get('max_results', 50), kwargs.get('start_at', 0))
        elif resource_type == 'components':
            project_key = kwargs.get('project_key')
            if not project_key:
                return {"success": False, "error": "project_key is required for listing components"}
            return self._list_components(project_key)
        elif resource_type == 'versions':
            project_key = kwargs.get('project_key')
            if not project_key:
                return {"success": False, "error": "project_key is required for listing versions"}
            return self._list_versions(project_key)
        else:
            return {
                "success": False,
                "error": f"Unsupported resource type: {resource_type}",
                "supported_types": ["projects", "users", "boards", "sprints", "components", "versions"]
            }
    
    def _list_projects(self, query: Optional[str] = None, max_results: int = 50) -> Dict[str, Any]:
        """List all accessible projects."""
        url = f"/project/search?maxResults={max_results}"
        if query:
            url += f"&query={query}"
        response = self._make_request("GET", url)
        return response.json()
    
    def _search_users(self, query: str, max_results: int = 50) -> Dict[str, Any]:
        """Search for users."""
        response = self._make_request("GET", f"/user/search?query={query}&maxResults={max_results}")
        return response.json()
    
    def _list_boards(self, project_key: Optional[str] = None, max_results: int = 50, start_at: int = 0) -> Dict[str, Any]:
        """List boards, optionally filtered by project."""
        url = f"/agile/1.0/board?maxResults={max_results}&startAt={start_at}"
        if project_key:
            url += f"&projectKeyOrId={project_key}"
        response = self._make_request("GET", url)
        return response.json()
    
    def _list_sprints(self, board_id: str, max_results: int = 50, start_at: int = 0) -> Dict[str, Any]:
        """List sprints for a board."""
        response = self._make_request(
            "GET", 
            f"/agile/1.0/board/{board_id}/sprint?maxResults={max_results}&startAt={start_at}"
        )
        return response.json()
    
    def _list_components(self, project_key: str) -> Dict[str, Any]:
        """List components for a project."""
        response = self._make_request("GET", f"/project/{project_key}/components")
        return response.json()
    
    def _list_versions(self, project_key: str) -> Dict[str, Any]:
        """List versions for a project."""
        response = self._make_request("GET", f"/project/{project_key}/versions")
        return response.json()


class JiraUpdateResource(JiraWriteTool):
    """Update Jira resources like projects, boards, and sprints.
    
    Handles updates for non-issue resources that have different update patterns.
    """
    name: str = "jira_update_resource"
    description: str = "Update Jira resources like projects, boards, or sprints"
    
    class Input(BaseModel):
        resource_type: str = Field(
            description="Type of resource: 'project', 'board', 'sprint'"
        )
        identifier: str = Field(
            description="Resource identifier (key, ID)"
        )
        updates: Dict[str, Any] = Field(
            description="Fields to update (varies by resource type)"
        )
    
    args_schema: type = Input  # pyright: ignore[reportIncompatibleVariableOverride]
    
    def _execute(self, **kwargs) -> Any:
        """Execute the resource update based on type."""
        resource_type = kwargs['resource_type'].lower()
        identifier = kwargs['identifier']
        updates = kwargs['updates']
        
        if resource_type == 'project':
            return self._update_project(identifier, updates)
        elif resource_type == 'board':
            return self._update_board(identifier, updates)
        elif resource_type == 'sprint':
            return self._update_sprint(identifier, updates)
        else:
            return {
                "success": False,
                "error": f"Unsupported resource type: {resource_type}",
                "supported_types": ["project", "board", "sprint"]
            }
    
    def _update_project(self, key_or_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update project details."""
        response = self._make_request("PUT", f"/project/{key_or_id}", json=updates)
        return {"success": True, "project": key_or_id, "updates": updates}
    
    def _update_board(self, board_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update board configuration."""
        # Board updates are limited - mainly name and type
        allowed_updates = {k: v for k, v in updates.items() if k in ['name', 'type']}
        response = self._make_request("PUT", f"/agile/1.0/board/{board_id}", json=allowed_updates)
        return {"success": True, "board": board_id, "updates": allowed_updates}
    
    def _update_sprint(self, sprint_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update sprint details."""
        # Sprint updates: name, startDate, endDate, goal, state
        response = self._make_request("PUT", f"/agile/1.0/sprint/{sprint_id}", json=updates)
        return {"success": True, "sprint": sprint_id, "updates": updates}


class JiraSprintOperations(JiraWriteTool):
    """Manage sprint operations in Jira.
    
    Create sprints, move issues between sprints, start/complete sprints.
    """
    name: str = "jira_sprint_operations"
    description: str = "Create sprints and manage sprint operations"
    
    class Input(BaseModel):
        operation: str = Field(
            description="Operation: 'create', 'start', 'complete', 'move_issues'"
        )
        board_id: Optional[str] = Field(
            None,
            description="Board ID (required for create)"
        )
        sprint_id: Optional[str] = Field(
            None,
            description="Sprint ID (required for start, complete, move_issues)"
        )
        name: Optional[str] = Field(
            None,
            description="Sprint name (required for create)"
        )
        start_date: Optional[str] = Field(
            None,
            description="Sprint start date ISO format (for create/start)"
        )
        end_date: Optional[str] = Field(
            None,
            description="Sprint end date ISO format (for create/start)"
        )
        goal: Optional[str] = Field(
            None,
            description="Sprint goal"
        )
        issue_keys: Optional[List[str]] = Field(
            None,
            description="Issue keys to move (for move_issues)"
        )
    
    args_schema: type = Input  # pyright: ignore[reportIncompatibleVariableOverride]
    
    def _execute(self, **kwargs) -> Any:
        """Execute the sprint operation."""
        operation = kwargs['operation'].lower()
        
        if operation == 'create':
            return self._create_sprint(kwargs)
        elif operation == 'start':
            return self._start_sprint(kwargs['sprint_id'])
        elif operation == 'complete':
            return self._complete_sprint(kwargs['sprint_id'])
        elif operation == 'move_issues':
            return self._move_issues_to_sprint(kwargs['sprint_id'], kwargs.get('issue_keys', []))
        else:
            return {
                "success": False,
                "error": f"Unsupported operation: {operation}",
                "supported_operations": ["create", "start", "complete", "move_issues"]
            }
    
    def _create_sprint(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new sprint."""
        sprint_data = {
            "name": params['name'],
            "originBoardId": params['board_id']
        }
        if params.get('start_date'):
            sprint_data['startDate'] = params['start_date']
        if params.get('end_date'):
            sprint_data['endDate'] = params['end_date']
        if params.get('goal'):
            sprint_data['goal'] = params['goal']
        
        response = self._make_request("POST", "/agile/1.0/sprint", json=sprint_data)
        return response.json()
    
    def _start_sprint(self, sprint_id: str) -> Dict[str, Any]:
        """Start a sprint."""
        response = self._make_request(
            "PUT", 
            f"/agile/1.0/sprint/{sprint_id}",
            json={"state": "active"}
        )
        return {"success": True, "sprint": sprint_id, "state": "active"}
    
    def _complete_sprint(self, sprint_id: str) -> Dict[str, Any]:
        """Complete a sprint."""
        response = self._make_request(
            "PUT",
            f"/agile/1.0/sprint/{sprint_id}",
            json={"state": "closed"}
        )
        return {"success": True, "sprint": sprint_id, "state": "closed"}
    
    def _move_issues_to_sprint(self, sprint_id: str, issue_keys: List[str]) -> Dict[str, Any]:
        """Move issues to a sprint."""
        response = self._make_request(
            "POST",
            f"/agile/1.0/sprint/{sprint_id}/issue",
            json={"issues": issue_keys}
        )
        return {"success": True, "sprint": sprint_id, "moved_issues": issue_keys}


# Export the new unified tools
UNIFIED_JIRA_TOOLS = [
    JiraGet(),
    JiraSearch(),
    JiraCreate(),
    JiraUpdate(),
    JiraCollaboration(),
    JiraAnalytics(),
    JiraProjectCreate(),
    JiraGetResource(),
    JiraListResources(),
    JiraUpdateResource(),
    JiraSprintOperations()
]