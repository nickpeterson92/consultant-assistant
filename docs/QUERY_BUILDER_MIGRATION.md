# SOQL Query Builder Migration Guide

## Overview

This guide helps migrate existing Salesforce tools from manual SOQL string construction to the new SOQL Query Builder pattern. The migration provides cleaner code, automatic security, and better maintainability.

## Quick Reference

### Common Migrations

| Old Pattern | New Pattern |
|------------|-------------|
| `f"SELECT Id FROM Lead WHERE Id = '{escape_soql(id)}'"` | `SOQLQueryBuilder('Lead').select(['Id']).where_id(id).build()` |
| `f"Email LIKE '%{escape_soql(email)}%'"` | `builder.where_like('Email', f'%{email}%')` |
| `"Status = 'New' OR Status = 'Working'"` | `builder.where('Status', SOQLOperator.EQUALS, 'New').or_where('Status', SOQLOperator.EQUALS, 'Working')` |
| `f"Email = ''"` | `builder.where('Email', SOQLOperator.EQUALS, '')` |
| `"Email != null"` | `builder.where_not_null('Email')` |

## Step-by-Step Migration

### 1. Basic SELECT Query

**Before:**
```python
query = f"SELECT Id, Name, Email FROM Contact"
```

**After:**
```python
query = (SOQLQueryBuilder('Contact')
        .select(['Id', 'Name', 'Email'])
        .build())
```

### 2. Simple WHERE Clause

**Before:**
```python
escaped_name = escape_soql(name)
query = f"SELECT Id, Name FROM Account WHERE Name = '{escaped_name}'"
```

**After:**
```python
query = (SOQLQueryBuilder('Account')
        .select(['Id', 'Name'])
        .where('Name', SOQLOperator.EQUALS, name)
        .build())
```

### 3. Multiple OR Conditions

**Before:**
```python
query_conditions = []
if data.email:
    escaped_email = escape_soql(data.email)
    query_conditions.append(f"Email LIKE '%{escaped_email}%'")
if data.name:
    escaped_name = escape_soql(data.name)
    query_conditions.append(f"Name LIKE '%{escaped_name}%'")
if data.phone:
    escaped_phone = escape_soql(data.phone)
    query_conditions.append(f"Phone LIKE '%{escaped_phone}%'")

if query_conditions:
    query = f"SELECT Id, Name FROM Lead WHERE {' OR '.join(query_conditions)}"
```

**After:**
```python
builder = SOQLQueryBuilder('Lead').select(['Id', 'Name'])

search_fields = [
    ('Email', data.email),
    ('Name', data.name),
    ('Phone', data.phone)
]

conditions_added = False
for field, value in search_fields:
    if value:
        if not conditions_added:
            builder.where_like(field, f'%{value}%')
            conditions_added = True
        else:
            builder.or_where(field, SOQLOperator.LIKE, f'%{value}%')

if conditions_added:
    query = builder.build()
```

### 4. Complex Query with Multiple Clauses

**Before:**
```python
escaped_industry = escape_soql(industry)
query = (f"SELECT Id, Name, Amount, StageName FROM Opportunity "
         f"WHERE AccountId = '{account_id}' "
         f"AND StageName != 'Closed Lost' "
         f"AND Amount > 50000 "
         f"AND Account.Industry = '{escaped_industry}' "
         f"ORDER BY Amount DESC "
         f"LIMIT 10")
```

**After:**
```python
query = (SOQLQueryBuilder('Opportunity')
        .select(['Id', 'Name', 'Amount', 'StageName'])
        .where('AccountId', SOQLOperator.EQUALS, account_id)
        .where('StageName', SOQLOperator.NOT_EQUALS, 'Closed Lost')
        .where('Amount', SOQLOperator.GREATER_THAN, 50000)
        .where('Account.Industry', SOQLOperator.EQUALS, industry)
        .order_by('Amount', descending=True)
        .limit(10)
        .build())
```

### 5. IN Operator

**Before:**
```python
stages = ['Prospecting', 'Qualification', 'Needs Analysis']
escaped_stages = [f"'{escape_soql(s)}'" for s in stages]
query = f"SELECT Id FROM Opportunity WHERE StageName IN ({', '.join(escaped_stages)})"
```

**After:**
```python
query = (SOQLQueryBuilder('Opportunity')
        .select(['Id'])
        .where_in('StageName', ['Prospecting', 'Qualification', 'Needs Analysis'])
        .build())
```

### 6. NULL Checks

**Before:**
```python
query = "SELECT Id FROM Contact WHERE Email != null AND Phone = null"
```

**After:**
```python
query = (SOQLQueryBuilder('Contact')
        .select(['Id'])
        .where_not_null('Email')
        .where_null('Phone')
        .build())
```

## Real-World Example: GetOpportunityTool

