"""Configuration for PostgreSQL memory storage."""

import os

# PostgreSQL connection configuration
POSTGRES_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'database': os.getenv('POSTGRES_DB', 'consultant_assistant'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', ''),
    
    # Connection pool settings
    'pool_size': int(os.getenv('POSTGRES_POOL_SIZE', '20')),
    'pool_min_size': int(os.getenv('POSTGRES_POOL_MIN_SIZE', '2')),
    'command_timeout': int(os.getenv('POSTGRES_COMMAND_TIMEOUT', '60')),
    
    # Memory-specific settings
    'memory_schema': 'memory',
    'enable_ssl': os.getenv('POSTGRES_SSL', 'false').lower() == 'true',
}


def get_connection_string() -> str:
    """Build PostgreSQL connection string from config."""
    config = POSTGRES_CONFIG
    
    # Build base connection string
    conn_str = f"postgresql://{config['user']}"
    
    if config['password']:
        conn_str += f":{config['password']}"
    
    conn_str += f"@{config['host']}:{config['port']}/{config['database']}"
    
    # Add SSL if enabled
    if config['enable_ssl']:
        conn_str += "?sslmode=require"
    
    return conn_str


def get_async_connection_params() -> dict:
    """Get connection parameters for asyncpg."""
    config = POSTGRES_CONFIG
    
    params = {
        'host': config['host'],
        'port': config['port'],
        'database': config['database'],
        'user': config['user'],
        'min_size': config['pool_min_size'],
        'max_size': config['pool_size'],
        'command_timeout': config['command_timeout'],
    }
    
    if config['password']:
        params['password'] = config['password']
    
    if config['enable_ssl']:
        params['ssl'] = 'require'
    
    return params