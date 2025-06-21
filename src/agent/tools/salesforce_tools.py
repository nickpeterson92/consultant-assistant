# salesforce_tools.py


import os
from datetime import date

from pydantic import BaseModel, field_validator
from langchain.tools import BaseTool
from typing import Optional
from simple_salesforce import Salesforce
from utils.state_manager import StateManager

# Tool activity logging
import json
from datetime import datetime
from pathlib import Path

def log_tool_activity(tool_name, operation, **data):
    """Log tool usage to external file with safe JSON serialization"""
    try:
        # Safely serialize data, handling Pydantic objects and other non-serializable types
        safe_data = {}
        for k, v in data.items():
            try:
                if hasattr(v, 'model_dump'):  # Pydantic object
                    safe_data[k] = v.model_dump()
                elif hasattr(v, '__dict__'):  # Other objects with attributes
                    safe_data[k] = str(v)
                else:
                    # Test if it's JSON serializable
                    json.dumps(v)
                    safe_data[k] = v
            except (TypeError, ValueError):
                # If not serializable, convert to string
                safe_data[k] = str(v)
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "tool": tool_name,
            "operation": operation,
            **safe_data
        }
        
        log_file = Path(__file__).parent.parent.parent.parent / "logs" / "tools.log"
        log_file.parent.mkdir(exist_ok=True)
        
        with open(log_file, 'a') as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - tools - INFO - {json.dumps(log_entry)}\n")
            f.flush()
    except Exception as e:
        # Fallback logging if all else fails
        try:
            log_file = Path(__file__).parent.parent.parent.parent / "logs" / "tools.log"
            log_file.parent.mkdir(exist_ok=True)
            with open(log_file, 'a') as f:
                f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - tools - ERROR - Failed to log {tool_name}:{operation} - {str(e)}\n")
                f.flush()
        except:
            pass


