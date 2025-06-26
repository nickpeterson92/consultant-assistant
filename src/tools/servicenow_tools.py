"""ServiceNow ITSM Tools - Enterprise-Grade IT Service Management Operations.

This module implements 15 comprehensive ServiceNow tools for IT Service Management:

Architecture Philosophy:
- **Query Builder Pattern**: Composable, reusable, and secure query construction
- **Security-First**: Automatic input sanitization through GlideQueryBuilder
- **Natural Language**: Support for human-friendly queries
- **Consistent Error Handling**: Graceful degradation with structured responses
- **Performance Optimized**: Field selection and pagination support

Tool Categories:
1. Incident Management (3 tools) - Core ITSM incident lifecycle
2. Change Management (3 tools) - Change request handling
3. Problem Management (3 tools) - Root cause analysis records
4. Task Management (3 tools) - Generic task operations
5. User & CMDB Tools (3 tools) - User, CI, and global search
"""

import os
import json
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

from pydantic import BaseModel, Field, field_validator
from langchain.tools import BaseTool

# Load environment variables
load_dotenv()

from src.utils.logging import get_logger
from src.utils.glide_query_builder import (
    GlideQueryBuilder,
    GlideOperator,
    QueryTemplates,
    escape_glide_query
)

# Initialize logger
logger = get_logger("servicenow")


def log_glide_query(tool_name: str, query: str, operation: str = "query_built"):
    """Log Glide query for debugging and monitoring."""
    logger.info("glide_query",
        component="servicenow",
        tool_name=tool_name,
        operation=operation,
        query=query,
        query_length=len(query)
    )


class ServiceNowClient:
    """ServiceNow API client with connection management."""
    
    def __init__(self, instance: str, username: str, password: str):
        """Initialize ServiceNow client."""
        self.instance = instance.rstrip('/')
        if not self.instance.startswith('https://'):
            self.instance = f"https://{self.instance}"
        self.auth = HTTPBasicAuth(username, password)
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def _make_request(self, method: str, endpoint: str, params: Dict = None, data: Dict = None) -> Dict:
        """Make a request to ServiceNow API with error handling."""
        url = f"{self.instance}/api/now/table/{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                auth=self.auth,
                headers=self.headers,
                params=params,
                json=data
            )
            response.raise_for_status()
            
            # Check if response is JSON
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' not in content_type:
                logger.error("non_json_response",
                    component="servicenow",
                    operation=f"{method}_{endpoint}",
                    content_type=content_type,
                    status_code=response.status_code,
                    body_preview=response.text[:500]
                )
                return {"error": f"ServiceNow returned non-JSON response (status {response.status_code})"}
            
            # Try to decode JSON
            try:
                result = response.json()
            except requests.exceptions.JSONDecodeError as e:
                logger.error("json_decode_error",
                    component="servicenow",
                    operation=f"{method}_{endpoint}",
                    error=str(e),
                    body_preview=response.text[:500]
                )
                return {"error": f"Failed to decode JSON response: {str(e)}"}
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error("servicenow_api_error",
                component="servicenow",
                operation=f"{method}_{endpoint}",
                error=str(e),
                status_code=getattr(e.response, 'status_code', None),
                response_text=getattr(e.response, 'text', '')[:500] if hasattr(e.response, 'text') else ''
            )
            return {"error": f"ServiceNow API error: {str(e)}"}
    
    def query(self, table: str, params: Dict) -> List[Dict]:
        """Query ServiceNow table."""
        result = self._make_request("GET", table, params=params)
        return result.get("result", [])
    
    def get(self, table: str, sys_id: str, params: Dict = None) -> Dict:
        """Get single record by sys_id."""
        result = self._make_request("GET", f"{table}/{sys_id}", params=params)
        return result.get("result", {})
    
    def create(self, table: str, data: Dict) -> Dict:
        """Create new record."""
        result = self._make_request("POST", table, data=data)
        
        # Check for error in response
        if "error" in result:
            return result
            
        # ServiceNow returns the created record directly, not wrapped in "result"
        return result
    
    def update(self, table: str, sys_id: str, data: Dict) -> Dict:
        """Update existing record."""
        result = self._make_request("PATCH", f"{table}/{sys_id}", data=data)
        
        # Check for error in response
        if "error" in result:
            return result
            
        # ServiceNow returns the updated record directly, not wrapped in "result"
        return result


def get_servicenow_connection() -> ServiceNowClient:
    """Create and return a ServiceNow client using environment variables."""
    instance = os.getenv('SERVICENOW_INSTANCE')
    username = os.getenv('SERVICENOW_USER')
    password = os.getenv('SERVICENOW_PASSWORD')
    
    if not all([instance, username, password]):
        raise ValueError(
            "Missing ServiceNow credentials. Please set SERVICENOW_INSTANCE, "
            "SERVICENOW_USER, and SERVICENOW_PASSWORD environment variables."
        )
    
    return ServiceNowClient(
        instance=instance,
        username=username,
        password=password
    )




# ============================================================================
# INCIDENT MANAGEMENT TOOLS (3 tools)
# ============================================================================

