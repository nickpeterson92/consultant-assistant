"""
Centralized Configuration Management for Multi-Agent System
Provides a single source of truth for all system configuration
"""

import os
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict, field
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    path: str = "memory_store.db"
    timeout: int = 30
    pool_size: int = 5
    auto_commit: bool = True

@dataclass 
class LoggingConfig:
    """Logging configuration settings"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    external_logs_dir: str = "logs"
    max_file_size: int = 10485760  # 10MB
    backup_count: int = 5
    buffer_size: int = 1000

@dataclass
class ModelPricing:
    """Pricing information for a model"""
    input_per_1k: float
    output_per_1k: float
    
    @property
    def average_per_1k(self) -> float:
        """Calculate average cost per 1K tokens"""
        return (self.input_per_1k + self.output_per_1k) / 2

@dataclass
class LLMConfig:
    """LLM configuration settings"""
    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    max_tokens: int = 4000
    timeout: int = 120
    retry_attempts: int = 3
    retry_delay: float = 1.0
    cache_enabled: bool = True
    cache_ttl: int = 3600  # 1 hour
    azure_deployment: str = "gpt-4o-mini"
    api_version: str = "2024-06-01"
    
    # Model pricing map  
    pricing: Dict[str, ModelPricing] = field(default_factory=dict)
    
    def __post_init__(self):
        # Only set default pricing if no pricing data was provided
        # This prevents overwriting pricing loaded from config file
        if not self.pricing:
            self.pricing = {
                "gpt-4": ModelPricing(input_per_1k=0.03, output_per_1k=0.06),
                "gpt-4o": ModelPricing(input_per_1k=0.005, output_per_1k=0.015),
                "gpt-4o-mini": ModelPricing(input_per_1k=0.00015, output_per_1k=0.00060),
                "gpt-3.5-turbo": ModelPricing(input_per_1k=0.0005, output_per_1k=0.0015),
            }
    
    def get_pricing(self, model: str = None) -> ModelPricing:
        """Get pricing for a specific model or the configured model"""
        model_name = model or self.model
        model_lower = model_name.lower()
        
        # First try exact match
        if model_lower in self.pricing:
            return self.pricing[model_lower]
        
        # Then try case-insensitive exact match
        for key in self.pricing:
            if key.lower() == model_lower:
                return self.pricing[key]
        
        # Finally try substring matching (longest match first to prefer specific models)
        sorted_keys = sorted(self.pricing.keys(), key=len, reverse=True)
        for key in sorted_keys:
            if key.lower() in model_lower:
                return self.pricing[key]
        
        # Default fallback
        return ModelPricing(input_per_1k=0.001, output_per_1k=0.001)

@dataclass
class A2AConfig:
    """Agent-to-Agent protocol configuration"""
    timeout: int = 30
    max_concurrent_calls: int = 10
    retry_attempts: int = 3
    retry_delay: float = 1.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 30
    connection_pool_size: int = 20

@dataclass
class SecurityConfig:
    """Security configuration settings"""
    input_validation_enabled: bool = True
    rate_limiting_enabled: bool = True
    max_requests_per_minute: int = 100
    max_input_length: int = 50000
    allowed_file_types: List[str] = None
    
    def __post_init__(self):
        if self.allowed_file_types is None:
            self.allowed_file_types = [".txt", ".pdf", ".docx", ".csv", ".json"]

@dataclass
class AgentConfig:
    """Individual agent configuration"""
    name: str
    endpoint: str
    port: int
    enabled: bool = True
    health_check_interval: int = 60
    max_memory_usage: int = 512  # MB
    timeout: int = 120

@dataclass
class SystemConfig:
    """Main system configuration container"""
    database: DatabaseConfig
    logging: LoggingConfig
    llm: LLMConfig
    a2a: A2AConfig
    security: SecurityConfig
    agents: Dict[str, AgentConfig]
    debug_mode: bool = False
    environment: str = "development"  # development, production, testing
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SystemConfig':
        """Create from dictionary"""
        # Handle nested dataclasses
        database = DatabaseConfig(**data.get('database', {}))
        logging_cfg = LoggingConfig(**data.get('logging', {}))
        
        # Handle LLM config with pricing
        llm_data = data.get('llm', {})
        # Extract pricing data if present
        pricing_data = llm_data.pop('pricing', None)
        
        # Create LLMConfig without calling __post_init__ yet
        llm = LLMConfig(**llm_data)
        
        # If pricing data was provided in config, set it before __post_init__
        if pricing_data:
            llm.pricing = {}
            for model_name, prices in pricing_data.items():
                llm.pricing[model_name] = ModelPricing(
                    input_per_1k=prices['input_per_1k'],
                    output_per_1k=prices['output_per_1k']
                )
        else:
            # If no pricing data in config, let __post_init__ set defaults
            llm.pricing = {}
        
        a2a = A2AConfig(**data.get('a2a', {}))
        security = SecurityConfig(**data.get('security', {}))
        
        # Handle agents dict
        agents_data = data.get('agents', {})
        agents = {}
        for name, agent_data in agents_data.items():
            agents[name] = AgentConfig(name=name, **agent_data)
        
        return cls(
            database=database,
            logging=logging_cfg,
            llm=llm,
            a2a=a2a,
            security=security,
            agents=agents,
            debug_mode=data.get('debug_mode', False),
            environment=data.get('environment', 'development')
        )

class ConfigManager:
    """Centralized configuration manager"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "system_config.json"
        self._config: Optional[SystemConfig] = None
        self._load_config()
    
    def _load_config(self):
        """Load configuration from file and environment variables"""
        # Start with defaults
        config_data = self._get_default_config()
        
        # Override with file config if it exists
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    file_config = json.load(f)
                    config_data = self._merge_configs(config_data, file_config)
                logger.info(f"Loaded configuration from {self.config_path}")
            except Exception as e:
                logger.warning(f"Failed to load config file {self.config_path}: {e}")
        
        # Override with environment variables
        env_overrides = self._get_env_overrides()
        config_data = self._merge_configs(config_data, env_overrides)
        
        self._config = SystemConfig.from_dict(config_data)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "database": {},
            "logging": {},
            "llm": {},
            "a2a": {},
            "security": {},
            "agents": {
                "salesforce-agent": {
                    "endpoint": "http://localhost",
                    "port": 8001,
                    "enabled": True
                }
            },
            "debug_mode": False,
            "environment": "development"
        }
    
    def _get_env_overrides(self) -> Dict[str, Any]:
        """Get configuration overrides from environment variables"""
        overrides = {}
        
        # Debug mode
        if os.environ.get('DEBUG_MODE', '').lower() == 'true':
            overrides['debug_mode'] = True
        
        # Environment
        if env := os.environ.get('ENVIRONMENT'):
            overrides['environment'] = env
        
        # LLM configuration
        llm_overrides = {}
        if model := os.environ.get('LLM_MODEL'):
            llm_overrides['model'] = model
        if temp := os.environ.get('LLM_TEMPERATURE'):
            try:
                llm_overrides['temperature'] = float(temp)
            except ValueError:
                logger.warning(f"Invalid LLM_TEMPERATURE: {temp}")
        if max_tokens := os.environ.get('LLM_MAX_TOKENS'):
            try:
                llm_overrides['max_tokens'] = int(max_tokens)
            except ValueError:
                logger.warning(f"Invalid LLM_MAX_TOKENS: {max_tokens}")
        
        if llm_overrides:
            overrides['llm'] = llm_overrides
        
        # Database configuration
        db_overrides = {}
        if db_path := os.environ.get('DATABASE_PATH'):
            db_overrides['path'] = db_path
        if db_overrides:
            overrides['database'] = db_overrides
        
        # Logging configuration
        log_overrides = {}
        if log_level := os.environ.get('LOG_LEVEL'):
            log_overrides['level'] = log_level
        if log_dir := os.environ.get('LOGS_DIR'):
            log_overrides['external_logs_dir'] = log_dir
        if log_overrides:
            overrides['logging'] = log_overrides
        
        return overrides
    
    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge configuration dictionaries"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def save_config(self):
        """Save current configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self._config.to_dict(), f, indent=2)
            logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
    
    def get_config(self) -> SystemConfig:
        """Get the current system configuration"""
        if self._config is None:
            self._load_config()
        return self._config
    
    def update_config(self, updates: Dict[str, Any]):
        """Update configuration with new values"""
        if self._config is None:
            self._load_config()
        
        current_dict = self._config.to_dict()
        updated_dict = self._merge_configs(current_dict, updates)
        self._config = SystemConfig.from_dict(updated_dict)
    
    def get_agent_config(self, agent_name: str) -> Optional[AgentConfig]:
        """Get configuration for a specific agent"""
        return self._config.agents.get(agent_name)
    
    def add_agent_config(self, agent_config: AgentConfig):
        """Add or update agent configuration"""
        self._config.agents[agent_config.name] = agent_config
    
    def remove_agent_config(self, agent_name: str):
        """Remove agent configuration"""
        if agent_name in self._config.agents:
            del self._config.agents[agent_name]

# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None

def get_config_manager(config_path: Optional[str] = None) -> ConfigManager:
    """Get the global configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_path)
    return _config_manager

def get_system_config() -> SystemConfig:
    """Get the current system configuration"""
    return get_config_manager().get_config()

# Export ModelPricing for external use
__all__ = ['ModelPricing', 'LLMConfig', 'SystemConfig', 'get_system_config', 'get_llm_config']

def get_database_config() -> DatabaseConfig:
    """Get database configuration"""
    return get_system_config().database

def get_logging_config() -> LoggingConfig:
    """Get logging configuration"""
    return get_system_config().logging

def get_llm_config() -> LLMConfig:
    """Get LLM configuration"""
    return get_system_config().llm

def get_a2a_config() -> A2AConfig:
    """Get A2A protocol configuration"""
    return get_system_config().a2a

def get_security_config() -> SecurityConfig:
    """Get security configuration"""
    return get_system_config().security

def get_agent_config(agent_name: str) -> Optional[AgentConfig]:
    """Get configuration for a specific agent"""
    return get_config_manager().get_agent_config(agent_name)

def is_debug_mode() -> bool:
    """Check if debug mode is enabled"""
    return get_system_config().debug_mode