"""Simplified orchestrator state management."""

from typing import Annotated, Dict, Any, List
import operator
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages

from src.utils.config import config
from src.utils.logging import get_smart_logger, log_execution

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
    plan_step_offset: int  # Track where current plan starts in past_steps


class OrchestratorState(TypedDict):
    """Simplified state schema for orchestrator graph."""
    messages: Annotated[list, add_messages]
    summary: str
    active_agents: List[str]
    last_agent_interaction: Dict[str, Any]