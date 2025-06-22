# SOQL Query Builder Documentation

## Overview

The SOQL Query Builder provides a fluent, type-safe interface for constructing Salesforce Object Query Language (SOQL) queries. It automatically handles escaping, proper formatting, and follows Salesforce best practices.

## Key Features

- **Fluent Interface**: Chain methods for readable query construction
- **Automatic Escaping**: Prevents SOQL injection attacks
- **Type Safety**: Proper handling of different data types (strings, numbers, booleans, nulls)
- **Reusable Templates**: Common query patterns ready to use
- **Relationship Support**: Easy construction of relationship queries
- **Performance Optimized**: Field selection and query optimization

## Basic Usage

### Simple Query
```python
from src.utils.soql_query_builder import SOQLQueryBuilder

query = (SOQLQueryBuilder('Account')
        .select(['Id', 'Name', 'Industry'])
        .where_like('Name', '%Acme%')
        .build())
# SELECT Id, Name, Industry FROM Account WHERE Name LIKE '%Acme%'
```

### Multiple Conditions
```python
query = (SOQLQueryBuilder('Opportunity')
        .select(['Id', 'Name', 'Amount'])
        .where('StageName', SOQLOperator.EQUALS, 'Closed Won')
        .where('Amount', SOQLOperator.GREATER_THAN, 100000)
        .order_by('Amount', descending=True)
        .limit(10)
        .build())
# SELECT Id, Name, Amount FROM Opportunity 
# WHERE StageName = 'Closed Won' AND Amount > 100000 
# ORDER BY Amount DESC LIMIT 10
```

## SOQL Syntax Notes

Based on Salesforce documentation:

### NULL Comparisons
SOQL uses `= null` and `!= null` (not `IS NULL`):
```python
# Check for NULL
builder.where('Email', SOQLOperator.EQUALS, None)
# or use convenience method
builder.where_null('Email')
# Generates: Email = null

# Check for NOT NULL
builder.where('Email', SOQLOperator.NOT_EQUALS, None)
# or use convenience method
builder.where_not_null('Email')
# Generates: Email != null
```

### Boolean Values
SOQL uses lowercase `true` and `false`:
```python
builder.where('IsActive', SOQLOperator.EQUALS, True)
# Generates: IsActive = true
```

### Empty Strings
Empty strings are treated as NULL in Salesforce:
```python
builder.where('Name', SOQLOperator.EQUALS, '')
# Generates: Name = ''
```

## Advanced Features

### OR Conditions
```python
query = (SOQLQueryBuilder('Lead')
        .select(['Id', 'Name', 'Company'])
        .where('Status', SOQLOperator.EQUALS, 'New')
        .or_where('Status', SOQLOperator.EQUALS, 'Working')
        .build())
# SELECT Id, Name, Company FROM Lead 
# WHERE Status = 'New' OR Status = 'Working'
```

### IN Operator
```python
query = (SOQLQueryBuilder('Account')
        .select(['Id', 'Name'])
        .where_in('Industry', ['Technology', 'Healthcare', 'Finance'])
        .build())
# SELECT Id, Name FROM Account 
# WHERE Industry IN ('Technology', 'Healthcare', 'Finance')
```

### Complex Queries
```python
query = (SOQLQueryBuilder('Contact')
        .select(['Id', 'Name', 'Email'])
        .where_like('Email', '%@gmail.com')
        .where('Account.Industry', SOQLOperator.EQUALS, 'Technology')
        .where_not_null('Phone')
        .order_by('LastName')
        .order_by('FirstName')
        .limit(50)
        .offset(100)
        .build())
```

## Search Query Builder

For flexible searching across multiple fields:

```python
from src.utils.soql_query_builder import SearchQueryBuilder

searcher = SearchQueryBuilder(sf, 'Contact')
results = (searcher
          .search_fields(['Name', 'Email', 'Phone'], 'john')
          .with_account_filter('Acme Corp')
          .recent_first()
          .execute())
```

## Query Templates

Pre-built templates for common operations:

```python
from src.utils.soql_query_builder import QueryTemplates

# Get all related records for an account
queries = QueryTemplates.get_all_related_records('001234567890ABC')
contacts = sf.query(queries['contacts'])['records']
opportunities = sf.query(queries['opportunities'])['records']

# Search by email domain
query = QueryTemplates.search_by_email_domain('Contact', 'example.com')
results = sf.query(query)['records']

# Get recent records
query = QueryTemplates.get_recent_records('Lead', days=7)
recent_leads = sf.query(query)['records']
```

## Integration with Salesforce Tools

All 15 Salesforce tools now use the query builder pattern:

```python
# Example from GetLeadTool
builder = SOQLQueryBuilder('Lead').select(['Id', 'Name', 'Company', 'Email', 'Phone', 'Status'])

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

query = builder.build()
records = sf.query(query)['records']
```

## Benefits Over String Concatenation

### Before (Error-prone)
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
```

### After (Clean & Safe)
```python
builder = SOQLQueryBuilder('Lead').select(['Id', 'Name'])
if data.lead_id:
    builder.where_id(data.lead_id)
else:
    if data.email:
        builder.where_like('Email', f'%{data.email}%')
```

## Performance Tips

1. **Select Only Required Fields**: Don't use `SELECT *` equivalent
   ```python
   builder.select(['Id', 'Name'])  # Good
   builder.select(all_fields)      # Avoid
   ```

2. **Use Indexes**: Filter on indexed fields when possible
   ```python
   builder.where_id('001234567890ABC')  # ID is always indexed
   ```

3. **Limit Results**: Always use LIMIT for better performance
   ```python
   builder.limit(200)
   ```

4. **Avoid Negative Operators**: They can cause full table scans
   ```python
   # Avoid
   builder.where('Status', SOQLOperator.NOT_EQUALS, 'Active')
   
   # Better
   builder.where_in('Status', ['New', 'Working', 'Qualified'])
   ```

## Error Handling

The query builder automatically escapes all string values to prevent SOQL injection:

```python
malicious_input = "'; DELETE FROM Account WHERE '' = '"
builder.where_like('Name', f'%{malicious_input}%')
# Safely generates: Name LIKE '%\'; DELETE FROM Account WHERE \'\' = \'%'
```

## Testing

Comprehensive test coverage ensures reliability:
- 41 tests covering all query builder functionality
- Tests for security (injection prevention)
- Tests for all SOQL operators and edge cases
- Real-world scenario tests

Run tests with:
```bash
python -m pytest tests/test_soql_query_builder.py -v
```

## Migration Guide

To migrate existing code to use the query builder:

1. Replace string concatenation with builder methods
2. Remove manual escaping (builder handles it)
3. Use convenience methods for common patterns
4. Test thoroughly with existing data

## Future Enhancements

- Aggregate function support (COUNT, SUM, etc.)
- GROUP BY and HAVING clauses
- Subquery support
- Query result caching
- Visual query builder UI