class GetIncidentTool(BaseTool):
    """Search/retrieve incidents by number, description, caller, assignment group."""
    
    name: str = "get_incident"
    description: str = """Search/retrieve ServiceNow incidents by number, description, caller, or assignment group.
    
    Examples:
    - "get incident INC0010023"
    - "critical incidents from last week"
    - "incidents assigned to john.smith"
    - "network-related incidents"
    - "open P1 incidents"
    
    Supports filtering by state, priority, assignment, keywords, and date ranges."""
    
    class InputSchema(BaseModel):
        query: str = Field(description="Incident number (INC0010023) or natural language search query")
        limit: int = Field(default=10, description="Maximum number of results (default 10)")
        
    args_schema = InputSchema
    
    def _run(self, query: str, limit: int = 10) -> str:
        """Search for incidents based on query."""
        # Log tool call
        logger.info("tool_call",
            component="servicenow",
            tool_name=self.name,
            tool_args={"query": query, "limit": limit}
        )
        
        try:
            client = get_servicenow_connection()
            
            # Check if it's a specific incident number
            if query.upper().startswith("INC") and len(query.split()) == 1:
                # Get specific incident
                builder = GlideQueryBuilder()
                builder.add_condition("number", GlideOperator.EQUALS, query.upper())
                params = builder.build_params()
                
                incidents = client.query("incident", params)
                if not incidents:
                    return {"error": f"No incident found with number: {query}"}
                
                # Return the raw incident data
                return incidents[0]
            
            # Otherwise do a search
            builder = GlideQueryBuilder()
            query_lower = query.lower()
            
            # State filters
            if any(word in query_lower for word in ["open", "active", "unresolved"]):
                builder.add_condition("state", GlideOperator.NOT_IN, "6,7,8")  # Not Resolved/Closed/Canceled
            elif "closed" in query_lower:
                builder.add_condition("state", GlideOperator.EQUALS, "7")
            elif "resolved" in query_lower:
                builder.add_condition("state", GlideOperator.EQUALS, "6")
            
            # Priority filters
            if any(word in query_lower for word in ["critical", "p1", "priority 1"]):
                builder.add_condition("priority", GlideOperator.EQUALS, "1")
            elif any(word in query_lower for word in ["high", "p2", "priority 2"]):
                builder.add_condition("priority", GlideOperator.EQUALS, "2")
            elif "low" in query_lower:
                builder.add_condition("priority", GlideOperator.GREATER_OR_EQUAL, "4")
            
            # Assignment filters
            if "assigned to me" in query_lower or "my incidents" in query_lower:
                builder.add_condition("assigned_to", GlideOperator.EQUALS, "javascript:gs.getUserID()")
            elif "assigned to" in query_lower:
                # Extract username after "assigned to"
                parts = query_lower.split("assigned to")
                if len(parts) > 1:
                    username = parts[1].strip().split()[0]
                    builder.add_condition("assigned_to.user_name", GlideOperator.CONTAINS, username)
            elif "unassigned" in query_lower:
                builder.add_condition("assigned_to", GlideOperator.IS_EMPTY, "")
            
            # Time filters
            if "today" in query_lower:
                builder.add_condition("opened_at", GlideOperator.GREATER_THAN, "javascript:gs.daysAgo(1)")
            elif "yesterday" in query_lower:
                builder.add_condition("opened_at", GlideOperator.BETWEEN, "javascript:gs.daysAgo(2)@javascript:gs.daysAgo(1)")
            elif "last week" in query_lower:
                builder.add_condition("opened_at", GlideOperator.GREATER_THAN, "javascript:gs.daysAgo(7)")
            elif "last month" in query_lower:
                builder.add_condition("opened_at", GlideOperator.GREATER_THAN, "javascript:gs.daysAgo(30)")
            
            # Keyword search
            keywords = [word for word in query.split() if len(word) > 3 and word.lower() not in 
                       ["incident", "incidents", "from", "last", "week", "month", "assigned", "priority", "open", "closed"]]
            if keywords:
                builder.add_condition("short_description", GlideOperator.CONTAINS, " ".join(keywords))
            
            # Default ordering
            builder.order_by("priority", ascending=True)
            builder.order_by("opened_at", ascending=False)
            builder.limit(limit)
            
            params = builder.build_params()
            log_glide_query("get_incident", params.get("sysparm_query", ""))
            
            incidents = client.query("incident", params)
            
            # Log result
            logger.info("tool_result",
                component="servicenow",
                tool_name=self.name,
                result_type="list",
                result_count=len(incidents) if isinstance(incidents, list) else 1
            )
            
            # Return raw list of incidents
            return incidents
            
        except Exception as e:
            logger.error("tool_error",
                component="servicenow",
                tool_name=self.name,
                error=str(e),
                error_type=type(e).__name__
            )
            return {"error": str(e)}


class CreateIncidentTool(BaseTool):
    """Create new incidents with category, urgency, impact, description."""
    
    name: str = "create_incident"
    description: str = """Create a new ServiceNow incident with category, urgency, impact, and description.
    
    Required: short_description
    Optional: description, priority (1-5), category, caller, assignment_group, urgency, impact"""
    
    class InputSchema(BaseModel):
        short_description: str = Field(description="Brief description of the incident")
        description: Optional[str] = Field(None, description="Detailed description")
        priority: Optional[str] = Field("3", description="Priority (1=Critical, 2=High, 3=Moderate, 4=Low, 5=Planning)")
        category: Optional[str] = Field(None, description="Category (e.g., 'Software', 'Hardware', 'Network')")
        subcategory: Optional[str] = Field(None, description="Subcategory")
        caller_id: Optional[str] = Field(None, description="Caller's username or email")
        assignment_group: Optional[str] = Field(None, description="Assignment group name")
        urgency: Optional[str] = Field(None, description="Urgency (1=High, 2=Medium, 3=Low)")
        impact: Optional[str] = Field(None, description="Impact (1=High, 2=Medium, 3=Low)")
        
        @field_validator('priority')
        def validate_priority(cls, v):
            if v and v not in ["1", "2", "3", "4", "5"]:
                raise ValueError("Priority must be between 1 and 5")
            return v
    
    args_schema = InputSchema
    
    def _run(self, short_description: str, description: Optional[str] = None,
             priority: Optional[str] = "3", category: Optional[str] = None,
             subcategory: Optional[str] = None, caller_id: Optional[str] = None,
             assignment_group: Optional[str] = None, urgency: Optional[str] = None,
             impact: Optional[str] = None) -> str:
        """Create a new incident."""
        # Log tool call
        logger.info("tool_call",
            component="servicenow",
            tool_name=self.name,
            tool_args={
                "short_description": short_description,
                "description": description,
                "priority": priority,
                "category": category,
                "subcategory": subcategory,
                "caller_id": caller_id,
                "assignment_group": assignment_group,
                "urgency": urgency,
                "impact": impact
            }
        )
        
        try:
            client = get_servicenow_connection()
            
            # Build incident data
            incident_data = {
                "short_description": short_description,
                "priority": priority,
                "state": "1",  # New
                "impact": impact or priority,  # Default impact to priority if not specified
                "urgency": urgency or priority,  # Default urgency to priority if not specified
            }
            
            if description:
                incident_data["description"] = description
            if category:
                incident_data["category"] = category
            if subcategory:
                incident_data["subcategory"] = subcategory
            if caller_id:
                incident_data["caller_id"] = caller_id
            if assignment_group:
                incident_data["assignment_group"] = assignment_group
            
            # Create the incident
            result = client.create("incident", incident_data)
            
            # Check for error response
            if "error" in result:
                return result
            
            # Log result
            logger.info("tool_result",
                component="servicenow",
                tool_name=self.name,
                result_type="created",
                result_preview=result.get("number", "Unknown") if isinstance(result, dict) else "Unknown"
            )
            
            # Return raw ServiceNow response - let the LLM format it
            return result
                
        except Exception as e:
            logger.error("tool_error",
                component="servicenow",
                tool_name=self.name,
                error=str(e),
                error_type=type(e).__name__
            )
            return {"error": str(e)}


