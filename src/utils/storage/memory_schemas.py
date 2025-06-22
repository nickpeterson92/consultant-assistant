# memory_schemas.py - Simplified flat collections for TrustCall

from pydantic import BaseModel, Field
from typing import List, Optional

# SIMPLE: Flat collections instead of nested relationships
class SimpleAccount(BaseModel):
    """Simple account record"""
    id: Optional[str] = Field(default="", description="Account ID from Salesforce")
    name: str = Field(description="Account name")

class SimpleContact(BaseModel):
    """Simple contact record with account reference"""
    id: Optional[str] = Field(default="", description="Contact ID from Salesforce") 
    name: str = Field(description="Contact name")
    account_id: Optional[str] = Field(default=None, description="Related account ID")
    email: Optional[str] = Field(default=None, description="Contact email")
    phone: Optional[str] = Field(default=None, description="Contact phone")

class SimpleOpportunity(BaseModel):
    """Simple opportunity record with account reference"""
    id: Optional[str] = Field(default="", description="Opportunity ID from Salesforce")
    name: str = Field(description="Opportunity name")
    account_id: Optional[str] = Field(default=None, description="Related account ID")
    stage: Optional[str] = Field(default=None, description="Opportunity stage")
    amount: Optional[float] = Field(default=None, description="Opportunity amount")

class SimpleCase(BaseModel):
    """Simple case record with account reference"""
    id: Optional[str] = Field(default="", description="Case ID from Salesforce")
    subject: str = Field(description="Case subject")
    account_id: Optional[str] = Field(default=None, description="Related account ID")
    contact_id: Optional[str] = Field(default=None, description="Related contact ID")
    description: Optional[str] = Field(default=None, description="Case description")

class SimpleTask(BaseModel):
    """Simple task record with account reference"""
    id: Optional[str] = Field(default="", description="Task ID from Salesforce")
    subject: str = Field(description="Task subject")
    account_id: Optional[str] = Field(default=None, description="Related account ID")
    contact_id: Optional[str] = Field(default=None, description="Related contact ID")

class SimpleLead(BaseModel):
    """Simple lead record"""
    id: Optional[str] = Field(default="", description="Lead ID from Salesforce")
    name: str = Field(description="Lead name")
    status: Optional[str] = Field(default=None, description="Lead status")

# Simple container - no nested lists, no complex validation
class SimpleMemory(BaseModel):
    """Simple flat memory structure for TrustCall"""
    accounts: List[SimpleAccount] = Field(default_factory=list, description="List of accounts")
    contacts: List[SimpleContact] = Field(default_factory=list, description="List of contacts") 
    opportunities: List[SimpleOpportunity] = Field(default_factory=list, description="List of opportunities")
    cases: List[SimpleCase] = Field(default_factory=list, description="List of cases")
    tasks: List[SimpleTask] = Field(default_factory=list, description="List of tasks")
    leads: List[SimpleLead] = Field(default_factory=list, description="List of leads")

# Legacy compatibility - keep old classes but mark as deprecated
class AccountList(BaseModel):
    """Legacy container - DEPRECATED, use SimpleMemory instead"""
    accounts: List[dict] = Field(default_factory=list)
    
    model_config = {"extra": "forbid"}
