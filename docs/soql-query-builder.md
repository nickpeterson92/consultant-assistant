# SOQL Query Builder Documentation

## Overview

The SOQL Query Builder provides a fluent, type-safe interface for constructing Salesforce Object Query Language (SOQL) queries. It serves as a critical security and productivity component in the Salesforce integration layer, automatically handling escaping, proper formatting, and following Salesforce best practices while eliminating SOQL injection vulnerabilities.

## Architecture

### Query Builder Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    SOQL Query Builder Architecture              │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────┐   │
│  │   SOQLQuery     │  │  SearchQuery     │  │     Query     │   │
│  │    Builder      │  │    Builder       │  │   Templates   │   │
│  │   (Core)        │  │  (Advanced)      │  │  (Patterns)   │   │
│  └─────────────────┘  └──────────────────┘  └───────────────┘   │
│           │                      │                     │        │
│           ▼                      ▼                     ▼        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                Security & Validation Layer              │    │
│  ├─────────────────┬─────────────────┬─────────────────────┤    │ 
│  │ SOQL Injection  │ Type Validation │ Operator Safety     │    │
│  │   Prevention    │    & Escaping   │   & Constraints     │    │
│  └─────────────────┴─────────────────┴────────────────────      │
│                                │                                │
│                                ▼                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              SOQL Query Generation                      │    │
│  ├─────────────────┬─────────────────┬─────────────────────┤    │
│  │ SELECT Clauses  │ WHERE Conditions│ ORDER/LIMIT/OFFSET  │    │
│  └─────────────────┴─────────────────┴─────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Core Design Principles

1. **Security First**: Automatic SOQL injection prevention through parameterization
2. **Fluent Interface**: Chainable methods for readable query construction
3. **Type Safety**: Proper handling of different data types and operators
4. **Performance**: Optimized query patterns and field selection
5. **Reusability**: Common query patterns as reusable templates

## Core Implementation

### SOQLQueryBuilder Class

```python
class SOQLQueryBuilder:
    """Fluent interface for building SOQL queries"""
    
    def __init__(self, sobject: str):
        self.sobject = sobject
        self.select_fields = []
        self.where_conditions = []
        self.order_by_clauses = []
        self.limit_value = None
        self.offset_value = None
    
    def select(self, fields: List[str]) -> 'SOQLQueryBuilder':
        """Add SELECT fields"""
        self.select_fields.extend(fields)
        return self
    
    def where(self, field: str, operator: SOQLOperator, value: Any) -> 'SOQLQueryBuilder':
        """Add WHERE condition with proper escaping"""
        escaped_value = escape_soql_value(value)
        condition = f"{field} {operator.value} {escaped_value}"
        self.where_conditions.append(("AND", condition))
        return self
    
    def or_where(self, field: str, operator: SOQLOperator, value: Any) -> 'SOQLQueryBuilder':
        """Add OR WHERE condition"""
        escaped_value = escape_soql_value(value)
        condition = f"{field} {operator.value} {escaped_value}"
        self.where_conditions.append(("OR", condition))
        return self
    
    def build(self) -> str:
        """Generate final SOQL query"""
        query_parts = []
        
        # SELECT clause
        fields = ", ".join(self.select_fields) if self.select_fields else "*"
        query_parts.append(f"SELECT {fields}")
        
        # FROM clause
        query_parts.append(f"FROM {self.sobject}")
        
        # WHERE clause
        if self.where_conditions:
            where_clause = self._build_where_clause()
            query_parts.append(f"WHERE {where_clause}")
        
        # ORDER BY clause
        if self.order_by_clauses:
            order_clause = ", ".join(self.order_by_clauses)
            query_parts.append(f"ORDER BY {order_clause}")
        
        # LIMIT clause
        if self.limit_value:
            query_parts.append(f"LIMIT {self.limit_value}")
        
        # OFFSET clause
        if self.offset_value:
            query_parts.append(f"OFFSET {self.offset_value}")
        
        return " ".join(query_parts)
```

### SOQL Operators Enum