class UpdateIncidentTool(BaseTool):
    """Update incident status, assignment, resolution details."""
    
    name: str = "update_incident"
    description: str = """Update a ServiceNow incident's status, assignment, or resolution details.
    
    Common updates:
    - Change state (New, In Progress, Resolved, Closed)
    - Update priority or assignment
    - Add work notes or resolution"""
    
    class InputSchema(BaseModel):
        incident_id: str = Field(description="Incident number (INC0010023) or sys_id")
        state: Optional[str] = Field(None, description="State (1=New, 2=In Progress, 6=Resolved, 7=Closed)")
        priority: Optional[str] = Field(None, description="Priority (1-5)")
        assigned_to: Optional[str] = Field(None, description="Username to assign to")
        assignment_group: Optional[str] = Field(None, description="Assignment group")
        work_notes: Optional[str] = Field(None, description="Work notes to add")
        close_notes: Optional[str] = Field(None, description="Resolution/close notes")
        resolution_code: Optional[str] = Field(None, description="Resolution code")
        
    args_schema = InputSchema
    
    def _run(self, incident_id: str, **kwargs) -> str:
        """Update an incident."""
        # Log tool call
        logger.info("tool_call",
            component="servicenow",
            tool_name=self.name,
            tool_args={"incident_id": incident_id, **kwargs}
        )
        
        try:
            client = get_servicenow_connection()
            
            # Get the incident first
            if incident_id.upper().startswith("INC"):
                builder = GlideQueryBuilder()
                builder.add_condition("number", GlideOperator.EQUALS, incident_id.upper())
                params = builder.build_params()
                
                incidents = client.query("incident", params)
                if not incidents:
                    return {"error": f"No incident found with number: {incident_id}"}
                sys_id = incidents[0]["sys_id"]
            else:
                sys_id = incident_id
            
            # Build update data
            update_data = {}
            for field, value in kwargs.items():
                if value is not None:
                    update_data[field] = value
            
            if not update_data:
                return {"error": "No fields to update provided"}
            
            # Update the incident
            result = client.update("incident", sys_id, update_data)
            
            # Log result
            logger.info("tool_result",
                component="servicenow",
                tool_name=self.name,
                result_type="updated",
                result_preview=f"Updated {incident_id}"
            )
            
            # Return raw response or error
            return result
                
        except Exception as e:
            logger.error("tool_error",
                component="servicenow",
                tool_name=self.name,
                error=str(e),
                error_type=type(e).__name__
            )
            return {"error": str(e)}


# ============================================================================
# CHANGE REQUEST MANAGEMENT TOOLS (3 tools)
# ============================================================================

class GetChangeRequestTool(BaseTool):
    """Search change requests by number, type, state, assignment."""
    
    name: str = "get_change_request"
    description: str = """Search ServiceNow change requests by number, type, state, or assignment.
    
    Examples:
    - "get change CHG0010023"
    - "emergency changes this week"
    - "changes pending approval"
    - "failed changes last month"
    - "changes for production servers"""
    
    class InputSchema(BaseModel):
        query: str = Field(description="Change number (CHG0010023) or natural language search query")
        limit: int = Field(default=10, description="Maximum number of results")
        
    args_schema = InputSchema
    
    def _run(self, query: str, limit: int = 10) -> str:
        """Search for change requests."""
        # Log tool call
        logger.info("tool_call",
            component="servicenow",
            tool_name=self.name,
            tool_args={"query": query, "limit": limit}
        )
        
        try:
            client = get_servicenow_connection()
            
            # Check if it's a specific change number
            if query.upper().startswith("CHG") and len(query.split()) == 1:
                builder = GlideQueryBuilder()
                builder.add_condition("number", GlideOperator.EQUALS, query.upper())
                params = builder.build_params()
                
                changes = client.query("change_request", params)
                if not changes:
                    return {"error": f"No change request found with number: {query}"}
                
                # Return raw change data
                return changes[0]
            
            # Otherwise do a search
            builder = GlideQueryBuilder()
            query_lower = query.lower()
            
            # Type filters
            if "emergency" in query_lower:
                builder.add_condition("type", GlideOperator.EQUALS, "Emergency")
            elif "standard" in query_lower:
                builder.add_condition("type", GlideOperator.EQUALS, "Standard")
            elif "normal" in query_lower:
                builder.add_condition("type", GlideOperator.EQUALS, "Normal")
            
            # State filters
            if "pending approval" in query_lower or "awaiting approval" in query_lower:
                builder.add_condition("state", GlideOperator.EQUALS, "-5")  # Pending Approval
            elif "scheduled" in query_lower:
                builder.add_condition("state", GlideOperator.EQUALS, "1")  # Scheduled
            elif "implement" in query_lower:
                builder.add_condition("state", GlideOperator.EQUALS, "2")  # Implement
            elif "failed" in query_lower:
                builder.add_condition("state", GlideOperator.EQUALS, "4")  # Failed
            elif "complete" in query_lower or "successful" in query_lower:
                builder.add_condition("state", GlideOperator.EQUALS, "3")  # Complete
            
            # Time filters
            if "today" in query_lower:
                builder.add_condition("opened_at", GlideOperator.GREATER_THAN, "javascript:gs.daysAgo(1)")
            elif "this week" in query_lower:
                builder.add_condition("opened_at", GlideOperator.GREATER_THAN, "javascript:gs.daysAgo(7)")
            elif "last month" in query_lower:
                builder.add_condition("opened_at", GlideOperator.GREATER_THAN, "javascript:gs.daysAgo(30)")
            
            # Keyword search
            keywords = [word for word in query.split() if len(word) > 3 and word.lower() not in 
                       ["change", "changes", "request", "from", "this", "last", "week", "month"]]
            if keywords:
                builder.add_condition("short_description", GlideOperator.CONTAINS, " ".join(keywords))
            
            builder.order_by("start_date", ascending=False)
            builder.limit(limit)
            
            params = builder.build_params()
            log_glide_query("get_change_request", params.get("sysparm_query", ""))
            
            changes = client.query("change_request", params)
            
            # Log result
            logger.info("tool_result",
                component="servicenow",
                tool_name=self.name,
                result_type="list",
                result_count=len(changes) if isinstance(changes, list) else 1
            )
            
            # Return raw list of changes
            return changes
            
        except Exception as e:
            logger.error("tool_error",
                component="servicenow",
                tool_name=self.name,
                error=str(e),
                error_type=type(e).__name__
            )
            return {"error": str(e)}


