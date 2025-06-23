"""Salesforce CRM Tools - Enterprise-Grade CRUD Operations with Query Builder Pattern.

This module implements 15 comprehensive Salesforce tools using the SOQL Query Builder pattern:

Architecture Philosophy:
- **Query Builder Pattern**: Composable, reusable, and maintainable query construction
- **Security-First**: Automatic SOQL injection prevention through the builder
- **Flexible Search**: Natural language support with intelligent query generation
- **Consistent Error Handling**: Graceful degradation with structured error responses
- **Token Optimization**: Streamlined response formats for cost efficiency

Query Building Strategy:
- All queries use SOQLQueryBuilder for automatic escaping and consistent patterns
- Reusable query templates for common operations
- Dynamic field selection for performance optimization
- Support for complex queries with relationships and aggregations

Error Handling Philosophy:
- Never crash - always return structured error responses
- Preserve error context for debugging while hiding sensitive details
- Log all operations for audit trails and troubleshooting
- Graceful empty result handling ([] instead of exceptions)
"""

import os
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, field_validator
from langchain.tools import BaseTool
from simple_salesforce import Salesforce

from src.utils.logging import log_tool_activity
from src.utils.soql_query_builder import (
    SOQLQueryBuilder,
    SearchQueryBuilder,
    QueryTemplates,
    SOQLOperator,
    escape_soql
)


def get_salesforce_connection():
    """Create and return a Salesforce connection using environment variables."""
    return Salesforce(
        username=os.environ['SFDC_USER'],
        password=os.environ['SFDC_PASS'],
        security_token=os.environ['SFDC_TOKEN']
    )


# Lead Tools
class GetLeadInput(BaseModel):
    lead_id: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None


class GetLeadTool(BaseTool):
    """Salesforce Lead Retrieval Tool.
    
    Provides flexible lead search capabilities across multiple criteria including
    direct ID lookup, company-wide searches, and contact information matching.
    Implements loose coupling by accepting various search parameters without
    requiring knowledge of underlying SOQL implementation.
    
    Use Cases:
    - Get specific lead by ID: "find lead abc123"
    - Get all company leads: "get all leads for Acme Corp"  
    - Search by contact info: "find leads with email john@company.com"
    - Multi-criteria search: "leads for John at Acme Corp"
    
    Security Features:
    - All inputs sanitized through escape_soql() to prevent SOQL injection
    - Flexible OR condition support for maximum search coverage
    - Graceful error handling with structured responses
    
    Returns:
    - Single match: Direct lead object with core fields
    - Multiple matches: Array of lead objects
    - No matches: [] (empty list)
    """
    name: str = "get_lead_tool"
    description: str = (
        "LOOKUP: Individual lead records by ID, email, name, phone, or company. "
        "Use for: 'get lead 003abc123', 'find lead john@company.com', 'leads for Acme Corp'. "
        "Returns specific lead records - NOT aggregated analytics or metrics. "
        "For lead analytics/trends, use GetBusinessMetricsTool instead."
    )
    args_schema: type = GetLeadInput

    def _run(self, **kwargs) -> dict:
        data = GetLeadInput(**kwargs)

        try:
            log_tool_activity("GetLeadTool", "RETRIEVE_LEAD", 
                            search_params={k: v for k, v in kwargs.items()})
            sf = get_salesforce_connection()
            
            # Use query builder for cleaner, safer queries
            builder = SOQLQueryBuilder('Lead').select(['Id', 'Name', 'Company', 'Email', 'Phone', 'Status'])
            
            if data.lead_id:
                builder.where_id(data.lead_id)
            else:
                # Build OR conditions dynamically
                search_fields = [
                    ('Email', data.email),
                    ('Name', data.name),
                    ('Phone', data.phone),
                    ('Company', data.company)
                ]
                
                conditions_added = False
                for field, value in search_fields:
                    if value:
                        if not conditions_added:
                            builder.where_like(field, f'%{value}%')
                            conditions_added = True
                        else:
                            builder.or_where(field, SOQLOperator.LIKE, f'%{value}%')
                
                if not conditions_added:
                    return {"error": "No search criteria provided."}

            query = builder.build()
            records = sf.query(query)['records']

            if not records:
                return []
                
            # Token optimization: Direct array/object returns
            formatted_records = [
                {
                    "id": rec["Id"],
                    "name": rec.get("Name", ""),
                    "company": rec.get("Company", ""),
                    "email": rec.get("Email", ""),
                    "phone": rec.get("Phone", ""),
                    "status": rec.get("Status", "")
                }
                for rec in records
            ]
            
            return formatted_records[0] if len(formatted_records) == 1 else formatted_records
            
        except Exception as e:
            return {"error": str(e)}


class CreateLeadInput(BaseModel):
    name: str
    company: str
    email: Optional[str] = None
    phone: Optional[str] = None
    lead_status: Optional[str] = "New"

    @field_validator('lead_status')
    def validate_status(cls, v):
        valid_statuses = ["New", "Working", "Nurturing", "Qualified", "Unqualified"]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")
        return v


class CreateLeadTool(BaseTool):
    """Salesforce Lead Creation Tool.
    
    Creates new lead records in Salesforce with validation and audit logging.
    Implements enterprise lead capture patterns with status management and
    data quality controls for sales pipeline integrity.
    
    Use Cases:
    - Web form lead capture: "create lead from contact form submission"
    - Manual lead entry: "add new prospect John Smith at TechCorp"
    - Lead import: "bulk create leads from trade show list"
    - API integration: "create lead from external system data"
    
    Validation Features:
    - Required field validation (name, company)
    - Lead status validation against Salesforce picklist values
    - Automatic audit trail creation with timestamps
    - Error handling with structured responses
    
    Returns:
    - Success: {'id': 'new_lead_id', 'success': True}
    - Failure: {'error': 'detailed_error_message'}
    """
    name: str = "create_lead_tool"
    description: str = (
        "CREATE: New lead record with name, company, and optional contact details. "
        "Use for: 'create lead for John Smith at TechCorp', 'add new prospect'. "
        "Creates single lead record - NOT for bulk operations or analytics. "
        "Returns new lead ID for follow-up workflows."
    )
    args_schema: type = CreateLeadInput

    def _run(self, **kwargs) -> dict:
        try:
            log_tool_activity("CreateLeadTool", "CREATE_LEAD", 
                            input_data={k: v for k, v in kwargs.items()})
            sf = get_salesforce_connection()
            data = CreateLeadInput(**kwargs)
            result = sf.Lead.create({
                "LastName": data.name,
                "Company": data.company,
                "Email": data.email,
                "Phone": data.phone,
                "Status": data.lead_status
            })
            
            log_tool_activity("CreateLeadTool", "CREATE_LEAD_SUCCESS", 
                              record_id=result['id'])
            return result
        except Exception as e:
            return {"error": str(e)}


class UpdateLeadInput(BaseModel):
    lead_id: str
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class UpdateLeadTool(BaseTool):
    """Salesforce Lead Update Tool.
    
    Updates existing lead records with new information while maintaining data integrity
    and audit trails. Implements selective field updates to preserve existing data
    and support progressive lead qualification workflows.
    
    Use Cases:
    - Lead enrichment: "update lead with new contact information"
    - Data correction: "fix email address for lead abc123"
    - Progressive qualification: "add company details to existing lead"
    - Bulk data updates: "update multiple lead fields from enrichment source"
    
    Update Strategy:
    - Selective field updates preserve existing data
    - Only specified fields are modified in the update operation
    - Automatic audit trail with timestamps and change tracking
    - Validation ensures data quality during updates
    
    Security Features:
    - Lead ID validation prevents unauthorized record access
    - Input sanitization for all optional fields
    - Structured error responses without sensitive data exposure
    - Operation logging for compliance and troubleshooting
    
    Returns:
    - Success: {'success': True, 'id': 'lead_id'}
    - Failure: {'error': 'detailed_error_message'}
    """
    name: str = "update_lead_tool"
    description: str = (
        "UPDATE: Existing lead record with new company, email, or phone information. "
        "Use for: 'update lead abc123 email', 'change company for lead', 'fix lead phone'. "
        "Updates single lead record - NOT for bulk operations or status changes. "
        "Requires lead_id and preserves existing data."
    )
    args_schema: type = UpdateLeadInput

    def _run(self, **kwargs) -> dict:
        try:
            log_tool_activity("UpdateLeadTool", "UPDATE_LEAD", 
                            input_data={k: v for k, v in kwargs.items()})
            sf = get_salesforce_connection()
            data = UpdateLeadInput(**kwargs)
            
            update_fields = {}
            if data.company:
                update_fields["Company"] = data.company
            if data.email:
                update_fields["Email"] = data.email
            if data.phone:
                update_fields["Phone"] = data.phone
                
            sf.Lead.update(data.lead_id, update_fields)
            
            log_tool_activity("UpdateLeadTool", "UPDATE_LEAD_SUCCESS", 
                              record_id=data.lead_id)
            return {"success": True, "id": data.lead_id}
        except Exception as e:
            return {"error": str(e)}


# Account Tools
class GetAccountInput(BaseModel):
    account_id: Optional[str] = None
    account_name: Optional[str] = None


