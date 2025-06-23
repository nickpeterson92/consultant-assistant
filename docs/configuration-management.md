# Configuration Management Documentation

## 🚨 Why Configuration Management Matters

### Real-World Configuration Disasters

Before diving into how to manage configuration, let's understand why it's critical by looking at some real-world disasters:

1. **Knight Capital Group (2012)** - A misconfigured deployment flag caused their trading software to execute 4 million trades in 45 minutes, losing $440 million and bankrupting the company.

2. **Amazon S3 Outage (2017)** - An engineer accidentally typed a larger server quantity than intended in a command, taking down a significant portion of the internet for hours. Proper configuration validation would have prevented this.

3. **GitLab Database Deletion (2017)** - A tired engineer ran a database deletion command on the wrong server (production instead of staging) due to similar configuration. They lost 6 hours of user data.

4. **Facebook Outage (2021)** - A configuration change to backbone routers knocked Facebook, Instagram, and WhatsApp offline for 6 hours, costing an estimated $100 million.

**The lesson**: Poor configuration management can destroy companies, lose customer data, and cost millions. That's why we take it seriously.

## 🎯 Configuration Management Goals

Good configuration management should:
- **Prevent disasters** - Make it hard to accidentally break production
- **Enable flexibility** - Easy to change behavior without code changes
- **Support multiple environments** - Dev, staging, and prod with different settings
- **Secure sensitive data** - API keys and passwords must be protected
- **Provide auditability** - Know who changed what and when
- **Enable rollback** - Quickly revert bad changes

## Overview

The configuration management system provides centralized, type-safe, and environment-aware configuration for all components of the multi-agent system. It supports multiple configuration sources (files, environment variables), validation, hot-reloading, and secure handling of sensitive data.

## Architecture

## 📊 Configuration Hierarchy Explained Simply

Think of configuration like layers of an onion, where each outer layer can override the inner ones:

### The Three Layers of Configuration

```
┌─────────────────────────────────────────────────────────────────────┐
│                    🌍 ENVIRONMENT VARIABLES (Highest Priority)      │
│                    Wins every time - like the boss's orders         │
├─────────────────────────────────────────────────────────────────────┤
│                    📄 CONFIG FILES (Medium Priority)                │
│                    Team decisions - used when boss doesn't care     │
├─────────────────────────────────────────────────────────────────────┤
│                    💻 HARDCODED DEFAULTS (Lowest Priority)          │
│                    Factory settings - only used as last resort      │
└─────────────────────────────────────────────────────────────────────┘
```

### Real Example from Our Codebase

Let's say we want to set the database timeout:

1. **Hardcoded Default** (in `src/utils/constants.py`):
   ```python
   DEFAULT_DATABASE_TIMEOUT = 30  # Factory setting: 30 seconds
   ```

2. **Config File** (in `system_config.json`):
   ```json
   {
     "database": {
       "timeout": 45  // Team decided 45 seconds is better
     }
   }
   ```

3. **Environment Variable** (in production):
   ```bash
   export DATABASE_TIMEOUT=60  # Ops team says production needs 60 seconds
   ```

**Result**: The app uses 60 seconds (environment variable wins!)

### Why This Hierarchy?

- **Development**: Use config files for easy team-wide settings
- **Testing**: Override specific values with environment variables
- **Production**: Secure secrets in environment variables, never in files
- **Emergency**: Quick fixes via environment variables without deployment

### Configuration Loading Order

1. **Default Values** - Hardcoded fallbacks (see `src/utils/constants.py`)
2. **Configuration Files** - JSON/YAML files  
3. **Environment Variables** - Override file values
4. **Runtime Updates** - Dynamic reconfiguration

## 🔀 Environment Variables vs Config Files vs Hardcoded Values

### When to Use Each

| Type | Use For | Example | Why |
|------|---------|---------|-----|
| **Hardcoded** | Universal constants that NEVER change | `MAX_RETRIES = 3` | These are laws of your system |
| **Config Files** | Settings that change between deployments | `"log_level": "INFO"` | Different for dev/staging/prod |
| **Env Variables** | Secrets & emergency overrides | `AZURE_API_KEY=secret123` | Security & quick changes |

### ❌ Common Mistakes (Don't Do This!)

