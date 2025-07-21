"""Observer pattern for plan-execute workflow events.

This module provides a clean way to observe and react to plan-execute workflow events
without coupling business logic to UX concerns. Observers can track search results,
plan progress, user interactions, and other workflow events.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Any
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
    event_type: str = "created"  # "created", "updated", "completed"


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


class UXObserver(PlanExecuteObserver):
    """Observer that tracks user-visible data for display in human input requests."""
    
    def __init__(self):
        self.user_visible_data: List[str] = []
        self.current_step = None
    
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
        else:
            # No additional context, just return the question
            return event.question
    
    def on_plan_step(self, event: PlanStepEvent) -> None:
        """Track plan progress (useful for future live updates)."""
        self.current_step = event.step_name
        # Future: Could emit to UI for live progress tracking
    
    def clear_data(self):
        """Clear accumulated user-visible data (useful for testing or manual resets)."""
        self.user_visible_data.clear()


class ObserverRegistry:
    """Registry for managing multiple observers."""
    
    def __init__(self):
        self.observers: List[PlanExecuteObserver] = []
    
    def add_observer(self, observer: PlanExecuteObserver):
        """Add an observer to the registry."""
        self.observers.append(observer)
    
    def remove_observer(self, observer: PlanExecuteObserver):
        """Remove an observer from the registry."""
        if observer in self.observers:
            self.observers.remove(observer)
    
    def notify_search_results(self, event: SearchResultsEvent):
        """Notify all observers of search results."""
        for observer in self.observers:
            observer.on_search_results(event)
    
    def notify_human_input_requested(self, event: HumanInputRequestedEvent) -> Optional[str]:
        """Notify observers of human input request. Returns enhanced message from first observer."""
        for observer in self.observers:
            result = observer.on_human_input_requested(event)
            if result:
                return result
        return event.question
    
    def notify_plan_step(self, event: PlanStepEvent):
        """Notify all observers of plan step events."""
        for observer in self.observers:
            observer.on_plan_step(event)


# Global observer registry - will be initialized by the plan-execute workflow
observer_registry: Optional[ObserverRegistry] = None


def get_observer_registry() -> ObserverRegistry:
    """Get the global observer registry, creating it if needed."""
    global observer_registry
    if observer_registry is None:
        observer_registry = ObserverRegistry()
    return observer_registry