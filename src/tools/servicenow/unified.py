"""Unified ServiceNow tools for ITSM operations and workflow management."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import requests

from .base import (
    ServiceNowReadTool,
    ServiceNowWriteTool,
    ServiceNowWorkflowTool,
    ServiceNowAnalyticsTool
    )
from src.utils.platform.servicenow import GlideQueryBuilder
from src.utils.logging import get_logger

logger = get_logger("servicenow")


class ServiceNowGet(ServiceNowReadTool):
    """Get any ServiceNow record by sys_id or number.
    
    Simple, direct record retrieval from any table with automatic
    table detection from number prefixes (INC, CHG, PRB, etc).
    """
    name: str = "servicenow_get"
    description: str = "Get a ServiceNow record by ID or number"
    
    class Input(BaseModel):
        table_name: Optional[str] = Field(None, description="Table name (e.g., incident, change_request). Optional if using number.")
        sys_id: Optional[str] = Field(None, description="System ID of the record")
        number: Optional[str] = Field(None, description="Record number (e.g., INC0001234)")
        fields: Optional[List[str]] = Field(None, description="Specific fields to return")
    
    args_schema: type = Input
    
    def _execute(self, **kwargs) -> Any:
        """Execute the get operation."""
        table_name = kwargs.get('table_name', None)
        sys_id = kwargs.get('sys_id', None)
        number = kwargs.get('number', None)
        fields = kwargs.get('fields', None)
        # Validate inputs
        if not sys_id and not number:
            return {
                "error": "Missing required identifier",
                "error_code": "MISSING_IDENTIFIER",
                "guidance": {
                    "reflection": "No sys_id or number was provided to identify the record.",
                    "consider": "What record are you trying to retrieve? Do you have its number or system ID?",
                    "approach": "Provide either the record number (e.g., INC0001234) or the sys_id."
                }
            }
            
        # Auto-detect table from number if not provided
        if not table_name and number:
            table_name = self._detect_table_from_number(number)
            if not table_name:
                return {
                    "error": "Unknown record number format",
                    "error_code": "UNKNOWN_NUMBER_FORMAT",
                    "number": number,
                    "guidance": {
                        "reflection": f"Could not determine the table type from number: {number}",
                        "consider": "What type of record is this? Common prefixes: INC (incident), CHG (change), PRB (problem).",
                        "approach": "Specify the table_name parameter explicitly (e.g., 'incident', 'change_request')."
                    }
                }
        
        if not table_name:
            return {
                "error": "Missing table name",
                "error_code": "MISSING_TABLE_NAME",
                "guidance": {
                    "reflection": "A sys_id was provided but no table name to search in.",
                    "consider": "What type of record does this sys_id belong to?",
                    "approach": "Specify the table_name parameter (e.g., 'incident', 'change_request', 'problem')."
                }
            }
            
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
                return {
                    "error": "Record not found",
                    "error_code": "NOT_FOUND",
                    "number": number,
                    "table": table_name,
                    "guidance": {
                        "reflection": f"No {table_name} record found with number: {number}",
                        "consider": "Is the record number correct? Has it been deleted or archived?",
                        "approach": "Verify the record exists in ServiceNow or try searching with different criteria."
                    }
                }


class ServiceNowSearch(ServiceNowReadTool):
    """Search ServiceNow records with flexible criteria.
    
    Handles both natural language queries and Glide encoded queries.
    The LLM can pass human-friendly searches or precise conditions.
    Supports dot-walking for related fields (e.g., caller_id.name).
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
    
    def _execute(self, **kwargs) -> Any:
        """Execute the search operation with NLQ support."""
        table_name = kwargs['table_name']
        query = kwargs['query']
        fields = kwargs.get('fields', None)
        limit = kwargs.get('limit', 100)
        order_by = kwargs.get('order_by', None)
        order_desc = kwargs.get('order_desc', True)
        
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
                return {
                    "error": "Natural language query not understood",
                    "error_code": "NLQ_INTERPRETATION_FAILED", 
                    "query": query,
                    "guidance": {
                        "reflection": f"ServiceNow couldn't interpret: '{query}'",
                        "consider": f"What specific {table_name} fields and conditions do you need?",
                        "approach": "Try an encoded query like: field=value^field2!=value2"
                    }
                }
        
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
    name: str = "servicenow_create"
    description: str = "Create a new ServiceNow record"
    
    class Input(BaseModel):
        table_name: str = Field(description="Table to create record in")
        data: Dict[str, Any] = Field(description="Field values for the new record")
    
    args_schema: type = Input
    
    def _execute(self, **kwargs) -> Any:
        """Execute the create operation."""
        table_name = kwargs['table_name']
        data = kwargs['data']
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
    
    def _execute(self, **kwargs) -> Any:
        """Execute the update operation following ServiceNow best practices."""
        table_name = kwargs['table_name']
        data = kwargs['data']
        sys_id = kwargs.get('sys_id', None)
        number = kwargs.get('number', None)
        where = kwargs.get('where', None)
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
                    "error": "Record not found",
                    "error_code": "NOT_FOUND",
                    "number": number,
                    "table": table_name,
                    "guidance": {
                        "reflection": f"No {table_name} record found with number: {number}",
                        "consider": "Is the record number correct? Does it exist in this table?",
                        "approach": "Verify the record exists or use sys_id if available."
                    }
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
            return {
                "error": "Missing required identifier",
                "error_code": "MISSING_IDENTIFIER",
                "guidance": {
                    "reflection": "No sys_id, number, or where clause was provided to identify records to update.",
                    "consider": "How do you want to identify the records to update?",
                    "approach": "Provide either sys_id for single record, number for lookup, or where clause for bulk updates."
                }
            }


