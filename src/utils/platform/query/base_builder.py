"""Base query builder with common patterns for platform-specific implementations.

This module provides a foundation for building type-safe, injection-resistant query builders
for various platforms (Salesforce SOQL, ServiceNow GlideRecord, etc.).

Design Principles:
- Security-first: All inputs automatically escaped
- Fluent interface: Chainable method calls for query construction
- Type safety: Leverages Python's type system
- Extensibility: Easy to extend for platform-specific features
"""

from abc import ABC, abstractmethod
from typing import List, Any, Optional, Union, TypeVar, Generic
from dataclasses import dataclass
from enum import Enum

T = TypeVar('T', bound='BaseQueryBuilder')


class BaseOperator(Enum):
    """Common operators across query languages."""
    EQUALS = "="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_OR_EQUAL = ">="
    LESS_OR_EQUAL = "<="
    IN = "IN"
    NOT_IN = "NOT IN"


class LogicalOperator(Enum):
    """Logical operators for combining conditions."""
    AND = "AND"
    OR = "OR"


@dataclass
class BaseCondition:
    """Base class for query conditions."""
    field: str
    operator: BaseOperator
    value: Any
    
    @abstractmethod
    def to_query_string(self) -> str:
        """Convert condition to platform-specific query string."""
        pass


@dataclass 
class ConditionGroup:
    """Groups multiple conditions with a logical operator."""
    conditions: List[Union[BaseCondition, 'ConditionGroup']]
    operator: LogicalOperator = LogicalOperator.AND
    
    def to_query_string(self, condition_formatter) -> str:
        """Convert group to query string using provided formatter."""
        parts = []
        for condition in self.conditions:
            if isinstance(condition, ConditionGroup):
                parts.append(f"({condition.to_query_string(condition_formatter)})")
            else:
                parts.append(condition_formatter(condition))
        return f" {self.operator.value} ".join(parts)


class BaseQueryBuilder(ABC, Generic[T]):
    """Abstract base class for platform-specific query builders."""
    
    def __init__(self):
        self._select_fields: List[str] = []
        self._from_object: Optional[str] = None
        self._conditions: List[Union[BaseCondition, ConditionGroup]] = []
        self._order_by: List[tuple[str, str]] = []
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self._group_by: List[str] = []
        self._having_conditions: List[Union[BaseCondition, ConditionGroup]] = []
    
    @abstractmethod
    def escape_value(self, value: Any) -> str:
        """Escape values to prevent injection attacks."""
        pass
    
    @abstractmethod
    def create_condition(self, field: str, operator: BaseOperator, value: Any) -> BaseCondition:
        """Create a platform-specific condition."""
        pass
    
    @abstractmethod
    def format_field_name(self, field: str) -> str:
        """Format field names according to platform conventions."""
        pass
    
    @abstractmethod
    def build(self) -> str:
        """Build the final query string."""
        pass
    
    def select(self: T, *fields: str) -> T:
        """Add fields to select."""
        self._select_fields.extend(fields)
        return self
    
    def from_object(self: T, object_name: str) -> T:
        """Set the object/table to query from."""
        self._from_object = object_name
        return self
    
    def where(self: T, field: str, operator: Union[BaseOperator, str], value: Any = None) -> T:
        """Add a WHERE condition."""
        if isinstance(operator, str):
            # Handle shorthand: where('field', 'value') -> where('field', '=', 'value')
            value = operator
            operator = BaseOperator.EQUALS
        
        condition = self.create_condition(field, operator, value)
        self._conditions.append(condition)
        return self
    
    def and_where(self: T, field: str, operator: Union[BaseOperator, str], value: Any = None) -> T:
        """Explicitly add an AND condition (same as where)."""
        return self.where(field, operator, value)
    
    def or_where(self: T, conditions_func) -> T:
        """Add OR conditions using a function."""
        # Create a new builder instance for the OR group
        or_builder = self.__class__()
        conditions_func(or_builder)
        
        if or_builder._conditions:
            group = ConditionGroup(or_builder._conditions, LogicalOperator.OR)
            self._conditions.append(group)
        return self
    
    def where_in(self: T, field: str, values: List[Any]) -> T:
        """Add WHERE IN condition."""
        return self.where(field, BaseOperator.IN, values)
    
    def where_not_in(self: T, field: str, values: List[Any]) -> T:
        """Add WHERE NOT IN condition."""
        return self.where(field, BaseOperator.NOT_IN, values)
    
    def order_by(self: T, field: str, direction: str = 'ASC') -> T:
        """Add ORDER BY clause."""
        self._order_by.append((field, direction.upper()))
        return self
    
    def limit(self: T, count: int) -> T:
        """Set result limit."""
        self._limit = count
        return self
    
    def offset(self: T, count: int) -> T:
        """Set result offset."""
        self._offset = count
        return self
    
    def group_by(self: T, *fields: str) -> T:
        """Add GROUP BY fields."""
        self._group_by.extend(fields)
        return self
    
    def having(self: T, field: str, operator: BaseOperator, value: Any) -> T:
        """Add HAVING condition."""
        condition = self.create_condition(field, operator, value)
        self._having_conditions.append(condition)
        return self
    
    def clear(self: T) -> T:
        """Clear all query components."""
        self._select_fields.clear()
        self._from_object = None
        self._conditions.clear()
        self._order_by.clear()
        self._limit = None
        self._offset = None
        self._group_by.clear()
        self._having_conditions.clear()
        return self
    
    def validate(self) -> bool:
        """Validate query has required components."""
        if not self._from_object:
            raise ValueError("FROM object is required")
        return True
    
    def __str__(self) -> str:
        """String representation returns the built query."""
        return self.build()