```python
# ❌ BAD: Hardcoding environment-specific values
class DatabaseClient:
    def __init__(self):
        self.host = "prod-db.company.com"  # What about dev/staging?
        self.password = "Super$ecret123"   # NEVER hardcode secrets!

# ❌ BAD: Putting secrets in config files
{
  "salesforce": {
    "password": "MyPassword123",  // This gets committed to Git!
    "api_token": "sk-1234567890"  // Hackers will find this!
  }
}

# ❌ BAD: Using magic numbers without context
if retry_count > 5:  # Why 5? What does this mean?
    raise Exception("Failed")
```

### ✅ Good Examples (Do This Instead!)

```python
# ✅ GOOD: Use constants with clear names
from src.utils.constants import MAX_RETRY_ATTEMPTS

if retry_count > MAX_RETRY_ATTEMPTS:
    raise Exception(f"Failed after {MAX_RETRY_ATTEMPTS} attempts")

# ✅ GOOD: Use environment variables for secrets
import os
password = os.environ.get("SFDC_PASS")  # Never in code!

# ✅ GOOD: Use config files for non-sensitive settings
config = load_config("system_config.json")
log_level = config.get("logging", {}).get("level", "INFO")
```

### Centralized Constants

All hardcoded values and constants are now centralized in `src/utils/constants.py`:

```python
# Memory and storage keys
MEMORY_NAMESPACE_PREFIX = "memory"
SIMPLE_MEMORY_KEY = "SimpleMemory"
STATE_KEY_PREFIX = "state_"

# Network constants
DEFAULT_A2A_PORT = 8000
SALESFORCE_AGENT_PORT = 8001

# Model pricing (per 1K tokens)
MODEL_PRICING = {
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.00060}
}

# Circuit breaker defaults
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
CIRCUIT_BREAKER_TIMEOUT = 30
```

## 📝 Step-by-Step Guide: Adding New Configuration

Let's walk through adding a new configuration option to our system. We'll add a "request timeout" setting for our agents.

### Step 1: Define the Constant (if needed)

First, add a default value to `src/utils/constants.py`:

```python
# src/utils/constants.py
# Agent request handling
DEFAULT_AGENT_REQUEST_TIMEOUT = 30  # seconds
MAX_AGENT_REQUEST_TIMEOUT = 300     # 5 minutes max
```

### Step 2: Add to Config File

Update `system_config.json`:

```json
{
  "agents": {
    "request_timeout": 45,  // Override the default 30 seconds
    "orchestrator": {
      "host": "localhost",
      "port": 8000
    }
  }
}
```

### Step 3: Create/Update Config Class

Add to the configuration dataclass in `src/utils/config.py`:

```python
@dataclass
class AgentConfig:
    """Agent-specific configuration"""
    request_timeout: int = DEFAULT_AGENT_REQUEST_TIMEOUT  # New field!
    host: str = "localhost"
    port: int = 8000
    
    def validate(self):
        """Validate configuration values"""
        if self.request_timeout > MAX_AGENT_REQUEST_TIMEOUT:
            raise ValueError(f"Request timeout {self.request_timeout} exceeds maximum {MAX_AGENT_REQUEST_TIMEOUT}")
        if self.request_timeout < 1:
            raise ValueError("Request timeout must be at least 1 second")
```

### Step 4: Add Environment Variable Support

Update the environment mapping in `config.py`:

```python
# src/utils/config.py
env_mapping = {
    "AGENT_REQUEST_TIMEOUT": "agents.request_timeout",  # New mapping!
    "AGENT_HOST": "agents.orchestrator.host",
    "AGENT_PORT": "agents.orchestrator.port"
}
```

### Step 5: Use the Configuration

In your code:

```python
# src/agents/base_agent.py
from src.utils.config import get_agent_config

class BaseAgent:
    def __init__(self):
        self.config = get_agent_config()
        self.request_timeout = self.config.request_timeout  # Use it!
    
    async def handle_request(self, request):
        try:
            async with timeout(self.request_timeout):
                return await self._process_request(request)
        except asyncio.TimeoutError:
            logger.error(f"Request timed out after {self.request_timeout} seconds")
            raise
```

### Step 6: Document the New Setting

Update your `.env.example`:

```bash
# Agent Configuration
AGENT_REQUEST_TIMEOUT=45    # Timeout for agent requests (seconds)
                           # Default: 30, Max: 300
```

### Step 7: Test Your Configuration

Write a test to verify it works:

