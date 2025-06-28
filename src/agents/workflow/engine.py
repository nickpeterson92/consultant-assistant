"""Core workflow execution engine"""

import asyncio
import json
import re
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta

from src.utils.logging import get_logger
from src.utils.storage import AsyncStoreAdapter
from src.a2a import A2AClient, A2ATask
from src.orchestrator.agent_registry import AgentRegistry
from .models import (
    WorkflowInstance, WorkflowDefinition, WorkflowStep, 
    WorkflowStatus, StepType
)

logger = get_logger("workflow")


async def call_agent(agent_name: str, instruction: str, context: Dict[str, Any] = None, state_snapshot: Dict[str, Any] = None) -> Any:
    """Helper function to call an agent via A2A protocol
    
    Args:
        agent_name: Name of the agent to call
        instruction: Instruction for the agent
        context: Additional context for the agent
        state_snapshot: State snapshot from orchestrator to propagate
    """
    registry = AgentRegistry()
    agent = registry.get_agent(agent_name)
    
    if not agent:
        raise ValueError(f"Agent '{agent_name}' not found in registry")
    
    # Create A2A task with state snapshot
    task = A2ATask(
        id=f"workflow_{agent_name}_{int(datetime.now().timestamp())}",
        instruction=instruction,
        context=context or {},
        state_snapshot=state_snapshot or {}  # Use provided state or empty dict
    )
    
    # Execute A2A call
    async with A2AClient() as client:
        endpoint = agent.endpoint + "/a2a"
        result = await client.process_task(endpoint=endpoint, task=task)
        
        # Extract response from artifacts
        if result.get("artifacts"):
            artifact = result["artifacts"][0]
            return artifact.get("content", artifact)
        
        return result


