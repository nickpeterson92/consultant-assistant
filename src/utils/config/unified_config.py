"""Unified configuration system with clear precedence and secrets handling."""

import os
import json
from typing import Dict, Any, Optional, Union
from pathlib import Path


# Import logger after class definition to avoid circular imports
logger = None

def _get_logger():
    """Lazy logger initialization to avoid circular imports."""
    global logger
    if logger is None:
        from ..logging import get_smart_logger
        logger = get_smart_logger("system")
    return logger


class ConfigError(Exception):
    """Configuration-related errors."""
    pass


class UnifiedConfig:
    """Unified configuration with clear precedence:
    
    Precedence (highest to lowest):
    1. Environment variables
    2. system_config.json
    3. Code defaults
    
    Secrets are handled separately and only come from environment variables.
    """
    
    def __init__(self, config_file: str = "system_config.json"):
        self._config_file = config_file
        self._config = {}
        self._secrets = {}
        self._defaults = self._get_code_defaults()
        
        # Load configuration
        self._load_json_config()
        self._load_secrets()
        self._apply_env_overrides()
        
        _get_logger().info("unified_config_loaded", 
                          config_file=config_file,
                          secrets_loaded=len(self._secrets),
                          config_sections=list(self._config.keys()))
    
    def _get_code_defaults(self) -> Dict[str, Any]:
        """Code defaults as fallback."""
        return {
            "database": {
                "path": "memory_store.db",
                "timeout": 30,
                "pool_size": 5,
                "auto_commit": True,
                "thread_pool_size": 4,
                "thread_prefix": "sqlite_"
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "external_logs_dir": "logs",
                "max_file_size": 10485760,
                "backup_count": 5,
                "buffer_size": 1000
            },
            "llm": {
                "model": "gpt-4o-mini",
                "temperature": 0.3,
                "top_p": 0.9,
                "max_tokens": 4000,
                "timeout": 120,
                "retry_attempts": 3,
                "retry_delay": 1.0,
                "recursion_limit": 15
            },
            "a2a": {
                "timeout": 120,
                "connect_timeout": 30,
                "sock_connect_timeout": 30,
                "sock_read_timeout": 120,
                "health_check_timeout": 10,
                "max_concurrent_calls": 10,
                "retry_attempts": 3,
                "retry_delay": 1.0,
                "circuit_breaker_threshold": 5,
                "circuit_breaker_timeout": 30,
                "connection_pool_size": 20
            },
            "conversation": {
                "summary_threshold": 5,
                "max_conversation_length": 50,
                "default_user_id": "user-1",
                "memory_namespace_prefix": "memory",
                "typing_effect_enabled": True,
                "animated_banner_enabled": True
            },
            "security": {
                "input_validation_enabled": True,
                "max_input_length": 50000
            }
        }
    
    def _load_json_config(self):
        """Load configuration from JSON file."""
        try:
            config_path = Path(self._config_file)
            if config_path.exists():
                with open(config_path, 'r') as f:
                    file_config = json.load(f)
                
                # Merge with defaults (file config takes precedence)
                self._config = self._deep_merge(self._defaults, file_config)
                _get_logger().info("config_file_loaded", 
                                  path=str(config_path),
                                  sections=list(file_config.keys()))
            else:
                _get_logger().warning("config_file_not_found", 
                                     path=str(config_path),
                                     using_defaults=True)
                self._config = self._defaults.copy()
        except Exception as e:
            _get_logger().error("config_file_load_error", 
                               error=str(e),
                               using_defaults=True)
            self._config = self._defaults.copy()
    
    def _load_secrets(self):
        """Load sensitive values from environment only."""
        secret_mappings = {
            # Azure OpenAI
            'azure_openai_key': 'AZURE_OPENAI_API_KEY',
            'azure_openai_endpoint': 'AZURE_OPENAI_ENDPOINT',
            'azure_openai_deployment': 'AZURE_OPENAI_CHAT_DEPLOYMENT_NAME',
            'azure_openai_api_version': 'AZURE_OPENAI_API_VERSION',
            
            # Salesforce
            'salesforce_user': 'SFDC_USER',
            'salesforce_pass': 'SFDC_PASS', 
            'salesforce_token': 'SFDC_TOKEN',
            
            # Jira
            'jira_url': 'JIRA_URL',
            'jira_user': 'JIRA_USER',
            'jira_token': 'JIRA_TOKEN',
            
            # ServiceNow
            'servicenow_url': 'SERVICENOW_URL',
            'servicenow_user': 'SERVICENOW_USER',
            'servicenow_pass': 'SERVICENOW_PASS',
            
            # Tavily (Web Search)
            'tavily_api_key': 'TAVILY_API_KEY',
        }
        
        for key, env_var in secret_mappings.items():
            value = os.getenv(env_var)
            if value:
                self._secrets[key] = value
        
        _get_logger().info("secrets_loaded", 
                          secret_count=len(self._secrets),
                          secret_keys=list(self._secrets.keys()))
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides for non-sensitive config."""
        env_mappings = {
            # Database
            'DB_PATH': 'database.path',
            'DB_TIMEOUT': 'database.timeout',
            
            # LLM
            'LLM_MODEL': 'llm.model',
            'LLM_TEMPERATURE': 'llm.temperature',
            'LLM_MAX_TOKENS': 'llm.max_tokens',
            'LLM_TIMEOUT': 'llm.timeout',
            'LLM_RECURSION_LIMIT': 'llm.recursion_limit',
            
            # Logging
            'LOG_LEVEL': 'logging.level',
            'LOG_DIR': 'logging.external_logs_dir',
            
            # Debug
            'DEBUG_MODE': 'debug_mode',
        }
        
        for env_var, config_path in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Convert to appropriate type
                converted_value = self._convert_env_value(value)
                self._set_nested_value(self._config, config_path, converted_value)
                _get_logger().debug("env_override_applied", 
                                   env_var=env_var,
                                   config_path=config_path,
                                   value=converted_value)
    
    def _convert_env_value(self, value: str) -> Union[str, int, float, bool]:
        """Convert environment variable string to appropriate type."""
        # Boolean values
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # Integer values
        try:
            if '.' not in value:
                return int(value)
        except ValueError:
            pass
        
        # Float values
        try:
            return float(value)
        except ValueError:
            pass
        
        # String values
        return value
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _set_nested_value(self, config: Dict, path: str, value: Any):
        """Set a nested configuration value using dot notation."""
        keys = path.split('.')
        current = config
        
        # Navigate to the parent of the target key
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Set the final value
        current[keys[-1]] = value
    
    def get(self, path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation.
        
        Args:
            path: Dot-separated path like 'database.timeout'
            default: Default value if path not found
            
        Returns:
            Configuration value or default
        """
        keys = path.split('.')
        current = self._config
        
        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return default
    
    def get_secret(self, key: str, required: bool = True) -> Optional[str]:
        """Get secret value from environment.
        
        Args:
            key: Secret key
            required: Whether to raise error if missing
            
        Returns:
            Secret value or None
            
        Raises:
            ConfigError: If required secret is missing
        """
        value = self._secrets.get(key)
        
        if value is None and required:
            raise ConfigError(f"Required secret '{key}' not found in environment variables")
        
        return value
    
    def has_secret(self, key: str) -> bool:
        """Check if secret exists without exposing value."""
        return key in self._secrets
    
    def validate_required_secrets(self, required_keys: list):
        """Validate that all required secrets are present."""
        missing = [key for key in required_keys if not self.has_secret(key)]
        
        if missing:
            raise ConfigError(f"Missing required secrets: {', '.join(missing)}")
    
    # Property shortcuts for common values
    @property
    def db_path(self) -> str:
        return self.get('database.path', 'memory_store.db')
    
    @property
    def db_timeout(self) -> int:
        return self.get('database.timeout', 30)
    
    @property
    def llm_model(self) -> str:
        return self.get('llm.model', 'gpt-4o-mini')
    
    @property
    def llm_temperature(self) -> float:
        return self.get('llm.temperature', 0.3)
    
    @property
    def llm_max_tokens(self) -> int:
        return self.get('llm.max_tokens', 4000)
    
    @property
    def llm_timeout(self) -> int:
        return self.get('llm.timeout', 120)
    
    @property
    def llm_recursion_limit(self) -> int:
        return self.get('llm.recursion_limit', 15)
    
    @property
    def a2a_timeout(self) -> int:
        return self.get('a2a.timeout', 120)
    
    @property
    def log_level(self) -> str:
        return self.get('logging.level', 'INFO')
    
    @property
    def log_dir(self) -> str:
        return self.get('logging.external_logs_dir', 'logs')
    
    @property
    def conversation_summary_threshold(self) -> int:
        return self.get('conversation.summary_threshold', 5)
    
    @property
    def default_user_id(self) -> str:
        return self.get('conversation.default_user_id', 'user-1')
    
    @property
    def memory_namespace_prefix(self) -> str:
        return self.get('conversation.memory_namespace_prefix', 'memory')
    
    @property
    def debug_mode(self) -> bool:
        return self.get('debug_mode', False)


# Singleton instance
config = UnifiedConfig()