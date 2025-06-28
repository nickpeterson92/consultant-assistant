"""Utilities package with organized submodules.

This package has been reorganized for better maintainability:
- agents/: Agent-specific utilities (prompts, message processing)
- config/: Configuration management
- core/: Core infrastructure (config, logging, storage)
- platform/: Platform-specific utilities (Salesforce, ServiceNow)
- shared/: Shared utilities (events, tool execution)
- ui/: User interface utilities (terminal, formatting, animations)

For backward compatibility, old imports are still supported but deprecated.
"""

# Core utilities (most commonly used)
from .logging import get_logger
from .config import get_system_config, get_llm_config

# Storage utilities
from .storage import (
    get_async_store_adapter,
    SimpleMemory,
    SimpleAccount,
    SimpleContact,
    SimpleOpportunity,
    SimpleCase,
    SimpleTask,
    SimpleLead
)

# Shared utilities
from .shared import Event, EventTracker, create_tool_node

# Platform utilities
from . import platform

# Agent utilities
from . import agents

# UI utilities  
from . import ui

# Other utilities
from .input_validation import validate_orchestrator_input
from .table_formatter import format_salesforce_response

__all__ = [
    # Core
    'get_logger',
    'get_system_config',
    'get_llm_config',
    
    # Storage
    'get_async_store_adapter',
    'SimpleMemory',
    'SimpleAccount',
    'SimpleContact', 
    'SimpleOpportunity',
    'SimpleCase',
    'SimpleTask',
    'SimpleLead',
    
    # Shared
    'Event',
    'EventTracker',
    'create_tool_node',
    
    # Other
    'validate_orchestrator_input',
    'format_salesforce_response',
    
    # Submodules
    'platform',
    'agents',
    'ui'
]