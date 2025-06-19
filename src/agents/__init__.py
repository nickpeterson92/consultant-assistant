"""
Specialized Agents Package
"""

from .salesforce import salesforce_graph, build_salesforce_graph, SalesforceA2AHandler

__all__ = [
    "salesforce_graph",
    "build_salesforce_graph",
    "SalesforceA2AHandler"
]