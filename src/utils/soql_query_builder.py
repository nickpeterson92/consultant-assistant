"""
SOQL Query Builder for Salesforce

A flexible, composable query builder that provides a fluent interface for
constructing SOQL queries with built-in security and optimization features.

Design Benefits:
- Prevents SOQL injection through automatic escaping
- Reduces code duplication across tools
- Enables complex queries with simple syntax
- Supports dynamic field selection and filtering
- Optimizes query performance with field limiting
"""

from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum


class SOQLOperator(Enum):
    """SOQL comparison operators"""
    EQUALS = "="
    NOT_EQUALS = "!="
    LIKE = "LIKE"
    NOT_LIKE = "NOT LIKE"
    IN = "IN"
    NOT_IN = "NOT IN"
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_OR_EQUAL = ">="
    LESS_OR_EQUAL = "<="
    

class LogicalOperator(Enum):
    """Logical operators for combining conditions"""
    AND = "AND"
    OR = "OR"


def escape_soql(value: Optional[str]) -> str:
    """Escape special characters to prevent SOQL injection"""
    if value is None:
        return ''
    return str(value).replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')


@dataclass
class SOQLCondition:
    """Represents a single SOQL condition"""
    field: str
    operator: SOQLOperator
    value: Any
    
    def to_soql(self) -> str:
        """Convert condition to SOQL string"""
        if self.operator == SOQLOperator.IN:
            # Handle IN operator with list of values
            if isinstance(self.value, list):
                escaped_values = [f"'{escape_soql(str(v))}'" for v in self.value]
                return f"{self.field} IN ({', '.join(escaped_values)})"
            else:
                return f"{self.field} IN ('{escape_soql(str(self.value))}')"
        elif self.operator == SOQLOperator.NOT_IN:
            # Handle NOT IN operator with list of values
            if isinstance(self.value, list):
                escaped_values = [f"'{escape_soql(str(v))}'" for v in self.value]
                return f"{self.field} NOT IN ({', '.join(escaped_values)})"
            else:
                return f"{self.field} NOT IN ('{escape_soql(str(self.value))}')"
        elif self.operator == SOQLOperator.LIKE:
            # Handle LIKE with wildcards
            return f"{self.field} LIKE '{escape_soql(str(self.value))}'"
        else:
            # Standard comparison
            if isinstance(self.value, str):
                return f"{self.field} {self.operator.value} '{escape_soql(self.value)}'"
            elif isinstance(self.value, bool):
                # SOQL uses lowercase true/false
                return f"{self.field} {self.operator.value} {str(self.value).lower()}"
            elif self.value is None:
                # SOQL uses = null or != null
                return f"{self.field} {self.operator.value} null"
            else:
                # Numbers and other types
                return f"{self.field} {self.operator.value} {self.value}"