```python
def test_agent_timeout_configuration():
    # Test default value
    config = AgentConfig()
    assert config.request_timeout == DEFAULT_AGENT_REQUEST_TIMEOUT
    
    # Test environment override
    os.environ["AGENT_REQUEST_TIMEOUT"] = "60"
    config = load_agent_config()
    assert config.request_timeout == 60
    
    # Test validation
    with pytest.raises(ValueError):
        config = AgentConfig(request_timeout=400)  # Too high!
        config.validate()
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

## 🔐 Security Best Practices for Sensitive Config

### The Golden Rules

1. **Never commit secrets to Git** - They live forever in history
2. **Use environment variables for all secrets** - Not config files
3. **Rotate secrets regularly** - Assume they're compromised
4. **Limit secret access** - Only who needs them
5. **Audit secret usage** - Know who accessed what

### Real Examples from Our Codebase

#### ❌ What NOT to Do

```python
# ❌ NEVER hardcode secrets
AZURE_API_KEY = "sk-proj-abc123def456"  # This is now on GitHub forever!

# ❌ NEVER put secrets in config files
{
  "azure": {
    "api_key": "sk-proj-abc123def456"  // Even in .gitignore files!
  }
}

# ❌ NEVER log secrets
logger.info(f"Connecting with password: {password}")  # Shows in logs!

# ❌ NEVER send secrets in error messages
raise Exception(f"Auth failed with token: {api_token}")  # Exposed!
```

#### ✅ What TO Do Instead

```python
# ✅ Use environment variables
import os
api_key = os.environ.get("AZURE_OPENAI_API_KEY")
if not api_key:
    raise ValueError("AZURE_OPENAI_API_KEY environment variable not set")

# ✅ Use secret managers in production
from azure.keyvault.secrets import SecretClient
client = SecretClient(vault_url="https://vault.azure.net", credential=credential)
api_key = client.get_secret("azure-api-key").value

# ✅ Sanitize logs
logger.info(f"Connecting to Azure OpenAI endpoint: {endpoint}")  # No secrets!

# ✅ Generic error messages
raise Exception("Authentication failed. Check your credentials.")  # No details!
```

### Protecting Secrets in Different Environments

#### Development (Local Machine)
```bash
# Use a .env file (BUT NEVER COMMIT IT!)
# .env (add to .gitignore!)
AZURE_OPENAI_API_KEY=sk-dev-1234567890
SFDC_PASS=mydevpassword

# Load in Python
from dotenv import load_dotenv
load_dotenv()  # Loads .env file
```

#### Staging/Testing
```bash
# Use CI/CD secret management
# GitHub Actions example:
- name: Run tests
  env:
    AZURE_OPENAI_API_KEY: ${{ secrets.AZURE_API_KEY }}
    SFDC_PASS: ${{ secrets.SFDC_PASSWORD }}
  run: pytest
```

#### Production
```bash
# Use cloud secret managers
# Azure Key Vault, AWS Secrets Manager, etc.
# Or Kubernetes secrets for containerized apps
```

### Secret Rotation Strategy

1. **Generate new secret** in secret manager
2. **Update application** to accept both old and new
3. **Deploy** application with dual support
4. **Update all references** to use new secret
5. **Remove old secret** support in next deployment
6. **Delete old secret** from secret manager

### Detecting Leaked Secrets

Use tools to scan for accidentally committed secrets:

```bash
# Install git-secrets
brew install git-secrets  # macOS
git secrets --install

# Add patterns to detect
git secrets --add "sk-[a-zA-Z0-9]{48}"  # OpenAI keys
git secrets --add "sfdc_[a-zA-Z0-9]{32}"  # Salesforce tokens

# Scan repository
git secrets --scan
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

## 🚫 Common Configuration Mistakes (Learn from Others' Pain)

### 1. The "It Works on My Machine" Mistake

```python
# ❌ BAD: Hardcoding local paths
DATABASE_PATH = "/Users/john/project/database.db"  # Breaks for everyone else!

# ✅ GOOD: Use relative or configurable paths
DATABASE_PATH = os.environ.get("DATABASE_PATH", "./database.db")
```

### 2. The "One Config to Rule Them All" Mistake

```python
# ❌ BAD: Same config for all environments
{
  "debug": true,           // Debug in production!
  "database": "test.db",   // Test database in production!
  "cache_ttl": 0          // No caching in production!
}

# ✅ GOOD: Environment-specific configs
if ENVIRONMENT == "production":
    config = load_config("config.prod.json")
elif ENVIRONMENT == "staging":
    config = load_config("config.staging.json")
else:
    config = load_config("config.dev.json")
```

### 3. The "Type Confusion" Mistake

