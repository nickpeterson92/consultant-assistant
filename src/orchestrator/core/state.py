"""Simplified orchestrator state management."""

from typing import Annotated, Dict, Any, List, NotRequired
import operator
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages
from langgraph.prebuilt.chat_agent_executor import AgentState

from src.utils.logging import get_smart_logger

logger = get_smart_logger("orchestrator")


class StepExecution(TypedDict):
    """Structured representation of a plan step execution."""
    step_seq_no: int              # Sequential number within the plan
    step_description: str         # The step text from the plan
    status: str                   # "pending", "executing", "completed", "failed", "skipped"
    result: str                   # The execution result (required)


class PlanExecute(TypedDict):
    """State for plan-and-execute workflow."""
    input: str
    plan: List[str]
    past_steps: Annotated[List[StepExecution], operator.add]
    response: str
    user_visible_responses: Annotated[List[str], operator.add]  # Responses that should be shown to user immediately
    messages: Annotated[List, add_messages]  # Persistent conversation history across requests
    thread_id: str  # Thread ID for memory context
    task_id: str  # Task ID for SSE event correlation
    user_id: str  # User ID for memory namespace
    plan_step_offset: int  # Track where current plan starts in past_steps


class OrchestratorState(AgentState):
    """State schema for orchestrator graph that extends AgentState.
    
    This ensures compatibility with create_react_agent's internal requirements
    while adding our custom fields.
    """
    # Additional fields beyond the base AgentState
    summary: NotRequired[str]
    active_agents: NotRequired[List[str]]
    last_agent_interaction: NotRequired[Dict[str, Any]]
    thread_id: NotRequired[str]
    task_id: NotRequired[str]
    user_id: NotRequired[str]