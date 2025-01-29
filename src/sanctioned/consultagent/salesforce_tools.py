# salesforce_tools.py


import os

from pydantic import BaseModel
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
        sf = get_salesforce_connection()
        data = CreateLeadInput(**kwargs)
        result = sf.Lead.create({
            "LastName": data.name,
            "Company": data.company,
            "Email": data.email,
            "Phone": data.phone
        })
        return {"message": f"Lead created with ID: {result['id']}"}



class GetOpportunityInput(BaseModel):
    account_name: Optional[str] = None
    opportunity_name: Optional[str] = None
    stage: Optional[str] = None
    amount: Optional[float] = None

class GetOpportunityTool(BaseTool):
    name: str = "get_opportunity_tool"
    description: str = (
        "Retrieves Salesforce opportunities by Account Name, Opportunity Name, or both. If multiple opportunities match, "
        "returns a list of options for user selection. Sometimes as part of an update opportunity flow. "
        "If called for such a scenario, ensure to maintain the values for both opportunity stage and amount"
    )
    args_schema: type = GetOpportunityInput
    
    def _run(self, **kwargs) -> dict:
        print(f"DEBUG: Tool 'get_opportunity_tool' invoked with input: {kwargs}")
        sf = get_salesforce_connection()
        data = GetOpportunityInput(**kwargs)
        
        account_name = data.account_name
        opportunity_name = data.opportunity_name
        stage = data.stage
        amount = data.amount
        
        if not account_name and not opportunity_name:
            return {"error": "Please refine request to contain account or opportunity name."}

        query_conditions = [f"Account.Name LIKE '%{account_name}%'"]
        if opportunity_name:
            query_conditions.append(f"Name LIKE '%{opportunity_name}%'")

        query = f"SELECT Id, Name, StageName, Amount, Account.Name FROM Opportunity WHERE {' AND '.join(query_conditions)}"
        print(f"DEBUG: Executing SOQL query: {query}")

        result = sf.query(query)
        records = result.get("records", [])

        if not records:
            return {"error": "No opportunities found."}

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
                ],
                "stage": stage,
                "amount": amount
            }

        return {
            "id": records[0]["Id"],
            "stage": stage,
            "amount": amount
        }



class UpdateOpportunityInput(BaseModel):
    account_name: Optional[str] = None
    opportunity_name: Optional[str] = None
    opportunity_id: Optional[str] = None
    stage: str
    amount: float

class UpdateOpportunityTool(BaseTool):
    name: str = "update_opportunity_tool"
    description: str = (
        "Updates an existing Opportunity. Called directly if an opportunity_id is provided. "
        "If opportunity_id not provided, the get_opportunity_tool is called to retrieve the opportunity_id "
        "if an account_name and/or opportunity_name are supplied in the user's request."
    )
    args_schema: type = UpdateOpportunityInput

    def _run(self, **kwargs) -> dict:
        print(f"DEBUG: Tool 'update_opportunity_tool' invoked with input: {kwargs}")
        sf = get_salesforce_connection()

        data = UpdateOpportunityInput(**kwargs)

        stage = data.stage
        amount = data.amount
        opp_id = data.opportunity_id
        
        try:
            #parsed_amount = parse_amount(amount)
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
            