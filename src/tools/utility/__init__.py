"""Utility tools for the orchestrator."""

from .web_search import WebSearchTool

# Export the tool class, not instances
# The orchestrator will instantiate as needed

__all__ = [
    'WebSearchTool'
]