```python
# ❌ BAD: Assuming types from config
timeout = config["timeout"]  # "30" (string) or 30 (int)?
if timeout > 25:  # TypeError if it's a string!
    do_something()

# ✅ GOOD: Validate and convert types
timeout = int(config.get("timeout", 30))
if timeout > 25:
    do_something()
```

### 4. The "Silent Failure" Mistake

```python
# ❌ BAD: Silently using defaults when config is missing
try:
    config = load_config()
except:
    config = {}  # App runs with no config!

# ✅ GOOD: Fail fast with clear errors
try:
    config = load_config()
except FileNotFoundError:
    logger.error("Configuration file not found. Please create system_config.json")
    sys.exit(1)
```

### 5. The "Configuration Sprawl" Mistake

```python
# ❌ BAD: Config values scattered everywhere
class DatabaseClient:
    TIMEOUT = 30  # Config in class
    
def connect():
    retry = 3  # Config in function
    
MAX_CONNECTIONS = 100  # Config in module

# ✅ GOOD: Centralized configuration
from src.utils.config import get_database_config

config = get_database_config()
# Now all database config is in one place
```

### 6. The "No Validation" Mistake

```python
# ❌ BAD: Using config values without validation
port = config["port"]  # What if it's negative? Or > 65535?
connect(port=port)     # Connection fails mysteriously

# ✅ GOOD: Validate configuration on load
def validate_port(port):
    if not isinstance(port, int):
        raise ValueError(f"Port must be integer, got {type(port)}")
    if not 1 <= port <= 65535:
        raise ValueError(f"Port {port} out of valid range (1-65535)")
    return port

port = validate_port(config["port"])
```

### 7. The "Commit and Forget" Mistake

```bash
# ❌ BAD: Committing .env files
git add .env  # Contains all your secrets!
git commit -m "Added config"
git push  # Now it's public forever!

# ✅ GOOD: Use .gitignore
echo ".env" >> .gitignore
echo "*.env" >> .gitignore
echo ".env.*" >> .gitignore
git add .gitignore
git commit -m "Ignore env files"
```

### 8. The "Copy-Paste Config" Mistake

```json
// ❌ BAD: Duplicating config across files
// config.dev.json
{
  "llm": {
    "model": "gpt-4",
    "temperature": 0.7,
    "max_tokens": 4000
  }
}

// config.prod.json (90% duplicate!)
{
  "llm": {
    "model": "gpt-4",
    "temperature": 0.7,  // Same as dev!
    "max_tokens": 4000   // Same as dev!
  }
}

// ✅ GOOD: Use base config with overrides
// config.base.json
{
  "llm": {
    "model": "gpt-4",
    "temperature": 0.7,
    "max_tokens": 4000
  }
}

// config.prod.json (only overrides)
{
  "llm": {
    "temperature": 0.1  // Production needs consistency
  }
}
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

## 🧪 Testing Different Configurations

### Unit Testing Configuration

Create a test helper to safely test configurations:

```python
# tests/test_config.py
import pytest
import os
from unittest.mock import patch
from src.utils.config import ConfigManager, get_llm_config

class TestConfiguration:
    """Test configuration management"""
    
    @pytest.fixture
    def clean_environment(self):
        """Clean environment for each test"""
        # Save current env
        original_env = dict(os.environ)
        yield
        # Restore original env
        os.environ.clear()
        os.environ.update(original_env)
    
    def test_default_configuration(self, clean_environment):
        """Test loading default configuration"""
        config = get_llm_config()
        assert config.temperature == 0.1  # Default value
        assert config.max_tokens == 4000
    
    def test_environment_override(self, clean_environment):
        """Test environment variable overrides"""
        os.environ["LLM_TEMPERATURE"] = "0.5"
        os.environ["LLM_MAX_TOKENS"] = "2000"
        
        config = get_llm_config()
        assert config.temperature == 0.5  # Overridden
        assert config.max_tokens == 2000  # Overridden
    
    def test_invalid_configuration(self, clean_environment):
        """Test configuration validation"""
        os.environ["LLM_TEMPERATURE"] = "2.0"  # Invalid: > 1.0
        
        with pytest.raises(ValueError) as exc:
            config = get_llm_config()
            config.validate()
        
        assert "temperature must be <= 1.0" in str(exc.value)
    
    @patch('builtins.open', side_effect=FileNotFoundError)
    def test_missing_config_file(self, mock_open, clean_environment):
        """Test behavior when config file is missing"""
        config_manager = ConfigManager()
        config = config_manager.load_config("nonexistent.json")
        
        # Should use defaults
        assert config["llm"]["temperature"] == 0.1
