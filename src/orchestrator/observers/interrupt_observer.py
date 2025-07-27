"""Interrupt observer for tracking and managing workflow interrupts."""

from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field

from .base import PlanExecuteObserver, WorkflowEvent
from src.utils.logging.framework import SmartLogger
from src.orchestrator.observers.direct_call_events import (
    emit_agent_call_event, 
    DirectCallEventTypes
)

logger = SmartLogger("orchestrator")


@dataclass
class InterruptEvent(WorkflowEvent):
    """Event fired when workflow is interrupted."""
    interrupt_type: str = ""  # "user_escape" or InterruptType values (clarification, confirmation, etc.)
    interrupt_reason: str = ""
    thread_id: str = ""
    completed_steps: int = 0
    total_steps: int = 0
    current_plan: list = field(default_factory=list)
    interrupt_payload: Optional[Dict[str, Any]] = None  # Full interrupt payload for structured interrupts


@dataclass
class InterruptResumeEvent(WorkflowEvent):
    """Event fired when workflow resumes from interrupt."""
    interrupt_type: str = ""
    thread_id: str = ""
    user_input: str = ""
    was_modified: bool = False  # True if user modified the plan


class InterruptObserver(PlanExecuteObserver):
    """Observer that tracks interrupt states and context."""
    
    def __init__(self):
        super().__init__()
        # Track interrupt states by thread_id
        self.interrupt_states: Dict[str, Dict[str, Any]] = {}
    
    # Implement required abstract methods from PlanExecuteObserver
    def on_search_results(self, event) -> None:
        """Not used by interrupt observer."""
        pass
    
    def on_human_input_requested(self, event) -> Optional[str]:
        """Not used by interrupt observer."""
        return None
    
    def on_plan_step(self, event) -> None:
        """Not used by interrupt observer."""
        pass
    
    def on_plan_created(self, event) -> None:
        """Not used by interrupt observer."""
        pass
    
    def on_task_started(self, event) -> None:
        """Not used by interrupt observer."""
        pass
    
    def on_task_completed(self, event) -> None:
        """Not used by interrupt observer."""
        pass
    
    def on_plan_modified(self, event) -> None:
        """Not used by interrupt observer."""
        pass
    
    def on_plan_updated(self, event) -> None:
        """Not used by interrupt observer."""
        pass
        
    def record_interrupt(self, thread_id: str, interrupt_type: str, reason: str, 
                        current_plan: list = None, state: Dict[str, Any] = None,
                        interrupt_payload: Optional[Dict[str, Any]] = None) -> None:
        """Record an interrupt event with full context."""
        
        # Calculate plan progress if state provided
        completed_steps = 0
        total_steps = len(current_plan) if current_plan else 0
        
        if state and "past_steps" in state and "plan_step_offset" in state:
            plan_offset = state.get("plan_step_offset", 0)
            current_plan_steps = state["past_steps"][plan_offset:]
            completed_steps = len(current_plan_steps)
        
        # Store interrupt context
        self.interrupt_states[thread_id] = {
            "interrupt_type": interrupt_type,
            "interrupt_reason": reason,
            "interrupt_time": datetime.now().isoformat(),
            "current_plan": current_plan or [],
            "completed_steps": completed_steps,
            "total_steps": total_steps,
            "state_snapshot": {
                "input": state.get("input", "") if state else "",
                "task_id": state.get("task_id", "") if state else "",
            }
        }
        
        logger.info("interrupt_recorded",
                   thread_id=thread_id,
                   interrupt_type=interrupt_type,
                   reason=reason[:100],
                   completed_steps=completed_steps,
                   total_steps=total_steps)
        
        # Emit interrupt event
        event = InterruptEvent(
            step_name="interrupt",
            task_id=state.get("task_id", "") if state else "",
            interrupt_type=interrupt_type,
            interrupt_reason=reason,
            thread_id=thread_id,
            current_plan=current_plan or [],
            completed_steps=completed_steps,
            total_steps=total_steps,
            interrupt_payload=interrupt_payload
        )
        
        # Notify registry
        from . import get_observer_registry
        registry = get_observer_registry()
        if hasattr(registry, 'notify_interrupt'):
            registry.notify_interrupt(event)
    
    def get_interrupt_context(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get stored interrupt context for a thread."""
        return self.interrupt_states.get(thread_id)
    
    def clear_interrupt(self, thread_id: str) -> None:
        """Clear interrupt state after successful resume."""
        if thread_id in self.interrupt_states:
            logger.info("interrupt_cleared",
                       thread_id=thread_id,
                       interrupt_type=self.interrupt_states[thread_id].get("interrupt_type"))
            del self.interrupt_states[thread_id]
    
    def record_resume(self, thread_id: str, user_input: str, interrupt_type: str = None) -> None:
        """Record a resume event."""
        
        # Get interrupt type from stored context if not provided
        if not interrupt_type and thread_id in self.interrupt_states:
            interrupt_type = self.interrupt_states[thread_id].get("interrupt_type", "unknown")
        
        was_modified = interrupt_type == "user_escape" and bool(user_input)
        
        logger.info("interrupt_resume_recorded",
                   thread_id=thread_id,
                   interrupt_type=interrupt_type,
                   user_input_length=len(user_input) if user_input else 0,
                   was_modified=was_modified)
        
        # Emit human input received event for the tool execution log
        # Only emit for actual human input interrupts, not escape key interrupts
        if user_input and interrupt_type != "user_escape":
            task_id = self.interrupt_states.get(thread_id, {}).get("state_snapshot", {}).get("task_id", "unknown")
            emit_agent_call_event(
                DirectCallEventTypes.HUMAN_INPUT_RECEIVED,
                agent_name="orchestrator",
                task_id=task_id,
                instruction=user_input,  # Send the user's response
                additional_data={
                    "tool_name": "human_input",
                    "response_length": len(user_input),
                    "interrupt_type": interrupt_type
                }
            )
        
        # Emit resume event
        event = InterruptResumeEvent(
            step_name="interrupt_resume",
            task_id=self.interrupt_states.get(thread_id, {}).get("state_snapshot", {}).get("task_id", ""),
            interrupt_type=interrupt_type,
            thread_id=thread_id,
            user_input=user_input,
            was_modified=was_modified
        )
        
        # Notify registry
        from . import get_observer_registry
        registry = get_observer_registry()
        if hasattr(registry, 'notify_interrupt_resume'):
            registry.notify_interrupt_resume(event)


# Global interrupt observer instance
_interrupt_observer: Optional[InterruptObserver] = None


def get_interrupt_observer() -> InterruptObserver:
    """Get or create the global interrupt observer instance."""
    global _interrupt_observer
    if _interrupt_observer is None:
        _interrupt_observer = InterruptObserver()
        
        # Register with observer registry
        from . import get_observer_registry
        registry = get_observer_registry()
        registry.register(_interrupt_observer)
        
    return _interrupt_observer