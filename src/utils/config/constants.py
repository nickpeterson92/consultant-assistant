"""
Central constants file for the Multi-Agent Orchestrator system.

This module defines all shared constants to avoid string duplication
and provide a single source of truth for configuration keys, 
component names, and other repeated values.
"""

# ASCII Art Banner
ENTERPRISE_ASSISTANT_BANNER = """
███████╗███╗   ██╗████████╗███████╗██████╗ ██████╗ ██████╗ ██╗███████╗███████╗
██╔════╝████╗  ██║╚══██╔══╝██╔════╝██╔══██╗██╔══██╗██╔══██╗██║██╔════╝██╔════╝
█████╗  ██╔██╗ ██║   ██║   █████╗  ██████╔╝██████╔╝██████╔╝██║███████╗█████╗  
██╔══╝  ██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗██╔═══╝ ██╔══██╗██║╚════██║██╔══╝  
███████╗██║ ╚████║   ██║   ███████╗██║  ██║██║     ██║  ██║██║███████║███████╗
╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝╚═╝╚══════╝╚══════╝

 █████╗ ███████╗███████╗██╗███████╗████████╗ █████╗ ███╗   ██╗████████╗
██╔══██╗██╔════╝██╔════╝██║██╔════╝╚══██╔══╝██╔══██╗████╗  ██║╚══██╔══╝
███████║███████╗███████╗██║███████╗   ██║   ███████║██╔██╗ ██║   ██║   
██╔══██║╚════██║╚════██║██║╚════██║   ██║   ██╔══██║██║╚██╗██║   ██║   
██║  ██║███████║███████║██║███████║   ██║   ██║  ██║██║ ╚████║   ██║   
╚═╝  ╚═╝╚══════╝╚══════╝╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   
"""

# Memory and storage keys
MEMORY_NAMESPACE_PREFIX = "memory"
SIMPLE_MEMORY_KEY = "SimpleMemory"
THREAD_LIST_KEY = "thread_list"
STATE_KEY_PREFIX = "state_"

# State keys
SUMMARY_KEY = "summary"
NO_SUMMARY_TEXT = "No summary available"
CONVERSATION_SUMMARY_KEY = "conversation_summary"
USER_CONTEXT_KEY = "user_context"
MESSAGES_KEY = "messages"
MEMORY_KEY = "memory"

# Numeric constants
RECENT_MESSAGES_COUNT = 5
SUMMARY_USER_MESSAGE_THRESHOLD = 3
SUMMARY_TIME_THRESHOLD_SECONDS = 180
MEMORY_TOOL_CALL_THRESHOLD = 3
MEMORY_AGENT_CALL_THRESHOLD = 2

# Network constants
DEFAULT_A2A_PORT = 8000
SALESFORCE_AGENT_PORT = 8001
DEFAULT_HOST = "0.0.0.0"
LOCALHOST = "localhost"

# API constants
AZURE_OPENAI_API_VERSION = "2024-06-01"

# A2A Protocol status values
A2A_STATUS_PENDING = "pending"
A2A_STATUS_IN_PROGRESS = "in_progress"
A2A_STATUS_COMPLETED = "completed"
A2A_STATUS_FAILED = "failed"

# A2A Message types
A2A_MESSAGE_INSTRUCTION = "instruction"
A2A_MESSAGE_RESPONSE = "response"
A2A_MESSAGE_STATUS = "status"

# Model pricing (per 1K tokens)
MODEL_PRICING = {
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.00060},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015}
}

# Default timeout values
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_CONNECT_TIMEOUT = 30
DEFAULT_SOCKET_TIMEOUT = 30
HEALTH_CHECK_TIMEOUT = 10

# Circuit breaker defaults
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
CIRCUIT_BREAKER_TIMEOUT = 30
CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS = 3