"""SOQL query builder with fluent interface and injection protection."""

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
    """Escape special characters to prevent SOQL injection.
    
    Args:
        value: String to escape
        
    Returns:
        Escaped string safe for SOQL
    """
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
        # Handle raw conditions
        if self.field == '__raw__':
            return str(self.value)
        
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
    group_by_fields: List[str] = field(default_factory=list)
    having_conditions: List[tuple] = field(default_factory=list)  # (condition, logical_operator)
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
    
    def where_raw(self, raw_condition: str) -> 'SOQLQueryBuilder':
        """Add raw WHERE condition string (use with caution)"""
        # Create a special condition that will be rendered as-is
        condition = SOQLCondition('__raw__', SOQLOperator.EQUALS, raw_condition)
        self.conditions.append((condition, LogicalOperator.AND))
        return self
    
    def select_count(self, field: str = 'Id', alias: str = 'recordCount') -> 'SOQLQueryBuilder':
        """Add COUNT aggregate function"""
        self.fields.append(f"COUNT({field}) {alias}")
        return self
    
    def select_sum(self, field: str, alias: str) -> 'SOQLQueryBuilder':
        """Add SUM aggregate function"""
        self.fields.append(f"SUM({field}) {alias}")
        return self
    
    def select_avg(self, field: str, alias: str) -> 'SOQLQueryBuilder':
        """Add AVG aggregate function"""
        self.fields.append(f"AVG({field}) {alias}")
        return self
    
    def select_max(self, field: str, alias: str) -> 'SOQLQueryBuilder':
        """Add MAX aggregate function"""
        self.fields.append(f"MAX({field}) {alias}")
        return self
    
    def select_min(self, field: str, alias: str) -> 'SOQLQueryBuilder':
        """Add MIN aggregate function"""
        self.fields.append(f"MIN({field}) {alias}")
        return self
    
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
    
    def group_by(self, field: Union[str, List[str]]) -> 'SOQLQueryBuilder':
        """Add GROUP BY clause"""
        if isinstance(field, str):
            self.group_by_fields.append(field)
        else:
            self.group_by_fields.extend(field)
        return self
    
    def having(self, aggregate_expr: str, operator: SOQLOperator, value: Any) -> 'SOQLQueryBuilder':
        """Add HAVING condition"""
        condition = SOQLCondition(aggregate_expr, operator, value)
        self.having_conditions.append((condition, LogicalOperator.AND))
        return self
    
    def or_having(self, aggregate_expr: str, operator: SOQLOperator, value: Any) -> 'SOQLQueryBuilder':
        """Add HAVING condition with OR"""
        condition = SOQLCondition(aggregate_expr, operator, value)
        self.having_conditions.append((condition, LogicalOperator.OR))
        return self
    
    def with_subquery(self, relationship: str, child_object: str, 
                     builder_fn: callable) -> 'SOQLQueryBuilder':
        """Add a subquery to SELECT fields"""
        # Create a SubqueryBuilder instance (defined later in this file)
        subquery_builder = SubqueryBuilder(relationship, child_object)
        builder_fn(subquery_builder)
        self.fields.append(subquery_builder.build())
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
        
        # Build GROUP BY clause
        if self.group_by_fields:
            query_parts.append(f"GROUP BY {', '.join(self.group_by_fields)}")
        
        # Build HAVING clause
        if self.having_conditions:
            having_parts = []
            for i, (condition, logical_op) in enumerate(self.having_conditions):
                if i == 0:
                    having_parts.append(condition.to_soql())
                else:
                    having_parts.append(f"{logical_op.value} {condition.to_soql()}")
            query_parts.append(f"HAVING {' '.join(having_parts)}")
        
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
    
    @staticmethod
    def get_top_opportunities_by_owner() -> str:
        """Get top opportunities grouped by owner using aggregate functions"""
        return (SOQLQueryBuilder('Opportunity')
            .select(['OwnerId', 'Owner.Name'])
            .select_count('Id', 'OpportunityCount')
            .select_sum('Amount', 'TotalPipeline')
            .where('IsClosed', SOQLOperator.EQUALS, False)
            .group_by(['OwnerId', 'Owner.Name'])
            .having('SUM(Amount)', SOQLOperator.GREATER_THAN, 100000)
            .order_by('TotalPipeline', descending=True)
            .limit(10)
            .build())
    
    @staticmethod
    def search_across_objects(search_term: str) -> str:
        """Search across multiple objects using SOSL"""
        return (SOSLQueryBuilder()
            .find(search_term)
            .returning('Account', ['Id', 'Name', 'Industry'])
            .returning('Contact', ['Id', 'Name', 'Email', 'Account.Name'])
            .returning('Opportunity', ['Id', 'Name', 'Amount', 'StageName'])
            .returning('Lead', ['Id', 'Name', 'Company', 'Email'])
            .limit(20)
            .build())
    
    @staticmethod
    def get_accounts_with_opportunities() -> str:
        """Get accounts with their opportunity summary using subquery"""
        return (SOQLQueryBuilder('Account')
            .select(['Id', 'Name', 'Industry', 'AnnualRevenue'])
            .with_subquery('Opportunities', 'Opportunity', lambda sq: sq
                .select(['Id', 'Name', 'Amount', 'StageName'])
                .where('IsClosed', SOQLOperator.EQUALS, False)
                .order_by('Amount', descending=True)
                .limit(5))
            .where_not_null('Industry')
            .order_by('AnnualRevenue', descending=True)
            .limit(20)
            .build())


