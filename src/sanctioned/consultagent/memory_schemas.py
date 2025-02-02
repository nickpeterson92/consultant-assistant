from pydantic import BaseModel
from typing import List, Optional

class Lead(BaseModel):
    id: str
    name: str
    company: str
    email: str
    phone: str

class Contact(BaseModel):
    id: str
    name: str
    email: str
    phone: str

class Opportunity(BaseModel):
    id: str
    name: str
    stage: str
    amount: Optional[float] = None

class Case(BaseModel):
    id: str
    subject: str
    description: Optional[str] = None
    contact: str

class Task(BaseModel):
    id: str
    subject: str
    contact: str

class Account(BaseModel):
    id: str
    name: str
    leads: Optional[List[Lead]] = None
    contacts: Optional[List[Contact]] = None
    opportunities: Optional[List[Opportunity]] = None
    cases: Optional[List[Case]] = None
    tasks: Optional[List[Task]] = None

class AccountList(BaseModel):
    accounts: Optional[List[Account]] = None