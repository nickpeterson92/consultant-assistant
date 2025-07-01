"""Salesforce CRM specialized agent with comprehensive CRUD operations."""

from .main import salesforce_graph, build_salesforce_graph, SalesforceA2AHandler  # pyright: ignore[reportAttributeAccessIssue]

__all__ = [
    "salesforce_graph",
    "build_salesforce_graph", 
    "SalesforceA2AHandler"
]