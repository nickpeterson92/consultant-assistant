# memory_schemas.py


from pydantic import BaseModel, Field
from typing import List, Optional

class Opportunity(BaseModel):
    id: str
    name: str
    stage: Optional[str] = None
    amount: Optional[float] = None

    class Config:
        extra = "forbid"

class Case(BaseModel):
    id: str
    subject: str
    description: Optional[str] = None
    contact: Optional[str] = None

    class Config:
        extra = "forbid"

class Task(BaseModel):
    id: str
    subject: str
    contact: Optional[str] = None

    class Config:
        extra = "forbid"

class Lead(BaseModel):
    id: str
    name: str
    status: Optional[str] = None

    class Config:
        extra = "forbid"

class Contact(BaseModel):
    id: str
    name: str
    email: Optional[str] = None

    class Config:
        extra = "forbid"

class Account(BaseModel):
    id: str
    name: str
    leads: List[Lead] = Field(default_factory=list)
    contacts: List[Contact] = Field(default_factory=list)
    opportunities: List[Opportunity] = Field(default_factory=list)
    cases: List[Case] = Field(default_factory=list)
    tasks: List[Task] = Field(default_factory=list)


class AccountList(BaseModel):
    accounts: List[Account] = Field(default_factory=list)

    class Config:
        extra = "forbid"


class SimpleAccount(BaseModel):
    id: str
    name: str

    class Config:
        extra = "forbid"