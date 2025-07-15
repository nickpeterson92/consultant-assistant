"""LLM configuration and invocation handling for the orchestrator."""

from typing import Any, List, Optional

from trustcall import create_extractor
from pydantic import BaseModel, Field

from src.utils.llm import (
    create_azure_openai_chat,
    create_deterministic_llm,
    create_llm_with_tools,
    create_flexible_llm
)
from src.utils.agents.prompts import orchestrator_chatbot_sys_msg
from src.utils.storage.memory_schemas import SimpleMemory
from .state import OrchestratorState


class ExtractedEntity(BaseModel):
    """Represents a Salesforce entity found in conversation context"""
    entity_type: str = Field(description="Type of entity: account, opportunity, contact, case")
    name: str = Field(description="Human readable name of the entity")
    salesforce_id: Optional[str] = Field(description="Salesforce ID (15-18 characters starting with 001, 006, etc.)")


class InstructionEnhancement(BaseModel):
    """Enhanced instruction with resolved entity references"""
    original_instruction: str = Field(description="The original task instruction")
    enhanced_instruction: str = Field(description="Instruction with vague references replaced by specific entity details")
    entities_found: List[ExtractedEntity] = Field(description="Entities extracted from conversation context")
    changes_made: bool = Field(description="Whether any changes were made to the original instruction")
    reasoning: str = Field(description="Explanation of what changes were made and why")


def create_llm_instances(tools: List[Any]):
    """Create LLM instances for orchestrator use.
    
    Returns:
        tuple: (llm_with_tools, deterministic_llm, trustcall_extractor, invoke_llm_func)
    """
    # Create main LLM with tools
    llm_with_tools = create_llm_with_tools(tools)
    
    # Create deterministic LLM for memory extraction
    deterministic_llm = create_deterministic_llm()
    
    # Configure TrustCall for structured data extraction with multiple schemas
    trustcall_extractor = create_extractor(
        deterministic_llm,
        tools=[SimpleMemory, InstructionEnhancement],
        # No fixed tool_choice - will specify per invocation
        enable_inserts=True
    )
    
    # Create dedicated instruction enhancement extractor (single tool only)
    instruction_extractor = create_extractor(
        deterministic_llm,
        tools=[InstructionEnhancement],
        enable_inserts=True
    )
    
    # Create flexible invocation function
    invoke_llm = create_flexible_llm(tools)
    
    return llm_with_tools, deterministic_llm, trustcall_extractor, instruction_extractor, invoke_llm


def get_orchestrator_system_message(state: OrchestratorState, agent_registry) -> str:
    """Generate dynamic system message with current context."""
    summary = state.get("summary", "No summary available")
    memory_val = state.get("memory", {})
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

COMPLEX WORKFLOWS:
Complex multi-step workflows (like deal risk assessment, customer 360 reports, incident resolution) are now handled through the orchestrator's built-in plan-and-execute functionality. When users request complex workflows, the system will automatically create execution plans with todo lists that can be modified during execution."""
    
    return orchestrator_chatbot_sys_msg(summary, memory_val, agent_context)