"""Platform-specific utilities for Salesforce, ServiceNow, and other platforms."""

from . import salesforce
from . import servicenow
from . import query

__all__ = ['salesforce', 'servicenow', 'query']