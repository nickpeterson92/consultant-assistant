"""Simplified plan-execute state for domain-specific agents."""

from typing import Dict, Any, List, Optional, Literal, Annotated
from typing_extensions import TypedDict
from dataclasses import dataclass, field
from datetime import datetime
from langgraph.graph.message import add_messages


# Agent execution status types
AgentTaskStatus = Literal["pending", "executing", "completed", "failed", "skipped"]
AgentPlanStatus = Literal["draft", "executing", "completed", "failed", "replanning"]


@dataclass
class AgentTask:
    """A single task in an agent's execution plan."""
    id: str
    description: str
    tool_name: str
    tool_args: Dict[str, Any]
    status: AgentTaskStatus = "pending"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 2
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.retry_count < self.max_retries

    def mark_failed(self, error: str) -> None:
        """Mark task as failed with error."""
        self.status = "failed"
        self.error = error
        self.completed_at = datetime.now().isoformat()

    def mark_completed(self, result: Dict[str, Any]) -> None:
        """Mark task as completed with result."""
        self.status = "completed"
        self.result = result
        self.completed_at = datetime.now().isoformat()


@dataclass
class AgentPlan:
    """Simplified execution plan for domain agents."""
    id: str
    description: str
    tasks: List[AgentTask]
    status: AgentPlanStatus = "draft"
    current_task_index: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    replan_count: int = 0
    max_replans: int = 3

    def get_current_task(self) -> Optional[AgentTask]:
        """Get the current task to execute."""
        if 0 <= self.current_task_index < len(self.tasks):
            return self.tasks[self.current_task_index]
        return None

    def advance_to_next_task(self) -> bool:
        """Move to next task. Returns True if more tasks available."""
        self.current_task_index += 1
        return self.current_task_index < len(self.tasks)

    def has_more_tasks(self) -> bool:
        """Check if there are more tasks to execute."""
        return self.current_task_index < len(self.tasks)

    def get_failed_tasks(self) -> List[AgentTask]:
        """Get all failed tasks."""
        return [task for task in self.tasks if task.status == "failed"]

    def get_completed_tasks(self) -> List[AgentTask]:
        """Get all completed tasks."""
        return [task for task in self.tasks if task.status == "completed"]

    def is_complete(self) -> bool:
        """Check if plan execution is complete."""
        return not self.has_more_tasks() and self.status in ["completed", "failed"]

    def can_replan(self) -> bool:
        """Check if plan can be replanned."""
        return self.replan_count < self.max_replans

    def mark_for_replan(self) -> None:
        """Mark plan for replanning."""
        self.status = "replanning"
        self.replan_count += 1


class AgentPlanExecuteState(TypedDict):
    """State for simplified agent plan-execute pattern."""
    # Core LangGraph state
    messages: Annotated[List[Any], add_messages]
    
    # Plan execution state
    plan: Optional[AgentPlan]
    current_task: Optional[AgentTask]
    
    # Context and configuration
    original_request: str
    task_context: Dict[str, Any]
    external_context: Dict[str, Any]
    
    # Agent-specific data
    agent_name: str
    tools_available: List[str]
    
    # Execution tracking
    execution_started: bool
    execution_completed: bool
    final_response: Optional[str]
    
    # Error handling
    last_error: Optional[str]
    should_replan: bool
    replan_reason: Optional[str]


# Helper functions for state management
def create_agent_task(task_id: str, description: str, tool_name: str, tool_args: Dict[str, Any]) -> AgentTask:
    """Create a new agent task."""
    return AgentTask(
        id=task_id,
        description=description,
        tool_name=tool_name,
        tool_args=tool_args
    )


def create_agent_plan(plan_id: str, description: str, tasks: List[AgentTask]) -> AgentPlan:
    """Create a new agent plan."""
    return AgentPlan(
        id=plan_id,
        description=description,
        tasks=tasks
    )


def create_initial_agent_state(
    original_request: str,
    agent_name: str,
    tools_available: List[str],
    task_context: Optional[Dict[str, Any]] = None,
    external_context: Optional[Dict[str, Any]] = None
) -> AgentPlanExecuteState:
    """Create initial state for agent plan-execute graph."""
    return AgentPlanExecuteState(
        messages=[],
        plan=None,
        current_task=None,
        original_request=original_request,
        task_context=task_context or {},
        external_context=external_context or {},
        agent_name=agent_name,
        tools_available=tools_available,
        execution_started=False,
        execution_completed=False,
        final_response=None,
        last_error=None,
        should_replan=False,
        replan_reason=None
    )


def update_agent_execution_state(
    state: AgentPlanExecuteState,
    **updates
) -> AgentPlanExecuteState:
    """Update agent execution state with new values."""
    updated_state = state.copy()
    updated_state.update(updates)
    return updated_state