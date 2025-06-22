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
from datetime import date
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, field_validator, ValidationError
from langchain.tools import BaseTool
from simple_salesforce import Salesforce

from src.utils.logging import log_tool_activity
from src.utils.input_validation import validate_tool_input
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
    """Salesforce Lead Retrieval Tool with Query Builder."""
    name: str = "get_lead_tool"
    description: str = (
        "Retrieves Salesforce lead records using flexible search criteria. "
        "Can search by: lead_id (exact match), email, name, phone, or company (partial match). "
        "Returns lead details including contact information and status."
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
    """Salesforce Lead Creation Tool."""
    name: str = "create_lead_tool"
    description: str = (
        "Creates a new lead in Salesforce CRM. "
        "Required: name, company. "
        "Optional: email, phone, lead_status (defaults to 'New')."
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
    """Salesforce Lead Update Tool."""
    name: str = "update_lead_tool"
    description: str = (
        "Updates existing Salesforce lead records with new information. "
        "Required: lead_id. Optional: company, email, phone."
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
    """Salesforce Account Retrieval Tool with Query Builder."""
    name: str = "get_account_tool"
    description: str = (
        "Retrieves Salesforce account information. "
        "Search by: account_id (exact) or account_name (partial match)."
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
    """Salesforce Account Creation Tool."""
    name: str = "create_account_tool"
    description: str = (
        "Creates a new account in Salesforce. "
        "Required: name. Optional: phone, website, industry."
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
    """Salesforce Account Update Tool."""
    name: str = "update_account_tool"
    description: str = (
        "Updates existing Salesforce account. "
        "Required: account_id. Optional: name, phone, website, industry."
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
    """Salesforce Opportunity Retrieval Tool with Query Builder."""
    name: str = "get_opportunity_tool"
    description: str = (
        "Retrieves Salesforce opportunities using flexible search. "
        "Search by: opportunity_id, opportunity_name, account_name, or account_id."
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
    """Salesforce Opportunity Creation Tool."""
    name: str = "create_opportunity_tool"
    description: str = (
        "Creates a new opportunity in Salesforce. "
        "Required: name, stage, close_date (YYYY-MM-DD), account_id. "
        "Optional: amount."
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
    """Salesforce Opportunity Update Tool."""
    name: str = "update_opportunity_tool"
    description: str = (
        "Updates an existing opportunity. "
        "Required: opportunity_id. Optional: stage, amount, close_date."
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
    """Salesforce Contact Retrieval Tool with Query Builder."""
    name: str = "get_contact_tool"
    description: str = (
        "Retrieves Salesforce contacts using flexible search. "
        "Search by: contact_id, email, name, phone, or account_name."
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
    """Salesforce Contact Creation Tool."""
    name: str = "create_contact_tool"
    description: str = (
        "Creates a new contact in Salesforce. "
        "Required: first_name, last_name, account_id. "
        "Optional: email, phone, title."
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
    """Salesforce Contact Update Tool."""
    name: str = "update_contact_tool"
    description: str = (
        "Updates existing Salesforce contact. "
        "Required: contact_id. Optional: email, phone, title."
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
    """Salesforce Case Retrieval Tool with Query Builder."""
    name: str = "get_case_tool"
    description: str = (
        "Retrieves Salesforce cases using flexible search. "
        "Search by: case_id, case_number, subject, account_name, or contact_name."
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
    """Salesforce Case Creation Tool."""
    name: str = "create_case_tool"
    description: str = (
        "Creates a new case in Salesforce. "
        "Required: subject, description. "
        "Optional: account_id, contact_id, priority (defaults to 'Medium')."
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
    """Salesforce Case Update Tool."""
    name: str = "update_case_tool"
    description: str = (
        "Updates existing Salesforce case. "
        "Required: case_id. Optional: status, priority."
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
    """Salesforce Task Retrieval Tool with Query Builder."""
    name: str = "get_task_tool"
    description: str = (
        "Retrieves Salesforce tasks using flexible search. "
        "Search by: task_id, subject, account_name, or contact_name."
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
    """Salesforce Task Creation Tool."""
    name: str = "create_task_tool"
    description: str = (
        "Creates a new task in Salesforce. "
        "Required: subject, due_date (YYYY-MM-DD). "
        "Optional: priority, account_id, contact_id, description."
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
    """Salesforce Task Update Tool."""
    name: str = "update_task_tool"
    description: str = (
        "Updates existing Salesforce task. "
        "Required: task_id. Optional: status, priority."
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


# Export all tools
__all__ = [
    'GetLeadTool', 'CreateLeadTool', 'UpdateLeadTool',
    'GetAccountTool', 'CreateAccountTool', 'UpdateAccountTool',
    'GetOpportunityTool', 'CreateOpportunityTool', 'UpdateOpportunityTool',
    'GetContactTool', 'CreateContactTool', 'UpdateContactTool',
    'GetCaseTool', 'CreateCaseTool', 'UpdateCaseTool',
    'GetTaskTool', 'CreateTaskTool', 'UpdateTaskTool'
]