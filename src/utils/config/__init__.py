"""Configuration management module for the Multi-Agent Orchestrator system."""

# New unified configuration system
from .unified_config import config, ConfigError


# Import all constants
from .constants import *

__all__ = [
    # Unified configuration system
    'config',
    'ConfigError',
]