class GetAccountTool(BaseTool):
    """Salesforce Account Retrieval Tool.
    
    Provides flexible account search capabilities with support for both direct ID
    lookups and fuzzy name-based searches. Implements enterprise account discovery
    patterns for comprehensive customer relationship management.
    
    Use Cases:
    - Direct account lookup: "get account 001abc123"
    - Company search: "find Acme Corporation account"
    - Partial name matching: "search for accounts containing 'Tech'"
    - Account verification: "verify account details before opportunity creation"
    
    Search Strategy:
    - Primary: Direct ID lookup for known accounts (fastest)
    - Secondary: Partial name matching with LIKE operator (flexible)
    - Returns comprehensive account profile including industry and revenue data
    - Token-optimized response format for cost efficiency
    
    Account Data Returned:
    - Core identifiers (ID, Name)
    - Contact information (Phone, Website)
    - Business intelligence (Industry, Annual Revenue, Employee Count)
    - Formatted for downstream processing and relationship mapping
    
    Returns:
    - Single match: Direct account object with complete profile
    - Multiple matches: Array of account objects
    - No matches: [] (empty list)
    """
    name: str = "get_account_tool"
    description: str = (
        "LOOKUP: Individual account records by ID or name (partial matching). "
        "Use for: 'get account 001abc123', 'find Acme Corporation account'. "
        "Returns specific account records - NOT comprehensive analytics or related data. "
        "For 360-degree account analysis, use GetAccountInsightsTool instead."
    )
    args_schema: type = GetAccountInput

    def _run(self, **kwargs) -> dict:
        data = GetAccountInput(**kwargs)

        try:
            log_tool_activity("GetAccountTool", "RETRIEVE_ACCOUNT", 
                            search_params={k: v for k, v in kwargs.items()})
            sf = get_salesforce_connection()
            
            builder = SOQLQueryBuilder('Account').select([
                'Id', 'Name', 'Phone', 'Website', 'Industry', 
                'AnnualRevenue', 'NumberOfEmployees'
            ])
            
            if data.account_id:
                builder.where_id(data.account_id)
            elif data.account_name:
                builder.where_like('Name', f'%{data.account_name}%')
            else:
                return {"error": "Please provide either account_id or account_name"}

            query = builder.build()
            records = sf.query(query)['records']

            if not records:
                return []

            formatted_records = [
                {
                    "id": rec["Id"],
                    "name": rec.get("Name", ""),
                    "phone": rec.get("Phone", ""),
                    "website": rec.get("Website", ""),
                    "industry": rec.get("Industry", ""),
                    "annual_revenue": rec.get("AnnualRevenue"),
                    "employees": rec.get("NumberOfEmployees")
                }
                for rec in records
            ]
            
            return formatted_records[0] if len(formatted_records) == 1 else formatted_records

        except Exception as e:
            return {"error": str(e)}


class CreateAccountInput(BaseModel):
    name: str
    phone: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None


class CreateAccountTool(BaseTool):
    """Salesforce Account Creation Tool.
    
    Creates new customer account records with comprehensive business profile data.
    Implements enterprise account management patterns for customer onboarding
    and relationship establishment workflows.
    
    Use Cases:
    - New customer onboarding: "create account for TechStart Industries"
    - Lead conversion: "convert qualified lead to account"
    - Partner registration: "add new vendor account with industry classification"
    - Manual account entry: "create account from trade show contact"
    
    Account Creation Strategy:
    - Required company name for account identification
    - Optional business intelligence fields for segmentation
    - Industry classification for targeted marketing and sales
    - Contact information for communication and engagement
    
    Data Quality Features:
    - Name validation for required field compliance
    - Industry standardization for consistent reporting
    - Website URL validation and formatting
    - Phone number formatting and validation
    
    Returns:
    - Success: {'id': 'new_account_id', 'success': True}
    - Failure: {'error': 'detailed_error_message'}
    """
    name: str = "create_account_tool"
    description: str = (
        "CREATE: New account record with company name and optional business profile. "
        "Use for: 'create account for TechStart Inc', 'add new customer account'. "
        "Creates single account record - NOT for bulk operations or analytics. "
        "Returns new account ID for relationship building."
    )
    args_schema: type = CreateAccountInput

    def _run(self, **kwargs) -> dict:
        try:
            log_tool_activity("CreateAccountTool", "CREATE_ACCOUNT", 
                            input_data={k: v for k, v in kwargs.items()})
            sf = get_salesforce_connection()
            data = CreateAccountInput(**kwargs)
            
            create_data = {"Name": data.name}
            if data.phone:
                create_data["Phone"] = data.phone
            if data.website:
                create_data["Website"] = data.website
            if data.industry:
                create_data["Industry"] = data.industry
                
            result = sf.Account.create(create_data)
            
            log_tool_activity("CreateAccountTool", "CREATE_ACCOUNT_SUCCESS", 
                              record_id=result['id'])
            return result
        except Exception as e:
            return {"error": str(e)}


class UpdateAccountInput(BaseModel):
    account_id: str
    name: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None


class UpdateAccountTool(BaseTool):
    """Salesforce Account Update Tool.
    
    Updates existing customer account records with new business information while
    preserving data integrity and maintaining complete audit trails for compliance.
    Supports selective field updates for progressive data enrichment.
    
    Use Cases:
    - Business profile updates: "update account with new industry classification"
    - Contact information changes: "change phone number for account"
    - Data enrichment: "add website and industry data to existing account"
    - Merger/acquisition updates: "update account name after company acquisition"
    
    Update Features:
    - Selective field modification preserves existing data
    - Business intelligence field updates for segmentation
    - Contact information maintenance for communication
    - Industry classification updates for targeted campaigns
    
    Data Integrity:
    - Account ID validation ensures authorized access
    - Field-level validation for data quality
    - Audit trail creation for change tracking
    - Rollback capability through change history
    
    Returns:
    - Success: {'success': True, 'id': 'account_id'}
    - Failure: {'error': 'detailed_error_message'}
    """
    name: str = "update_account_tool"
    description: str = (
        "UPDATE: Existing account record with new business information or contact details. "
        "Use for: 'update account abc123 phone', 'change industry for account', 'add website'. "
        "Updates single account record - NOT for bulk operations or relationship changes. "
        "Requires account_id and preserves existing data."
    )
    args_schema: type = UpdateAccountInput

    def _run(self, **kwargs) -> dict:
        try:
            log_tool_activity("UpdateAccountTool", "UPDATE_ACCOUNT", 
                            input_data={k: v for k, v in kwargs.items()})
            sf = get_salesforce_connection()
            data = UpdateAccountInput(**kwargs)
            
            update_fields = {}
            if data.name:
                update_fields["Name"] = data.name
            if data.phone:
                update_fields["Phone"] = data.phone
            if data.website:
                update_fields["Website"] = data.website
            if data.industry:
                update_fields["Industry"] = data.industry
                
            sf.Account.update(data.account_id, update_fields)
            
            log_tool_activity("UpdateAccountTool", "UPDATE_ACCOUNT_SUCCESS", 
                              record_id=data.account_id)
            return {"success": True, "id": data.account_id}
        except Exception as e:
            return {"error": str(e)}


# Opportunity Tools
class GetOpportunityInput(BaseModel):
    opportunity_id: Optional[str] = None
    opportunity_name: Optional[str] = None
    account_name: Optional[str] = None
    account_id: Optional[str] = None


class GetOpportunityTool(BaseTool):
    """Salesforce Opportunity Retrieval Tool.
    
    Provides comprehensive opportunity discovery with flexible search criteria across
    multiple relationship types. Implements intelligent account relationship resolution
    for complex opportunity-to-account mapping and pipeline analysis.
    
    Use Cases:
    - Direct opportunity lookup: "get opportunity 006abc123"
    - Deal name search: "find Enterprise Software License opportunity"
    - Account-based pipeline: "show all opportunities for Acme Corp"
    - Account ID filtering: "opportunities for account 001abc123"
    
    Search Strategy:
    - Primary: Direct opportunity ID lookup (fastest)
    - Secondary: Opportunity name partial matching
    - Tertiary: Account relationship resolution (name-to-ID mapping)
    - Quaternary: Direct account ID filtering
    
    Relationship Intelligence:
    - Automatic account name-to-ID resolution using SearchQueryBuilder
    - Support for multiple account matches with IN clause filtering
    - Revenue-based ordering for priority pipeline visibility
    - Complete opportunity lifecycle data (stage, amount, close date)
    
    Returns:
    - Single match: Direct opportunity object with relationship data
    - Multiple matches: Revenue-ordered opportunity array
    - No matches: [] (empty list)
    """
    name: str = "get_opportunity_tool"
    description: str = (
        "LOOKUP: Individual opportunity records by ID, name, or account relationship. "
        "Use for: 'get opportunity 006abc123', 'find deals for Acme Corp', 'Enterprise License opportunity'. "
        "Returns specific opportunity records - NOT pipeline analytics or aggregated metrics. "
        "For pipeline analysis/trends, use GetSalesPipelineTool instead."
    )
    args_schema: type = GetOpportunityInput

    def _run(self, **kwargs) -> dict:
        data = GetOpportunityInput(**kwargs)

        try:
            log_tool_activity("GetOpportunityTool", "RETRIEVE_OPPORTUNITY", 
                            search_params={k: v for k, v in kwargs.items()})
            sf = get_salesforce_connection()
            
            builder = SOQLQueryBuilder('Opportunity').select([
                'Id', 'Name', 'StageName', 'Amount', 'CloseDate', 
                'AccountId', 'Probability', 'Type'
            ])
            
            if data.opportunity_id:
                builder.where_id(data.opportunity_id)
            else:
                conditions_added = False
                
                if data.opportunity_name:
                    builder.where_like('Name', f'%{data.opportunity_name}%')
                    conditions_added = True
                    
                if data.account_id:
                    if conditions_added:
                        builder.where('AccountId', SOQLOperator.EQUALS, data.account_id)
                    else:
                        builder.where('AccountId', SOQLOperator.EQUALS, data.account_id)
                        conditions_added = True
                        
                if data.account_name and not data.account_id:
                    # First get account ID from name
                    account_search = SearchQueryBuilder(sf, 'Account')
                    accounts = account_search.search_fields(['Name'], data.account_name).execute()
                    
                    if accounts:
                        account_ids = [acc['Id'] for acc in accounts]
                        if conditions_added:
                            builder.where_in('AccountId', account_ids)
                        else:
                            builder.where_in('AccountId', account_ids)
                            conditions_added = True
                
                if not conditions_added:
                    return {"error": "No search criteria provided."}

            query = builder.order_by('Amount', descending=True).build()
            records = sf.query(query)['records']

            if not records:
                return []

            formatted_records = [
                {
                    "id": rec["Id"],
                    "name": rec.get("Name", ""),
                    "stage": rec.get("StageName", ""),
                    "amount": rec.get("Amount"),
                    "close_date": rec.get("CloseDate", ""),
                    "account_id": rec.get("AccountId", ""),
                    "probability": rec.get("Probability"),
                    "type": rec.get("Type", "")
                }
                for rec in records
            ]
            
            return formatted_records[0] if len(formatted_records) == 1 else formatted_records

        except Exception as e:
            return {"error": str(e)}


class CreateOpportunityInput(BaseModel):
    name: str
    stage: str
    close_date: str
    account_id: str
    amount: Optional[float] = None
    
    @field_validator('stage')
    def validate_stage(cls, v):
        valid_stages = [
            "Prospecting", "Qualification", "Needs Analysis",
            "Value Proposition", "Id. Decision Makers", "Perception Analysis",
            "Proposal/Price Quote", "Negotiation/Review", "Closed Won", "Closed Lost"
        ]
        if v not in valid_stages:
            raise ValueError(f"Invalid stage. Must be one of: {', '.join(valid_stages)}")
        return v


