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
    salesforce_id: Optional[str] = Field(description="Salesforce ID if found in conversation context. Leave null if no actual ID is available. Do not generate or make up IDs.")



class ExecutionTaskStructured(BaseModel):
    """Structured task for plan generation"""
    step_number: int = Field(description="Sequential step number (1, 2, 3, etc.)", ge=1)
    description: str = Field(description="Clear, specific description of what needs to be done", min_length=15, max_length=200)
    agent: str = Field(description="Which agent should handle this task", pattern="^(salesforce|jira|servicenow|orchestrator|workflow)$")
    depends_on: Optional[List[int]] = Field(description="List of step numbers this task depends on (must be less than current step)", default=None)
    priority: Optional[str] = Field(description="Task priority", enum=["low", "medium", "high", "urgent"], default="medium")
    estimated_duration: Optional[str] = Field(description="Estimated time to complete (e.g., '5 minutes', '1 hour')", default=None)


class ExecutionPlanStructured(BaseModel):
    """Structured execution plan for orchestrator"""
    description: str = Field(description="Brief description of what this plan accomplishes", min_length=20, max_length=150)
    tasks: List[ExecutionTaskStructured] = Field(description="List of tasks in execution order", min_items=1)
    success_criteria: Optional[str] = Field(description="How to determine if the plan succeeded", default=None)
    estimated_total_time: Optional[str] = Field(description="Estimated total execution time", default=None)


class PlanModification(BaseModel):
    """Structured plan modification based on user input"""
    modification_type: str = Field(
        description="Type of modification based on user intent",
        enum=[
            "skip_to_step",      # Jump to specific step in current plan
            "skip_steps",        # Skip specific steps in current plan
            "conversation_only"  # Just talking, no plan changes needed
        ]
    )
    
    # For step navigation within current plan
    target_step_number: Optional[int] = Field(description="Target step number (1-indexed) for skip_to_step")
    steps_to_skip: Optional[List[int]] = Field(description="List of step numbers (1-indexed) to skip")
    
    # Metadata
    reasoning: str = Field(description="Clear explanation of user's intent and what modification should be applied")
    confidence: float = Field(description="Confidence in interpretation from 0.0 to 1.0", ge=0.0, le=1.0)
    user_input: str = Field(description="Original user input that triggered this modification")
    
    class Config:
        use_enum_values = True


def create_llm_instances(tools: List[Any]):
    """Create LLM instances for orchestrator use.
    
    Returns:
        tuple: (llm_with_tools, deterministic_llm, trustcall_extractor, plan_modification_extractor, plan_extractor, invoke_llm_func)
    """
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Create main LLM with tools
    llm_with_tools = create_llm_with_tools(tools)
    
    # Create deterministic LLM for memory extraction and structured planning
    deterministic_llm = create_deterministic_llm()
    
    # Configure TrustCall for memory extraction only
    trustcall_extractor = create_extractor(
        deterministic_llm,
        tools=[SimpleMemory],
        enable_inserts=True
    )
    
    # Create dedicated plan modification extractor
    plan_modification_extractor = create_extractor(
        deterministic_llm,
        tools=[PlanModification],
        enable_inserts=True
    )
    
    # Create structured plan extractor
    plan_extractor = create_extractor(
        deterministic_llm,
        tools=[ExecutionPlanStructured],
        enable_inserts=True
    )
    
    # Create flexible invocation function
    invoke_llm = create_flexible_llm(tools)
    
    return llm_with_tools, deterministic_llm, trustcall_extractor, plan_modification_extractor, plan_extractor, invoke_llm


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