# Unified Tool Description Pattern

## Description Format Standard

Each tool description should follow this pattern:

```
{ACTION VERB} {OBJECT} {WHEN CLAUSE} - {DISTINCTION}
```

- **ACTION VERB**: Start with a clear action (Retrieve, Find, Calculate, Add, Modify, etc.)
- **OBJECT**: What the tool operates on
- **WHEN CLAUSE**: When to use this tool  
- **DISTINCTION**: How it differs from similar tools

## Key Principles

1. **Be Action-Oriented**: Start with verbs that clearly indicate what the tool does
2. **Specify Use Cases**: Include "when" or "use for" to guide selection
3. **Differentiate Clearly**: Explicitly state what makes this tool different
4. **Keep It Concise**: Maximum 2 lines, ideally 1

## Standard Verbs by Operation Type

### Read Operations
- **Retrieve**: Get a single specific record by ID/key
- **Find**: Search for records using criteria  
- **Calculate**: Compute aggregations and metrics
- **Discover**: Search across multiple object types

### Write Operations  
- **Add**: Create new records
- **Modify**: Update existing records
- **Execute**: Perform workflow actions

### Collaboration Operations
- **Manage**: Handle relationships and interactions

## Proposed Descriptions

### Salesforce Tools

```python
# Current → Proposed
SalesforceGet:
    Current: "Retrieve a single record when you have its ID (15 or 18 character identifier)"
    Proposed: "Retrieve a single Salesforce record by ID - use when you have the exact 15/18 character identifier"

SalesforceSearch:
    Current: "LIST individual records with details - use when you need the actual records, not summaries (e.g., list all opportunities, show contacts)"
    Proposed: "Find Salesforce records using filters or natural language - returns actual records with details (not summaries)"

SalesforceCreate:
    Current: "Add a new record to Salesforce (lead, contact, opportunity, case, etc.)"
    Proposed: "Add new records to Salesforce - handles any object type with automatic field validation"

SalesforceUpdate:
    Current: "Modify existing records - change field values, update status, etc."
    Proposed: "Modify existing Salesforce records - supports single updates by ID or bulk updates with conditions"

SalesforceSOSL:
    Current: "Search across MULTIPLE object types simultaneously - use ONLY when you don't know which object contains the data"
    Proposed: "Discover records across multiple Salesforce objects - use when object type is unknown or searching globally"

SalesforceAnalytics:
    Current: "CALCULATE aggregated numbers and statistics - use ONLY for totals, averages, counts, insights (NOT for listing records)"
    Proposed: "Calculate Salesforce metrics and statistics - aggregations only (use Search to list individual records)"
```

### Jira Tools

```python
JiraGet:
    Current: "Get a Jira issue by key"
    Proposed: "Retrieve a single Jira issue by key - includes comments, attachments, and full context"

JiraSearch:
    Current: "Search Jira issues with flexible criteria"
    Proposed: "Find Jira issues using JQL or natural language - returns multiple issues matching criteria"

JiraCreate:
    Current: "Create a new Jira issue or subtask"
    Proposed: "Add new Jira issues or subtasks - supports all issue types with smart field handling"

JiraUpdate:
    Current: "Update Jira issue fields, status, or assignment"
    Proposed: "Modify Jira issues - handles field updates, status transitions, and assignments in one call"

JiraCollaboration:
    Current: "Add comments, attachments, or link issues"
    Proposed: "Manage Jira interactions - comments, attachments, and issue linking (not for field updates)"

JiraAnalytics:
    Current: "Get issue history, metrics, and analytics"
    Proposed: "Calculate Jira metrics and retrieve history - worklog analysis, project stats, and change tracking"
```

### ServiceNow Tools

```python
ServiceNowGet:
    Current: "Get a ServiceNow record by ID or number"
    Proposed: "Retrieve a single ServiceNow record - use sys_id or number (auto-detects INC/CHG/PRB prefixes)"

ServiceNowSearch:
    Current: "Search ServiceNow records with natural language or encoded queries"
    Proposed: "Find ServiceNow records using queries - supports natural language and encoded queries with dot-walking"

ServiceNowCreate:
    Current: "Create a new ServiceNow record"
    Proposed: "Add new ServiceNow records - validates required fields based on table type automatically"

ServiceNowUpdate:
    Current: "Update ServiceNow records"
    Proposed: "Modify ServiceNow records - single record by ID/number or bulk updates with conditions"

ServiceNowWorkflow:
    Current: "Handle ServiceNow workflow operations like approvals and state changes"
    Proposed: "Execute ServiceNow workflow actions - approvals, assignments, state transitions (not basic field updates)"

ServiceNowAnalytics:
    Current: "Get analytics, metrics, and statistics from ServiceNow"
    Proposed: "Calculate ServiceNow metrics - counts, breakdowns, and trends across any table"
```

## Implementation Example

```python
class SalesforceSearch(SalesforceReadTool):
    """Search any Salesforce object with natural language or structured queries."""
    name: str = "salesforce_search"
    description: str = "Find Salesforce records using filters or natural language - returns actual records with details (not summaries)"
```

## Benefits of This Pattern

1. **Consistency**: All tools follow the same format
2. **Clarity**: Action verbs make intent obvious
3. **Differentiation**: Clear distinctions prevent tool confusion
4. **LLM-Friendly**: Helps models choose the right tool
5. **Scannable**: Easy to quickly understand each tool's purpose

## Quick Reference Table

| Operation | Get | Search | Create | Update | Analytics | Special |
|-----------|-----|--------|--------|---------|-----------|---------|
| **Verb** | Retrieve | Find | Add | Modify | Calculate | Execute/Discover/Manage |
| **When** | Have exact ID | Need multiple | New record | Change existing | Need metrics | Workflow/Cross-object/Collab |
| **Returns** | Single record | Record list | Created record | Updated record | Statistics | Varies |
| **Example** | "get INC0001234" | "find open incidents" | "create new case" | "update ticket status" | "incident count by priority" | "approve change request" |