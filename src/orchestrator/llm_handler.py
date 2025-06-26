"""LLM configuration and invocation handling for the orchestrator."""

import os
from typing import Any, List, Optional

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage
from trustcall import create_extractor

from src.utils.config import get_llm_config, DETERMINISTIC_TEMPERATURE, DETERMINISTIC_TOP_P
from src.utils.sys_msg import orchestrator_chatbot_sys_msg
from src.utils.storage.memory_schemas import SimpleMemory
from .state import OrchestratorState


def create_llm_instances(tools: List[Any]):
    """Create LLM instances for orchestrator use.
    
    Returns:
        tuple: (llm_with_tools, deterministic_llm, trustcall_extractor, invoke_llm_func)
    """
    llm_config = get_llm_config()
    
    # Create main LLM instance
    llm_kwargs = {
        "azure_endpoint": os.environ["AZURE_OPENAI_ENDPOINT"],
        "azure_deployment": llm_config.azure_deployment,
        "openai_api_version": llm_config.api_version,
        "openai_api_key": os.environ["AZURE_OPENAI_API_KEY"],
        "temperature": llm_config.temperature,
        "max_tokens": llm_config.max_tokens,
        "timeout": llm_config.timeout,
    }
    if llm_config.top_p is not None:
        llm_kwargs["top_p"] = llm_config.top_p
    
    llm = AzureChatOpenAI(**llm_kwargs)
    llm_with_tools = llm.bind_tools(tools)
    
    # Create deterministic LLM for memory extraction
    deterministic_llm = AzureChatOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=llm_config.azure_deployment,
        openai_api_version=llm_config.api_version,
        openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
        temperature=DETERMINISTIC_TEMPERATURE,
        top_p=DETERMINISTIC_TOP_P,
        max_tokens=llm_config.max_tokens,
        timeout=llm_config.timeout,
    )
    
    # Configure TrustCall for structured data extraction
    trustcall_extractor = create_extractor(
        deterministic_llm,
        tools=[SimpleMemory],
        tool_choice="SimpleMemory",
        enable_inserts=True
    )
    
    def invoke_llm(messages, use_tools=False, temperature=None, top_p=None):
        """Invoke LLM with optional tool binding and generation parameters."""
        if temperature is not None or top_p is not None:
            # Create a new LLM with custom parameters
            temp_llm = AzureChatOpenAI(
                azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                azure_deployment=llm_config.azure_deployment,
                openai_api_version=llm_config.api_version,
                openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
                temperature=temperature if temperature is not None else llm_config.temperature,
                max_tokens=llm_config.max_tokens,
                timeout=llm_config.timeout,
                top_p=top_p
            )
            if use_tools:
                temp_llm = temp_llm.bind_tools(tools)
            return temp_llm.invoke(messages)
        
        if use_tools:
            return llm_with_tools.invoke(messages)
        else:
            return llm.invoke(messages)
    
    return llm_with_tools, deterministic_llm, trustcall_extractor, invoke_llm


def get_orchestrator_system_message(state: OrchestratorState, agent_registry) -> str:
    """Generate dynamic system message with current context."""
    summary = state.get("summary", "No summary available")
    memory_val = state.get("memory", "No memory available")
    active_agents = state.get("active_agents", [])
    
    registry_stats = agent_registry.get_registry_stats()
    
    agent_context = f"""AVAILABLE SPECIALIZED AGENTS:
{', '.join(registry_stats['available_capabilities']) if registry_stats['available_capabilities'] else 'None currently available'}

CURRENTLY ACTIVE AGENTS: {', '.join(active_agents) if active_agents else 'None'}

ORCHESTRATOR TOOLS:
1. salesforce_agent: For Salesforce CRM operations (leads, accounts, opportunities, contacts, cases, tasks)
2. call_agent: For general agent calls (travel, expenses, HR, OCR, etc.)
3. manage_agents: To check agent status and capabilities"""
    
    return orchestrator_chatbot_sys_msg(summary, memory_val, agent_context)