class CreateChangeRequestTool(BaseTool):
    """Create standard/normal/emergency changes."""
    
    name: str = "create_change_request"
    description: str = """Create a new ServiceNow change request (standard/normal/emergency).
    
    Types: Normal, Standard, Emergency
    Required: short_description, type"""
    
    class InputSchema(BaseModel):
        short_description: str = Field(description="Brief description of the change")
        type: str = Field(description="Change type: Normal, Standard, or Emergency")
        description: Optional[str] = Field(None, description="Detailed description")
        justification: Optional[str] = Field(None, description="Business justification")
        risk: Optional[str] = Field("3", description="Risk level (1=High, 2=Medium, 3=Low)")
        impact: Optional[str] = Field("3", description="Impact (1=High, 2=Medium, 3=Low)")
        start_date: Optional[str] = Field(None, description="Planned start date (YYYY-MM-DD HH:MM:SS)")
        end_date: Optional[str] = Field(None, description="Planned end date (YYYY-MM-DD HH:MM:SS)")
        assignment_group: Optional[str] = Field(None, description="Assignment group")
        implementation_plan: Optional[str] = Field(None, description="Implementation plan")
        backout_plan: Optional[str] = Field(None, description="Backout plan")
        test_plan: Optional[str] = Field(None, description="Test plan")
        
    args_schema = InputSchema
    
    def _run(self, short_description: str, type: str, **kwargs) -> str:
        """Create a new change request."""
        # Log tool call
        logger.info("tool_call",
            component="servicenow",
            tool_name=self.name,
            tool_args={"short_description": short_description, "type": type, **kwargs}
        )
        
        try:
            client = get_servicenow_connection()
            
            # Validate type
            valid_types = ["Normal", "Standard", "Emergency"]
            if type not in valid_types:
                return f"Invalid change type. Must be one of: {', '.join(valid_types)}"
            
            change_data = {
                "short_description": short_description,
                "type": type,
                "state": "-5",  # Draft
            }
            
            # Add optional fields
            for field in ["description", "justification", "risk", "impact", 
                         "start_date", "end_date", "assignment_group",
                         "implementation_plan", "backout_plan", "test_plan"]:
                if field in kwargs and kwargs[field]:
                    change_data[field] = kwargs[field]
            
            result = client.create("change_request", change_data)
            
            # Log result
            logger.info("tool_result",
                component="servicenow",
                tool_name=self.name,
                result_type="created",
                result_preview=result.get("number", "Unknown") if isinstance(result, dict) else "Unknown"
            )
            
            # Return raw response or error
            return result
                
        except Exception as e:
            logger.error("tool_error",
                component="servicenow",
                tool_name=self.name,
                error=str(e),
                error_type=type(e).__name__
            )
            return {"error": str(e)}


class UpdateChangeRequestTool(BaseTool):
    """Update change state, implementation details, approvals."""
    
    name: str = "update_change_request"
    description: str = """Update a ServiceNow change request's state, implementation details, or approvals.
    
    Common updates:
    - Change state (Draft, Scheduled, Implement, Complete)
    - Update implementation details
    - Add approval notes
    - Modify schedule"""
    
    class InputSchema(BaseModel):
        change_id: str = Field(description="Change number (CHG0010023) or sys_id")
        state: Optional[str] = Field(None, description="State (-5=Draft, 1=Scheduled, 2=Implement, 3=Complete)")
        priority: Optional[str] = Field(None, description="Priority (1-4)")
        implementation_plan: Optional[str] = Field(None, description="Implementation plan details")
        backout_plan: Optional[str] = Field(None, description="Backout plan")
        test_plan: Optional[str] = Field(None, description="Test plan")
        start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD HH:MM:SS)")
        end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD HH:MM:SS)")
        work_notes: Optional[str] = Field(None, description="Work notes")
        
    args_schema = InputSchema
    
    def _run(self, change_id: str, **kwargs) -> str:
        """Update a change request."""
        # Log tool call
        logger.info("tool_call",
            component="servicenow",
            tool_name=self.name,
            tool_args={"change_id": change_id, **kwargs}
        )
        
        try:
            client = get_servicenow_connection()
            
            # Get the change first
            if change_id.upper().startswith("CHG"):
                builder = GlideQueryBuilder()
                builder.add_condition("number", GlideOperator.EQUALS, change_id.upper())
                params = builder.build_params()
                
                changes = client.query("change_request", params)
                if not changes:
                    return {"error": f"No change request found with number: {change_id}"}
                sys_id = changes[0]["sys_id"]
            else:
                sys_id = change_id
            
            # Build update data
            update_data = {}
            for field, value in kwargs.items():
                if value is not None:
                    update_data[field] = value
            
            if not update_data:
                return {"error": "No fields to update provided"}
            
            # Update the change
            result = client.update("change_request", sys_id, update_data)
            
            # Log result
            logger.info("tool_result",
                component="servicenow",
                tool_name=self.name,
                result_type="updated",
                result_preview=f"Updated {change_id}"
            )
            
            # Return raw response or error
            return result
                
        except Exception as e:
            logger.error("tool_error",
                component="servicenow",
                tool_name=self.name,
                error=str(e),
                error_type=type(e).__name__
            )
            return {"error": str(e)}