```python
class SOQLOperator(Enum):
    """Type-safe SOQL operators"""
    EQUALS = "="
    NOT_EQUALS = "!="
    LESS_THAN = "<"
    LESS_THAN_OR_EQUAL = "<="
    GREATER_THAN = ">"
    GREATER_THAN_OR_EQUAL = ">="
    LIKE = "LIKE"
    IN = "IN"
    NOT_IN = "NOT IN"
    INCLUDES = "INCLUDES"
    EXCLUDES = "EXCLUDES"
```

## Security Features

### SOQL Injection Prevention

```python
def escape_soql_value(value: Any) -> str:
    """Escape values for SOQL injection prevention"""
    
    if value is None:
        return "null"
    elif isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, str):
        # Escape single quotes and backslashes
        escaped = value.replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"
    elif isinstance(value, list):
        # For IN clauses
        escaped_items = [escape_soql_value(item) for item in value]
        return f"({', '.join(escaped_items)})"
    else:
        # Convert to string and escape
        escaped = str(value).replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"
```

### Input Validation

```python
def validate_field_name(field: str) -> str:
    """Validate and sanitize field names"""
    
    # Allow alphanumeric, underscores, dots (for relationships)
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_\.]*$', field):
        raise ValueError(f"Invalid field name: {field}")
    
    return field

def validate_sobject_name(sobject: str) -> str:
    """Validate Salesforce object names"""
    
    # Standard and custom objects
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*(__c)?$', sobject):
        raise ValueError(f"Invalid sObject name: {sobject}")
    
    return sobject
```

## Query Building Patterns

### Basic Query Construction

```python
# Simple query
query = (SOQLQueryBuilder('Account')
        .select(['Id', 'Name', 'Industry'])
        .where('Name', SOQLOperator.LIKE, '%Acme%')
        .build())
# Result: SELECT Id, Name, Industry FROM Account WHERE Name LIKE '%Acme%'

# Multiple conditions
query = (SOQLQueryBuilder('Opportunity')
        .select(['Id', 'Name', 'Amount'])
        .where('StageName', SOQLOperator.EQUALS, 'Closed Won')
        .where('Amount', SOQLOperator.GREATER_THAN, 100000)
        .order_by('Amount', descending=True)
        .limit(10)
        .build())
```

### Convenience Methods

```python
class SOQLQueryBuilder:
    
    def where_id(self, record_id: str) -> 'SOQLQueryBuilder':
        """Convenience method for ID filtering"""
        return self.where('Id', SOQLOperator.EQUALS, record_id)
    
    def where_like(self, field: str, pattern: str) -> 'SOQLQueryBuilder':
        """Convenience method for LIKE patterns"""
        return self.where(field, SOQLOperator.LIKE, pattern)
    
    def where_in(self, field: str, values: List[Any]) -> 'SOQLQueryBuilder':
        """Convenience method for IN clauses"""
        return self.where(field, SOQLOperator.IN, values)
    
    def where_null(self, field: str) -> 'SOQLQueryBuilder':
        """Convenience method for null checks"""
        return self.where(field, SOQLOperator.EQUALS, None)
    
    def where_not_null(self, field: str) -> 'SOQLQueryBuilder':
        """Convenience method for not null checks"""
        return self.where(field, SOQLOperator.NOT_EQUALS, None)
    
    def order_by(self, field: str, descending: bool = False) -> 'SOQLQueryBuilder':
        """Add ORDER BY clause"""
        direction = " DESC" if descending else ""
        self.order_by_clauses.append(f"{field}{direction}")
        return self
    
    def limit(self, count: int) -> 'SOQLQueryBuilder':
        """Add LIMIT clause"""
        self.limit_value = count
        return self
    
    def offset(self, count: int) -> 'SOQLQueryBuilder':
        """Add OFFSET clause"""
        self.offset_value = count
        return self
```

### Complex Query Examples

```python
# Multi-condition with OR logic
query = (SOQLQueryBuilder('Lead')
        .select(['Id', 'Name', 'Company', 'Status'])
        .where('Status', SOQLOperator.EQUALS, 'New')
        .or_where('Status', SOQLOperator.EQUALS, 'Working')
        .where('Company', SOQLOperator.NOT_EQUALS, None)
        .order_by('CreatedDate', descending=True)
        .limit(50)
        .build())

# Relationship queries
query = (SOQLQueryBuilder('Contact')
        .select(['Id', 'Name', 'Email', 'Account.Name', 'Account.Industry'])
        .where('Account.Industry', SOQLOperator.EQUALS, 'Technology')
        .where_not_null('Email')
        .build())
```

