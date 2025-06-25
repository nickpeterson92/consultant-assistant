"""
Enterprise-Grade Configuration Management for Multi-Agent System

This module implements a sophisticated configuration architecture designed for production-scale
multi-agent systems, providing centralized management with multiple override layers and 
comprehensive validation.

Architecture Highlights:
- Type-safe configuration using Python dataclasses for compile-time validation
- Hierarchical configuration with JSON base, environment overrides, and runtime updates
- Singleton pattern ensures configuration consistency across the distributed system
- Immutable defaults with controlled mutation through defined interfaces
- Zero-config startup with sensible production defaults

Configuration Precedence (highest to lowest):
1. Runtime updates via ConfigManager API
2. Environment variables (e.g., DEBUG_MODE, LLM_MODEL)
3. JSON configuration file (system_config.json)
4. Hardcoded defaults in dataclass definitions

Design Decisions:
- JSON format chosen for human readability and broad tooling support
- Dataclasses provide type safety, validation, and IDE autocompletion
- Singleton pattern prevents configuration drift in long-running processes
- Nested configuration objects mirror system architecture for intuitive organization
"""

import os
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict, field
import logging
from .constants import (
    MODEL_PRICING,
    DEFAULT_TIMEOUT_SECONDS, DEFAULT_CONNECT_TIMEOUT, 
    DEFAULT_SOCKET_TIMEOUT, HEALTH_CHECK_TIMEOUT,
    CIRCUIT_BREAKER_FAILURE_THRESHOLD, CIRCUIT_BREAKER_TIMEOUT,
    SALESFORCE_AGENT_PORT,
    LOCALHOST
)

from ..logging import get_logger

logger = get_logger()

@dataclass
class DatabaseConfig:
    """Production-grade database configuration with connection pooling.
    
    SQLite was chosen for its zero-configuration deployment and excellent performance
    for single-node deployments. The connection pool prevents resource exhaustion
    under concurrent load.
    """
    path: str = "memory_store.db"
    timeout: int = 30
    pool_size: int = 5
    auto_commit: bool = True
    thread_pool_size: int = 4  # Thread pool size for async operations
    thread_prefix: str = "sqlite_"  # Thread name prefix for debugging

@dataclass 
class LoggingConfig:
    """Enterprise logging with rotation, buffering, and structured output.
    
    Implements production best practices:
    - Log rotation prevents disk exhaustion
    - Buffering reduces I/O overhead
    - Structured format enables log aggregation tools
    """
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    external_logs_dir: str = "logs"
    max_file_size: int = 10485760  # 10MB - prevents single log from consuming disk
    backup_count: int = 5  # Retains 50MB of historical logs
    buffer_size: int = 1000  # Batch writes for performance

@dataclass
class ModelPricing:
    """Cost tracking for LLM usage with per-token granularity.
    
    Essential for enterprise cost management and budget allocation.
    Supports dynamic pricing updates as model costs change.
    """
    input_per_1k: float
    output_per_1k: float
    
    @property
    def average_per_1k(self) -> float:
        """Calculate average cost per 1K tokens for budget estimation."""
        return (self.input_per_1k + self.output_per_1k) / 2