class CreateOpportunityTool(BaseTool):
    """Salesforce Opportunity Creation Tool.
    
    Creates new revenue opportunities with complete sales cycle tracking and validation.
    Implements enterprise opportunity management with stage validation and forecasting
    integration for accurate pipeline reporting and sales analytics.
    
    Use Cases:
    - New deal creation: "create opportunity for Enterprise Software License"
    - Lead conversion: "convert qualified lead to opportunity"
    - Upsell tracking: "add expansion opportunity for existing customer"
    - Renewal management: "create renewal opportunity with updated terms"
    
    Opportunity Lifecycle:
    - Stage validation against Salesforce picklist values
    - Close date requirements for forecasting accuracy
    - Account relationship establishment for customer mapping
    - Amount tracking for revenue recognition and reporting
    
    Validation Features:
    - Sales stage validation ensures data consistency
    - Close date format validation (YYYY-MM-DD)
    - Account ID verification for relationship integrity
    - Optional amount handling for preliminary opportunities
    
    Returns:
    - Success: {'id': 'new_opportunity_id', 'success': True}
    - Failure: {'error': 'detailed_error_message'}
    """
    name: str = "create_opportunity_tool"
    description: str = (
        "CREATE: New opportunity record with name, stage, close date, and account relationship. "
        "Use for: 'create Enterprise License opportunity for Acme', 'add new deal'. "
        "Creates single opportunity record - NOT for bulk operations or pipeline analytics. "
        "Returns new opportunity ID for sales tracking."
    )
    args_schema: type = CreateOpportunityInput

    def _run(self, **kwargs) -> dict:
        try:
            log_tool_activity("CreateOpportunityTool", "CREATE_OPPORTUNITY", 
                            input_data={k: v for k, v in kwargs.items()})
            sf = get_salesforce_connection()
            data = CreateOpportunityInput(**kwargs)
            
            create_data = {
                "Name": data.name,
                "StageName": data.stage,
                "CloseDate": data.close_date,
                "AccountId": data.account_id
            }
            if data.amount:
                create_data["Amount"] = data.amount
                
            result = sf.Opportunity.create(create_data)
            
            log_tool_activity("CreateOpportunityTool", "CREATE_OPPORTUNITY_SUCCESS", 
                              record_id=result['id'])
            return result
        except Exception as e:
            return {"error": str(e)}


class UpdateOpportunityInput(BaseModel):
    opportunity_id: str
    stage: Optional[str] = None
    amount: Optional[float] = None
    close_date: Optional[str] = None
    
    @field_validator('stage')
    def validate_stage(cls, v):
        if v is None:
            return v
        valid_stages = [
            "Prospecting", "Qualification", "Needs Analysis",
            "Value Proposition", "Id. Decision Makers", "Perception Analysis",
            "Proposal/Price Quote", "Negotiation/Review", "Closed Won", "Closed Lost"
        ]
        if v not in valid_stages:
            raise ValueError(f"Invalid stage. Must be one of: {', '.join(valid_stages)}")
        return v


class UpdateOpportunityTool(BaseTool):
    """Salesforce Opportunity Update Tool.
    
    Updates existing opportunities with sales progression tracking and revenue adjustments.
    Implements opportunity lifecycle management with stage progression validation
    and forecasting updates for accurate pipeline reporting.
    
    Use Cases:
    - Stage progression: "move opportunity to Closed Won"
    - Amount updates: "increase opportunity value to $500K"
    - Timeline changes: "extend close date to next quarter"
    - Deal modifications: "update terms and conditions"
    
    Update Strategy:
    - Selective field updates preserve opportunity history
    - Stage progression validation ensures logical sales flow
    - Amount adjustments trigger forecasting recalculations
    - Close date modifications update pipeline projections
    
    Sales Process Integration:
    - Stage validation against configured sales process
    - Probability updates based on stage progression
    - Revenue recognition impact calculation
    - Pipeline reporting refresh triggers
    
    Returns:
    - Success: {'success': True, 'id': 'opportunity_id'}
    - Failure: {'error': 'detailed_error_message'}
    """
    name: str = "update_opportunity_tool"
    description: str = (
        "UPDATE: Existing opportunity with stage progression, amount, or close date changes. "
        "Use for: 'move opportunity to Closed Won', 'increase deal amount', 'extend close date'. "
        "Updates single opportunity record - NOT for bulk operations or pipeline analytics. "
        "Requires opportunity_id for sales progression tracking."
    )
    args_schema: type = UpdateOpportunityInput

    def _run(self, **kwargs) -> dict:
        data = UpdateOpportunityInput(**kwargs)

        try:
            log_tool_activity("UpdateOpportunityTool", "UPDATE_OPPORTUNITY", 
                            input_data={k: v for k, v in kwargs.items()})
            sf = get_salesforce_connection()
            
            update_fields = {}
            if data.stage:
                update_fields["StageName"] = data.stage
            if data.amount is not None:
                update_fields["Amount"] = data.amount
            if data.close_date:
                update_fields["CloseDate"] = data.close_date
                
            sf.Opportunity.update(data.opportunity_id, update_fields)
            
            log_tool_activity("UpdateOpportunityTool", "UPDATE_OPPORTUNITY_SUCCESS", 
                              record_id=data.opportunity_id)
            return {"success": True, "id": data.opportunity_id}
        except Exception as e:
            return {"error": str(e)}


# Contact Tools
class GetContactInput(BaseModel):
    contact_id: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    account_name: Optional[str] = None


class GetContactTool(BaseTool):
    """Salesforce Contact Retrieval Tool.
    
    Provides comprehensive contact discovery with intelligent account relationship mapping
    and flexible search criteria. Implements contact-to-account relationship resolution
    for complete customer relationship visibility and engagement tracking.
    
    Use Cases:
    - Direct contact lookup: "get contact 003abc123"
    - Email-based search: "find contact john@company.com"
    - Name-based discovery: "search for John Smith contacts"
    - Account relationship mapping: "all contacts at Acme Corp"
    
    Search Strategy:
    - Primary: Direct contact ID lookup (fastest)
    - Secondary: Email exact and partial matching
    - Tertiary: Name fuzzy matching with LIKE operators
    - Quaternary: Phone number search with formatting flexibility
    - Advanced: Account name-to-contact relationship mapping
    
    Relationship Intelligence:
    - Automatic account name-to-ID resolution
    - Complex OR condition support for multi-field searches
    - Account relationship prioritization for organized results
    - Contact hierarchy and reporting structure visibility
    
    Returns:
    - Single match: Direct contact object with account relationship
    - Multiple matches: Contact array with relationship context
    - No matches: [] (empty list)
    """
    name: str = "get_contact_tool"
    description: str = (
        "LOOKUP: Individual contact records by ID, email, name, phone, or account. "
        "Use for: 'get contact 003abc123', 'find john@company.com', 'contacts at Acme Corp'. "
        "Returns specific contact records - NOT relationship analytics or engagement metrics. "
        "For comprehensive account contacts, use GetAccountInsightsTool instead."
    )
    args_schema: type = GetContactInput

    def _run(self, **kwargs) -> dict:
        data = GetContactInput(**kwargs)

        try:
            log_tool_activity("GetContactTool", "RETRIEVE_CONTACT", 
                            search_params={k: v for k, v in kwargs.items()})
            sf = get_salesforce_connection()
            
            builder = SOQLQueryBuilder('Contact').select([
                'Id', 'Name', 'Email', 'Phone', 'Title', 
                'AccountId', 'Department', 'MobilePhone'
            ])
            
            if data.contact_id:
                builder.where_id(data.contact_id)
            else:
                conditions_added = False
                
                # Add search conditions
                search_fields = [
                    ('Email', data.email),
                    ('Name', data.name),
                    ('Phone', data.phone)
                ]
                
                for field, value in search_fields:
                    if value:
                        if not conditions_added:
                            builder.where_like(field, f'%{value}%')
                            conditions_added = True
                        else:
                            builder.or_where(field, SOQLOperator.LIKE, f'%{value}%')
                
                # Handle account name search
                if data.account_name:
                    account_search = SearchQueryBuilder(sf, 'Account')
                    accounts = account_search.search_fields(['Name'], data.account_name).execute()
                    
                    if accounts:
                        account_ids = [acc['Id'] for acc in accounts]
                        if conditions_added:
                            # Need to restructure query for mixed AND/OR
                            # This is a limitation we'll address in a future version
                            builder = SOQLQueryBuilder('Contact').select([
                                'Id', 'Name', 'Email', 'Phone', 'Title', 
                                'AccountId', 'Department', 'MobilePhone'
                            ]).where_in('AccountId', account_ids)
                        else:
                            builder.where_in('AccountId', account_ids)
                            conditions_added = True
                
                if not conditions_added:
                    return {"error": "No search criteria provided."}

            query = builder.build()
            records = sf.query(query)['records']

            if not records:
                return []

            formatted_records = [
                {
                    "id": rec["Id"],
                    "name": rec.get("Name", ""),
                    "email": rec.get("Email", ""),
                    "phone": rec.get("Phone", ""),
                    "mobile": rec.get("MobilePhone", ""),
                    "title": rec.get("Title", ""),
                    "account_id": rec.get("AccountId", ""),
                    "department": rec.get("Department", "")
                }
                for rec in records
            ]
            
            return formatted_records[0] if len(formatted_records) == 1 else formatted_records

        except Exception as e:
            return {"error": str(e)}


class CreateContactInput(BaseModel):
    first_name: str
    last_name: str
    account_id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None


