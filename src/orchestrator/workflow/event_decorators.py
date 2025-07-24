"""Event emission decorators for plan-execute workflow.

These decorators automatically emit plan events based on function execution,
keeping the core LangGraph logic clean while enabling live updates.
"""

from functools import wraps
from typing import Any, Callable, Dict, List

from src.orchestrator.observers import (
    get_observer_registry, 
    PlanCreatedEvent, 
    TaskStartedEvent, 
    TaskCompletedEvent,
    PlanModifiedEvent,
    PlanUpdatedEvent
)
from src.utils.logging.framework import SmartLogger

logger = SmartLogger("orchestrator")


def emit_plan_created(func: Callable) -> Callable:
    """Decorator that emits PlanCreatedEvent when a plan is created."""
    
    @wraps(func)
    def wrapper(state: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
        result = func(state, *args, **kwargs)
        
        try:
            # Extract plan from result
            if isinstance(result, dict) and "plan" in result:
                thread_id = state.get("thread_id", "unknown")
                task_id = state.get("task_id", thread_id)  # Use actual task_id for SSE events
                plan_steps = result["plan"]
                
                registry = get_observer_registry()
                event = PlanCreatedEvent(
                    step_name="plan_creation",
                    task_id=task_id,
                    plan_steps=plan_steps,
                    total_steps=len(plan_steps)
                )
                registry.notify_plan_created(event)
                
                logger.info("plan_created_event_emitted",
                           component="orchestrator",
                           thread_id=thread_id,
                           total_steps=len(plan_steps))
        except Exception as e:
            logger.error("failed_to_emit_plan_created",
                        component="orchestrator",
                        error=str(e))
        
        return result
    
    return wrapper


def emit_task_lifecycle(func: Callable) -> Callable:
    """Decorator that emits TaskStarted and TaskCompleted events for execution."""
    
    @wraps(func) 
    def wrapper(state: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
        thread_id = state.get("thread_id", "unknown")
        task_id = state.get("task_id", thread_id)  # Use actual task_id for SSE events
        plan = state.get("plan", [])
        past_steps = state.get("past_steps", [])
        current_step_num = len(past_steps) + 1
        
        # Get current task
        current_task = plan[0] if plan else "Unknown task"
        
        try:
            # Emit task started event
            registry = get_observer_registry()
            start_event = TaskStartedEvent(
                step_name="task_execution",
                task_id=task_id,
                task_description=current_task,
                step_number=current_step_num,
                total_steps=len(plan)
            )
            registry.notify_task_started(start_event)
            
            logger.info("task_started_event_emitted",
                       component="orchestrator",
                       thread_id=thread_id,
                       task=current_task[:50],
                       step_number=current_step_num)
        except Exception as e:
            logger.error("failed_to_emit_task_started",
                        component="orchestrator", 
                        error=str(e))
        
        # Execute the actual function
        result = func(state, *args, **kwargs)
        
        try:
            # Emit task completed event
            registry = get_observer_registry()
            
            # Determine status based on result
            status = "success"  # Default to success
            result_content = ""
            
            if isinstance(result, dict) and "past_steps" in result:
                # Extract result from past_steps
                new_past_steps = result["past_steps"]
                if new_past_steps:
                    last_step = new_past_steps[-1]
                    if isinstance(last_step, dict):
                        result_content = str(last_step.get('result', ''))
                        status = last_step.get('status', 'completed')
                        if status != 'failed' and any(error_word in result_content.lower() 
                               for error_word in ["error", "failed", "exception"]):
                            status = "failed"
            
            complete_event = TaskCompletedEvent(
                step_name="task_execution",
                task_id=task_id,
                task_description=current_task,
                step_number=current_step_num,
                total_steps=len(plan),
                result=result_content,
                status=status
            )
            registry.notify_task_completed(complete_event)
            
            logger.info("task_completed_event_emitted",
                       component="orchestrator",
                       thread_id=thread_id,
                       task=current_task[:50],
                       status=status)
        except Exception as e:
            logger.error("failed_to_emit_task_completed",
                        component="orchestrator",
                        error=str(e))
        
        return result
    
    return wrapper


def emit_plan_modified(func: Callable) -> Callable:
    """Decorator that emits PlanModifiedEvent when replanning changes the plan."""
    
    @wraps(func)
    def wrapper(state: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
        # Capture original plan before execution
        original_plan = state.get("plan", []).copy()
        thread_id = state.get("thread_id", "unknown")
        task_id = state.get("task_id", thread_id)  # Use actual task_id for SSE events
        
        # Execute the function
        result = func(state, *args, **kwargs)
        
        try:
            # Check if plan was modified (new plan in result)
            if isinstance(result, dict) and "plan" in result:
                new_plan = result["plan"]
                
                # Only emit if plan actually changed
                if new_plan != original_plan:
                    registry = get_observer_registry()
                    event = PlanModifiedEvent(
                        step_name="plan_modification",
                        task_id=task_id,
                        old_plan=original_plan,
                        new_plan=new_plan,
                        modification_reason="replanning"
                    )
                    registry.notify_plan_modified(event)
                    
                    logger.info("plan_modified_event_emitted",
                               component="orchestrator",
                               thread_id=thread_id,
                               old_steps=len(original_plan),
                               new_steps=len(new_plan))
        except Exception as e:
            logger.error("failed_to_emit_plan_modified",
                        component="orchestrator",
                        error=str(e))
        
        return result
    
    return wrapper


def emit_plan_updated(func: Callable) -> Callable:
    """Decorator that emits PlanUpdatedEvent with current progress status."""
    
    @wraps(func)
    def wrapper(state: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
        result = func(state, *args, **kwargs)
        
        try:
            thread_id = state.get("thread_id", "unknown")
            task_id = state.get("task_id", thread_id)  # Use actual task_id for SSE events
            
            # Build current status from state and result
            plan = state.get("plan", [])
            past_steps = state.get("past_steps", [])
            
            # Extract completed steps
            completed_steps = []
            failed_steps = []
            for step_data in past_steps:
                if isinstance(step_data, dict):
                    step_desc = step_data.get('step_description', '')
                    status = step_data.get('status', 'completed')
                    if status == 'failed':
                        failed_steps.append(step_desc)
                    elif status == 'completed':
                        completed_steps.append(step_desc)
            
            # Determine current step and overall status
            current_step = None
            overall_status = "in_progress"
            
            if len(completed_steps) + len(failed_steps) >= len(plan):
                overall_status = "completed" if not failed_steps else "failed"
            elif plan and len(past_steps) < len(plan):
                current_step = plan[len(past_steps)]
            
            # Check if this is a final response (task completion)
            if isinstance(result, dict) and "response" in result and result["response"]:
                overall_status = "completed"
            
            registry = get_observer_registry()
            event = PlanUpdatedEvent(
                step_name="plan_progress",
                task_id=task_id,
                plan_steps=plan,
                completed_steps=completed_steps,
                current_step=current_step,
                failed_steps=failed_steps,
                total_steps=len(plan),
                completed_count=len(completed_steps),
                failed_count=len(failed_steps)
            )
            registry.notify_plan_updated(event)
            
            logger.info("plan_updated_event_emitted",
                       component="orchestrator",
                       thread_id=thread_id,
                       status=overall_status,
                       completed=len(completed_steps),
                       failed=len(failed_steps),
                       total=len(plan))
        except Exception as e:
            logger.error("failed_to_emit_plan_updated",
                        component="orchestrator",
                        error=str(e))
        
        return result
    
    return wrapper


def emit_coordinated_events(event_types: List[str]) -> Callable:
    """Coordinated decorator that emits multiple event types safely in the right order.
    
    Args:
        event_types: List of event types to emit, e.g. ["task_lifecycle", "plan_updated"]
    
    Execution order:
    1. Pre-execution: task_started (if task_lifecycle)
    2. Function execution
    3. Post-execution (in order): plan_created -> plan_modified -> task_completed -> plan_updated
    
    This prevents race conditions and ensures events are emitted in logical sequence.
    """
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(state: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
            thread_id = state.get("thread_id", "unknown")
            task_id = state.get("task_id", thread_id)  # Use actual task_id for SSE events
            registry = get_observer_registry()
            
            # Pre-execution context tracking
            pre_execution_data = {}
            
            try:
                # Handle task lifecycle start
                if "task_lifecycle" in event_types:
                    plan = state.get("plan", [])
                    past_steps = state.get("past_steps", [])
                    current_step_num = len(past_steps) + 1
                    current_task = plan[0] if plan else "Unknown task"
                    
                    start_event = TaskStartedEvent(
                        step_name="task_execution",
                        task_id=task_id,
                        task_description=current_task,
                        step_number=current_step_num,
                        total_steps=len(plan)
                    )
                    registry.notify_task_started(start_event)
                    pre_execution_data["task"] = (current_task, current_step_num, len(plan))
                    
                    logger.info("coordinated_task_started",
                               component="orchestrator",
                               thread_id=thread_id,
                               task=current_task[:50])
            except Exception as e:
                logger.error("coordinated_pre_execution_failed",
                            component="orchestrator",
                            error=str(e))
            
            # Store original plan for modification detection
            original_plan = state.get("plan", []).copy()
            
            # Execute the actual function
            result = func(state, *args, **kwargs)
            
            # Post-execution events (coordinated order prevents race conditions)
            events_emitted = []
            
            try:
                # 1. Plan creation (highest priority - new structure)
                if "plan_created" in event_types and isinstance(result, dict) and "plan" in result:
                    plan_steps = result["plan"]
                    event = PlanCreatedEvent(
                        step_name="plan_creation",
                        task_id=task_id,
                        plan_steps=plan_steps,
                        total_steps=len(plan_steps)
                    )
                    registry.notify_plan_created(event)
                    events_emitted.append("plan_created")
                
                # 2. Plan modification (structural changes)
                if "plan_modified" in event_types and isinstance(result, dict) and "plan" in result:
                    new_plan = result["plan"]
                    if new_plan != original_plan:
                        # Determine modification type
                        if len(new_plan) > len(original_plan):
                            mod_type = "add"
                        elif len(new_plan) < len(original_plan):
                            mod_type = "remove"
                        elif new_plan != original_plan:
                            mod_type = "replace"
                        else:
                            mod_type = "reorder"
                        
                        event = PlanModifiedEvent(
                            step_name="plan_modification",
                            task_id=task_id,
                            plan_steps=new_plan,
                            modification_type=mod_type,
                            details=f"Plan modified from {len(original_plan)} to {len(new_plan)} steps"
                        )
                        registry.notify_plan_modified(event)
                        events_emitted.append("plan_modified")
                
                # 3. Task completion (execution results)
                if "task_lifecycle" in event_types and "task" in pre_execution_data:
                    current_task, current_step_num, total_steps = pre_execution_data["task"]
                    
                    status = "success"
                    result_content = ""
                    
                    if isinstance(result, dict) and "past_steps" in result:
                        new_past_steps = result["past_steps"]
                        if new_past_steps:
                            last_step = new_past_steps[-1]
                            if isinstance(last_step, dict):
                                result_content = str(last_step.get('result', ''))
                                status = last_step.get('status', 'completed')
                                if status != 'failed' and any(error_word in result_content.lower() 
                                       for error_word in ["error", "failed", "exception"]):
                                    status = "failed"
                    
                    complete_event = TaskCompletedEvent(
                        step_name="task_execution",
                        task_id=task_id,
                        task_description=current_task,
                        step_number=current_step_num,
                        total_steps=total_steps,
                        result=result_content,
                        success=(status != "failed")
                    )
                    registry.notify_task_completed(complete_event)
                    events_emitted.append("task_completed")
                
                # 4. Plan update (final status - always last to ensure consistent state)
                if "plan_updated" in event_types:
                    plan = result.get("plan", state.get("plan", []))
                    past_steps = state.get("past_steps", [])
                    
                    completed_steps = []
                    failed_steps = []
                    for step_data in past_steps:
                        if isinstance(step_data, dict):
                            step_desc = step_data.get('step_description', '')
                            status = step_data.get('status', 'completed')
                            if status == 'failed':
                                failed_steps.append(step_desc)
                            elif status == 'completed':
                                completed_steps.append(step_desc)
                    
                    current_step = None
                    
                    if len(completed_steps) + len(failed_steps) >= len(plan):
                        pass
                    elif plan and len(past_steps) < len(plan):
                        current_step = plan[len(past_steps)]
                    
                    if isinstance(result, dict) and "response" in result and result["response"]:
                        pass
                    
                    update_event = PlanUpdatedEvent(
                        step_name="plan_progress",
                        task_id=task_id,
                        plan_steps=plan,
                        completed_steps=completed_steps,
                        current_step=current_step,
                        failed_steps=failed_steps,
                        total_steps=len(plan),
                        completed_count=len(completed_steps),
                        failed_count=len(failed_steps)
                    )
                    registry.notify_plan_updated(update_event)
                    events_emitted.append("plan_updated")
                
                logger.info("coordinated_events_completed",
                           component="orchestrator",
                           thread_id=thread_id,
                           function=func.__name__,
                           events=events_emitted)
                           
            except Exception as e:
                logger.error("coordinated_post_execution_failed",
                            component="orchestrator",
                            function=func.__name__,
                            events_attempted=event_types,
                            events_completed=events_emitted,
                            error=str(e))
            
            return result
        
        return wrapper
    return decorator