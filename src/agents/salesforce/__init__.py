"""Salesforce Specialized Agent Package.

This package implements the Salesforce CRM specialized agent, providing comprehensive
integration with Salesforce for managing customer relationships, sales pipelines,
and support operations. The agent leverages the simple-salesforce library for API
communication and implements 15 enterprise-grade tools for CRUD operations.

Capabilities:
- Lead Management: Search, create, and update sales leads
- Account Management: Handle customer and partner accounts
- Opportunity Pipeline: Track deals through sales stages
- Contact Management: Maintain customer relationships
- Case Management: Support ticket handling and resolution
- Task Management: Activity coordination and follow-ups

Technical features:
- SOQL injection prevention with parameterized queries
- Comprehensive error handling and validation
- Efficient batch operations for bulk data handling
- A2A protocol handler for orchestrator communication
- LangGraph workflow for stateful processing
- Memory extraction for persistent context

The agent operates as an independent microservice, registering its capabilities
with the orchestrator and responding to CRM-related requests via the A2A protocol.
"""

from .main import salesforce_graph, build_salesforce_graph, SalesforceA2AHandler

__all__ = [
    "salesforce_graph",
    "build_salesforce_graph", 
    "SalesforceA2AHandler"
]