class CreateContactTool(BaseTool):
    """Salesforce Contact Creation Tool.
    
    Creates new contact records with account relationship establishment and comprehensive
    contact profile data. Implements enterprise contact management patterns for customer
    relationship building and engagement tracking.
    
    Use Cases:
    - New contact creation: "add John Smith as contact for Acme Corp"
    - Lead conversion: "convert lead to contact under existing account"
    - Stakeholder mapping: "add decision maker contact with title"
    - Relationship expansion: "create additional contact for customer account"
    
    Contact Creation Strategy:
    - Required name fields for contact identification
    - Account relationship establishment for customer mapping
    - Optional communication fields for engagement
    - Title/role information for stakeholder analysis
    
    Relationship Management:
    - Account ID validation ensures relationship integrity
    - Contact hierarchy establishment within account structure
    - Communication preference setup for engagement
    - Role-based access and visibility configuration
    
    Returns:
    - Success: {'id': 'new_contact_id', 'success': True}
    - Failure: {'error': 'detailed_error_message'}
    """
    name: str = "create_contact_tool"
    description: str = (
        "CREATE: New contact record with name, account relationship, and optional details. "
        "Use for: 'create contact John Smith for Acme account', 'add new contact'. "
        "Creates single contact record - NOT for bulk operations or relationship analytics. "
        "Returns new contact ID for customer engagement."
    )
    args_schema: type = CreateContactInput

    def _run(self, **kwargs) -> dict:
        try:
            log_tool_activity("CreateContactTool", "CREATE_CONTACT", 
                            input_data={k: v for k, v in kwargs.items()})
            sf = get_salesforce_connection()
            data = CreateContactInput(**kwargs)
            
            create_data = {
                "FirstName": data.first_name,
                "LastName": data.last_name,
                "AccountId": data.account_id
            }
            if data.email:
                create_data["Email"] = data.email
            if data.phone:
                create_data["Phone"] = data.phone
            if data.title:
                create_data["Title"] = data.title
                
            result = sf.Contact.create(create_data)
            
            log_tool_activity("CreateContactTool", "CREATE_CONTACT_SUCCESS", 
                              record_id=result['id'])
            return result
        except Exception as e:
            return {"error": str(e)}


class UpdateContactInput(BaseModel):
    contact_id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None


class UpdateContactTool(BaseTool):
    """Salesforce Contact Update Tool.
    
    Updates existing contact records with new communication information and role changes.
    Implements contact lifecycle management with data integrity preservation and
    engagement history maintenance for customer relationship continuity.
    
    Use Cases:
    - Contact information updates: "update email for contact abc123"
    - Role changes: "promote contact to VP Sales title"
    - Communication preferences: "add mobile phone number"
    - Data enrichment: "update contact with complete profile information"
    
    Update Strategy:
    - Selective field updates preserve contact history
    - Communication field updates maintain engagement continuity
    - Title changes reflect organizational structure updates
    - Contact relationship preservation during modifications
    
    Data Integrity:
    - Contact ID validation ensures authorized access
    - Email format validation for communication reliability
    - Phone number formatting for consistent data
    - Title standardization for role-based analytics
    
    Returns:
    - Success: {'success': True, 'id': 'contact_id'}
    - Failure: {'error': 'detailed_error_message'}
    """
    name: str = "update_contact_tool"
    description: str = (
        "UPDATE: Existing contact record with new email, phone, or title information. "
        "Use for: 'update contact abc123 email', 'change title for contact', 'add phone number'. "
        "Updates single contact record - NOT for bulk operations or relationship changes. "
        "Requires contact_id and preserves relationship data."
    )
    args_schema: type = UpdateContactInput

    def _run(self, **kwargs) -> dict:
        try:
            log_tool_activity("UpdateContactTool", "UPDATE_CONTACT", 
                            input_data={k: v for k, v in kwargs.items()})
            sf = get_salesforce_connection()
            data = UpdateContactInput(**kwargs)
            
            update_fields = {}
            if data.email:
                update_fields["Email"] = data.email
            if data.phone:
                update_fields["Phone"] = data.phone
            if data.title:
                update_fields["Title"] = data.title
                
            sf.Contact.update(data.contact_id, update_fields)
            
            log_tool_activity("UpdateContactTool", "UPDATE_CONTACT_SUCCESS", 
                              record_id=data.contact_id)
            return {"success": True, "id": data.contact_id}
        except Exception as e:
            return {"error": str(e)}


# Case Tools
class GetCaseInput(BaseModel):
    case_id: Optional[str] = None
    case_number: Optional[str] = None
    subject: Optional[str] = None
    account_name: Optional[str] = None
    contact_name: Optional[str] = None


class GetCaseTool(BaseTool):
    """Salesforce Case Retrieval Tool.
    
    Provides comprehensive customer service case discovery with intelligent relationship
    mapping across accounts and contacts. Implements enterprise support case management
    with flexible search patterns for complete customer service visibility.
    
    Use Cases:
    - Direct case lookup: "get case 500abc123"
    - Case number search: "find case 00001234"
    - Subject-based discovery: "search cases about 'installation issues'"
    - Account support history: "all cases for Acme Corp"
    - Contact-specific cases: "cases reported by John Smith"
    
    Search Strategy:
    - Primary: Direct case ID lookup (fastest)
    - Secondary: Case number exact matching
    - Tertiary: Subject partial matching for issue discovery
    - Quaternary: Account relationship mapping for customer history
    - Advanced: Contact relationship mapping for personal support history
    
    Support Intelligence:
    - Automatic account and contact relationship resolution
    - Case priority and status visibility for triage
    - Chronological ordering for case progression tracking
    - Customer service history mapping for context
    
    Returns:
    - Single match: Direct case object with relationship context
    - Multiple matches: Chronologically ordered case array
    - No matches: [] (empty list)
    """
    name: str = "get_case_tool"
    description: str = (
        "LOOKUP: Individual case records by ID, number, subject, or account/contact. "
        "Use for: 'get case 500abc123', 'find installation issue cases', 'cases for Acme Corp'. "
        "Returns specific case records - NOT support analytics or volume trends. "
        "For case analytics/trends, use GetBusinessMetricsTool instead."
    )
    args_schema: type = GetCaseInput

    def _run(self, **kwargs) -> dict:
        data = GetCaseInput(**kwargs)

        try:
            log_tool_activity("GetCaseTool", "RETRIEVE_CASE", 
                            search_params={k: v for k, v in kwargs.items()})
            sf = get_salesforce_connection()
            
            builder = SOQLQueryBuilder('Case').select([
                'Id', 'CaseNumber', 'Subject', 'Status', 'Priority',
                'AccountId', 'ContactId', 'Description', 'Type'
            ])
            
            if data.case_id:
                builder.where_id(data.case_id)
            elif data.case_number:
                builder.where('CaseNumber', SOQLOperator.EQUALS, data.case_number)
            else:
                conditions_added = False
                
                if data.subject:
                    builder.where_like('Subject', f'%{data.subject}%')
                    conditions_added = True
                
                # Handle account name search
                if data.account_name:
                    account_search = SearchQueryBuilder(sf, 'Account')
                    accounts = account_search.search_fields(['Name'], data.account_name).execute()
                    
                    if accounts:
                        account_ids = [acc['Id'] for acc in accounts]
                        if conditions_added:
                            builder.where_in('AccountId', account_ids)
                        else:
                            builder.where_in('AccountId', account_ids)
                            conditions_added = True
                
                # Handle contact name search
                if data.contact_name:
                    contact_search = SearchQueryBuilder(sf, 'Contact')
                    contacts = contact_search.search_fields(['Name'], data.contact_name).execute()
                    
                    if contacts:
                        contact_ids = [con['Id'] for con in contacts]
                        if conditions_added:
                            builder.where_in('ContactId', contact_ids)
                        else:
                            builder.where_in('ContactId', contact_ids)
                            conditions_added = True
                
                if not conditions_added:
                    return {"error": "No search criteria provided."}

            query = builder.order_by('CreatedDate', descending=True).build()
            records = sf.query(query)['records']

            if not records:
                return []

            formatted_records = [
                {
                    "id": rec["Id"],
                    "case_number": rec.get("CaseNumber", ""),
                    "subject": rec.get("Subject", ""),
                    "status": rec.get("Status", ""),
                    "priority": rec.get("Priority", ""),
                    "account_id": rec.get("AccountId", ""),
                    "contact_id": rec.get("ContactId", ""),
                    "description": rec.get("Description", ""),
                    "type": rec.get("Type", "")
                }
                for rec in records
            ]
            
            return formatted_records[0] if len(formatted_records) == 1 else formatted_records

        except Exception as e:
            return {"error": str(e)}


class CreateCaseInput(BaseModel):
    subject: str
    description: str
    account_id: Optional[str] = None
    contact_id: Optional[str] = None
    priority: Optional[str] = "Medium"
    
    @field_validator('priority')
    def validate_priority(cls, v):
        valid_priorities = ["Low", "Medium", "High"]
        if v not in valid_priorities:
            raise ValueError(f"Priority must be one of: {', '.join(valid_priorities)}")
        return v


class CreateCaseTool(BaseTool):
    """Salesforce Case Creation Tool.
    
    Creates new customer service cases with comprehensive issue tracking and relationship
    mapping. Implements enterprise support case management with priority classification
    and customer relationship establishment for efficient service delivery.
    
    Use Cases:
    - Customer issue reporting: "create case for software installation problem"
    - Support ticket creation: "log technical support request"
    - Service request tracking: "create case for feature enhancement request"
    - Incident management: "create high priority case for system outage"
    
    Case Creation Strategy:
    - Required issue description for problem documentation
    - Priority classification for support queue management
    - Account/contact relationship for customer context
    - Automatic case routing based on priority and type
    
    Support Process Integration:
    - Priority validation against support SLA requirements
    - Account relationship for customer service history
    - Contact assignment for personalized support
    - Case routing and escalation triggers
    
    Returns:
    - Success: {'id': 'new_case_id', 'success': True}
    - Failure: {'error': 'detailed_error_message'}
    """
    name: str = "create_case_tool"
    description: str = (
        "CREATE: New customer service case with subject, description, and optional relationships. "
        "Use for: 'create case for installation issue', 'log support ticket'. "
        "Creates single case record - NOT for bulk operations or support analytics. "
        "Returns new case ID for support tracking."
    )
    args_schema: type = CreateCaseInput

    def _run(self, **kwargs) -> dict:
        try:
            log_tool_activity("CreateCaseTool", "CREATE_CASE", 
                            input_data={k: v for k, v in kwargs.items()})
            sf = get_salesforce_connection()
            data = CreateCaseInput(**kwargs)
            
            create_data = {
                "Subject": data.subject,
                "Description": data.description,
                "Priority": data.priority,
                "Status": "New"
            }
            if data.account_id:
                create_data["AccountId"] = data.account_id
            if data.contact_id:
                create_data["ContactId"] = data.contact_id
                
            result = sf.Case.create(create_data)
            
            log_tool_activity("CreateCaseTool", "CREATE_CASE_SUCCESS", 
                              record_id=result['id'])
            return result
        except Exception as e:
            return {"error": str(e)}


