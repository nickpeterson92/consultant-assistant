"""Tools Package.

This package contains all domain-specific tool implementations that provide the
actual functionality for specialized agents in the multi-agent orchestrator system.
Tools are the atomic units of work that agents compose to fulfill user requests.

Current tool collections:
- salesforce_tools: Comprehensive CRM operations including 15 CRUD tools for
  managing leads, accounts, opportunities, contacts, cases, and tasks

Tool implementation patterns:
- Input validation with Pydantic models
- Comprehensive error handling and recovery
- Security measures (SQL injection prevention, input sanitization)
- Structured logging for observability
- Consistent response formats
- Batch operation support for efficiency

Each tool follows enterprise patterns:
- Single responsibility principle
- Idempotent operations where possible
- Comprehensive documentation
- Type safety with annotations
- Performance optimization
"""