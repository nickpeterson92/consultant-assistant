"""Tools Package - Unified Architecture (2024 Best Practices).

This package contains domain-specific tool implementations following the unified
tool pattern that reduces complexity while increasing capability. Tools are the
atomic units that agents compose to fulfill user requests.

Current unified tool collections:
- salesforce_unified: 6 powerful, composable tools (reduced from 23)
  - SalesforceGet: Retrieve any record by ID
  - SalesforceSearch: Natural language search on any object
  - SalesforceCreate: Create any type of record
  - SalesforceUpdate: Update any record
  - SalesforceSOSL: Cross-object search
  - SalesforceAnalytics: Metrics and aggregations

- jira_unified: 6 unified tools (reduced from 15)
  - Similar pattern to Salesforce

Tool architecture principles:
- Unified tools that work across all object types
- LLM determines object types and parameters
- Natural language understanding built-in
- Simplified error handling with structured responses
- Minimal validation (trust the LLM)
- Composable operations

Key improvements from legacy:
- 74% reduction in tool count
- More flexible and powerful operations
- Better LLM understanding through focused tools
- Cleaner error messages guide retry behavior
- Removed unnecessary escaping/validation
"""