## Advanced Features

### SearchQueryBuilder

```python
class SearchQueryBuilder:
    """Advanced search with natural language support"""
    
    def __init__(self, sf_connection, sobject: str):
        self.sf = sf_connection
        self.query_builder = SOQLQueryBuilder(sobject)
        self.search_executed = False
    
    def search_fields(self, fields: List[str], search_term: str) -> 'SearchQueryBuilder':
        """Search across multiple fields"""
        
        # Add OR conditions for each field
        for i, field in enumerate(fields):
            if i == 0:
                self.query_builder.where_like(field, f'%{search_term}%')
            else:
                self.query_builder.or_where(field, SOQLOperator.LIKE, f'%{search_term}%')
        
        return self
    
    def with_account_filter(self, account_name: str) -> 'SearchQueryBuilder':
        """Filter by account name"""
        self.query_builder.where_like('Account.Name', f'%{account_name}%')
        return self
    
    def recent_first(self) -> 'SearchQueryBuilder':
        """Order by most recent first"""
        self.query_builder.order_by('CreatedDate', descending=True)
        return self
    
    def execute(self) -> List[Dict[str, Any]]:
        """Execute the search query"""
        query = self.query_builder.build()
        result = self.sf.query(query)
        return result['records']
```

### Query Templates

```python
class QueryTemplates:
    """Pre-built query patterns for common operations"""
    
    @staticmethod
    def get_all_related_records(account_id: str) -> Dict[str, str]:
        """Get all related records for an account"""
        
        return {
            'contacts': (SOQLQueryBuilder('Contact')
                        .select(['Id', 'Name', 'Email', 'Phone', 'Title'])
                        .where('AccountId', SOQLOperator.EQUALS, account_id)
                        .order_by('Name')
                        .build()),
            
            'opportunities': (SOQLQueryBuilder('Opportunity')
                            .select(['Id', 'Name', 'Amount', 'StageName', 'CloseDate'])
                            .where('AccountId', SOQLOperator.EQUALS, account_id)
                            .order_by('CloseDate', descending=True)
                            .build()),
            
            'cases': (SOQLQueryBuilder('Case')
                     .select(['Id', 'Subject', 'Status', 'Priority', 'CreatedDate'])
                     .where('AccountId', SOQLOperator.EQUALS, account_id)
                     .order_by('CreatedDate', descending=True)
                     .build())
        }
    
    @staticmethod
    def search_by_email_domain(sobject: str, domain: str) -> str:
        """Search records by email domain"""
        return (SOQLQueryBuilder(sobject)
               .select(['Id', 'Name', 'Email'])
               .where_like('Email', f'%@{domain}')
               .build())
    
    @staticmethod
    def get_recent_records(sobject: str, days: int = 7) -> str:
        """Get records created in the last N days"""
        from datetime import datetime, timedelta
        
        date_filter = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        return (SOQLQueryBuilder(sobject)
               .select(['Id', 'Name', 'CreatedDate'])
               .where('CreatedDate', SOQLOperator.GREATER_THAN_OR_EQUAL, f'{date_filter}T00:00:00Z')
               .order_by('CreatedDate', descending=True)
               .build())
    
    @staticmethod
    def get_stale_opportunities(days: int = 30) -> str:
        """Find opportunities with no recent activity"""
        from datetime import datetime, timedelta
        
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        return (SOQLQueryBuilder('Opportunity')
               .select(['Id', 'Name', 'LastActivityDate', 'Owner.Name', 'Amount'])
               .where('IsClosed', SOQLOperator.EQUALS, False)
               .where('LastActivityDate', SOQLOperator.LESS_THAN, f'{cutoff_date}T00:00:00Z')
               .order_by('LastActivityDate')
               .build())
```

## Integration with Salesforce Tools

### Tool Implementation Pattern

