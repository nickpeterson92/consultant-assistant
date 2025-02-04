# memory_schemas.py


from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Union

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
    id: Optional[str] = None
    name: Optional[str] = None
    leads: Union[Lead, List[Lead]] = Field(default_factory=list)
    contacts: Union[Contact, List[Contact]] = Field(default_factory=list)
    opportunities: Union[Opportunity, List[Opportunity]] = Field(default_factory=list)
    cases: Union[Case, List[Case]] = Field(default_factory=list)
    tasks: Union[Task, List[Task]] = Field(default_factory=list)


class AccountList(BaseModel):
    accounts: Union[Account, List[Account]] = Field(default_factory=list)

    @field_validator("accounts", mode="before")
    def ensure_list(cls, v):
        # If a single object is provided, wrap it in a list
        if isinstance(v, dict):
            return [v]
        return v


class SimpleAccount(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None

class SimpleAccountList(BaseModel):
    accounts: Union[SimpleAccount, List[SimpleAccount]] = Field(default_factory=list)

    @field_validator("accounts", mode="before")
    def ensure_list(cls, v):
        # If a single object is provided, wrap it in a list
        if isinstance(v, dict):
            return [v]
        return v