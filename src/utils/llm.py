"""Centralized LLM utilities for the multi-agent orchestrator system"""

import os
from typing import Optional, Dict, Any, Callable, Dict, Any, List
from langchain_openai import AzureChatOpenAI
from src.utils.config.unified_config import config as app_config
from src.utils.logging.framework import SmartLogger

logger = SmartLogger("system")


def create_azure_openai_chat(**kwargs) -> AzureChatOpenAI:
    """Create Azure OpenAI chat instance using global config.
    
    Args:
        **kwargs: Optional overrides for LLM configuration
        
    Returns:
        Configured AzureChatOpenAI instance
    """
    # Build base configuration from global config
    llm_kwargs: Dict[str, Any] = {
        "azure_endpoint": os.environ.get("AZURE_OPENAI_ENDPOINT"),
        "azure_deployment": app_config.get_secret("azure_openai_deployment", required=False) or os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"),
        "openai_api_version": app_config.get_secret("azure_openai_api_version", required=False) or os.environ.get("AZURE_OPENAI_API_VERSION"),
        "openai_api_key": os.environ.get("AZURE_OPENAI_API_KEY"),
        "temperature": app_config.llm_temperature,
        "max_tokens": app_config.llm_max_tokens,
        "timeout": app_config.llm_timeout,
    }
    
    # Add optional top_p if configured
    top_p = app_config.get('llm.top_p')
    if top_p is not None:
        llm_kwargs["top_p"] = top_p
    
    # Apply any overrides
    llm_kwargs.update(kwargs)
    
    # Validate required environment variables
    if not llm_kwargs.get("azure_endpoint"):
        raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is required")
    if not llm_kwargs.get("openai_api_key"):
        raise ValueError("AZURE_OPENAI_API_KEY environment variable is required")
    
    logger.info("creating_llm_instance",
                deployment=llm_kwargs.get("azure_deployment"),
                temperature=llm_kwargs.get("temperature"),
                max_tokens=llm_kwargs.get("max_tokens"))
    
    return AzureChatOpenAI(**llm_kwargs)


def create_streaming_llm(**kwargs) -> AzureChatOpenAI:
    """Create Azure OpenAI chat instance configured for streaming.
    
    Args:
        **kwargs: Optional overrides for LLM configuration
        
    Returns:
        Configured AzureChatOpenAI instance with streaming enabled
    """
    # Enable streaming by default
    streaming_kwargs: Dict[str, Any] = {"streaming": True}
    streaming_kwargs.update(kwargs)
    
    return create_azure_openai_chat(**streaming_kwargs)


def create_low_temp_llm(**kwargs) -> AzureChatOpenAI:
    """Create Azure OpenAI chat instance with low temperature for deterministic outputs.
    
    Useful for structured data extraction, tool selection, and other tasks
    requiring consistent outputs.
    
    Args:
        **kwargs: Optional overrides for LLM configuration
        
    Returns:
        Configured AzureChatOpenAI instance with temperature=0
    """
    low_temp_kwargs: Dict[str, Any] = {"temperature": 0}
    low_temp_kwargs.update(kwargs)
    
    return create_azure_openai_chat(**low_temp_kwargs)



def create_deterministic_llm(**kwargs) -> AzureChatOpenAI:
    """Create Azure OpenAI chat instance for deterministic outputs.
    
    Uses temperature=0 and top_p=0.1 for maximum consistency.
    Ideal for structured data extraction and classification tasks.
    
    Args:
        **kwargs: Optional overrides for LLM configuration
        
    Returns:
        Configured AzureChatOpenAI instance for deterministic outputs
    """
    from src.utils.config import DETERMINISTIC_TEMPERATURE, DETERMINISTIC_TOP_P
    
    deterministic_kwargs: Dict[str, Any] = {
        "temperature": DETERMINISTIC_TEMPERATURE,
        "top_p": DETERMINISTIC_TOP_P
    }
    deterministic_kwargs.update(kwargs)
    
    return create_azure_openai_chat(**deterministic_kwargs)


def create_llm_with_tools(tools: list, **kwargs) -> Any:
    """Create Azure OpenAI chat instance with tools bound.
    
    Args:
        tools: List of tools to bind to the LLM
        **kwargs: Optional overrides for LLM configuration
        
    Returns:
        Configured AzureChatOpenAI instance with tools bound
    """
    llm = create_azure_openai_chat(**kwargs)
    return llm.bind_tools(tools)


def create_flexible_llm(tools: Optional[list] = None) -> Callable:
    """Create a flexible LLM invocation function like the orchestrator uses.
    
    Args:
        tools: Optional list of tools to bind when use_tools=True
        
    Returns:
        A function that can invoke LLM with dynamic parameters
    """
    # Create base LLMs
    base_llm = create_azure_openai_chat()
    llm_with_tools = base_llm.bind_tools(tools) if tools else base_llm
    
    def invoke_llm(messages, use_tools=False, temperature=None, top_p=None):
        """Invoke LLM with optional tool binding and generation parameters."""
        if temperature is not None or top_p is not None:
            # Create a new LLM with custom parameters
            custom_kwargs: Dict[str, Any] = {}
            if temperature is not None:
                custom_kwargs["temperature"] = temperature
            if top_p is not None:
                custom_kwargs["top_p"] = top_p
                
            temp_llm = create_azure_openai_chat(**custom_kwargs)
            if use_tools and tools:
                temp_llm = temp_llm.bind_tools(tools)
            return temp_llm.invoke(messages)
        
        if use_tools and tools:
            return llm_with_tools.invoke(messages)
        else:
            return base_llm.invoke(messages)
    
    return invoke_llm


# Export all utilities
__all__ = [
    "create_azure_openai_chat",
    "create_streaming_llm",
    "create_low_temp_llm",
    "create_deterministic_llm",
    "create_llm_with_tools",
    "create_flexible_llm"
]