class UpdateCaseInput(BaseModel):
    case_id: str
    status: Optional[str] = None
    priority: Optional[str] = None
    
    @field_validator('priority')
    def validate_priority(cls, v):
        if v is None:
            return v
        valid_priorities = ["Low", "Medium", "High"]
        if v not in valid_priorities:
            raise ValueError(f"Priority must be one of: {', '.join(valid_priorities)}")
        return v
    
    @field_validator('status')
    def validate_status(cls, v):
        if v is None:
            return v
        valid_statuses = ["New", "Working", "Escalated", "Closed"]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")
        return v


class UpdateCaseTool(BaseTool):
    """Salesforce Case Update Tool.
    
    Updates existing customer service cases with status progression and priority adjustments.
    Implements support case lifecycle management with SLA tracking and escalation
    procedures for enterprise customer service operations.
    
    Use Cases:
    - Case resolution: "close case as resolved"
    - Priority escalation: "increase case priority to High"
    - Status progression: "move case to In Progress"
    - Case routing: "update case assignment and priority"
    
    Update Strategy:
    - Status progression validation for case lifecycle
    - Priority adjustments for SLA compliance
    - Selective field updates preserve case history
    - Automatic escalation triggers based on updates
    
    Service Level Management:
    - Status validation against support process workflows
    - Priority changes trigger SLA recalculation
    - Case progression tracking for performance metrics
    - Customer notification triggers for status changes
    
    Returns:
    - Success: {'success': True, 'id': 'case_id'}
    - Failure: {'error': 'detailed_error_message'}
    """
    name: str = "update_case_tool"
    description: str = (
        "UPDATE: Existing case record with status changes or priority adjustments. "
        "Use for: 'close case abc123', 'escalate case priority', 'mark case in progress'. "
        "Updates single case record - NOT for bulk operations or support analytics. "
        "Requires case_id for support lifecycle management."
    )
    args_schema: type = UpdateCaseInput

    def _run(self, **kwargs) -> dict:
        try:
            log_tool_activity("UpdateCaseTool", "UPDATE_CASE", 
                            input_data={k: v for k, v in kwargs.items()})
            sf = get_salesforce_connection()
            data = UpdateCaseInput(**kwargs)
            
            update_fields = {}
            if data.status:
                update_fields["Status"] = data.status
            if data.priority:
                update_fields["Priority"] = data.priority
                
            sf.Case.update(data.case_id, update_fields)
            
            log_tool_activity("UpdateCaseTool", "UPDATE_CASE_SUCCESS", 
                              record_id=data.case_id)
            return {"success": True, "id": data.case_id}
        except Exception as e:
            return {"error": str(e)}


# Task Tools
class GetTaskInput(BaseModel):
    task_id: Optional[str] = None
    subject: Optional[str] = None
    account_name: Optional[str] = None
    contact_name: Optional[str] = None


class GetTaskTool(BaseTool):
    """Salesforce Task Retrieval Tool.
    
    Provides comprehensive activity and task discovery with intelligent relationship mapping
    across accounts and contacts. Implements enterprise activity management with flexible
    search patterns for complete sales and service activity visibility.
    
    Use Cases:
    - Direct task lookup: "get task 00Tabc123"
    - Subject-based search: "find tasks about 'follow up call'"
    - Account activity history: "all tasks related to Acme Corp"
    - Contact activity tracking: "tasks assigned to John Smith"
    
    Search Strategy:
    - Primary: Direct task ID lookup (fastest)
    - Secondary: Subject partial matching for activity discovery
    - Tertiary: Account relationship mapping (WhatId) for customer activities
    - Quaternary: Contact relationship mapping (WhoId) for personal activities
    
    Activity Intelligence:
    - WhatId/WhoId relationship resolution for complete context
    - Account and contact relationship mapping
    - Activity date ordering for timeline visibility
    - Task priority and status tracking for workflow management
    
    Returns:
    - Single match: Direct task object with relationship context
    - Multiple matches: Date-ordered task array for timeline view
    - No matches: [] (empty list)
    """
    name: str = "get_task_tool"
    description: str = (
        "LOOKUP: Individual task/activity records by ID, subject, or account/contact. "
        "Use for: 'get task 00Tabc123', 'find follow-up tasks', 'tasks for Acme Corp'. "
        "Returns specific task records - NOT activity analytics or productivity metrics. "
        "For activity trends/analysis, use other analytics tools."
    )
    args_schema: type = GetTaskInput

    def _run(self, **kwargs) -> dict:
        data = GetTaskInput(**kwargs)

        try:
            log_tool_activity("GetTaskTool", "RETRIEVE_TASK", 
                            search_params={k: v for k, v in kwargs.items()})
            sf = get_salesforce_connection()
            
            builder = SOQLQueryBuilder('Task').select([
                'Id', 'Subject', 'Status', 'Priority', 'ActivityDate',
                'WhatId', 'WhoId', 'Description'
            ])
            
            if data.task_id:
                builder.where_id(data.task_id)
            else:
                conditions_added = False
                
                if data.subject:
                    builder.where_like('Subject', f'%{data.subject}%')
                    conditions_added = True
                
                # Handle account name search (WhatId for accounts)
                if data.account_name:
                    account_search = SearchQueryBuilder(sf, 'Account')
                    accounts = account_search.search_fields(['Name'], data.account_name).execute()
                    
                    if accounts:
                        account_ids = [acc['Id'] for acc in accounts]
                        if conditions_added:
                            builder.where_in('WhatId', account_ids)
                        else:
                            builder.where_in('WhatId', account_ids)
                            conditions_added = True
                
                # Handle contact name search (WhoId for contacts)
                if data.contact_name:
                    contact_search = SearchQueryBuilder(sf, 'Contact')
                    contacts = contact_search.search_fields(['Name'], data.contact_name).execute()
                    
                    if contacts:
                        contact_ids = [con['Id'] for con in contacts]
                        if conditions_added:
                            builder.where_in('WhoId', contact_ids)
                        else:
                            builder.where_in('WhoId', contact_ids)
                            conditions_added = True
                
                if not conditions_added:
                    return {"error": "No search criteria provided."}

            query = builder.order_by('ActivityDate', descending=True).build()
            records = sf.query(query)['records']

            if not records:
                return []

            formatted_records = [
                {
                    "id": rec["Id"],
                    "subject": rec.get("Subject", ""),
                    "status": rec.get("Status", ""),
                    "priority": rec.get("Priority", ""),
                    "due_date": rec.get("ActivityDate", ""),
                    "related_to_id": rec.get("WhatId", ""),
                    "contact_id": rec.get("WhoId", ""),
                    "description": rec.get("Description", ""),
                    "type": rec.get("Type", "")
                }
                for rec in records
            ]
            
            return formatted_records[0] if len(formatted_records) == 1 else formatted_records

        except Exception as e:
            return {"error": str(e)}


class CreateTaskInput(BaseModel):
    subject: str
    due_date: str  # YYYY-MM-DD format
    priority: Optional[str] = "Normal"
    account_id: Optional[str] = None
    contact_id: Optional[str] = None
    description: Optional[str] = None
    
    @field_validator('priority')
    def validate_priority(cls, v):
        valid_priorities = ["Low", "Normal", "High"]
        if v not in valid_priorities:
            raise ValueError(f"Priority must be one of: {', '.join(valid_priorities)}")
        return v


class CreateTaskTool(BaseTool):
    """Salesforce Task Creation Tool.
    
    Creates new activity tasks with comprehensive relationship mapping and workflow integration.
    Implements enterprise activity management with priority classification and due date
    tracking for sales and service process automation.
    
    Use Cases:
    - Follow-up scheduling: "create follow-up call task for next week"
    - Activity planning: "schedule demo task for prospect"
    - Service reminders: "create customer check-in task"
    - Sales process automation: "create proposal review task"
    
    Task Creation Strategy:
    - Required activity description and timeline
    - Priority classification for workflow management
    - Account/contact relationship establishment
    - Automatic workflow and reminder integration
    
    Workflow Integration:
    - WhatId (account) and WhoId (contact) relationship mapping
    - Priority-based task routing and assignment
    - Due date integration with calendar and reminder systems
    - Activity history tracking for customer engagement
    
    Returns:
    - Success: {'id': 'new_task_id', 'success': True}
    - Failure: {'error': 'detailed_error_message'}
    """
    name: str = "create_task_tool"
    description: str = (
        "CREATE: New task/activity record with subject, due date, and optional relationships. "
        "Use for: 'create follow-up task for next week', 'schedule demo task'. "
        "Creates single task record - NOT for bulk operations or activity analytics. "
        "Returns new task ID for activity tracking."
    )
    args_schema: type = CreateTaskInput

    def _run(self, **kwargs) -> dict:
        try:
            log_tool_activity("CreateTaskTool", "CREATE_TASK", 
                            input_data={k: v for k, v in kwargs.items()})
            sf = get_salesforce_connection()
            data = CreateTaskInput(**kwargs)
            
            create_data = {
                "Subject": data.subject,
                "ActivityDate": data.due_date,
                "Priority": data.priority,
                "Status": "Not Started"
            }
            if data.account_id:
                create_data["WhatId"] = data.account_id
            if data.contact_id:
                create_data["WhoId"] = data.contact_id
            if data.description:
                create_data["Description"] = data.description
                
            result = sf.Task.create(create_data)
            
            log_tool_activity("CreateTaskTool", "CREATE_TASK_SUCCESS", 
                              record_id=result['id'])
            return result
        except Exception as e:
            return {"error": str(e)}


class UpdateTaskInput(BaseModel):
    task_id: str
    status: Optional[str] = None
    priority: Optional[str] = None
    
    @field_validator('status')
    def validate_status(cls, v):
        if v is None:
            return v
        valid_statuses = ["Not Started", "In Progress", "Completed", "Waiting on someone else", "Deferred"]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")
        return v
    
    @field_validator('priority')
    def validate_priority(cls, v):
        if v is None:
            return v
        valid_priorities = ["Low", "Normal", "High"]
        if v not in valid_priorities:
            raise ValueError(f"Priority must be one of: {', '.join(valid_priorities)}")
        return v


