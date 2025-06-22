# Configuration Management Documentation

## Overview

The configuration management system provides centralized, type-safe, and environment-aware configuration for all components of the multi-agent system. It supports multiple configuration sources (files, environment variables), validation, hot-reloading, and secure handling of sensitive data.

## Architecture

### Configuration Hierarchy

```
┌──────────────────────────────────────────────────────────────────┐
│                    Configuration Sources                         │
├──────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐    │
│  │ Environment │  │    JSON      │  │    Default Values     │    │
│  │  Variables  │  │    Files     │  │    (Hardcoded)        │    │
│  └──────┬──────┘  └──────┬───────┘  └───────────┬───────────┘    │
│         │                 │                       │              │
│         └─────────────────┴───────────────────────┘              │
│                           │                                      │
│                    ┌──────▼──────┐                               │
│                    │   Config    │                               │
│                    │   Manager   │                               │
│                    └──────┬──────┘                               │
│                           │                                      │
│         ┌─────────────────┼─────────────────────┐                │
│         ▼                 ▼                     ▼                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │     LLM      │  │     A2A      │  │   Database   │            │
│  │   Config     │  │   Config     │  │    Config    │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
└──────────────────────────────────────────────────────────────────┘
```

### Configuration Loading Order

1. **Default Values** - Hardcoded fallbacks
2. **Configuration Files** - JSON/YAML files
3. **Environment Variables** - Override file values
4. **Runtime Updates** - Dynamic reconfiguration

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
    "auto_commit": true,
    "wal_mode": true
  },
  
  "logging": {
    "level": "INFO",
    "format": "json",
    "file_rotation": true,
    "max_file_size": "100MB",
    "backup_count": 5,
    "buffer_size": 1000
  },
  
  "llm": {
    "provider": "azure_openai",
    "model": "gpt-4",
    "azure_deployment": "gpt-4-deployment",
    "api_version": "2024-02-15-preview",
    "temperature": 0.1,
    "max_tokens": 4000,
    "timeout": 120.0,
    "retry_attempts": 3,
    "retry_delay": 1.0,
    "cost_per_1k_tokens": {
      "input": 0.01,
      "output": 0.03
    }
  },
  
  "a2a": {
    "timeout": 30,
    "health_check_timeout": 10,
    "retry_attempts": 3,
    "retry_delay": 1.0,
    "circuit_breaker_threshold": 5,
    "circuit_breaker_timeout": 60,
    "connection_pool_size": 50,
    "connection_pool_size_per_host": 20,
    "keepalive_timeout": 30,
    "dns_cache_ttl": 300
  },
  
  "conversation": {
    "summary_trigger_messages": 5,
    "max_messages_to_preserve": 10,
    "max_tokens_to_preserve": 3000,
    "max_event_history": 50,
    "memory_update_trigger_messages": 5
  },
  
  "agents": {
    "orchestrator": {
      "host": "localhost",
      "port": 8000,
      "recursion_limit": 50
    },
    "salesforce": {
      "host": "localhost", 
      "port": 8001,
      "capabilities": ["salesforce_operations", "crm_management"],
      "health_check_interval": 30
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
          "account_management",
          "opportunity_tracking",
          "contact_management",
          "case_handling",
          "task_management"
        ],
        "endpoints": {
          "process_task": "/a2a",
          "agent_card": "/a2a/agent-card"
        },
        "communication_modes": ["synchronous", "streaming"]
      },
      "status": "online",
      "last_health_check": "2024-01-15T10:30:45Z"
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
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Salesforce (Sensitive)
SFDC_USER=salesforce-username
SFDC_PASS=salesforce-password
SFDC_TOKEN=salesforce-security-token

# Database
DATABASE_PATH=./memory_store.db
DATABASE_TIMEOUT=30

# Logging
LOG_LEVEL=INFO                  # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=json                 # json, plain

# LLM Settings
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=4000
LLM_TIMEOUT=120

