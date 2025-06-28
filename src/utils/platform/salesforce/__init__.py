"""Salesforce platform utilities."""

from .soql_builder import SOQLQueryBuilder, SOQLOperator, SOQLCondition
from .soql_helpers import (
    escape_soql,
    format_soql_value,
    validate_field_name,
    validate_object_name,
    parse_field_list,
    build_field_list
)

__all__ = [
    'SOQLQueryBuilder',
    'SOQLOperator',
    'SOQLCondition',
    'escape_soql',
    'format_soql_value',
    'validate_field_name',
    'validate_object_name',
    'parse_field_list',
    'build_field_list'
]