class SubqueryBuilder(SOQLQueryBuilder):
    """Builder for SOQL subqueries"""
    
    def __init__(self, parent_relationship: str, child_object: str):
        super().__init__(child_object)
        self.parent_relationship = parent_relationship
    
    def build(self) -> str:
        """Build subquery with parentheses"""
        query = super().build()
        # Replace object name with relationship name
        query = query.replace(f"FROM {self.object_name}", f"FROM {self.parent_relationship}")
        return f"({query})"


class SOSLQueryBuilder:
    """Builder for Salesforce Object Search Language queries"""
    
    def __init__(self):
        self.search_term = ""
        self.search_scope = "ALL FIELDS"
        self.returning_objects = {}
        self.limit_value = None
    
    def find(self, term: str) -> 'SOSLQueryBuilder':
        """Set search term"""
        self.search_term = escape_soql(term)
        return self
    
    def in_scope(self, scope: str) -> 'SOSLQueryBuilder':
        """Set search scope (ALL FIELDS, NAME FIELDS, etc.)"""
        self.search_scope = scope
        return self
    
    def returning(self, object_name: str, fields: List[str], 
                 where_clause: str = None, order_by: str = None, 
                 limit: int = None) -> 'SOSLQueryBuilder':
        """Add RETURNING clause for an object"""
        returning_def = f"{object_name}({', '.join(fields)}"
        
        if where_clause:
            returning_def += f" WHERE {where_clause}"
        
        if order_by:
            returning_def += f" ORDER BY {order_by}"
            
        if limit:
            returning_def += f" LIMIT {limit}"
            
        returning_def += ")"
        self.returning_objects[object_name] = returning_def
        return self
    
    def limit(self, count: int) -> 'SOSLQueryBuilder':
        """Set overall result limit"""
        self.limit_value = count
        return self
    
    def build(self) -> str:
        """Build SOSL query"""
        query = f"FIND '{{{self.search_term}}}' IN {self.search_scope}"
        
        if self.returning_objects:
            returning_parts = list(self.returning_objects.values())
            query += f" RETURNING {', '.join(returning_parts)}"
        
        if self.limit_value:
            query += f" LIMIT {self.limit_value}"
        
        return query


class AggregateQueryBuilder:
    """Specialized builder for aggregate queries with common patterns"""
    
    @staticmethod
    def opportunity_pipeline_by_stage(sf_object: str = 'Opportunity') -> str:
        """Get opportunity pipeline grouped by stage"""
        return (SOQLQueryBuilder(sf_object)
            .select(['StageName'])
            .select_count('Id', 'OpportunityCount')
            .select_sum('Amount', 'TotalAmount')
            .select_avg('Amount', 'AvgAmount')
            .group_by('StageName')
            .having('SUM(Amount)', SOQLOperator.GREATER_THAN, 0)
            .order_by('TotalAmount', descending=True)
            .build())
    
    @staticmethod
    def account_summary_by_industry() -> str:
        """Get account metrics grouped by industry"""
        return (SOQLQueryBuilder('Account')
            .select(['Industry'])
            .select_count('Id', 'AccountCount')
            .select_sum('AnnualRevenue', 'TotalRevenue')
            .where_not_null('Industry')
            .group_by('Industry')
            .having('COUNT(Id)', SOQLOperator.GREATER_THAN, 5)
            .build())
    
    @staticmethod
    def top_sales_reps(min_revenue: float = 100000) -> str:
        """Get top performing sales reps by closed revenue"""
        return (SOQLQueryBuilder('Opportunity')
            .select(['OwnerId', 'Owner.Name'])
            .select_count('Id', 'DealsWon')
            .select_sum('Amount', 'TotalRevenue')
            .where('IsClosed', SOQLOperator.EQUALS, True)
            .where('IsWon', SOQLOperator.EQUALS, True)
            .group_by(['OwnerId', 'Owner.Name'])
            .having('SUM(Amount)', SOQLOperator.GREATER_THAN, min_revenue)
            .order_by('TotalRevenue', descending=True)
            .limit(10)
            .build())
    
    @staticmethod
    def case_volume_by_priority() -> str:
        """Get case distribution by priority and status"""
        return (SOQLQueryBuilder('Case')
            .select(['Priority', 'Status'])
            .select_count('Id', 'CaseCount')
            .select_avg('(CASE WHEN IsClosed = true THEN 1 ELSE 0 END)', 'CloseRate')
            .group_by(['Priority', 'Status'])
            .order_by(['Priority', 'Status'])
            .build())