# A2A Protocol
A2A_TIMEOUT=30
A2A_RETRY_ATTEMPTS=3
A2A_CIRCUIT_BREAKER_THRESHOLD=5
A2A_CONNECTION_POOL_SIZE=50
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
    azure_deployment: str = "gpt-4-deployment"
    api_version: str = "2024-02-15-preview"
    temperature: float = 0.1
    max_tokens: int = 4000
    timeout: float = 120.0
    retry_attempts: int = 3
    retry_delay: float = 1.0
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
    retry_delay: float = 1.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 60
    connection_pool_size: int = 50
    connection_pool_size_per_host: int = 20
    keepalive_timeout: int = 30
    dns_cache_ttl: int = 300
    
    def get_pool_config(self) -> Dict[str, Any]:
        """Get aiohttp connection pool configuration"""
        return {
            "limit": self.connection_pool_size,
            "limit_per_host": self.connection_pool_size_per_host,
            "ttl_dns_cache": self.dns_cache_ttl,
            "keepalive_timeout": self.keepalive_timeout,
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
        "A2A_TIMEOUT": "a2a.timeout",
        # ... more mappings
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

def get_database_config() -> DatabaseConfig:
    """Get database configuration"""
    if "database" not in _config_cache:
        _config_cache["database"] = ConfigManager().get_database_config()
    return _config_cache["database"]
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
    
    # Environment-specific validation
    if config.get("environment") == "production":
        if config.get("debug", False):
            logger.warning("Debug mode enabled in production!")
```

### Type Safety

```python
from typing import TypeVar, Type

T = TypeVar('T')

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
    
    elif target_type == str:
        return str(value)
    
    else:
        raise ValueError(f"Unsupported type: {target_type}")
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

### Encryption

```python
from cryptography.fernet import Fernet

class SecureConfigStore:
    """Encrypted configuration storage"""
    
    def __init__(self, key: bytes):
        self.cipher = Fernet(key)
    
    def save_secure_config(self, config: Dict[str, Any], path: str):
        """Save encrypted configuration"""
        json_data = json.dumps(config)
        encrypted = self.cipher.encrypt(json_data.encode())
        
        with open(path, 'wb') as f:
            f.write(encrypted)
    
    def load_secure_config(self, path: str) -> Dict[str, Any]:
        """Load and decrypt configuration"""
        with open(path, 'rb') as f:
            encrypted = f.read()
        
        decrypted = self.cipher.decrypt(encrypted)
        return json.loads(decrypted.decode())
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
        self.last_modified = os.path.getmtime(config_path)
    
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
    
    def _on_modified(self, event):
        """Handle file modification"""
        if event.src_path == self.config_path:
            current_modified = os.path.getmtime(self.config_path)
            if current_modified != self.last_modified:
                self.last_modified = current_modified
                self.callback()
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

## Environment-Specific Configuration

### Development Settings

```python
if get_system_config().environment == "development":
    # Enable debug features
    logging.getLogger().setLevel(logging.DEBUG)
    
    # Use local services
    os.environ["AGENT_REGISTRY_URL"] = "http://localhost:8080"
    
    # Disable SSL verification
    os.environ["PYTHONHTTPSVERIFY"] = "0"
```

### Production Settings

```python
if get_system_config().environment == "production":
    # Enforce security
    assert os.environ.get("AZURE_OPENAI_API_KEY"), "API key required"
    
    # Use production services
    os.environ["AGENT_REGISTRY_URL"] = "https://registry.prod.company.com"
    
    # Enable monitoring
    enable_apm_monitoring()
```

## Best Practices

### 1. Configuration Structure

- Group related settings
- Use consistent naming
- Provide sensible defaults
- Document all options
- Version configuration schema

### 2. Security

- Never commit secrets
- Use environment variables for sensitive data
- Encrypt configuration files
- Rotate credentials regularly
- Audit configuration access

### 3. Validation

- Validate on load
- Type check values
- Check value ranges
- Verify dependencies
- Test configurations

### 4. Performance

- Cache configuration objects
- Minimize file I/O
- Use lazy loading
- Batch configuration updates
- Profile configuration access

## Monitoring

### Configuration Metrics

```python
# Track configuration usage
config_access_counter = Counter(
    'config_access_total',
    'Configuration access count',
    ['component', 'config_type']
)

# Track reload events
config_reload_counter = Counter(
    'config_reload_total',
    'Configuration reload count'
)

# Track validation failures
config_validation_errors = Counter(
    'config_validation_errors_total',
    'Configuration validation errors'
)
```

### Audit Logging

```json
{
  "timestamp": "2024-01-15T10:30:45Z",
  "event": "config_access",
  "component": "orchestrator",
  "config_type": "llm",
  "user": "system",
  "source": "file"
}
```

## Troubleshooting

### Common Issues

1. **Missing Configuration**
   - Check file exists
   - Verify environment variables
   - Review validation errors
   - Check file permissions

2. **Type Mismatches**
   - Verify JSON syntax
   - Check type conversions
   - Review schema changes
   - Update validation rules

3. **Override Not Working**
   - Check environment variable names
   - Verify loading order
   - Review merge logic
   - Check for typos

4. **Performance Issues**
   - Enable configuration caching
   - Reduce file reads
   - Optimize validation
   - Profile access patterns

## Future Enhancements

1. **Configuration Service**: Centralized configuration server
2. **Schema Evolution**: Automatic migration support
3. **A/B Testing**: Configuration experiments
4. **Feature Flags**: Dynamic feature toggles
5. **Audit Trail**: Complete configuration history