# ============================================================================
# PROBLEM MANAGEMENT TOOLS (3 tools)
# ============================================================================

class GetProblemTool(BaseTool):
    """Search problems by number, description, root cause."""
    
    name: str = "get_problem"
    description: str = """Search ServiceNow problems by number, description, or root cause.
    
    Examples:
    - "get problem PRB0010023"
    - "active problems"
    - "problems related to email"
    - "high priority problems"
    - "known errors"""
    
    class InputSchema(BaseModel):
        query: str = Field(description="Problem number (PRB0010023) or search query")
        limit: int = Field(default=10, description="Maximum results")
        
    args_schema = InputSchema
    
    def _run(self, query: str, limit: int = 10) -> str:
        """Search for problems."""
        # Log tool call
        logger.info("tool_call",
            component="servicenow",
            tool_name=self.name,
            tool_args={"query": query, "limit": limit}
        )
        
        try:
            client = get_servicenow_connection()
            
            # Check if it's a specific problem number
            if query.upper().startswith("PRB") and len(query.split()) == 1:
                builder = GlideQueryBuilder()
                builder.add_condition("number", GlideOperator.EQUALS, query.upper())
                params = builder.build_params()
                
                problems = client.query("problem", params)
                if not problems:
                    return {"error": f"No problem found with number: {query}"}
                
                # Return raw problem data
                return problems[0]
            
            # Otherwise do a search
            builder = GlideQueryBuilder()
            query_lower = query.lower()
            
            # State filters
            if "active" in query_lower:
                builder.add_condition("state", GlideOperator.NOT_EQUALS, "4")  # Not Closed
            elif "closed" in query_lower:
                builder.add_condition("state", GlideOperator.EQUALS, "4")
            
            # Known error filter
            if "known error" in query_lower:
                builder.add_condition("known_error", GlideOperator.EQUALS, "true")
            
            # Priority filters
            if "high priority" in query_lower or "critical" in query_lower:
                builder.add_condition("priority", GlideOperator.LESS_OR_EQUAL, "2")
            
            # Keywords
            keywords = [word for word in query.split() if len(word) > 3 and 
                       word.lower() not in ["problem", "problems", "active", "high", "priority", "known", "error"]]
            if keywords:
                builder.add_condition("short_description", GlideOperator.CONTAINS, " ".join(keywords))
                builder.add_or_condition("root_cause", GlideOperator.CONTAINS, " ".join(keywords))
            
            builder.order_by("priority", ascending=True)
            builder.limit(limit)
            
            params = builder.build_params()
            log_glide_query("get_problem", params.get("sysparm_query", ""))
            
            problems = client.query("problem", params)
            
            # Log result
            logger.info("tool_result",
                component="servicenow",
                tool_name=self.name,
                result_type="list",
                result_count=len(problems) if isinstance(problems, list) else 1
            )
            
            # Return raw list of problems
            return problems
            
        except Exception as e:
            logger.error("tool_error",
                component="servicenow",
                tool_name=self.name,
                error=str(e),
                error_type=type(e).__name__
            )
            return {"error": str(e)}


class CreateProblemTool(BaseTool):
    """Create problem records with known error info."""
    
    name: str = "create_problem"
    description: str = """Create a new ServiceNow problem record with known error information.
    
    Required: short_description
    Optional: description, priority, category, known_error, workaround, root_cause"""
    
    class InputSchema(BaseModel):
        short_description: str = Field(description="Brief description of the problem")
        description: Optional[str] = Field(None, description="Detailed description")
        priority: Optional[str] = Field("3", description="Priority (1=Critical, 2=High, 3=Moderate, 4=Low)")
        category: Optional[str] = Field(None, description="Problem category")
        known_error: Optional[bool] = Field(False, description="Is this a known error?")
        workaround: Optional[str] = Field(None, description="Workaround instructions")
        root_cause: Optional[str] = Field(None, description="Root cause analysis")
        assignment_group: Optional[str] = Field(None, description="Assignment group")
        
    args_schema = InputSchema
    
    def _run(self, short_description: str, **kwargs) -> str:
        """Create a new problem."""
        # Log tool call
        logger.info("tool_call",
            component="servicenow",
            tool_name=self.name,
            tool_args={"short_description": short_description, **kwargs}
        )
        
        try:
            client = get_servicenow_connection()
            
            problem_data = {
                "short_description": short_description,
                "state": "1",  # New
                "priority": kwargs.get("priority", "3"),
            }
            
            # Add optional fields
            for field in ["description", "category", "known_error", "workaround", 
                         "root_cause", "assignment_group"]:
                if field in kwargs and kwargs[field] is not None:
                    problem_data[field] = kwargs[field]
            
            result = client.create("problem", problem_data)
            
            # Log result
            logger.info("tool_result",
                component="servicenow",
                tool_name=self.name,
                result_type="created",
                result_preview=result.get("number", "Unknown") if isinstance(result, dict) else "Unknown"
            )
            
            # Return raw response or error
            return result
                
        except Exception as e:
            logger.error("tool_error",
                component="servicenow",
                tool_name=self.name,
                error=str(e),
                error_type=type(e).__name__
            )
            return {"error": str(e)}