@dataclass
class SOQLQueryBuilder:
    """
    Fluent interface for building SOQL queries
    
    Example usage:
        query = (SOQLQueryBuilder('Account')
                .select(['Id', 'Name', 'Phone'])
                .where('Name', SOQLOperator.LIKE, '%Acme%')
                .or_where('Industry', SOQLOperator.EQUALS, 'Technology')
                .order_by('CreatedDate', descending=True)
                .limit(10)
                .build())
    """
    object_name: str
    fields: List[str] = field(default_factory=list)
    conditions: List[tuple] = field(default_factory=list)  # (condition, logical_operator)
    order_fields: List[tuple] = field(default_factory=list)  # (field, direction)
    limit_value: Optional[int] = None
    offset_value: Optional[int] = None
    
    def select(self, fields: Union[List[str], str]) -> 'SOQLQueryBuilder':
        """Select fields to retrieve"""
        if isinstance(fields, str):
            self.fields.append(fields)
        else:
            self.fields.extend(fields)
        return self
    
    def where(self, field: str, operator: SOQLOperator, value: Any) -> 'SOQLQueryBuilder':
        """Add WHERE condition with AND operator"""
        condition = SOQLCondition(field, operator, value)
        self.conditions.append((condition, LogicalOperator.AND))
        return self
    
    def or_where(self, field: str, operator: SOQLOperator, value: Any) -> 'SOQLQueryBuilder':
        """Add WHERE condition with OR operator"""
        condition = SOQLCondition(field, operator, value)
        self.conditions.append((condition, LogicalOperator.OR))
        return self
    
    def where_id(self, record_id: str) -> 'SOQLQueryBuilder':
        """Convenience method for ID lookup"""
        return self.where('Id', SOQLOperator.EQUALS, record_id)
    
    def where_like(self, field: str, pattern: str) -> 'SOQLQueryBuilder':
        """Convenience method for LIKE queries"""
        return self.where(field, SOQLOperator.LIKE, pattern)
    
    def where_in(self, field: str, values: List[Any]) -> 'SOQLQueryBuilder':
        """Convenience method for IN queries"""
        return self.where(field, SOQLOperator.IN, values)
    
    def where_null(self, field: str) -> 'SOQLQueryBuilder':
        """Convenience method for NULL checks"""
        return self.where(field, SOQLOperator.EQUALS, None)
    
    def where_not_null(self, field: str) -> 'SOQLQueryBuilder':
        """Convenience method for NOT NULL checks"""
        return self.where(field, SOQLOperator.NOT_EQUALS, None)
    
    def order_by(self, field: str, descending: bool = False) -> 'SOQLQueryBuilder':
        """Add ORDER BY clause"""
        direction = "DESC" if descending else "ASC"
        self.order_fields.append((field, direction))
        return self
    
    def limit(self, count: int) -> 'SOQLQueryBuilder':
        """Add LIMIT clause"""
        self.limit_value = count
        return self
    
    def offset(self, count: int) -> 'SOQLQueryBuilder':
        """Add OFFSET clause for pagination"""
        self.offset_value = count
        return self
    
    def build(self) -> str:
        """Build the final SOQL query"""
        # Default fields if none specified
        if not self.fields:
            self.fields = ['Id']
        
        # Remove duplicate fields while preserving order
        seen = set()
        unique_fields = []
        for field in self.fields:
            if field not in seen:
                seen.add(field)
                unique_fields.append(field)
            
        # Build SELECT clause
        query_parts = [f"SELECT {', '.join(unique_fields)} FROM {self.object_name}"]
        
        # Build WHERE clause
        if self.conditions:
            where_parts = []
            for i, (condition, logical_op) in enumerate(self.conditions):
                if i == 0:
                    where_parts.append(condition.to_soql())
                else:
                    where_parts.append(f"{logical_op.value} {condition.to_soql()}")
            query_parts.append(f"WHERE {' '.join(where_parts)}")
        
        # Build ORDER BY clause
        if self.order_fields:
            order_parts = [f"{field} {direction}" for field, direction in self.order_fields]
            query_parts.append(f"ORDER BY {', '.join(order_parts)}")
        
        # Build LIMIT clause
        if self.limit_value:
            query_parts.append(f"LIMIT {self.limit_value}")
            
        # Build OFFSET clause
        if self.offset_value:
            query_parts.append(f"OFFSET {self.offset_value}")
        
        return ' '.join(query_parts)


class RelationshipQueryBuilder(SOQLQueryBuilder):
    """
    Extended query builder for relationship queries
    
    Example:
        query = (RelationshipQueryBuilder('Account')
                .select(['Id', 'Name'])
                .with_related('Contacts', ['Id', 'Name', 'Email'])
                .where('Industry', SOQLOperator.EQUALS, 'Technology')
                .build())
    """
    
    def __init__(self, object_name: str):
        super().__init__(object_name)
        self.relationships: List[tuple] = []  # (relationship_name, fields)
    
    def with_related(self, relationship: str, fields: List[str]) -> 'RelationshipQueryBuilder':
        """Include related records in query"""
        self.relationships.append((relationship, fields))
        return self
    
    def build(self) -> str:
        """Build query with relationship subqueries"""
        # Add relationship subqueries to field list
        for relationship, rel_fields in self.relationships:
            subquery = f"(SELECT {', '.join(rel_fields)} FROM {relationship})"
            self.fields.append(subquery)
        
        return super().build()


