"""Pure plan-and-execute graph implementation for LangGraph orchestrator."""

from typing import Dict, Any, List, Optional, Literal
from datetime import datetime
import asyncio
import time

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import interrupt
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import time

from src.orchestrator.plan_execute_state import (
    PlanExecuteState, ExecutionPlan, ExecutionTask, InterruptData,
    PlanStatus, TaskStatus, InterruptType,
    create_new_plan, create_new_task, create_initial_state,
    get_current_task, get_next_executable_task, update_progress_state,
    is_plan_complete, get_plan_summary
)
from src.utils.config.unified_config import config as app_config
from src.utils.agents.message_processing import trim_messages_for_context, smart_preserve_messages
from src.utils.logging.framework import SmartLogger

# Create orchestrator-specific logger
logger = SmartLogger("orchestrator")


class PlanExecuteGraph:
    """Pure plan-and-execute graph for orchestrator."""
    
    def __init__(self, checkpointer=None, invoke_llm=None, plan_extractor=None):
        """Initialize the plan-execute graph."""
        self.checkpointer = checkpointer or MemorySaver()
        self.graph = self._build_graph()
        self._agent_tools = {}  # Will be populated with agent caller tools
        self._invoke_llm = invoke_llm  # LLM function for orchestrator tasks and planning
        self._plan_extractor = plan_extractor  # Structured plan extractor using trustcall
        self._last_summary_time = 0
        self._last_summary_message_count = 0
    
    def _build_graph(self) -> StateGraph:
        """Build the baseline plan-and-execute graph."""
        print("🔧 DEBUG: Building graph - this should appear in console")
        logger.info("building_graph_start")
        
        builder = StateGraph(PlanExecuteState)
        
        # Add nodes - canonical plan-and-execute pattern
        logger.info("adding_nodes")
        builder.add_node("planner", self._planner_node)
        builder.add_node("agent", self._agent_node)  
        builder.add_node("replan", self._replan_node)
        builder.add_node("plan_summary", self._summary_node)
        
        # Entry point
        logger.info("adding_edges")
        builder.add_edge(START, "planner")
        
        # Simple flow control
        builder.add_conditional_edges(
            "planner",
            self._route_after_planning,
            {
                "execute": "agent",
                "end": END
            }
        )
        
        builder.add_conditional_edges(
            "agent",
            self._route_after_execution,
            {
                "replan": "replan",
                "end": END
            }
        )
        
        builder.add_conditional_edges(
            "replan",
            self._route_after_replan,
            {
                "execute": "agent",
                "plan_summary": "plan_summary",
                "end": END
            }
        )
        
        builder.add_conditional_edges(
            "plan_summary",
            self._route_after_summary,
            {
                "end": END
            }
        )
        
        logger.info("compiling_graph")
        compiled_graph = builder.compile(checkpointer=self.checkpointer)
        logger.info("graph_compiled_successfully")
        
        return compiled_graph
    
    def set_agent_tools(self, agent_tools: Dict[str, Any]):
        """Set agent caller tools for task execution."""
        self._agent_tools = agent_tools
        logger.info("agent_tools_configured", agent_count=len(agent_tools))
    
    # ================================
    # Node Implementations
    # ================================
    
    async def _planner_node(self, state: PlanExecuteState, config: dict = None) -> PlanExecuteState:
        """Plan generation node - creates todo-style execution plans."""
        print("🧠 DEBUG: Planner node called - this should appear in console")
        logger.info("planner_node_start", 
                   component="orchestrator",
                   request=state.get("original_request", "NO_REQUEST"),
                   existing_plan=bool(state.get("plan")),
                   messages_count=len(state.get("messages", [])))
        
        # Trim messages if needed before planning
        state = self._trim_messages_if_needed(state)
        
        # Trigger background summarization if needed
        await self._trigger_background_summary(state, config)
        
        try:
            # Check if there's an existing plan
            existing_plan = state.get("plan")
            
            if existing_plan:
                # Check if the existing plan is complete
                plan_is_complete = is_plan_complete(state)
                
                print(f"🔄 DEBUG: Found existing plan, checking completion: {plan_is_complete}")
                logger.info("checking_existing_plan", 
                           component="orchestrator",
                           plan_id=existing_plan.get("id"),
                           task_count=len(existing_plan.get("tasks", [])),
                           plan_is_complete=plan_is_complete)
                
                if plan_is_complete:
                    # Plan is complete, create new plan for the new request
                    print("🔄 DEBUG: Existing plan is complete, creating new plan")
                    logger.info("existing_plan_complete_creating_new", 
                               component="orchestrator",
                               completed_plan_id=existing_plan.get("id"))
                    
                    result = await self._handle_initial_planning(state)
                    print("✅ DEBUG: New plan created")
                    logger.info("planner_node_complete", 
                               component="orchestrator",
                               success=True,
                               plan_created=bool(result.get("plan")),
                               task_count=len(result["plan"]["tasks"]) if result.get("plan") else 0)
                    
                    # Stream plan creation event (handled by A2A streaming)
                    logger.info("plan_created_event", 
                               plan_id=result.get("plan", {}).get("id"),
                               task_count=len(result.get("plan", {}).get("tasks", [])))
                    
                    return result
                else:
                    # Plan is not complete, continue with existing plan
                    print("🔄 DEBUG: Continuing with incomplete existing plan")
                    logger.info("continuing_incomplete_plan", 
                               component="orchestrator",
                               plan_id=existing_plan.get("id"))
                    return state
                
            else:
                # Create new plan for first message in conversation
                print("🔄 DEBUG: Starting initial planning")
                logger.info("initial_planning_mode")
                result = await self._handle_initial_planning(state)
                print("✅ DEBUG: Initial planning completed")
                logger.info("planner_node_complete", 
                           component="orchestrator",
                           success=True,
                           plan_created=bool(result.get("plan")),
                           task_count=len(result["plan"]["tasks"]) if result.get("plan") else 0)
                
                # Stream plan creation event (handled by A2A streaming)
                logger.info("plan_created_event", 
                           plan_id=result.get("plan", {}).get("id"),
                           task_count=len(result.get("plan", {}).get("tasks", [])))
                
                return result
                
        except Exception as e:
            print(f"❌ DEBUG: Planner error: {str(e)}")
            logger.error("planner_node_error", error=str(e), exception_type=type(e).__name__)
            return {
                **state,
                "interrupted": True,
                "interrupt_data": InterruptData(
                    interrupt_type=InterruptType.ERROR_RECOVERY.value,
                    reason=f"Planning failed: {str(e)}",
                    context={"error": str(e), "node": "planner"},
                    user_input=None,
                    pending_approval=None,
                    created_at=datetime.now().isoformat(),
                    resolved_at=None
                )
            }
    
    async def _handle_initial_planning(self, state: PlanExecuteState) -> PlanExecuteState:
        """Handle initial plan creation using structured extraction only."""
        print("📋 DEBUG: Handle initial planning called")
        logger.info("initial_planning_start", request=state["original_request"])
        
        if not self._plan_extractor:
            raise ValueError("Plan extractor is required for structured planning")
        
        # Create planning prompt for structured extraction
        planning_prompt = self._create_structured_planning_prompt(state)
        
        logger.info("invoking_structured_planning", 
                   prompt_length=len(str(planning_prompt)),
                   message_count=len(planning_prompt))
        
        # Log extraction attempt
        extraction_logger = get_logger("extraction")
        
        extraction_logger.info("trustcall_plan_extraction_start",
                              component="extraction",
                              operation="initial_planning",
                              request_preview=state["original_request"][:100],
                              prompt_length=len(str(planning_prompt)),
                              message_count=len(planning_prompt))
        
        # Extract structured plan using trustcall
        extraction_result = await self._plan_extractor.ainvoke({"messages": planning_prompt})
        
        extraction_logger.info("trustcall_plan_extraction_complete",
                              component="extraction",
                              operation="initial_planning",
                              has_result=bool(extraction_result),
                              result_type=type(extraction_result).__name__ if extraction_result else "None")
        
        if not extraction_result:
            extraction_logger.error("trustcall_plan_extraction_failed",
                                   component="extraction",
                                   operation="initial_planning",
                                   error="No result from trustcall extractor")
            raise ValueError("No structured plan could be extracted from LLM response")
        
        # trustcall returns a dict with messages/responses, need to extract the actual plan
        if isinstance(extraction_result, dict) and "responses" in extraction_result:
            # New trustcall format: plan is in responses
            responses = extraction_result.get("responses", [])
            if responses and len(responses) > 0:
                structured_plan = responses[0]  # First response should be the ExecutionPlanStructured
            else:
                extraction_logger.error("trustcall_no_responses",
                                       component="extraction",
                                       operation="initial_planning", 
                                       error="No responses in trustcall result")
                raise ValueError("No plan found in trustcall responses")
        else:
            # Fallback: assume it's the plan object directly
            structured_plan = extraction_result
        
        extraction_logger.info("plan_object_extracted",
                              component="extraction",
                              operation="initial_planning",
                              plan_type=type(structured_plan).__name__,
                              has_description=hasattr(structured_plan, 'description'),
                              has_tasks=hasattr(structured_plan, 'tasks'),
                              task_count=len(structured_plan.tasks) if hasattr(structured_plan, 'tasks') else 0)
        
        extraction_logger.info("structured_plan_details", 
                              component="extraction",
                              operation="initial_planning",
                              plan_description=structured_plan.description,
                              task_count=len(structured_plan.tasks),
                              has_success_criteria=bool(getattr(structured_plan, 'success_criteria', None)),
                              has_estimated_time=bool(getattr(structured_plan, 'estimated_total_time', None)))
        
        # Log the actual plan content for debugging
        extraction_logger.info("extracted_plan_content",
                              component="extraction", 
                              operation="initial_planning",
                              full_plan_description=structured_plan.description,
                              tasks=[{
                                  "step": task.step_number,
                                  "description": task.description, 
                                  "agent": task.agent,
                                  "depends_on": task.depends_on,
                                  "priority": task.priority
                              } for task in structured_plan.tasks])
        
        logger.info("structured_plan_extracted", 
                   component="orchestrator",
                   plan_description=structured_plan.description,
                   task_count=len(structured_plan.tasks))
        
        # Convert structured plan to internal format
        plan = await self._convert_structured_plan(structured_plan, state["original_request"])
        
        logger.info("plan_created", 
                   plan_id=plan["id"], 
                   task_count=len(plan["tasks"]),
                   plan_status=plan.get("status", "unknown"))
        
        return {
            **state,
            "plan": plan
        }
    
    async def _handle_replanning(self, state: PlanExecuteState) -> PlanExecuteState:
        """Handle plan modification/replanning."""
        current_plan = state["plan"]
        
        # Get the latest user message for replanning context
        latest_message = None
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                latest_message = msg.content
                break
        
        if not latest_message:
            logger.warning("replanning_no_user_input")
            return state
        
        logger.info("replanning_with_context", user_input=latest_message[:100])
        
        if not self._plan_extractor:
            raise ValueError("Plan extractor is required for structured replanning")
        
        # Create structured replanning prompt
        replan_prompt = self._create_structured_replanning_prompt(state, current_plan, latest_message)
        
        # Log replanning extraction attempt
        extraction_logger = get_logger("extraction")
        
        extraction_logger.info("trustcall_plan_extraction_start",
                              component="extraction",
                              operation="replanning",
                              user_request_preview=latest_message[:100],
                              current_plan_id=current_plan.get("id", "unknown"),
                              prompt_length=len(str(replan_prompt)),
                              message_count=len(replan_prompt))
        
        # Extract updated structured plan using trustcall
        extracted_plans = await self._plan_extractor.ainvoke({"messages": replan_prompt})
        
        extraction_logger.info("trustcall_plan_extraction_complete",
                              component="extraction",
                              operation="replanning",
                              has_result=bool(extracted_plans),
                              plan_count=len(extracted_plans) if extracted_plans else 0,
                              result_type=type(extracted_plans).__name__ if extracted_plans else "None")
        
        if not extracted_plans or len(extracted_plans) == 0:
            extraction_logger.error("trustcall_plan_extraction_failed",
                                   component="extraction",
                                   operation="replanning",
                                   error="No structured plan could be extracted during replanning")
            raise ValueError("No structured plan could be extracted during replanning")
        
        structured_plan = extracted_plans[0]
        
        extraction_logger.info("structured_replan_details", 
                              component="extraction",
                              operation="replanning",
                              plan_description=structured_plan.description,
                              task_count=len(structured_plan.tasks),
                              has_success_criteria=bool(getattr(structured_plan, 'success_criteria', None)))
        
        logger.info("structured_replan_extracted", 
                   component="orchestrator",
                   plan_description=structured_plan.description,
                   task_count=len(structured_plan.tasks))
        
        # Convert structured plan to internal format, preserving completed tasks
        updated_plan = await self._convert_structured_plan_with_preservation(
            structured_plan, current_plan
        )
        
        # Increment version
        updated_plan["version"] = current_plan.get("version", 1) + 1
        
        logger.info("plan_updated", 
                   plan_id=updated_plan["id"], 
                   version=updated_plan["version"],
                   task_count=len(updated_plan["tasks"]))
        
        return {
            **state,
            "plan": updated_plan,
            "plan_history": state["plan_history"] + [current_plan]
        }
    
    async def _agent_node(self, state: PlanExecuteState, config: dict = None) -> PlanExecuteState:
        """Execute tasks one by one - canonical agent pattern."""
        logger.info("agent_node_start",
                   component="orchestrator",
                   has_plan=bool(state.get("plan")),
                   task_count=len(state["plan"]["tasks"]) if state.get("plan") else 0)
        
        # Trim messages if needed before execution
        state = self._trim_messages_if_needed(state)
        
        # Trigger background summarization if needed
        await self._trigger_background_summary(state, config)
        
        if not state["plan"]:
            logger.warning("agent_no_plan")
            return state
        
        # Get next executable task
        next_task = get_next_executable_task(state)
        if not next_task:
            logger.info("agent_no_more_tasks")
            return state
        
        logger.info("agent_executing_task", task_id=next_task["id"], content=next_task["content"][:100])
        
        # Stream task start event (handled by A2A streaming)
        logger.info("task_started_event", 
                   task_id=next_task["id"], 
                   task_content=next_task["content"][:100])
        
        
        try:
            # Execute the task
            result = await self._execute_task(next_task, state)
            
            # Update task with result
            updated_tasks = []
            for task in state["plan"]["tasks"]:
                if task["id"] == next_task["id"]:
                    task = {
                        **task,
                        "status": TaskStatus.COMPLETED.value if (
                            result.get("status") == "completed" or  # External agents
                            result.get("success") == True or        # Internal tasks  
                            result.get("result", {}).get("status") == "completed"  # Internal tasks nested
                        ) else TaskStatus.FAILED.value,
                        "completed_at": datetime.now().isoformat(),
                        "result": result
                    }
                    
                    # Debug: Log what we're storing in the task result
                    logger.info("storing_task_result", 
                               task_id=next_task["id"], 
                               result_type=type(result).__name__,
                               result_keys=list(result.keys()) if isinstance(result, dict) else "not_dict",
                               inner_result_type=type(result.get("result", {})).__name__ if isinstance(result, dict) else "no_inner")
                updated_tasks.append(task)
            
            updated_plan = {**state["plan"], "tasks": updated_tasks}
            
            logger.info("agent_task_completed", 
                       component="orchestrator",
                       task_id=next_task["id"], 
                       success=result.get("success", False))
            
            # Stream task completion event (handled by A2A streaming)
            logger.info("task_completed_event", 
                       task_id=next_task["id"], 
                       success=result.get("success", False),
                       task_content=next_task["content"][:100])
            
            # Debug: Log the actual task status that was set in the plan
            actual_task_status = None
            for task in updated_tasks:
                if task["id"] == next_task["id"]:
                    actual_task_status = task.get("status")
                    break
            
            logger.info("plan_task_status_updated", 
                       task_id=next_task["id"], 
                       actual_task_status=actual_task_status,
                       result_success=result.get("success"),
                       result_status=result.get("status"),
                       result_result_status=result.get("result", {}).get("status"))
            
            # Create appropriate message based on success/failure
            if result.get("success"):
                # Extract the actual response from the result structure
                result_data = result.get("result", {})
                logger.info("extracting_message_content", 
                           task_id=next_task["id"], 
                           result_data_type=type(result_data).__name__,
                           result_data_keys=list(result_data.keys()) if isinstance(result_data, dict) else "not_dict",
                           has_response="response" in result_data if isinstance(result_data, dict) else False)
                
                if isinstance(result_data, dict) and "response" in result_data:
                    message_content = result_data["response"]
                    logger.info("using_response_from_result", 
                               task_id=next_task["id"], 
                               raw_response_type=type(result_data["response"]).__name__,
                               response_preview=message_content[:100])
                elif isinstance(result_data, dict) and "status" in result_data and "response" in result_data:
                    # Handle direct orchestrator result format
                    message_content = result_data["response"]
                    logger.info("using_direct_orchestrator_response", 
                               task_id=next_task["id"], response_preview=message_content[:100])
                else:
                    message_content = f"[COMPLETED] {next_task['content']}"
                    logger.info("using_fallback_message", 
                               task_id=next_task["id"], message=message_content)
            else:
                # For failed tasks, show the error
                error_msg = result.get("error", "Task failed")
                message_content = f"[FAILED] {next_task['content']} - {error_msg}"
            
            # Debug: Log the final message content before creating AIMessage
            logger.info("final_message_content", 
                       task_id=next_task["id"], 
                       message_content_type=type(message_content).__name__,
                       message_content_preview=str(message_content)[:100])
            
            return {
                **state,
                "plan": updated_plan,
                "messages": state["messages"] + [
                    AIMessage(content=message_content)
                ]
            }
            
        except Exception as e:
            logger.error("agent_task_execution_error", task_id=next_task["id"], error=str(e))
            
            # Stream task error event (handled by A2A streaming)
            logger.error("task_error_event", 
                        task_id=next_task["id"], 
                        error=str(e),
                        task_content=next_task["content"][:100])
            
            # Mark task as failed
            updated_tasks = []
            for task in state["plan"]["tasks"]:
                if task["id"] == next_task["id"]:
                    task = {
                        **task,
                        "status": TaskStatus.FAILED.value,
                        "completed_at": datetime.now().isoformat(),
                        "error": str(e)
                    }
                updated_tasks.append(task)
            
            return {
                **state,
                "plan": {**state["plan"], "tasks": updated_tasks},
                "messages": state["messages"] + [
                    AIMessage(content=f"[FAILED] {next_task['content']} - {str(e)}")
                ]
            }
    