def get_salesforce_connection():
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
    name: str = "get_lead_tool"
    description: str = (
        "Retrieves Salesforce leads by lead_id. If no lead_id is supplied the tool uses email, name, phone, or company. "
        "If multiple leads match, returns a list of options for user selection. "
        "Must be used in workflows involving tools that require a lead_id where one is not supplied."
    )
    args_schema: type = GetLeadInput

    def _run(self, **kwargs) -> dict:
        data = GetLeadInput(**kwargs)

        try:
            # Log tool activity
            log_tool_activity("GetLeadTool", "RETRIEVE_LEAD", 
                            search_params={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            if data.lead_id:
                query = f"SELECT Id, Name, Company, Email, Phone FROM Lead WHERE Id = '{data.lead_id}'"
            else:
                query_conditions = []
                if data.email:
                    query_conditions.append(f"Email LIKE '%{data.email}%'")
                if data.name:
                    query_conditions.append(f"Name LIKE '%{data.name}%'")
                if data.phone:
                    query_conditions.append(f"Phone LIKE '%{data.phone}%'")
                if data.company:
                    query_conditions.append(f"Company LIKE '%{data.company}%'")

                if not query_conditions:
                    return {"error": "No search criteria provided."}

                query = f"SELECT Id, Name, Company, Email, Phone FROM Lead WHERE {' OR '.join(query_conditions)}"

            records = sf.query(query)['records']

            if not records:
                return records
                
            if len(records) > 1:
                multiple_matches = {
                    "multiple_matches": [
                        {
                            "id": rec["Id"],
                            "name": rec["Name"],
                            "company": rec["Company"],
                            "email": rec["Email"],
                            "phone": rec["Phone"]
                        }
                        for rec in records
                    ]
                }
                return multiple_matches
            else:
                match = {"match": records[0]}
                return match
        except Exception as e:
            return {"error": str(e)}


class CreateLeadInput(BaseModel):
    name: str
    company: str
    email: str
    phone: str


class CreateLeadTool(BaseTool):
    name: str = "create_lead_tool"
    description: str = (
        "Creates a new Salesforce lead. Requires: name, company, email, and phone."
    )
    args_schema: type = CreateLeadInput

    def _run(self, **kwargs) -> dict:
        try:
            # Log tool activity
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
    name: str = "update_lead_tool"
    description: str = (
        "Updates an existing Salesforce lead. Requires a lead_id. "
        "Optionally takes a company, email, and/or phone."
    )
    args_schema: type = UpdateLeadInput

    def _run(self, **kwargs) -> dict:
        try:
            # Log tool activity
            log_tool_activity("UpdateLeadTool", "UPDATE_LEAD", 
                            input_data={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            data = UpdateLeadInput(**kwargs)
            sf.Lead.update(data.lead_id, {
                "Company": data.company,
                "Email": data.email,
                "Phone": data.phone
            })
            
            # Log successful update
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
    name: str = "get_opportunity_tool"
    description: str = (
        "Retrieves Salesforce opportunities, always by opportunity_id if one is available. "
        "If no opportunity_id is available the tool uses account_name, account_id, opportunity_name, or combinations. "
        "If multiple opportunities match, returns a list of options for user selection. "
        "Must be used in workflows involving tools that require an opportunity_id where one is not supplied."
    )
    args_schema: type = GetOpportunityInput
    
    def _run(self, **kwargs) -> dict:
        data = GetOpportunityInput(**kwargs)
        
        account_name = data.account_name
        account_id = data.account_id
        opportunity_name = data.opportunity_name
        opportunity_id = data.opportunity_id

        if opportunity_id:
            query =f"SELECT Id, Name, StageName, Amount, Account.Name FROM Opportunity WHERE Id = '{opportunity_id}'"
        else:
            query_conditions = []
            if account_name:
                query_conditions.append(f"Account.Name LIKE '%{account_name}%'")
            if account_id:
                query_conditions.append(f"AccountId = '{account_id}'")
            if opportunity_name:
                query_conditions.append(f"Name LIKE '%{opportunity_name}%'")
            
            if not query_conditions:
                return {"error": "No search criteria provided."}
    
            query = f"SELECT Id, Name, StageName, Amount, Account.Name FROM Opportunity WHERE {' OR '.join(query_conditions)}"
            
        try:
            # Log tool activity
            log_tool_activity("GetOpportunityTool", "RETRIEVE_OPPORTUNITY", 
                            search_params={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            result = sf.query(query)
        except Exception as e:
            return {"error": str(e)}
        
        records = result.get("records", [])

        if not records:
            return records
            
        if len(records) > 1:
            multiple_matches = {
                "multiple_matches": [
                    {
                        "id": rec["Id"],
                        "name": rec["Name"],
                        "account": rec["Account"]["Name"],
                        "stage": rec["StageName"],
                        "amount": rec["Amount"],
                    }
                    for rec in records
                ]
            }
            return multiple_matches
        else:
            match = {"match": records[0]}
            return match
    

class CreateOpportunityInput(BaseModel):
    opportunity_name: str
    account_id: str
    stage_name: Optional[str] = "New"
    close_date: Optional[str] = str(date.today())
    amount: float


class CreateOpportunityTool(BaseTool):
    name: str = "create_opportunity_tool"
    description: str = (
        "Creates an opportunity. Requires an opportunity_name, an amount, a stage_name, "
        "a close_date, and the Salesforce account_id of the account the opportunity is for."
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
            # Log tool activity
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
            # Log tool activity
            log_tool_activity("UpdateOpportunityTool", "UPDATE_OPPORTUNITY", 
                            input_data={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            sf.Opportunity.update(opp_id, {
                "StageName": stage,
                "Amount": amount
            })
            
            # Log successful update
            log_tool_activity("UpdateOpportunityTool", "UPDATE_OPPORTUNITY_SUCCESS", 
                              record_id=opp_id)
            return "Successfully updated opportunity with Id: " + opp_id
        except Exception as e:
            return {"error": str(e)}


class GetAccountInput(BaseModel):
    account_id: Optional[str] = None
    account_name: Optional[str] = None


class GetAccountTool(BaseTool):
    name: str = "get_account_tool"
    description: str = (
        "Retrieves Salesforce accounts by account_id. If no account_id is supplied the tool uses account_name. "
        "If multiple accounts match, returns a list of options for user selection. "
        "Must be used in workflows involving tools that require an account_id where one is not supplied."
    )
    args_schema: type = GetAccountInput
    
    def _run(self, **kwargs) -> dict:
        data = GetAccountInput(**kwargs)
        
        account_id = data.account_id
        account_name = data.account_name

        if account_id:
            query =f"SELECT Id, Name FROM Account WHERE Id = '{account_id}'"
        else:
            query_conditions = [f"Name LIKE '%{account_name}%'"]
    
            query = f"SELECT Id, Name FROM Account WHERE {' AND '.join(query_conditions)}"

        try:
            # Log tool activity
            log_tool_activity("GetAccountTool", "RETRIEVE_ACCOUNT", 
                            search_params={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            result = sf.query(query)
        except Exception as e:
            return {"error": str(e)}
        
        records = result.get("records", [])

        if not records:
            return records
            
        if len(records) > 1:
            multiple_matches = {
                "multiple_matches": [
                    {
                        "id": rec["Id"],
                        "name": rec["Name"]
                    }
                    for rec in records
                ]
            }
            return multiple_matches
        else:
            match = {"match": records[0]}
            return match
    

class CreateAccountInput(BaseModel):
    account_name: str
    phone: str
    website: Optional[str] = None


class CreateAccountTool(BaseTool):
    name: str = "create_account_tool"
    description: str = (
        "Creates a new Salesforce account. Requires: account_name and phone. "
        "Optionally takes a website."
    )
    args_schema: type = CreateAccountInput

    def _run(self, **kwargs) -> dict:
        data = CreateAccountInput(**kwargs)

        try:
            # Log tool activity
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
    name: str = "update_account_tool"
    description: str = (
        "Updates an existing Salesforce account. Requires an account_id. "
        "Optionally takes a phone and/or website."
    )
    args_schema: type = UpdateAccountInput

    def _run(self, **kwargs) -> dict:
        data = UpdateAccountInput(**kwargs)
        try:
            # Log tool activity
            log_tool_activity("UpdateAccountTool", "UPDATE_ACCOUNT", 
                            input_data={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            sf.Account.update(data.account_id, {
                "Phone": data.phone,
                "Website": data.website
            })
            
            # Log successful update
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
    name: str = "get_contact_tool"
    description: str = (
        "Retrieves Salesforce contacts by contact_id. If no contact_id is supplied the tool uses email, name, phone, account_name, or account_id. "
        "If multiple contacts match, returns a list of options for user selection. "
        "Must be used in workflows involving tools that require a contact_id where one is not supplied."
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

        if contact_id:
            query =f"SELECT Id, Name, Account.Name, Email, Phone FROM Contact WHERE Id = '{contact_id}'"
        else:
            query_conditions = []
            if email:
                query_conditions.append(f"Email LIKE '%{email}%'")
            if name:
                query_conditions.append(f"Name LIKE '%{name}%'")
            if phone:
                query_conditions.append(f"Phone LIKE '%{phone}%'")
            if account_name:
                query_conditions.append(f"Account.Name LIKE '%{account_name}%'")
            if account_id:
                query_conditions.append(f"AccountId = '{account_id}'")

            if not query_conditions:
                return {"error": "No search criteria provided."}
    
            query = f"SELECT Id, Name, Account.Name, Email, Phone FROM Contact WHERE {' OR '.join(query_conditions)}"

        try:
            # Log tool activity
            log_tool_activity("GetContactTool", "RETRIEVE_CONTACT", 
                            search_params={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            result = sf.query(query)
        except Exception as e:
            return {"error": str(e)}
        
        records = result.get("records", [])

        if not records:
            return records
            
        if len(records) > 1:
            multiple_matches = {
                "multiple_matches": [
                    {
                        "id": rec["Id"],
                        "name": rec["Name"],
                        "account": rec["Account"]["Name"] if rec["Account"] else None,
                        "email": rec["Email"],
                        "phone": rec["Phone"]
                    }
                    for rec in records
                ]
            }
            return multiple_matches
        else:
            match = {"match": records[0]}
            return match
    

class CreateContactInput(BaseModel):
    name: str
    account_id: str
    email: str
    phone: str


class CreateContactTool(BaseTool):
    name: str = "create_contact_tool"
    description: str = (
        "Creates a new Salesforce contact. Requires: name, account_id, email, and phone."
    )
    args_schema: type = CreateContactInput

    def _run(self, **kwargs) -> dict:
        data = CreateContactInput(**kwargs)

        try:
            # Log tool activity
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
    name: str = "update_contact_tool"
    description: str = (
        "Updates an existing Salesforce contact. Requires a contact_id. "
        "Optionally takes an email and/or phone."
    )
    args_schema: type = UpdateContactInput

    def _run(self, **kwargs) -> dict:
        data = UpdateContactInput(**kwargs)
        try:
            # Log tool activity
            log_tool_activity("UpdateContactTool", "UPDATE_CONTACT", 
                            input_data={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            sf.Contact.update(data.contact_id, {
                "Email": data.email,
                "Phone": data.phone
            })
            
            # Log successful update
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
    name: str = "get_case_tool"
    description: str = (
        "Retrieves Salesforce cases by case_id. If no case_id is supplied the tool uses subject, account_name, account_id, or contact_name. "
        "If multiple cases match, returns a list of options for user selection. "
        "Must be used in workflows involving tools that require a case_id where one is not supplied."
    )
    args_schema: type = GetCaseInput

    def _run(self, **kwargs) -> dict:
        data = GetCaseInput(**kwargs)
        try:
            # Log tool activity
            log_tool_activity("GetCaseTool", "RETRIEVE_CASE", 
                            search_params={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            if data.case_id:
                query = f"SELECT Id, Subject, Description, Account.Name, Contact.Name FROM Case WHERE Id = '{data.case_id}'"
            else:
                query_conditions = []
                if data.account_name:
                    query_conditions.append(f"Account.Name LIKE '%{data.account_name}%'")
                if data.account_id:
                    query_conditions.append(f"AccountId = '{data.account_id}'")
                if data.contact_name:
                    query_conditions.append(f"Contact.Name LIKE '%{data.contact_name}%'")

                if not query_conditions:
                    return {"error": "No search criteria provided."}

                query = f"SELECT Id, Subject, Description, Account.Name, Contact.Name FROM Case WHERE {' OR '.join(query_conditions)}"
            
            result = sf.query(query)
            records = result['records']

            if not records:
                return records
                
            if len(records) > 1:
                multiple_matches = {
                    "multiple_matches": [
                        {
                            "id": rec["Id"],
                            "subject": rec["Subject"],
                            "account": rec["Account"]["Name"] if rec["Account"] else None,
                            "contact": rec["Contact"]["Name"] if rec["Contact"] else None
                        }
                        for rec in records
                    ]
                }
                return multiple_matches
            else:
                match = {"match": records[0]}
                return match
        except Exception as e:
            return {"error": str(e)}
        

class CreateCaseInput(BaseModel):
    subject: str
    description: Optional[str] = None
    account_id: str
    contact_id: str


class CreateCaseTool(BaseTool):
    name: str = "create_case_tool"
    description: str = (
        "Creates a new Salesforce case. Requires a subject, account_id and contact_id. Optional fields include description. "
        "Use your discretion on how best to summarize the input into a subject and when to include a description."
    )
    args_schema: type = CreateCaseInput

    def _run(self, **kwargs) -> dict:
        data = CreateCaseInput(**kwargs)
        try:
            # Log tool activity
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
    name: str = "update_case_tool"
    description: str = (
        "Updates an existing Salesforce case. Requires a case_id and status. "
        "Optionally takes a description."
    )
    args_schema: type = UpdateCaseInput

    def _run(self, **kwargs) -> dict:
        data = UpdateCaseInput(**kwargs)
        try:
            # Log tool activity
            log_tool_activity("UpdateCaseTool", "UPDATE_CASE", 
                            input_data={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            sf.Case.update(data.case_id, {
                "Status": data.status,
                "Description": data.description
            })
            
            # Log successful update
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
    name: str = "get_task_tool"
    description: str = (
        "Retrieves Salesforce tasks by task_id. If no task_id is supplied the tool uses subject, account_name, account_id, or contact_name. "
        "If multiple tasks match, returns a list of options for user selection. "
        "Must be used in workflows involving tools that require a task_id where one is not supplied."
    )
    args_schema: type = GetTaskInput

    def _run(self, **kwargs) -> dict:
        data = GetTaskInput(**kwargs)
        try:
            # Log tool activity
            log_tool_activity("GetTaskTool", "RETRIEVE_TASK", 
                            search_params={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            if data.task_id:
                query = f"SELECT Id, Subject, Account.Name, Who.Name FROM Task WHERE Id = '{data.task_id}'"
            else:
                query_conditions = []
                if data.subject:
                    query_conditions.append(f"Subject LIKE '%{data.subject}%'")
                if data.account_name:
                    query_conditions.append(f"Account.Name LIKE '%{data.account_name}%'")
                if data.account_id:
                    query_conditions.append(f"WhatId = '{data.account_id}'")
                if data.contact_name:
                    query_conditions.append(f"Who.Name LIKE '%{data.contact_name}%'")

                if not query_conditions:
                    return {"error": "No search criteria provided."}

                query = f"SELECT Id, Subject, Account.Name, Who.Name FROM Task WHERE {' OR '.join(query_conditions)}"
            
            result = sf.query(query)
            records = result['records']

            if not records:
                return records
                
            if len(records) > 1:
                multiple_matches = {
                    "multiple_matches": [
                        {
                            "id": rec["Id"],
                            "subject": rec["Subject"],
                            "account": rec["Account"]["Name"] if rec["Account"] else None,
                            "contact": rec["Who"]["Name"] if rec["Who"] else None
                        }
                        for rec in records
                    ]
                }
                return multiple_matches
            else:
                match = {"match": records[0]}
                return match
        except Exception as e:
            return {"error": str(e)}
        

class CreateTaskInput(BaseModel):
    subject: str
    description: Optional[str] = None
    account_id: str
    contact_id: str


class CreateTaskTool(BaseTool):
    name: str = "create_task_tool"
    description: str = (
        "Creates a new Salesforce task. Requires a subject, account_id and contact_id. Optional fields include description. "
        "Use your discretion on how best to summarize the input into a subject and when to include a description."
    )
    args_schema: type = CreateTaskInput

    def _run(self, **kwargs) -> dict:
        data = CreateTaskInput(**kwargs)
        try:
            # Log tool activity
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
    name: str = "update_task_tool"
    description: str = (
        "Updates an existing Salesforce task. Requires a task_id and status. "
        "Optionally takes a description."
    )
    args_schema: type = UpdateTaskInput

    def _run(self, **kwargs) -> dict:
        data = UpdateTaskInput(**kwargs)
        try:
            # Log tool activity
            log_tool_activity("UpdateTaskTool", "UPDATE_TASK", 
                            input_data={k: v for k, v in locals().items() if k not in ['self', 'sf']})
            sf = get_salesforce_connection()
            sf.Task.update(data.task_id, {
                "Status": data.status,
                "Description": data.description
            })
            
            # Log successful update
            log_tool_activity("UpdateTaskTool", "UPDATE_TASK_SUCCESS", 
                              record_id=data.task_id)
            return "Successfully updated task with Id: " + data.task_id
        except Exception as e:
            return {"error": str(e)}
    