```python
class GetLeadTool(BaseTool):
    """Example using query builder pattern"""
    
    def _run(self, **kwargs) -> dict:
        data = GetLeadInput(**kwargs)
        
        try:
            sf = get_salesforce_connection()
            
            # Use query builder for clean, safe queries
            builder = SOQLQueryBuilder('Lead').select([
                'Id', 'Name', 'Company', 'Email', 'Phone', 'Status'
            ])
            
            if data.lead_id:
                builder.where_id(data.lead_id)
            else:
                # Build OR conditions dynamically
                search_fields = [
                    ('Email', data.email),
                    ('Name', data.name),
                    ('Phone', data.phone),
                    ('Company', data.company)
                ]
                
                conditions_added = False
                for field, value in search_fields:
                    if value:
                        if not conditions_added:
                            builder.where_like(field, f'%{value}%')
                            conditions_added = True
                        else:
                            builder.or_where(field, SOQLOperator.LIKE, f'%{value}%')
                
                if not conditions_added:
                    return {"error": "No search criteria provided"}
            
            query = builder.build()
            records = sf.query(query)['records']
            
            return {
                "leads": records,
                "count": len(records),
                "query_used": query
            }
            
        except Exception as e:
            return {"error": f"Lead retrieval failed: {str(e)}"}
```

### Migration from String Concatenation

**Before (Error-prone)**:
```python
if data.lead_id:
    escaped_id = escape_soql(data.lead_id)
    query = f"SELECT Id, Name FROM Lead WHERE Id = '{escaped_id}'"
else:
    query_conditions = []
    if data.email:
        escaped_email = escape_soql(data.email)
        query_conditions.append(f"Email LIKE '%{escaped_email}%'")
    # ... repeat for each field
    
    if not query_conditions:
        return {"error": "No search criteria provided"}
    
    query = f"SELECT Id, Name FROM Lead WHERE {' OR '.join(query_conditions)}"
```

**After (Clean & Safe)**:
```python
builder = SOQLQueryBuilder('Lead').select(['Id', 'Name'])

if data.lead_id:
    builder.where_id(data.lead_id)
else:
    search_fields = [(field, value) for field, value in [
        ('Email', data.email),
        ('Name', data.name),
        # ... other fields
    ] if value]
    
    if not search_fields:
        return {"error": "No search criteria provided"}
    
    for i, (field, value) in enumerate(search_fields):
        if i == 0:
            builder.where_like(field, f'%{value}%')
        else:
            builder.or_where(field, SOQLOperator.LIKE, f'%{value}%')

query = builder.build()
```

## SOQL Syntax Compliance

### Salesforce-Specific Rules

```python
# NULL comparisons (SOQL uses = null, not IS NULL)
builder.where('Email', SOQLOperator.EQUALS, None)
# Generates: Email = null

builder.where_null('Email')
# Generates: Email = null

builder.where_not_null('Email')
# Generates: Email != null

# Boolean values (lowercase)
builder.where('IsActive', SOQLOperator.EQUALS, True)
# Generates: IsActive = true

# Date/DateTime formatting
builder.where('CreatedDate', SOQLOperator.GREATER_THAN, '2024-01-01T00:00:00Z')
# Generates: CreatedDate > 2024-01-01T00:00:00Z

# IN clauses with proper escaping
builder.where_in('Industry', ['Technology', 'Healthcare', 'Finance'])
# Generates: Industry IN ('Technology', 'Healthcare', 'Finance')
```

## Performance Optimization

### Query Efficiency Patterns

```python
# 1. Select only required fields
builder.select(['Id', 'Name'])  # Good
# Avoid selecting all fields unnecessarily

# 2. Use indexed fields for WHERE clauses
builder.where_id('001234567890ABC')  # ID is always indexed
builder.where('Name', SOQLOperator.EQUALS, 'Acme Corp')  # Name is often indexed

# 3. Always use LIMIT for better performance
builder.limit(200)  # Standard batch size

# 4. Avoid negative operators when possible
# Avoid: Status != 'Active' (can cause full table scan)
# Better: Status IN ('New', 'Working', 'Qualified')
builder.where_in('Status', ['New', 'Working', 'Qualified'])

# 5. Efficient pagination
def get_all_records(sobject: str, batch_size: int = 200) -> List[Dict]:
    all_records = []
    offset = 0
    
    while True:
        batch = (SOQLQueryBuilder(sobject)
                .select(['Id', 'Name'])
                .limit(batch_size)
                .offset(offset)
                .build())
        
        results = sf.query(batch)['records']
        if not results:
            break
        
        all_records.extend(results)
        offset += batch_size
        
        # Prevent runaway queries
        if len(all_records) > 10000:
            break
    
    return all_records
```