class UpdateProblemTool(BaseTool):
    """Update problem investigation, workaround, resolution."""
    
    name: str = "update_problem"
    description: str = """Update a ServiceNow problem record's investigation, workaround, or resolution.
    
    Common updates:
    - Add root cause analysis
    - Update workaround
    - Mark as known error
    - Change state or priority"""
    
    class InputSchema(BaseModel):
        problem_id: str = Field(description="Problem number (PRB0010023) or sys_id")
        state: Optional[str] = Field(None, description="State (1=New, 2=Assigned, 3=Root Cause Analysis, 4=Closed)")
        priority: Optional[str] = Field(None, description="Priority (1-4)")
        root_cause: Optional[str] = Field(None, description="Root cause analysis")
        workaround: Optional[str] = Field(None, description="Workaround instructions")
        known_error: Optional[bool] = Field(None, description="Mark as known error")
        work_notes: Optional[str] = Field(None, description="Investigation notes")
        
    args_schema = InputSchema
    
    def _run(self, problem_id: str, **kwargs) -> str:
        """Update a problem."""
        # Log tool call
        logger.info("tool_call",
            component="servicenow",
            tool_name=self.name,
            tool_args={"problem_id": problem_id, **kwargs}
        )
        
        try:
            client = get_servicenow_connection()
            
            # Get the problem first
            if problem_id.upper().startswith("PRB"):
                builder = GlideQueryBuilder()
                builder.add_condition("number", GlideOperator.EQUALS, problem_id.upper())
                params = builder.build_params()
                
                problems = client.query("problem", params)
                if not problems:
                    return {"error": f"No problem found with number: {problem_id}"}
                sys_id = problems[0]["sys_id"]
            else:
                sys_id = problem_id
            
            # Build update data
            update_data = {}
            for field, value in kwargs.items():
                if value is not None:
                    update_data[field] = value
            
            if not update_data:
                return {"error": "No fields to update provided"}
            
            # Update the problem
            result = client.update("problem", sys_id, update_data)
            
            # Log result
            logger.info("tool_result",
                component="servicenow",
                tool_name=self.name,
                result_type="updated",
                result_preview=f"Updated {problem_id}"
            )
            
            # Return raw response or error
            return result
                
        except Exception as e:
            logger.error("tool_error",
                component="servicenow",
                tool_name=self.name,
                error=str(e),
                error_type=type(e).__name__
            )
            return {"error": str(e)}


# ============================================================================
# TASK MANAGEMENT TOOLS (3 tools)
# ============================================================================

class GetTaskTool(BaseTool):
    """Search generic tasks across tables."""
    
    name: str = "get_task"
    description: str = """Search ServiceNow tasks across all task-based tables.
    
    Searches incidents, problems, changes, and generic tasks.
    Examples:
    - "all tasks assigned to me"
    - "overdue tasks"
    - "high priority tasks"
    - "tasks due this week"""
    
    class InputSchema(BaseModel):
        query: str = Field(description="Search query for tasks")
        limit: int = Field(default=10, description="Maximum results")
        
    args_schema = InputSchema
    
    def _run(self, query: str, limit: int = 10) -> str:
        """Search for tasks."""
        # Log tool call
        logger.info("tool_call",
            component="servicenow",
            tool_name=self.name,
            tool_args={"query": query, "limit": limit}
        )
        
        try:
            client = get_servicenow_connection()
            builder = GlideQueryBuilder()
            
            query_lower = query.lower()
            
            # Assignment filters
            if "assigned to me" in query_lower or "my tasks" in query_lower:
                builder.add_condition("assigned_to", GlideOperator.EQUALS, "javascript:gs.getUserID()")
            elif "unassigned" in query_lower:
                builder.add_condition("assigned_to", GlideOperator.IS_EMPTY, "")
            
            # State filters
            if "overdue" in query_lower:
                builder.add_condition("due_date", GlideOperator.LESS_THAN, "javascript:gs.now()")
                builder.add_condition("state", GlideOperator.NOT_IN, "3,4,7")  # Not complete/closed
            elif "open" in query_lower or "active" in query_lower:
                builder.add_condition("active", GlideOperator.EQUALS, "true")
            
            # Due date filters
            if "due today" in query_lower:
                builder.add_condition("due_date", GlideOperator.ON, "javascript:gs.now()")
            elif "due this week" in query_lower:
                builder.add_condition("due_date", GlideOperator.LESS_THAN, "javascript:gs.daysAgo(-7)")
            
            # Priority
            if "high priority" in query_lower:
                builder.add_condition("priority", GlideOperator.LESS_OR_EQUAL, "2")
            
            # Keywords
            keywords = [word for word in query.split() if len(word) > 3 and 
                       word.lower() not in ["task", "tasks", "assigned", "overdue", "open", "due", "this", "week"]]
            if keywords:
                builder.add_condition("short_description", GlideOperator.CONTAINS, " ".join(keywords))
            
            builder.order_by("priority", ascending=True)
            builder.order_by("due_date", ascending=True)
            builder.limit(limit)
            
            params = builder.build_params()
            log_glide_query("get_task", params.get("sysparm_query", ""))
            
            tasks = client.query("task", params)
            
            # Log result
            logger.info("tool_result",
                component="servicenow",
                tool_name=self.name,
                result_type="list",
                result_count=len(tasks) if isinstance(tasks, list) else 1
            )
            
            # Return raw list of tasks
            return tasks
            
        except Exception as e:
            logger.error("tool_error",
                component="servicenow",
                tool_name=self.name,
                error=str(e),
                error_type=type(e).__name__
            )
            return {"error": str(e)}


