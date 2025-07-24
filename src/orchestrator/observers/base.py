"""Base classes and event definitions for observer pattern.

This module provides the foundation for observing plan-execute workflow events
without coupling business logic to UX concerns.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Any, Dict
from dataclasses import dataclass, field


@dataclass
class WorkflowEvent:
    """Base class for workflow events."""
    step_name: str
    task_id: Optional[str] = None
    timestamp: Optional[str] = None


@dataclass
class SearchResultsEvent(WorkflowEvent):
    """Event fired when search tools produce results that users might need to see."""
    results: str = ""
    tool_name: str = ""
    is_user_selectable: bool = True  # Results that users might need to select from


@dataclass
class HumanInputRequestedEvent(WorkflowEvent):
    """Event fired when human input is needed."""
    question: str = ""
    context: Optional[str] = None


@dataclass
class PlanStepEvent(WorkflowEvent):
    """Event fired when plan steps are created or updated."""
    plan_steps: List[str] = field(default_factory=list)
    completed_steps: List[str] = field(default_factory=list)
    failed_steps: List[str] = field(default_factory=list)
    current_step: Optional[str] = None


@dataclass  
class PlanCreatedEvent(WorkflowEvent):
    """Event fired when a new plan is created."""
    plan_steps: List[str] = field(default_factory=list)
    total_steps: int = 0


@dataclass
class TaskStartedEvent(WorkflowEvent):
    """Event fired when a task/step begins execution."""
    task_description: str = ""
    step_number: int = 0
    total_steps: int = 0


@dataclass
class TaskCompletedEvent(WorkflowEvent):
    """Event fired when a task/step completes execution."""
    task_description: str = ""
    step_number: int = 0
    total_steps: int = 0
    success: bool = True
    result: Optional[str] = None


@dataclass
class PlanModifiedEvent(WorkflowEvent):
    """Event fired when plan structure changes (steps added/removed/reordered)."""
    plan_steps: List[str] = field(default_factory=list)
    modification_type: str = ""  # "add", "remove", "reorder", "replace"
    details: Optional[str] = None


@dataclass
class PlanUpdatedEvent(WorkflowEvent):
    """Event fired with full plan status update."""
    plan_steps: List[str] = field(default_factory=list)
    completed_steps: List[str] = field(default_factory=list)
    failed_steps: List[str] = field(default_factory=list)
    current_step: Optional[str] = None
    total_steps: int = 0
    completed_count: int = 0
    failed_count: int = 0


@dataclass
class MemoryNodeAddedEvent(WorkflowEvent):
    """Event fired when a node is added to the memory graph."""
    node_id: str = ""
    node_data: Dict[str, Any] = field(default_factory=dict)
    thread_id: str = ""


@dataclass
class MemoryEdgeAddedEvent(WorkflowEvent):
    """Event fired when an edge is added between memory nodes."""
    edge_data: Dict[str, Any] = field(default_factory=dict)
    thread_id: str = ""


@dataclass
class MemoryGraphSnapshotEvent(WorkflowEvent):
    """Event fired with a full snapshot of the memory graph."""
    graph_data: Dict[str, Any] = field(default_factory=dict)
    thread_id: str = ""


@dataclass
class LLMContextEvent(WorkflowEvent):
    """Event fired when context is built for LLM requests."""
    context_type: str = ""  # "execution", "planning", "replanning"
    context_text: str = ""  # The actual context that will be sent
    metadata: Dict[str, Any] = field(default_factory=dict)  # Stats about the context
    full_prompt: Optional[str] = None  # The complete prompt if available
    thread_id: Optional[str] = None


class PlanExecuteObserver(ABC):
    """Abstract base class for plan-execute workflow observers."""
    
    @abstractmethod
    def on_search_results(self, event: SearchResultsEvent) -> None:
        """Called when search results are produced that users might need to see."""
        pass
    
    @abstractmethod
    def on_human_input_requested(self, event: HumanInputRequestedEvent) -> Optional[str]:
        """Called when human input is needed. Can return the input directly."""
        pass
    
    @abstractmethod
    def on_plan_step(self, event: PlanStepEvent) -> None:
        """Called when plan steps are created, updated, or completed."""
        pass
    
    @abstractmethod
    def on_plan_created(self, event: PlanCreatedEvent) -> None:
        """Called when a new plan is created."""
        pass
    
    @abstractmethod
    def on_task_started(self, event: TaskStartedEvent) -> None:
        """Called when a task/step begins execution."""
        pass
    
    @abstractmethod
    def on_task_completed(self, event: TaskCompletedEvent) -> None:
        """Called when a task/step completes execution."""
        pass
    
    @abstractmethod
    def on_plan_modified(self, event: PlanModifiedEvent) -> None:
        """Called when plan is modified (steps added/removed/reordered)."""
        pass
    
    @abstractmethod
    def on_plan_updated(self, event: PlanUpdatedEvent) -> None:
        """Called with full plan status update."""
        pass
    
    def on_memory_node_added(self, event: MemoryNodeAddedEvent) -> None:
        """Called when a memory node is added. Default implementation does nothing."""
        pass
    
    def on_memory_edge_added(self, event: MemoryEdgeAddedEvent) -> None:
        """Called when a memory edge is added. Default implementation does nothing."""
        pass
    
    def on_memory_graph_snapshot(self, event: MemoryGraphSnapshotEvent) -> None:
        """Called with memory graph snapshot. Default implementation does nothing."""
        pass
    
    def on_llm_context(self, event: LLMContextEvent) -> None:
        """Called when LLM context is built. Default implementation does nothing."""
        pass


class UXObserver(PlanExecuteObserver):
    """Observer that tracks user-visible data for display in human input requests."""
    
    def __init__(self):
        self.user_visible_data: List[str] = []
        self.current_step = None
        # Plan state tracking
        self.current_plan: List[str] = []
        self.completed_steps: List[str] = []
        self.failed_steps: List[str] = []
    
    def on_search_results(self, event: SearchResultsEvent) -> None:
        """Store search results for later display when human input is needed."""
        if event.is_user_selectable:
            self.user_visible_data.append(event.results)
    
    def on_human_input_requested(self, event: HumanInputRequestedEvent) -> Optional[str]:
        """Combine accumulated data with the question for comprehensive user context."""
        if self.user_visible_data:
            # Combine all user-visible data with the question
            full_context = "\n\n".join(self.user_visible_data)
            full_message = f"{full_context}\n\n{event.question}"
            
            # Clear the data after use to prevent duplication in subsequent requests
            self.user_visible_data.clear()
            
            return full_message
        return event.question
    
    def on_plan_step(self, event: PlanStepEvent) -> None:
        """Track plan step events."""
        self.current_plan = event.plan_steps
        self.completed_steps = event.completed_steps
        self.failed_steps = event.failed_steps
        self.current_step = event.current_step
    
    def on_plan_created(self, event: PlanCreatedEvent) -> None:
        """Track initial plan creation."""
        self.current_plan = event.plan_steps
        self.completed_steps = []
        self.failed_steps = []
    
    def on_task_started(self, event: TaskStartedEvent) -> None:
        """Track task start."""
        self.current_step = event.task_description
    
    def on_task_completed(self, event: TaskCompletedEvent) -> None:
        """Track task completion."""
        if event.success:
            if event.task_description not in self.completed_steps:
                self.completed_steps.append(event.task_description)
        else:
            if event.task_description not in self.failed_steps:
                self.failed_steps.append(event.task_description)
    
    def on_plan_modified(self, event: PlanModifiedEvent) -> None:
        """Handle plan modifications."""
        self.current_plan = event.plan_steps
    
    def on_plan_updated(self, event: PlanUpdatedEvent) -> None:
        """Handle comprehensive plan updates."""
        self.current_plan = event.plan_steps
        self.completed_steps = event.completed_steps
        self.failed_steps = event.failed_steps
        self.current_step = event.current_step
    
    def get_plan_summary(self) -> str:
        """Get a summary of the current plan state."""
        if not self.current_plan:
            return "No plan created yet."
        
        lines = ["Current Plan:"]
        for i, step in enumerate(self.current_plan, 1):
            if step in self.completed_steps:
                status = "✓"
            elif step in self.failed_steps:
                status = "✗"
            elif step == self.current_step:
                status = "→"
            else:
                status = " "
            lines.append(f"{status} {i}. {step}")
        
        return "\n".join(lines)
    
    def clear_data(self):
        """Clear accumulated user-visible data (useful for testing or manual resets)."""
        self.user_visible_data.clear()
        self.current_plan = []
        self.completed_steps = []
        self.failed_steps = []