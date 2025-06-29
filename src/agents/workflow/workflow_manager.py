"""Workflow Manager - Manages compiled workflow graphs"""

from typing import Dict, Any, Optional
from langgraph.types import Command

from src.utils.logging import get_logger
from .templates import WorkflowTemplates
from .compiler import WorkflowCompiler, WorkflowState
from .models import WorkflowDefinition
from .config import WORKFLOW_DEFAULTS
from .router import WorkflowRouter
from .error_handler import WorkflowErrorHandler

logger = get_logger("workflow")


class WorkflowManager:
    """Manages compiled workflow graphs and their execution"""
    
    def __init__(self):
        self.compiler = WorkflowCompiler()
        self.templates = WorkflowTemplates()
        self.router = WorkflowRouter()
        self._compiled_workflows: Dict[str, Any] = {}  # Compiled StateGraph objects
        self._workflow_definitions: Dict[str, WorkflowDefinition] = {}
        self._interrupted_workflows: Dict[str, str] = {}  # thread_id -> workflow_name mapping
        
        # Pre-compile all available workflows
        self._compile_all_workflows()
    
    def _compile_all_workflows(self):
        """Compile all available workflow templates"""
        for name, workflow_def in WorkflowTemplates.get_all_templates().items():
            try:
                logger.info("compiling_workflow_template",
                           component="workflow",
                           workflow_name=name)
                
                # Compile the workflow
                compiled_graph = self.compiler.compile(workflow_def)
                self._compiled_workflows[name] = compiled_graph
                self._workflow_definitions[name] = workflow_def
                
                logger.info("workflow_compiled_successfully",
                           component="workflow",
                           workflow_name=name,
                           steps=len(workflow_def.steps))
            except Exception as e:
                logger.error("workflow_compilation_failed",
                            component="workflow",
                            workflow_name=name,
                            error=str(e))
    
    def get_workflow(self, name: str) -> Optional[Any]:
        """Get a compiled workflow by name"""
        return self._compiled_workflows.get(name)
    
    def get_workflow_definition(self, name: str) -> Optional[WorkflowDefinition]:
        """Get a workflow definition by name"""
        return self._workflow_definitions.get(name)
    
    def list_workflows(self) -> Dict[str, Dict[str, Any]]:
        """List all available workflows"""
        workflows = {}
        for name, definition in self._workflow_definitions.items():
            workflows[name] = {
                "name": definition.name,
                "description": definition.description,
                "trigger": definition.trigger,
                "steps": len(definition.steps)
            }
        return workflows
    
    def select_workflow(self, instruction: str) -> Optional[str]:
        """Select the appropriate workflow based on instruction"""
        return self.router.select_workflow(instruction)
    
    def get_interrupted_workflow(self, thread_id: str) -> Optional[str]:
        """Get the workflow name for an interrupted thread"""
        return self._interrupted_workflows.get(thread_id)
    
    async def execute_workflow(self, workflow_name: str, instruction: str, 
                             context: Dict[str, Any] = None,
                             thread_id: str = None) -> Dict[str, Any]:
        """Execute a workflow"""
        workflow = self.get_workflow(workflow_name)
        if not workflow:
            raise ValueError(f"Workflow '{workflow_name}' not found")
        
        # Prepare initial state
        initial_state: WorkflowState = {
            "workflow_id": f"wf_{workflow_name}_{thread_id or 'default'}",
            "workflow_name": workflow_name,
            "current_step": "",
            "status": "pending",
            "step_results": {},
            "variables": context or {},
            "human_inputs": {},
            "history": [],
            "original_instruction": instruction,
            "orchestrator_state_snapshot": context.get("orchestrator_state_snapshot") if context else None
        }
        
        # Configure execution
        config = {
            "configurable": {
                "thread_id": thread_id or f"workflow-{workflow_name}-default"
            }
        }
        
        logger.info("executing_compiled_workflow",
                   component="workflow",
                   workflow_name=workflow_name,
                   thread_id=thread_id,
                   instruction_preview=instruction[:100])
        
        try:
            # Execute the workflow
            result = await workflow.ainvoke(initial_state, config)
            
            # Debug log the result
            logger.info("workflow_result_debug",
                       component="workflow",
                       workflow_name=workflow_name,
                       thread_id=thread_id,
                       result_keys=list(result.keys()),
                       status=result.get("status"))
            
            # Check if the workflow was interrupted
            # LangGraph's interrupt() pauses execution, we need to check the state
            config = {"configurable": {"thread_id": thread_id}}
            state = workflow.get_state(config)
            
            # Log the state structure for debugging
            if state:
                logger.info("checking_workflow_state_for_interrupts",
                           component="workflow",
                           workflow_name=workflow_name,
                           thread_id=thread_id,
                           state_type=type(state).__name__,
                           has_tasks=hasattr(state, 'tasks'),
                           has_next=hasattr(state, 'next'),
                           tasks_count=len(state.tasks) if hasattr(state, 'tasks') and state.tasks else 0)
            
            if state and hasattr(state, 'tasks') and state.tasks:
                # Check if any task has interrupts
                for task in state.tasks:
                    if hasattr(task, 'interrupts') and task.interrupts:
                        logger.info("workflow_interrupt_detected_via_state",
                                   component="workflow",
                                   workflow_name=workflow_name,
                                   thread_id=thread_id,
                                   has_interrupt=True)
                        # Handle the interrupt
                        return await self._handle_interrupt(workflow, workflow_name, thread_id, None)
            
            logger.info("workflow_execution_complete",
                       component="workflow",
                       workflow_name=workflow_name,
                       thread_id=thread_id,
                       status=result.get("status"),
                       steps_executed=len(result.get("history", [])))
            
            # Clean up tracking if workflow completed
            if result.get("status") != "interrupted":
                self._interrupted_workflows.pop(thread_id, None)
            
            return result
        except Exception as e:
            # Check if this is a GraphInterrupt (expected for human-in-the-loop)
            if WorkflowErrorHandler.is_graph_interrupt(e):
                return await self._handle_interrupt(workflow, workflow_name, thread_id, e)
            
            WorkflowErrorHandler.handle_workflow_error(e, workflow_name, thread_id)
            raise
    
    async def resume_workflow(self, workflow_name: str, human_input: str, 
                            thread_id: str) -> Dict[str, Any]:
        """Resume an interrupted workflow with human input"""
        workflow = self.get_workflow(workflow_name)
        if not workflow:
            raise ValueError(f"Workflow '{workflow_name}' not found")
        
        # Configure for the specific thread
        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }
        
        # Get current state
        state = workflow.get_state(config)
        if not state or not hasattr(state, 'values'):
            raise ValueError(f"No interrupted state found for thread {thread_id}")
        
        current_step = state.values.get("current_step", "")
        
        logger.info("resuming_workflow_with_human_input",
                   component="workflow",
                   workflow_name=workflow_name,
                   thread_id=thread_id,
                   current_step=current_step,
                   human_input_preview=human_input[:100])
        
        try:
            # Resume the workflow using Command with the human input
            # LangGraph will pass this value back to the interrupt() call
            config["recursion_limit"] = WORKFLOW_DEFAULTS["recursion_limit"]
            result = await workflow.ainvoke(
                Command(resume=human_input),  # Use Command to resume with human input
                config
            )
            
            logger.info("workflow_resume_complete",
                       component="workflow",
                       workflow_name=workflow_name,
                       thread_id=thread_id,
                       status=result.get("status"),
                       steps_executed=len(result.get("history", [])))
            
            # Clean up tracking if workflow completed
            if result.get("status") != "interrupted":
                self._interrupted_workflows.pop(thread_id, None)
            
            return result
        except Exception as e:
            # Check if this is another interrupt
            if WorkflowErrorHandler.is_graph_interrupt(e):
                return await self._handle_interrupt(workflow, workflow_name, thread_id, e)
            
            WorkflowErrorHandler.handle_workflow_error(e, workflow_name, thread_id,
                                                     {"operation": "resume"})
            raise
    
    async def _handle_interrupt(self, workflow, workflow_name: str, 
                              thread_id: str, interrupt_exception) -> Dict[str, Any]:
        """Handle workflow interrupt consistently"""
        logger.info("workflow_interrupted_for_human_input",
                   component="workflow",
                   workflow_name=workflow_name,
                   thread_id=thread_id)
        
        # Extract interrupt data using centralized handler
        interrupt_data = WorkflowErrorHandler.extract_interrupt_data(
            workflow, thread_id, workflow_name
        )
        
        # Track this interrupted workflow
        self._interrupted_workflows[thread_id] = workflow_name
        
        # Return the interrupt data
        return {
            "status": "interrupted",
            "__interrupt__": interrupt_data
        }