class CreateTaskTool(BaseTool):
    """Create tasks with assignment, due dates."""
    
    name: str = "create_task"
    description: str = """Create a new generic task with assignment and due dates.
    
    Required: short_description
    Optional: description, priority, assigned_to, assignment_group, due_date"""
    
    class InputSchema(BaseModel):
        short_description: str = Field(description="Brief description of the task")
        description: Optional[str] = Field(None, description="Detailed description")
        priority: Optional[str] = Field("3", description="Priority (1-5)")
        assigned_to: Optional[str] = Field(None, description="Username to assign to")
        assignment_group: Optional[str] = Field(None, description="Assignment group")
        due_date: Optional[str] = Field(None, description="Due date (YYYY-MM-DD HH:MM:SS)")
        
    args_schema = InputSchema
    
    def _run(self, short_description: str, **kwargs) -> str:
        """Create a task."""
        # Log tool call
        logger.info("tool_call",
            component="servicenow",
            tool_name=self.name,
            tool_args={"short_description": short_description, **kwargs}
        )
        
        try:
            client = get_servicenow_connection()
            
            task_data = {
                "short_description": short_description,
                "state": "1",  # Open
                "priority": kwargs.get("priority", "3"),
            }
            
            # Add optional fields
            for field in ["description", "assigned_to", "assignment_group", "due_date"]:
                if field in kwargs and kwargs[field]:
                    task_data[field] = kwargs[field]
            
            result = client.create("task", task_data)
            
            # Log result
            logger.info("tool_result",
                component="servicenow",
                tool_name=self.name,
                result_type="created",
                result_preview=result.get("number", "Unknown") if isinstance(result, dict) else "Unknown"
            )
            
            # Return raw response or error
            return result
                
        except Exception as e:
            logger.error("tool_error",
                component="servicenow",
                tool_name=self.name,
                error=str(e),
                error_type=type(e).__name__
            )
            return {"error": str(e)}


class UpdateTaskTool(BaseTool):
    """Update task progress, completion status."""
    
    name: str = "update_task"
    description: str = """Update task progress and completion status.
    
    Common updates:
    - Change state (Open, Work in Progress, Complete)
    - Update assignment
    - Modify due date"""
    
    class InputSchema(BaseModel):
        task_id: str = Field(description="Task number or sys_id")
        state: Optional[str] = Field(None, description="State (1=Open, 2=Work in Progress, 3=Complete)")
        priority: Optional[str] = Field(None, description="Priority (1-5)")
        assigned_to: Optional[str] = Field(None, description="Username to assign to")
        due_date: Optional[str] = Field(None, description="Due date (YYYY-MM-DD HH:MM:SS)")
        work_notes: Optional[str] = Field(None, description="Progress notes")
        
    args_schema = InputSchema
    
    def _run(self, task_id: str, **kwargs) -> str:
        """Update a task."""
        # Log tool call
        logger.info("tool_call",
            component="servicenow",
            tool_name=self.name,
            tool_args={"task_id": task_id, **kwargs}
        )
        
        try:
            client = get_servicenow_connection()
            
            # Build update data
            update_data = {}
            for field, value in kwargs.items():
                if value is not None:
                    update_data[field] = value
            
            if not update_data:
                return {"error": "No fields to update provided"}
            
            # Update the task
            result = client.update("task", task_id, update_data)
            
            # Log result
            logger.info("tool_result",
                component="servicenow",
                tool_name=self.name,
                result_type="updated",
                result_preview=f"Updated {task_id}"
            )
            
            # Return raw response or error
            return result
                
        except Exception as e:
            logger.error("tool_error",
                component="servicenow",
                tool_name=self.name,
                error=str(e),
                error_type=type(e).__name__
            )
            return {"error": str(e)}


# ============================================================================
# USER & CMDB TOOLS (3 tools)
# ============================================================================

class GetUserTool(BaseTool):
    """Search users by name, email, department, role."""
    
    name: str = "get_user"
    description: str = """Search ServiceNow users by name, email, department, or role.
    
    Examples:
    - "john smith"
    - "john.smith@company.com"
    - "active users in IT department"
    - "users with admin role"""
    
    class InputSchema(BaseModel):
        query: str = Field(description="Search query for users")
        limit: int = Field(default=10, description="Maximum results")
        
    args_schema = InputSchema
    
    def _run(self, query: str, limit: int = 10) -> str:
        """Search for users."""
        # Log tool call
        logger.info("tool_call",
            component="servicenow",
            tool_name=self.name,
            tool_args={"query": query, "limit": limit}
        )
        
        try:
            client = get_servicenow_connection()
            
            # Use the query template for user search
            builder = QueryTemplates.user_search(query)
            
            # Add additional filters based on query
            query_lower = query.lower()
            if "active" in query_lower:
                builder.add_condition("active", GlideOperator.EQUALS, "true")
            elif "inactive" in query_lower:
                builder.add_condition("active", GlideOperator.EQUALS, "false")
            
            # Department filter
            if "department" in query_lower:
                dept_keywords = query_lower.split("department")[1].strip().split()[0]
                builder.add_condition("department", GlideOperator.CONTAINS, dept_keywords)
            
            # Role filter
            if "role" in query_lower:
                # Note: Role checking requires a different approach in ServiceNow
                # This is a simplified version
                if "admin" in query_lower:
                    builder.add_condition("roles", GlideOperator.CONTAINS, "admin")
            
            builder.limit(limit)
            params = builder.build_params()
            log_glide_query("get_user", params.get("sysparm_query", ""))
            
            users = client.query("sys_user", params)
            
            # Log result
            logger.info("tool_result",
                component="servicenow",
                tool_name=self.name,
                result_type="list",
                result_count=len(users) if isinstance(users, list) else 1
            )
            
            # Return raw list of users
            return users
            
        except Exception as e:
            logger.error("tool_error",
                component="servicenow",
                tool_name=self.name,
                error=str(e),
                error_type=type(e).__name__
            )
            return {"error": str(e)}


