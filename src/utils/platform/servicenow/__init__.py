"""ServiceNow platform utilities."""

from .glide_builder import GlideQueryBuilder, GlideOperator
from .glide_helpers import (
    escape_glide_value,
    format_glide_datetime,
    format_glide_date,
    validate_table_name,
    get_common_fields
)

__all__ = [
    'GlideQueryBuilder',
    'GlideOperator',
    'escape_glide_value',
    'format_glide_datetime',
    'format_glide_date',
    'validate_table_name',
    'get_common_fields'
]