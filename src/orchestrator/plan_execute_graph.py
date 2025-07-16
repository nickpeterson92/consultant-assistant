"""Pure plan-and-execute graph implementation for LangGraph orchestrator."""

from typing import Dict, Any, List, Optional, Literal
from datetime import datetime
import asyncio

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import interrupt
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from src.orchestrator.plan_execute_state import (
    PlanExecuteState, ExecutionPlan, ExecutionTask, InterruptData,
    PlanStatus, TaskStatus, InterruptType,
    create_new_plan, create_new_task, create_initial_state,
    get_current_task, get_next_executable_task, update_progress_state,
    is_plan_complete, get_plan_summary
)
from src.utils.logging import get_logger
from src.utils.config import get_llm_config

logger = get_logger("orchestrator")
print(f"🔧 DEBUG: Logger level: {logger.logger.level if hasattr(logger, 'logger') else 'unknown'}")
print(f"🔧 DEBUG: Logger effective level: {logger.logger.getEffectiveLevel() if hasattr(logger, 'logger') else 'unknown'}")


class PlanExecuteGraph:
    """Pure plan-and-execute graph for orchestrator."""
    
    def __init__(self, checkpointer=None, invoke_llm=None):
        """Initialize the plan-execute graph."""
        self.checkpointer = checkpointer or MemorySaver()
        self.graph = self._build_graph()
        self._agent_tools = {}  # Will be populated with agent caller tools
        self._invoke_llm = invoke_llm  # LLM function for orchestrator tasks and planning
    
    def _build_graph(self) -> StateGraph:
        """Build the baseline plan-and-execute graph."""
        print("🔧 DEBUG: Building graph - this should appear in console")
        logger.info("building_graph_start", component="orchestrator")
        
        builder = StateGraph(PlanExecuteState)
        
        # Add nodes - canonical plan-and-execute pattern
        logger.info("adding_nodes", component="orchestrator")
        builder.add_node("planner", self._planner_node)
        builder.add_node("agent", self._agent_node)  
        builder.add_node("replan", self._replan_node)
        
        # Entry point
        logger.info("adding_edges", component="orchestrator")
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
                "end": END
            }
        )
        
        logger.info("compiling_graph", component="orchestrator")
        compiled_graph = builder.compile(checkpointer=self.checkpointer)
        logger.info("graph_compiled_successfully", component="orchestrator")
        
        return compiled_graph
    
    def set_agent_tools(self, agent_tools: Dict[str, Any]):
        """Set agent caller tools for task execution."""
        self._agent_tools = agent_tools
        logger.info("agent_tools_configured", component="orchestrator", agent_count=len(agent_tools))
    
    # ================================
    # Node Implementations
    # ================================
    
    async def _planner_node(self, state: PlanExecuteState) -> PlanExecuteState:
        """Plan generation node - creates todo-style execution plans."""
        print("🧠 DEBUG: Planner node called - this should appear in console")
        logger.info("planner_node_start", 
                   component="orchestrator",
                   request=state.get("original_request", "NO_REQUEST"),
                   existing_plan=bool(state.get("plan")),
                   messages_count=len(state.get("messages", [])))
        
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
                logger.info("initial_planning_mode", component="orchestrator")
                result = await self._handle_initial_planning(state)
                print("✅ DEBUG: Initial planning completed")
                logger.info("planner_node_complete", 
                           component="orchestrator",
                           success=True,
                           plan_created=bool(result.get("plan")),
                           task_count=len(result["plan"]["tasks"]) if result.get("plan") else 0)
                return result
                
        except Exception as e:
            print(f"❌ DEBUG: Planner error: {str(e)}")
            logger.error("planner_node_error", component="orchestrator", error=str(e), exception_type=type(e).__name__)
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
        """Handle initial plan creation."""
        print("📋 DEBUG: Handle initial planning called")
        logger.info("initial_planning_start", component="orchestrator", request=state["original_request"])
        
        # Use the proper planning system message from prompts
        from src.utils.agents.prompts import get_planning_system_message
        system_msg = get_planning_system_message()
        
        # Create user prompt for the specific request
        user_prompt = f'Create an execution plan for: "{state["original_request"]}"'
        
        # Build the complete planning prompt using LangChain message format
        from langchain_core.messages import SystemMessage, HumanMessage
        planning_prompt = [
            SystemMessage(content=system_msg),
            HumanMessage(content=user_prompt)
        ]
        
        logger.info("invoking_planning_llm", component="orchestrator", prompt_length=len(str(planning_prompt)))
        
        # Generate plan using LLM factory pattern
        if self._invoke_llm:
            # The invoke_llm function is synchronous and returns an AIMessage
            response = self._invoke_llm(planning_prompt)
            plan_text = response.content if hasattr(response, 'content') else str(response)
        else:
            # Fallback if LLM not available
            plan_text = f"1. {state['original_request']} (Agent: orchestrator)"
        
        logger.info("llm_response_received", response_length=len(plan_text), response_preview=plan_text[:100])
        
        # Parse the plan into structured tasks
        plan = await self._parse_plan_from_text(plan_text, state["original_request"])
        
        logger.info("plan_created", 
                   plan_id=plan["id"], 
                   task_count=len(plan["tasks"]),
                   plan_status=plan.get("status", "unknown"))
        
        return {
            **state,
            "plan": plan,
            "messages": state["messages"] + [
                AIMessage(content=f"📋 **Execution Plan Created**\n\n{self._format_plan_display(plan)}")
            ]
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
        
        # Create replanning prompt
        replan_prompt = f"""
        CURRENT PLAN: {self._format_plan_display(current_plan)}
        
        USER REQUEST: {latest_message}
        
        Modify the plan based on the user's request. You can:
        - Add new tasks
        - Remove pending tasks (keep completed ones)
        - Reorder tasks
        - Change task priorities or agent assignments
        
        Preserve completed tasks and their results.
        Format the updated plan as a numbered list like before.
        """
        
        # Generate updated plan using LLM factory pattern
        if self._invoke_llm:
            # The invoke_llm function is synchronous and returns an AIMessage
            replan_messages = [HumanMessage(content=replan_prompt)]
            response = self._invoke_llm(replan_messages)
            updated_plan_text = response.content if hasattr(response, 'content') else str(response)
        else:
            # Fallback if LLM not available
            updated_plan_text = f"1. {latest_message} (Agent: orchestrator)"
        updated_plan = await self._parse_plan_from_text(
            updated_plan_text, 
            current_plan["original_request"],
            base_plan=current_plan
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
            "plan_history": state["plan_history"] + [current_plan],
            "messages": state["messages"] + [
                AIMessage(content=f"📋 **Plan Updated** (v{updated_plan['version']})\n\n{self._format_plan_display(updated_plan)}")
            ]
        }
    
    async def _agent_node(self, state: PlanExecuteState) -> PlanExecuteState:
        """Execute tasks one by one - canonical agent pattern."""
        logger.info("agent_node_start",
                   component="orchestrator",
                   has_plan=bool(state.get("plan")),
                   task_count=len(state["plan"]["tasks"]) if state.get("plan") else 0)
        
        if not state["plan"]:
            logger.warning("agent_no_plan", component="orchestrator")
            return state
        
        # Get next executable task
        next_task = get_next_executable_task(state)
        if not next_task:
            logger.info("agent_no_more_tasks", component="orchestrator")
            return state
        
        logger.info("agent_executing_task", component="orchestrator", task_id=next_task["id"], content=next_task["content"][:100])
        
        try:
            # Execute the task
            result = await self._execute_task(next_task, state)
            
            # Update task with result
            updated_tasks = []
            for task in state["plan"]["tasks"]:
                if task["id"] == next_task["id"]:
                    task = {
                        **task,
                        "status": TaskStatus.COMPLETED.value if result.get("success") else TaskStatus.FAILED.value,
                        "completed_at": datetime.now().isoformat(),
                        "result": result
                    }
                    
                    # Debug: Log what we're storing in the task result
                    logger.info("storing_task_result", component="orchestrator", 
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
            
            # Create appropriate message based on success/failure
            if result.get("success"):
                # Extract the actual response from the result structure
                result_data = result.get("result", {})
                logger.info("extracting_message_content", component="orchestrator", 
                           task_id=next_task["id"], 
                           result_data_type=type(result_data).__name__,
                           result_data_keys=list(result_data.keys()) if isinstance(result_data, dict) else "not_dict",
                           has_response="response" in result_data if isinstance(result_data, dict) else False)
                
                if isinstance(result_data, dict) and "response" in result_data:
                    message_content = result_data["response"]
                    logger.info("using_response_from_result", component="orchestrator", 
                               task_id=next_task["id"], 
                               raw_response_type=type(result_data["response"]).__name__,
                               response_preview=message_content[:100])
                elif isinstance(result_data, dict) and "status" in result_data and "response" in result_data:
                    # Handle direct orchestrator result format
                    message_content = result_data["response"]
                    logger.info("using_direct_orchestrator_response", component="orchestrator", 
                               task_id=next_task["id"], response_preview=message_content[:100])
                else:
                    message_content = f"✅ Completed: {next_task['content']}"
                    logger.info("using_fallback_message", component="orchestrator", 
                               task_id=next_task["id"], message=message_content)
            else:
                # For failed tasks, show the error
                error_msg = result.get("error", "Task failed")
                message_content = f"❌ Failed: {next_task['content']} - {error_msg}"
            
            # Debug: Log the final message content before creating AIMessage
            logger.info("final_message_content", component="orchestrator", 
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
            logger.error("agent_task_execution_error", component="orchestrator", task_id=next_task["id"], error=str(e))
            
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
                    AIMessage(content=f"❌ Failed: {next_task['content']} - {str(e)}")
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
        """Route after agent execution - replan if more tasks needed, otherwise end."""
        if state["plan"] and not is_plan_complete(state):
            route = "replan"
        else:
            route = "end"
            
        logger.info("route_after_agent_execution",
                   component="orchestrator",
                   plan_complete=is_plan_complete(state),
                   route=route)
        return route
    
    def _route_after_replan(self, state: PlanExecuteState) -> str:
        """Route after replanning - execute new tasks or end."""
        if state["plan"] and state["plan"]["tasks"]:
            route = "execute"
        else:
            route = "end"
            
        logger.info("route_after_replan_to_agent",
                   component="orchestrator",
                   has_plan=bool(state["plan"]),
                   task_count=len(state["plan"]["tasks"]) if state["plan"] else 0,
                   route=route)
        return route
    
    async def _replan_node(self, state: PlanExecuteState) -> PlanExecuteState:
        """Replan node - decides if more tasks are needed."""
        logger.info("replan_node_start",
                   component="orchestrator",
                   has_plan=bool(state.get("plan")),
                   task_count=len(state["plan"]["tasks"]) if state.get("plan") else 0)
        
        # Simple replan: if all tasks complete, we're done
        if state["plan"] and is_plan_complete(state):
            logger.info("replan_complete", component="orchestrator", reason="all_tasks_complete")
            return {
                **state,
                "messages": state["messages"] + [
                    AIMessage(content="✅ All tasks completed successfully!")
                ]
            }
        
        # Otherwise, continue with existing plan
        logger.info("replan_continue", component="orchestrator", reason="tasks_remaining")
        return state
    
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
        
        logger.info("built_agent_state", component="orchestrator", 
                   keys=list(agent_state.keys()), 
                   message_count=len(agent_state.get("messages", [])))
        
        return agent_state
    
    def _format_plan_display(self, plan: ExecutionPlan) -> str:
        """Format plan for display with checkboxes."""
        if not plan or not plan["tasks"]:
            return "No tasks in plan"
        
        lines = []
        for i, task in enumerate(plan["tasks"], 1):
            if task["status"] == TaskStatus.COMPLETED.value:
                lines.append(f"✓ {i}. {task['content']}")
            elif task["status"] == TaskStatus.FAILED.value:
                lines.append(f"✗ {i}. {task['content']}")
            else:
                lines.append(f"□ {i}. {task['content']}")
        
        return "\n".join(lines)
    
    
    async def _parse_plan_from_text(self, plan_text: str, original_request: str, base_plan: Optional[ExecutionPlan] = None) -> ExecutionPlan:
        """Parse plan text into structured ExecutionPlan."""
        from uuid import uuid4
        import re
        
        # Create base plan structure
        plan_id = base_plan["id"] if base_plan else str(uuid4())
        plan = create_new_plan(original_request, plan_id)
        
        # Parse tasks from text
        lines = [line.strip() for line in plan_text.strip().split('\n') if line.strip()]
        tasks = []
        
        for line in lines:
            # Match numbered list items
            match = re.match(r'(\d+)\.\s*(.+)', line)
            if match:
                task_content = match.group(2)
                
                # Extract agent from content
                agent_match = re.search(r'\(Agent:\s*(\w+)', task_content)
                agent = agent_match.group(1) if agent_match else None
                
                # Extract dependencies
                deps_match = re.search(r'depends on:\s*([0-9,\s]+)', task_content)
                depends_on = []
                if deps_match:
                    dep_nums = [int(x.strip()) for x in deps_match.group(1).split(',') if x.strip().isdigit()]
                    # Convert numbers to task IDs (we'll need to track this)
                    depends_on = [f"task_{num}" for num in dep_nums]
                
                # Clean up content
                clean_content = re.sub(r'\s*\(Agent:.*?\)', '', task_content)
                clean_content = re.sub(r'\s*depends on:.*', '', clean_content)
                
                task = create_new_task(
                    content=clean_content.strip(),
                    agent=agent,
                    depends_on=depends_on
                )
                task["id"] = f"task_{len(tasks) + 1}"  # Simple ID for dependencies
                tasks.append(task)
        
        plan["tasks"] = tasks
        return plan
    
    async def _execute_task(self, task: ExecutionTask, state: PlanExecuteState) -> Dict[str, Any]:
        """Execute a single task - pure and simple."""
        logger.info("execute_task_start", component="orchestrator", task_id=task["id"], agent=task.get("agent"))
        
        try:
            agent_name = task.get("agent", "orchestrator")
            logger.info("execute_task_routing", component="orchestrator", task_id=task["id"], agent=agent_name)
            
            # Convert plan-execute state to agent tool expected format
            agent_state = self._build_agent_state(state)
            
            # Pure execution - call with proper state injection pattern from legacy code
            if agent_name == "salesforce" and "salesforce_agent" in self._agent_tools:
                logger.info("calling_salesforce_agent", component="orchestrator", task_id=task["id"])
                result = await self._agent_tools["salesforce_agent"]._arun(
                    instruction=task["content"],
                    state=agent_state,
                    tool_call_id=f"task_{task['id']}"
                )
            elif agent_name == "jira" and "jira_agent" in self._agent_tools:
                logger.info("calling_jira_agent", component="orchestrator", task_id=task["id"])
                result = await self._agent_tools["jira_agent"]._arun(
                    instruction=task["content"],
                    state=agent_state,
                    tool_call_id=f"task_{task['id']}"
                ) 
            elif agent_name == "servicenow" and "servicenow_agent" in self._agent_tools:
                logger.info("calling_servicenow_agent", component="orchestrator", task_id=task["id"])
                result = await self._agent_tools["servicenow_agent"]._arun(
                    instruction=task["content"],
                    state=agent_state,
                    tool_call_id=f"task_{task['id']}"
                )
            elif agent_name == "orchestrator":
                # For orchestrator tasks, use existing LLM infrastructure
                logger.info("handling_orchestrator_task", component="orchestrator", task_id=task["id"])
                
                # Use the invoke_llm function from llm_handler if available
                if hasattr(self, '_invoke_llm') and self._invoke_llm:
                    # The invoke_llm function is synchronous and returns an AIMessage
                    try:
                        orchestrator_messages = [HumanMessage(content=task["content"])]
                        response = self._invoke_llm(orchestrator_messages)
                        llm_response = response.content if hasattr(response, 'content') else str(response)
                        logger.info("orchestrator_llm_response", component="orchestrator", 
                                   task_id=task["id"], 
                                   response_type=type(response).__name__,
                                   has_content=hasattr(response, 'content'),
                                   llm_response_preview=llm_response[:100])
                    except Exception as e:
                        logger.error("orchestrator_llm_error", component="orchestrator", task_id=task["id"], error=str(e))
                        llm_response = f"I'm ready to help with: {task['content']}"
                else:
                    # Fallback to simple response if LLM not available
                    llm_response = f"I'm ready to help with: {task['content']}"
                
                result = {
                    "status": "completed", 
                    "type": "coordination",
                    "response": llm_response
                }
                
                logger.info("orchestrator_result_created", component="orchestrator", 
                           task_id=task["id"], 
                           result_keys=list(result.keys()),
                           response_preview=result["response"][:100])
                
                # Debug: Log the result object ID to track modifications
                logger.info("orchestrator_result_debug", component="orchestrator", 
                           task_id=task["id"], 
                           result_id=id(result),
                           result_response_id=id(result["response"]),
                           result_response_type=type(result["response"]).__name__)
            else:
                # Agent not available or unknown
                logger.warning("unknown_agent", component="orchestrator", task_id=task["id"], agent=agent_name)
                return {
                    "success": False,
                    "error": f"Agent {agent_name} not available or unknown",
                    "agent": agent_name,
                    "task_id": task["id"]
                }
            
            logger.info("execute_task_success", component="orchestrator", task_id=task["id"], agent=agent_name)
            
            # Debug: Log what we're about to return
            logger.info("execute_task_return_debug", component="orchestrator", 
                       task_id=task["id"], 
                       result_type=type(result).__name__,
                       result_preview=str(result)[:200])
            
            # Handle Command pattern results from agent tools
            if hasattr(result, 'update') and isinstance(result.update, dict):
                # This is a Command object with state updates
                logger.info("agent_command_received", component="orchestrator", 
                           task_id=task["id"], agent=agent_name,
                           update_keys=list(result.update.keys()),
                           has_messages="messages" in result.update)
                
                # Extract the response from messages if available
                response_content = "Task completed successfully"
                if "messages" in result.update:
                    messages = result.update["messages"]
                    if messages and hasattr(messages[-1], 'content'):
                        response_content = messages[-1].content
                
                return {
                    "success": True,
                    "result": {
                        "status": "completed",
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


def create_plan_execute_graph(checkpointer=None, invoke_llm=None) -> PlanExecuteGraph:
    """Factory function to create a plan-execute graph."""
    return PlanExecuteGraph(checkpointer=checkpointer, invoke_llm=invoke_llm)