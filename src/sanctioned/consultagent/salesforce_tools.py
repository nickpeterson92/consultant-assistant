# salesforce_tools.py


import os
from datetime import date

from pydantic import BaseModel, field_validator
from langchain.tools import BaseTool
from typing import Optional
from simple_salesforce import Salesforce


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
        #print(f"DEBUG: Tool 'get_lead_tool' invoked with input: {kwargs}")
        data = GetLeadInput(**kwargs)
        try:
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
                print(f"DEBUG: Executing SOQL query: {query}")

            records = sf.query(query)['records']

            if not records:
                return {"message": "No leads found."}
        
            if len(records) > 1:
                return {
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

            return {
                "match": records[0]
            }
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
        #print(f"DEBUG: Tool 'create_lead_tool' invoked with input: {kwargs}")
        try:
            sf = get_salesforce_connection()
            data = CreateLeadInput(**kwargs)
            result = sf.Lead.create({
                "LastName": data.name,
                "Company": data.company,
                "Email": data.email,
                "Phone": data.phone
            })
            return {"message": f"Lead created with ID: {result['id']}"}
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
        #print(f"DEBUG: Tool 'update_lead_tool' invoked with input: {kwargs}")
        try:
            sf = get_salesforce_connection()
            data = UpdateLeadInput(**kwargs)
            result = sf.Lead.update(data.lead_id, {
                "Company": data.company,
                "Email": data.email,
                "Phone": data.phone
            })
            return {"message": f"Lead updated with ID: {data.lead_id}"}
        except Exception as e:
            return {"error": str(e)}
    

class GetOpportunityInput(BaseModel):
    opportunity_id: Optional[str] = None
    account_name: Optional[str] = None
    opportunity_name: Optional[str] = None


class GetOpportunityTool(BaseTool):
    name: str = "get_opportunity_tool"
    description: str = (
        "Retrieves Salesforce opportunities, always by opportunity_id if one is available. "
        "If no opportunity_id is available the tool uses account_name, opportunity_name, or both. "
        "If multiple opportunities match, returns a list of options for user selection. "
        "Must be used in workflows involving tools that require an opportunity_id where one is not supplied."
    )
    args_schema: type = GetOpportunityInput
    
    def _run(self, **kwargs) -> dict:
        #print(f"DEBUG: Tool 'get_opportunity_tool' invoked with input: {kwargs}")
        data = GetOpportunityInput(**kwargs)
        
        account_name = data.account_name
        opportunity_name = data.opportunity_name
        opportunity_id = data.opportunity_id

        if opportunity_id:
            query =f"SELECT Id, Name, StageName, Amount, Account.Name FROM Opportunity WHERE Id = '{opportunity_id}'"
        else:
            query_conditions = [f"Account.Name LIKE '%{account_name}%'"]
            if opportunity_name:
                query_conditions.append(f"Name LIKE '%{opportunity_name}%'")
    
            query = f"SELECT Id, Name, StageName, Amount, Account.Name FROM Opportunity WHERE {' AND '.join(query_conditions)}"
            print(f"DEBUG: Executing SOQL query: {query}")

        try:
            sf = get_salesforce_connection()
            result = sf.query(query)
        except Exception as e:
            return {"error": str(e)}
        
        records = result.get("records", [])

        if not records:
            return {"message": "No opportunities found."}

        if len(records) > 1:
            return {
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

        return {
            "match": records[0]
        }
    

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
        #print(f"DEBUG: Tool 'create_opportunity_tool' invoked with input: {kwargs}")

        data = CreateOpportunityInput(**kwargs)

        opportunity_name = data.opportunity_name
        amount = data.amount
        account_id = data.account_id
        stage_name = data.stage_name
        close_date = data.close_date

        try:
            sf = get_salesforce_connection()
            sf.Opportunity.create({
                "Name": opportunity_name,
                "AccountId": account_id,
                "Amount": amount,
                "StageName": stage_name,
                "CloseDate": close_date
            })
            return {
                "message": "Opportunity created successfully",
                "opportunity_name": opportunity_name,
                "amount": amount,
                "stage_name": stage_name,
                "close_date": close_date
            }
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
        #print(f"DEBUG: Tool 'update_opportunity_tool' invoked with input: {kwargs}")

        data = UpdateOpportunityInput(**kwargs)

        stage = data.stage
        amount = data.amount
        opp_id = data.opportunity_id
        
        try:
            sf = get_salesforce_connection()
            sf.Opportunity.update(opp_id, {
                "StageName": stage,
                "Amount": amount
            })
            return {
                "message": f"Opportunity updated successfully with ID: {opp_id}",
                "stage": stage,
                "amount": amount
            }
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
        #print(f"DEBUG: Tool 'get_account_tool' invoked with input: {kwargs}")
        data = GetAccountInput(**kwargs)
        
        account_id = data.account_id
        account_name = data.account_name

        if account_id:
            query =f"SELECT Id, Name FROM Account WHERE Id = '{account_id}'"
        else:
            query_conditions = [f"Account.Name LIKE '%{account_name}%'"]
    
            query = f"SELECT Id, Name FROM Account WHERE {' AND '.join(query_conditions)}"
            print(f"DEBUG: Executing SOQL query: {query}")

        try:
            sf = get_salesforce_connection()
            result = sf.query(query)
        except Exception as e:
            return {"error": str(e)}
        
        records = result.get("records", [])

        if not records:
            return {"message": "No accounts found."}

        if len(records) > 1:
            return {
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

        return {
            "match": records[0]
        }
    

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
        #print(f"DEBUG: Tool 'create_account_tool' invoked with input: {kwargs}")
        data = CreateAccountInput(**kwargs)

        try:
            sf = get_salesforce_connection()
            result = sf.Account.create({
                "Name": data.account_name,
                "Phone": data.phone,
                "Website": data.website
            })
        except Exception as e:
            return {"error": str(e)}
        return {"message": f"Account created with ID: {result['id']}"}


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
        #print(f"DEBUG: Tool 'update_account_tool' invoked with input: {kwargs}")
        data = UpdateAccountInput(**kwargs)
        try:
            sf = get_salesforce_connection()
            result = sf.Account.update(data.account_id, {
                "Phone": data.phone,
                "Website": data.website
            })
        except Exception as e:
            return {"error": str(e)}
        return {"message": f"Account updated with ID: {data.account_id}"}
    

class GetContactInput(BaseModel):
    contact_id: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    account_name: Optional[str] = None


class GetContactTool(BaseTool):
    name: str = "get_contact_tool"
    description: str = (
        "Retrieves Salesforce contacts by contact_id. If no contact_id is supplied the tool uses email, name, phone, or account_name. "
        "If multiple contacts match, returns a list of options for user selection. "
        "Must be used in workflows involving tools that require a contact_id where one is not supplied."
    )
    args_schema: type = GetContactInput
    
    def _run(self, **kwargs) -> dict:
        #print(f"DEBUG: Tool 'get_contact_tool' invoked with input: {kwargs}")
        data = GetContactInput(**kwargs)
        
        contact_id = data.contact_id
        email = data.email
        name = data.name
        phone = data.phone
        account_name = data.account_name

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
    
            query = f"SELECT Id, Name, Account.Name, Email, Phone FROM Contact WHERE {' AND '.join(query_conditions)}"
            print(f"DEBUG: Executing SOQL query: {query}")

        try:
            sf = get_salesforce_connection()
            result = sf.query(query)
        except Exception as e:
            return {"error": str(e)}
        
        records = result.get("records", [])

        if not records:
            return {"message": "No contacts found."}

        if len(records) > 1:
            return {
                "multiple_matches": [
                    {
                        "id": rec["Id"],
                        "name": rec["Name"],
                        "account": rec["Account"]["Name"],
                        "email": rec["Email"],
                        "phone": rec["Phone"]
                    }
                    for rec in records
                ]
            }

        return {
            "match": records[0]
        }
    

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
        #print(f"DEBUG: Tool 'create_contact_tool' invoked with input: {kwargs}")
        data = CreateContactInput(**kwargs)

        try:
            sf = get_salesforce_connection()
            result = sf.Contact.create({
                "LastName": data.name,
                "AccountId": data.account_id,
                "Email": data.email,
                "Phone": data.phone
            })
        except Exception as e:
            return {"error": str(e)}
        return {"message": f"Contact created with ID: {result['id']}"}


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
        #print(f"DEBUG: Tool 'update_contact_tool' invoked with input: {kwargs}")
        data = UpdateContactInput(**kwargs)
        try:
            sf = get_salesforce_connection()
            result = sf.Contact.update(data.contact_id, {
                "Email": data.email,
                "Phone": data.phone
            })
        except Exception as e:
            return {"error": str(e)}
        return {"message": f"Contact updated with ID: {data.contact_id}"}
    

class GetCaseInput(BaseModel):
    case_id: Optional[str] = None
    account_name: Optional[str] = None
    contact_name: Optional[str] = None


class GetCaseTool(BaseTool):
    name: str = "get_case_tool"
    description: str = (
        "Retrieves Salesforce cases by case_id. If no case_id is supplied the tool uses subject, account_name, or contact_name. "
        "If multiple cases match, returns a list of options for user selection. "
        "Must be used in workflows involving tools that require a case_id where one is not supplied."
    )
    args_schema: type = GetCaseInput

    def _run(self, **kwargs) -> dict:
        #print(f"DEBUG: Tool 'get_case_tool' invoked with input: {kwargs}")
        data = GetCaseInput(**kwargs)
        try:
            sf = get_salesforce_connection()
            if data.case_id:
                query = f"SELECT Id, Subject, Description, Account.Name, Contact.Name FROM Case WHERE Id = '{data.case_id}'"
            else:
                query_conditions = []
                if data.account_name:
                    query_conditions.append(f"Account.Name LIKE '%{data.account_name}%'")
                if data.contact_name:
                    query_conditions.append(f"Contact.Name LIKE '%{data.contact_name}%'")

                if not query_conditions:
                    return {"error": "No search criteria provided."}

                query = f"SELECT Id, Subject, Description, Account.Name, Contact.Name FROM Case WHERE {' OR '.join(query_conditions)}"
                print(f"DEBUG: Executing SOQL query: {query}")

            records = sf.query(query)['records']

            if not records:
                return {"message": "No cases found."}
            
            if len(records) > 1:
                return {
                    "multiple_matches": [
                        {
                            "id": rec["Id"],
                            "subject": rec["Subject"],
                            "account": rec["Account"]["Name"],
                            "contact": rec["Contact"]["Name"]
                        }
                        for rec in records
                    ]
                }

            return {
                "match": records[0]
            }
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
        #print(f"DEBUG: Tool 'create_case_tool' invoked with input: {kwargs}")
        data = CreateCaseInput(**kwargs)
        try:
            sf = get_salesforce_connection()
            result = sf.Case.create({
                "Subject": data.subject,
                "Description": data.description,
                "AccountId": data.account_id,
                "ContactId": data.contact_id
            })
        except Exception as e:
            return {"error": str(e)}
        return {"message": f"Case created with ID: {result['id']}"}


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
        #print(f"DEBUG: Tool 'update_case_tool' invoked with input: {kwargs}")
        data = UpdateCaseInput(**kwargs)
        try:
            sf = get_salesforce_connection()
            result = sf.Case.update(data.case_id, {
                "Status": data.status,
                "Description": data.description
            })
        except Exception as e:
            return {"error": str(e)}
        return {"message": f"Case updated with ID: {data.case_id}"}
    

class GetTaskInput(BaseModel):
    task_id: Optional[str] = None
    subject: Optional[str] = None
    account_name: Optional[str] = None
    contact_name: Optional[str] = None


class GetTaskTool(BaseTool):
    name: str = "get_task_tool"
    description: str = (
        "Retrieves Salesforce tasks by task_id. If no task_id is supplied the tool uses subject, account_name, or contact_name. "
        "If multiple tasks match, returns a list of options for user selection. "
        "Must be used in workflows involving tools that require a task_id where one is not supplied."
    )
    args_schema: type = GetTaskInput

    def _run(self, **kwargs) -> dict:
        #print(f"DEBUG: Tool 'get_task_tool' invoked with input: {kwargs}")
        data = GetTaskInput(**kwargs)
        try:
            sf = get_salesforce_connection()
            if data.task_id:
                query = f"SELECT Id, Subject, Account.Name, Who.Name FROM Task WHERE Id = '{data.task_id}'"
            else:
                query_conditions = []
                if data.subject:
                    query_conditions.append(f"Subject LIKE '%{data.subject}%'")
                if data.account_name:
                    query_conditions.append(f"Account.Name LIKE '%{data.account_name}%'")
                if data.contact_name:
                    query_conditions.append(f"Who.Name LIKE '%{data.contact_name}%'")

                if not query_conditions:
                    return {"error": "No search criteria provided."}

                query = f"SELECT Id, Subject, Account.Name, Who.Name FROM Task WHERE {' OR '.join(query_conditions)}"
                print(f"DEBUG: Executing SOQL query: {query}")

            records = sf.query(query)['records']

            if not records:
                return {"message": "No tasks found."}
            
            if len(records) > 1:
                return {
                    "multiple_matches": [
                        {
                            "id": rec["Id"],
                            "subject": rec["Subject"],
                            "account": rec["Account"]["Name"],
                            "contact": rec["Who"]["Name"]
                        }
                        for rec in records
                    ]
                }

            return {
                "match": records[0]
            }
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
        #print(f"DEBUG: Tool 'create_task_tool' invoked with input: {kwargs}")
        data = CreateTaskInput(**kwargs)
        try:
            sf = get_salesforce_connection()
            result = sf.Task.create({
                "Subject": data.subject,
                "Description": data.description,
                "WhatId": data.account_id,
                "WhoId": data.contact_id
            })
        except Exception as e:
            return {"error": str(e)}
        return {"message": f"Task created with ID: {result['id']}"}


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
        #print(f"DEBUG: Tool 'update_task_tool' invoked with input: {kwargs}")
        data = UpdateTaskInput(**kwargs)
        try:
            sf = get_salesforce_connection()
            result = sf.Task.update(data.task_id, {
                "Status": data.status,
                "Description": data.description
            })
        except Exception as e:
            return {"error": str(e)}
        return {"message": f"Task updated with ID: {data.task_id}"}

