"""SOQL query builder extending the base query builder pattern.

Provides Salesforce-specific query building with SOQL syntax support.
"""

from typing import List, Any, Union
from dataclasses import dataclass
from enum import Enum

from ..query import BaseQueryBuilder, BaseOperator, BaseCondition


class SOQLOperator(Enum):
    """SOQL-specific operators extending base operators."""
    # Inherit base operators
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
    
    # SOQL-specific
    INCLUDES = "INCLUDES"
    EXCLUDES = "EXCLUDES"


@dataclass
class SOQLCondition(BaseCondition):
    """SOQL-specific condition implementation."""
    field: str
    operator: Union[BaseOperator, SOQLOperator]  # type: ignore[assignment]
    value: Any
    
    def to_query_string(self) -> str:
        """Convert condition to SOQL string."""
        # Handle raw conditions (special case for where_raw)
        if self.field == '__raw__':
            return str(self.value)
            
        from .soql_helpers import format_soql_value
        
        if isinstance(self.operator, BaseOperator):
            op_str = self.operator.value
        else:
            op_str = self.operator.value
            
        if self.operator in (BaseOperator.IN, BaseOperator.NOT_IN, SOQLOperator.IN, SOQLOperator.NOT_IN):
            if isinstance(self.value, (list, tuple)):
                values = [format_soql_value(v) for v in self.value]
                return f"{self.field} {op_str} ({', '.join(values)})"
            else:
                return f"{self.field} {op_str} ({format_soql_value(self.value)})"
        else:
            return f"{self.field} {op_str} {format_soql_value(self.value)}"


