"""Centralized Error Handling for Workflow Agent"""

from typing import Dict, Any, Optional
from .config import WORKFLOW_DEFAULTS
from src.utils.logging import get_logger

logger = get_logger("workflow")


class WorkflowErrorHandler:
    """Handles workflow errors and interrupts consistently"""
    
    @staticmethod
    def is_graph_interrupt(exception: Exception) -> bool:
        """Check if exception is a LangGraph interrupt"""
        return exception.__class__.__name__ == "GraphInterrupt"
    
    @staticmethod
    def extract_interrupt_data(workflow, thread_id: str, workflow_name: str) -> Dict[str, Any]:
        """Extract interrupt data from workflow state
        
        Args:
            workflow: The compiled workflow graph
            thread_id: Thread ID for the workflow
            workflow_name: Name of the workflow
            
        Returns:
            Dictionary containing interrupt context
        """
        config = {"configurable": {"thread_id": thread_id}}
        state = workflow.get_state(config)
        
        interrupt_data = {}
        if state:
            # Log the state structure for debugging
            logger.info("workflow_state_structure",
                       component="workflow",
                       thread_id=thread_id,
                       state_type=type(state).__name__,
                       has_values=hasattr(state, 'values'),
                       has_tasks=hasattr(state, 'tasks'),
                       has_next=hasattr(state, 'next'),
                       state_attrs=dir(state) if hasattr(state, '__dir__') else [])
            logger.info("extracting_interrupt_data",
                       component="workflow",
                       thread_id=thread_id,
                       has_tasks=hasattr(state, 'tasks'),
                       tasks_count=len(state.tasks) if hasattr(state, 'tasks') and state.tasks else 0,
                       has_values=hasattr(state, 'values'))
            
            # First check if there are tasks with interrupts
            if hasattr(state, 'tasks') and state.tasks:
                for i, task in enumerate(state.tasks):
                    logger.info("checking_task_for_interrupts",
                               component="workflow",
                               thread_id=thread_id,
                               task_index=i,
                               has_interrupts=hasattr(task, 'interrupts'),
                               interrupts_count=len(task.interrupts) if hasattr(task, 'interrupts') and task.interrupts else 0)
                    
                    if hasattr(task, 'interrupts') and task.interrupts:
                        # Get the first interrupt (there should only be one pending)
                        interrupt = task.interrupts[0]
                        logger.info("interrupt_found",
                                   component="workflow",
                                   thread_id=thread_id,
                                   interrupt_type=type(interrupt).__name__,
                                   has_value=hasattr(interrupt, 'value'),
                                   value_type=type(interrupt.value).__name__ if hasattr(interrupt, 'value') else None)
                        
                        if hasattr(interrupt, 'value') and isinstance(interrupt.value, dict):
                            # The interrupt value contains our metadata
                            interrupt_data = interrupt.value
                            logger.info("interrupt_metadata_extracted",
                                       component="workflow",
                                       thread_id=thread_id,
                                       workflow_name=workflow_name,
                                       step_id=interrupt_data.get("step_id"),
                                       has_context=bool(interrupt_data.get("context")))
                            return interrupt_data
            
            # Fallback to building from state values if no interrupt metadata found
            if hasattr(state, 'values'):
                current_step = state.values.get("current_step", "")
                step_results = state.values.get("step_results", {})
                variables = state.values.get("variables", {})
                
                # Build interrupt data dynamically
                interrupt_data = {
                    "step_id": current_step,
                    "workflow_id": state.values.get("workflow_id"),
                    "workflow_name": state.values.get("workflow_name"),
                    "context": {
                        "step_results": step_results,
                        "variables": variables,
                        "current_step": current_step,
                        "history": state.values.get("history", [])[-WORKFLOW_DEFAULTS["history_window"]:]
                    }
                }
                logger.info("interrupt_metadata_fallback",
                           component="workflow",
                           thread_id=thread_id,
                           workflow_name=workflow_name,
                           reason="No interrupt metadata in tasks, using state values")
        
        return interrupt_data
    
    @staticmethod
    def handle_workflow_error(error: Exception, workflow_name: str, 
                            thread_id: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log workflow errors with consistent format
        
        Args:
            error: The exception that occurred
            workflow_name: Name of the workflow
            thread_id: Thread ID for the workflow
            context: Additional context to log
        """
        logger.error("workflow_execution_error",
                    component="workflow",
                    workflow_name=workflow_name,
                    thread_id=thread_id,
                    error=str(error),
                    error_type=type(error).__name__,
                    **context or {})
    
    @staticmethod
    def create_error_response(task_id: str, error: Exception) -> Dict[str, Any]:
        """Create standardized error response for A2A
        
        Args:
            task_id: Task ID from the request
            error: The exception that occurred
            
        Returns:
            A2A error response dictionary
        """
        return {
            "artifacts": [{
                "id": f"workflow-error-{task_id}",
                "task_id": task_id,
                "content": {
                    "error": str(error),
                    "error_type": type(error).__name__
                },
                "content_type": "application/json"
            }],
            "status": "failed"
        }