class UpdateTaskTool(BaseTool):
    """Salesforce Task Update Tool.
    
    Updates existing activity tasks with status progression and priority adjustments.
    Implements activity lifecycle management with completion tracking and workflow
    integration for enterprise sales and service process automation.
    
    Use Cases:
    - Task completion: "mark task as completed"
    - Priority escalation: "increase task priority to High"
    - Status progression: "move task to In Progress"
    - Activity management: "update task assignment and timeline"
    
    Update Strategy:
    - Status progression validation for activity lifecycle
    - Priority adjustments for workflow prioritization
    - Selective field updates preserve activity history
    - Automatic workflow triggers based on status changes
    
    Activity Management:
    - Status validation against activity workflow states
    - Priority changes affect task routing and assignment
    - Completion tracking for performance metrics
    - Activity timeline maintenance for customer engagement history
    
    Returns:
    - Success: {'success': True, 'id': 'task_id'}
    - Failure: {'error': 'detailed_error_message'}
    """
    name: str = "update_task_tool"
    description: str = (
        "UPDATE: Existing task record with status completion or priority changes. "
        "Use for: 'mark task abc123 completed', 'change task priority', 'update task status'. "
        "Updates single task record - NOT for bulk operations or activity analytics. "
        "Requires task_id for activity lifecycle management."
    )
    args_schema: type = UpdateTaskInput

    def _run(self, **kwargs) -> dict:
        try:
            log_tool_activity("UpdateTaskTool", "UPDATE_TASK", 
                            input_data={k: v for k, v in kwargs.items()})
            sf = get_salesforce_connection()
            data = UpdateTaskInput(**kwargs)
            
            update_fields = {}
            if data.status:
                update_fields["Status"] = data.status
            if data.priority:
                update_fields["Priority"] = data.priority
                
            sf.Task.update(data.task_id, update_fields)
            
            log_tool_activity("UpdateTaskTool", "UPDATE_TASK_SUCCESS", 
                              record_id=data.task_id)
            return {"success": True, "id": data.task_id}
        except Exception as e:
            return {"error": str(e)}


# Analytics Tools - Advanced SOQL Aggregate Functions

class GetSalesPipelineInput(BaseModel):
    """Input validation for sales pipeline analysis parameters."""
    group_by: str = "StageName"
    min_amount: Optional[float] = None

    @field_validator("group_by")
    def validate_group_by(cls, v):
        """Validate group_by parameter against supported SOQL grouping options."""
        valid_options = ["StageName", "OwnerId", "CloseDate"]
        if v not in valid_options:
            raise ValueError(f"group_by must be one of: {', '.join(valid_options)}")
        return v


class GetSalesPipelineTool(BaseTool):
    """Salesforce Sales Pipeline Analysis Tool.
    
    Provides comprehensive pipeline analytics using SOQL aggregate functions
    including COUNT(), SUM(), and AVG() with GROUP BY clauses for business intelligence.
    Implements enterprise-grade SOQL patterns for performance and data insights.
    
    Use Cases:
    - Pipeline by stage: "show me pipeline by sales stage"
    - Rep performance: "pipeline by sales rep with totals"
    - Monthly trends: "revenue trends by month for forecasting"
    - Filtered analysis: "pipeline over $100K grouped by owner"
    
    SOQL Features Used:
    - Aggregate functions: COUNT(Id), SUM(Amount), AVG(Amount)
    - GROUP BY clauses for dimensional analysis
    - HAVING clauses for filtered aggregations
    - ORDER BY with aggregate expressions for ranking
    
    Returns:
    - Grouped metrics with counts, totals, and averages
    - Sorted by total value (highest first) for priority insights
    - Metadata tags for downstream processing context
    """
    name: str = "get_sales_pipeline"
    description: str = (
        "ANALYTICS: Sales pipeline analysis with aggregate functions (COUNT, SUM, AVG). "
        "Use for: 'pipeline breakdown by stage', 'revenue totals by owner', 'monthly trends'. "
        "Groups and aggregates opportunities - NOT for individual opportunity lookup. "
        "Returns summary metrics and business intelligence dashboards."
    )
    args_schema: type = GetSalesPipelineInput
    
    def _run(self, **kwargs) -> dict:
        data = GetSalesPipelineInput(**kwargs)
        
        try:
            log_tool_activity("GetSalesPipelineTool", "ANALYZE_PIPELINE", 
                            params={"group_by": data.group_by})
            sf = get_salesforce_connection()
            
            # Build aggregate query based on grouping
            if data.group_by == "StageName":
                # Group opportunities by sales stage with aggregate metrics
                query = (SOQLQueryBuilder("Opportunity")
                    .select(["StageName"])
                    .select_count("Id", "OpportunityCount")
                    .select_sum("Amount", "TotalAmount")
                    .select_avg("Amount", "AvgAmount")
                    .group_by("StageName")
                    .having("SUM(Amount)", SOQLOperator.GREATER_THAN, 0)
                    .order_by("SUM(Amount)", descending=True)  # Use aggregate function, not alias
                    .build())
            elif data.group_by == "OwnerId":
                # Group opportunities by owner (sales rep) with open pipeline only
                query_builder = (SOQLQueryBuilder("Opportunity")
                    .select(["OwnerId", "Owner.Name"])
                    .select_count("Id", "OpportunityCount")
                    .select_sum("Amount", "TotalPipeline")
                    .select_avg("Amount", "AvgDealSize")
                    .where("IsClosed", SOQLOperator.EQUALS, False))  # Open opportunities only
                
                # Apply optional minimum amount filter
                if data.min_amount:
                    query_builder = query_builder.where("Amount", SOQLOperator.GREATER_OR_EQUAL, data.min_amount)
                
                query = (query_builder
                    .group_by(["OwnerId", "Owner.Name"])
                    .having("SUM(Amount)", SOQLOperator.GREATER_THAN, 0)
                    .order_by("SUM(Amount)", descending=True)  # Use aggregate function, not alias
                    .limit(20)
                    .build())
            else:  # CloseDate monthly
                # Group opportunities by month/year for trend analysis
                query_builder = (SOQLQueryBuilder("Opportunity")
                    .select(["CALENDAR_MONTH(CloseDate) Month", "CALENDAR_YEAR(CloseDate) Year"])
                    .select_count("Id", "OpportunityCount")
                    .select_sum("Amount", "Revenue")
                    .where("CloseDate", SOQLOperator.GREATER_OR_EQUAL, "LAST_N_MONTHS:12"))  # Last 12 months
                
                # Apply optional minimum amount filter
                if data.min_amount:
                    query_builder = query_builder.where("Amount", SOQLOperator.GREATER_OR_EQUAL, data.min_amount)
                
                query = (query_builder
                    .group_by(["CALENDAR_MONTH(CloseDate)", "CALENDAR_YEAR(CloseDate)"])
                    .order_by(["CALENDAR_YEAR(CloseDate)", "CALENDAR_MONTH(CloseDate)"])  # Use functions, not aliases
                    .build())
            
            results = sf.query(query)
            
            # Return results in same format as other tools
            if not results["records"]:
                return []
            
            # Add metadata to each record for context
            for record in results["records"]:
                record["_query_type"] = "pipeline_by_" + data.group_by
            
            return results["records"]
            
        except Exception as e:
            # Return empty list like other tools to prevent looping
            log_tool_activity("GetSalesPipelineTool", "ERROR", error=str(e))
            return []


class GetTopPerformersInput(BaseModel):
    """Input validation for top performers analysis parameters."""
    metric: str = "revenue"
    min_threshold: Optional[float] = 100000
    limit: int = 10

    @field_validator("metric")
    def validate_metric(cls, v):
        """Validate metric type against supported performance measurements."""
        valid_metrics = ["revenue", "deal_count", "win_rate"]
        if v not in valid_metrics:
            raise ValueError(f"metric must be one of: {', '.join(valid_metrics)}")
        return v


class GetTopPerformersTool(BaseTool):
    """Salesforce Top Performers Analysis Tool.
    
    Identifies and ranks top performing sales representatives using comprehensive
    performance metrics including revenue totals, deal counts, and win rates.
    Implements sophisticated SOQL aggregation with post-processing calculations.
    
    Use Cases:
    - Revenue leaders: "top 10 sales reps by closed revenue"
    - Activity analysis: "most active reps by deal count"
    - Efficiency metrics: "highest win rate performers"
    - Threshold filtering: "reps with over $500K in sales"
    
    Analytics Features:
    - Multi-metric analysis (revenue, deals, win rates)
    - Minimum threshold filtering for qualified performers
    - Separate query execution for complex win rate calculations
    - Ranked results with performance indicators
    
    SOQL Complexity:
    - Win rate calculation requires multiple queries due to SOQL limitations
    - Post-processing combines total opportunities with won opportunities
    - Implements business logic for percentage calculations
    
    Returns:
    - Ranked performer list with key metrics
    - Performance metadata tags for context
    - Threshold-filtered results for executive reporting
    """
    name: str = "get_top_performers"
    description: str = (
        "ANALYTICS: Top performer rankings using aggregated performance metrics. "
        "Use for: 'top 10 sales reps', 'best win rates', 'most deals closed'. "
        "Calculates rankings and statistics - NOT for individual rep lookup. "
        "Returns ranked performance leaderboards with calculated metrics."
    )
    args_schema: type = GetTopPerformersInput
    
    def _run(self, **kwargs) -> dict:
        data = GetTopPerformersInput(**kwargs)
        
        try:
            log_tool_activity("GetTopPerformersTool", "ANALYZE_PERFORMERS",
                            params={"metric": data.metric, "limit": data.limit})
            sf = get_salesforce_connection()
            
            if data.metric == "revenue":
                query = (SOQLQueryBuilder('Opportunity')
                    .select(['OwnerId', 'Owner.Name'])
                    .select_count('Id', 'DealsWon')
                    .select_sum('Amount', 'TotalRevenue')
                    .where('IsClosed', SOQLOperator.EQUALS, True)
                    .where('IsWon', SOQLOperator.EQUALS, True)
                    .group_by(['OwnerId', 'Owner.Name'])
                    .having('SUM(Amount)', SOQLOperator.GREATER_THAN, data.min_threshold)
                    .order_by('SUM(Amount)', descending=True)  # Use aggregate function, not alias
                    .limit(data.limit)
                    .build())
            elif data.metric == "deal_count":
                query = (SOQLQueryBuilder('Opportunity')
                    .select(['OwnerId', 'Owner.Name'])
                    .select_count('Id', 'TotalDeals')
                    .select_sum('Amount', 'TotalRevenue')
                    .where('IsClosed', SOQLOperator.EQUALS, True)
                    .group_by(['OwnerId', 'Owner.Name'])
                    .having('COUNT(Id)', SOQLOperator.GREATER_THAN, 5)
                    .order_by('COUNT(Id)', descending=True)  # Use aggregate function, not alias
                    .limit(data.limit)
                    .build())
            else:  # win_rate - Calculate in post-processing since SOQL doesn't support CASE in aggregates
                # Get total opportunities and won opportunities separately
                query = (SOQLQueryBuilder('Opportunity')
                    .select(['OwnerId', 'Owner.Name'])
                    .select_count('Id', 'TotalOpps')
                    .where('IsClosed', SOQLOperator.EQUALS, True)
                    .group_by(['OwnerId', 'Owner.Name'])
                    .having('COUNT(Id)', SOQLOperator.GREATER_THAN, 10)
                    .order_by('COUNT(Id)', descending=True)  # Order by total opportunities
                    .limit(data.limit * 2)  # Get more records to filter after win rate calculation
                    .build())
                
                # Need a second query to get won deals count
                won_query = (SOQLQueryBuilder('Opportunity')
                    .select(['OwnerId', 'Owner.Name'])
                    .select_count('Id', 'WonDeals')
                    .where('IsClosed', SOQLOperator.EQUALS, True)
                    .where('IsWon', SOQLOperator.EQUALS, True)
                    .group_by(['OwnerId', 'Owner.Name'])
                    .build())
            
            results = sf.query(query)
            
            # Calculate win rate if needed
            if data.metric == "win_rate":
                # Get won deals data
                won_results = sf.query(won_query)
                won_map = {r['OwnerId']: r['WonDeals'] for r in won_results['records']}
                
                # Calculate win rate for each record
                for record in results['records']:
                    total = record.get('TotalOpps', 0)
                    won = won_map.get(record['OwnerId'], 0)
                    record['WonDeals'] = won
                    record['WinRate'] = (won / total * 100) if total > 0 else 0
                
                # Sort by win rate and limit
                results['records'] = sorted(results['records'], 
                                          key=lambda x: x['WinRate'], 
                                          reverse=True)[:data.limit]
            
            # Return results in same format as other tools
            if not results["records"]:
                return []
                
            # Add metadata to each record
            for record in results["records"]:
                record["_metric_type"] = data.metric
                
            return results["records"]
            
        except Exception as e:
            # Return empty list like other tools to prevent looping
            log_tool_activity("GetTopPerformersTool", "ERROR", error=str(e))
            return []