class GetCMDBItemTool(BaseTool):
    """Search configuration items by name, class, relationships."""
    
    name: str = "get_cmdb_item"
    description: str = """Search ServiceNow Configuration Items (CIs) by name, class, or relationships.
    
    Examples:
    - "web servers"
    - "database servers in production"
    - "windows servers"
    - "CIs related to email service"
    - "server123.company.com"""
    
    class InputSchema(BaseModel):
        query: str = Field(description="Search query for configuration items")
        ci_class: Optional[str] = Field(None, description="CI class (e.g., cmdb_ci_server, cmdb_ci_database)")
        limit: int = Field(default=10, description="Maximum results")
        
    args_schema = InputSchema
    
    def _run(self, query: str, ci_class: Optional[str] = None, limit: int = 10) -> str:
        """Search for CMDB items."""
        # Log tool call
        logger.info("tool_call",
            component="servicenow",
            tool_name=self.name,
            tool_args={"query": query, "ci_class": ci_class, "limit": limit}
        )
        
        try:
            client = get_servicenow_connection()
            
            # Determine table to query
            table = ci_class or "cmdb_ci"
            
            builder = GlideQueryBuilder()
            
            query_lower = query.lower()
            
            # Environment filters
            if "production" in query_lower or "prod" in query_lower:
                builder.add_condition("environment", GlideOperator.EQUALS, "Production")
            elif "development" in query_lower or "dev" in query_lower:
                builder.add_condition("environment", GlideOperator.EQUALS, "Development")
            elif "test" in query_lower:
                builder.add_condition("environment", GlideOperator.EQUALS, "Test")
            
            # State filters
            if "active" in query_lower:
                builder.add_condition("operational_status", GlideOperator.EQUALS, "1")  # Operational
            elif "retired" in query_lower:
                builder.add_condition("operational_status", GlideOperator.EQUALS, "6")  # Retired
            
            # Class-specific filters
            if "server" in query_lower and not ci_class:
                table = "cmdb_ci_server"
            elif "database" in query_lower and not ci_class:
                table = "cmdb_ci_database"
            elif "application" in query_lower and not ci_class:
                table = "cmdb_ci_appl"
            
            # Keywords
            keywords = [word for word in query.split() if len(word) > 3 and 
                       word.lower() not in ["cmdb", "item", "items", "configuration", "production", "development", "server", "database"]]
            if keywords:
                builder.add_condition("name", GlideOperator.CONTAINS, " ".join(keywords))
                builder.add_or_condition("short_description", GlideOperator.CONTAINS, " ".join(keywords))
            
            builder.order_by("name", ascending=True)
            builder.limit(limit)
            
            params = builder.build_params()
            log_glide_query("get_cmdb_item", params.get("sysparm_query", ""))
            
            items = client.query(table, params)
            
            # Log result
            logger.info("tool_result",
                component="servicenow",
                tool_name=self.name,
                result_type="list",
                result_count=len(items) if isinstance(items, list) else 1
            )
            
            # Return raw list of items
            return items
            
        except Exception as e:
            logger.error("tool_error",
                component="servicenow",
                tool_name=self.name,
                error=str(e),
                error_type=type(e).__name__
            )
            return {"error": str(e)}


class SearchServiceNowTool(BaseTool):
    """Global search across multiple tables with encoded queries."""
    
    name: str = "search_servicenow"
    description: str = """Perform a global search across ServiceNow tables using encoded queries.
    
    This is the most flexible search tool, allowing complex queries across any table.
    
    Examples:
    - Search incidents: table=incident, query="priority=1^state!=7"
    - Search all tasks: table=task, query="assigned_to=javascript:gs.getUserID()"
    - Search changes by date: table=change_request, query="opened_at>javascript:gs.daysAgo(7)"
    
    Supports all GlideRecord query operators and JavaScript functions."""
    
    class InputSchema(BaseModel):
        table: str = Field(description="ServiceNow table name (incident, problem, change_request, task, etc.)")
        encoded_query: Optional[str] = Field(None, description="Encoded query string (e.g., 'state=1^priority<=2')")
        fields: Optional[List[str]] = Field(None, description="Fields to return")
        limit: int = Field(default=20, description="Maximum results")
        order_by: Optional[str] = Field(None, description="Field to order by (prefix with - for descending)")
        
    args_schema = InputSchema
    
    def _run(self, table: str, encoded_query: Optional[str] = None, 
             fields: Optional[List[str]] = None, limit: int = 20,
             order_by: Optional[str] = None) -> str:
        """Perform global search."""
        # Log tool call
        logger.info("tool_call",
            component="servicenow",
            tool_name=self.name,
            tool_args={
                "table": table,
                "encoded_query": encoded_query,
                "fields": fields,
                "limit": limit,
                "order_by": order_by
            }
        )
        
        try:
            client = get_servicenow_connection()
            
            builder = GlideQueryBuilder()
            
            # Parse encoded query if provided
            if encoded_query:
                # For simplicity, we'll pass it directly as sysparm_query
                # In a full implementation, we'd parse and validate it
                params = {
                    "sysparm_query": encoded_query,
                    "sysparm_limit": str(limit),
                    "sysparm_display_value": "true"
                }
                
                if fields:
                    params["sysparm_fields"] = ",".join(fields)
                
                if order_by:
                    if order_by.startswith("-"):
                        params["sysparm_query"] += f"^ORDERBYDESC{order_by[1:]}"
                    else:
                        params["sysparm_query"] += f"^ORDERBY{order_by}"
            else:
                # Use builder for empty query
                builder.limit(limit)
                if fields:
                    builder.fields(fields)
                if order_by:
                    if order_by.startswith("-"):
                        builder.order_by(order_by[1:], ascending=False)
                    else:
                        builder.order_by(order_by, ascending=True)
                params = builder.build_params()
            
            log_glide_query("search_servicenow", params.get("sysparm_query", ""))
            
            results = client.query(table, params)
            
            # Log result
            logger.info("tool_result",
                component="servicenow",
                tool_name=self.name,
                result_type="list",
                result_count=len(results) if isinstance(results, list) else 1
            )
            
            # Return raw list of results
            return results
            
        except Exception as e:
            logger.error("tool_error",
                component="servicenow",
                tool_name=self.name,
                error=str(e),
                error_type=type(e).__name__
            )
            return {"error": str(e)}


# Export all tools - EXACTLY 15 tools as requested
ALL_SERVICENOW_TOOLS = [
    # Incident Management (3 tools)
    GetIncidentTool(),
    CreateIncidentTool(),
    UpdateIncidentTool(),
    # Change Request Management (3 tools)
    GetChangeRequestTool(),
    CreateChangeRequestTool(),
    UpdateChangeRequestTool(),
    # Problem Management (3 tools)
    GetProblemTool(),
    CreateProblemTool(),
    UpdateProblemTool(),
    # Task Management (3 tools)
    GetTaskTool(),
    CreateTaskTool(),
    UpdateTaskTool(),
    # User & CMDB Tools (3 tools)
    GetUserTool(),
    GetCMDBItemTool(),
    SearchServiceNowTool(),
]