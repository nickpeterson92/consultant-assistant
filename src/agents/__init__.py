"""Specialized Agents Package.

This package contains all specialized agents that provide domain-specific expertise
within the multi-agent orchestrator system. Each agent is an independently deployable
microservice that communicates via the A2A protocol and implements the LangGraph
framework for stateful workflow management.

Current specialized agents:
- Salesforce: CRM operations including lead, account, opportunity, contact, case,
  and task management with 15 comprehensive CRUD tools
- Travel (planned): Booking platforms, itinerary management, expense integration
- HR (planned): Employee onboarding, feedback systems, organizational management
- Document (planned): OCR processing, content extraction, workflow automation
- Finance (planned): Expense reporting, approval workflows, budget tracking

Architecture patterns:
- Independent deployment with health monitoring
- Capability-based registration and discovery
- LangGraph state management for complex workflows
- Tool composition for comprehensive functionality
- A2A protocol compliance for seamless integration
"""

from .salesforce import salesforce_graph, build_salesforce_graph, SalesforceA2AHandler  # pyright: ignore[reportAttributeAccessIssue]

__all__ = [
    "salesforce_graph",
    "build_salesforce_graph",
    "SalesforceA2AHandler"
]