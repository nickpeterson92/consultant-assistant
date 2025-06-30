"""Pydantic models for structured workflow data extraction using TrustCall"""

from pydantic import BaseModel, Field
from typing import Optional


class OnboardingDetails(BaseModel):
    """All details needed for customer onboarding workflow"""
    account_id: str = Field(description="Salesforce Account ID (starts with 001)")
    account_name: str = Field(description="Account/Company name")
    opportunity_id: str = Field(description="Salesforce Opportunity ID (starts with 006)")
    opportunity_name: str = Field(description="Opportunity/Deal name")


class AccountMatch(BaseModel):
    """Account search result for disambiguation"""
    account_id: str = Field(description="Salesforce Account ID")
    account_name: str = Field(description="Account name")
    account_type: Optional[str] = Field(default=None, description="Account type (Customer, Prospect, etc.)")


class OpportunityMatch(BaseModel):
    """Opportunity search result for disambiguation"""
    opportunity_id: str = Field(description="Salesforce Opportunity ID")
    opportunity_name: str = Field(description="Opportunity name")
    stage: Optional[str] = Field(default=None, description="Opportunity stage")
    amount: Optional[float] = Field(default=None, description="Opportunity amount")


class UserSelection(BaseModel):
    """Extracted user selection from multiple options"""
    selected_id: str = Field(description="The ID that was selected (Account or Opportunity)")
    selected_name: str = Field(description="The name of the selected item")
    selection_type: str = Field(description="Type of selection: 'account' or 'opportunity'")