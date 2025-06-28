"""LLM configuration and invocation handling for the orchestrator."""

from typing import Any, List

from trustcall import create_extractor

from src.utils.llm import (
    create_azure_openai_chat,
    create_deterministic_llm,
    create_llm_with_tools,
    create_flexible_llm
)
from src.utils.agents.prompts import orchestrator_chatbot_sys_msg
from src.utils.storage.memory_schemas import SimpleMemory
from .state import OrchestratorState


def create_llm_instances(tools: List[Any]):
    """Create LLM instances for orchestrator use.
    
    Returns:
        tuple: (llm_with_tools, deterministic_llm, trustcall_extractor, invoke_llm_func)
    """
    # Create main LLM with tools
    llm_with_tools = create_llm_with_tools(tools)
    
    # Create deterministic LLM for memory extraction
    deterministic_llm = create_deterministic_llm()
    
    # Configure TrustCall for structured data extraction
    trustcall_extractor = create_extractor(
        deterministic_llm,
        tools=[SimpleMemory],
        tool_choice="SimpleMemory",
        enable_inserts=True
    )
    
    # Create flexible invocation function
    invoke_llm = create_flexible_llm(tools)
    
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
1. salesforce_agent: For Salesforce CRM operations (leads, accounts, opportunities, contacts, cases, tasks, etc.)
2. jira_agent: For project management (projects, bugs, epics, stories, etc.)
3. servicenow_agent: For incident management and IT (change requests, incidents, problems, etc.)
4. workflow_agent: For complex multi-step workflows (at-risk deals, customer 360, incident resolution, etc.)
5. manage_agents: To check agent status and capabilities
6. web_search: Search the web for information about entities, companies, people, or topics

WORKFLOW CAPABILITIES:
- Deal Risk Assessment: Use workflow_agent for "check at-risk deals" or "analyze deal risks"
- Customer 360 Report: Use workflow_agent for comprehensive customer information across all systems
- Incident to Resolution: Use workflow_agent for end-to-end incident management workflows
- Account Health Check: Use workflow_agent for analyzing key account health metrics
- New Customer Onboarding: Use workflow_agent for automated customer setup across systems"""
    
    return orchestrator_chatbot_sys_msg(summary, memory_val, agent_context)