class ServiceNowWorkflow(ServiceNowWorkflowTool):
    """Handle ServiceNow workflow operations.
    
    Specialized tool for state transitions, approvals, assignments,
    and other workflow-related actions.
    """
    name: str = "servicenow_workflow"
    description: str = "Handle ServiceNow workflow operations like approvals and state changes"
    
    class Input(BaseModel):
        table_name: str = Field(description="Table containing the record")
        sys_id: str = Field(description="System ID of the record")
        action: str = Field(description="Workflow action (e.g., approve, assign, transition)")
        data: Optional[Dict[str, Any]] = Field(None, description="Additional data for the action")
    
    args_schema: type = Input
    
    def _execute(self, **kwargs) -> Any:
        """Execute the workflow operation."""
        table_name = kwargs['table_name']
        sys_id = kwargs['sys_id']
        action = kwargs['action']
        data = kwargs.get('data', None)
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
                return {
                    "error": "Missing required field for assignment",
                    "error_code": "MISSING_REQUIRED_FIELD",
                    "field": "assigned_to",
                    "guidance": {
                        "reflection": "Assignment action requires an 'assigned_to' field in the data.",
                        "consider": "Who should this record be assigned to?",
                        "approach": "Include 'assigned_to' in the data parameter with the user's sys_id or username."
                    }
                }
            update_data = {
                'assigned_to': data['assigned_to'],
                'assignment_group': data.get('assignment_group')
            }
            
        elif action == "transition":
            # State transition logic
            if not data.get('state'):
                return {
                    "error": "Missing required field for transition",
                    "error_code": "MISSING_REQUIRED_FIELD",
                    "field": "state",
                    "guidance": {
                        "reflection": "State transition requires a 'state' field in the data.",
                        "consider": "What state should the record transition to?",
                        "approach": "Include 'state' in the data parameter (e.g., 'in_progress', 'resolved', 'closed')."
                    }
                }
                
            # Validate state value
            valid_states = self._get_valid_states(table_name)
            state_value = valid_states.get(data['state'], data['state'])
            
            update_data = {
                'state': state_value,
                'work_notes': data.get('work_notes', f"State changed to {data['state']}")
            }
            
        else:
            return {
                "error": "Unknown workflow action",
                "error_code": "INVALID_ACTION",
                "action": action,
                "guidance": {
                    "reflection": f"The workflow action '{action}' is not recognized.",
                    "consider": "What workflow operation are you trying to perform?",
                    "approach": "Use one of: 'approve', 'reject', 'assign', or 'transition'."
                }
            }
            
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
    
    def _execute(self, **kwargs) -> Any:
        """Execute the analytics operation."""
        table_name = kwargs['table_name']
        metric_type = kwargs['metric_type']
        group_by = kwargs.get('group_by', None)
        conditions = kwargs.get('conditions', None)
        time_field = kwargs.get('time_field', "sys_created_on")
        time_period = kwargs.get('time_period', None)
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
            # Group by analysis using correct API parameters
            params = {
                'sysparm_count': 'true',
                'sysparm_group_by': group_by
            }
            
            # Add base query if provided
            if base_query:
                params['sysparm_query'] = base_query
            
            # Log the request for debugging
            logger.info("servicenow_analytics_request",
                component="servicenow",
                tool_name=self.name,
                endpoint=f"/stats/{table_name}",
                params=params
            )
            
            response = self._make_request("GET", f"/stats/{table_name}", params=params)
            
            # Handle response - check if it's JSON first
            try:
                data = response.json()
            except requests.exceptions.JSONDecodeError:
                logger.error("servicenow_analytics_non_json_response",
                    component="servicenow",
                    tool_name=self.name,
                    response_text=response.text[:500],
                    content_type=response.headers.get('Content-Type', 'unknown')
                )
                return {
                    "error": "ServiceNow returned non-JSON response",
                    "error_code": "INVALID_RESPONSE",
                    "details": f"Response: {response.text[:200]}...",
                    "guidance": {
                        "reflection": "The stats API returned an unexpected response format.",
                        "consider": "Is the stats API available on this instance? Is the table name correct?",
                        "approach": "Try using the search tool instead for counting records by group."
                    }
                }
            
            # Log the response structure for debugging
            logger.info("servicenow_analytics_response",
                component="servicenow",
                tool_name=self.name,
                response_type=type(data).__name__,
                response_keys=list(data.keys()) if isinstance(data, dict) else "not_dict",
                result_type=type(data.get('result')).__name__ if isinstance(data, dict) else "n/a",
                result_length=len(data.get('result', [])) if isinstance(data.get('result'), list) else "not_list",
                sample_item=data.get('result', [])[0] if isinstance(data.get('result'), list) and data.get('result') else None
            )
            
            # Format results - handle both possible response formats
            breakdown = {}
            
            # Check if result is a list (multiple groups) or dict (single result)
            result = data.get('result', {})
            
            if isinstance(result, list):
                # Multiple groups returned
                for item in result:
                    # Extract group value from groupby_fields list
                    group_value = 'Unknown'
                    groupby_fields = item.get('groupby_fields', [])
                    if isinstance(groupby_fields, list):
                        # Find the field matching our group_by parameter
                        for field in groupby_fields:
                            if isinstance(field, dict) and field.get('field') == group_by:
                                group_value = field.get('value', 'Unknown')
                                break
                    
                    # Extract count from stats
                    stats = item.get('stats', {})
                    count = stats.get('count', 0) if isinstance(stats, dict) else 0
                    
                    # Convert count to int (it might be a string)
                    try:
                        count = int(count) if count else 0
                    except (ValueError, TypeError):
                        count = 0
                    
                    breakdown[str(group_value)] = count
            elif isinstance(result, dict):
                # Single result or different format
                if 'stats' in result:
                    # Simple count result
                    breakdown['Total'] = int(result.get('stats', {}).get('count', 0))
                else:
                    # Try to extract grouped data from other possible structures
                    logger.warning("servicenow_analytics_unexpected_format",
                        component="servicenow",
                        tool_name=self.name,
                        result_structure=str(result)[:200]
                    )
                    breakdown['Unknown'] = 0
            
            # Log the final breakdown for debugging
            logger.info("servicenow_analytics_breakdown",
                component="servicenow",
                tool_name=self.name,
                breakdown_items=len(breakdown),
                breakdown_keys=list(breakdown.keys()),
                breakdown_total=sum(breakdown.values())
            )
            
            # If breakdown is empty, try fallback method using table API
            if not breakdown or (len(breakdown) == 1 and 'Unknown' in breakdown):
                logger.info("servicenow_analytics_fallback",
                    component="servicenow",
                    tool_name=self.name,
                    reason="Stats API returned empty or unknown results, using table API fallback"
                )
                return self._breakdown_using_table_api(table_name, group_by, base_query)
            
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
            return {
                "error": "Unknown metric type",
                "error_code": "INVALID_METRIC_TYPE",
                "metric_type": metric_type,
                "guidance": {
                    "reflection": f"The metric type '{metric_type}' is not supported.",
                    "consider": "What kind of analytics are you looking for?",
                    "approach": "Use one of: 'count' for totals, 'breakdown' for grouping, or 'trend' for time-based analysis."
                }
            }
    
    def _breakdown_using_table_api(self, table_name: str, group_by: str, conditions: Optional[str] = None) -> Dict[str, Any]:
        """Fallback method to calculate breakdown using table API when stats API fails."""
        try:
            # Build query to get all distinct values for the group_by field
            # For this fallback method, we'll just use the encoded query directly
            
            # We need to get all records and group them manually
            # Limit to 1000 records for performance
            params = {
                'sysparm_query': conditions or '',
                'sysparm_fields': f'{group_by},sys_id',
                'sysparm_limit': '1000',
                'sysparm_display_value': 'all'
            }
            
            response = self._make_request("GET", f"/table/{table_name}", params=params)
            data = response.json()
            records = data.get('result', [])
            
            # Count occurrences of each group value
            breakdown: Dict[str, int] = {}
            for record in records:
                # Handle both display value and raw value
                if isinstance(record.get(group_by), dict):
                    # Reference field with display_value
                    group_value = record[group_by].get('display_value', record[group_by].get('value', 'Unknown'))
                else:
                    # Regular field
                    group_value = str(record.get(group_by, 'Unknown'))
                
                # Convert empty values to meaningful labels
                if not group_value or group_value == 'None':
                    group_value = 'Not Set'
                
                breakdown[group_value] = breakdown.get(group_value, 0) + 1
            
            logger.info("servicenow_analytics_table_api_success",
                component="servicenow",
                tool_name=self.name,
                groups_found=len(breakdown),
                total_records=len(records)
            )
            
            return {
                'metric_type': 'breakdown',
                'table': table_name,
                'group_by': group_by,
                'breakdown': breakdown,
                'total': sum(breakdown.values()),
                'note': 'Results limited to 1000 records using table API fallback'
            }
            
        except Exception as e:
            logger.error("servicenow_analytics_table_api_failed",
                component="servicenow",
                tool_name=self.name,
                error=str(e)
            )
            return self._handle_error(e)


# Export unified tools
UNIFIED_SERVICENOW_TOOLS = [
    ServiceNowGet(),
    ServiceNowSearch(),
    ServiceNowCreate(),
    ServiceNowUpdate(),
    ServiceNowWorkflow(),
    ServiceNowAnalytics()
]