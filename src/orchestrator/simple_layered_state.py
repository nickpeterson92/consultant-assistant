"""Simple layered state architecture for LangGraph orchestrator.

Clean separation between public (agent-visible) and private (orchestrator-internal) state
without complex memory filtering or domain mappings.
"""

from typing import Annotated, Dict, Any, List, Optional, Literal
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

from src.utils.logging.framework import SmartLogger

logger = SmartLogger("orchestrator")


# =================================
# Public State Schema (Agent-Visible)
# =================================

class TaskContext(TypedDict):
    """Simple task context for agents."""
    current_task: str
    task_id: Optional[str]
    original_request: str


class AgentVisibleState(TypedDict):
    """Public state schema - what agents can see.
    
    This is the clean, minimal context agents receive.
    No sensitive orchestrator internals, no large memory objects.
    """
    # Core conversation
    messages: Annotated[List[BaseMessage], add_messages]
    summary: str
    
    # Current task info
    task_context: TaskContext
    
    # Simple counters for memory triggers
    tool_calls_since_memory: int
    agent_calls_since_memory: int


# =================================
# Private State Schema (Orchestrator-Internal)
# =================================

class OrchestratorPrivateState(TypedDict):
    """Private state schema - orchestrator internals only.
    
    Agents never see this. Contains plan execution details,
    interrupts, and system management state.
    """
    # Plan management
    plan: Optional[Dict[str, Any]]  # ExecutionPlan
    current_task_index: int
    skipped_task_indices: List[int]
    plan_history: List[Dict[str, Any]]
    task_results: Dict[str, Any]
    
    # Interrupt handling
    interrupted: bool
    interrupt_data: Optional[Dict[str, Any]]
    approval_pending: bool
    plan_modification_applied: Optional[Dict[str, Any]]
    
    # Agent management
    active_agents: List[str]
    last_agent_interaction: Dict[str, Any]
    agent_context: Dict[str, Any]
    
    # UI coordination
    progress_state: Dict[str, Any]
    ui_mode: Literal["simple", "progressive"]
    
    # System state
    config: Dict[str, Any]
    execution_context: Dict[str, Any]


# =================================
# Combined State Schema
# =================================

class PlanExecuteState(AgentVisibleState, OrchestratorPrivateState):
    """Complete orchestrator state combining public and private schemas.
    
    This is the full internal state used by the orchestrator graph.
    Agents only receive the AgentVisibleState portion.
    """
    # Core request tracking
    original_request: str


# =================================
# State Filtering Functions
# =================================

def create_agent_context(state: PlanExecuteState, 
                        task_content: str = "") -> AgentVisibleState:
    """Create clean agent context from orchestrator state.
    
    Args:
        state: Complete orchestrator state
        task_content: Current task description (optional override)
        
    Returns:
        Clean agent-visible state
    """
    # Extract current task info
    current_task = task_content
    task_id = None
    
    if not current_task and state.get("plan"):
        current_index = state.get("current_task_index", 0)
        tasks = state.get("plan", {}).get("tasks", [])
        
        if 0 <= current_index < len(tasks):
            current_task_obj = tasks[current_index]
            current_task = current_task_obj.get("content", "")
            task_id = current_task_obj.get("id")
    
    # Fallback to original request
    if not current_task:
        current_task = state.get("original_request", "")
    
    # Create task context
    task_context = TaskContext(
        current_task=current_task,
        task_id=task_id,
        original_request=state.get("original_request", "")
    )
    
    # Create clean agent state
    agent_state = AgentVisibleState(
        messages=state.get("messages", []),
        summary=state.get("summary", ""),
        task_context=task_context,
        tool_calls_since_memory=state.get("tool_calls_since_memory", 0),
        agent_calls_since_memory=state.get("agent_calls_since_memory", 0)
    )
    
    logger.debug("agent_context_created",
                current_task_preview=current_task[:100] if current_task else "",
                task_id=task_id,
                message_count=len(agent_state["messages"]),
                has_summary=bool(agent_state["summary"]))
    
    return agent_state


def build_agent_state_dict(state: PlanExecuteState, 
                          task_content: str = "") -> Dict[str, Any]:
    """Build agent state dictionary for tool consumption.
    
    Args:
        state: Complete orchestrator state
        task_content: Current task description
        
    Returns:
        Dictionary format expected by agent tools
    """
    agent_context = create_agent_context(state, task_content)
    
    # Convert to dict format expected by tools
    return {
        "messages": agent_context["messages"],
        "summary": agent_context["summary"],
        "task_context": agent_context["task_context"],
        "tool_calls_since_memory": agent_context["tool_calls_since_memory"],
        "agent_calls_since_memory": agent_context["agent_calls_since_memory"],
        "config": state.get("config", {})
    }


def get_state_summary(state: PlanExecuteState) -> Dict[str, Any]:
    """Get summary information about the state for monitoring."""
    plan = state.get("plan", {})
    tasks = plan.get("tasks", [])
    
    return {
        "message_count": len(state.get("messages", [])),
        "has_plan": bool(plan),
        "task_count": len(tasks),
        "current_task_index": state.get("current_task_index", 0),
        "completed_tasks": len([t for t in tasks if t.get("status") == "completed"]),
        "failed_tasks": len([t for t in tasks if t.get("status") == "failed"]),
        "interrupted": state.get("interrupted", False),
        "active_agents": state.get("active_agents", [])
    }