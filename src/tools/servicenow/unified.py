"""Unified ServiceNow tools for ITSM operations and workflow management."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from .base import (
    ServiceNowReadTool,
    ServiceNowWriteTool,
    ServiceNowWorkflowTool,
    ServiceNowAnalyticsTool
    )
from src.utils.glide_query_builder import GlideQueryBuilder
from src.utils.logging.framework import log_execution


class ServiceNowGet(ServiceNowReadTool):
    """Get any ServiceNow record by sys_id or number.
    
    Simple, direct record retrieval from any table with automatic
    table detection from number prefixes (INC, CHG, PRB, etc).
    """
    name: str = "servicenow_get"
    description: str = "Get a ServiceNow record by ID or number"
    produces_user_data: bool = True  # Record details may need user review
    
    class Input(BaseModel):
        table_name: Optional[str] = Field(None, description="Table name (e.g., incident, change_request). Optional if using number.")
        sys_id: Optional[str] = Field(None, description="System ID of the record")
        number: Optional[str] = Field(None, description="Record number (e.g., INC0001234)")
        fields: Optional[List[str]] = Field(None, description="Specific fields to return")
    
    args_schema: type = Input
    
    @log_execution("servicenow", "get_record", include_args=True, include_result=False)
    def _execute(self, table_name: Optional[str] = None, sys_id: Optional[str] = None,
                 number: Optional[str] = None, fields: Optional[List[str]] = None) -> Any:
        """Execute the get operation."""
        # Validate inputs
        if not sys_id and not number:
            raise ValueError("Missing required identifier: No sys_id or number was provided to identify the record.")
            
        # Auto-detect table from number if not provided
        if not table_name and number:
            table_name = self._detect_table_from_number(number)
            if not table_name:
                raise ValueError(f"Unknown record number format: Could not determine the table type from number: {number}")
        
        if not table_name:
            raise ValueError("Missing table name: A sys_id was provided but no table name to search in.")
            
        # Use default fields if not specified
        if not fields:
            fields = self._get_default_fields(table_name)
            
        # Build endpoint
        if sys_id:
            endpoint = f"/table/{table_name}/{sys_id}"
            # Get by sys_id with dot-walking support
            params = self._build_query_params(
                fields=fields,
                display_value="all"  # Important for dot-walking
            )
            response = self._make_request("GET", endpoint, params=params)
            return response.json().get('result', {})
        else:
            # Use search endpoint with number
            params = self._build_query_params(
                query=f"number={number}",
                fields=fields,
                limit=1,
                display_value="all"  # Important for dot-walking
            )
            response = self._make_request("GET", f"/table/{table_name}", params=params)
            data = response.json()
            if data.get('result'):
                return data['result'][0]
            else:
                raise ValueError(f"Record not found: No {table_name} record found with number: {number}")


class ServiceNowSearch(ServiceNowReadTool):
    """Search ServiceNow records with flexible criteria.
    
    Handles both natural language queries and Glide encoded queries.
    The LLM can pass human-friendly searches or precise conditions.
    Supports dot-walking for related fields (e.g., caller_id.name).
    produces_user_data: bool = True  # Search results often need user selection
    """
    name: str = "servicenow_search"
    description: str = "Search ServiceNow records with natural language or encoded queries"
    
    class Input(BaseModel):
        table_name: str = Field(description="Table to search (e.g., incident, change_request)")
        query: str = Field(description="Natural language or encoded query")
        fields: Optional[List[str]] = Field(None, description="Fields to return (supports dot-walking like 'caller_id.name')")
        limit: int = Field(100, description="Maximum records to return")
        order_by: Optional[str] = Field(None, description="Field to sort by")
        order_desc: bool = Field(True, description="Sort descending")
    
    args_schema: type = Input
    
    @log_execution("servicenow", "search_records", include_args=True, include_result=False)
    def _execute(self, table_name: str, query: str, fields: Optional[List[str]] = None,
                 limit: int = 100, order_by: Optional[str] = None, 
                 order_desc: bool = True) -> Any:
        """Execute the search operation with NLQ support."""
        
        # Check if query is already encoded
        if self._is_encoded_query(query):
            # Use as-is
            encoded_query = query
        else:
            # Try NLQ API
            nlq_result = self._execute_nlq_query(query, table_name)
            
            if nlq_result["success"]:
                encoded_query = nlq_result["encoded_query"]
            else:
                # Return guidance for LLM to retry with structured query
                raise ValueError(f"Natural language query not understood: ServiceNow couldn't interpret: '{query}'")
        
        # Add ordering if specified
        if order_by:
            if order_desc:
                encoded_query += f"^ORDERBYDESC{order_by}"
            else:
                encoded_query += f"^ORDERBY{order_by}"
                
        self._log_query(encoded_query)
        
        # Use default fields if not specified
        if not fields:
            fields = self._get_default_fields(table_name)
            
        # Build params with dot-walking support
        params = self._build_query_params(
            query=encoded_query,
            fields=fields,
            limit=limit,
            display_value="all"  # Important for dot-walking
        )
        
        response = self._make_request("GET", f"/table/{table_name}", params=params)
        return response.json().get('result', [])


class ServiceNowCreate(ServiceNowWriteTool):
    """Create records in any ServiceNow table.
    
    Simple creation with automatic validation of required fields
    based on table type.
    """
    produces_user_data: bool = False  # Create operations don't require user selection
    name: str = "servicenow_create"
    description: str = "Create a new ServiceNow record"
    
    class Input(BaseModel):
        table_name: str = Field(description="Table to create record in")
        data: Dict[str, Any] = Field(description="Field values for the new record")
    
    args_schema: type = Input
    
    @log_execution("servicenow", "create_record", include_args=True, include_result=False)
    def _execute(self, table_name: str, data: Dict[str, Any]) -> Any:
        """Execute the create operation."""
        # Validate required fields
        self._validate_required_fields(table_name, data)
        
        # Create the record
        response = self._make_request("POST", f"/table/{table_name}", json=data)
        result = response.json().get('result', {})
        
        # Return key identifying fields
        return {
            'sys_id': result.get('sys_id'),
            'number': result.get('number'),
            'short_description': result.get('short_description'),
            'state': result.get('state'),
            'message': f"Created {table_name} record successfully"
        }


class ServiceNowUpdate(ServiceNowWriteTool):
    """Update ServiceNow records following best practices.
    
    Supports updates by:
    - sys_id (preferred for performance)
    - number (queries for sys_id first)
    produces_user_data: bool = False  # Update operations don't require user selection
    - where clause (bulk updates)
    
    Uses PATCH method for partial updates per ServiceNow Table API.
    """
    name: str = "servicenow_update"
    description: str = "Update ServiceNow records"
    
    class Input(BaseModel):
        table_name: str = Field(description="Table containing the record")
        sys_id: Optional[str] = Field(None, description="System ID of record to update (preferred)")
        number: Optional[str] = Field(None, description="Record number to update (e.g., INC0001234)")
        where: Optional[str] = Field(None, description="Encoded query for bulk updates")
        data: Dict[str, Any] = Field(description="Field values to update")
    
    args_schema: type = Input
    
    @log_execution("servicenow", "update_record", include_args=True, include_result=False)
    def _execute(self, table_name: str, data: Dict[str, Any],
                 sys_id: Optional[str] = None, number: Optional[str] = None,
                 where: Optional[str] = None) -> Any:
        """Execute the update operation following ServiceNow best practices."""
        # Best practice: Use sys_id when available for direct updates
        if sys_id and not number:  # Only use sys_id if number not provided
            endpoint = f"/table/{table_name}/{sys_id}"
            response = self._make_request("PATCH", endpoint, json=data)
            result = response.json().get('result', {})
            return {
                'sys_id': result.get('sys_id'),
                'number': result.get('number'),
                'short_description': result.get('short_description'),
                'state': result.get('state'),
                'message': "Record updated successfully"
            }
        
        elif number:
            # Find by number first - ServiceNow best practice
            search_params = {
                'sysparm_query': f"number={number}",
                'sysparm_fields': 'sys_id',
                'sysparm_limit': '1'
            }
            search_response = self._make_request("GET", f"/table/{table_name}", params=search_params)
            search_data = search_response.json()
            
            if not search_data.get('result') or len(search_data['result']) == 0:
                return {
                    "message": f"No {table_name} record found with number: {number}",
                    "updated_count": 0,
                    "records_updated": []
                }
                
            # Update using the found sys_id
            record_sys_id = search_data['result'][0]['sys_id']
            endpoint = f"/table/{table_name}/{record_sys_id}"
            response = self._make_request("PATCH", endpoint, json=data)
            result = response.json().get('result', {})
            return {
                'sys_id': result.get('sys_id'),
                'number': result.get('number'),
                'short_description': result.get('short_description'),
                'state': result.get('state'),
                'message': "Record updated successfully"
            }
            
        elif where:
            # Bulk update using query
            params = {'sysparm_query': where}
            response = self._make_request("PATCH", f"/table/{table_name}", params=params, json=data)
            return {
                'message': f"Bulk update completed",
                'query': where
            }
            
        else:
            raise ValueError("Missing required identifier: No sys_id, number, or where clause was provided to identify records to update.")


class ServiceNowWorkflow(ServiceNowWorkflowTool):
    """Handle ServiceNow workflow operations.
    
    Specialized tool for state transitions, approvals, assignments,
    and other workflow-related actions.
    """
    produces_user_data: bool = False  # Workflow actions don't require user selection
    name: str = "servicenow_workflow"
    description: str = "Handle ServiceNow workflow operations like approvals and state changes"
    
    class Input(BaseModel):
        table_name: str = Field(description="Table containing the record")
        sys_id: str = Field(description="System ID of the record")
        action: str = Field(description="Workflow action (e.g., approve, assign, transition)")
        data: Optional[Dict[str, Any]] = Field(None, description="Additional data for the action")
    
    args_schema: type = Input
    
    @log_execution("servicenow", "workflow_operation", include_args=True, include_result=False)
    def _execute(self, table_name: str, sys_id: str, action: str,
                 data: Optional[Dict[str, Any]] = None) -> Any:
        """Execute the workflow operation."""
        data = data or {}
        
        # Handle different workflow actions
        if action == "approve":
            # Approval logic
            update_data = {
                'approval': 'approved',
                'approved_by': data.get('approved_by', 'system'),
                'approval_history': data.get('comments', 'Approved via API')
            }
            
        elif action == "reject":
            # Rejection logic
            update_data = {
                'approval': 'rejected',
                'approved_by': data.get('approved_by', 'system'),
                'approval_history': data.get('comments', 'Rejected via API')
            }
            
        elif action == "assign":
            # Assignment logic
            if not data.get('assigned_to'):
                raise ValueError("Missing required field for assignment: Assignment action requires an 'assigned_to' field in the data.")
            update_data = {
                'assigned_to': data['assigned_to'],
                'assignment_group': data.get('assignment_group')
            }
            
        elif action == "transition":
            # State transition logic
            if not data.get('state'):
                raise ValueError("Missing required field for transition: State transition requires a 'state' field in the data.")
                
            # Validate state value
            valid_states = self._get_valid_states(table_name)
            state_value = valid_states.get(data['state'], data['state'])
            
            update_data = {
                'state': state_value,
                'work_notes': data.get('work_notes', f"State changed to {data['state']}")
            }
            
        else:
            raise ValueError(f"Unknown workflow action: The workflow action '{action}' is not recognized.")
            
        # Execute the update
        endpoint = f"/table/{table_name}/{sys_id}"
        response = self._make_request("PATCH", endpoint, json=update_data)
        result = response.json().get('result', {})
        
        return {
            'sys_id': result.get('sys_id'),
            'number': result.get('number'),
            'action': action,
            'message': f"Workflow action '{action}' completed successfully"
        }


class ServiceNowAnalytics(ServiceNowAnalyticsTool):
    """Get analytics and metrics from ServiceNow.
    
    Provides aggregations, statistics, and reporting capabilities
    across any ServiceNow table.
    """
    produces_user_data: bool = True  # Analytics results may need user review
    name: str = "servicenow_analytics"
    description: str = "Get analytics, metrics, and statistics from ServiceNow"
    
    class Input(BaseModel):
        table_name: str = Field(description="Table to analyze")
        metric_type: str = Field(description="Type of metric (count, breakdown, trend)")
        group_by: Optional[str] = Field(None, description="Field to group results by")
        conditions: Optional[str] = Field(None, description="Filter conditions")
        time_field: Optional[str] = Field("sys_created_on", description="Field for time-based analysis")
        time_period: Optional[str] = Field(None, description="Time period (e.g., 'last 7 days')")
    
    args_schema: type = Input
    
    @log_execution("servicenow", "analytics", include_args=True, include_result=False)
    def _execute(self, table_name: str, metric_type: str, 
                 group_by: Optional[str] = None, conditions: Optional[str] = None,
                 time_field: str = "sys_created_on", time_period: Optional[str] = None) -> Any:
        """Execute the analytics operation."""
        # Build base query
        query_parts = []
        
        # Add time period filter
        if time_period:
            if "day" in time_period.lower():
                days = 7  # Default
                if "30" in time_period:
                    days = 30
                elif "90" in time_period:
                    days = 90
                query_parts.append(f"{time_field}>javascript:gs.daysAgo({days})")
                
        # Add custom conditions
        if conditions:
            query_parts.append(conditions)
            
        base_query = "^".join(query_parts) if query_parts else ""
        
        if metric_type == "count":
            # Simple count
            params = {
                'sysparm_query': base_query,
                'sysparm_fields': 'sys_id',
                'sysparm_limit': '1'
            }
            params['sysparm_count'] = 'true'
            
            response = self._make_request("GET", f"/table/{table_name}", params=params)
            headers = response.headers
            total_count = headers.get('X-Total-Count', '0')
            
            return {
                'metric_type': 'count',
                'table': table_name,
                'count': int(total_count),
                'conditions': base_query
            }
            
        elif metric_type == "breakdown" and group_by:
            # Group by analysis
            # Build aggregate query
            query_parts = []
            if base_query:
                query_parts.append(base_query)
            query_parts.append(f"GROUPBY{group_by}")
            query_parts.append("COUNT")
            aggregate_query = '^'.join(query_parts)
            
            params = {
                'sysparm_query': aggregate_query,
                'sysparm_count': 'true'
            }
            
            response = self._make_request("GET", f"/stats/{table_name}", params=params)
            data = response.json()
            
            # Format results
            breakdown = {}
            for item in data.get('result', []):
                group_value = item.get('groupby_fields', {}).get(group_by, 'Unknown')
                count = item.get('stats', {}).get('count', 0)
                breakdown[group_value] = count
                
            return {
                'metric_type': 'breakdown',
                'table': table_name,
                'group_by': group_by,
                'breakdown': breakdown,
                'total': sum(breakdown.values())
            }
            
        elif metric_type == "trend":
            # Time-based trend analysis
            # This would typically require multiple queries or specialized APIs
            return {
                'metric_type': 'trend',
                'message': 'Trend analysis requires specialized implementation',
                'table': table_name,
                'time_field': time_field,
                'time_period': time_period
            }
            
        else:
            raise ValueError(f"Unknown metric type: The metric type '{metric_type}' is not supported.")


# Export unified tools
UNIFIED_SERVICENOW_TOOLS = [
    ServiceNowGet(),
    ServiceNowSearch(),
    ServiceNowCreate(),
    ServiceNowUpdate(),
    ServiceNowWorkflow(),
    ServiceNowAnalytics()
]