class SearchQueryBuilder:
    """
    Builder for flexible search queries across multiple fields
    
    Example:
        results = SearchQueryBuilder(sf, 'Contact')
                 .search_fields(['Name', 'Email', 'Phone'], 'john')
                 .with_account_filter('Acme Corp')
                 .execute()
    """
    
    def __init__(self, sf_connection, object_name: str):
        self.sf = sf_connection
        self.query_builder = SOQLQueryBuilder(object_name)
        self.default_fields = {
            'Lead': ['Id', 'Name', 'Company', 'Email', 'Phone', 'Status'],
            'Contact': ['Id', 'Name', 'Email', 'Phone', 'AccountId'],
            'Account': ['Id', 'Name', 'Phone', 'Industry', 'Website'],
            'Opportunity': ['Id', 'Name', 'StageName', 'Amount', 'CloseDate', 'AccountId'],
            'Case': ['Id', 'Subject', 'Status', 'Priority', 'AccountId', 'ContactId'],
            'Task': ['Id', 'Subject', 'Status', 'Priority', 'WhatId', 'WhoId']
        }
        # Set default fields for object
        if object_name in self.default_fields:
            self.query_builder.select(self.default_fields[object_name])
    
    def search_fields(self, fields: List[str], search_term: str) -> 'SearchQueryBuilder':
        """Search across multiple fields with OR logic"""
        for i, field in enumerate(fields):
            pattern = f'%{search_term}%'
            if i == 0:
                self.query_builder.where_like(field, pattern)
            else:
                self.query_builder.or_where(field, SOQLOperator.LIKE, pattern)
        return self
    
    def with_account_filter(self, account_name: str) -> 'SearchQueryBuilder':
        """Filter by account name (for objects with AccountId)"""
        # First get the account ID
        account_query = (SOQLQueryBuilder('Account')
                        .select(['Id'])
                        .where_like('Name', f'%{account_name}%')
                        .limit(1)
                        .build())
        
        results = self.sf.query(account_query)
        if results['records']:
            account_id = results['records'][0]['Id']
            self.query_builder.where('AccountId', SOQLOperator.EQUALS, account_id)
        return self
    
    def recent_first(self, field: str = 'CreatedDate') -> 'SearchQueryBuilder':
        """Order by most recent first"""
        self.query_builder.order_by(field, descending=True)
        return self
    
    def execute(self) -> List[Dict[str, Any]]:
        """Execute the query and return results"""
        query = self.query_builder.build()
        return self.sf.query(query)['records']


# Predefined query templates for common operations
class QueryTemplates:
    """Common query patterns as reusable templates"""
    
    @staticmethod
    def get_all_related_records(account_id: str) -> Dict[str, str]:
        """Generate queries for all records related to an account"""
        return {
            'contacts': (SOQLQueryBuilder('Contact')
                        .select(['Id', 'Name', 'Email', 'Phone', 'Title'])
                        .where('AccountId', SOQLOperator.EQUALS, account_id)
                        .build()),
            
            'opportunities': (SOQLQueryBuilder('Opportunity')
                            .select(['Id', 'Name', 'StageName', 'Amount', 'CloseDate'])
                            .where('AccountId', SOQLOperator.EQUALS, account_id)
                            .order_by('Amount', descending=True)
                            .build()),
            
            'cases': (SOQLQueryBuilder('Case')
                     .select(['Id', 'Subject', 'Status', 'Priority', 'ContactId'])
                     .where('AccountId', SOQLOperator.EQUALS, account_id)
                     .order_by('CreatedDate', descending=True)
                     .build()),
            
            'tasks': (SOQLQueryBuilder('Task')
                     .select(['Id', 'Subject', 'Status', 'Priority'])
                     .where('WhatId', SOQLOperator.EQUALS, account_id)
                     .build())
        }
    
    @staticmethod
    def search_by_email_domain(object_name: str, domain: str) -> str:
        """Find all contacts/leads with email from specific domain"""
        return (SOQLQueryBuilder(object_name)
                .select(['Id', 'Name', 'Email', 'Phone'])
                .where_like('Email', f'%@{domain}')
                .build())
    
    @staticmethod
    def get_recent_records(object_name: str, days: int = 7) -> str:
        """Get records created in the last N days"""
        from datetime import datetime, timedelta
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        return (SOQLQueryBuilder(object_name)
                .select(['Id', 'Name', 'CreatedDate'])
                .where('CreatedDate', SOQLOperator.GREATER_OR_EQUAL, f'{cutoff_date}T00:00:00Z')
                .order_by('CreatedDate', descending=True)
                .limit(100)
                .build())
    
    @staticmethod
    def get_opportunities_by_stage(stages: List[str], min_amount: float = None) -> str:
        """Get opportunities in specific stages with optional amount filter"""
        builder = (SOQLQueryBuilder('Opportunity')
                  .select(['Id', 'Name', 'AccountId', 'StageName', 'Amount', 'CloseDate'])
                  .where_in('StageName', stages))
        
        if min_amount:
            builder.where('Amount', SOQLOperator.GREATER_OR_EQUAL, min_amount)
        
        return builder.order_by('CloseDate').build()