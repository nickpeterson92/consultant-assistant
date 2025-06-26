# Configuration Management

Centralized, type-safe, and environment-aware configuration system with hierarchical loading, validation, and secure handling of sensitive data.

## Overview

The configuration system provides a three-layer hierarchy:
1. **Environment Variables** (highest priority) - secrets and overrides
2. **Configuration Files** (medium priority) - environment-specific settings
3. **Hardcoded Defaults** (lowest priority) - universal constants

## Architecture

### Configuration Hierarchy

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ENVIRONMENT VARIABLES (Highest Priority)         │
│                    Wins every time - like the boss's orders         │
├─────────────────────────────────────────────────────────────────────┤
│                    CONFIG FILES (Medium Priority)                   │
│                    Team decisions - used when boss doesn't care     │
├─────────────────────────────────────────────────────────────────────┤
│                    HARDCODED DEFAULTS (Lowest Priority)             │
│                    Factory settings - only used as last resort      │
└─────────────────────────────────────────────────────────────────────┘
```

### Centralized Constants

All hardcoded values are centralized in `src/utils/constants.py`:

```python
# Memory and storage keys
MEMORY_NAMESPACE_PREFIX = "memory"
SIMPLE_MEMORY_KEY = "SimpleMemory"
STATE_KEY_PREFIX = "state_"

# Network constants
DEFAULT_A2A_PORT = 8000
SALESFORCE_AGENT_PORT = 8001

# Circuit breaker defaults
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
CIRCUIT_BREAKER_TIMEOUT = 30
```

## Configuration Files

### Master Configuration (system_config.json)

```json
{
  "environment": "development",
  "debug": false,
  "version": "1.0.0",
  
  "database": {
    "path": "./memory_store.db",
    "timeout": 30.0,
    "pool_size": 20,
    "wal_mode": true
  },
  
  "llm": {
    "provider": "azure_openai",
    "model": "gpt-4",
    "temperature": 0.1,
    "max_tokens": 4000,
    "timeout": 120.0,
    "retry_attempts": 3
  },
  
  "a2a": {
    "timeout": 30,
    "health_check_timeout": 10,
    "retry_attempts": 3,
    "circuit_breaker_threshold": 5,
    "connection_pool_size": 50
  },
  
  "agents": {
    "orchestrator": {
      "host": "localhost",
      "port": 8000
    },
    "salesforce": {
      "host": "localhost", 
      "port": 8001,
      "capabilities": ["salesforce_operations", "crm_management"]
    }
  }
}
```

### Agent Registry (agent_registry.json)

```json
{
  "agents": [
    {
      "name": "salesforce-agent",
      "endpoint": "http://localhost:8001",
      "agent_card": {
        "name": "salesforce-agent",
        "version": "1.0.0",
        "description": "Specialized agent for Salesforce CRM operations",
        "capabilities": [
          "salesforce_operations",
          "lead_management",
          "account_management"
        ],
        "endpoints": {
          "process_task": "/a2a",
          "agent_card": "/a2a/agent-card"
        }
      },
      "status": "online"
    }
  ]
}
```

## Environment Variables

### Core Settings

```bash
# Environment
ENVIRONMENT=development          # development, staging, production
DEBUG_MODE=true                 # Enable debug logging

# Azure OpenAI (Sensitive)
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-4-deployment

# Salesforce (Sensitive)
SFDC_USER=salesforce-username
SFDC_PASS=salesforce-password
SFDC_TOKEN=salesforce-security-token

# Database
DATABASE_PATH=./memory_store.db
DATABASE_TIMEOUT=30

# LLM Settings
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=4000
LLM_TIMEOUT=120

# A2A Protocol
A2A_TIMEOUT=30
A2A_RETRY_ATTEMPTS=3
A2A_CIRCUIT_BREAKER_THRESHOLD=5
```

## Configuration Classes

### Base Configuration

```python
@dataclass
class BaseConfig:
    """Base configuration with common fields"""
    environment: str = "development"
    debug: bool = False
    version: str = "1.0.0"
```

### Database Configuration

```python
@dataclass
class DatabaseConfig:
    """SQLite database configuration"""
    path: str = "./memory_store.db"
    timeout: float = 30.0
    pool_size: int = 20
    auto_commit: bool = True
    wal_mode: bool = True
    
    @property
    def connection_string(self) -> str:
        return f"sqlite:///{self.path}?timeout={self.timeout}"