### Query Caching

```python
from functools import lru_cache
from typing import Optional

class CachedQueryBuilder:
    """Query builder with caching for common patterns"""
    
    @lru_cache(maxsize=100)
    def get_account_id_by_name(self, name: str) -> Optional[str]:
        """Cache account lookups by name"""
        query = (SOQLQueryBuilder('Account')
                .select(['Id'])
                .where_like('Name', f'%{name}%')
                .limit(1)
                .build())
        
        results = sf.query(query)['records']
        return results[0]['Id'] if results else None
    
    @lru_cache(maxsize=50)
    def get_record_type_id(self, sobject: str, developer_name: str) -> Optional[str]:
        """Cache record type lookups"""
        query = (SOQLQueryBuilder('RecordType')
                .select(['Id'])
                .where('SObjectType', SOQLOperator.EQUALS, sobject)
                .where('DeveloperName', SOQLOperator.EQUALS, developer_name)
                .limit(1)
                .build())
        
        results = sf.query(query)['records']
        return results[0]['Id'] if results else None
```

## Testing Strategy

### Unit Tests

```python
class TestSOQLQueryBuilder:
    """Comprehensive test coverage for query builder"""
    
    def test_basic_query_construction(self):
        """Test basic SELECT FROM WHERE"""
        query = (SOQLQueryBuilder('Account')
                .select(['Id', 'Name'])
                .where('Industry', SOQLOperator.EQUALS, 'Technology')
                .build())
        
        expected = "SELECT Id, Name FROM Account WHERE Industry = 'Technology'"
        assert query == expected
    
    def test_soql_injection_prevention(self):
        """Test that malicious input is properly escaped"""
        malicious_input = "'; DELETE FROM Account WHERE '' = '"
        
        query = (SOQLQueryBuilder('Account')
                .select(['Id'])
                .where_like('Name', f'%{malicious_input}%')
                .build())
        
        # Should be safely escaped
        assert "DELETE" not in query.replace("\\'", "")
        assert "\\'" in query  # Quotes should be escaped
    
    def test_null_handling(self):
        """Test proper NULL handling"""
        query = (SOQLQueryBuilder('Contact')
                .select(['Id'])
                .where_null('Email')
                .build())
        
        expected = "SELECT Id FROM Contact WHERE Email = null"
        assert query == expected
    
    def test_boolean_handling(self):
        """Test boolean value formatting"""
        query = (SOQLQueryBuilder('Account')
                .select(['Id'])
                .where('IsActive', SOQLOperator.EQUALS, True)
                .build())
        
        expected = "SELECT Id FROM Account WHERE IsActive = true"
        assert query == expected
    
    def test_in_clause(self):
        """Test IN operator with list values"""
        query = (SOQLQueryBuilder('Opportunity')
                .select(['Id'])
                .where_in('StageName', ['New', 'Working', 'Qualified'])
                .build())
        
        expected = "SELECT Id FROM Opportunity WHERE StageName IN ('New', 'Working', 'Qualified')"
        assert query == expected
    
    def test_complex_query_with_all_clauses(self):
        """Test query with SELECT, WHERE, ORDER BY, LIMIT, OFFSET"""
        query = (SOQLQueryBuilder('Contact')
                .select(['Id', 'Name', 'Email'])
                .where('Account.Industry', SOQLOperator.EQUALS, 'Technology')
                .where_not_null('Email')
                .order_by('Name')
                .order_by('CreatedDate', descending=True)
                .limit(50)
                .offset(100)
                .build())
        
        expected = (
            "SELECT Id, Name, Email FROM Contact "
            "WHERE Account.Industry = 'Technology' AND Email != null "
            "ORDER BY Name, CreatedDate DESC LIMIT 50 OFFSET 100"
        )
        assert query == expected
```

### Integration Tests

