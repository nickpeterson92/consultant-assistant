"""Workflow Compiler - Converts declarative workflow templates to LangGraph graphs"""

import asyncio
import json
from typing import Dict, Any, Optional, Callable, Annotated
from typing_extensions import TypedDict
import operator

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
from langchain_core.messages import HumanMessage

from src.utils.logging import get_logger
from .models import WorkflowDefinition, WorkflowStep, StepType, WorkflowStatus
# Removed old engine import - we'll implement call_agent here
from src.a2a import A2AClient, A2ATask
from .config import AGENT_PORTS, WORKFLOW_DEFAULTS
from .utils import safe_variable_substitution

logger = get_logger("workflow")


async def call_agent(agent_name: str, instruction: str, context: Dict[str, Any], state_snapshot: Dict[str, Any]) -> str:
    """Call an agent via A2A protocol"""
    
    port = AGENT_PORTS.get(agent_name)
    if not port:
        raise ValueError(f"Unknown agent: {agent_name}")
    
    # A2AClient doesn't take endpoint in constructor, just timeout
    client = A2AClient()
    
    try:
        # Create task object
        task = A2ATask(
            id=f"workflow-{context.get('workflow_id', 'unknown')}-{context.get('step_id', 'unknown')}",
            instruction=instruction,
            context=context,
            state_snapshot=state_snapshot
        )
        
        response = await client.process_task(
            endpoint=f"http://localhost:{port}/a2a",
            task=task
        )
        
        # Extract the actual content from the response
        if response.get("artifacts"):
            artifact = response["artifacts"][0]
            return artifact.get("content", "")
        
        return str(response)
    except Exception as e:
        logger.error("agent_call_failed",
                    component="workflow",
                    agent=agent_name,
                    error=str(e))
        raise


class WorkflowState(TypedDict, total=False):
    """Universal workflow state that can handle any workflow"""
    # Core workflow tracking
    workflow_id: str
    workflow_name: str
    current_step: str
    status: str
    
    # Step results and variables - stores all intermediate results
    step_results: Annotated[Dict[str, Any], lambda x, y: {**x, **y}]
    variables: Annotated[Dict[str, Any], lambda x, y: {**x, **y}]
    
    # For human interactions
    human_inputs: Annotated[Dict[str, Any], lambda x, y: {**x, **y}]
    
    # Execution history
    history: Annotated[list, operator.add]
    
    # Original context
    original_instruction: str
    orchestrator_state_snapshot: Optional[Dict[str, Any]]
    
    # Remove __interrupt__ - it's reserved in LangGraph