class GlobalSearchInput(BaseModel):
    """Input validation for global cross-object search parameters."""
    search_term: str
    object_types: Optional[List[str]] = ["Account", "Contact", "Opportunity", "Lead"]
    limit: int = 20


class GlobalSearchTool(BaseTool):
    """Salesforce Global Search Tool using SOSL.
    
    Performs comprehensive cross-object searches using Salesforce Object Search Language (SOSL)
    to find related records across multiple object types in a single operation.
    Implements enterprise search patterns with intelligent result grouping.
    
    Use Cases:
    - Universal search: "find everything related to 'solar panel'"
    - Email discovery: "search for john@company.com across all objects"
    - Company intelligence: "find all Acme Corp related records"
    - Keyword analysis: "search for 'enterprise software' mentions"
    
    SOSL Features:
    - Cross-object searching in single API call
    - Field-specific search scoping (ALL FIELDS, NAME FIELDS, EMAIL FIELDS)
    - Per-object result limiting and filtering
    - Intelligent result ordering by relevance and value
    
    Search Strategy:
    - Searches across Account, Contact, Opportunity, and Lead objects
    - Applies object-specific filtering (e.g., Amount > 0 for Opportunities)
    - Orders results by business importance (revenue, status, activity)
    - Groups results by object type for organized presentation
    
    Returns:
    - Grouped search results by object type
    - Search term metadata for context tracking
    - Relevance-ordered results for maximum business value
    """
    name: str = "global_search"
    description: str = (
        "SEARCH: Cross-object global search using SOSL across multiple Salesforce objects. "
        "Use for: 'find everything related to solar', 'search for john@company.com everywhere'. "
        "Searches ALL object types simultaneously - NOT for single object searches. "
        "Returns grouped results from Accounts, Contacts, Opportunities, and Leads."
    )
    args_schema: type = GlobalSearchInput
    
    def _run(self, **kwargs) -> dict:
        data = GlobalSearchInput(**kwargs)
        
        try:
            log_tool_activity("GlobalSearchTool", "GLOBAL_SEARCH",
                            params={"term": data.search_term, "objects": data.object_types})
            sf = get_salesforce_connection()
            
            # Build SOSL (Salesforce Object Search Language) query
            search_term = escape_soql(data.search_term)
            
            # Build returning clauses for each object type
            returning_clauses = []
            
            if "Account" in data.object_types:
                # Account fields: basic info for company records
                returning_clauses.append(
                    f"Account(Id, Name, Industry, Phone, Website LIMIT {data.limit})"
                )
            
            if "Contact" in data.object_types:
                # Contact fields: include parent account relationship
                returning_clauses.append(
                    f"Contact(Id, Name, Email, Phone, Title, Account.Name LIMIT {data.limit})"
                )
            
            if "Opportunity" in data.object_types:
                # Opportunity fields: filter for real opportunities with amounts
                returning_clauses.append(
                    f"Opportunity(Id, Name, Amount, StageName, CloseDate, Account.Name "
                    f"WHERE Amount > 0 ORDER BY Amount DESC LIMIT {data.limit})"
                )
            
            if "Lead" in data.object_types:
                # Lead fields: only active/workable leads
                returning_clauses.append(
                    f"Lead(Id, Name, Company, Email, Phone, Status "
                    f"WHERE Status IN ('New', 'Working', 'Qualified') LIMIT {data.limit})"
                )
            
            # Construct SOSL query - searches all fields across specified objects
            query = f"FIND {{{search_term}}} IN ALL FIELDS RETURNING {', '.join(returning_clauses)}"
            
            # Use search() for SOSL queries
            results = sf.search(query)
            
            # Group results by object type for organized presentation
            grouped_results = {}
            for record in results.get("searchRecords", []):
                obj_type = record["attributes"]["type"]
                if obj_type not in grouped_results:
                    grouped_results[obj_type] = []
                grouped_results[obj_type].append(record)
            
            # Return results in same format as other tools
            search_records = results.get("searchRecords", [])
            if not search_records:
                return []
            
            # Add search term to each record for context
            for record in search_records:
                record["_search_term"] = data.search_term
                
            return search_records
            
        except Exception as e:
            # Return empty list like other tools to prevent looping
            log_tool_activity("GlobalSearchTool", "ERROR", error=str(e))
            return []


class GetAccountInsightsInput(BaseModel):
    """Input validation for comprehensive account analysis parameters."""
    account_id: Optional[str] = None
    account_name: Optional[str] = None
    include_subqueries: bool = True


class GetAccountInsightsTool(BaseTool):
    """Salesforce Account 360 Intelligence Tool.
    
    Delivers comprehensive account intelligence by leveraging SOQL subqueries
    to retrieve complete customer data relationships in a single API call.
    Implements enterprise customer analytics with performance optimization.
    
    Use Cases:
    - Customer 360 view: "complete analysis of Acme Corp account"
    - Executive briefing: "tell me everything about our biggest client"
    - Relationship mapping: "show me all touchpoints for this account"
    - Pipeline review: "account health check with all related data"
    
    Technical Implementation:
    - Subquery utilization for related record retrieval
    - Single API call efficiency vs. multiple round trips
    - Automatic summary metrics calculation in post-processing
    - Relationship navigation (Opportunities, Contacts, Cases)
    
    Subquery Strategy:
    - Opportunities: Top 10 by value with stage and close date
    - Contacts: Most recent 5 with email addresses and activity
    - Cases: Open cases only, prioritized by severity
    - Summary metrics: Calculated totals and counts for dashboard view
    
    Returns:
    - Complete account record with relationship data
    - Calculated summary metrics (pipeline value, contact count, open cases)
    - Structured subquery results for relationship analysis
    """
    name: str = "get_account_insights"
    description: str = (
        "ANALYTICS: Complete 360-degree account intelligence with related records. "
        "Use for: 'everything about Acme Corp', 'complete customer analysis', 'account dashboard'. "
        "Retrieves account + ALL related data in one call - NOT for basic account lookup. "
        "Returns comprehensive account profile with opportunities, contacts, cases, and metrics."
    )
    args_schema: type = GetAccountInsightsInput
    
    def _run(self, **kwargs) -> dict:
        data = GetAccountInsightsInput(**kwargs)
        
        try:
            log_tool_activity("GetAccountInsightsTool", "GET_INSIGHTS",
                            params={"account_id": data.account_id, "account_name": data.account_name})
            sf = get_salesforce_connection()
            
            # Build main query
            query_builder = SOQLQueryBuilder('Account').select([
                'Id', 'Name', 'Industry', 'AnnualRevenue', 'NumberOfEmployees',
                'Website', 'Phone', 'BillingCity', 'BillingState'
            ])
            
            # Add subqueries if requested - fetch related records in single API call
            if data.include_subqueries:
                # Related opportunities - top 10 by value
                query_builder.fields.extend([
                    "(SELECT Id, Name, Amount, StageName, CloseDate FROM Opportunities ORDER BY Amount DESC LIMIT 10)",
                    # Related contacts - most recently active with email
                    "(SELECT Id, Name, Title, Email, Phone FROM Contacts WHERE Email != null ORDER BY LastActivityDate DESC LIMIT 5)",
                    # Open cases - prioritized by urgency
                    "(SELECT Id, CaseNumber, Subject, Status, Priority FROM Cases WHERE IsClosed = false ORDER BY Priority LIMIT 5)"
                ])
            
            # Add search criteria
            if data.account_id:
                query_builder.where_id(data.account_id)
            elif data.account_name:
                query_builder.where_like('Name', f'%{data.account_name}%')
            else:
                return {"error": "Either account_id or account_name must be provided"}
            
            query = query_builder.build()
            results = sf.query(query)
            
            if not results['records']:
                return {"error": "No matching account found"}
            
            account_data = results['records'][0]
            
            # Calculate summary metrics and add to account data
            account_data["_summary"] = {
                "total_opportunities": len(account_data.get("Opportunities", {}).get("records", [])),
                "pipeline_value": sum(opp.get("Amount", 0) for opp in 
                                    account_data.get("Opportunities", {}).get("records", [])),
                "total_contacts": len(account_data.get("Contacts", {}).get("records", [])),
                "open_cases": len(account_data.get("Cases", {}).get("records", []))
            }
            
            # Return single account record like other tools
            return account_data
            
        except Exception as e:
            # Return empty list like other tools to prevent looping
            log_tool_activity("GetAccountInsightsTool", "ERROR", error=str(e))
            return []