```python
def test_query_builder_with_salesforce():
    """Test query builder with actual Salesforce connection"""
    
    # Test basic query execution
    query = (SOQLQueryBuilder('Account')
            .select(['Id', 'Name'])
            .limit(5)
            .build())
    
    results = sf.query(query)
    assert 'records' in results
    assert len(results['records']) <= 5
    
    # Test search functionality
    searcher = SearchQueryBuilder(sf, 'Contact')
    results = (searcher
              .search_fields(['Name'], 'Test')
              .query_builder.limit(10)
              .execute())
    
    assert isinstance(results, list)
    assert len(results) <= 10
```

## Best Practices

### 1. Query Construction

- Always use query builder instead of string concatenation
- Select only required fields for better performance
- Use convenience methods (where_id, where_like, etc.)
- Validate inputs before query construction
- Apply appropriate limits to prevent large result sets

### 2. Security

- Never bypass the query builder's escaping mechanism
- Validate field names and object names
- Be cautious with dynamic field selection
- Log queries in debug mode for troubleshooting
- Use parameterized queries through the builder

### 3. Performance

- Cache common queries and lookups
- Use indexed fields in WHERE clauses
- Implement efficient pagination for large datasets
- Monitor query execution times
- Avoid SELECT * equivalent operations

### 4. Maintenance

- Use query templates for common patterns
- Keep query logic centralized in builder methods
- Document complex query patterns
- Write comprehensive tests for custom queries
- Monitor query usage and optimize frequently used patterns

## Troubleshooting

### Common Issues

1. **SOQL Syntax Errors**
   - Verify field names are correct for the object
   - Check relationship field syntax (Account.Name)
   - Ensure proper escaping of special characters
   - Validate date/datetime formats

2. **Performance Issues**
   - Add appropriate LIMIT clauses
   - Use indexed fields in WHERE conditions
   - Avoid complex OR conditions on large objects
   - Consider query optimization patterns

3. **Injection Vulnerabilities**
   - Always use query builder methods
   - Never concatenate user input directly
   - Validate input data before query construction
   - Test with malicious input patterns

4. **Complex Logic Errors**
   - Break complex queries into simpler parts
   - Use query templates for tested patterns
   - Test query logic with sample data
   - Debug by examining generated SOQL

## Advanced Query Features (Implemented)

### Aggregate Functions

The query builder now supports all major aggregate functions:

```python
# Example: Sales pipeline analysis
query = (SOQLQueryBuilder('Opportunity')
    .select(['StageName'])
    .select_count('Id', 'OpportunityCount')
    .select_sum('Amount', 'TotalAmount')
    .select_avg('Amount', 'AvgAmount')
    .select_max('Amount', 'MaxDeal')
    .select_min('Amount', 'MinDeal')
    .group_by('StageName')
    .having('SUM(Amount)', SOQLOperator.GREATER_THAN, 0)
    .order_by('TotalAmount', descending=True)
    .build())
# Result: SELECT StageName, COUNT(Id) OpportunityCount, SUM(Amount) TotalAmount, 
#         AVG(Amount) AvgAmount, MAX(Amount) MaxDeal, MIN(Amount) MinDeal 
#         FROM Opportunity GROUP BY StageName HAVING SUM(Amount) > 0 
#         ORDER BY TotalAmount DESC
```

### GROUP BY and HAVING Clauses

Support for complex grouping and filtering of aggregated data:

```python
# Example: Top performing sales reps
query = (SOQLQueryBuilder('Opportunity')
    .select(['OwnerId', 'Owner.Name'])
    .select_count('Id', 'DealsWon')
    .select_sum('Amount', 'TotalRevenue')
    .where('IsClosed', SOQLOperator.EQUALS, True)
    .where('IsWon', SOQLOperator.EQUALS, True)
    .group_by(['OwnerId', 'Owner.Name'])
    .having('SUM(Amount)', SOQLOperator.GREATER_THAN, 1000000)
    .order_by('TotalRevenue', descending=True)
    .limit(10)
    .build())
```

### Subquery Support

Build complex queries with nested subqueries:

```python
# Example: Accounts with their top opportunities
query = (SOQLQueryBuilder('Account')
    .select(['Id', 'Name', 'Industry'])
    .with_subquery('Opportunities', 'Opportunity', lambda sq: sq
        .select(['Id', 'Name', 'Amount', 'StageName'])
        .where('IsClosed', SOQLOperator.EQUALS, False)
        .order_by('Amount', descending=True)
        .limit(5))
    .where('Industry', SOQLOperator.EQUALS, 'Technology')
    .build())
# Result: SELECT Id, Name, Industry, 
#         (SELECT Id, Name, Amount, StageName FROM Opportunities 
#          WHERE IsClosed = false ORDER BY Amount DESC LIMIT 5) 
#         FROM Account WHERE Industry = 'Technology'
```