```

### Integration Testing with Different Configs

```python
# tests/test_integration_config.py
import pytest
import tempfile
import json
from src.orchestrator.main import create_orchestrator

class TestConfigurationIntegration:
    """Test system behavior with different configurations"""
    
    @pytest.fixture
    def temp_config_file(self):
        """Create temporary config file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            yield f
    
    def test_development_configuration(self, temp_config_file):
        """Test with development settings"""
        dev_config = {
            "environment": "development",
            "debug": True,
            "llm": {
                "temperature": 0.7,  # More creative in dev
                "timeout": 30  # Shorter timeout for faster iteration
            }
        }
        
        json.dump(dev_config, temp_config_file)
        temp_config_file.flush()
        
        orchestrator = create_orchestrator(config_path=temp_config_file.name)
        assert orchestrator.config.debug is True
        assert orchestrator.llm.temperature == 0.7
    
    def test_production_configuration(self, temp_config_file):
        """Test with production settings"""
        prod_config = {
            "environment": "production",
            "debug": False,
            "llm": {
                "temperature": 0.1,  # Consistent in production
                "timeout": 120,  # Longer timeout for reliability
                "retry_attempts": 5  # More retries in production
            }
        }
        
        json.dump(prod_config, temp_config_file)
        temp_config_file.flush()
        
        orchestrator = create_orchestrator(config_path=temp_config_file.name)
        assert orchestrator.config.debug is False
        assert orchestrator.llm.temperature == 0.1
        assert orchestrator.llm.retry_attempts == 5
```

### Testing Configuration Changes

```python
# tests/test_config_changes.py
def test_configuration_reload():
    """Test dynamic configuration reloading"""
    # Initial config
    config_manager = ConfigManager()
    initial_config = config_manager.get_llm_config()
    assert initial_config.temperature == 0.1
    
    # Simulate config file change
    new_config = {
        "llm": {
            "temperature": 0.3
        }
    }
    
    with patch('builtins.open', mock_open(read_data=json.dumps(new_config))):
        config_manager.reload_config()
    
    # Verify new config is loaded
    updated_config = config_manager.get_llm_config()
    assert updated_config.temperature == 0.3
```

## 🌍 Configuration for Different Environments

### Development Environment

```json
// config.dev.json
{
  "environment": "development",
  "debug": true,  // Enable detailed logging
  "llm": {
    "temperature": 0.7,  // More creative responses
    "timeout": 30,  // Fail fast during development
    "retry_attempts": 1  // Don't waste time retrying
  },
  "database": {
    "path": "./dev_memory.db",  // Separate dev database
    "wal_mode": false  // Simpler for development
  },
  "logging": {
    "level": "DEBUG",  // See everything
    "format": "plain"  // Easier to read
  }
}
```

```bash
# .env.development
ENVIRONMENT=development
DEBUG_MODE=true
AZURE_OPENAI_ENDPOINT=https://dev.openai.azure.com/
DATABASE_PATH=./dev_memory.db
LOG_LEVEL=DEBUG
```

### Staging Environment

```json
// config.staging.json
{
  "environment": "staging",
  "debug": false,  // Production-like
  "llm": {
    "temperature": 0.1,  // Match production behavior
    "timeout": 60,  // Balance between dev and prod
    "retry_attempts": 3
  },
  "database": {
    "path": "./staging_memory.db",
    "wal_mode": true,  // Test production features
    "pool_size": 10  // Smaller than production
  },
  "logging": {
    "level": "INFO",
    "format": "json"  // Structured logging like prod
  }
}
```

```bash
# .env.staging
ENVIRONMENT=staging
DEBUG_MODE=false
AZURE_OPENAI_ENDPOINT=https://staging.openai.azure.com/
DATABASE_PATH=./staging_memory.db
LOG_LEVEL=INFO
# Use staging API keys
AZURE_OPENAI_API_KEY=${STAGING_AZURE_KEY}
```

### Production Environment

```json
// config.prod.json
{
  "environment": "production",
  "debug": false,
  "llm": {
    "temperature": 0.1,  // Consistent, reliable responses
    "timeout": 120,  // Allow time for complex operations
    "retry_attempts": 5,  // High availability
    "max_tokens": 4000
  },
  "database": {
    "path": "/data/memory_store.db",  // Persistent volume
    "wal_mode": true,  // Better concurrency
    "pool_size": 50,  // Handle high load
    "backup_enabled": true  // Regular backups
  },
  "logging": {
    "level": "WARNING",  // Only important stuff
    "format": "json",
    "file_rotation": true,
    "max_file_size": "1GB",
    "backup_count": 10
  },
  "monitoring": {
    "enabled": true,
    "apm_endpoint": "https://monitoring.company.com"
  }
}
```

```bash
# Production deployment (Kubernetes example)
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  ENVIRONMENT: "production"
  LOG_LEVEL: "WARNING"
  DATABASE_PATH: "/data/memory_store.db"
---
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
type: Opaque
data:
  AZURE_OPENAI_API_KEY: <base64-encoded-key>
  SFDC_PASS: <base64-encoded-password>
```

### Environment-Specific Code

```python
# src/utils/environment.py
import os
from enum import Enum

class Environment(Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    
    @classmethod
    def current(cls):
        """Get current environment"""
        env_name = os.environ.get("ENVIRONMENT", "development").lower()
        try:
            return cls(env_name)
        except ValueError:
            logger.warning(f"Unknown environment: {env_name}, defaulting to development")
            return cls.DEVELOPMENT
    
    def is_production(self):
        return self == Environment.PRODUCTION
    
    def is_development(self):
        return self == Environment.DEVELOPMENT

# Use in code
from src.utils.environment import Environment

env = Environment.current()

if env.is_production():
    # Production-specific behavior
    setup_monitoring()
    enable_rate_limiting()
    configure_backups()
elif env.is_development():
    # Development helpers
    enable_debug_endpoints()
    disable_rate_limiting()
```

### Configuration Checklist for Each Environment

#### Development Checklist
- [ ] Use `.env` file for local secrets
- [ ] Enable debug logging
- [ ] Use shorter timeouts for faster feedback
- [ ] Point to local/dev services
- [ ] Disable rate limiting
- [ ] Use test API keys

#### Staging Checklist
- [ ] Mirror production configuration
- [ ] Use staging API endpoints
- [ ] Enable structured logging
- [ ] Test with production-like data volumes
- [ ] Verify backup procedures
- [ ] Test configuration reloading

#### Production Checklist
- [ ] All secrets in secure vault
- [ ] Monitoring and alerting configured
- [ ] Backup strategy implemented
- [ ] Rate limiting enabled
- [ ] Circuit breakers configured
- [ ] Log rotation set up
- [ ] Configuration validation on deploy
- [ ] Rollback plan ready

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

## 🎓 Summary for Junior Engineers

### Key Takeaways

1. **Configuration Management Saves Companies**: Poor configuration has literally bankrupted companies and caused massive outages. Take it seriously!

2. **Three Layers Rule**:
   - Hardcoded = Universal constants
   - Config Files = Environment-specific settings
   - Environment Variables = Secrets and overrides

3. **Never Commit Secrets**: If you accidentally commit a secret, assume it's compromised and rotate it immediately.

4. **Test Your Configurations**: Configuration bugs are just as dangerous as code bugs. Test them!

5. **Environment Parity**: Keep dev, staging, and production as similar as possible, with only necessary differences.

6. **Fail Fast**: If configuration is invalid, fail immediately with a clear error rather than limping along with defaults.

7. **Document Everything**: Every configuration option should have a comment explaining what it does and valid values.

### Quick Reference Card

```bash
# Adding a new config option? Follow this checklist:
□ 1. Add constant to src/utils/constants.py
□ 2. Add to system_config.json with default
□ 3. Add to config dataclass with validation
□ 4. Add environment variable mapping
□ 5. Use get_xxx_config() to access
□ 6. Add to .env.example with documentation
□ 7. Write tests for default and override cases
□ 8. Update this documentation

# Debugging configuration issues:
□ 1. Check if environment variable is set: echo $VAR_NAME
□ 2. Check if config file exists and is valid JSON
□ 3. Enable debug logging to see what's loaded
□ 4. Use config validation to catch errors early
□ 5. Check logs for configuration warnings

# Security checklist:
□ 1. No secrets in code
□ 2. No secrets in config files
□ 3. Use .gitignore for .env files
□ 4. Rotate secrets regularly
□ 5. Use secret managers in production
□ 6. Audit configuration access
```

### Remember

> "Configuration is code. Treat it with the same respect, testing, and review process. A bad configuration change can bring down your system just as effectively as a bad code change." - A wise senior engineer

Good configuration management is invisible when done right, but catastrophic when done wrong. Make it a habit to think about configuration early and often in your development process.