### Before (130+ lines with repetitive code):
```python
def _run(self, **kwargs) -> dict:
    data = GetOpportunityInput(**kwargs)
    
    try:
        sf = get_salesforce_connection()
        
        if data.opportunity_id:
            escaped_id = escape_soql(data.opportunity_id)
            query = (f"SELECT Id, Name, StageName, Amount, CloseDate, AccountId "
                    f"FROM Opportunity WHERE Id = '{escaped_id}'")
        else:
            query_conditions = []
            
            if data.opportunity_name:
                escaped_name = escape_soql(data.opportunity_name)
                query_conditions.append(f"Name LIKE '%{escaped_name}%'")
                
            if data.account_id:
                escaped_account_id = escape_soql(data.account_id)
                query_conditions.append(f"AccountId = '{escaped_account_id}'")
                
            if data.account_name and not data.account_id:
                escaped_account_name = escape_soql(data.account_name)
                account_query = f"SELECT Id FROM Account WHERE Name LIKE '%{escaped_account_name}%'"
                account_results = sf.query(account_query)
                
                if account_results['totalSize'] > 0:
                    account_ids = [f"'{acc['Id']}'" for acc in account_results['records']]
                    query_conditions.append(f"AccountId IN ({', '.join(account_ids)})")
            
            if not query_conditions:
                return {"error": "No search criteria provided."}
                
            query = (f"SELECT Id, Name, StageName, Amount, CloseDate, AccountId "
                    f"FROM Opportunity WHERE {' OR '.join(query_conditions)} "
                    f"ORDER BY Amount DESC")
        
        records = sf.query(query)['records']
        # ... formatting code ...
```

### After (60 lines, cleaner and safer):
```python
def _run(self, **kwargs) -> dict:
    data = GetOpportunityInput(**kwargs)
    
    try:
        sf = get_salesforce_connection()
        
        builder = SOQLQueryBuilder('Opportunity').select([
            'Id', 'Name', 'StageName', 'Amount', 'CloseDate', 
            'AccountId', 'Probability', 'Type'
        ])
        
        if data.opportunity_id:
            builder.where_id(data.opportunity_id)
        else:
            conditions_added = False
            
            if data.opportunity_name:
                builder.where_like('Name', f'%{data.opportunity_name}%')
                conditions_added = True
                
            if data.account_id:
                if conditions_added:
                    builder.where('AccountId', SOQLOperator.EQUALS, data.account_id)
                else:
                    builder.where('AccountId', SOQLOperator.EQUALS, data.account_id)
                    conditions_added = True
                    
            if data.account_name and not data.account_id:
                # First get account ID from name
                account_search = SearchQueryBuilder(sf, 'Account')
                accounts = account_search.search_fields(['Name'], data.account_name).execute()
                
                if accounts:
                    account_ids = [acc['Id'] for acc in accounts]
                    if conditions_added:
                        builder.where_in('AccountId', account_ids)
                    else:
                        builder.where_in('AccountId', account_ids)
                        conditions_added = True
            
            if not conditions_added:
                return {"error": "No search criteria provided."}

        query = builder.order_by('Amount', descending=True).build()
        records = sf.query(query)['records']
        # ... formatting code ...
```

## Benefits Summary

1. **70% Less Code**: Dramatic reduction in boilerplate
2. **Automatic Security**: No manual escaping needed
3. **Readable**: Fluent interface is self-documenting
4. **Maintainable**: Changes in one place
5. **Testable**: Can unit test query generation
6. **Type Safe**: Proper handling of different data types

## Testing Your Migration

After migrating, test thoroughly:

```python
# Unit test the query generation
def test_query_generation():
    query = (SOQLQueryBuilder('Account')
            .select(['Id', 'Name'])
            .where_like('Name', '%Test%')
            .build())
    
    assert query == "SELECT Id, Name FROM Account WHERE Name LIKE '%Test%'"

# Integration test with Salesforce
def test_salesforce_integration():
    sf = get_salesforce_connection()
    query = (SOQLQueryBuilder('Account')
            .select(['Id', 'Name'])
            .limit(1)
            .build())
    
    result = sf.query(query)
    assert 'records' in result
```

## Common Pitfalls to Avoid

1. **Don't Mix Patterns**: Either use the builder or string concatenation, not both
2. **Remember AND/OR Logic**: The first condition doesn't need AND/OR
3. **Check for Empty Conditions**: Ensure at least one condition before building
4. **Handle Relationships**: Use dot notation for relationship fields
5. **Test Edge Cases**: Empty strings, None values, special characters

## Resources

- [SOQL Query Builder Documentation](./SOQL_QUERY_BUILDER.md)
- [Query Builder Examples](./soql_query_builder_examples.md)
- [Test Suite](../tests/test_soql_query_builder.py)
- [Salesforce SOQL Reference](https://developer.salesforce.com/docs/atlas.en-us.soql_sosl.meta/soql_sosl/)