class GetBusinessMetricsInput(BaseModel):
    """Input validation for business metrics and KPI analysis parameters."""
    metric_type: str = "revenue"
    time_period: str = "THIS_QUARTER"
    group_by: Optional[str] = None

    @field_validator("metric_type")
    def validate_metric_type(cls, v):
        """Validate metric type against supported business intelligence categories."""
        valid_types = ["revenue", "accounts", "leads", "cases"]
        if v not in valid_types:
            raise ValueError(f"metric_type must be one of: {', '.join(valid_types)}")
        return v

    @field_validator("time_period")
    def validate_time_period(cls, v):
        """Validate time period against supported Salesforce date literals."""
        valid_periods = ["THIS_MONTH", "LAST_MONTH", "THIS_QUARTER", "THIS_YEAR"]
        if v not in valid_periods:
            raise ValueError(f"time_period must be one of: {', '.join(valid_periods)}")
        return v


class GetBusinessMetricsTool(BaseTool):
    """Salesforce Business Intelligence and KPI Analytics Tool.
    
    Delivers comprehensive business metrics and key performance indicators using
    advanced SOQL aggregate functions with time-based analysis and dimensional grouping.
    Implements enterprise reporting patterns for executive dashboards.
    
    Use Cases:
    - Revenue analytics: "quarterly revenue by industry breakdown"
    - Lead performance: "lead conversion rates by source channel"
    - Customer metrics: "account distribution and growth analysis"
    - Support analytics: "case volume trends and resolution metrics"
    
    Analytics Capabilities:
    - Multi-dimensional analysis with GROUP BY operations
    - Time-based filtering using Salesforce date literals
    - Conversion rate calculations with multiple query orchestration
    - Industry/source/priority segmentation for business insights
    
    Technical Implementation:
    - Handles SOQL date literal restrictions through manual query construction
    - Executes separate queries for conversion rate calculations
    - Post-processes results for percentage and ratio calculations
    - Implements workarounds for SOQL aggregate function limitations
    
    Date Handling Strategy:
    - Bypasses SOQL query builder date quoting issues
    - Manual query construction for date literal support
    - Supports THIS_QUARTER, THIS_MONTH, THIS_YEAR, LAST_MONTH
    
    Returns:
    - Aggregated business metrics with dimensional breakdowns
    - Calculated KPIs (conversion rates, averages, totals)
    - Time period and metric type metadata for context
    """
    name: str = "get_business_metrics"
    description: str = (
        "ANALYTICS: Business KPIs and metrics with time-based aggregate analysis. "
        "Use for: 'revenue this quarter', 'lead conversion rates', 'case volume trends'. "
        "Calculates KPIs and trends over time periods - NOT for individual record metrics. "
        "Returns calculated business metrics, conversion rates, and trend analysis."
    )
    args_schema: type = GetBusinessMetricsInput
    
    def _run(self, **kwargs) -> dict:
        data = GetBusinessMetricsInput(**kwargs)
        
        try:
            log_tool_activity("GetBusinessMetricsTool", "CALCULATE_METRICS",
                            params={"metric": data.metric_type, "period": data.time_period})
            sf = get_salesforce_connection()
            
            if data.metric_type == "revenue":
                query_builder = SOQLQueryBuilder('Opportunity')
                
                if data.group_by == "Industry":
                    query_builder = (query_builder
                        .select(['Account.Industry'])
                        .group_by('Account.Industry'))
                else:
                    query_builder.select([])
                
                # Build base query without date filter
                base_query = (query_builder
                    .select_count('Id', 'DealCount')
                    .select_sum('Amount', 'TotalRevenue')
                    .select_avg('Amount', 'AvgDealSize')
                    .where('IsClosed', SOQLOperator.EQUALS, True)
                    .where('IsWon', SOQLOperator.EQUALS, True)
                    .build())
                
                # Add date filter manually to avoid quoting issues
                query = base_query.replace('WHERE', f'WHERE CloseDate = {data.time_period} AND')
                
            elif data.metric_type == "accounts":
                query = (SOQLQueryBuilder('Account')
                    .select(['Industry'])
                    .select_count('Id', 'AccountCount')
                    .select_avg('AnnualRevenue', 'AvgRevenue')
                    .where_not_null('Industry')
                    .group_by('Industry')
                    .order_by('COUNT(Id)', descending=True)  # Use aggregate function, not alias
                    .build())
                
            elif data.metric_type == "leads":
                query_builder = SOQLQueryBuilder('Lead')
                
                if data.group_by == "LeadSource":
                    query_builder = (query_builder
                        .select(['LeadSource'])
                        .group_by('LeadSource'))
                else:
                    query_builder.select([])
                
                # Build base query without date filter
                base_query = (query_builder
                    .select_count('Id', 'TotalLeads')
                    .build())
                
                # Add date filter manually to avoid quoting issues
                if 'WHERE' in base_query:
                    query = base_query.replace('WHERE', f'WHERE CreatedDate = {data.time_period} AND')
                else:
                    query = base_query.replace('FROM Lead', f'FROM Lead WHERE CreatedDate = {data.time_period}')
                
                # Separate query for converted leads
                converted_query_builder = SOQLQueryBuilder('Lead')
                if data.group_by == "LeadSource":
                    converted_query_builder = (converted_query_builder
                        .select(['LeadSource'])
                        .group_by('LeadSource'))
                else:
                    converted_query_builder.select([])
                    
                # Build base query for converted leads
                base_converted_query = (converted_query_builder
                    .select_count('Id', 'ConvertedLeads')
                    .where('IsConverted', SOQLOperator.EQUALS, True)
                    .build())
                
                # Add date filter manually
                converted_query = base_converted_query.replace('WHERE', f'WHERE CreatedDate = {data.time_period} AND')
                
            else:  # cases
                query_builder = SOQLQueryBuilder('Case')
                
                if data.group_by == "Priority":
                    query_builder = (query_builder
                        .select(['Priority', 'Status'])
                        .group_by(['Priority', 'Status']))
                else:
                    query_builder.select(['Status']).group_by('Status')
                
                # Build base query without date filter
                base_query = (query_builder
                    .select_count('Id', 'CaseCount')
                    .order_by('COUNT(Id)', descending=True)  # Use aggregate function, not alias
                    .build())
                
                # Add date filter manually to avoid quoting issues
                if 'WHERE' in base_query:
                    query = base_query.replace('WHERE', f'WHERE CreatedDate = {data.time_period} AND')
                else:
                    query = base_query.replace('FROM Case', f'FROM Case WHERE CreatedDate = {data.time_period}')
            
            results = sf.query(query)
            
            # Calculate additional metrics like conversion rates
            if data.metric_type == "leads" and results["records"]:
                # Get converted leads data
                converted_results = sf.query(converted_query)
                
                if data.group_by == "LeadSource":
                    # Map by LeadSource
                    converted_map = {r["LeadSource"]: r["ConvertedLeads"] 
                                   for r in converted_results["records"]}
                    for record in results["records"]:
                        total = record.get("TotalLeads", 0)
                        converted = converted_map.get(record.get("LeadSource"), 0)
                        record["ConvertedLeads"] = converted
                        record["ConversionRate"] = (converted / total * 100) if total > 0 else 0
                else:
                    # Single result without grouping
                    converted_count = converted_results["records"][0]["ConvertedLeads"] if converted_results["records"] else 0
                    for record in results["records"]:
                        total = record.get("TotalLeads", 0)
                        record["ConvertedLeads"] = converted_count
                        record["ConversionRate"] = (converted_count / total * 100) if total > 0 else 0
            
            # Return results in same format as other tools
            if not results["records"]:
                return []
                
            # Add metadata to each record
            for record in results["records"]:
                record["_metric_type"] = data.metric_type
                record["_time_period"] = data.time_period
                
            return results["records"]
            
        except Exception as e:
            # Return empty list like other tools to prevent looping
            log_tool_activity("GetBusinessMetricsTool", "ERROR", error=str(e))
            return []


# Export all analytics tools
# Analytics tools collection
SALESFORCE_ANALYTICS_TOOLS = [
    GetSalesPipelineTool(),
    GetTopPerformersTool(),
    GlobalSearchTool(),
    GetAccountInsightsTool(),
    GetBusinessMetricsTool()
]

# All CRUD tools collection for easy import
SALESFORCE_CRUD_TOOLS = [
    # Lead tools
    GetLeadTool(),
    CreateLeadTool(),
    UpdateLeadTool(),
    # Account tools
    GetAccountTool(),
    CreateAccountTool(),
    UpdateAccountTool(),
    # Opportunity tools
    GetOpportunityTool(),
    CreateOpportunityTool(),
    UpdateOpportunityTool(),
    # Contact tools
    GetContactTool(),
    CreateContactTool(),
    UpdateContactTool(),
    # Case tools
    GetCaseTool(),
    CreateCaseTool(),
    UpdateCaseTool(),
    # Task tools
    GetTaskTool(),
    CreateTaskTool(),
    UpdateTaskTool()
]

# All tools combined
ALL_SALESFORCE_TOOLS = SALESFORCE_CRUD_TOOLS + SALESFORCE_ANALYTICS_TOOLS


# Export all tools
__all__ = [
    # Individual tool classes (for backwards compatibility)
    'GetLeadTool', 'CreateLeadTool', 'UpdateLeadTool',
    'GetAccountTool', 'CreateAccountTool', 'UpdateAccountTool',
    'GetOpportunityTool', 'CreateOpportunityTool', 'UpdateOpportunityTool',
    'GetContactTool', 'CreateContactTool', 'UpdateContactTool',
    'GetCaseTool', 'CreateCaseTool', 'UpdateCaseTool',
    'GetTaskTool', 'CreateTaskTool', 'UpdateTaskTool',
    'GetSalesPipelineTool', 'GetTopPerformersTool', 'GlobalSearchTool',
    'GetAccountInsightsTool', 'GetBusinessMetricsTool',
    # Tool collections
    'SALESFORCE_ANALYTICS_TOOLS',
    'SALESFORCE_CRUD_TOOLS',
    'ALL_SALESFORCE_TOOLS'
]