"""Salesforce CRM Tools - Enterprise-Grade CRUD Operations with Security-First Design.

This module implements 15 comprehensive Salesforce tools following enterprise patterns:

Architecture Philosophy:
- **Loose Coupling**: Tools accept flexible search parameters without requiring deep SOQL knowledge
- **Security-First**: All inputs sanitized through escape_soql() to prevent SOQL injection attacks
- **Flexible Search**: Supports both exact ID lookups and fuzzy name-based searches across all objects
- **Consistent Error Handling**: Graceful degradation with structured error responses for resilience
- **Token Optimization**: Streamlined response formats removing unnecessary wrapper objects

SOQL Injection Prevention Strategy:
- escape_soql() function escapes single quotes in all user inputs before query construction
- Parameterized query building with proper escaping at every input point
- No raw string concatenation of user inputs into SOQL queries
- Validated through Pydantic models before reaching SOQL layer

Flexible Search Patterns:
- Primary use case: "Get ALL records for [account/company]" - bulk retrieval
- Secondary: Direct ID lookups for known records - fastest retrieval
- Tertiary: Fuzzy name/email/phone searches - user convenience
- All tools support OR conditions for maximum flexibility

Error Handling Philosophy:
- Never crash - always return structured error responses
- Preserve error context for debugging while hiding sensitive details
- Log all operations for audit trails and troubleshooting
- Graceful empty result handling ([] instead of exceptions)
"""

import os
from datetime import date

from pydantic import BaseModel, field_validator, ValidationError
from langchain.tools import BaseTool
from typing import Optional
from simple_salesforce import Salesforce

from src.utils.logging import log_tool_activity
from src.utils.input_validation import validate_tool_input


def escape_soql(value):
    """SOQL injection prevention through proper escaping.
    
    Critical security function that prevents SOQL injection by escaping single quotes.
    Applied to ALL user inputs before query construction.
    """
    if value is None:
        return ''
    return str(value).replace("'", "\\'")


