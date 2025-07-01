"""Unified Salesforce tools for CRUD operations and analytics."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from .base import (
    SalesforceReadTool,
    SalesforceWriteTool,
    SalesforceAnalyticsTool,
    logger
)
from src.utils.platform.salesforce import (
    SOQLQueryBuilder,
    SOQLOperator
    )


class SalesforceGet(SalesforceReadTool):
    """Get any Salesforce record by ID."""
    name: str = "salesforce_get"
    description: str = "Retrieve a single record when you have its ID (15 or 18 character identifier)"
    
    class Input(BaseModel):
        record_id: str = Field(description="Salesforce record ID (15 or 18 character)")
        object_type: Optional[str] = Field(None, description="Object type (auto-detected if not provided)")
        fields: Optional[List[str]] = Field(None, description="Specific fields to retrieve")
    
    args_schema: type = Input  # pyright: ignore[reportIncompatibleVariableOverride]
    
    def _execute(self, **kwargs) -> Any:
        """Execute the get operation."""
        record_id = kwargs['record_id']
        object_type = kwargs.get('object_type', None)
        fields = kwargs.get('fields', None)
        # Auto-detect object type from ID prefix if not provided
        if not object_type:
            id_prefixes = {
                '001': 'Account',
                '003': 'Contact',
                '00Q': 'Lead',
                '006': 'Opportunity',
                '500': 'Case',
                '00T': 'Task'
            }
            prefix = record_id[:3]
            object_type = id_prefixes.get(prefix)
            
            if not object_type:
                return {"success": False, "error": f"Cannot determine object type from ID prefix '{prefix}'"}
        
        # Get the record
        fields_to_query = self._build_field_list(object_type, fields)
        
        # Use the Salesforce REST API for single record retrieval
        try:
            sobject = getattr(self.sf, object_type)
            result = sobject.get(record_id)
            
            # Filter to requested fields if specified
            if fields:
                result = {k: v for k, v in result.items() if k in fields or k == 'attributes'}
            
            return result
        except Exception as e:
            if "NOT_FOUND" in str(e):
                return {"success": False, "error": f"No {object_type} found with ID {record_id}"}
            raise


class SalesforceSearch(SalesforceReadTool):
    """Search any Salesforce object with natural language or structured queries."""
    name: str = "salesforce_search"
    description: str = "LIST individual records with details - use when you need the actual records, not summaries (e.g., list all opportunities, show contacts)"
    
    class Input(BaseModel):
        object_type: str = Field(description="Object to search (Account, Contact, Lead, etc.)")
        filter: str = Field(description="Natural language or WHERE clause condition")
        fields: Optional[List[str]] = Field(None, description="Fields to return")
        limit: int = Field(50, description="Maximum records to return")
        order_by: Optional[str] = Field(None, description="Field to sort by")
    
    args_schema: type = Input  # pyright: ignore[reportIncompatibleVariableOverride]
    
    def _execute(self, **kwargs) -> Any:
        """Execute the search operation."""
        object_type = kwargs['object_type']
        filter = kwargs['filter']
        fields = kwargs.get('fields', None)
        limit = kwargs.get('limit', 50)
        order_by = kwargs.get('order_by', None)
        # Ensure filter is a string - Pydantic validates the type but LangChain
        # may still pass non-string values in some edge cases
        if not isinstance(filter, str):
            filter = str(filter) if filter else ""
            
        # Validate filter doesn't contain non-filterable fields
        validation_error = self._validate_filter_fields(object_type, filter)
        if validation_error:
            return {"success": False, "error": validation_error}
        
        # Build field list
        fields_to_query = self._build_field_list(object_type, fields)
        
        # Start with base query
        builder = SOQLQueryBuilder().from_object(object_type).select(*fields_to_query)
        
        # Check if filter looks like a structured condition (contains =, >, <, etc.)
        if any(op in filter for op in ['=', '>', '<', '!=', ' LIKE ', ' IN ']):
            # Direct SOQL condition - trust the LLM
            builder.where_raw(filter)
        else:
            # Natural language - parse it
            builder = self._parse_natural_language_query(filter, object_type)
            builder.select(*fields_to_query)
            
            # Also add text search on name fields
            if filter and not any(keyword in filter.lower() for keyword in ['today', 'yesterday', 'week', 'month']):
                name_field = 'Name' if object_type != 'Case' else 'Subject'
                builder.where(name_field, SOQLOperator.LIKE, f'%{filter}%')  # type: ignore[arg-type]
        
        # Add ordering
        if order_by:
            # Parse order_by string to separate field and direction
            parts = order_by.split()
            if len(parts) == 2 and parts[1].upper() in ['ASC', 'DESC']:
                builder.order_by(parts[0], parts[1].upper())
            else:
                builder.order_by(order_by)  # Just field name, use default ASC
        else:
            # Default ordering by most relevant field
            default_order = {
                'Opportunity': 'Amount DESC',
                'Case': 'CreatedDate DESC',
                'Task': 'ActivityDate ASC'
            }
            if object_type in default_order:
                field, direction = default_order[object_type].split()
                builder.order_by(field, direction)
        
        # Add limit
        builder.limit(limit)
        
        # Execute query
        soql = builder.build()
        logger.info("soql_query",
            component="salesforce",
            tool_name=self.name,
            operation="query_built",
            query=soql,
            query_length=len(soql)
        )
        
        result = self.sf.query(soql)
        return result.get('records', [])


class SalesforceCreate(SalesforceWriteTool):
    """Create any type of Salesforce record."""
    name: str = "salesforce_create"
    description: str = "Add a new record to Salesforce (lead, contact, opportunity, case, etc.)"
    
    class Input(BaseModel):
        object_type: str = Field(description="Type of object to create")
        data: Dict[str, Any] = Field(description="Field values for the new record")
    
    args_schema: type = Input  # pyright: ignore[reportIncompatibleVariableOverride]
    
    def _execute(self, **kwargs) -> Any:
        """Execute the create operation."""
        object_type = kwargs['object_type']
        data = kwargs['data']
        # Validate required fields
        validation_error = self._validate_required_fields(object_type, data)
        if validation_error:
            return {"success": False, "error": validation_error}
        
        # Prepare data
        prepared_data = self._prepare_data(data)
        
        # Create the record
        sobject = getattr(self.sf, object_type)
        result = sobject.create(prepared_data)
        
        if result.get('success'):
            # Fetch the created record to return full details using REST API
            created_id = result['id']
            sobject = getattr(self.sf, object_type)
            return sobject.get(created_id)
        else:
            errors = result.get('errors', [])
            error_msg = errors[0].get('message', 'Unknown error') if errors else 'Creation failed'
            return {"success": False, "error": f"Failed to create {object_type}: {error_msg}"}


class SalesforceUpdate(SalesforceWriteTool):
    """Update any Salesforce record."""
    name: str = "salesforce_update"
    description: str = "Modify existing records - change field values, update status, etc."
    
    class Input(BaseModel):
        object_type: str = Field(description="Type of object to update")
        record_id: Optional[str] = Field(None, description="ID of record to update")
        where: Optional[str] = Field(None, description="Condition to find records to update")
        data: Dict[str, Any] = Field(description="Fields to update")
    
    args_schema: type = Input  # pyright: ignore[reportIncompatibleVariableOverride]
    
    def _execute(self, **kwargs) -> Any:
        """Execute the update operation."""
        object_type = kwargs['object_type']
        data = kwargs['data']
        record_id = kwargs.get('record_id', None)
        where = kwargs.get('where', None)
        if not record_id and not where:
            return {"success": False, "error": "Must provide either record_id or where condition"}
        
        # Prepare update data
        prepared_data = self._prepare_data(data)
        
        if record_id:
            # Direct update by ID
            sobject = getattr(self.sf, object_type)
            result = sobject.update(record_id, prepared_data)
            
            if result == 204:  # Success response code
                # Fetch updated record using REST API instead of SOQL
                sobject = getattr(self.sf, object_type)
                updated_record = sobject.get(record_id)
                return updated_record
            else:
                return {"success": False, "error": f"Failed to update {object_type} {record_id}"}
        else:
            # Find records to update using query builder
            if where:
                query = SOQLQueryBuilder().from_object(object_type).select('Id').where_raw(where).build()
                records = self.sf.query(query)['records']
            else:
                return {"success": False, "error": "where condition cannot be None when record_id is not provided"}
            
            if not records:
                return {"success": False, "error": f"No {object_type} records found matching: {where}"}
            
            # Update each record
            updated = []
            for record in records:
                sobject = getattr(self.sf, object_type)
                result = sobject.update(record['Id'], prepared_data)
                if result == 204:
                    updated.append(record['Id'])
            
            return {
                "updated_count": len(updated),
                "updated_ids": updated,
                "message": f"Updated {len(updated)} {object_type} record(s)"
            }


class SalesforceSOSL(SalesforceReadTool):
    """Cross-object search using Salesforce Object Search Language (SOSL)."""
    name: str = "salesforce_sosl"
    description: str = "Search across MULTIPLE object types simultaneously - use ONLY when you don't know which object contains the data"
    
    class Input(BaseModel):
        search_term: str = Field(description="Text to search for across objects")
        object_types: Optional[List[str]] = Field(
            default=['Account', 'Contact', 'Lead', 'Opportunity', 'Case'],
            description="Objects to search in"
        )
        fields_per_object: Optional[Dict[str, List[str]]] = Field(
            None,
            description="Specific fields to return per object type"
        )
        limit_per_object: int = Field(20, description="Max results per object type")
    
    args_schema: type = Input  # pyright: ignore[reportIncompatibleVariableOverride]
    
    def _execute(self, **kwargs) -> Any:
        """Execute cross-object search."""
        search_term = kwargs['search_term']
        object_types = kwargs.get('object_types', None)
        fields_per_object = kwargs.get('fields_per_object', None)
        limit_per_object = kwargs.get('limit_per_object', 20)
        # Default object types if not specified
        if not object_types:
            object_types = ['Account', 'Contact', 'Lead', 'Opportunity', 'Case']
        
        # Build SOSL query
        # SOSL requires curly braces around search terms, not quotes
        sosl_parts = [f"FIND {{{search_term}}} IN ALL FIELDS"]
        
        # Configure return fields for each object
        returning_parts = []
        for obj_type in object_types:
            # Use provided fields or defaults
            if fields_per_object and obj_type in fields_per_object:
                fields = fields_per_object[obj_type]
            else:
                fields = self._build_field_list(obj_type)
            
            fields_str = ', '.join(fields)
            returning_parts.append(f"{obj_type}({fields_str} LIMIT {limit_per_object})")
        
        sosl_parts.append(f"RETURNING {', '.join(returning_parts)}")
        
        # Execute search
        sosl = ' '.join(sosl_parts)
        logger.info("sosl_query",
            component="salesforce",
            tool_name=self.name,
            operation="query_built",
            query=sosl
        )
        
        results = self.sf.search(sosl)
        
        # Format results by object type
        formatted_results = {
            "search_term": search_term,
            "total_results": 0,
            "results_by_type": {}
        }
        
        for record in results.get('searchRecords', []):
            obj_type = record['attributes']['type']
            if obj_type not in formatted_results['results_by_type']:
                formatted_results['results_by_type'][obj_type] = []
            
            formatted_results['results_by_type'][obj_type].append(record)
            formatted_results['total_results'] += 1
        
        return formatted_results


class SalesforceAnalytics(SalesforceAnalyticsTool):
    """Perform analytics and aggregations on Salesforce data."""
    name: str = "salesforce_analytics"
    description: str = "CALCULATE aggregated numbers and statistics - use ONLY for totals, averages, counts, insights (NOT for listing records)"
    
    class Input(BaseModel):
        object_type: str = Field(description="Object to analyze")
        metrics: List[str] = Field(
            description="Metrics to calculate (COUNT, SUM(Amount), AVG(Amount), etc.)"
        )
        group_by: Optional[str] = Field(None, description="Field to group results by")
        where: Optional[str] = Field(None, description="Filter conditions")
        time_period: Optional[str] = Field(
            default=None,
            description="Time period filter (THIS_MONTH, LAST_MONTH, THIS_YEAR, etc.) - leave empty if not filtering by time"
        )
    
    args_schema: type = Input  # pyright: ignore[reportIncompatibleVariableOverride]
    
    def _execute(self, **kwargs) -> Any:
        """Execute analytics query."""
        object_type = kwargs['object_type']
        metrics = kwargs['metrics']
        group_by = kwargs.get('group_by', None)
        where = kwargs.get('where', None)
        time_period = kwargs.get('time_period', None)
        # Ensure time_period is None or string - LangChain may pass boolean values
        if time_period is not None and not isinstance(time_period, str):
            time_period = None
            
        builder = SOQLQueryBuilder().from_object(object_type)
        
        # Add metrics
        for metric in metrics:
            metric_upper = metric.upper()
            if 'COUNT' in metric_upper:
                if '(' in metric:
                    # Extract field name from COUNT(field)
                    field = metric.split('(')[1].rstrip(')')
                    builder.select_count(field, f'count_{field.lower()}')
                else:
                    builder.select_count('Id', 'record_count')
            elif 'SUM' in metric_upper:
                field = metric.split('(')[1].rstrip(')')
                builder.select_sum(field, f'total_{field.lower()}')
            elif 'AVG' in metric_upper:
                field = metric.split('(')[1].rstrip(')')
                builder.select_avg(field, f'avg_{field.lower()}')
            elif 'MAX' in metric_upper:
                field = metric.split('(')[1].rstrip(')')
                builder.select_max(field, f'max_{field.lower()}')
            elif 'MIN' in metric_upper:
                field = metric.split('(')[1].rstrip(')')
                builder.select_min(field, f'min_{field.lower()}')
        
        # Add grouping
        if group_by:
            builder.select(group_by)
            builder.group_by(group_by)
        
        # Build WHERE clause combining user filter and time period
        where_clauses = []
        
        if where:
            where_clauses.append(where)
        
        # Add time period filter
        if time_period and time_period.upper() != 'ALL_TIME':
            # Determine appropriate date field
            date_field = 'CreatedDate'
            if object_type == 'Opportunity':
                date_field = 'CloseDate'
            elif object_type == 'Task':
                date_field = 'ActivityDate'
            
            # For standard SOQL date literals, use without quotes
            if time_period.upper() in ['THIS_MONTH', 'LAST_MONTH', 'THIS_YEAR', 
                                       'LAST_YEAR', 'THIS_QUARTER', 'LAST_QUARTER',
                                       'THIS_WEEK', 'LAST_WEEK', 'TODAY', 'YESTERDAY',
                                       'LAST_90_DAYS', 'LAST_N_DAYS:X', 'NEXT_N_DAYS:X',
                                       'LAST_12_MONTHS', 'THIS_FISCAL_YEAR', 'LAST_FISCAL_YEAR']:
                where_clauses.append(f"{date_field} = {time_period}")
            else:
                # For specific dates, use with quotes
                where_clauses.append(f"{date_field} = '{time_period}'")
        
        # Apply combined WHERE clause
        if where_clauses:
            builder.where_raw(' AND '.join(where_clauses))
        
        # Execute query
        soql = builder.build()
        logger.info("soql_analytics_query",
            component="salesforce",
            tool_name=self.name,
            operation="query_built",
            query=soql
        )
        
        result = self.sf.query(soql)
        records = result.get('records', [])
        
        # Format results
        if not records:
            return {"message": "No data found for the specified criteria"}
        
        # Add summary if no grouping
        if not group_by and len(records) == 1:
            return {
                "metrics": records[0],
                "object_type": object_type,
                "filters_applied": {
                    "where": where,
                    "time_period": time_period
                }
            }
        
        return {
            "results": records,
            "object_type": object_type,
            "grouped_by": group_by,
            "record_count": len(records),
            "filters_applied": {
                "where": where,
                "time_period": time_period
            }
        }


# Export the new unified tools
UNIFIED_SALESFORCE_TOOLS = [
    SalesforceGet(),
    SalesforceSearch(),
    SalesforceCreate(),
    SalesforceUpdate(),
    SalesforceSOSL(),
    SalesforceAnalytics()
]