```

### LLM Configuration

```python
@dataclass
class LLMConfig:
    """Language model configuration"""
    provider: str = "azure_openai"
    model: str = "gpt-4"
    temperature: float = 0.1
    max_tokens: int = 4000
    timeout: float = 120.0
    retry_attempts: int = 3
    cost_per_1k_tokens: Dict[str, float] = field(default_factory=lambda: {
        "input": 0.01,
        "output": 0.03
    })
    
    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for token usage"""
        input_cost = (input_tokens / 1000) * self.cost_per_1k_tokens["input"]
        output_cost = (output_tokens / 1000) * self.cost_per_1k_tokens["output"]
        return input_cost + output_cost
```

### A2A Configuration

```python
@dataclass
class A2AConfig:
    """Agent-to-Agent protocol configuration"""
    timeout: int = 30
    health_check_timeout: int = 10
    retry_attempts: int = 3
    circuit_breaker_threshold: int = 5
    connection_pool_size: int = 50
    connection_pool_size_per_host: int = 20
    
    def get_pool_config(self) -> Dict[str, Any]:
        """Get aiohttp connection pool configuration"""
        return {
            "limit": self.connection_pool_size,
            "limit_per_host": self.connection_pool_size_per_host,
            "ttl_dns_cache": 300,
            "keepalive_timeout": 30,
            "enable_cleanup_closed": True
        }
```

## Configuration Manager

### Singleton Implementation

```python
class ConfigManager:
    """Centralized configuration management"""
    _instance = None
    _config = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def load_config(self, config_path: str = "system_config.json"):
        """Load configuration from file and environment"""
        # Load from file
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                file_config = json.load(f)
        else:
            file_config = {}
        
        # Override with environment variables
        self._config = self._merge_with_env(file_config)
        
        # Validate configuration
        self._validate_config()
        
        return self._config
```

### Environment Variable Override

```python
def _merge_with_env(self, config: Dict[str, Any]) -> Dict[str, Any]:
    """Override config values with environment variables"""
    
    # Map of env vars to config paths
    env_mapping = {
        "ENVIRONMENT": "environment",
        "DEBUG_MODE": "debug",
        "DATABASE_PATH": "database.path",
        "DATABASE_TIMEOUT": "database.timeout",
        "LOG_LEVEL": "logging.level",
        "LLM_TEMPERATURE": "llm.temperature",
        "LLM_MAX_TOKENS": "llm.max_tokens",
        "A2A_TIMEOUT": "a2a.timeout"
    }
    
    for env_var, config_path in env_mapping.items():
        if env_var in os.environ:
            set_nested_value(config, config_path, 
                           parse_env_value(os.environ[env_var]))
    
    return config
```

## Access Patterns

### Global Access Functions

```python
# Cached configuration access
_config_cache = {}

def get_system_config() -> SystemConfig:
    """Get complete system configuration"""
    if "system" not in _config_cache:
        _config_cache["system"] = ConfigManager().get_system_config()
    return _config_cache["system"]

def get_llm_config() -> LLMConfig:
    """Get LLM configuration"""
    if "llm" not in _config_cache:
        _config_cache["llm"] = ConfigManager().get_llm_config()
    return _config_cache["llm"]

def get_a2a_config() -> A2AConfig:
    """Get A2A protocol configuration"""
    if "a2a" not in _config_cache:
        _config_cache["a2a"] = ConfigManager().get_a2a_config()
    return _config_cache["a2a"]
```

### Component Usage

```python
# In orchestrator
llm_config = get_llm_config()
llm = AzureChatOpenAI(
    temperature=llm_config.temperature,
    max_tokens=llm_config.max_tokens,
    timeout=llm_config.timeout
)

# In A2A client
a2a_config = get_a2a_config()
connector = aiohttp.TCPConnector(
    **a2a_config.get_pool_config()
)

# In storage layer
db_config = get_database_config()
engine = create_engine(
    db_config.connection_string,
    pool_size=db_config.pool_size
)
```

## Security

### Sensitive Data Handling

```python
# Never log sensitive configuration
SENSITIVE_KEYS = {
    "AZURE_OPENAI_API_KEY",
    "SFDC_PASS",
    "SFDC_TOKEN",
    "DATABASE_PASSWORD"
}

def sanitize_config_for_logging(config: Dict[str, Any]) -> Dict[str, Any]:
    """Remove sensitive values before logging"""
    sanitized = deepcopy(config)
    
    for key in SENSITIVE_KEYS:
        if key in sanitized:
            sanitized[key] = "***REDACTED***"
    
    return sanitized
```

### Best Practices

- Never commit secrets to Git
- Use environment variables for sensitive data
- Rotate credentials regularly
- Audit configuration access
- Encrypt configuration files when needed

## Validation

### Configuration Validation

```python
def validate_config(config: Dict[str, Any]) -> None:
    """Validate configuration completeness and correctness"""
    
    # Required fields
    required_fields = [
        "llm.provider",
        "llm.model",
        "database.path",
        "a2a.timeout"
    ]
    
    for field in required_fields:
        if not get_nested_value(config, field):
            raise ConfigurationError(f"Missing required field: {field}")
    
    # Value constraints
    if config.get("llm", {}).get("temperature", 0) > 1.0:
        raise ConfigurationError("LLM temperature must be <= 1.0")
    
    if config.get("a2a", {}).get("timeout", 0) < 1:
        raise ConfigurationError("A2A timeout must be >= 1")
```

### Type Safety

```python
def parse_config_value(value: Any, target_type: Type[T]) -> T:
    """Safely parse configuration values to target types"""
    
    if target_type == bool:
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value)
    
    elif target_type == int:
        return int(value)
    
    elif target_type == float:
        return float(value)
    
    else:
        raise ValueError(f"Unsupported type: {target_type}")
```

## Environment-Specific Configuration

### Development vs Production

```python
# Development
{
  "environment": "development",
  "debug": true,
  "llm": {
    "temperature": 0.7,  // More creative
    "timeout": 30        // Fail fast
  }
}

# Production
{
  "environment": "production", 
  "debug": false,
  "llm": {
    "temperature": 0.1,  // Consistent
    "timeout": 120,      // Reliable
    "retry_attempts": 5  // High availability
  }
}
```

### Environment Detection

```python
class Environment(Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    
    @classmethod
    def current(cls):
        """Get current environment"""
        env_name = os.environ.get("ENVIRONMENT", "development").lower()
        return cls(env_name)
    
    def is_production(self):
        return self == Environment.PRODUCTION
```

## Hot Reloading

### File Watcher

```python
class ConfigWatcher:
    """Watch configuration files for changes"""
    
    def __init__(self, config_path: str, callback: Callable):
        self.config_path = config_path
        self.callback = callback
        self.observer = Observer()
    
    def start(self):
        """Start watching for changes"""
        event_handler = FileSystemEventHandler()
        event_handler.on_modified = self._on_modified
        
        self.observer.schedule(
            event_handler,
            os.path.dirname(self.config_path),
            recursive=False
        )
        self.observer.start()
```

### Dynamic Reconfiguration

```python
def reload_configuration():
    """Reload configuration without restart"""
    global _config_cache
    
    # Clear cache
    _config_cache.clear()
    
    # Reload from files
    ConfigManager().load_config()
    
    # Notify components
    for component in registered_components:
        component.on_config_reload()
    
    logger.info("Configuration reloaded successfully")
```

## Best Practices

### Configuration Structure
- Group related settings
- Use consistent naming conventions
- Provide sensible defaults
- Document all options
- Version configuration schema

### Security
- Never commit secrets to version control
- Use environment variables for sensitive data
- Implement proper secret rotation
- Audit configuration access
- Encrypt sensitive configuration files

### Performance
- Cache configuration objects
- Minimize file I/O operations
- Use lazy loading for large configurations
- Profile configuration access patterns

### Testing
- Test with different configuration combinations
- Validate configuration on startup
- Test environment variable overrides
- Verify type conversions work correctly

## Troubleshooting

### Common Issues

1. **Missing Configuration**
   - Check file exists and has valid JSON
   - Verify environment variables are set
   - Review validation error messages

2. **Type Mismatches**
   - Verify JSON syntax is correct
   - Check environment variable parsing
   - Review configuration schema

3. **Override Not Working**
   - Check environment variable names match mapping
   - Verify loading order (env vars override files)
   - Check for typos in variable names

4. **Performance Issues**
   - Enable configuration caching
   - Reduce file reads with hot reloading
   - Profile configuration access patterns