### SOSL (Salesforce Object Search Language)

Cross-object search capabilities:

```python
# Example: Search across multiple objects
query = (SOSLQueryBuilder()
    .find('Acme')
    .returning('Account', ['Id', 'Name', 'Industry'], 
              where_clause="Industry = 'Technology'")
    .returning('Contact', ['Id', 'Name', 'Email', 'Account.Name'])
    .returning('Opportunity', ['Id', 'Name', 'Amount'], 
              where_clause='Amount > 50000')
    .returning('Lead', ['Id', 'Name', 'Company'])
    .limit(50)
    .build())
# Result: FIND {Acme} IN ALL FIELDS 
#         RETURNING Account(Id, Name, Industry WHERE Industry = 'Technology'), 
#                   Contact(Id, Name, Email, Account.Name), 
#                   Opportunity(Id, Name, Amount WHERE Amount > 50000), 
#                   Lead(Id, Name, Company) 
#         LIMIT 50
```

### Pre-built Aggregate Patterns

Common analytical queries available out-of-the-box:

```python
# Opportunity pipeline by stage
query = AggregateQueryBuilder.opportunity_pipeline_by_stage()

# Account metrics by industry
query = AggregateQueryBuilder.account_summary_by_industry()

# Top sales representatives
query = AggregateQueryBuilder.top_sales_reps(min_revenue=500000)

# Case volume analysis
query = AggregateQueryBuilder.case_volume_by_priority()
```

### Enterprise Analytics Tools Integration

The SOQL Query Builder now powers 5 advanced analytics tools in the Salesforce agent:

#### 1. Sales Pipeline Analysis (`GetSalesPipelineTool`)
```python
# Generated SOQL for pipeline analysis
SELECT StageName, COUNT(Id) OpportunityCount, 
       SUM(Amount) TotalAmount, AVG(Amount) AvgAmount 
FROM Opportunity 
GROUP BY StageName 
HAVING SUM(Amount) > 0 
ORDER BY SUM(Amount) DESC
```

#### 2. Performance Analytics (`GetTopPerformersTool`)
```python
# Top performers by revenue
SELECT OwnerId, Owner.Name, COUNT(Id) DealsWon, SUM(Amount) TotalRevenue 
FROM Opportunity 
WHERE IsClosed = true AND IsWon = true 
GROUP BY OwnerId, Owner.Name 
HAVING SUM(Amount) > 100000 
ORDER BY SUM(Amount) DESC LIMIT 10
```

#### 3. Cross-Object Search (`GlobalSearchTool`)
```sosl
FIND {search_term} IN ALL FIELDS 
RETURNING Account(Id, Name, Industry, Phone LIMIT 20),
         Contact(Id, Name, Email, Account.Name LIMIT 20),
         Opportunity(Id, Name, Amount, StageName LIMIT 20),
         Lead(Id, Name, Company, Status LIMIT 20)
```

#### 4. Account Intelligence (`GetAccountInsightsTool`)
```python
# Account 360 with subqueries
SELECT Id, Name, Industry, AnnualRevenue,
       (SELECT Id, Name, Amount, StageName FROM Opportunities LIMIT 10),
       (SELECT Id, Name, Email, Title FROM Contacts LIMIT 5),
       (SELECT Id, Subject, Status, Priority FROM Cases WHERE IsClosed = false LIMIT 5)
FROM Account WHERE Name LIKE '%{account_name}%'
```

#### 5. Business Metrics (`GetBusinessMetricsTool`)
```python
# Revenue analysis by time period
SELECT Account.Industry, COUNT(Id) DealCount, 
       SUM(Amount) TotalRevenue, AVG(Amount) AvgDealSize 
FROM Opportunity 
WHERE IsClosed = true AND IsWon = true AND CloseDate = THIS_QUARTER 
GROUP BY Account.Industry
```

### Advanced SOQL Syntax Handling

The query builder handles complex SOQL syntax requirements:

