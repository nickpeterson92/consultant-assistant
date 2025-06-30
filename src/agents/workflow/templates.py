"""Backward compatibility wrapper for workflow templates

This module maintains backward compatibility by re-exporting
the WorkflowTemplates class from the templates package.
"""

from .templates import WorkflowTemplates

__all__ = ['WorkflowTemplates']