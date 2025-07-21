"""Observer pattern for plan-execute workflow events.

This module provides a clean way to observe and react to plan-execute workflow events
without coupling business logic to UX concerns. Observers can track search results,
plan progress, user interactions, and other workflow events.

New plan events for live updates:
- PlanCreatedEvent: When a new plan is created
- TaskStartedEvent: When a task/step begins execution  
- TaskCompletedEvent: When a task/step completes
- PlanModifiedEvent: When plan structure changes (steps added/removed)
- PlanUpdatedEvent: When plan progress updates (same steps, different status)
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Any, Dict
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import concurrent.futures
import threading


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
    result: str = ""
    status: str = "success"  # "success", "failed"


@dataclass  
class PlanModifiedEvent(WorkflowEvent):
    """Event fired when plan is modified (steps added/removed/reordered)."""
    old_plan: List[str] = field(default_factory=list)
    new_plan: List[str] = field(default_factory=list)
    modification_reason: str = ""


@dataclass
class PlanUpdatedEvent(WorkflowEvent):
    """Event fired with full plan status update."""
    plan_steps: List[str] = field(default_factory=list)
    completed_steps: List[str] = field(default_factory=list)
    current_step: Optional[str] = None
    failed_steps: List[str] = field(default_factory=list)
    status: str = "in_progress"  # "in_progress", "completed", "failed"


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
        else:
            # No additional context, just return the question
            return event.question
    
    def on_plan_step(self, event: PlanStepEvent) -> None:
        """Track plan progress (useful for future live updates)."""
        self.current_step = event.step_name
        # Future: Could emit to UI for live progress tracking
    
    def on_plan_created(self, event: PlanCreatedEvent) -> None:
        """Handle new plan creation."""
        self.current_plan = event.plan_steps.copy()
        self.completed_steps = []
        self.failed_steps = []
        # Future: Emit SSE event for UI
    
    def on_task_started(self, event: TaskStartedEvent) -> None:
        """Handle task start."""
        self.current_step = event.task_description
        # Future: Emit SSE event for UI
    
    def on_task_completed(self, event: TaskCompletedEvent) -> None:
        """Handle task completion."""
        if event.status == "success":
            if event.task_description not in self.completed_steps:
                self.completed_steps.append(event.task_description)
        else:
            if event.task_description not in self.failed_steps:
                self.failed_steps.append(event.task_description)
        # Future: Emit SSE event for UI
    
    def on_plan_modified(self, event: PlanModifiedEvent) -> None:
        """Handle plan structure changes."""
        self.current_plan = event.new_plan.copy()
        # Reset completion tracking when plan structure changes
        # Keep completed steps that still exist in new plan
        self.completed_steps = [step for step in self.completed_steps if step in event.new_plan]
        self.failed_steps = [step for step in self.failed_steps if step in event.new_plan]
        # Future: Emit SSE event for UI
    
    def on_plan_updated(self, event: PlanUpdatedEvent) -> None:
        """Handle plan progress updates."""
        self.current_plan = event.plan_steps.copy()
        self.completed_steps = event.completed_steps.copy()
        self.failed_steps = event.failed_steps.copy()
        self.current_step = event.current_step
        # Future: Emit SSE event for UI
    
    def clear_data(self):
        """Clear accumulated user-visible data (useful for testing or manual resets)."""
        self.user_visible_data.clear()
        self.current_plan = []
        self.completed_steps = []
        self.failed_steps = []


class SSEObserver(PlanExecuteObserver):
    """Observer that converts plan events to SSE messages for live UI updates."""
    
    def __init__(self):
        self.sse_queue: List[Dict] = []  # Queue of SSE messages
        self._observers = []  # SSE clients listening
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="sse-observer")
    
    def add_client(self, client_callback):
        """Add an SSE client callback."""
        self._observers.append(client_callback)
    
    def remove_client(self, client_callback):
        """Remove an SSE client callback."""
        if client_callback in self._observers:
            self._observers.remove(client_callback)
    
    def _emit_sse_threadsafe(self, event_type: str, data: Dict):
        """Thread-safe method to emit SSE events."""
        from src.utils.logging.framework import SmartLogger
        logger = SmartLogger("orchestrator")
        
        logger.info("SSE_OBSERVER_emit_threadsafe", 
                   event_type=event_type,
                   connected_clients=len(self._observers))
        
        # Format to match main branch: {"event": "type", "data": {...}}
        sse_payload = {
            "event": event_type,
            "data": data
        }
        
        sse_message = {
            "event": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat(),
            "sse_payload": sse_payload  # Store formatted payload for transmission
        }
        
        # Add to queue for new connections (thread-safe for simple operations)
        self.sse_queue.append(sse_message)
        
        # Keep only last 50 messages
        if len(self.sse_queue) > 50:
            self.sse_queue.pop(0)
        
        # Send to all connected clients using the executor
        def run_callbacks():
            """Run callbacks in the executor thread with its own event loop."""
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Run the async emission
                loop.run_until_complete(self._emit_sse_async(sse_message))
            except Exception as e:
                logger.error("SSE_OBSERVER_callback_execution_failed", error=str(e))
            finally:
                loop.close()
        
        # Submit to thread pool
        self._executor.submit(run_callbacks)
    
    async def _emit_sse_async(self, sse_message: Dict):
        """Async method to actually send SSE messages to connected clients."""
        from src.utils.logging.framework import SmartLogger
        logger = SmartLogger("orchestrator")
        
        event_type = sse_message.get("event", "unknown")
        logger.info("SSE_OBSERVER_sending_to_clients", 
                   event_type=event_type, 
                   connected_clients=len(self._observers))
        
        # Send to all connected clients
        for callback in self._observers[:]:  # Copy to avoid modification during iteration
            try:
                await callback(sse_message)  # Await the async callback
                logger.info("SSE_OBSERVER_callback_success", event_type=event_type)
            except Exception as e:
                logger.error("SSE_OBSERVER_callback_failed", event_type=event_type, error=str(e))
                # Remove dead clients
                try:
                    self._observers.remove(callback)
                except ValueError:
                    pass  # Already removed
    
    def on_search_results(self, event: SearchResultsEvent) -> None:
        """Forward search results via SSE."""
        pass  # Not needed for plan updates
    
    def on_human_input_requested(self, event: HumanInputRequestedEvent) -> Optional[str]:
        """Forward human input requests via SSE."""
        return None  # Not handling input via SSE
    
    def on_plan_step(self, event: PlanStepEvent) -> None:
        """Forward plan step events via SSE."""
        pass  # Using more specific events instead
    
    def on_plan_created(self, event: PlanCreatedEvent) -> None:
        """Emit plan_created SSE event."""
        from src.utils.logging.framework import SmartLogger
        logger = SmartLogger("orchestrator")
        logger.info("SSE_OBSERVER_DEBUG_plan_created", 
                   task_id=event.task_id, 
                   total_steps=event.total_steps,
                   connected_clients=len(self._observers))
        
        # Use thread-safe emission
        self._emit_sse_threadsafe("plan_created", {
            "task_id": event.task_id,
            "plan_steps": event.plan_steps,
            "total_steps": event.total_steps
        })
    
    def on_task_started(self, event: TaskStartedEvent) -> None:
        """Emit task_started SSE event."""
        self._emit_sse_threadsafe("task_started", {
            "task_id": event.task_id,
            "task_description": event.task_description,
            "step_number": event.step_number,
            "total_steps": event.total_steps
        })
    
    def on_task_completed(self, event: TaskCompletedEvent) -> None:
        """Emit task_completed SSE event."""
        self._emit_sse_threadsafe("task_completed", {
            "task_id": event.task_id,
            "task_description": event.task_description,
            "step_number": event.step_number,
            "total_steps": event.total_steps,
            "result": event.result,
            "status": event.status
        })
    
    def on_plan_modified(self, event: PlanModifiedEvent) -> None:
        """Emit plan_modified SSE event."""
        self._emit_sse_threadsafe("plan_modified", {
            "task_id": event.task_id,
            "old_plan": event.old_plan,
            "new_plan": event.new_plan,
            "modification_reason": event.modification_reason
        })
    
    def on_plan_updated(self, event: PlanUpdatedEvent) -> None:
        """Emit plan_updated SSE event."""
        self._emit_sse_threadsafe("plan_updated", {
            "task_id": event.task_id,
            "plan_steps": event.plan_steps,
            "completed_steps": event.completed_steps,
            "current_step": event.current_step,
            "failed_steps": event.failed_steps,
            "status": event.status
        })


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


# Global observer registry - will be initialized by the plan-execute workflow
observer_registry: Optional[ObserverRegistry] = None


def get_observer_registry() -> ObserverRegistry:
    """Get the global observer registry, creating it if needed."""
    global observer_registry
    if observer_registry is None:
        observer_registry = ObserverRegistry()
    return observer_registry