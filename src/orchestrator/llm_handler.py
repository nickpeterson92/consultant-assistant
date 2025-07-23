"""LLM configuration and invocation handling for the orchestrator."""

import os
from typing import Any, List

from langchain_openai import AzureChatOpenAI
from trustcall import create_extractor

from src.utils.config import config, DETERMINISTIC_TEMPERATURE, DETERMINISTIC_TOP_P
from src.utils.prompt_templates import create_orchestrator_prompt, ContextInjectorOrchestrator
from src.utils.storage.memory_schemas import SimpleMemory
from .state import OrchestratorState


def create_llm_instances(tools: List[Any]):
    """Create LLM instances for orchestrator use.
    
    Returns:
        tuple: (llm_with_tools, deterministic_llm, trustcall_extractor, invoke_llm_func)
    """
    llm_config = config
    
    # Create main LLM instance
    llm_kwargs = {
        "azure_endpoint": os.environ["AZURE_OPENAI_ENDPOINT"],
        "azure_deployment": os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4o-mini"),
        "openai_api_version": os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01"),
        "openai_api_key": os.environ["AZURE_OPENAI_API_KEY"],
        "temperature": llm_config.llm_temperature,
        "max_tokens": llm_config.llm_max_tokens,
        "timeout": llm_config.llm_timeout,
    }
    if llm_config.get('llm.top_p') is not None:
        llm_kwargs["top_p"] = llm_config.get('llm.top_p')
    
    llm = AzureChatOpenAI(**llm_kwargs)
    llm_with_tools = llm.bind_tools(tools)
    
    # Create deterministic LLM for memory extraction
    deterministic_llm = AzureChatOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4o-mini"),
        openai_api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01"),
        openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
        temperature=DETERMINISTIC_TEMPERATURE,
        top_p=DETERMINISTIC_TOP_P,
        max_tokens=llm_config.llm_max_tokens,
        timeout=llm_config.llm_timeout,
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
                azure_deployment=os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4o-mini"),
                openai_api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01"),
                openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
                temperature=temperature if temperature is not None else llm_config.llm_temperature,
                max_tokens=llm_config.llm_max_tokens,
                timeout=llm_config.llm_timeout,
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
    active_agents = state.get("active_agents", [])
    
    registry_stats = agent_registry.get_registry_stats()
    
    agent_context = f"""AVAILABLE SPECIALIZED AGENTS:
{', '.join(registry_stats['available_capabilities']) if registry_stats['available_capabilities'] else 'None currently available'}

CURRENTLY ACTIVE AGENTS: {', '.join(active_agents) if active_agents else 'None'}

ORCHESTRATOR TOOLS:
1. salesforce_agent: For Salesforce CRM operations (leads, accounts, opportunities, contacts, cases, tasks, etc.)
2. jira_agent: For project management (projects, bugs, epics, stories, etc.)
3. servicenow_agent: For incident management and IT (change requests, incidents, problems, etc.)
4. manage_agents: To check agent status and capabilities
5. web_search: Search the web for information about entities, companies, people, or topics
6. human_input: Request human clarification when requests are ambiguous or need additional context"""
    
    # Create the prompt template
    orchestrator_prompt = create_orchestrator_prompt()
    
    # Prepare context using the new ContextInjectorOrchestrator
    context_dict = ContextInjectorOrchestrator.prepare_context(
        summary=summary,
        memory=None,  # Memory context is handled in plan_and_execute.py
        agent_context=agent_context
    )
    
    # Format the system message and extract it
    # Since we just need the system message content, we create a dummy message list
    from langchain_core.messages import HumanMessage
    formatted_prompt = orchestrator_prompt.format_prompt(
        messages=[HumanMessage(content="dummy")],  # Just to satisfy the template
        **context_dict
    )
    
    # Extract the system message content
    system_message = formatted_prompt.to_messages()[0]
    return system_message.content