class SOQLQueryBuilder(BaseQueryBuilder['SOQLQueryBuilder']):
    """SOQL query builder with fluent interface and injection protection."""
    
    def __init__(self):
        super().__init__()
        self._for_update = False
        self._for_view = False
        self._for_reference = False
        self._with_data_category: List[tuple[str, str, str]] = []
        self._subqueries: List[tuple[str, 'SOQLQueryBuilder']] = []
    
    def escape_value(self, value: Any) -> str:
        """Escape special characters to prevent SOQL injection."""
        if value is None:
            return ''
        return str(value).replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
    
    def create_condition(self, field: str, operator: Union[BaseOperator, SOQLOperator], value: Any) -> SOQLCondition:
        """Create a SOQL-specific condition."""
        # Map base operators to SOQL operators if needed
        if isinstance(operator, BaseOperator):
            if operator == BaseOperator.EQUALS:
                operator = SOQLOperator.EQUALS
            elif operator == BaseOperator.NOT_EQUALS:
                operator = SOQLOperator.NOT_EQUALS
            # Add more mappings as needed
        
        return SOQLCondition(field, operator, value)
    
    def format_field_name(self, field: str) -> str:
        """Format field names according to SOQL conventions."""
        # Handle relationship queries (e.g., Account.Name)
        if '.' in field:
            parts = field.split('.')
            return '.'.join(self.format_field_name(part) for part in parts)
        
        # Standard field names don't need special formatting in SOQL
        return field
    
    def where_like(self, field: str, pattern: str) -> 'SOQLQueryBuilder':
        """Add WHERE LIKE condition."""
        return self.where(field, SOQLOperator.LIKE, pattern)  # type: ignore[arg-type]
    
    def where_not_like(self, field: str, pattern: str) -> 'SOQLQueryBuilder':
        """Add WHERE NOT LIKE condition."""
        return self.where(field, SOQLOperator.NOT_LIKE, pattern)  # type: ignore[arg-type]
    
    def for_update(self) -> 'SOQLQueryBuilder':
        """Add FOR UPDATE clause."""
        self._for_update = True
        return self
    
    def for_view(self) -> 'SOQLQueryBuilder':
        """Add FOR VIEW clause."""
        self._for_view = True
        return self
    
    def for_reference(self) -> 'SOQLQueryBuilder':
        """Add FOR REFERENCE clause."""
        self._for_reference = True
        return self
    
    def with_data_category(self, group: str, selector: str, categories: str) -> 'SOQLQueryBuilder':
        """Add WITH DATA CATEGORY clause."""
        self._with_data_category.append((group, selector, categories))
        return self
    
    def add_subquery(self, alias: str, subquery: 'SOQLQueryBuilder') -> 'SOQLQueryBuilder':
        """Add a subquery to the SELECT clause."""
        self._subqueries.append((alias, subquery))
        return self
    
    def where_raw(self, raw_condition: str) -> 'SOQLQueryBuilder':
        """Add raw WHERE condition string (use with caution)."""
        # Create a special condition that will be rendered as-is
        condition = SOQLCondition('__raw__', SOQLOperator.EQUALS, raw_condition)
        self._conditions.append(condition)
        return self
    
    def select_count(self, field: str = 'Id', alias: str = 'recordCount') -> 'SOQLQueryBuilder':
        """Add COUNT aggregate function."""
        self._select_fields.append(f"COUNT({field}) {alias}")
        return self
    
    def select_sum(self, field: str, alias: str) -> 'SOQLQueryBuilder':
        """Add SUM aggregate function."""
        self._select_fields.append(f"SUM({field}) {alias}")
        return self
    
    def select_avg(self, field: str, alias: str) -> 'SOQLQueryBuilder':
        """Add AVG aggregate function."""
        self._select_fields.append(f"AVG({field}) {alias}")
        return self
    
    def select_max(self, field: str, alias: str) -> 'SOQLQueryBuilder':
        """Add MAX aggregate function."""
        self._select_fields.append(f"MAX({field}) {alias}")
        return self
    
    def select_min(self, field: str, alias: str) -> 'SOQLQueryBuilder':
        """Add MIN aggregate function."""
        self._select_fields.append(f"MIN({field}) {alias}")
        return self
    
    def build(self) -> str:
        """Build the complete SOQL query string."""
        self.validate()
        
        # Build SELECT clause
        if self._select_fields or self._subqueries:
            fields = list(self._select_fields)
            
            # Add subqueries
            for alias, subquery in self._subqueries:
                fields.append(f"({subquery.build()}) {alias}")
            
            select_clause = f"SELECT {', '.join(fields)}"
        else:
            select_clause = "SELECT Id"  # Default to Id if no fields specified
        
        # Build FROM clause
        from_clause = f"FROM {self._from_object}"
        
        # Build WHERE clause
        where_parts = []
        for condition in self._conditions:
            if hasattr(condition, 'to_query_string'):
                from ..query.base_builder import ConditionGroup
                if isinstance(condition, ConditionGroup):
                    where_parts.append(f"({condition.to_query_string(lambda c: c.to_query_string())})")
                else:
                    where_parts.append(condition.to_query_string())
        
        where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
        
        # Build WITH DATA CATEGORY clause
        with_clause = ""
        if self._with_data_category:
            category_parts = []
            for group, selector, categories in self._with_data_category:
                category_parts.append(f"{group} {selector} ({categories})")
            with_clause = f"WITH DATA CATEGORY {' AND '.join(category_parts)}"
        
        # Build GROUP BY clause
        group_by_clause = f"GROUP BY {', '.join(self._group_by)}" if self._group_by else ""
        
        # Build HAVING clause
        having_parts = []
        for condition in self._having_conditions:
            if hasattr(condition, 'to_query_string'):
                from ..query.base_builder import ConditionGroup
                if isinstance(condition, ConditionGroup):
                    having_parts.append(f"({condition.to_query_string(lambda c: c.to_query_string())})")
                else:
                    having_parts.append(condition.to_query_string())
        having_clause = f"HAVING {' AND '.join(having_parts)}" if having_parts else ""
        
        # Build ORDER BY clause
        order_by_clause = ""
        if self._order_by:
            order_parts = [f"{field} {direction}" for field, direction in self._order_by]
            order_by_clause = f"ORDER BY {', '.join(order_parts)}"
        
        # Build LIMIT clause
        limit_clause = f"LIMIT {self._limit}" if self._limit else ""
        
        # Build OFFSET clause
        offset_clause = f"OFFSET {self._offset}" if self._offset else ""
        
        # Build FOR clause
        for_clauses = []
        if self._for_update:
            for_clauses.append("FOR UPDATE")
        if self._for_view:
            for_clauses.append("FOR VIEW")
        if self._for_reference:
            for_clauses.append("FOR REFERENCE")
        for_clause = " ".join(for_clauses)
        
        # Combine all clauses
        query_parts = [
            select_clause,
            from_clause,
            where_clause,
            with_clause,
            group_by_clause,
            having_clause,
            order_by_clause,
            limit_clause,
            offset_clause,
            for_clause
        ]
        
        # Filter out empty parts and join
        query = " ".join(part for part in query_parts if part)
        return query.strip()
    
    @classmethod
    def from_natural_language(cls, query: str, object_type: str) -> 'SOQLQueryBuilder':
        """Create a query builder from natural language.
        
        This is a simplified implementation - in production, you'd use
        more sophisticated NLP or LLM-based parsing.
        """
        builder = cls()
        builder.from_object(object_type)
        
        # Basic pattern matching for common queries
        query_lower = query.lower()
        
        # Extract fields mentioned
        if "all" in query_lower or "everything" in query_lower:
            # In practice, you'd list actual fields, not use *
            builder.select("Id", "Name")  # Add more standard fields
        
        # Extract conditions
        if "where" in query_lower:
            # Simple extraction - production would use better parsing
            if "name" in query_lower and ("is" in query_lower or "equals" in query_lower):
                # Extract the value after "is" or "equals"
                parts = query_lower.split()
                for i, part in enumerate(parts):
                    if part in ("is", "equals") and i + 1 < len(parts):
                        builder.where("Name", BaseOperator.EQUALS, parts[i + 1])
        
        # Extract limit
        if "limit" in query_lower or "top" in query_lower:
            # Extract number
            import re
            numbers = re.findall(r'\d+', query)
            if numbers:
                builder.limit(int(numbers[0]))
        
        return builder