"""Unified Jira tools for issue management and JQL queries."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from .base import (
    JiraReadTool,
    JiraWriteTool,
    JiraCollaborationTool,
    JiraAnalyticsTool
)
from src.utils.logging.framework import log_execution


class JiraGet(JiraReadTool):
    """Get any Jira issue by key.
    
    Simple, direct issue retrieval with full context including
    comments, attachments, and relationships.
    """
    name: str = "jira_get"
    description: str = "Get a Jira issue by key"
    produces_user_data: bool = True  # Issue details may need user review
    
    class Input(BaseModel):
        issue_key: str = Field(description="Jira issue key (e.g., PROJ-123)")
        include_comments: bool = Field(True, description="Include comments in response")
        include_attachments: bool = Field(True, description="Include attachments in response")
    
    args_schema: type = Input
    
    @log_execution("jira", "get_issue", include_args=True, include_result=False)
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
    produces_user_data: bool = True  # Search results often need user selection
    
    class Input(BaseModel):
        query: str = Field(description="JQL query or natural language search")
        max_results: int = Field(50, description="Maximum issues to return")
        start_at: int = Field(0, description="Starting index for pagination")
        fields: Optional[List[str]] = Field(None, description="Specific fields to return")
    
    args_schema: type = Input
    
    @log_execution("jira", "search_issues", include_args=True, include_result=False)
    def _execute(self, query: str, max_results: int = 50, start_at: int = 0,
                 fields: Optional[List[str]] = None) -> Any:
        """Execute the search operation."""
        # Build JQL query
        jql_query = self._build_jql_query(query)
        self._log_jql(jql_query)
        
        # Default fields if not specified
        default_fields = [
            "key", "summary", "status", "assignee", "reporter", 
            "created", "updated", "priority", "issuetype", "project",
            "parent", "subtasks", "issuelinks"  # Add relationship fields
        ]
        
        # Merge requested fields with defaults
        if fields:
            # Start with requested fields to respect model's ordering preference
            merged_fields = list(fields)
            # Add any default fields not already included
            for field in default_fields:
                if field not in merged_fields:
                    merged_fields.append(field)
            fields = merged_fields
        else:
            fields = default_fields
        
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
    NOTE: Assignee requires account ID - use jira_list_resources with resource_type='users' to find valid account IDs.
    """
    produces_user_data: bool = False  # Create operations don't require user selection
    name: str = "jira_create"
    description: str = "Create a new Jira issue or subtask"
    
    class Input(BaseModel):
        project_key: str = Field(description="Project key (e.g., PROJ)")
        issue_type: str = Field(description="Issue type (Bug, Story, Task, etc.)")
        summary: str = Field(description="Issue summary/title")
        description: Optional[str] = Field(None, description="Issue description")
        parent_key: Optional[str] = Field(None, description="Parent issue key for subtasks")
        assignee_account_id: Optional[str] = Field(None, description="Assignee account ID (not username - use jira_list_resources to find)")
        priority: Optional[str] = Field(None, description="Priority name")
        labels: Optional[List[str]] = Field(None, description="Issue labels")
        components: Optional[List[str]] = Field(None, description="Component names")
        custom_fields: Optional[Dict[str, Any]] = Field(None, description="Custom field values")
    
    args_schema: type = Input
    
    @log_execution("jira", "create_issue", include_args=True, include_result=False)
    def _execute(self, project_key: str, issue_type: str, summary: str,
                 description: Optional[str] = None, parent_key: Optional[str] = None,
                 assignee_account_id: Optional[str] = None, priority: Optional[str] = None,
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
        
        if assignee_account_id:
            # Use accountId for Jira Cloud
            issue_data["fields"]["assignee"] = {"accountId": assignee_account_id}
        
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
    NOTE: Assignee requires account ID - use jira_list_resources with resource_type='users' to find valid account IDs.
    """
    name: str = "jira_update"
    produces_user_data: bool = False  # Update operations don't require user selection
    description: str = "Update Jira issue fields, status, or assignment"
    
    class Input(BaseModel):
        issue_key: str = Field(description="Jira issue key to update")
        fields: Optional[Dict[str, Any]] = Field(None, description="Fields to update")
        transition_to: Optional[str] = Field(None, description="Status to transition to")
        assignee_account_id: Optional[str] = Field(None, description="New assignee account ID (not username - use jira_list_resources to find)")
        comment: Optional[str] = Field(None, description="Comment to add with update")
    
    args_schema: type = Input
    
    @log_execution("jira", "update_issue", include_args=True, include_result=False)
    def _execute(self, issue_key: str, fields: Optional[Dict[str, Any]] = None,
                 transition_to: Optional[str] = None, assignee_account_id: Optional[str] = None,
                 comment: Optional[str] = None) -> Any:
        """Execute the update operation."""
        results = []
        
        # Handle field updates
        if fields or assignee_account_id:
            update_data = {"fields": {}}
            
            if fields:
                # Process fields to ensure proper format for assignee if present
                processed_fields = {}
                for key, value in fields.items():
                    if key == "assignee" and isinstance(value, str):
                        # Convert string assignee to proper format
                        processed_fields["assignee"] = {"accountId": value}
                    else:
                        processed_fields[key] = value
                update_data["fields"].update(processed_fields)
            
            if assignee_account_id:
                # Use accountId for Jira Cloud
                update_data["fields"]["assignee"] = {"accountId": assignee_account_id}
            
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
    produces_user_data: bool = False  # Collaboration actions don't require user selection
    description: str = "Add comments, attachments, or link issues"
    
    class Input(BaseModel):
        issue_key: str = Field(description="Jira issue key")
        action: str = Field(description="Action: 'comment', 'attach', or 'link'")
        content: Optional[str] = Field(None, description="Comment text or attachment path")
        link_to: Optional[str] = Field(None, description="Issue key to link to")
        link_type: Optional[str] = Field("relates to", description="Link type")
        visibility: Optional[str] = Field(None, description="Comment visibility group")
    
    args_schema: type = Input
    
    @log_execution("jira", "collaboration", include_args=True, include_result=False)
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
        
        self._make_request("POST", "/issueLink", json=link_data)
        return {"status": "success", "link_created": f"{from_key} {link_type} {to_key}"}


class JiraProjectCreate(JiraWriteTool):
    """Create a new Jira project.
    
    Creates a project in Jira Cloud. Requires Administer Jira global permission.
    IMPORTANT: Project lead is required - use jira_list_resources with resource_type='users' to find valid user account IDs.
    """
    name: str = "jira_project_create"
    description: str = "Create a new Jira project (requires project lead - search users first)"
    produces_user_data: bool = False
    
    class Input(BaseModel):
        key: str = Field(description="Project key (2-10 uppercase letters)")
        name: str = Field(description="Project name")
        lead_account_id: str = Field(description="Project lead account ID (required - use jira_list_resources to find users)")
        project_type_key: str = Field("software", description="Project type: software, service_desk, business")
        template_key: Optional[str] = Field(None, description="Template key")
        description: Optional[str] = Field(None, description="Project description")
        
    args_schema: type = Input
    
    @log_execution("jira", "project_create", include_args=True, include_result=False)
    def _execute(self, key: str, name: str, lead_account_id: str, project_type_key: str = "software", 
                 template_key: Optional[str] = None, description: Optional[str] = None) -> Any:
        """Execute project creation."""
        # Validate required fields
        if not lead_account_id:
            return {
                "success": False,
                "error": "Project lead is required",
                "guidance": "Use jira_list_resources with resource_type='users' to find valid user account IDs"
            }
        
        project_data = {
            "key": key.upper(),
            "name": name,
            "projectTypeKey": project_type_key,
            "leadAccountId": lead_account_id  # Required field
        }
        
        if template_key:
            project_data["projectTemplateKey"] = template_key
        if description:
            project_data["description"] = description
            
        response = self._make_request("POST", "/project", json=project_data)
        return response.json()


class JiraGetResource(JiraReadTool):
    """Get any Jira resource by type and identifier.
    
    Universal getter for projects, users, boards, sprints, and other Jira objects.
    Handles the most common non-issue resources in Jira.
    """
    name: str = "jira_get_resource"
    description: str = "Get any Jira resource like project, user, board, or sprint by ID"
    produces_user_data: bool = True
    
    class Input(BaseModel):
        resource_type: str = Field(description="Type: 'project', 'user', 'board', 'sprint', 'component', 'version'")
        resource_id: str = Field(description="ID or key of the resource")
        board_id: Optional[str] = Field(None, description="Board ID (required for sprint)")
        
    args_schema: type = Input
    
    @log_execution("jira", "get_resource", include_args=True, include_result=False)
    def _execute(self, resource_type: str, resource_id: str, board_id: Optional[str] = None) -> Any:
        """Execute resource retrieval based on type."""
        resource_type = resource_type.lower()
        
        if resource_type == 'project':
            response = self._make_request("GET", f"/project/{resource_id}")
            return response.json()
        elif resource_type == 'user':
            response = self._make_request("GET", f"/user?accountId={resource_id}")
            return response.json()
        elif resource_type == 'board':
            response = self._make_request("GET", f"/agile/1.0/board/{resource_id}")
            return response.json()
        elif resource_type == 'sprint':
            response = self._make_request("GET", f"/agile/1.0/sprint/{resource_id}")
            return response.json()
        elif resource_type == 'component':
            response = self._make_request("GET", f"/component/{resource_id}")
            return response.json()
        elif resource_type == 'version':
            response = self._make_request("GET", f"/version/{resource_id}")
            return response.json()
        else:
            return {
                "success": False,
                "error": f"Unsupported resource type: {resource_type}",
                "supported_types": ["project", "user", "board", "sprint", "component", "version"]
            }


class JiraListResources(JiraReadTool):
    """List or search for Jira resources.
    
    Universal listing tool for projects, users, boards, sprints, and other collections.
    """
    name: str = "jira_list_resources"
    description: str = "List Jira resources like all projects, users, boards, or sprints"
    produces_user_data: bool = True
    
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
    
    args_schema: type = Input
    
    @log_execution("jira", "list_resources", include_args=True, include_result=False)
    def _execute(self, resource_type: str, project_key: Optional[str] = None, board_id: Optional[str] = None,
                 query: Optional[str] = None, max_results: int = 50, start_at: int = 0) -> Any:
        """Execute the resource listing based on type."""
        resource_type = resource_type.lower()
        
        if resource_type == 'projects':
            return self._list_projects(query, max_results)
        elif resource_type == 'users':
            return self._search_users(query or '', max_results)
        elif resource_type == 'boards':
            return self._list_boards(project_key, max_results, start_at)
        elif resource_type == 'sprints':
            if not board_id:
                return {"success": False, "error": "board_id is required for listing sprints"}
            return self._list_sprints(board_id, max_results, start_at)
        elif resource_type == 'components':
            if not project_key:
                return {"success": False, "error": "project_key is required for listing components"}
            return self._list_components(project_key)
        elif resource_type == 'versions':
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
        users = response.json()
        
        # Format the response to make it more helpful
        if isinstance(users, list):
            formatted_users = []
            for user in users:
                formatted_user = {
                    "accountId": user.get("accountId"),
                    "displayName": user.get("displayName"),
                    "emailAddress": user.get("emailAddress", "Not available"),
                    "active": user.get("active", True)
                }
                # Only include active users
                if formatted_user["active"]:
                    formatted_users.append(formatted_user)
            
            return {
                "users": formatted_users,
                "total": len(formatted_users),
                "query": query,
                "note": "Use the accountId field when assigning issues or setting project lead"
            }
        
        return users
    
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
    description: str = "Update Jira resources like projects or boards"
    produces_user_data: bool = False
    
    class Input(BaseModel):
        resource_type: str = Field(description="Type: 'project', 'board', 'sprint', 'component', 'version'")
        resource_id: str = Field(description="ID or key of resource to update")
        updates: Dict[str, Any] = Field(description="Fields to update")
        
    args_schema: type = Input
    
    @log_execution("jira", "update_resource", include_args=True, include_result=False)
    def _execute(self, resource_type: str, resource_id: str, updates: Dict[str, Any]) -> Any:
        """Execute resource update based on type."""
        resource_type = resource_type.lower()
        
        if resource_type == 'project':
            response = self._make_request("PUT", f"/project/{resource_id}", json=updates)
            # Return updated project
            updated_response = self._make_request("GET", f"/project/{resource_id}")
            return updated_response.json()
        elif resource_type == 'board':
            response = self._make_request("PUT", f"/agile/1.0/board/{resource_id}", json=updates)
            return {"success": True, "updated_board": resource_id}
        elif resource_type == 'sprint':
            response = self._make_request("PUT", f"/agile/1.0/sprint/{resource_id}", json=updates)
            return {"success": True, "updated_sprint": resource_id}
        elif resource_type == 'component':
            response = self._make_request("PUT", f"/component/{resource_id}", json=updates)
            return response.json()
        elif resource_type == 'version':
            response = self._make_request("PUT", f"/version/{resource_id}", json=updates)
            return response.json()
        else:
            return {
                "success": False,
                "error": f"Unsupported resource type: {resource_type}",
                "supported_types": ["project", "board", "sprint", "component", "version"]
            }


class JiraSprintOperations(JiraWriteTool):
    """Manage sprint operations in Jira.
    
    Create sprints, move issues between sprints, start/complete sprints.
    """
    name: str = "jira_sprint_operations"
    description: str = "Manage sprints: create, start, complete, move issues"
    produces_user_data: bool = False
    
    class Input(BaseModel):
        operation: str = Field(description="Operation: 'create', 'start', 'complete', 'move_issues'")
        board_id: Optional[str] = Field(None, description="Board ID (required for create)")
        sprint_id: Optional[str] = Field(None, description="Sprint ID (required for start/complete/move_issues)")
        sprint_name: Optional[str] = Field(None, description="Sprint name (for create)")
        issue_keys: Optional[List[str]] = Field(None, description="Issue keys to move (for move_issues)")
        
    args_schema: type = Input
    
    @log_execution("jira", "sprint_operations", include_args=True, include_result=False)
    def _execute(self, operation: str, board_id: Optional[str] = None, sprint_id: Optional[str] = None,
                 sprint_name: Optional[str] = None, issue_keys: Optional[List[str]] = None) -> Any:
        """Execute sprint operation."""
        operation = operation.lower()
        
        if operation == 'create':
            if not board_id or not sprint_name:
                return {"success": False, "error": "board_id and sprint_name required for create"}
            return self._create_sprint(board_id, sprint_name)
        elif operation == 'start':
            if not sprint_id:
                return {"success": False, "error": "sprint_id required for start"}
            return self._start_sprint(sprint_id)
        elif operation == 'complete':
            if not sprint_id:
                return {"success": False, "error": "sprint_id required for complete"}
            return self._complete_sprint(sprint_id)
        elif operation == 'move_issues':
            if not sprint_id or not issue_keys:
                return {"success": False, "error": "sprint_id and issue_keys required for move_issues"}
            return self._move_issues_to_sprint(sprint_id, issue_keys)
        else:
            return {
                "success": False,
                "error": f"Unsupported operation: {operation}",
                "supported_operations": ["create", "start", "complete", "move_issues"]
            }
    
    def _create_sprint(self, board_id: str, name: str) -> Dict[str, Any]:
        """Create a new sprint."""
        sprint_data = {
            "name": name,
            "originBoardId": int(board_id)
        }
        response = self._make_request("POST", "/agile/1.0/sprint", json=sprint_data)
        return response.json()
    
    def _start_sprint(self, sprint_id: str) -> Dict[str, Any]:
        """Start a sprint."""
        import datetime
        start_date = datetime.datetime.now().isoformat()
        end_date = (datetime.datetime.now() + datetime.timedelta(days=14)).isoformat()
        
        sprint_data = {
            "state": "active",
            "startDate": start_date,
            "endDate": end_date
        }
        self._make_request("POST", f"/agile/1.0/sprint/{sprint_id}", json=sprint_data)
        return {"success": True, "sprint": sprint_id, "state": "started"}
    
    def _complete_sprint(self, sprint_id: str) -> Dict[str, Any]:
        """Complete a sprint."""
        sprint_data = {"state": "closed"}
        self._make_request("POST", f"/agile/1.0/sprint/{sprint_id}", json=sprint_data)
        return {"success": True, "sprint": sprint_id, "state": "completed"}
    
    def _move_issues_to_sprint(self, sprint_id: str, issue_keys: List[str]) -> Dict[str, Any]:
        """Move issues to a sprint."""
        self._make_request(
            "POST",
            f"/agile/1.0/sprint/{sprint_id}/issue",
            json={"issues": issue_keys}
        )
        return {"success": True, "sprint": sprint_id, "moved_issues": issue_keys}


class JiraAnalytics(JiraAnalyticsTool):
    """Get Jira analytics and metrics.
    
    Provides issue history, worklog data, and project metrics.
    """
    name: str = "jira_analytics"
    produces_user_data: bool = True  # Analytics results may need user review
    description: str = "Get issue history, metrics, and analytics"
    
    class Input(BaseModel):
        issue_key: Optional[str] = Field(None, description="Issue key for history")
        project_key: Optional[str] = Field(None, description="Project key for metrics")
        metric_type: str = Field("history", description="Type: 'history', 'worklog', 'project_stats'")
        time_period: Optional[str] = Field(None, description="Time period filter")
    
    args_schema: type = Input
    
    @log_execution("jira", "analytics", include_args=True, include_result=False)
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