class WorkflowEngine:
    """Core workflow execution engine"""
    
    def __init__(self, storage: AsyncStoreAdapter):
        self.storage = storage
        self.running_workflows: Dict[str, WorkflowInstance] = {}
        self.step_handlers = {
            StepType.ACTION: self._handle_action_step,
            StepType.CONDITION: self._handle_condition_step,
            StepType.WAIT: self._handle_wait_step,
            StepType.PARALLEL: self._handle_parallel_step,
            StepType.HUMAN: self._handle_human_step,
            StepType.SWITCH: self._handle_switch_step,
            StepType.FOR_EACH: self._handle_for_each_step,
        }
        self.workflow_namespace = ("workflow", "definitions")
        self.instance_namespace = ("workflow", "instances")
    
    async def execute_workflow(self, definition: WorkflowDefinition, 
                             initial_variables: Dict[str, Any] = None,
                             triggered_by: str = None) -> WorkflowInstance:
        """Execute a workflow from definition"""
        # Create instance
        instance = WorkflowInstance(
            id=f"wf_{definition.id}_{int(datetime.now().timestamp())}",
            workflow_id=definition.id,
            workflow_name=definition.name,
            status=WorkflowStatus.RUNNING,
            current_step="start",
            variables={**definition.variables, **(initial_variables or {})},
            triggered_by=triggered_by
        )
        
        # Store instance
        await self._save_instance(instance)
        self.running_workflows[instance.id] = instance
        
        logger.info("workflow_started",
                   component="workflow",
                   workflow_id=instance.id,
                   workflow_name=definition.name,
                   triggered_by=triggered_by)
        
        # Execute workflow
        try:
            await self._execute_steps(definition, instance)
            instance.status = WorkflowStatus.COMPLETED
            instance.completed_at = datetime.now()
            
            logger.info("workflow_completed",
                       component="workflow",
                       workflow_id=instance.id,
                       duration=(instance.completed_at - instance.created_at).total_seconds())
        except Exception as e:
            logger.error("workflow_failed", 
                        component="workflow",
                        workflow_id=instance.id,
                        error=str(e),
                        error_type=type(e).__name__)
            instance.status = WorkflowStatus.FAILED
            instance.error = str(e)
        finally:
            instance.updated_at = datetime.now()
            await self._save_instance(instance)
            self.running_workflows.pop(instance.id, None)
            
        return instance
    
    async def _execute_steps(self, definition: WorkflowDefinition, 
                           instance: WorkflowInstance):
        """Execute workflow steps"""
        current_step_id = "start"
        
        # Special handling for start step
        if "start" in definition.steps:
            current_step_id = await self._execute_single_step(
                definition.steps["start"], instance, definition
            )
        else:
            # If no explicit start, find first step
            current_step_id = next(iter(definition.steps.keys())) if definition.steps else None
        
        while current_step_id and current_step_id != "end":
            if current_step_id not in definition.steps:
                raise ValueError(f"Step '{current_step_id}' not found in workflow")
            
            step = definition.steps[current_step_id]
            current_step_id = await self._execute_single_step(step, instance, definition)
    
    async def _execute_single_step(self, step: WorkflowStep, 
                                 instance: WorkflowInstance,
                                 definition: WorkflowDefinition) -> Optional[str]:
        """Execute a single workflow step"""
        # Check skip condition first
        if step.skip_if:
            should_skip = self._evaluate_condition(step.skip_if, instance.variables)
            if should_skip:
                logger.info("workflow_step_skipped",
                           component="workflow",
                           workflow_id=instance.id,
                           step_id=step.id,
                           skip_condition=step.skip_if)
                return step.next_step
        
        instance.current_step = step.id
        instance.updated_at = datetime.now()
        await self._save_instance(instance)
        
        logger.info("workflow_step_start",
                   component="workflow",
                   workflow_id=instance.id,
                   step_id=step.id,
                   step_type=step.type,
                   step_name=step.name)
        
        # Execute step based on type
        handler = self.step_handlers.get(step.type)
        if not handler:
            raise ValueError(f"Unknown step type: {step.type}")
        
        start_time = datetime.now()
        try:
            next_step_id = await handler(step, instance, definition)
            
            # Record in history
            instance.history.append({
                "step_id": step.id,
                "step_name": step.name,
                "step_type": step.type.value,
                "timestamp": datetime.now().isoformat(),
                "duration_ms": int((datetime.now() - start_time).total_seconds() * 1000),
                "result": "completed",
                "next_step": next_step_id
            })
            
            logger.info("workflow_step_completed",
                       component="workflow",
                       workflow_id=instance.id,
                       step_id=step.id,
                       next_step=next_step_id)
            
            return next_step_id
            
        except Exception as e:
            instance.history.append({
                "step_id": step.id,
                "step_name": step.name,
                "step_type": step.type.value,
                "timestamp": datetime.now().isoformat(),
                "duration_ms": int((datetime.now() - start_time).total_seconds() * 1000),
                "result": "failed",
                "error": str(e)
            })
            raise
    
    async def _handle_action_step(self, step: WorkflowStep, 
                                instance: WorkflowInstance,
                                definition: WorkflowDefinition) -> Optional[str]:
        """Handle action steps - call agents"""
        # Variable substitution in instruction
        instruction = self._substitute_variables(step.instruction, instance.variables)
        
        logger.info("workflow_action_step",
                   component="workflow",
                   workflow_id=instance.id,
                   agent=step.agent,
                   instruction_full=instruction)
        
        # Prepare context with workflow info
        context = {
            "workflow_id": instance.id,
            "workflow_name": definition.name,
            "step_id": step.id,
            "step_name": step.name,
            "workflow_variables": instance.variables
        }
        
        # Call agent with retry logic
        retry_policy = step.retry_policy or {"max_retries": 3, "delay": 1}
        max_retries = retry_policy.get("max_retries", 3)
        retry_delay = retry_policy.get("delay", 1)
        
        for attempt in range(max_retries):
            try:
                # Use the agent registry to call agents
                # Get state snapshot from workflow variables (passed from orchestrator)
                state_snapshot = instance.variables.get("orchestrator_state_snapshot", {})
                
                result = await call_agent(
                    agent_name=step.agent,
                    instruction=instruction,
                    context=context,
                    state_snapshot=state_snapshot
                )
                
                # Log the full response for debugging
                logger.info("workflow_step_response",
                           component="workflow",
                           workflow_id=instance.id,
                           step_id=step.id,
                           step_name=step.name,
                           agent=step.agent,
                           response_type=type(result).__name__,
                           response_length=len(str(result)) if result else 0,
                           response_full=result)
                
                # Store result in variables
                instance.variables[f"{step.id}_result"] = result
                instance.variables["last_action_result"] = result
                
                # Handle conditional next step
                if step.on_complete:
                    condition = step.on_complete.get("condition")
                    if condition:
                        if self._evaluate_condition(condition, instance.variables):
                            return step.on_complete.get("if_true", step.next_step)
                        else:
                            return step.on_complete.get("if_false", step.next_step)
                
                return step.next_step
                
            except Exception as e:
                logger.warning("workflow_action_retry",
                             component="workflow",
                             workflow_id=instance.id,
                             step_id=step.id,
                             attempt=attempt + 1,
                             error=str(e))
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                else:
                    raise
    
    async def _handle_condition_step(self, step: WorkflowStep,
                                   instance: WorkflowInstance,
                                   definition: WorkflowDefinition) -> Optional[str]:
        """Handle conditional branching"""
        condition = step.condition
        if not condition:
            raise ValueError(f"Condition step {step.id} has no condition defined")
        
        # Evaluate condition
        result = self._evaluate_condition(condition, instance.variables)
        
        logger.info("workflow_condition_evaluated",
                   component="workflow",
                   workflow_id=instance.id,
                   step_id=step.id,
                   condition=condition,
                   result=result)
        
        # Store result
        instance.variables[f"{step.id}_result"] = result
        
        return step.true_next if result else step.false_next
    
    async def _handle_wait_step(self, step: WorkflowStep,
                              instance: WorkflowInstance,
                              definition: WorkflowDefinition) -> Optional[str]:
        """Handle wait steps"""
        if step.wait_until:
            wait_seconds = (step.wait_until - datetime.now()).total_seconds()
            if wait_seconds > 0:
                instance.status = WorkflowStatus.WAITING
                await self._save_instance(instance)
                
                logger.info("workflow_waiting",
                           component="workflow",
                           workflow_id=instance.id,
                           step_id=step.id,
                           wait_seconds=wait_seconds)
                
                # For production, use a proper scheduler
                # For now, async sleep with max 60 seconds
                await asyncio.sleep(min(wait_seconds, 60))
                
                instance.status = WorkflowStatus.RUNNING
        
        elif step.wait_for_event:
            # Handle special compile events
            if step.wait_for_event and step.wait_for_event.endswith("_complete") and step.metadata:
                # Compile results from specified fields
                compile_fields = step.metadata.get("compile_fields", [])
                summary_template = step.metadata.get("summary_template", "Workflow completed successfully")
                
                compiled_results = {}
                for field in compile_fields:
                    if field in instance.variables:
                        compiled_results[field] = instance.variables[field]
                
                # Store compiled results
                instance.variables["compiled_results"] = compiled_results
                instance.variables["summary"] = summary_template
                
                logger.info("workflow_results_compiled",
                           component="workflow",
                           workflow_id=instance.id,
                           step_id=step.id,
                           fields_compiled=len(compiled_results))
            else:
                # Regular event wait
                logger.info("workflow_waiting_for_event",
                           component="workflow",
                           workflow_id=instance.id,
                           step_id=step.id,
                           event=step.wait_for_event)
                # For now, just continue
                pass
        
        return step.next_step
    
    async def _handle_parallel_step(self, step: WorkflowStep,
                                  instance: WorkflowInstance,
                                  definition: WorkflowDefinition) -> Optional[str]:
        """Handle parallel execution"""
        if not step.parallel_steps:
            return step.next_step
        
        parallel_tasks = []
        
        for step_id in step.parallel_steps:
            if step_id in definition.steps:
                parallel_step = definition.steps[step_id]
                task = asyncio.create_task(
                    self._execute_single_step(parallel_step, instance, definition)
                )
                parallel_tasks.append((step_id, task))
            else:
                logger.warning("workflow_parallel_step_not_found",
                             component="workflow",
                             workflow_id=instance.id,
                             step_id=step_id)
        
        # Wait for all parallel steps
        results = []
        for step_id, task in parallel_tasks:
            try:
                result = await task
                results.append((step_id, result))
            except Exception as e:
                logger.error("workflow_parallel_step_failed",
                           component="workflow",
                           workflow_id=instance.id,
                           step_id=step_id,
                           error=str(e))
                results.append((step_id, {"error": str(e)}))
        
        # Store results
        instance.variables[f"{step.id}_parallel_results"] = results
        
        return step.next_step
    
    async def _handle_human_step(self, step: WorkflowStep,
                               instance: WorkflowInstance,
                               definition: WorkflowDefinition) -> Optional[str]:
        """Handle human approval steps"""
        instance.status = WorkflowStatus.WAITING
        await self._save_instance(instance)
        
        logger.info("workflow_awaiting_human_input",
                   component="workflow",
                   workflow_id=instance.id,
                   step_id=step.id,
                   step_name=step.name)
        
        # In production, this would create a task in a task queue
        # For now, we'll simulate approval after a short wait
        await asyncio.sleep(5)
        
        # Simulate approval
        instance.variables[f"{step.id}_approval"] = {
            "approved": True,
            "approved_by": "system",
            "approved_at": datetime.now().isoformat(),
            "notes": "Auto-approved for demo"
        }
        
        instance.status = WorkflowStatus.RUNNING
        return step.next_step
    
    async def _handle_switch_step(self, step: WorkflowStep,
                                instance: WorkflowInstance,
                                definition: WorkflowDefinition) -> Optional[str]:
        """Handle switch statements with multiple conditions"""
        if not step.switch_conditions:
            return step.default_next or step.next_step
        
        # Evaluate each condition in order
        for case in step.switch_conditions:
            condition = case.get("case")
            if condition and self._evaluate_condition(condition, instance.variables):
                next_step = case.get("goto")
                logger.info("workflow_switch_match",
                           component="workflow",
                           workflow_id=instance.id,
                           step_id=step.id,
                           matched_condition=condition,
                           next_step=next_step)
                return next_step
        
        # No conditions matched, use default
        logger.info("workflow_switch_default",
                   component="workflow",
                   workflow_id=instance.id,
                   step_id=step.id,
                   default_next=step.default_next)
        
        return step.default_next or step.next_step
    
    async def _handle_for_each_step(self, step: WorkflowStep,
                                  instance: WorkflowInstance,
                                  definition: WorkflowDefinition) -> Optional[str]:
        """Handle for-each loops over collections"""
        if not step.iterate_over or not step.loop_steps:
            return step.next_step
        
        # Get the collection to iterate over
        collection = self._resolve_variable(f"${step.iterate_over}", instance.variables)
        if not isinstance(collection, (list, tuple)):
            logger.warning("workflow_for_each_invalid_collection",
                         component="workflow",
                         workflow_id=instance.id,
                         step_id=step.id,
                         collection_type=type(collection).__name__)
            return step.next_step
        
        # Apply iteration limit
        max_iterations = step.max_iterations or 100
        items_to_process = collection[:max_iterations]
        
        logger.info("workflow_for_each_start",
                   component="workflow",
                   workflow_id=instance.id,
                   step_id=step.id,
                   collection_size=len(collection),
                   processing_count=len(items_to_process))
        
        # Process each item
        loop_results = []
        iterator_var = step.iterator_variable or "current_item"
        
        for idx, item in enumerate(items_to_process):
            # Set iterator variable
            instance.variables[iterator_var] = item
            instance.variables[f"{iterator_var}_index"] = idx
            
            # Execute loop steps
            for loop_step_id in step.loop_steps:
                if loop_step_id in definition.steps:
                    loop_step = definition.steps[loop_step_id]
                    try:
                        await self._execute_single_step(loop_step, instance, definition)
                    except Exception as e:
                        logger.error("workflow_for_each_iteration_error",
                                   component="workflow",
                                   workflow_id=instance.id,
                                   step_id=step.id,
                                   iteration=idx,
                                   error=str(e))
                        # Continue with next iteration
                        continue
            
            # Collect results
            if f"{loop_step_id}_result" in instance.variables:
                loop_results.append(instance.variables[f"{loop_step_id}_result"])
        
        # Store aggregated results
        instance.variables[f"{step.id}_results"] = loop_results
        
        # Clean up iterator variable
        instance.variables.pop(iterator_var, None)
        instance.variables.pop(f"{iterator_var}_index", None)
        
        logger.info("workflow_for_each_complete",
                   component="workflow",
                   workflow_id=instance.id,
                   step_id=step.id,
                   iterations_completed=len(items_to_process))
        
        return step.next_step
    
    def _substitute_variables(self, text: str, variables: Dict[str, Any]) -> str:
        """Replace {variable} with actual values"""
        if not text:
            return text
            
        pattern = r'\{(\w+(?:\.\w+)*)\}'
        
        def replacer(match):
            var_path = match.group(1)
            parts = var_path.split('.')
            
            value = variables
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return match.group(0)  # Keep original if not found
            
            # Check if the value is an error message
            value_str = str(value)
            if any(err_pattern in value_str.lower() for err_pattern in [
                "error processing", 
                "query complexity exceeded",
                "recursion limit",
                "failed to",
                "error:"
            ]):
                # Return a placeholder instead of propagating the error
                return f"[Previous step failed: {var_path}]"
            
            return value_str
        
        return re.sub(pattern, replacer, text)
    
    def _evaluate_condition(self, condition: Dict[str, Any], 
                          variables: Dict[str, Any]) -> bool:
        """Evaluate conditions with variable resolution"""
        # Handle new condition types
        condition_type = condition.get("type")
        if condition_type:
            return self._evaluate_typed_condition(condition, variables)
        
        # Legacy operator-based conditions
        operator = condition.get("operator", "equals")
        left = condition.get("left")
        right = condition.get("right")
        
        # Resolve variable references
        left = self._resolve_variable(left, variables)
        right = self._resolve_variable(right, variables)
        
        # Evaluate based on operator
        try:
            if operator == "equals":
                return left == right
            elif operator == "not_equals":
                return left != right
            elif operator == "greater_than":
                return float(left) > float(right)
            elif operator == "less_than":
                return float(left) < float(right)
            elif operator == "greater_equal":
                return float(left) >= float(right)
            elif operator == "less_equal":
                return float(left) <= float(right)
            elif operator == "contains":
                return str(right) in str(left)
            elif operator == "not_contains":
                return str(right) not in str(left)
            elif operator == "exists":
                return left is not None
            elif operator == "not_exists":
                return left is None
            elif operator == "in":
                return left in right if isinstance(right, (list, tuple)) else False
            elif operator == "not_in":
                return left not in right if isinstance(right, (list, tuple)) else True
            else:
                logger.warning("Unknown condition operator",
                             operator=operator)
                return False
        except Exception as e:
            logger.error("Condition evaluation error",
                        error=str(e),
                        operator=operator,
                        left=left,
                        right=right)
            return False
    
    def _evaluate_typed_condition(self, condition: Dict[str, Any], 
                                variables: Dict[str, Any]) -> bool:
        """Evaluate typed conditions (new format)"""
        condition_type = condition.get("type")
        variable_name = condition.get("variable")
        
        # Get variable value
        if variable_name:
            value = self._resolve_variable(f"${variable_name}", variables)
        else:
            value = None
        
        try:
            if condition_type == "is_empty":
                if isinstance(value, (list, dict, str)):
                    return len(value) == 0
                return value is None
            
            elif condition_type == "is_not_empty":
                if isinstance(value, (list, dict, str)):
                    return len(value) > 0
                return value is not None
            
            elif condition_type == "count_greater_than":
                target = condition.get("value", 0)
                if isinstance(value, (list, dict)):
                    return len(value) > target
                return False
            
            elif condition_type == "count_less_than":
                target = condition.get("value", 0)
                if isinstance(value, (list, dict)):
                    return len(value) < target
                return False
            
            elif condition_type == "contains":
                target = condition.get("value", "")
                return target in str(value)
            
            elif condition_type == "equals":
                target = condition.get("value")
                return value == target
            
            elif condition_type == "response_contains":
                # Check last action result
                last_result = variables.get("last_action_result", "")
                target = condition.get("value", "")
                return target.lower() in str(last_result).lower()
            
            elif condition_type == "has_error":
                # Check if last result contains error indicators
                last_result = str(variables.get("last_action_result", ""))
                error_indicators = ["error", "failed", "exception", "traceback"]
                return any(indicator in last_result.lower() for indicator in error_indicators)
            
            else:
                logger.warning("Unknown condition type",
                             condition_type=condition_type)
                return False
                
        except Exception as e:
            logger.error("Typed condition evaluation error",
                        error=str(e),
                        condition_type=condition_type,
                        value=value)
            return False
    
    def _resolve_variable(self, value: Any, variables: Dict[str, Any]) -> Any:
        """Resolve variable references starting with $"""
        if isinstance(value, str) and value.startswith("$"):
            var_path = value[1:]  # Remove $
            parts = var_path.split('.')
            
            result = variables
            for part in parts:
                if isinstance(result, dict) and part in result:
                    result = result[part]
                else:
                    return None
            return result
        return value
    
    async def _save_instance(self, instance: WorkflowInstance):
        """Save workflow instance to storage"""
        try:
            await self.storage.put(
                self.instance_namespace,
                instance.id,
                instance.model_dump_json()
            )
        except Exception as e:
            logger.error("Failed to save workflow instance",
                        component="workflow",
                        workflow_id=instance.id,
                        error=str(e))
    
    async def load_instance(self, instance_id: str) -> Optional[WorkflowInstance]:
        """Load workflow instance from storage"""
        try:
            data = await self.storage.get(self.instance_namespace, instance_id)
            if data:
                return WorkflowInstance.model_validate_json(data)
        except Exception as e:
            logger.error("Failed to load workflow instance",
                        component="workflow",
                        instance_id=instance_id,
                        error=str(e))
        return None
    
    async def save_definition(self, definition: WorkflowDefinition):
        """Save workflow definition to storage"""
        try:
            await self.storage.put(
                self.workflow_namespace,
                definition.id,
                definition.model_dump_json()
            )
            logger.info("Workflow definition saved",
                       component="workflow",
                       workflow_id=definition.id,
                       workflow_name=definition.name)
        except Exception as e:
            logger.error("Failed to save workflow definition",
                        component="workflow",
                        workflow_id=definition.id,
                        error=str(e))
            raise
    
    async def load_definition(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        """Load workflow definition from storage"""
        try:
            data = await self.storage.get(self.workflow_namespace, workflow_id)
            if data:
                return WorkflowDefinition.model_validate_json(data)
        except Exception as e:
            logger.error("Failed to load workflow definition",
                        component="workflow",
                        workflow_id=workflow_id,
                        error=str(e))
        return None