class WorkflowCompiler:
    """Compiles declarative workflow definitions into executable LangGraph graphs"""
    
    def __init__(self):
        self.logger = get_logger("workflow")
        # Create dispatch table for step types
        self._step_handlers = {
            StepType.ACTION: self._create_action_node,
            StepType.HUMAN: self._create_human_node,
            StepType.CONDITION: self._create_condition_node,
            StepType.WAIT: self._create_wait_node,
            StepType.PARALLEL: self._create_parallel_node,
            StepType.SWITCH: self._create_switch_node,
            StepType.FOR_EACH: self._create_for_each_node,
            StepType.EXTRACT: self._create_extract_node
        }
        
    def compile(self, definition: WorkflowDefinition) -> StateGraph:
        """Compile a workflow definition into a LangGraph graph"""
        
        # Create the state graph
        workflow = StateGraph(WorkflowState)
        
        # Add a start node that initializes the workflow
        workflow.add_node("workflow_init", self._create_start_node(definition))
        workflow.set_entry_point("workflow_init")
        
        # Add all workflow steps as nodes
        for step_id, step in definition.steps.items():
            node_func = self._create_node_for_step(step, definition)
            workflow.add_node(step_id, node_func)
        
        # Add edges based on workflow flow
        workflow.add_edge("workflow_init", "start" if "start" in definition.steps else list(definition.steps.keys())[0])
        
        # Add workflow completion node
        workflow.add_node("workflow_complete", self._create_completion_node(definition))
        
        for step_id, step in definition.steps.items():
            if step.type == StepType.CONDITION:
                # Add conditional edges
                # Handle "end" as a special case
                true_target = END if step.true_next == "end" else (step.true_next or END)
                false_target = END if step.false_next == "end" else (step.false_next or END)
                
                workflow.add_conditional_edges(
                    step_id,
                    self._create_condition_function(step),
                    {
                        "true": true_target,
                        "false": false_target
                    }
                )
            elif step.type == StepType.SWITCH:
                # Add switch edges
                routes = {}
                for i, case in enumerate(step.switch_conditions or []):
                    goto = case.get("goto", END)
                    routes[f"case_{i}"] = END if goto == "end" else goto
                default_target = step.default_next or END
                routes["default"] = END if default_target == "end" else default_target
                
                workflow.add_conditional_edges(
                    step_id,
                    self._create_switch_function(step),
                    routes
                )
            else:
                # Normal edge
                if step.next_step:
                    workflow.add_edge(step_id, step.next_step)
                else:
                    # Route to completion node instead of END
                    workflow.add_edge(step_id, "workflow_complete")
        
        # Add edge from completion node to END
        workflow.add_edge("workflow_complete", END)
        
        # Compile with checkpointer for persistence
        checkpointer = MemorySaver()
        return workflow.compile(checkpointer=checkpointer)
    
    def _create_completion_node(self, definition: WorkflowDefinition) -> Callable:
        """Create the workflow completion node"""
        def completion_node(state: WorkflowState) -> Dict[str, Any]:
            logger.info("workflow_completed",
                component="workflow",
                workflow_id=state.get("workflow_id"),
                workflow_name=state.get("workflow_name"),
                steps_executed=len(state.get("history", []))
            )
            
            return {
                "status": WorkflowStatus.COMPLETED.value,
                "current_step": "completed"
            }
        return completion_node
    
    def _create_start_node(self, definition: WorkflowDefinition) -> Callable:
        """Create the initialization node"""
        def start_node(state: WorkflowState) -> Dict[str, Any]:
            return {
                "workflow_id": definition.id,
                "workflow_name": definition.name,
                "status": WorkflowStatus.RUNNING.value,
                "current_step": "start",
                "variables": {**definition.variables, **state.get("variables", {})},
                "step_results": {},
                "human_inputs": {},
                "history": [{
                    "step": "workflow_init",
                    "action": "workflow_initialized",
                    "timestamp": self._get_timestamp()
                }]
            }
        return start_node
    
    def _create_node_for_step(self, step: WorkflowStep, definition: WorkflowDefinition) -> Callable:
        """Create a LangGraph node function for a workflow step"""
        
        handler = self._step_handlers.get(step.type)
        if not handler:
            raise ValueError(f"Unknown step type: {step.type}")
        
        # Special handling for steps that need the definition
        if step.type in (StepType.PARALLEL, StepType.FOR_EACH):
            return handler(step, definition)
        return handler(step)
    
    def _create_action_node(self, step: WorkflowStep) -> Callable:
        """Create an action node that calls an agent"""
        async def action_node(state: WorkflowState) -> Dict[str, Any]:
            # Substitute variables in the instruction
            instruction = self._substitute_variables(step.instruction, state)
            
            logger.info("workflow_action_node_executing",
                       component="workflow",
                       workflow_id=state["workflow_id"],
                       step_id=step.id,
                       agent=step.agent,
                       instruction_preview=instruction[:100] if instruction else "")
            
            try:
                # Call the agent
                result = await call_agent(
                    agent_name=step.agent,
                    instruction=instruction,
                    context={
                        "workflow_id": state["workflow_id"],
                        "workflow_name": state["workflow_name"],
                        "step_id": step.id,
                        "step_name": step.name,
                        "variables": state["variables"]
                    },
                    state_snapshot=state.get("orchestrator_state_snapshot", {})
                )
                
                # Store the result
                return {
                    "current_step": step.id,
                    "step_results": {
                        step.id: result,
                        f"{step.id}_result": result
                    },
                    "variables": {
                        f"{step.id}_result": result,
                        "last_action_result": result
                    },
                    "history": [{
                        "step": step.id,
                        "action": "completed",
                        "result": str(result)[:200]
                    }]
                }
            except Exception as e:
                logger.error("workflow_action_node_error",
                           component="workflow",
                           workflow_id=state["workflow_id"],
                           step_id=step.id,
                           error=str(e))
                
                if step.critical:
                    raise
                
                return {
                    "current_step": step.id,
                    "step_results": {
                        f"{step.id}_error": str(e)
                    },
                    "history": [{
                        "step": step.id,
                        "action": "failed",
                        "error": str(e)
                    }]
                }
        
        return action_node
    
    def _create_human_node(self, step: WorkflowStep) -> Callable:
        """Create a human interaction node"""
        async def human_node(state: WorkflowState) -> Dict[str, Any]:
            logger.info("workflow_human_node_executing",
                       component="workflow",
                       workflow_id=state["workflow_id"],
                       step_id=step.id)
            
            # Build context dynamically from state and step metadata
            context = {
                "step_results": state.get("step_results", {}),
                "variables": state.get("variables", {}),
                "history": state.get("history", [])[-WORKFLOW_DEFAULTS["history_window"]:],  # Recent history
                "instruction": step.description or f"Human input needed for {step.name}"
            }
            
            # Add any step-specific context from metadata
            if step.metadata:
                # metadata can specify which previous results to include
                if "context_from" in step.metadata:
                    for prev_step in step.metadata["context_from"]:
                        if prev_step in state["step_results"]:
                            context[prev_step] = state["step_results"][prev_step]
                
                # Add any additional context fields from metadata
                for key, value in step.metadata.items():
                    if key not in ["context_from"]:
                        context[key] = value
            
            # Use LangGraph's interrupt to pause for human input
            human_response = interrupt({
                "step_id": step.id,
                "step_name": step.name,
                "description": step.description,
                "workflow_id": state["workflow_id"],
                "workflow_name": state["workflow_name"],
                "context": context,
                "metadata": step.metadata or {}
            })
            
            # Store the human response generically
            return {
                "current_step": step.id,
                "human_inputs": {
                    step.id: human_response
                },
                "variables": {
                    f"{step.id}_response": human_response,
                    "last_human_response": human_response
                },
                "history": [{
                    "step": step.id,
                    "action": "human_input_received",
                    "response": str(human_response)[:100]
                }]
            }
        
        return human_node
    
    def _create_condition_node(self, step: WorkflowStep) -> Callable:
        """Create a condition evaluation node"""
        async def condition_node(state: WorkflowState) -> Dict[str, Any]:
            # Condition evaluation happens in the edge function
            # This node just records the evaluation
            return {
                "current_step": step.id,
                "history": [{
                    "step": step.id,
                    "action": "condition_evaluated"
                }]
            }
        return condition_node
    
    def _create_condition_function(self, step: WorkflowStep) -> Callable:
        """Create the edge function for conditional routing"""
        def condition_func(state: WorkflowState) -> str:
            result = self._evaluate_condition(step.condition, state)
            logger.info("workflow_condition_evaluated",
                       component="workflow",
                       workflow_id=state["workflow_id"],
                       step_id=step.id,
                       condition=step.condition,
                       result=result)
            return "true" if result else "false"
        return condition_func
    
    def _create_switch_node(self, step: WorkflowStep) -> Callable:
        """Create a switch node"""
        async def switch_node(state: WorkflowState) -> Dict[str, Any]:
            return {
                "current_step": step.id,
                "history": [{
                    "step": step.id,
                    "action": "switch_evaluated"
                }]
            }
        return switch_node
    
    def _create_switch_function(self, step: WorkflowStep) -> Callable:
        """Create the edge function for switch routing"""
        def switch_func(state: WorkflowState) -> str:
            for i, case in enumerate(step.switch_conditions or []):
                condition = case.get("case")
                if condition and self._evaluate_condition(condition, state):
                    return f"case_{i}"
            return "default"
        return switch_func
    
    def _create_extract_node(self, step: WorkflowStep) -> Callable:
        """Create an extraction node that uses direct LLM call for parsing"""
        async def extract_node(state: WorkflowState) -> Dict[str, Any]:
            logger.info("workflow_extract_node_executing",
                       component="workflow",
                       workflow_id=state["workflow_id"],
                       step_id=step.id,
                       extract_from=step.extract_from)
            
            try:
                # Get the source data to extract from
                source_data = self._resolve_variable(f"${step.extract_from}", state) if step.extract_from else ""
                
                # If source data is empty, return empty result
                if not source_data:
                    logger.warning("workflow_extract_node_empty_source",
                               component="workflow",
                               workflow_id=state["workflow_id"],
                               step_id=step.id)
                    return {
                        "current_step": step.id,
                        "step_results": {
                            step.id: "",
                            f"{step.id}_result": ""
                        },
                        "variables": {
                            f"{step.id}_result": "",
                            "last_extract_result": ""
                        },
                        "history": [{
                            "step": step.id,
                            "action": "completed",
                            "result": "Empty source data"
                        }]
                    }
                
                # Build extraction instruction using extract_prompt
                extraction_prompt = step.extract_prompt or f"Extract the value from: {source_data}"
                
                # Substitute variables in the prompt
                extraction_prompt = self._substitute_variables(extraction_prompt, state)
                
                # Check if structured extraction is requested
                from src.utils.llm import create_deterministic_llm
                from .extraction_prompts import get_extraction_prompt
                
                llm = create_deterministic_llm()
                
                if step.extract_model:
                    # Use TrustCall with specified model
                    from trustcall import create_extractor
                    from . import extraction_models
                    
                    # Dynamically get the model class
                    model_class = getattr(extraction_models, step.extract_model, None)
                    
                    if model_class:
                        extractor = create_extractor(
                            llm,
                            tools=[model_class],
                            tool_choice=step.extract_model
                        )
                        
                        # Use structured extraction prompt for TrustCall
                        # Format similar to TRUSTCALL_INSTRUCTION from salesforce_prompts.py
                        prompt = f"""Extract the following structured data from the provided information.

{extraction_prompt}

Return a structured {step.extract_model} object with these fields:
"""
                        
                        # Add model-specific field descriptions
                        if step.extract_model == "OnboardingDetails":
                            prompt += """- account_id: The Salesforce Account ID (18-character string starting with 001)
- account_name: The full account/company name
- opportunity_id: The Salesforce Opportunity ID (18-character string starting with 006)
- opportunity_name: The full opportunity/deal name

Rules:
1. Extract ONLY from the provided data, do not make up values
2. Use the exact IDs and names as they appear in the source
3. If a field is not found, leave it empty

Source data:
""" + str(source_data)
                        else:
                            # Generic structured extraction
                            prompt += f"""Extract all relevant fields for {step.extract_model} from the source data.

Source data:
{source_data}"""
                        
                        try:
                            # TrustCall uses invoke, not aextract
                            result = await asyncio.to_thread(
                                extractor.invoke,
                                {"messages": [("human", prompt)]}
                            )
                            
                            # TrustCall returns a dict with the model name as key
                            logger.info("trustcall_raw_result",
                                       component="workflow",
                                       step_id=step.id,
                                       result_type=type(result).__name__,
                                       result_keys=list(result.keys()) if isinstance(result, dict) else None)
                            
                            # Extract the actual model instance
                            # TrustCall returns {"responses": [model_instance], "response_metadata": [...]}
                            if isinstance(result, dict) and 'responses' in result:
                                responses = result.get('responses', [])
                                if responses and len(responses) > 0:
                                    extracted = responses[0]  # Get first response
                                    logger.info("trustcall_extracted_model",
                                               component="workflow",
                                               step_id=step.id,
                                               model_type=type(extracted).__name__)
                                else:
                                    logger.warning("trustcall_empty_responses",
                                                 component="workflow",
                                                 step_id=step.id)
                                    extracted = None
                            else:
                                # Fallback if result structure is different
                                logger.warning("trustcall_unexpected_format",
                                             component="workflow",
                                             step_id=step.id,
                                             result_type=type(result).__name__)
                                extracted = result
                            
                            # Flatten extracted data into simple variables
                            flattened_vars = {}
                            if step.extract_model == "OnboardingDetails" and hasattr(extracted, 'account_id'):
                                # Flatten all fields into top-level variables
                                flattened_vars["account_id"] = extracted.account_id
                                flattened_vars["account_name"] = extracted.account_name
                                flattened_vars["opportunity_id"] = extracted.opportunity_id
                                flattened_vars["opportunity_name"] = extracted.opportunity_name
                                
                                # Store a summary for logging/debugging
                                result = f"Extracted: {extracted.account_name} ({extracted.account_id})"
                            else:
                                # Generic: flatten all fields from the model
                                if hasattr(extracted, 'dict'):
                                    for field_name, field_value in extracted.dict().items():
                                        if isinstance(field_value, (str, int, float, bool)):
                                            flattened_vars[field_name] = field_value
                                    result = f"Extracted {step.extract_model} successfully"
                                else:
                                    # Extraction failed, log for debugging
                                    logger.warning("trustcall_extraction_no_model",
                                                 component="workflow",
                                                 step_id=step.id,
                                                 extracted_type=type(extracted).__name__)
                                    result = str(extracted)[:200]
                            
                            logger.info("workflow_structured_extraction_success",
                                       component="workflow",
                                       workflow_id=state["workflow_id"],
                                       step_id=step.id,
                                       model=step.extract_model)
                        except Exception as e:
                            logger.warning("workflow_structured_extraction_failed",
                                         component="workflow",
                                         workflow_id=state["workflow_id"],
                                         step_id=step.id,
                                         model=step.extract_model,
                                         error=str(e))
                            # Fallback to direct extraction
                            flattened_vars = {}  # Empty for fallback
                            messages = [
                                {"role": "system", "content": get_extraction_prompt()},
                                {"role": "user", "content": f"{extraction_prompt}\n\nSource data:\n{source_data}"}
                            ]
                            response = await llm.ainvoke(messages)
                            result = response.content.strip()
                    else:
                        logger.error("workflow_extraction_model_not_found",
                                   component="workflow",
                                   workflow_id=state["workflow_id"],
                                   step_id=step.id,
                                   model=step.extract_model)
                        # Fallback to direct extraction
                        flattened_vars = {}  # Model not found
                        messages = [
                            {"role": "system", "content": get_extraction_prompt()},
                            {"role": "user", "content": f"{extraction_prompt}\n\nSource data:\n{str(source_data)[:2000]}"}
                        ]
                        response = await llm.ainvoke(messages)
                        result = response.content.strip()
                else:
                    # Use direct LLM extraction
                    flattened_vars = {}  # No structured extraction
                    messages = [
                        {"role": "system", "content": get_extraction_prompt()},
                        {"role": "user", "content": f"{extraction_prompt}\n\nSource data:\n{str(source_data)[:2000]}"}
                    ]
                    response = await llm.ainvoke(messages)
                    result = response.content.strip()
                
                logger.info("workflow_extract_node_completed",
                           component="workflow",
                           workflow_id=state["workflow_id"],
                           step_id=step.id,
                           extracted_value=result[:100])
                
                # Prepare variables update - include flattened vars if extraction succeeded
                variables_update = {
                    f"{step.id}_result": result,
                    "last_extract_result": result
                }
                
                # Add flattened variables from structured extraction
                if 'flattened_vars' in locals() and flattened_vars:
                    variables_update.update(flattened_vars)
                    logger.info("workflow_extract_flattened_vars",
                               component="workflow",
                               workflow_id=state["workflow_id"],
                               step_id=step.id,
                               flattened_vars=list(flattened_vars.keys()))
                
                # Store the extracted result
                return {
                    "current_step": step.id,
                    "step_results": {
                        step.id: result,
                        f"{step.id}_result": result
                    },
                    "variables": variables_update,
                    "history": [{
                        "step": step.id,
                        "action": "completed",
                        "result": f"Extracted: {result[:100]}"
                    }]
                }
            except Exception as e:
                logger.error("workflow_extract_node_error",
                           component="workflow",
                           workflow_id=state["workflow_id"],
                           step_id=step.id,
                           error=str(e))
                
                if step.critical:
                    raise
                
                return {
                    "current_step": step.id,
                    "step_results": {
                        f"{step.id}_error": str(e)
                    },
                    "history": [{
                        "step": step.id,
                        "action": "failed",
                        "error": str(e)
                    }]
                }
        
        return extract_node
    
    def _create_wait_node(self, step: WorkflowStep) -> Callable:
        """Create a wait node"""
        async def wait_node(state: WorkflowState) -> Dict[str, Any]:
            # For now, just record the wait and mark as completed
            # In production, this would handle actual waiting
            logger.info("workflow_wait_node_executing",
                component="workflow",
                workflow_id=state.get("workflow_id"),
                step_id=step.id,
                wait_event=step.wait_for_event
            )
            
            # If this is the last step (no next_step), mark workflow as completed
            is_final_step = not step.next_step
            
            return {
                "current_step": step.id,
                "status": WorkflowStatus.COMPLETED.value if is_final_step else state.get("status"),
                "history": [{
                    "step": step.id,
                    "action": "wait_completed"
                }]
            }
        return wait_node
    
    def _create_parallel_node(self, step: WorkflowStep, definition: WorkflowDefinition) -> Callable:
        """Create a parallel execution node"""
        async def parallel_node(state: WorkflowState) -> Dict[str, Any]:
            # Execute parallel steps
            import asyncio
            from langgraph.types import interrupt
            
            logger.info("workflow_parallel_node_executing",
                component="workflow",
                workflow_id=state.get("workflow_id"),
                step_id=step.id,
                parallel_steps=step.parallel_steps
            )
            
            results = {}
            tasks = []
            
            # Create tasks for each parallel step
            for substep_id in step.parallel_steps or []:
                if substep_id in definition.steps:
                    substep = definition.steps[substep_id]
                    
                    # For ACTION steps, execute them
                    if substep.type == StepType.ACTION:
                        # Create the action node and execute it
                        action_node = self._create_action_node(substep)
                        # Execute the substep with current state
                        task = asyncio.create_task(action_node(state))
                        tasks.append((substep_id, task))
                    else:
                        # For non-action steps, just mark as needing execution
                        results[substep_id] = f"Substep {substep_id} requires sequential execution"
            
            # Wait for all tasks to complete
            if tasks:
                task_results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
                
                # Process results
                for i, (substep_id, _) in enumerate(tasks):
                    result = task_results[i]
                    if isinstance(result, Exception):
                        logger.error("workflow_parallel_step_failed",
                            component="workflow",
                            workflow_id=state.get("workflow_id"),
                            step_id=substep_id,
                            error=str(result)
                        )
                        results[substep_id] = f"Error: {str(result)}"
                    else:
                        # Extract the result from the state update
                        if isinstance(result, dict) and "step_results" in result:
                            # Get the specific result for this step
                            step_result_key = f"{substep_id}_result"
                            results[substep_id] = result["step_results"].get(step_result_key, "Completed")
                        else:
                            results[substep_id] = "Completed"
            
            # Check if any substep requested an interrupt
            for substep_id, result in results.items():
                if isinstance(result, str) and "INTERRUPT" in result:
                    # Propagate the interrupt
                    return interrupt({"step_id": step.id, "interrupted_at": substep_id})
            
            logger.info("workflow_parallel_node_completed",
                component="workflow",
                workflow_id=state.get("workflow_id"),
                step_id=step.id,
                substeps_completed=list(results.keys())
            )
            
            # Update state with all results
            updated_step_results = {**state.get("step_results", {})}
            updated_step_results.update(results)
            updated_step_results[f"{step.id}_parallel_results"] = results
            
            return {
                "current_step": step.id,
                "step_results": updated_step_results,
                "history": [{
                    "step": step.id,
                    "action": "parallel_completed",
                    "substeps": list(results.keys())
                }]
            }
        return parallel_node
    
    def _create_for_each_node(self, step: WorkflowStep, definition: WorkflowDefinition) -> Callable:
        """Create a for-each loop node"""
        async def for_each_node(state: WorkflowState) -> Dict[str, Any]:
            # Get the collection to iterate over
            collection = self._resolve_variable(f"${step.iterate_over}", state)
            if not isinstance(collection, (list, tuple)):
                return {
                    "current_step": step.id,
                    "history": [{
                        "step": step.id,
                        "action": "for_each_skipped",
                        "reason": "Invalid collection"
                    }]
                }
            
            # For now, just record - in production would actually iterate
            return {
                "current_step": step.id,
                "step_results": {
                    f"{step.id}_results": f"Processed {len(collection)} items"
                },
                "history": [{
                    "step": step.id,
                    "action": "for_each_completed",
                    "items_processed": len(collection)
                }]
            }
        return for_each_node
    
    def _substitute_variables(self, text: Optional[str], state: WorkflowState) -> str:
        """Substitute {variable} placeholders with actual values"""
        if not text:
            return ""
        
        # Combine all variable sources
        all_vars = {
            **state.get("variables", {}),
            **state.get("step_results", {}),
            **state.get("human_inputs", {}),
            "workflow_id": state.get("workflow_id"),
            "workflow_name": state.get("workflow_name")
        }
        
        return safe_variable_substitution(text, all_vars)
    
    def _evaluate_condition(self, condition: Dict[str, Any], state: WorkflowState) -> bool:
        """Evaluate a condition against the current state"""
        if not condition:
            return True
        
        operator = condition.get("operator", "equals")
        left = condition.get("left")
        right = condition.get("right")
        
        # Resolve variables
        left = self._resolve_variable(left, state) if left else None
        right = self._resolve_variable(right, state) if right else None
        
        try:
            if operator == "equals":
                return left == right
            elif operator == "not_equals":
                return left != right
            elif operator == "contains":
                return str(right) in str(left)
            elif operator == "not_contains":
                return str(right) not in str(left)
            elif operator == "exists":
                return left is not None
            elif operator == "not_exists":
                return left is None
            # Add more operators as needed
        except Exception as e:
            logger.error("condition_evaluation_error",
                       component="workflow",
                       error=str(e))
            return False
        
        return False
    
    def _resolve_variable(self, value: Any, state: WorkflowState) -> Any:
        """Resolve variable references starting with $"""
        if isinstance(value, str) and value.startswith("$"):
            var_name = value[1:]
            
            # Check all variable sources
            if var_name in state.get("variables", {}):
                return state["variables"][var_name]
            elif var_name in state.get("step_results", {}):
                return state["step_results"][var_name]
            elif var_name in state.get("human_inputs", {}):
                return state["human_inputs"][var_name]
        
        return value
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"