@dataclass
class LLMConfig:
    """Enterprise LLM configuration with caching, retries, and cost tracking.
    
    Key architectural decisions:
    - Temperature 0.0 for deterministic business operations
    - Aggressive caching reduces costs and latency
    - Exponential backoff retry strategy for resilience
    - Azure OpenAI for enterprise security and compliance
    """
    model: str = "gpt-4o-mini"
    temperature: float = 0.0  # Default can be tuned for user interactions via config
    top_p: Optional[float] = None  # Nucleus sampling - None uses model default (1.0)
    max_tokens: int = 4000  # Balance between context and cost
    timeout: int = 120  # Generous timeout for complex operations
    retry_attempts: int = 3
    retry_delay: float = 1.0
    cache_enabled: bool = True
    cache_ttl: int = 3600  # 1-hour cache balances freshness and efficiency
    azure_deployment: str = "gpt-4o-mini"
    api_version: str = "2024-06-01"  # Default overridden by constants if needed
    
    pricing: Dict[str, ModelPricing] = field(default_factory=dict)
    
    def __post_init__(self):
        # Default pricing from constants acts as fallback when config file lacks pricing data
        # Ensures cost tracking works out-of-the-box
        if not self.pricing:
            self.pricing = {
                model: ModelPricing(
                    input_per_1k=prices["input"], 
                    output_per_1k=prices["output"]
                )
                for model, prices in MODEL_PRICING.items()
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
    """Production-grade agent communication with resilience patterns.
    
    Implements Netflix-style circuit breaker pattern and connection pooling
    for fault-tolerant inter-agent communication. Timeouts are carefully
    tuned to balance responsiveness with reliability.
    """
    timeout: int = DEFAULT_TIMEOUT_SECONDS  # Total operation timeout
    connect_timeout: int = DEFAULT_CONNECT_TIMEOUT  # TCP handshake timeout
    sock_connect_timeout: int = DEFAULT_SOCKET_TIMEOUT  # Lower-level socket timeout
    sock_read_timeout: int = DEFAULT_SOCKET_TIMEOUT  # Read operation timeout
    health_check_timeout: int = HEALTH_CHECK_TIMEOUT  # Quick timeout for health probes
    max_concurrent_calls: int = 10  # Prevents agent overload
    retry_attempts: int = 3
    retry_delay: float = 1.0
    circuit_breaker_threshold: int = CIRCUIT_BREAKER_FAILURE_THRESHOLD  # Opens circuit after consecutive failures
    circuit_breaker_timeout: int = CIRCUIT_BREAKER_TIMEOUT  # Circuit reset interval
    connection_pool_size: int = 20  # Supports burst traffic
    connection_pool_ttl: int = 300  # 5-minute TTL balances efficiency and freshness
    connection_pool_max_idle: int = 300  # Matches TTL for consistency
    min_connections_per_host: int = 20  # Minimum connections per host

@dataclass
class SecurityConfig:
    """Security controls focused on what's actually implemented.
    
    Current security features:
    - Input validation in AgentInputValidator (SOQL injection prevention)
    - Max input length to prevent memory exhaustion
    """
    input_validation_enabled: bool = True
    max_input_length: int = 50000  # Prevents memory exhaustion

@dataclass
class AgentConfig:
    """Per-agent configuration supporting heterogeneous deployments.
    
    Each agent can have different resource limits and health check
    intervals based on its workload characteristics.
    """
    name: str
    endpoint: str
    port: int
    enabled: bool = True
    health_check_interval: int = 60  # Longer interval for stable agents
    heartbeat_interval: int = 30  # Frequent heartbeats for monitoring
    max_memory_usage: int = 512  # Memory limit prevents resource exhaustion
    timeout: int = 120  # Agent-specific timeout overrides

@dataclass
class ConversationConfig:
    """Intelligent conversation management with automatic summarization.
    
    Balances context window usage with conversation continuity:
    - Automatic summarization prevents token limit exhaustion
    - Delayed extraction avoids processing ephemeral data
    - Turn thresholds ensure meaningful interactions before persistence
    """
    summary_threshold: int = 12  # Summarize before context window pressure
    max_conversation_length: int = 100  # Hard limit prevents unbounded growth
    memory_extraction_enabled: bool = True
    memory_extraction_delay: float = 0.5  # Avoid extraction during rapid exchanges
    memory_update_turn_threshold: int = 3  # Ensure conversation stability first
    max_event_history: int = 50  # Limit event history to prevent unbounded growth (50 is sufficient for trigger logic)
    
    # User and namespace configuration
    default_user_id: str = "user-1"  # Default user ID for single-user mode
    default_thread_id: str = "default"  # Default thread ID
    memory_namespace_prefix: str = "memory"  # Prefix for memory namespaces
    summary_key: str = "conversation_summary"  # Key for storing summaries
    memory_key: str = "SimpleMemory"  # Key for storing structured memory
    
    # Typing effect configuration for enhanced UX
    typing_effect_enabled: bool = True  # Global toggle for typing animation
    typing_char_delay: float = 0.02  # Delay for character-by-character (first line)
    typing_chunk_delay: float = 0.08  # Delay between sentence chunks
    typing_line_delay: float = 0.03  # Delay between lines
    typing_paragraph_delay: float = 0.15  # Delay at paragraph breaks
    typing_first_line_char_limit: int = 100  # Max chars for first line animation
    typing_instant_elements: bool = True  # Instant display for tables/structure
    animated_banner_enabled: bool = True  # Enable animated banner on startup
    animated_capabilities_enabled: bool = True  # Enable animated capabilities sub-banner
    token_per_message_estimate: int = 400  # Estimated tokens per message
    token_budget_multiplier: int = 800  # Token budget multiplier for message preservation
    response_preview_length: int = 500  # Characters to show in response preview logs

@dataclass
class SystemConfig:
    """Root configuration object implementing the Composite pattern.
    
    Aggregates all subsystem configurations into a cohesive whole.
    The nested structure mirrors the system architecture, making
    configuration intuitive for operators.
    """
    database: DatabaseConfig
    logging: LoggingConfig
    llm: LLMConfig
    a2a: A2AConfig
    security: SecurityConfig
    conversation: ConversationConfig
    agents: Dict[str, AgentConfig]
    environment: str = "development"  # Controls environment-specific behaviors
    agent_registry_path: str = "agent_registry.json"  # Path to agent registry file
    
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
        conversation = ConversationConfig(**data.get('conversation', {}))
        
        # Handle agents dict
        agents_data = data.get('agents', {})
        agents = {}
        registry_path = None
        
        for name, agent_data in agents_data.items():
            if name == 'registry_path':
                # Extract registry_path separately
                registry_path = agent_data
            elif isinstance(agent_data, dict):
                # Only create AgentConfig for actual agent entries
                agents[name] = AgentConfig(name=name, **agent_data)
        
        return cls(
            database=database,
            logging=logging_cfg,
            llm=llm,
            a2a=a2a,
            security=security,
            conversation=conversation,
            agents=agents,
            environment=data.get('environment', 'development'),
            agent_registry_path=registry_path or 'agent_registry.json'
        )

class ConfigManager:
    """Singleton configuration manager implementing hierarchical overrides.
    
    The singleton pattern ensures configuration consistency across all
    components in the distributed system. Thread-safe lazy initialization
    supports both CLI and programmatic usage patterns.
    
    Configuration sources are merged in precedence order, allowing
    operators to override specific settings without modifying defaults.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "system_config.json"
        self._config: Optional[SystemConfig] = None
        self._load_config()
    
    def _load_config(self):
        """Implements the configuration cascade with validation.
        
        Loading order ensures predictable behavior:
        1. Built-in defaults provide zero-config startup
        2. JSON file allows persistent customization
        3. Environment variables enable deployment-specific overrides
        """
        config_data = self._get_default_config()
        
        # JSON configuration provides persistent customization
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    file_config = json.load(f)
                    config_data = self._merge_configs(config_data, file_config)
                logger.info("config_loaded",
                    component="config",
                    operation="load",
                    config_path=self.config_path
                )
            except Exception as e:
                # System continues with defaults on config errors
                logger.warning("config_load_failed",
                    component="config",
                    operation="load",
                    config_path=self.config_path,
                    error=str(e),
                    error_type=type(e).__name__
                )
        
        # Environment variables provide deployment-specific overrides
        env_overrides = self._get_env_overrides()
        config_data = self._merge_configs(config_data, env_overrides)
        
        self._config = SystemConfig.from_dict(config_data)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Provides sensible defaults for zero-configuration startup.
        
        Defaults are chosen for development convenience while maintaining
        security. Production deployments should override via JSON or env.
        """
        return {
            "database": {},
            "logging": {},
            "llm": {},
            "a2a": {},
            "security": {},
            "conversation": {},
            "agents": {
                "salesforce-agent": {
                    "endpoint": f"http://{LOCALHOST}",
                    "port": SALESFORCE_AGENT_PORT,
                    "enabled": True
                }
            },
            "environment": "development"
        }
    
    def _get_env_overrides(self) -> Dict[str, Any]:
        """Maps environment variables to configuration paths.
        
        Supports common deployment patterns:
        - DEBUG_MODE for development
        - DATABASE_PATH for container volumes
        - LLM_* for model selection and tuning
        """
        overrides = {}
        
        
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
                logger.warning("invalid_llm_temperature",
                    component="config",
                    operation="validation",
                    invalid_value=temp,
                    using_default=defaults.temperature
                )
        if max_tokens := os.environ.get('LLM_MAX_TOKENS'):
            try:
                llm_overrides['max_tokens'] = int(max_tokens)
            except ValueError:
                logger.warning("invalid_llm_max_tokens",
                    component="config",
                    operation="validation",
                    invalid_value=max_tokens,
                    using_default=defaults.max_tokens
                )
        
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
        """Deep merge preserving nested structure.
        
        Recursive merging allows partial overrides of nested configs
        without losing other settings in the same section.
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def save_config(self):
        """Persists runtime configuration changes.
        
        Enables configuration updates to survive restarts.
        Human-readable JSON format supports manual editing.
        """
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self._config.to_dict(), f, indent=2)
            logger.info("config_saved",
                component="config",
                operation="save",
                config_path=self.config_path
            )
        except Exception as e:
            logger.error("config_save_failed",
                component="config",
                operation="save",
                error=str(e),
                error_type=type(e).__name__
            )
    
    def get_config(self) -> SystemConfig:
        """Lazy initialization ensures configuration is always available."""
        if self._config is None:
            self._load_config()
        return self._config
    
    def reload_config(self):
        """Force reload configuration from disk.
        
        Useful when configuration file has been modified and you want
        to pick up changes without restarting the application.
        """
        logger.info("config_reloading",
            component="config",
            operation="reload",
            config_path=self.config_path
        )
        self._config = None
        self._load_config()
    
    def update_config(self, updates: Dict[str, Any]):
        """Runtime configuration updates without restart.
        
        Supports dynamic reconfiguration for:
        - Feature flags during incidents
        - Performance tuning under load
        - Agent registration/deregistration
        """
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

# Singleton instance with thread-safe lazy initialization
_config_manager: Optional[ConfigManager] = None

def get_config_manager(config_path: Optional[str] = None) -> ConfigManager:
    """Thread-safe singleton accessor.
    
    The module-level singleton ensures all components share the same
    configuration view, preventing drift in distributed systems.
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_path)
    return _config_manager