#### Date Literal Handling
```python
# Proper date literal formatting (no quotes)
query = (SOQLQueryBuilder('Opportunity')
    .select(['Id', 'Name', 'CloseDate'])
    .where('CloseDate', SOQLOperator.EQUALS, 'THIS_QUARTER')  # No quotes added
    .build())
# Result: SELECT Id, Name, CloseDate FROM Opportunity WHERE CloseDate = THIS_QUARTER
```

#### Aggregate Expression Ordering
```python
# ORDER BY using aggregate expressions, not aliases
query = (SOQLQueryBuilder('Opportunity')
    .select(['StageName'])
    .select_sum('Amount', 'TotalAmount')
    .group_by('StageName')
    .order_by('SUM(Amount)', descending=True)  # Use actual aggregate function
    .build())
# Result: SELECT StageName, SUM(Amount) TotalAmount FROM Opportunity 
#         GROUP BY StageName ORDER BY SUM(Amount) DESC
```

#### Complex HAVING Clauses
```python
# HAVING with multiple conditions
query = (SOQLQueryBuilder('Opportunity')
    .select(['OwnerId'])
    .select_count('Id', 'OpptyCount')
    .select_sum('Amount', 'TotalRevenue')
    .group_by('OwnerId')
    .having('COUNT(Id)', SOQLOperator.GREATER_THAN, 5)
    .having('SUM(Amount)', SOQLOperator.GREATER_THAN, 1000000)
    .build())
```

## Implementation Status

### ✅ Completed Features

The following advanced features have been successfully implemented and are production-ready:

1. **Aggregate Functions** - Full support for COUNT, SUM, AVG, MAX, MIN with proper aliases
2. **GROUP BY Clauses** - Single and multiple field grouping with relationship support
3. **HAVING Clauses** - Aggregate filtering with complex conditions
4. **Subquery Support** - Nested queries with relationship-aware construction
5. **SOSL Integration** - Cross-object search with flexible RETURNING clauses
6. **Advanced Analytics Tools** - Pre-built patterns for common business intelligence queries
7. **Security Hardening** - Enhanced SOQL injection prevention with comprehensive escaping
8. **Performance Optimization** - Connection pooling, efficient pagination, and query optimization

### 🚀 Recent Enhancements (v2.0)

#### Enhanced Analytics Capabilities
- **Pipeline Analysis**: Comprehensive sales pipeline reporting with stage-based aggregations
- **Performance Metrics**: Sales rep ranking with revenue, deal count, and win rate calculations
- **Business Intelligence**: KPI tracking with time-based analysis and industry segmentation
- **Account 360**: Complete account views with subquery-driven related record retrieval

#### Advanced Query Patterns
- **Complex Aggregations**: Multi-level grouping with relationship field support
- **Time-Based Analytics**: Calendar functions for trend analysis and period comparisons
- **Cross-Object Search**: SOSL integration for global search across all Salesforce objects
- **Dynamic Filtering**: Runtime query construction with flexible condition building

#### Security & Performance
- **Enhanced Escaping**: Comprehensive SOQL injection prevention with edge case handling
- **Query Optimization**: Automatic query plan optimization and field selection efficiency
- **Connection Management**: HTTP connection pooling with automatic cleanup
- **Error Resilience**: Graceful degradation with circuit breaker pattern integration

### 🔄 Future Enhancements

#### Performance Improvements
- Query result caching layer for frequently accessed data
- Query plan analysis and optimization recommendations
- ~~Automatic query optimization~~ ✅ **Basic implementation complete**
- ~~Batch query execution~~ ✅ **Implemented in connection pooling**

#### Developer Experience
- Visual query builder UI for complex query construction
- IntelliSense/autocomplete for Salesforce fields and objects
- Query performance profiling with execution time analysis
- Real-time query validation with syntax checking

#### Integration Features
- GraphQL-style query interface for modern API consumption
- REST API query endpoint for external system integration
- Webhook query triggers for real-time data processing
- ~~Cross-object relationship mapping~~ ✅ **Implemented in subqueries**

#### Advanced Analytics
- Machine learning integration for predictive analytics
- Custom dashboard generation from query results
- Automated report scheduling and delivery
- Data visualization integration with popular BI tools