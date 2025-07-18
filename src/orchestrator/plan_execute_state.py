"""Pure plan-and-execute state schema for LangGraph orchestrator."""

from typing import Annotated, Dict, Any, List, Optional, Literal, Union
from typing_extensions import TypedDict
from datetime import datetime
from enum import Enum

from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

from src.utils.logging.framework import SmartLogger

logger = SmartLogger("orchestrator")


class PlanStatus(Enum):
    """Status of the overall plan execution."""
    PLANNING = "planning"
    EXECUTING = "executing" 
    PAUSED = "paused"
    INTERRUPTED = "interrupted"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(Enum):
    """Status of individual tasks."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Priority levels for tasks."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class InterruptType(Enum):
    """Types of interrupts that can occur."""
    USER_ESCAPE = "user_escape"
    PLAN_MODIFICATION = "plan_modification"
    APPROVAL_REQUEST = "approval_request"
    ERROR_RECOVERY = "error_recovery"
    MANUAL_PAUSE = "manual_pause"


class ExecutionTask(TypedDict):
    """Individual task in the execution plan."""
    id: str
    content: str
    description: Optional[str]  # Detailed description if needed
    status: Literal["pending", "in_progress", "completed", "failed", "skipped", "cancelled"]
    priority: Literal["low", "medium", "high", "urgent"]
    agent: Optional[str]  # Which agent should handle this task (salesforce, jira, servicenow)
    depends_on: List[str]  # Task IDs this task depends on
    created_at: str  # ISO timestamp
    started_at: Optional[str]  # ISO timestamp
    completed_at: Optional[str]  # ISO timestamp
    result: Optional[Dict[str, Any]]  # Task execution result
    error: Optional[str]  # Error message if task failed
    retry_count: int  # Number of retries attempted
    max_retries: int  # Maximum number of retries allowed


class ExecutionPlan(TypedDict):
    """Complete execution plan with tasks and metadata."""
    id: str
    original_request: str
    description: Optional[str]  # Human-readable plan description
    tasks: List[ExecutionTask]
    status: Literal["planning", "executing", "paused", "interrupted", "completed", "failed", "cancelled"]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    metadata: Dict[str, Any]
    version: int  # For plan versioning during modifications


class ProgressState(TypedDict):
    """Real-time progress tracking for UI coordination."""
    current_step: Optional[str]  # "Step 3/7: Getting account details..."
    completed_steps: List[str]  # Task contents for completed tasks
    failed_steps: List[str]  # Task contents for failed tasks
    total_steps: int
    progress_percent: float  # 0.0 to 1.0
    last_updated: str  # ISO timestamp


class InterruptData(TypedDict):
    """Data structure for handling interrupts and human-in-the-loop."""
    interrupt_type: Literal["user_escape", "plan_modification", "approval_request", "error_recovery", "manual_pause"]
    reason: str
    context: Dict[str, Any]  # Additional context for the interrupt
    user_input: Optional[str]  # User input that triggered the interrupt
    pending_approval: Optional[Dict[str, Any]]  # Data waiting for approval
    created_at: str
    resolved_at: Optional[str]


class PlanExecuteState(TypedDict):
    """Pure plan-and-execute state schema for LangGraph orchestrator."""
    
    # Core messaging
    messages: Annotated[List[BaseMessage], add_messages]
    original_request: str
    
    # Plan management
    plan: Optional[ExecutionPlan]
    current_task_index: int
    skipped_task_indices: List[int]  # 0-indexed task positions to skip
    plan_history: List[ExecutionPlan]  # For versioning/rollback
    
    # Task execution
    task_results: Dict[str, Any]  # task_id -> result data
    execution_context: Dict[str, Any]  # Shared context between tasks
    agent_context: Dict[str, Any]  # Context for agent routing
    
    # Interrupt and human-in-the-loop
    interrupted: bool
    interrupt_data: Optional[InterruptData]
    approval_pending: bool
    plan_modification_applied: Optional[Dict[str, Any]]  # Last modification for debugging
    
    # Real-time UI coordination (replaces progress_state.py)
    progress_state: ProgressState
    ui_mode: Literal["simple", "progressive"]  # Simple spinner vs step-by-step
    
    # Memory and background operations (preserved from original)
    summary: str
    memory: Dict[str, Any]
    tool_calls_since_memory: int
    agent_calls_since_memory: int
    
    # Agent management
    active_agents: List[str]
    last_agent_interaction: Dict[str, Any]
    
    # Configuration
    config: Dict[str, Any]  # Runtime configuration


def create_new_plan(original_request: str, plan_id: Optional[str] = None) -> ExecutionPlan:
    """Create a new execution plan."""
    from uuid import uuid4
    
    if plan_id is None:
        plan_id = str(uuid4())
    
    return ExecutionPlan(
        id=plan_id,
        original_request=original_request,
        description=None,
        tasks=[],
        status=PlanStatus.PLANNING.value,
        created_at=datetime.now().isoformat(),
        started_at=None,
        completed_at=None,
        metadata={},
        version=1
    )


def create_new_task(content: str, 
                   priority: str = "medium",
                   agent: Optional[str] = None,
                   depends_on: Optional[List[str]] = None) -> ExecutionTask:
    """Create a new execution task."""
    from uuid import uuid4
    
    return ExecutionTask(
        id=str(uuid4()),
        content=content,
        description=None,
        status=TaskStatus.PENDING.value,
        priority=priority,
        agent=agent,
        depends_on=depends_on or [],
        created_at=datetime.now().isoformat(),
        started_at=None,
        completed_at=None,
        result=None,
        error=None,
        retry_count=0,
        max_retries=3
    )


def create_initial_state(original_request: str) -> PlanExecuteState:
    """Create initial state for plan-and-execute graph."""
    return PlanExecuteState(
        messages=[],
        original_request=original_request,
        plan=None,
        current_task_index=0,
        skipped_task_indices=[],
        plan_history=[],
        task_results={},
        execution_context={},
        agent_context={},
        interrupted=False,
        interrupt_data=None,
        approval_pending=False,
        plan_modification_applied=None,
        progress_state=ProgressState(
            current_step=None,
            completed_steps=[],
            failed_steps=[],
            total_steps=0,
            progress_percent=0.0,
            last_updated=datetime.now().isoformat()
        ),
        ui_mode="simple",
        summary="",
        memory={},
        tool_calls_since_memory=0,
        agent_calls_since_memory=0,
        active_agents=[],
        last_agent_interaction={},
        config={}
    )


def get_current_task(state: PlanExecuteState) -> Optional[ExecutionTask]:
    """Get the current task being executed."""
    if not state["plan"] or not state["plan"]["tasks"]:
        return None
    
    current_index = state["current_task_index"]
    tasks = state["plan"]["tasks"]
    
    if 0 <= current_index < len(tasks):
        return tasks[current_index]
    
    return None


def get_next_executable_task(state: PlanExecuteState) -> Optional[ExecutionTask]:
    """Get the next task that can be executed (dependencies satisfied).
    
    Respects plan modifications:
    - current_task_index: starts search from this position
    - skipped_task_indices: marks these tasks as skipped
    """
    print("🚨 DEBUG: get_next_executable_task called!")  # Simple debug print
    
    if not state["plan"] or not state["plan"]["tasks"]:
        return None
    
    tasks = state["plan"]["tasks"]
    
    # Log plan modification state for debugging
    from src.utils.logging.multi_file_logger import StructuredLogger
    logger = StructuredLogger()
    
    current_task_index = state.get("current_task_index", 0)
    skipped_indices = state.get("skipped_task_indices", [])
    
    print(f"🔍 DEBUG: current_task_index={current_task_index}, skipped_indices={skipped_indices}")
    print(f"🔍 DEBUG: total_tasks={len(tasks)}, task_statuses={[t['status'] for t in tasks]}")
    print(f"🔍 DEBUG: plan_modification_applied={state.get('plan_modification_applied')}")
    
    logger.info("get_next_executable_task_called",
               component="orchestrator",
               current_task_index=current_task_index,
               skipped_indices=skipped_indices,
               total_tasks=len(tasks),
               task_statuses=[t["status"] for t in tasks])
    
    # Handle skipped tasks - mark them as skipped if they're still pending
    for i in skipped_indices:
        if i < len(tasks) and tasks[i]["status"] == TaskStatus.PENDING.value:
            tasks[i]["status"] = TaskStatus.SKIPPED.value
            logger.info("task_marked_as_skipped",
                       component="orchestrator",
                       task_index=i,
                       task_id=tasks[i]["id"],
                       task_content=tasks[i]["content"][:100])
    
    # Get completed and skipped task IDs (both satisfy dependencies)
    satisfied_task_ids = {
        task["id"] for task in tasks
        if task["status"] in [TaskStatus.COMPLETED.value, TaskStatus.SKIPPED.value]
    }
    
    # Find the next executable task starting from current_task_index
    for i in range(current_task_index, len(tasks)):
        task = tasks[i]
        if task["status"] == TaskStatus.PENDING.value:
            # Check if all dependencies are satisfied
            unmet_deps = [dep for dep in task["depends_on"] if dep not in satisfied_task_ids]
            if not unmet_deps:
                # Update current_task_index to this position
                state["current_task_index"] = i
                logger.info("next_executable_task_selected",
                           component="orchestrator",
                           selected_task_index=i,
                           task_id=task["id"],
                           task_content=task["content"][:100],
                           started_from_index=current_task_index)
                return task
    
    # If no tasks found from current_task_index onwards, check earlier tasks
    # (in case of dependency issues or complex modification scenarios)
    for i in range(0, current_task_index):
        task = tasks[i]
        if task["status"] == TaskStatus.PENDING.value:
            # Check if all dependencies are satisfied
            unmet_deps = [dep for dep in task["depends_on"] if dep not in satisfied_task_ids]
            if not unmet_deps:
                state["current_task_index"] = i
                logger.info("next_executable_task_selected_fallback",
                           component="orchestrator",
                           selected_task_index=i,
                           task_id=task["id"],
                           task_content=task["content"][:100],
                           original_start_index=current_task_index)
                return task
    
    logger.info("no_executable_task_found",
               component="orchestrator",
               current_task_index=current_task_index,
               total_tasks=len(tasks))
    return None


def update_progress_state(state: PlanExecuteState) -> ProgressState:
    """Update progress state based on current plan execution."""
    if not state["plan"]:
        return state["progress_state"]
    
    plan = state["plan"]
    total_tasks = len(plan["tasks"])
    completed_tasks = [t for t in plan["tasks"] if t["status"] == TaskStatus.COMPLETED.value]
    failed_tasks = [t for t in plan["tasks"] if t["status"] == TaskStatus.FAILED.value]
    
    current_task = get_current_task(state)
    current_step = None
    if current_task:
        step_num = len(completed_tasks) + 1
        current_step = f"Step {step_num}/{total_tasks}: {current_task['content']}"
    
    progress_percent = len(completed_tasks) / total_tasks if total_tasks > 0 else 0.0
    
    return ProgressState(
        current_step=current_step,
        completed_steps=[t["content"] for t in completed_tasks],
        failed_steps=[t["content"] for t in failed_tasks],
        total_steps=total_tasks,
        progress_percent=progress_percent,
        last_updated=datetime.now().isoformat()
    )


def is_plan_complete(state: PlanExecuteState) -> bool:
    """Check if the current plan is complete (all tasks done)."""
    if not state["plan"]:
        return False
    
    for task in state["plan"]["tasks"]:
        if task["status"] in [TaskStatus.PENDING.value, TaskStatus.IN_PROGRESS.value]:
            return False
    
    return True


def get_plan_summary(plan: ExecutionPlan) -> str:
    """Generate a human-readable summary of the plan."""
    if not plan or not plan["tasks"]:
        return "No tasks in plan"
    
    total = len(plan["tasks"])
    completed = sum(1 for t in plan["tasks"] if t["status"] == TaskStatus.COMPLETED.value)
    failed = sum(1 for t in plan["tasks"] if t["status"] == TaskStatus.FAILED.value)
    pending = total - completed - failed
    
    return f"Plan Status: {completed} completed, {failed} failed, {pending} pending ({total} total)"