# Removed complex nodes - keeping baseline plan-and-execute pattern
    
    # ================================
    # Routing Functions
    # ================================
    
    def _route_after_planning(self, state: PlanExecuteState) -> str:
        """Route after planning - execute tasks or end if no plan."""
        if state["plan"] and state["plan"]["tasks"]:
            route = "execute"
        else:
            route = "end"
            
        logger.info("route_after_planning", 
                   component="orchestrator",
                   has_plan=bool(state["plan"]),
                   task_count=len(state["plan"]["tasks"]) if state["plan"] else 0,
                   route=route)
        return route
    
    def _route_after_execution(self, state: PlanExecuteState) -> str:
        """Route after agent execution - always go to replan to decide next step."""
        # Always route to replan - let replan decide if we need summary or end
        route = "replan"
            
        logger.info("route_after_agent_execution",
                   component="orchestrator",
                   plan_complete=is_plan_complete(state),
                   route=route)
        return route
    
    def _route_after_replan(self, state: PlanExecuteState) -> str:
        """Route after replanning - execute new tasks or summarize if complete."""
        if state["plan"] and is_plan_complete(state):
            route = "plan_summary"
        elif state["plan"] and state["plan"]["tasks"]:
            route = "execute"
        else:
            route = "end"  # Fallback for empty plans
            
        logger.info("route_after_replan",
                   component="orchestrator",
                   has_plan=bool(state["plan"]),
                   plan_complete=is_plan_complete(state) if state.get("plan") else False,
                   task_count=len(state["plan"]["tasks"]) if state["plan"] else 0,
                   route=route)
        return route
    
    async def _replan_node(self, state: PlanExecuteState) -> PlanExecuteState:
        """Replan node - decides if more tasks are needed or plan needs replacement."""
        logger.info("replan_node_start",
                   component="orchestrator",
                   has_plan=bool(state.get("plan")),
                   task_count=len(state["plan"]["tasks"]) if state.get("plan") else 0)
        
        # Check for plan replacement requests
        if state.get("replace_plan_requested"):
            logger.info("replan_replacement_requested", 
                       replace_plan=state.get("replace_plan_requested", False))
            
            # Get the new plan description
            new_plan_description = state.get("new_plan_description", "")
            
            if new_plan_description:
                # Create a new plan to replace the current one
                logger.info("generating_replacement_plan",
                           new_plan_description=new_plan_description[:100])
                
                # Create new plan with the replacement description
                replacement_state = {
                    **state,
                    "original_request": new_plan_description,
                    "messages": state.get("messages", []),
                    "plan": None,  # Clear existing plan
                    "replace_plan_requested": False,  # Clear flag
                    "new_plan_description": None  # Clear description
                }
                
                # Generate new plan
                result = await self._handle_initial_planning(replacement_state)
                
                logger.info("replacement_plan_created",
                           plan_id=result.get("plan", {}).get("id"),
                           task_count=len(result.get("plan", {}).get("tasks", [])))
                
                # Stream plan creation event (handled by A2A streaming)
                logger.info("plan_created_event", 
                           plan_id=result.get("plan", {}).get("id"),
                           task_count=len(result.get("plan", {}).get("tasks", [])))
                
                return result
            else:
                logger.warning("replacement_plan_missing_description")
        
        # Check for add to plan requests
        elif state.get("add_to_plan_requested"):
            logger.info("replan_add_to_plan_requested")
            
            additional_steps = state.get("additional_steps", [])
            insert_after_step = state.get("insert_after_step", None)
            
            if additional_steps:
                # Add new steps to existing plan
                current_plan = state.get("plan", {})
                current_tasks = current_plan.get("tasks", [])
                
                # Create new tasks from additional steps
                new_tasks = []
                for i, step_description in enumerate(additional_steps):
                    new_task = {
                        "id": f"added_task_{len(current_tasks) + i + 1}",
                        "content": step_description,
                        "agent": "orchestrator",  # Will be determined during execution
                        "status": TaskStatus.PENDING.value,
                        "created_at": datetime.now().isoformat()
                    }
                    new_tasks.append(new_task)
                
                # Insert new tasks at the right position
                if insert_after_step and insert_after_step <= len(current_tasks):
                    # Insert after specific step
                    insert_index = insert_after_step
                    updated_tasks = current_tasks[:insert_index] + new_tasks + current_tasks[insert_index:]
                else:
                    # Append to end
                    updated_tasks = current_tasks + new_tasks
                
                # Update plan with new tasks
                updated_plan = {
                    **current_plan,
                    "tasks": updated_tasks,
                    "version": current_plan.get("version", 1) + 1
                }
                
                logger.info("plan_extended",
                           plan_id=updated_plan.get("id"),
                           original_task_count=len(current_tasks),
                           new_task_count=len(new_tasks),
                           total_task_count=len(updated_tasks))
                
                return {
                    **state,
                    "plan": updated_plan,
                    "add_to_plan_requested": False,  # Clear flag
                    "additional_steps": None,  # Clear steps
                    "insert_after_step": None  # Clear position
                }
        
        # Simple replan: if all tasks complete, we're done
        if state["plan"] and is_plan_complete(state):
            logger.info("replan_complete", reason="all_tasks_complete")
            
            # Stream plan completion event (handled by A2A streaming)
            logger.info("plan_completed_event", 
                       plan_id=state["plan"].get("id"))
            
            return state
        
        # Otherwise, continue with existing plan
        logger.info("replan_continue", reason="tasks_remaining")
        return state
    
    def _summary_node(self, state: PlanExecuteState) -> PlanExecuteState:
        """Summary node - generates LLM summary for multi-task plans only."""
        plan = state.get("plan", {})
        tasks = plan.get("tasks", [])
        task_count = len(tasks)
        
        logger.info("summary_node_start",
                   component="orchestrator",
                   plan_id=plan.get("id") if plan else "none",
                   task_count=task_count)
        
        # Only generate LLM summary for multi-task plans (>1 task)
        if task_count > 1:
            logger.info("generating_llm_summary_for_multi_task_plan",
                       component="orchestrator",
                       task_count=task_count)
            
            summary = self._generate_plan_completion_summary(state)
            
            # Add the summary to the state
            if state.get("plan"):
                state["plan"]["summary"] = summary
        else:
            # For single-task plans, extract the direct task response
            logger.info("extracting_direct_response_for_single_task_plan",
                       component="orchestrator",
                       task_count=task_count)
            
            summary = ""
            if tasks:
                task = tasks[0]
                if (task.get("result", {}).get("success") and 
                    "result" in task.get("result", {}) and 
                    "response" in task.get("result", {}).get("result", {})):
                    summary = task["result"]["result"]["response"]
            
            # Use direct response for single-task plans
            if state.get("plan"):
                state["plan"]["summary"] = summary
        
        logger.info("summary_node_complete",
                   component="orchestrator",
                   plan_id=plan.get("id") if plan else "none",
                   task_count=task_count,
                   is_multi_task=task_count > 1,
                   summary_generated=bool(summary),
                   summary_length=len(summary) if summary else 0)
        
        return state
    
    def _route_after_summary(self, state: PlanExecuteState) -> str:
        """Route after summary generation - always go to end."""
        logger.info("route_after_summary", route="end")
        return "end"
    
    def _generate_plan_completion_summary(self, state: PlanExecuteState) -> str:
        """Generate an LLM summary of the completed plan execution."""
        try:
            plan = state.get("plan", {})
            tasks = plan.get("tasks", [])
            original_request = state.get("original_request", "")
            
            # Collect task results
            completed_tasks = []
            failed_tasks = []
            
            for task in tasks:
                task_content = task.get("content", "Unknown task")
                task_status = task.get("status", "unknown")
                
                if task_status == "completed":
                    # Extract task response if available
                    task_response = "Completed successfully"
                    if (task.get("result", {}).get("success") and 
                        "result" in task.get("result", {}) and 
                        "response" in task.get("result", {}).get("result", {})):
                        task_response = task["result"]["result"]["response"]
                    
                    completed_tasks.append({
                        "task": task_content,
                        "response": task_response
                    })
                elif task_status == "failed":
                    error_msg = task.get("error", "Unknown error")
                    failed_tasks.append({
                        "task": task_content,
                        "error": error_msg
                    })
            
            # Create summary prompt
            summary_prompt = f"""Please provide a concise executive summary of the following plan execution:

**Original Request:** {original_request}

**Completed Tasks ({len(completed_tasks)}):**
"""
            
            for i, task_info in enumerate(completed_tasks, 1):
                summary_prompt += f"{i}. {task_info['task']}\n   Result: {task_info['response']}\n\n"
            
            if failed_tasks:
                summary_prompt += f"**Failed Tasks ({len(failed_tasks)}):**\n"
                for i, task_info in enumerate(failed_tasks, 1):
                    summary_prompt += f"{i}. {task_info['task']}\n   Error: {task_info['error']}\n\n"
            
            summary_prompt += """
Please provide a brief, professional summary using proper markdown formatting:

**Executive Summary:**

Create a well-structured summary with:
1. A clear opening statement acknowledging what was requested
2. Numbered list of what was accomplished with specific details
3. Bullet points for key results or outcomes  
4. Notes on any issues if applicable

Use proper markdown formatting with:
- **Bold headers** for sections
- Numbered lists (1. 2. 3.) for main accomplishments
- Bullet points (- or *) for details and sub-items
- Clear line breaks between sections

Keep the summary concise but informative and well-formatted."""
            
            # Generate summary using the LLM
            from langchain_core.messages import HumanMessage
            logger.info("generating_plan_summary", 
                       component="orchestrator",
                       completed_count=len(completed_tasks),
                       failed_count=len(failed_tasks))
            
            summary_response = self._invoke_llm([HumanMessage(content=summary_prompt)])
            summary = summary_response.content if hasattr(summary_response, 'content') else str(summary_response)
            
            logger.info("plan_summary_generated", 
                       component="orchestrator",
                       summary_length=len(summary),
                       summary_preview=summary[:200])
            
            return summary
            
        except Exception as e:
            logger.error("plan_summary_generation_error",
                        component="orchestrator",
                        error=str(e))
            return f"Plan execution completed with {len([t for t in tasks if t.get('status') == 'completed'])} tasks completed successfully."
    
    # ================================
    # Helper Methods
    # ================================
    
    def _build_agent_state(self, state: PlanExecuteState) -> Dict[str, Any]:
        """Build agent state in the format expected by agent tools."""
        # Serialize messages to avoid JSON serialization errors
        from src.utils.agents.message_processing.unified_serialization import serialize_messages_for_json
        serialized_messages = serialize_messages_for_json(state.get("messages", []))
        
        # Convert plan-execute state to orchestrator state format
        agent_state = {
            "messages": serialized_messages,
            "memory": state.get("memory", {}),
            "summary": state.get("summary", ""),
            "execution_context": state.get("execution_context", {}),
            "agent_context": state.get("agent_context", {}),
            "tool_calls_since_memory": state.get("tool_calls_since_memory", 0),
            "agent_calls_since_memory": state.get("agent_calls_since_memory", 0),
            "active_agents": state.get("active_agents", []),
            "config": state.get("config", {})
        }
        
        # Add plan context if available
        if state.get("plan"):
            agent_state["current_plan"] = state["plan"]
            agent_state["plan_context"] = {
                "original_request": state["original_request"],
                "current_task_index": state.get("current_task_index", 0),
                "task_results": state.get("task_results", {})
            }
        
        logger.info("built_agent_state", 
                   keys=list(agent_state.keys()), 
                   message_count=len(agent_state.get("messages", [])))
        
        return agent_state
    
    
    
    def _create_structured_planning_prompt(self, state: PlanExecuteState) -> List:
        """Create planning prompt for structured extraction."""
        from langchain_core.messages import SystemMessage, HumanMessage
        from src.utils.agents.prompts import get_planning_system_message
        
        # Use the proper planning system message but adapted for structured output
        system_msg = get_planning_system_message()
        
        # Enhance system message for structured output
        enhanced_system_msg = system_msg + """

IMPORTANT: You must respond with a structured ExecutionPlanStructured object containing:
- description: Brief description of what this plan accomplishes
- tasks: List of tasks with step_number, description, agent, depends_on (optional), priority (optional), estimated_duration (optional)

Each task must specify which agent will handle it:
- salesforce: For CRM operations (accounts, contacts, opportunities, leads, cases, tasks)
- jira: For project management (projects, issues, sprints, boards)
- servicenow: For IT service management (incidents, changes, problems)
- orchestrator: For coordination, web search, or multi-agent workflows
- workflow: For complex pre-built workflows

Ensure step numbers are sequential (1, 2, 3...) and dependencies reference valid step numbers.
"""
        
        planning_prompt = [SystemMessage(content=enhanced_system_msg)]
        
        # Add conversation history from state for context
        conversation_messages = state.get("messages", [])
        if conversation_messages:
            planning_prompt.extend(conversation_messages)
        
        # Add final planning instruction
        planning_prompt.append(
            HumanMessage(content=f'Based on the conversation context above, create a structured execution plan for: "{state["original_request"]}"')
        )
        
        return planning_prompt
    
    async def _convert_structured_plan(self, structured_plan, original_request: str) -> ExecutionPlan:
        """Convert structured plan from trustcall to internal ExecutionPlan format."""
        from uuid import uuid4
        
        # Create base plan
        plan = create_new_plan(original_request, str(uuid4()))
        plan["description"] = structured_plan.description
        
        # Convert tasks
        tasks = []
        for task_struct in structured_plan.tasks:
            # Create task with proper dependencies
            depends_on = []
            if task_struct.depends_on:
                # Convert step numbers to task IDs
                depends_on = [f"task_{step_num}" for step_num in task_struct.depends_on]
            
            task = create_new_task(
                content=task_struct.description,
                agent=task_struct.agent,
                depends_on=depends_on
            )
            task["id"] = f"task_{task_struct.step_number}"
            task["priority"] = task_struct.priority or "medium"
            task["estimated_duration"] = task_struct.estimated_duration
            
            tasks.append(task)
        
        plan["tasks"] = tasks
        plan["success_criteria"] = getattr(structured_plan, 'success_criteria', None)
        plan["estimated_total_time"] = getattr(structured_plan, 'estimated_total_time', None)
        
        return plan
    
    def _create_structured_replanning_prompt(self, state: PlanExecuteState, current_plan: ExecutionPlan, user_request: str) -> List:
        """Create replanning prompt for structured extraction."""
        from langchain_core.messages import SystemMessage, HumanMessage
        
        # Create current plan summary for context
        plan_summary = self._format_plan_display(current_plan)
        
        system_msg = f"""You are updating an execution plan based on user feedback.

CURRENT PLAN:
{plan_summary}

USER REQUEST: {user_request}

You must create an updated ExecutionPlanStructured that:
1. Preserves any completed tasks and their results
2. Modifies the plan based on the user's request (add/remove/reorder tasks)
3. Maintains proper step numbering (1, 2, 3...)
4. Ensures dependencies reference valid step numbers
5. Uses appropriate agents: salesforce, jira, servicenow, orchestrator, workflow

When preserving completed tasks, keep their original content and mark them appropriately.
When adding new tasks, ensure they integrate properly with existing work.
"""
        
        planning_prompt = [SystemMessage(content=system_msg)]
        
        # Add conversation context
        conversation_messages = state.get("messages", [])
        if conversation_messages:
            # Only include recent messages to avoid token limits
            recent_messages = conversation_messages[-5:] if len(conversation_messages) > 5 else conversation_messages
            planning_prompt.extend(recent_messages)
        
        # Add final replanning instruction
        planning_prompt.append(
            HumanMessage(content=f'Update the execution plan based on this request: "{user_request}"')
        )
        
        return planning_prompt
    
    async def _convert_structured_plan_with_preservation(self, structured_plan, current_plan: ExecutionPlan) -> ExecutionPlan:
        """Convert structured plan while preserving completed tasks from current plan."""
        from uuid import uuid4
        
        # Start with the base conversion
        updated_plan = await self._convert_structured_plan(structured_plan, current_plan["original_request"])
        
        # Preserve plan ID and other metadata
        updated_plan["id"] = current_plan["id"]
        updated_plan["created_at"] = current_plan.get("created_at")
        
        # Preserve completed tasks by merging with new plan
        completed_tasks = [task for task in current_plan.get("tasks", []) 
                          if task.get("status") == TaskStatus.COMPLETED.value]
        
        # If we have completed tasks, we need to integrate them intelligently
        if completed_tasks:
            logger.info("preserving_completed_tasks", 
                       component="orchestrator",
                       completed_count=len(completed_tasks))
            
            # This is a simplified approach - in practice you might want more sophisticated merging
            # For now, we'll keep completed tasks and append new ones with adjusted step numbers
            preserved_tasks = []
            max_completed_step = 0
            
            for task in completed_tasks:
                preserved_tasks.append(task)
                # Extract step number from task ID
                if task.get("id", "").startswith("task_"):
                    try:
                        step_num = int(task["id"].split("_")[1])
                        max_completed_step = max(max_completed_step, step_num)
                    except (IndexError, ValueError):
                        pass
            
            # Adjust new task step numbers to continue from completed tasks
            for task in updated_plan["tasks"]:
                if task.get("id", "").startswith("task_"):
                    try:
                        old_step_num = int(task["id"].split("_")[1])
                        new_step_num = max_completed_step + old_step_num
                        task["id"] = f"task_{new_step_num}"
                        
                        # Update dependencies to account for step number shift
                        if task.get("depends_on"):
                            adjusted_deps = []
                            for dep in task["depends_on"]:
                                if dep.startswith("task_"):
                                    try:
                                        dep_num = int(dep.split("_")[1])
                                        adjusted_deps.append(f"task_{max_completed_step + dep_num}")
                                    except (IndexError, ValueError):
                                        adjusted_deps.append(dep)
                                else:
                                    adjusted_deps.append(dep)
                            task["depends_on"] = adjusted_deps
                        
                    except (IndexError, ValueError):
                        pass
                
                preserved_tasks.append(task)
            
            updated_plan["tasks"] = preserved_tasks
        
        return updated_plan
    
    async def _execute_task(self, task: ExecutionTask, state: PlanExecuteState) -> Dict[str, Any]:
        """Execute a single task - pure and simple."""
        logger.info("execute_task_start", task_id=task["id"], agent=task.get("agent"))
        
        try:
            agent_name = task.get("agent", "orchestrator")
            logger.info("execute_task_routing", task_id=task["id"], agent=agent_name)
            
            # Convert plan-execute state to agent tool expected format
            agent_state = self._build_agent_state(state)
            
            # Pure execution - call with proper state injection pattern from legacy code
            if agent_name == "salesforce" and "salesforce_agent" in self._agent_tools:
                logger.info("calling_salesforce_agent", task_id=task["id"])
                result = await self._agent_tools["salesforce_agent"]._arun(
                    instruction=task["content"],
                    state=agent_state,
                    tool_call_id=f"task_{task['id']}"
                )
            elif agent_name == "jira" and "jira_agent" in self._agent_tools:
                logger.info("calling_jira_agent", task_id=task["id"])
                result = await self._agent_tools["jira_agent"]._arun(
                    instruction=task["content"],
                    state=agent_state,
                    tool_call_id=f"task_{task['id']}"
                ) 
            elif agent_name == "servicenow" and "servicenow_agent" in self._agent_tools:
                logger.info("calling_servicenow_agent", task_id=task["id"])
                result = await self._agent_tools["servicenow_agent"]._arun(
                    instruction=task["content"],
                    state=agent_state,
                    tool_call_id=f"task_{task['id']}"
                )
            elif agent_name == "orchestrator":
                # For orchestrator tasks, use existing LLM infrastructure
                logger.info("handling_orchestrator_task", task_id=task["id"])
                
                # Use the invoke_llm function from llm_handler if available
                if hasattr(self, '_invoke_llm') and self._invoke_llm:
                    # The invoke_llm function is synchronous and returns an AIMessage
                    try:
                        orchestrator_messages = [HumanMessage(content=task["content"])]
                        response = self._invoke_llm(orchestrator_messages)
                        llm_response = response.content if hasattr(response, 'content') else str(response)
                        logger.info("orchestrator_llm_response", 
                                   task_id=task["id"], 
                                   response_type=type(response).__name__,
                                   has_content=hasattr(response, 'content'),
                                   llm_response_preview=llm_response[:100])
                    except Exception as e:
                        logger.error("orchestrator_llm_error", task_id=task["id"], error=str(e))
                        llm_response = f"I'm ready to help with: {task['content']}"
                else:
                    # Fallback to simple response if LLM not available
                    llm_response = f"I'm ready to help with: {task['content']}"
                
                result = {
                    "status": "completed", 
                    "type": "coordination",
                    "response": llm_response
                }
                
                logger.info("orchestrator_result_created", 
                           task_id=task["id"], 
                           result_keys=list(result.keys()),
                           response_preview=result["response"][:100])
                
                # Debug: Log the result object ID to track modifications
                logger.info("orchestrator_result_debug", 
                           task_id=task["id"], 
                           result_id=id(result),
                           result_response_id=id(result["response"]),
                           result_response_type=type(result["response"]).__name__)
            else:
                # Agent not available or unknown
                logger.warning("unknown_agent", task_id=task["id"], agent=agent_name)
                return {
                    "success": False,
                    "error": f"Agent {agent_name} not available or unknown",
                    "agent": agent_name,
                    "task_id": task["id"]
                }
            
            logger.info("execute_task_success", task_id=task["id"], agent=agent_name)
            
            # Debug: Log what we're about to return
            logger.info("execute_task_return_debug", 
                       task_id=task["id"], 
                       result_type=type(result).__name__,
                       result_preview=str(result)[:200])
            
            # Handle Command pattern results from agent tools
            if hasattr(result, 'update') and isinstance(result.update, dict):
                # This is a Command object with state updates
                logger.info("agent_command_received", 
                           task_id=task["id"], agent=agent_name,
                           update_keys=list(result.update.keys()),
                           has_messages="messages" in result.update)
                
                # Extract the response from messages if available
                response_content = "Task completed successfully"
                is_error = False
                
                if "messages" in result.update:
                    messages = result.update["messages"]
                    if messages and hasattr(messages[-1], 'content'):
                        response_content = messages[-1].content
                        # Check if this is an error message from agent tools
                        if response_content.startswith("Error:"):
                            is_error = True
                
                # Determine success based on whether this is an error message
                task_success = not is_error
                task_status = "failed" if is_error else "completed"
                
                logger.info("agent_command_result_analysis",
                           task_id=task["id"], 
                           is_error=is_error,
                           task_success=task_success,
                           response_preview=response_content[:100])
                
                return {
                    "success": task_success,
                    "result": {
                        "status": task_status,
                        "type": "agent_command",
                        "response": response_content,
                        "state_updates": result.update
                    },
                    "agent": agent_name,
                    "task_id": task["id"]
                }
            else:
                # Handle orchestrator result (dictionary) vs legacy string result
                if isinstance(result, dict) and "response" in result:
                    # This is an orchestrator result dictionary
                    return {
                        "success": True,
                        "result": result,  # Use the orchestrator result as-is
                        "agent": agent_name,
                        "task_id": task["id"]
                    }
                else:
                    # Legacy string result
                    return {
                        "success": True,
                        "result": {
                            "status": "completed",
                            "type": "agent_response", 
                            "response": str(result)
                        },
                        "agent": agent_name,
                        "task_id": task["id"]
                    }
                
        except Exception as e:
            logger.error("task_execution_failed", task_id=task["id"], error=str(e))
            return {
                "success": False,
                "error": str(e),
                "agent": task.get("agent"),
                "task_id": task["id"]
            }
    
    # Interrupt handlers (to be implemented)
    async def _handle_escape_interrupt(self, state: PlanExecuteState) -> PlanExecuteState:
        """Handle ESC key interrupt - pause execution for user input."""
        logger.info("handling_escape_interrupt")
        
        # Use LangGraph's interrupt() to pause and ask user what to do
        user_choice = interrupt({
            "type": "escape_interrupt",
            "message": "⏸️ Execution paused. What would you like to do?",
            "options": [
                "continue - Resume execution",
                "cancel - Cancel the current plan", 
                "modify - Modify the current plan",
                "status - Show current progress"
            ]
        })
        
        if user_choice == "continue":
            return {**state, "interrupted": False, "interrupt_data": None}
        elif user_choice == "cancel":
            return {
                **state,
                "plan": {**state["plan"], "status": PlanStatus.CANCELLED.value},
                "interrupted": False,
                "interrupt_data": None,
                "messages": state["messages"] + [
                    AIMessage(content="❌ Plan execution cancelled by user.")
                ]
            }
        elif user_choice == "modify":
            # Trigger plan modification
            return {
                **state,
                "interrupted": True,
                "interrupt_data": InterruptData(
                    interrupt_type=InterruptType.PLAN_MODIFICATION.value,
                    reason="User requested plan modification via ESC",
                    context={"user_choice": user_choice},
                    user_input=str(user_choice),
                    pending_approval=None,
                    created_at=datetime.now().isoformat(),
                    resolved_at=None
                )
            }
        else:
            # Show status and continue
            current_task = get_current_task(state)
            status_msg = f"📊 Current status: {current_task['content'] if current_task else 'No active task'}"
            return {
                **state,
                "interrupted": False,
                "interrupt_data": None,
                "messages": state["messages"] + [AIMessage(content=status_msg)]
            }
    
    async def _handle_modification_interrupt(self, state: PlanExecuteState) -> PlanExecuteState:
        """Handle plan modification interrupt - allow user to modify the plan."""
        logger.info("handling_modification_interrupt")
        
        if not state["plan"]:
            return {**state, "interrupted": False, "interrupt_data": None}
        
        current_plan_display = self._format_plan_display(state["plan"])
        
        # Use interrupt() to get user's modification request
        modification_request = interrupt({
            "type": "plan_modification",
            "current_plan": current_plan_display,
            "message": "🔧 Current plan shown above. How would you like to modify it?",
            "instructions": "Describe the changes you want to make to the plan."
        })
        
        if not modification_request or modification_request.strip() == "":
            # No modification requested, continue with current plan
            return {**state, "interrupted": False, "interrupt_data": None}
        
        # Add modification request to messages for replanning
        updated_messages = state["messages"] + [
            HumanMessage(content=f"Please modify the plan: {modification_request}")
        ]
        
        # Clear the current plan to trigger replanning
        return {
            **state,
            "messages": updated_messages,
            "plan": None,  # This will trigger replanning
            "interrupted": False,
            "interrupt_data": None
        }
    
    async def _handle_error_interrupt(self, state: PlanExecuteState) -> PlanExecuteState:
        """Handle error recovery interrupt - let user decide how to handle errors."""
        logger.info("handling_error_interrupt")
        
        interrupt_data = state.get("interrupt_data")
        error_context = interrupt_data.get("context", {}) if interrupt_data else {}
        error_message = error_context.get("error", "Unknown error")
        
        # Use interrupt() to let user decide error handling
        recovery_choice = interrupt({
            "type": "error_recovery",
            "error": error_message,
            "message": f"❌ Error encountered: {error_message}",
            "options": [
                "retry - Try the failed task again",
                "skip - Skip the failed task and continue",
                "abort - Cancel the entire plan",
                "modify - Modify the plan to work around the error"
            ]
        })
        
        if recovery_choice == "retry":
            # Reset the failed task and continue
            return {**state, "interrupted": False, "interrupt_data": None}
        elif recovery_choice == "skip":
            # Mark current task as skipped and continue
            if state["plan"]:
                current_task = get_current_task(state)
                if current_task:
                    updated_tasks = []
                    for task in state["plan"]["tasks"]:
                        if task["id"] == current_task["id"]:
                            task = {**task, "status": TaskStatus.SKIPPED.value}
                        updated_tasks.append(task)
                    
                    return {
                        **state,
                        "plan": {**state["plan"], "tasks": updated_tasks},
                        "interrupted": False,
                        "interrupt_data": None,
                        "messages": state["messages"] + [
                            AIMessage(content="⏭️ Task skipped, continuing with next task.")
                        ]
                    }
            return {**state, "interrupted": False, "interrupt_data": None}
        elif recovery_choice == "abort":
            # Cancel the entire plan
            return {
                **state,
                "plan": {**state["plan"], "status": PlanStatus.CANCELLED.value},
                "interrupted": False,
                "interrupt_data": None,
                "messages": state["messages"] + [
                    AIMessage(content="🛑 Plan execution aborted due to error.")
                ]
            }
        else:
            # Modify plan to work around error
            return {
                **state,
                "interrupted": True,
                "interrupt_data": InterruptData(
                    interrupt_type=InterruptType.PLAN_MODIFICATION.value,
                    reason="User requested plan modification to handle error",
                    context={"error": error_message, "recovery_choice": recovery_choice},
                    user_input=str(recovery_choice),
                    pending_approval=None,
                    created_at=datetime.now().isoformat(),
                    resolved_at=None
                )
            }
    
    async def _handle_approval_interrupt(self, state: PlanExecuteState) -> PlanExecuteState:
        """Handle approval request interrupt - process approval responses."""
        logger.info("handling_approval_interrupt")
        
        # This is handled in the approver node, so we just clear the interrupt
        return {**state, "interrupted": False, "interrupt_data": None}
    
    # ================================
    # Message Processing and Summarization
    # ================================
    
    def _should_trim_messages(self, messages: List) -> bool:
        """Check if messages should be trimmed based on length."""
        if not messages:
            return False
        
        # Simple heuristic from old system: trim if more than 20 messages
        return len(messages) > 20
    
    def _should_trigger_summary(self, messages: List) -> bool:
        """Check if conversation should be summarized."""
        current_time = time.time()
        message_count = len(messages)
        
        # Check message count threshold
        if message_count - self._last_summary_message_count >= app_config.conversation_summary_threshold:
            return True
        
        # Check time threshold (5 minutes = 300 seconds)
        if current_time - self._last_summary_time >= 300 and message_count > self._last_summary_message_count:
            return True
        
        return False
    
    def _trim_messages_if_needed(self, state: PlanExecuteState) -> PlanExecuteState:
        """Trim messages if context is getting too large."""
        messages = state.get("messages", [])
        
        if not self._should_trim_messages(messages):
            return state
        
        logger.info("trimming_messages_for_context",
                   component="orchestrator",
                   original_count=len(messages),
                   triggering_trim=True)
        
        # Use 80k token limit matching old system orchestrator settings
        trimmed_messages = trim_messages_for_context(
            messages,
            max_tokens=80000,
            keep_system=True,
            keep_first_n=2,
            keep_last_n=15,
            use_smart_trimming=True
        )
        
        logger.info("message_trimming_complete",
                   component="orchestrator",
                   original_count=len(messages),
                   trimmed_count=len(trimmed_messages),
                   tokens_saved=len(messages) - len(trimmed_messages))
        
        return {
            **state,
            "messages": trimmed_messages
        }
    
    async def _trigger_background_summary(self, state: PlanExecuteState, config: dict = None) -> None:
        """Trigger background conversation summarization."""
        messages = state.get("messages", [])
        
        if not self._should_trigger_summary(messages):
            return
        
        logger.info("triggering_background_summary",
                   message_count=len(messages),
                   last_summary_count=self._last_summary_message_count)
        
        # Update tracking
        self._last_summary_time = time.time()
        self._last_summary_message_count = len(messages)
        
        # Run summarization in background without blocking using the working pattern
        # Use passed config or try to get from state
        if config is None:
            config = state.get("config", {})
        
        logger.info("background_summary_config_check",
                   config_available=bool(config),
                   config_keys=list(config.keys()) if config else [],
                   has_configurable=bool(config.get("configurable")) if config else False)
        
        asyncio.create_task(self._run_background_summary_with_storage(state, config))
    
    async def _run_background_summary(self, state: PlanExecuteState) -> None:
        """Run conversation summarization in background."""
        try:
            messages = state.get("messages", [])
            current_summary = state.get("summary", "No summary available")
            
            logger.info("background_summary_start",
                       component="storage",
                       message_count=len(messages),
                       has_existing_summary=bool(current_summary),
                       existing_summary_length=len(current_summary) if current_summary != "No summary available" else 0,
                       existing_summary_preview=current_summary[:200] if current_summary != "No summary available" else "NO_EXISTING_SUMMARY")
            
            # Create summary prompt similar to old system
            summary_prompt = self._create_summary_prompt(messages, current_summary)
            
            logger.info("background_summary_prompt_created",
                       component="storage",
                       prompt_length=len(summary_prompt),
                       recent_messages_used=len(smart_preserve_messages(messages, keep_count=10)),
                       current_summary_in_prompt=current_summary != "No summary available")
            
            # Generate summary using LLM
            if self._invoke_llm:
                summary_response = self._invoke_llm([HumanMessage(content=summary_prompt)])
                new_summary = summary_response.content if hasattr(summary_response, 'content') else str(summary_response)
                
                # Validate summary format (simplified version of old validation)
                if self._is_valid_summary_format(new_summary):
                    logger.info("background_summary_complete",
                               component="storage",
                               summary_length=len(new_summary),
                               summary_preview=new_summary[:200],
                               previous_summary_length=len(current_summary) if current_summary != "No summary available" else 0,
                               summary_growth=len(new_summary) - (len(current_summary) if current_summary != "No summary available" else 0))
                    
                    # Update state with new summary
                    state["summary"] = new_summary
                    logger.info("background_summary_state_updated",
                               component="storage",
                               state_summary_length=len(state.get("summary", "")),
                               state_updated=True)
                    
                else:
                    logger.warning("background_summary_invalid_format",
                                 component="storage",
                                 summary_preview=new_summary[:200])
            
        except Exception as e:
            logger.error("background_summary_error",
                        component="storage",
                        error=str(e),
                        exception_type=type(e).__name__)
    
    async def _run_background_summary_with_storage(self, state: PlanExecuteState, config: dict) -> None:
        """Run conversation summarization in background using simplified working pattern."""
        from src.utils.storage import get_async_store_adapter
        from src.utils.config import STATE_KEY_PREFIX
        from src.utils.logging import log_operation
        
        with log_operation("orchestrator", "background_summarization", 
                          thread_id=config.get("configurable", {}).get("thread_id"),
                          user_id=config.get("configurable", {}).get("user_id", app_config.default_user_id)):
            
            # Get thread_id from passed config
            thread_id = config.get("configurable", {}).get("thread_id")
            if not thread_id:
                logger.error("background_summary_no_thread_id",
                           config_keys=list(config.keys()),
                           configurable_keys=list(config.get("configurable", {}).keys()))
                return
            
            # Get user_id 
            user_id = config.get("configurable", {}).get("user_id", app_config.default_user_id)
            
            # Extract current state
            messages = state.get("messages", [])
            current_summary = state.get("summary", "")
            
            logger.info("background_summary_start",
                        thread_id=thread_id,
                        user_id=user_id,
                        message_count=len(messages),
                        existing_summary_length=len(current_summary))
            
            # Load existing summary from storage if available
            try:
                memory_store = get_async_store_adapter(db_path=app_config.db_path)
                namespace = (app_config.memory_namespace_prefix, user_id)
                key = f"{STATE_KEY_PREFIX}{thread_id}"
                
                stored_data = await memory_store.get(namespace, key)
                if stored_data and "summary" in stored_data:
                    current_summary = stored_data["summary"]
                    logger.info("summary_loaded_from_storage",
                                thread_id=thread_id,
                                loaded_summary_length=len(current_summary),
                                state_summary_length=len(state.get("summary", "")))
                else:
                    logger.info("no_stored_summary_found", thread_id=thread_id)
            except Exception as e:
                logger.error("summary_load_error", thread_id=thread_id, error=str(e))
            
            # Generate new summary using existing method
            summary_prompt = self._create_summary_prompt(messages, current_summary)
            
            if self._invoke_llm:
                summary_response = self._invoke_llm([HumanMessage(content=summary_prompt)])
                new_summary = summary_response.content if hasattr(summary_response, 'content') else str(summary_response)
                
                if self._is_valid_summary_format(new_summary):
                    logger.info("background_summary_generated",
                                summary_length=len(new_summary),
                                summary_preview=new_summary[:200])
                    
                    # Save to external storage (simplified - only summary)
                    await memory_store.put(namespace, key, {
                        "summary": new_summary,
                        "thread_id": thread_id,
                        "timestamp": time.time()
                    })
                    
                    logger.info("background_summary_saved",
                                thread_id=thread_id,
                                summary_length=len(new_summary))
                else:
                    logger.error("background_summary_invalid_format",
                               summary_preview=new_summary[:200])
    
    def _create_summary_prompt(self, messages: List, current_summary: str) -> str:
        """Create summary prompt similar to old system."""
        # Preserve recent messages for context
        recent_messages = smart_preserve_messages(messages, keep_count=10)
        
        logger.info("summary_prompt_building",
                   total_messages=len(messages),
                   recent_messages_kept=len(recent_messages),
                   current_summary_chars=len(current_summary),
                   has_valid_current_summary=current_summary != "No summary available")
        
        # Format messages for summary
        formatted_messages = []
        for msg in recent_messages:
            role = "User" if isinstance(msg, HumanMessage) else "Assistant"
            content = str(msg.content)[:500]  # Truncate long messages
            formatted_messages.append(f"{role}: {content}")
        
        prompt = f"""Please provide a structured summary of this conversation.

CURRENT SUMMARY:
{current_summary}

RECENT MESSAGES:
{chr(10).join(formatted_messages)}

Please update the summary to include the recent conversation while maintaining the following format:

TECHNICAL/SYSTEM INFORMATION:
- Key system operations, tool calls, data retrieved
- Agent interactions and coordination
- Technical outcomes and results

USER INTERACTION:
- User requests and intentions
- Questions asked and answered
- Task completion status

AGENT COORDINATION CONTEXT:
- Which agents were involved
- What operations were performed
- Current system state and context

Keep the summary concise but comprehensive."""
        
        return prompt
    
    def _is_valid_summary_format(self, summary: str) -> bool:
        """Simple validation of summary format."""
        required_sections = [
            "TECHNICAL/SYSTEM INFORMATION:",
            "USER INTERACTION:",
            "AGENT COORDINATION CONTEXT:"
        ]
        
        return all(section in summary for section in required_sections)


def create_plan_execute_graph(checkpointer=None, invoke_llm=None, plan_extractor=None) -> PlanExecuteGraph:
    """Factory function to create a plan-execute graph."""
    return PlanExecuteGraph(checkpointer=checkpointer, invoke_llm=invoke_llm, plan_extractor=plan_extractor)