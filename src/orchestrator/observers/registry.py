"""Observer registry for managing multiple observers."""

from typing import List, Optional

from .base import (
    PlanExecuteObserver,
    SearchResultsEvent,
    HumanInputRequestedEvent,
    PlanStepEvent,
    PlanCreatedEvent,
    TaskStartedEvent,
    TaskCompletedEvent,
    PlanModifiedEvent,
    PlanUpdatedEvent,
    MemoryNodeAddedEvent,
    MemoryEdgeAddedEvent,
    MemoryGraphSnapshotEvent,
    LLMContextEvent
)


class ObserverRegistry:
    """Registry for managing multiple observers."""
    
    def __init__(self):
        self.observers: List[PlanExecuteObserver] = []
    
    def add_observer(self, observer: PlanExecuteObserver):
        """Add an observer to the registry."""
        self.observers.append(observer)
    
    def register(self, observer: PlanExecuteObserver):
        """Register an observer (alias for add_observer)."""
        self.add_observer(observer)
    
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
    
    def notify_plan_created(self, event: PlanCreatedEvent):
        """Notify all observers of plan creation."""
        for observer in self.observers:
            observer.on_plan_created(event)
    
    def notify_task_started(self, event: TaskStartedEvent):
        """Notify all observers of task start."""
        for observer in self.observers:
            observer.on_task_started(event)
    
    def notify_task_completed(self, event: TaskCompletedEvent):
        """Notify all observers of task completion."""
        for observer in self.observers:
            observer.on_task_completed(event)
    
    def notify_plan_modified(self, event: PlanModifiedEvent):
        """Notify all observers of plan modification."""
        for observer in self.observers:
            observer.on_plan_modified(event)
    
    def notify_plan_updated(self, event: PlanUpdatedEvent):
        """Notify all observers of plan updates."""
        for observer in self.observers:
            observer.on_plan_updated(event)
    
    def notify_memory_node_added(self, event: MemoryNodeAddedEvent):
        """Notify all observers of memory node addition."""
        for observer in self.observers:
            observer.on_memory_node_added(event)
    
    def notify_memory_edge_added(self, event: MemoryEdgeAddedEvent):
        """Notify all observers of memory edge addition."""
        for observer in self.observers:
            observer.on_memory_edge_added(event)
    
    def notify_memory_graph_snapshot(self, event: MemoryGraphSnapshotEvent):
        """Notify all observers of memory graph snapshot."""
        for observer in self.observers:
            observer.on_memory_graph_snapshot(event)
    
    def notify_interrupt(self, event):
        """Notify all observers of interrupt event."""
        for observer in self.observers:
            if hasattr(observer, 'on_interrupt'):
                observer.on_interrupt(event)
    
    def notify_interrupt_resume(self, event):
        """Notify all observers of interrupt resume event."""
        for observer in self.observers:
            if hasattr(observer, 'on_interrupt_resume'):
                observer.on_interrupt_resume(event)
    
    def notify_llm_context(self, event: LLMContextEvent):
        """Notify all observers of LLM context event."""
        for observer in self.observers:
            observer.on_llm_context(event)


# Global observer registry - will be initialized by the plan-execute workflow
observer_registry: Optional[ObserverRegistry] = None


def get_observer_registry() -> ObserverRegistry:
    """Get the global observer registry, creating it if needed."""
    global observer_registry
    if observer_registry is None:
        observer_registry = ObserverRegistry()
    return observer_registry