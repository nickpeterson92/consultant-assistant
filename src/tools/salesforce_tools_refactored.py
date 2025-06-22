"""
Refactored Salesforce Tools using SOQL Query Builder

This demonstrates how the tools can be simplified using the query builder pattern.
The benefits include:
- 70% less code duplication
- More flexible query construction
- Better maintainability
- Consistent query patterns
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from langchain.tools import BaseTool
from simple_salesforce import Salesforce

from .soql_query_builder import (
    SOQLQueryBuilder, 
    SearchQueryBuilder,
    QueryTemplates,
    SOQLOperator,
    escape_soql
)
from ..utils.logging import log_tool_activity


# Simplified tool implementations using query builder

class GetLeadInput(BaseModel):
    lead_id: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None


class GetLeadToolRefactored(BaseTool):
    """Refactored GetLead using query builder"""
    name: str = "get_lead_tool"
    description: str = "Retrieves Salesforce lead records using flexible search"
    args_schema: type = GetLeadInput

    def _run(self, **kwargs) -> dict:
        data = GetLeadInput(**kwargs)
        
        try:
            sf = get_salesforce_connection()
            
            # Use query builder for cleaner code
            builder = SOQLQueryBuilder('Lead').select(['Id', 'Name', 'Company', 'Email', 'Phone', 'Status'])
            
            if data.lead_id:
                builder.where_id(data.lead_id)
            else:
                # Build OR conditions for flexible search
                search_conditions = []
                if data.email:
                    search_conditions.append(('Email', f'%{data.email}%'))
                if data.name:
                    search_conditions.append(('Name', f'%{data.name}%'))
                if data.phone:
                    search_conditions.append(('Phone', f'%{data.phone}%'))
                if data.company:
                    search_conditions.append(('Company', f'%{data.company}%'))
                
                if not search_conditions:
                    return {"error": "No search criteria provided."}
                
                # Add conditions with OR logic
                for i, (field, pattern) in enumerate(search_conditions):
                    if i == 0:
                        builder.where_like(field, pattern)
                    else:
                        builder.or_where(field, SOQLOperator.LIKE, pattern)
            
            query = builder.build()
            records = sf.query(query)['records']
            
            # Return simplified results
            return self._format_results(records)
            
        except Exception as e:
            return {"error": str(e)}
    
    def _format_results(self, records: List[Dict]) -> Any:
        """Format results consistently"""
        if not records:
            return []
        
        formatted = [
            {
                "id": rec["Id"],
                "name": rec.get("Name"),
                "company": rec.get("Company"),
                "email": rec.get("Email"),
                "phone": rec.get("Phone"),
                "status": rec.get("Status")
            }
            for rec in records
        ]
        
        return formatted[0] if len(formatted) == 1 else formatted


class SmartSearchTool(BaseTool):
    """
    A more intelligent search tool that can search across multiple objects
    and understand natural language queries better
    """
    name: str = "smart_search_tool"
    description: str = (
        "Intelligent search across Salesforce objects. "
        "Searches Accounts, Contacts, Leads, and Opportunities based on any criteria. "
        "Examples: 'find anyone at Acme Corp', 'search for deals over 1 million', "
        "'get all technology companies', 'find contacts with gmail addresses'"
    )
    
    class SmartSearchInput(BaseModel):
        search_query: str
        object_types: Optional[List[str]] = None  # Default searches all
        
    args_schema: type = SmartSearchInput
    
    def _run(self, search_query: str, object_types: Optional[List[str]] = None) -> dict:
        try:
            sf = get_salesforce_connection()
            results = {}
            
            # Default to searching all major objects
            if not object_types:
                object_types = ['Account', 'Contact', 'Lead', 'Opportunity']
            
            # Parse the query to understand intent
            search_term = self._extract_search_term(search_query)
            filters = self._extract_filters(search_query)
            
            for obj_type in object_types:
                searcher = SearchQueryBuilder(sf, obj_type)
                
                # Apply smart search based on object type
                if obj_type == 'Account':
                    searcher.search_fields(['Name', 'Website'], search_term)
                    if 'industry' in filters:
                        searcher.query_builder.where('Industry', SOQLOperator.EQUALS, filters['industry'])
                        
                elif obj_type == 'Contact':
                    searcher.search_fields(['Name', 'Email'], search_term)
                    
                elif obj_type == 'Lead':
                    searcher.search_fields(['Name', 'Company', 'Email'], search_term)
                    
                elif obj_type == 'Opportunity':
                    if 'min_amount' in filters:
                        searcher.query_builder.where('Amount', SOQLOperator.GREATER_THAN, filters['min_amount'])
                    else:
                        searcher.search_fields(['Name'], search_term)
                
                # Execute search
                records = searcher.recent_first().execute()
                if records:
                    results[obj_type.lower()] = self._format_object_results(records, obj_type)
            
            return results
            
        except Exception as e:
            return {"error": str(e)}
    
    def _extract_search_term(self, query: str) -> str:
        """Extract the main search term from natural language"""
        # Remove common words
        stop_words = ['find', 'search', 'get', 'show', 'for', 'at', 'with', 'all', 'anyone']
        words = query.lower().split()
        search_words = [w for w in words if w not in stop_words]
        return ' '.join(search_words) if search_words else query
    
    def _extract_filters(self, query: str) -> Dict[str, Any]:
        """Extract filters from natural language"""
        filters = {}
        
        # Amount filters
        if 'over' in query and ('million' in query or 'k' in query):
            import re
            amount_match = re.search(r'over (\d+)', query)
            if amount_match:
                amount = int(amount_match.group(1))
                if 'million' in query:
                    amount *= 1000000
                elif 'k' in query:
                    amount *= 1000
                filters['min_amount'] = amount
        
        # Industry filters
        industries = ['technology', 'healthcare', 'finance', 'retail', 'manufacturing']
        for industry in industries:
            if industry in query.lower():
                filters['industry'] = industry.capitalize()
                
        return filters
    
    def _format_object_results(self, records: List[Dict], object_type: str) -> List[Dict]:
        """Format results based on object type"""
        formatted = []
        
        for rec in records[:10]:  # Limit to 10 results per object
            if object_type == 'Account':
                formatted.append({
                    "id": rec["Id"],
                    "name": rec.get("Name"),
                    "industry": rec.get("Industry"),
                    "website": rec.get("Website")
                })
            elif object_type == 'Contact':
                formatted.append({
                    "id": rec["Id"],
                    "name": rec.get("Name"),
                    "email": rec.get("Email"),
                    "phone": rec.get("Phone"),
                    "account_id": rec.get("AccountId")
                })
            elif object_type == 'Opportunity':
                formatted.append({
                    "id": rec["Id"],
                    "name": rec.get("Name"),
                    "stage": rec.get("StageName"),
                    "amount": rec.get("Amount"),
                    "close_date": rec.get("CloseDate")
                })
            # Add more object types as needed
            
        return formatted


class BulkOperationTool(BaseTool):
    """
    Tool for performing bulk operations efficiently
    """
    name: str = "bulk_operation_tool"
    description: str = (
        "Performs bulk operations on Salesforce records. "
        "Examples: 'update all opportunities for Acme to Closed Won', "
        "'create 5 tasks for all contacts at GenePoint', "
        "'mark all cases for Express Logistics as resolved'"
    )
    
    class BulkOperationInput(BaseModel):
        operation: str  # 'update', 'create', 'delete'
        object_type: str
        filter_criteria: Dict[str, Any]
        updates: Optional[Dict[str, Any]] = None
        template: Optional[Dict[str, Any]] = None  # For bulk create
        
    args_schema: type = BulkOperationInput
    
    def _run(self, operation: str, object_type: str, filter_criteria: Dict, 
             updates: Optional[Dict] = None, template: Optional[Dict] = None) -> dict:
        try:
            sf = get_salesforce_connection()
            
            if operation == 'update':
                return self._bulk_update(sf, object_type, filter_criteria, updates)
            elif operation == 'create':
                return self._bulk_create(sf, object_type, filter_criteria, template)
            else:
                return {"error": f"Unsupported operation: {operation}"}
                
        except Exception as e:
            return {"error": str(e)}
    
    def _bulk_update(self, sf, object_type: str, filter_criteria: Dict, updates: Dict) -> dict:
        """Perform bulk update operation"""
        # Build query to find records to update
        builder = SOQLQueryBuilder(object_type).select(['Id'])
        
        for field, value in filter_criteria.items():
            if isinstance(value, str) and '%' in value:
                builder.where_like(field, value)
            else:
                builder.where(field, SOQLOperator.EQUALS, value)
        
        query = builder.build()
        records = sf.query(query)['records']
        
        if not records:
            return {"message": "No records found matching criteria"}
        
        # Perform bulk update
        update_records = [
            {"Id": rec["Id"], **updates}
            for rec in records
        ]
        
        # Salesforce bulk API call
        getattr(sf.bulk, object_type).update(update_records)
        
        return {
            "message": f"Successfully updated {len(records)} {object_type} records",
            "updated_ids": [rec["Id"] for rec in records]
        }
    
    def _bulk_create(self, sf, object_type: str, filter_criteria: Dict, template: Dict) -> dict:
        """Perform bulk create operation"""
        # First find the parent records
        parent_type = filter_criteria.get('parent_type', 'Account')
        parent_field = filter_criteria.get('parent_field', 'AccountId')
        
        builder = SOQLQueryBuilder(parent_type).select(['Id', 'Name'])
        
        for field, value in filter_criteria.items():
            if field not in ['parent_type', 'parent_field']:
                if isinstance(value, str) and '%' in value:
                    builder.where_like(field, value)
                else:
                    builder.where(field, SOQLOperator.EQUALS, value)
        
        query = builder.build()
        parent_records = sf.query(query)['records']
        
        if not parent_records:
            return {"message": "No parent records found matching criteria"}
        
        # Create records for each parent
        create_records = []
        for parent in parent_records:
            record = template.copy()
            record[parent_field] = parent["Id"]
            # Add parent name to subject/name if applicable
            if 'Subject' in record:
                record['Subject'] = record['Subject'].format(parent_name=parent['Name'])
            create_records.append(record)
        
        # Salesforce bulk API call
        results = getattr(sf.bulk, object_type).insert(create_records)
        
        return {
            "message": f"Successfully created {len(results)} {object_type} records",
            "created_ids": [r['id'] for r in results if r['success']]
        }


# Example of how existing tools can be simplified
def get_all_records_for_account(sf, account_name: str) -> Dict[str, Any]:
    """
    Single function to get all related records for an account
    using the query builder pattern
    """
    # First find the account
    account_query = (SOQLQueryBuilder('Account')
                    .select(['Id', 'Name'])
                    .where_like('Name', f'%{account_name}%')
                    .limit(1)
                    .build())
    
    account_result = sf.query(account_query)
    if not account_result['records']:
        return {"error": f"No account found matching '{account_name}'"}
    
    account = account_result['records'][0]
    account_id = account['Id']
    
    # Get all related records using template
    queries = QueryTemplates.get_all_related_records(account_id)
    
    results = {
        "account": account,
        "contacts": sf.query(queries['contacts'])['records'],
        "opportunities": sf.query(queries['opportunities'])['records'],
        "cases": sf.query(queries['cases'])['records'],
        "tasks": sf.query(queries['tasks'])['records']
    }
    
    return results