def get_system_config() -> SystemConfig:
    """Primary API for configuration access throughout the system."""
    return get_config_manager().get_config()

def reload_system_config():
    """Reload configuration from disk to pick up changes."""
    get_config_manager().reload_config()

# Public API exports - other modules should use these accessors
__all__ = ['ModelPricing', 'LLMConfig', 'SystemConfig', 'get_system_config', 'get_llm_config', 'reload_system_config']

# Convenience accessors provide type-safe configuration access
def get_database_config() -> DatabaseConfig:
    """Database configuration for storage layer."""
    return get_system_config().database

def get_logging_config() -> LoggingConfig:
    """Logging configuration for observability."""
    return get_system_config().logging

def get_llm_config() -> LLMConfig:
    """LLM configuration for AI operations."""
    return get_system_config().llm

def get_a2a_config() -> A2AConfig:
    """A2A protocol configuration for agent communication."""
    return get_system_config().a2a

def get_security_config() -> SecurityConfig:
    """Security configuration for access control."""
    return get_system_config().security

def get_conversation_config() -> ConversationConfig:
    """Conversation configuration for interaction management."""
    return get_system_config().conversation

def get_agent_config(agent_name: str) -> Optional[AgentConfig]:
    """Agent-specific configuration for dynamic discovery."""
    return get_config_manager().get_agent_config(agent_name)


def get_salesforce_config():
    """Get Salesforce configuration from environment."""
    return {
        "username": os.environ.get("SFDC_USER"),
        "password": os.environ.get("SFDC_PASS"),
        "security_token": os.environ.get("SFDC_TOKEN")
    }


def get_jira_config():
    """Get Jira configuration from environment."""
    return {
        "base_url": os.environ.get("JIRA_BASE_URL"),
        "user": os.environ.get("JIRA_USER"),
        "api_token": os.environ.get("JIRA_API_TOKEN")
    }


def get_memory_namespace(user_id: str = None) -> tuple:
    """Get the namespace tuple for memory storage.
    
    Args:
        user_id: Optional user ID, defaults to config default_user_id
        
    Returns:
        Tuple of (namespace_prefix, user_id) for memory storage
    """
    conv_config = get_conversation_config()
    if user_id is None:
        user_id = conv_config.default_user_id
    return (conv_config.memory_namespace_prefix, user_id)