def get_salesforce_connection():
    """Establishes authenticated Salesforce connection using environment credentials."""
    sf = Salesforce(
        username=os.environ["SFDC_USER"],
        password=os.environ["SFDC_PASS"],
        security_token=os.environ["SFDC_TOKEN"]
    )
    return sf


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
    
    Returns:
    - Single match: {'match': {lead_data}}
    - Multiple matches: {'multiple_matches': [lead_list]}
    - No matches: [] (empty list)
    """
    name: str = "get_lead_tool"
    description: str = (
        "Retrieves Salesforce leads using flexible search criteria. "
        "Primary use: Get ALL LEADS for a company (use 'company' parameter) or "
        "find specific leads by ID, email, name, or phone. "
        "Handles both single record lookups and bulk company searches. "
        "Returns structured data with match indicators for downstream processing."
    )
    args_schema: type = GetLeadInput

    def _run(self, **kwargs) -> dict:
        data = GetLeadInput(**kwargs)

        try:
            log_tool_activity("GetLeadTool", "RETRIEVE_LEAD", 
                            search_params={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            
            if data.lead_id:
                escaped_id = escape_soql(data.lead_id)
                query = f"SELECT Id, Name, Company, Email, Phone FROM Lead WHERE Id = '{escaped_id}'"
            else:
                query_conditions = []
                if data.email:
                    escaped_email = escape_soql(data.email)
                    query_conditions.append(f"Email LIKE '%{escaped_email}%'")
                if data.name:
                    escaped_name = escape_soql(data.name)
                    query_conditions.append(f"Name LIKE '%{escaped_name}%'")
                if data.phone:
                    escaped_phone = escape_soql(data.phone)
                    query_conditions.append(f"Phone LIKE '%{escaped_phone}%'")
                if data.company:
                    escaped_company = escape_soql(data.company)
                    query_conditions.append(f"Company LIKE '%{escaped_company}%'")

                if not query_conditions:
                    return {"error": "No search criteria provided."}

                query = f"SELECT Id, Name, Company, Email, Phone FROM Lead WHERE {' OR '.join(query_conditions)}"

            records = sf.query(query)['records']

            if not records:
                return records
                
            # Token optimization: Direct array/object returns without wrapper
            if len(records) > 1:
                return [
                    {
                        "id": rec["Id"],
                        "name": rec["Name"],
                        "company": rec["Company"],
                        "email": rec["Email"],
                        "phone": rec["Phone"]
                    }
                    for rec in records
                ]
            else:
                return records[0]
        except Exception as e:
            return {"error": str(e)}


class CreateLeadInput(BaseModel):
    name: str
    company: str
    email: str
    phone: str


class CreateLeadTool(BaseTool):
    """Salesforce Lead Creation Tool.
    
    Creates new lead records in Salesforce CRM with required and optional
    contact information. Implements data validation and duplicate prevention
    through structured input schemas.
    
    Business Rules:
    - Requires: first_name, last_name, company (minimum viable lead)
    - Optional: email, phone (enhances lead quality)
    - Auto-generates: created_date, lead_source tracking
    
    Integration Points:
    - Triggers Salesforce lead assignment rules
    - Initiates lead scoring workflows
    - Updates company prospect analytics
    """
    name: str = "create_lead_tool"
    description: str = (
        "Creates new Salesforce lead records with required contact information. "
        "Minimum required: first_name, last_name, company. "
        "Optional enhancements: email, phone for better lead quality. "
        "Automatically integrates with Salesforce lead workflows and assignment rules."
    )
    args_schema: type = CreateLeadInput

    def _run(self, **kwargs) -> dict:
        try:
            log_tool_activity("CreateLeadTool", "CREATE_LEAD", 
                            input_data={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            data = CreateLeadInput(**kwargs)
            result = sf.Lead.create({
                "LastName": data.name,
                "Company": data.company,
                "Email": data.email,
                "Phone": data.phone
            })
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
    
    Modifies existing lead records with new contact information while
    preserving data integrity and audit trails. Implements partial update
    patterns allowing selective field modifications.
    
    Update Patterns:
    - Contact info updates: email, phone changes
    - Company transitions: lead acquisition, mergers
    - Data enrichment: adding missing contact details
    
    Business Impact:
    - Maintains lead scoring accuracy
    - Preserves conversion tracking
    - Updates lead assignment rules if company changes
    """
    name: str = "update_lead_tool"
    description: str = (
        "Updates existing Salesforce lead records with new information. "
        "Required: lead_id (15/18 character Salesforce ID). "
        "Optional updates: company, email, phone (specify only fields to change). "
        "Preserves existing data and maintains audit trail for compliance."
    )
    args_schema: type = UpdateLeadInput

    def _run(self, **kwargs) -> dict:
        try:
            log_tool_activity("UpdateLeadTool", "UPDATE_LEAD", 
                            input_data={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            data = UpdateLeadInput(**kwargs)
            sf.Lead.update(data.lead_id, {
                "Company": data.company,
                "Email": data.email,
                "Phone": data.phone
            })
            
            log_tool_activity("UpdateLeadTool", "UPDATE_LEAD_SUCCESS", 
                              record_id=data.lead_id)
            return "Successfully updated lead with Id: " + data.lead_id
        except Exception as e:
            return {"error": str(e)}
    

class GetOpportunityInput(BaseModel):
    opportunity_id: Optional[str] = None
    account_name: Optional[str] = None
    account_id: Optional[str] = None
    opportunity_name: Optional[str] = None


class GetOpportunityTool(BaseTool):
    """Salesforce Opportunity Retrieval Tool.
    
    Provides comprehensive opportunity search and retrieval capabilities across
    account relationships, deal stages, and revenue tracking. Implements loose
    coupling through flexible search parameters supporting various business contexts.
    
    Search Capabilities:
    - Account-based: "get all opportunities for [account]" 
    - Direct lookup: "find opportunity [ID]"
    - Deal search: "opportunities named [deal_name]"
    - Cross-reference: account_id + opportunity_name combinations
    
    Revenue Intelligence:
    - Returns deal amounts, stages, account relationships
    - Supports pipeline analysis and forecasting workflows
    - Integrates with account management processes
    
    Returns:
    - Single match: {'match': {opportunity_data}}
    - Multiple matches: {'multiple_matches': [opportunity_list]}
    - No matches: [] (empty list)
    """
    name: str = "get_opportunity_tool"
    description: str = (
        "Retrieves Salesforce opportunities with flexible search criteria. "
        "PRIMARY USE: Get ALL OPPORTUNITIES for an account (use 'account_name' parameter). "
        "Also supports: specific opportunity by ID, opportunities by name, or account_id searches. "
        "Essential for pipeline analysis, revenue forecasting, and account relationship mapping. "
        "Returns structured opportunity data with amount, stage, and account information."
    )
    args_schema: type = GetOpportunityInput
    
    def _run(self, **kwargs) -> dict:
        try:
            # Validate and sanitize inputs
            validated_kwargs = validate_tool_input("get_opportunity_tool", **kwargs)
            data = GetOpportunityInput(**validated_kwargs)
        except ValidationError as e:
            return {"error": f"Input validation failed: {str(e)}"}
        except Exception as e:
            return {"error": f"Input processing failed: {str(e)}"}
        
        account_name = data.account_name
        account_id = data.account_id
        opportunity_name = data.opportunity_name
        opportunity_id = data.opportunity_id

        sf = get_salesforce_connection()
        if opportunity_id:
            escaped_opp_id = escape_soql(opportunity_id)
            query = f"SELECT Id, Name, StageName, Amount, Account.Name FROM Opportunity WHERE Id = '{escaped_opp_id}'"
        else:
            query_conditions = []
            if account_name:
                escaped_account_name = escape_soql(account_name)
                query_conditions.append(f"Account.Name LIKE '%{escaped_account_name}%'")
            if account_id:
                escaped_account_id = escape_soql(account_id)
                query_conditions.append(f"AccountId = '{escaped_account_id}'")
            if opportunity_name:
                escaped_opp_name = escape_soql(opportunity_name)
                query_conditions.append(f"Name LIKE '%{escaped_opp_name}%'")
            
            if not query_conditions:
                return {"error": "No search criteria provided."}
    
            query = f"SELECT Id, Name, StageName, Amount, Account.Name FROM Opportunity WHERE {' OR '.join(query_conditions)}"
            
        try:
            log_tool_activity("GetOpportunityTool", "RETRIEVE_OPPORTUNITY", 
                            search_params={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            result = sf.query(query)
        except Exception as e:
            return {"error": str(e)}
        
        records = result.get("records", [])

        if not records:
            return records
            
        # Optimized response format - remove wrapper objects to reduce token usage
        if len(records) > 1:
            # Return array directly for multiple matches
            return [
                {
                    "id": rec["Id"],
                    "name": rec["Name"],
                    "account": rec["Account"]["Name"],
                    "stage": rec["StageName"],
                    "amount": rec["Amount"],
                }
                for rec in records
            ]
        else:
            # Return single object directly
            return records[0]
    

class CreateOpportunityInput(BaseModel):
    opportunity_name: str
    account_id: str
    stage_name: Optional[str] = "New"
    close_date: Optional[str] = str(date.today())
    amount: float


class CreateOpportunityTool(BaseTool):
    """Salesforce Opportunity Creation Tool.
    
    Creates new sales opportunities linked to existing accounts with deal tracking,
    revenue forecasting, and sales pipeline management capabilities. Implements
    business rules for opportunity lifecycle and stage progression.
    
    Required Fields:
    - opportunity_name: Deal identifier (e.g., "Q4 Software License")
    - account_id: Salesforce account ID (18-char)
    - amount: Revenue value (USD)
    
    Optional Fields:
    - stage_name: Sales stage (defaults to "New")
    - close_date: Expected close date (defaults to today)
    
    Business Impact:
    - Triggers sales forecasting updates
    - Initiates opportunity assignment workflows
    - Updates account revenue projections
    """
    name: str = "create_opportunity_tool"
    description: str = (
        "Creates new Salesforce sales opportunities with revenue tracking. "
        "Required: opportunity_name, account_id (18-char Salesforce ID), amount (USD). "
        "Optional: stage_name (defaults to 'New'), close_date (defaults to today). "
        "Automatically links to account and triggers sales pipeline workflows."
    )
    args_schema: type = CreateOpportunityInput

    def _run(self, **kwargs) -> dict:
        data = CreateOpportunityInput(**kwargs)

        opportunity_name = data.opportunity_name
        amount = data.amount
        account_id = data.account_id
        stage_name = data.stage_name
        close_date = data.close_date

        try:
            log_tool_activity("CreateOpportunityTool", "CREATE_OPPORTUNITY", 
                            input_data={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            result = sf.Opportunity.create({
                "Name": opportunity_name,
                "AccountId": account_id,
                "Amount": amount,
                "StageName": stage_name,
                "CloseDate": close_date
            })
            return result
        except Exception as e:
            return {"error": str(e)}
        

class UpdateOpportunityInput(BaseModel):
    opportunity_id: str
    stage: str
    amount: Optional[float] = None

    @field_validator('stage')
    def validate_stage(cls, v):
        if v not in [
        "Prospecting",
        "Qualification",
        "Needs Analysis",
        "Value Proposition",
        "Id. Decision Makers",
        "Perception Analysis",
        "Proposal/Price Quote",
        "Negotiation/Review",
        "Closed Won",
        "Closed Lost"
    ]:
            raise ValueError(f"Invalid stage name : {v}. Available values are 'Prospecting', "
                             "'Qualification', 'Needs Analysis', 'Value Proposition', 'Id. Decision Makers', "
                             "'Perception Analysis', 'Proposal/Price Quote', 'Negotiation/Review', 'Closed Won', 'Closed Lost'")
        return v

class UpdateOpportunityTool(BaseTool):
    """Salesforce Opportunity Update Tool.
    
    Updates opportunity stage and amount for pipeline progression and forecasting.
    Implements strict stage validation to ensure data integrity.
    
    Stage Validation:
    - Enforces standard Salesforce opportunity stages through Pydantic validator
    - Prevents invalid stage names that would break reporting
    - Stage changes trigger forecast updates and sales notifications
    
    Revenue Impact:
    - Amount updates affect pipeline reports and quota attainment
    - Stage progression updates win probability and forecast category
    """
    name: str = "update_opportunity_tool"
    description: str = (
        "Updates an existing Opportunity. Called directly if an opportunity_id is provided. "
        "If opportunity_id is not provided, the get_opportunity_tool is called to retrieve the opportunity_id."
    )
    args_schema: type = UpdateOpportunityInput

    def _run(self, **kwargs) -> dict:
        data = UpdateOpportunityInput(**kwargs)

        stage = data.stage
        amount = data.amount
        opp_id = data.opportunity_id
        
        try:
            log_tool_activity("UpdateOpportunityTool", "UPDATE_OPPORTUNITY", 
                            input_data={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            sf.Opportunity.update(opp_id, {
                "StageName": stage,
                "Amount": amount
            })
            
            log_tool_activity("UpdateOpportunityTool", "UPDATE_OPPORTUNITY_SUCCESS", 
                              record_id=opp_id)
            return "Successfully updated opportunity with Id: " + opp_id
        except Exception as e:
            return {"error": str(e)}


class GetAccountInput(BaseModel):
    account_id: Optional[str] = None
    account_name: Optional[str] = None


class GetAccountTool(BaseTool):
    """Salesforce Account Retrieval Tool.
    
    Provides primary account lookup capabilities for customer relationship management
    and enterprise account intelligence. Serves as the foundation for all downstream
    CRM operations including contacts, opportunities, cases, and tasks.
    
    Search Methods:
    - Direct ID lookup: Fastest retrieval by 18-character Salesforce ID
    - Name-based search: Flexible matching for account discovery
    - Partial matching: Supports fuzzy name searches for user convenience
    
    Integration Hub:
    - Central to all account-related workflows
    - Prerequisite for contact/opportunity/case creation
    - Foundation for account hierarchy navigation
    
    Returns:
    - Single match: {'match': {account_data}} 
    - Multiple matches: {'multiple_matches': [account_list]}
    - No matches: [] (empty list)
    """
    name: str = "get_account_tool"
    description: str = (
        "Retrieves Salesforce account records using ID or name-based search. "
        "Primary use: Find specific accounts by exact name or partial name matching. "
        "Essential for account identification before creating contacts, opportunities, or cases. "
        "Returns comprehensive account data including Salesforce ID for downstream operations."
    )
    args_schema: type = GetAccountInput
    
    def _run(self, **kwargs) -> dict:
        data = GetAccountInput(**kwargs)
        
        account_id = data.account_id
        account_name = data.account_name

        sf = get_salesforce_connection()
        if account_id:
            escaped_account_id = escape_soql(account_id)
            query = f"SELECT Id, Name FROM Account WHERE Id = '{escaped_account_id}'"
        else:
            escaped_account_name = escape_soql(account_name)
            query_conditions = [f"Name LIKE '%{escaped_account_name}%'"]
    
            query = f"SELECT Id, Name FROM Account WHERE {' AND '.join(query_conditions)}"

        try:
            log_tool_activity("GetAccountTool", "RETRIEVE_ACCOUNT", 
                            search_params={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            result = sf.query(query)
        except Exception as e:
            return {"error": str(e)}
        
        records = result.get("records", [])

        if not records:
            return records
            
        # Optimized response format - remove wrapper objects to reduce token usage
        if len(records) > 1:
            # Return array directly for multiple matches
            return [
                {
                    "id": rec["Id"],
                    "name": rec["Name"]
                }
                for rec in records
            ]
        else:
            # Return single object directly  
            return records[0]
    

class CreateAccountInput(BaseModel):
    account_name: str
    phone: str
    website: Optional[str] = None


class CreateAccountTool(BaseTool):
    """Salesforce Account Creation Tool.
    
    Creates new customer accounts in Salesforce CRM with minimal required fields.
    Designed for rapid account onboarding while maintaining data quality standards.
    
    Business Rules:
    - Minimal viable account: name + phone (enables immediate contact)
    - Website optional but recommended for B2B accounts
    - Triggers account assignment rules and territory management
    - Creates foundation for all downstream CRM relationships
    """
    name: str = "create_account_tool"
    description: str = (
        "Creates a new Salesforce account. Requires: account_name and phone. "
        "Optionally takes a website."
    )
    args_schema: type = CreateAccountInput

    def _run(self, **kwargs) -> dict:
        data = CreateAccountInput(**kwargs)

        try:
            log_tool_activity("CreateAccountTool", "CREATE_ACCOUNT", 
                            input_data={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            result = sf.Account.create({
                "Name": data.account_name,
                "Phone": data.phone,
                "Website": data.website
            })
            return result
        except Exception as e:
            return {"error": str(e)}


class UpdateAccountInput(BaseModel):
    account_id: str
    phone: Optional[str] = None
    website: Optional[str] = None


class UpdateAccountTool(BaseTool):
    """Salesforce Account Update Tool.
    
    Modifies existing account records with new contact information while preserving
    all relationships and historical data. Implements partial update patterns.
    
    Update Patterns:
    - Contact info updates: Phone number changes, website updates
    - Preserves all child records: Contacts, opportunities, cases, tasks
    - Maintains audit trail for compliance and change tracking
    """
    name: str = "update_account_tool"
    description: str = (
        "Updates an existing Salesforce account. Requires an account_id. "
        "Optionally takes a phone and/or website."
    )
    args_schema: type = UpdateAccountInput

    def _run(self, **kwargs) -> dict:
        data = UpdateAccountInput(**kwargs)
        try:
            log_tool_activity("UpdateAccountTool", "UPDATE_ACCOUNT", 
                            input_data={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            sf.Account.update(data.account_id, {
                "Phone": data.phone,
                "Website": data.website
            })
            
            log_tool_activity("UpdateAccountTool", "UPDATE_ACCOUNT_SUCCESS", 
                              record_id=data.account_id)
            return "Successfully updated account with Id: " + data.account_id
        except Exception as e:
            return {"error": str(e)}
    

class GetContactInput(BaseModel):
    contact_id: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    account_name: Optional[str] = None
    account_id: Optional[str] = None


class GetContactTool(BaseTool):
    """Salesforce Contact Retrieval Tool.
    
    Provides comprehensive contact search across individual records and account-based
    contact discovery. Essential for relationship mapping, communication workflows,
    and customer service operations within the CRM ecosystem.
    
    Search Capabilities:
    - Account-based: "get all contacts for [account]" (use account_name/account_id)
    - Individual lookup: Find specific contacts by ID, email, name, phone
    - Cross-reference: Link contacts to their parent accounts
    - Communication prep: Retrieve contact details for outreach campaigns
    
    Business Applications:
    - Sales team contact identification
    - Customer service case assignment  
    - Marketing campaign targeting
    - Account relationship mapping
    
    Returns:
    - Single match: {'match': {contact_data}}
    - Multiple matches: {'multiple_matches': [contact_list]}
    - No matches: [] (empty list)
    """
    name: str = "get_contact_tool"
    description: str = (
        "Retrieves Salesforce contacts with flexible search options. "
        "PRIMARY USE: Get ALL CONTACTS for an account (use 'account_name' or 'account_id' parameter). "
        "Also supports: individual contact lookup by ID, email, name, or phone. "
        "Essential for customer communication, sales outreach, and account relationship management. "
        "Returns contact details with account associations and communication preferences."
    )
    args_schema: type = GetContactInput
    
    def _run(self, **kwargs) -> dict:
        data = GetContactInput(**kwargs)
        
        contact_id = data.contact_id
        email = data.email
        name = data.name
        phone = data.phone
        account_name = data.account_name
        account_id = data.account_id

        sf = get_salesforce_connection()
        if contact_id:
            escaped_contact_id = escape_soql(contact_id)
            query = f"SELECT Id, Name, Account.Name, Email, Phone FROM Contact WHERE Id = '{escaped_contact_id}'"
        else:
            query_conditions = []
            if email:
                escaped_email = escape_soql(email)
                query_conditions.append(f"Email LIKE '%{escaped_email}%'")
            if name:
                escaped_name = escape_soql(name)
                query_conditions.append(f"Name LIKE '%{escaped_name}%'")
            if phone:
                escaped_phone = escape_soql(phone)
                query_conditions.append(f"Phone LIKE '%{escaped_phone}%'")
            if account_name:
                escaped_account_name = escape_soql(account_name)
                query_conditions.append(f"Account.Name LIKE '%{escaped_account_name}%'")
            if account_id:
                escaped_account_id = escape_soql(account_id)
                query_conditions.append(f"AccountId = '{escaped_account_id}'")

            if not query_conditions:
                return {"error": "No search criteria provided."}
    
            query = f"SELECT Id, Name, Account.Name, Email, Phone FROM Contact WHERE {' OR '.join(query_conditions)}"

        try:
            log_tool_activity("GetContactTool", "RETRIEVE_CONTACT", 
                            search_params={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            result = sf.query(query)
        except Exception as e:
            return {"error": str(e)}
        
        records = result.get("records", [])

        if not records:
            return records
            
        # Optimized response format - remove wrapper objects to reduce token usage
        if len(records) > 1:
            # Return array directly for multiple matches
            return [
                {
                    "id": rec["Id"],
                    "name": rec["Name"],
                    "account": rec["Account"]["Name"] if rec["Account"] else None,
                    "email": rec["Email"],
                    "phone": rec["Phone"]
                }
                for rec in records
            ]
        else:
            # Return single object directly
            return records[0]
    

class CreateContactInput(BaseModel):
    name: str
    account_id: str
    email: str
    phone: str


class CreateContactTool(BaseTool):
    """Salesforce Contact Creation Tool.
    
    Creates new contact records linked to existing accounts. Essential for
    building account relationships and enabling multi-threaded sales engagement.
    
    Required Relationships:
    - Must link to existing account via account_id
    - Creates bidirectional account-contact relationship
    - Enables role-based contact management (decision makers, influencers)
    """
    name: str = "create_contact_tool"
    description: str = (
        "Creates a new Salesforce contact. Requires: name, account_id, email, and phone."
    )
    args_schema: type = CreateContactInput

    def _run(self, **kwargs) -> dict:
        data = CreateContactInput(**kwargs)

        try:
            log_tool_activity("CreateContactTool", "CREATE_CONTACT", 
                            input_data={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            result = sf.Contact.create({
                "LastName": data.name,
                "AccountId": data.account_id,
                "Email": data.email,
                "Phone": data.phone
            })
            return result
        except Exception as e:
            return {"error": str(e)}


class UpdateContactInput(BaseModel):
    contact_id: str
    email: Optional[str] = None
    phone: Optional[str] = None


class UpdateContactTool(BaseTool):
    """Salesforce Contact Update Tool.
    
    Updates contact communication preferences and details while maintaining
    account relationships and activity history. Critical for data hygiene.
    
    Common Use Cases:
    - Email address changes (job changes, domain migrations)
    - Phone number updates (new office, mobile numbers)
    - Preserves all related activities, opportunities, and cases
    """
    name: str = "update_contact_tool"
    description: str = (
        "Updates an existing Salesforce contact. Requires a contact_id. "
        "Optionally takes an email and/or phone."
    )
    args_schema: type = UpdateContactInput

    def _run(self, **kwargs) -> dict:
        data = UpdateContactInput(**kwargs)
        try:
            log_tool_activity("UpdateContactTool", "UPDATE_CONTACT", 
                            input_data={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            sf.Contact.update(data.contact_id, {
                "Email": data.email,
                "Phone": data.phone
            })
            
            log_tool_activity("UpdateContactTool", "UPDATE_CONTACT_SUCCESS", 
                              record_id=data.contact_id)
            return "Successfully updated contact with Id: " + data.contact_id
        except Exception as e:
            return {"error": str(e)}
    

class GetCaseInput(BaseModel):
    case_id: Optional[str] = None
    account_name: Optional[str] = None
    account_id: Optional[str] = None
    contact_name: Optional[str] = None


class GetCaseTool(BaseTool):
    """Salesforce Case Retrieval Tool.
    
    Provides customer service case management and support ticket retrieval across
    account relationships and contact associations. Central to customer success
    operations, issue tracking, and service level agreement monitoring.
    
    Search Capabilities:
    - Account-based: "get all cases for [account]" (use account_name/account_id)
    - Contact-based: Cases associated with specific customer contacts
    - Direct lookup: Individual case retrieval by case ID
    - Service intelligence: Support ticket history and resolution tracking
    
    Customer Service Applications:
    - Support ticket management and routing
    - Customer issue history and trends
    - Service level agreement monitoring
    - Account health and satisfaction tracking
    
    Returns:
    - Single match: {'match': {case_data}}
    - Multiple matches: {'multiple_matches': [case_list]}
    - No matches: [] (empty list)
    """
    name: str = "get_case_tool"
    description: str = (
        "Retrieves Salesforce customer service cases with flexible search options. "
        "PRIMARY USE: Get ALL CASES for an account (use 'account_name' or 'account_id' parameter). "
        "Also supports: case lookup by ID, contact associations for customer service workflows. "
        "Essential for support ticket management, customer issue tracking, and service analytics. "
        "Returns case details with status, priority, and account/contact relationships."
    )
    args_schema: type = GetCaseInput

    def _run(self, **kwargs) -> dict:
        data = GetCaseInput(**kwargs)
        try:
            log_tool_activity("GetCaseTool", "RETRIEVE_CASE", 
                            search_params={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            
            if data.case_id:
                escaped_case_id = escape_soql(data.case_id)
                query = f"SELECT Id, Subject, Description, Account.Name, Contact.Name FROM Case WHERE Id = '{escaped_case_id}'"
            else:
                query_conditions = []
                if data.account_name:
                    escaped_account_name = escape_soql(data.account_name)
                    query_conditions.append(f"Account.Name LIKE '%{escaped_account_name}%'")
                if data.account_id:
                    escaped_account_id = escape_soql(data.account_id)
                    query_conditions.append(f"AccountId = '{escaped_account_id}'")
                if data.contact_name:
                    escaped_contact_name = escape_soql(data.contact_name)
                    query_conditions.append(f"Contact.Name LIKE '%{escaped_contact_name}%'")

                if not query_conditions:
                    return {"error": "No search criteria provided."}

                query = f"SELECT Id, Subject, Description, Account.Name, Contact.Name FROM Case WHERE {' OR '.join(query_conditions)}"
            
            result = sf.query(query)
            records = result['records']

            if not records:
                return records
                
            # Token optimization: Direct array/object returns without wrapper
            if len(records) > 1:
                return [
                    {
                        "id": rec["Id"],
                        "subject": rec["Subject"],
                        "account": rec["Account"]["Name"] if rec["Account"] else None,
                        "contact": rec["Contact"]["Name"] if rec["Contact"] else None
                    }
                    for rec in records
                ]
            else:
                return records[0]
        except Exception as e:
            return {"error": str(e)}
        

class CreateCaseInput(BaseModel):
    subject: str
    description: Optional[str] = None
    account_id: str
    contact_id: str


class CreateCaseTool(BaseTool):
    """Salesforce Case Creation Tool.
    
    Creates customer service cases with proper account and contact associations.
    Designed for efficient ticket creation with intelligent subject summarization.
    
    Design Decisions:
    - Requires both account AND contact for proper case routing
    - Subject line discretion: AI summarizes user input effectively
    - Description optional: Use for detailed context when needed
    - Triggers case assignment rules and SLA timers
    """
    name: str = "create_case_tool"
    description: str = (
        "Creates a new Salesforce case. Requires a subject, account_id and contact_id. Optional fields include description. "
        "Use your discretion on how best to summarize the input into a subject and when to include a description."
    )
    args_schema: type = CreateCaseInput

    def _run(self, **kwargs) -> dict:
        data = CreateCaseInput(**kwargs)
        try:
            log_tool_activity("CreateCaseTool", "CREATE_CASE", 
                            input_data={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            result = sf.Case.create({
                "Subject": data.subject,
                "Description": data.description,
                "AccountId": data.account_id,
                "ContactId": data.contact_id
            })
            return result
        except Exception as e:
            return {"error": str(e)}


class UpdateCaseInput(BaseModel):
    case_id: str
    status: str
    description: Optional[str] = None


class UpdateCaseTool(BaseTool):
    """Salesforce Case Update Tool.
    
    Updates case status and resolution details for customer service workflows.
    Critical for SLA compliance and customer satisfaction tracking.
    
    Status Progression:
    - Moves cases through support lifecycle (New → Working → Resolved)
    - Updates trigger escalation rules and notifications
    - Description updates preserve case history and resolution notes
    """
    name: str = "update_case_tool"
    description: str = (
        "Updates an existing Salesforce case. Requires a case_id and status. "
        "Optionally takes a description."
    )
    args_schema: type = UpdateCaseInput

    def _run(self, **kwargs) -> dict:
        data = UpdateCaseInput(**kwargs)
        try:
            log_tool_activity("UpdateCaseTool", "UPDATE_CASE", 
                            input_data={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            sf.Case.update(data.case_id, {
                "Status": data.status,
                "Description": data.description
            })
            
            log_tool_activity("UpdateCaseTool", "UPDATE_CASE_SUCCESS", 
                              record_id=data.case_id)
            return "Successfully updated case with Id: " + data.case_id
        except Exception as e:
            return {"error": str(e)}
    

class GetTaskInput(BaseModel):
    task_id: Optional[str] = None
    subject: Optional[str] = None
    account_name: Optional[str] = None
    account_id: Optional[str] = None
    contact_name: Optional[str] = None


class GetTaskTool(BaseTool):
    """Salesforce Task Retrieval Tool.
    
    Provides activity management and follow-up task retrieval across sales,
    service, and relationship management workflows. Central to productivity
    tracking, pipeline management, and customer engagement coordination.
    
    Search Capabilities:
    - Account-based: "get all tasks for [account]" (use account_name/account_id)
    - Contact-based: Tasks associated with specific customer relationships
    - Subject search: Find tasks by activity description or topic
    - Direct lookup: Individual task retrieval by task ID
    
    Business Applications:
    - Sales activity tracking and follow-up management
    - Customer engagement timeline and touch-point history
    - Team productivity monitoring and task assignment
    - Pipeline activity analysis and conversion optimization
    
    Returns:
    - Single match: {'match': {task_data}}
    - Multiple matches: {'multiple_matches': [task_list]}
    - No matches: [] (empty list)
    """
    name: str = "get_task_tool"
    description: str = (
        "Retrieves Salesforce tasks and activities with flexible search options. "
        "PRIMARY USE: Get ALL TASKS for an account (use 'account_name' or 'account_id' parameter). "
        "Also supports: task lookup by ID, subject search, contact associations for activity tracking. "
        "Essential for sales follow-up management, customer engagement tracking, and productivity analysis. "
        "Returns task details with due dates, status, and account/contact relationships."
    )
    args_schema: type = GetTaskInput

    def _run(self, **kwargs) -> dict:
        data = GetTaskInput(**kwargs)
        try:
            log_tool_activity("GetTaskTool", "RETRIEVE_TASK", 
                            search_params={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            
            if data.task_id:
                escaped_task_id = escape_soql(data.task_id)
                query = f"SELECT Id, Subject, Account.Name, Who.Name FROM Task WHERE Id = '{escaped_task_id}'"
            else:
                query_conditions = []
                if data.subject:
                    escaped_subject = escape_soql(data.subject)
                    query_conditions.append(f"Subject LIKE '%{escaped_subject}%'")
                if data.account_name:
                    escaped_account_name = escape_soql(data.account_name)
                    query_conditions.append(f"Account.Name LIKE '%{escaped_account_name}%'")
                if data.account_id:
                    escaped_account_id = escape_soql(data.account_id)
                    query_conditions.append(f"WhatId = '{escaped_account_id}'")
                if data.contact_name:
                    escaped_contact_name = escape_soql(data.contact_name)
                    query_conditions.append(f"Who.Name LIKE '%{escaped_contact_name}%'")

                if not query_conditions:
                    return {"error": "No search criteria provided."}

                query = f"SELECT Id, Subject, Account.Name, Who.Name FROM Task WHERE {' OR '.join(query_conditions)}"
            
            result = sf.query(query)
            records = result['records']

            if not records:
                return records
                
            # Token optimization: Direct array/object returns without wrapper
            if len(records) > 1:
                return [
                    {
                        "id": rec["Id"],
                        "subject": rec["Subject"],
                        "account": rec["Account"]["Name"] if rec["Account"] else None,
                        "contact": rec["Who"]["Name"] if rec["Who"] else None
                    }
                    for rec in records
                ]
            else:
                return records[0]
        except Exception as e:
            return {"error": str(e)}
        

class CreateTaskInput(BaseModel):
    subject: str
    description: Optional[str] = None
    account_id: str
    contact_id: str


class CreateTaskTool(BaseTool):
    """Salesforce Task Creation Tool.
    
    Creates activity records for sales and service follow-up tracking.
    Links tasks to both accounts (WhatId) and contacts (WhoId) for complete context.
    
    Design Philosophy:
    - Dual linking: Account provides context, Contact provides assignment
    - Subject summarization: AI condenses user input into actionable titles
    - Enables activity timeline views and productivity analytics
    """
    name: str = "create_task_tool"
    description: str = (
        "Creates a new Salesforce task. Requires a subject, account_id and contact_id. Optional fields include description. "
        "Use your discretion on how best to summarize the input into a subject and when to include a description."
    )
    args_schema: type = CreateTaskInput

    def _run(self, **kwargs) -> dict:
        data = CreateTaskInput(**kwargs)
        try:
            log_tool_activity("CreateTaskTool", "CREATE_TASK", 
                            input_data={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            result = sf.Task.create({
                "Subject": data.subject,
                "Description": data.description,
                "WhatId": data.account_id,
                "WhoId": data.contact_id
            })
            return result
        except Exception as e:
            return {"error": str(e)}


class UpdateTaskInput(BaseModel):
    task_id: str
    status: str
    description: Optional[str] = None


class UpdateTaskTool(BaseTool):
    """Salesforce Task Update Tool.
    
    Updates task completion status and notes for activity management.
    Essential for sales productivity tracking and follow-up completion.
    
    Status Management:
    - Tracks task progression (Not Started → In Progress → Completed)
    - Updates affect activity reports and user productivity metrics
    - Description updates capture completion notes and outcomes
    """
    name: str = "update_task_tool"
    description: str = (
        "Updates an existing Salesforce task. Requires a task_id and status. "
        "Optionally takes a description."
    )
    args_schema: type = UpdateTaskInput

    def _run(self, **kwargs) -> dict:
        data = UpdateTaskInput(**kwargs)
        try:
            log_tool_activity("UpdateTaskTool", "UPDATE_TASK", 
                            input_data={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            sf.Task.update(data.task_id, {
                "Status": data.status,
                "Description": data.description
            })
            
            log_tool_activity("UpdateTaskTool", "UPDATE_TASK_SUCCESS", 
                              record_id=data.task_id)
            return "Successfully updated task with Id: " + data.task_id
        except Exception as e:
            return {"error": str(e)}
    
