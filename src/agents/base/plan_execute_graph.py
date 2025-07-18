"""Base plan-execute graph for domain-specific agents."""

import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from .plan_execute_state import (
    AgentPlanExecuteState,
    AgentTask,
    AgentPlan,
    create_agent_task,
    create_agent_plan,
    update_agent_execution_state
)
from src.utils.logging import get_logger


class BaseAgentPlanExecute(ABC):
    """Base class for simplified agent plan-execute pattern."""
    
    def __init__(
        self,
        agent_name: str,
        tools: List[Any],
        invoke_llm: Callable,
        checkpointer=None
    ):
        """Initialize the base agent plan-execute graph."""
        self.agent_name = agent_name
        self.tools = tools
        self.tool_map = {tool.name: tool for tool in tools}
        self.invoke_llm = invoke_llm
        self.checkpointer = checkpointer or MemorySaver()
        self.logger = get_logger(agent_name.lower())
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the simplified plan-execute graph."""
        self.logger.info("building_agent_plan_execute_graph",
                        component=self.agent_name.lower(),
                        operation="build_graph")
        
        builder = StateGraph(AgentPlanExecuteState)
        
        # Add nodes - simplified plan-execute pattern
        builder.add_node("planner", self._planner_node)
        builder.add_node("executor", self._executor_node)  
        builder.add_node("replanner", self._replanner_node)
        builder.add_node("finalizer", self._finalizer_node)
        
        # Entry point
        builder.add_edge(START, "planner")
        
        # Flow control
        builder.add_conditional_edges(
            "planner",
            self._route_after_planning,
            {
                "execute": "executor",
                "end": END
            }
        )
        
        builder.add_conditional_edges(
            "executor",
            self._route_after_execution,
            {
                "continue": "executor",  # Next task
                "replan": "replanner",
                "finalize": "finalizer"
            }
        )
        
        builder.add_conditional_edges(
            "replanner",
            self._route_after_replanning,
            {
                "execute": "executor",
                "end": END
            }
        )
        
        builder.add_edge("finalizer", END)
        
        self.logger.info("compiling_agent_graph", 
                        component=self.agent_name.lower())
        return builder.compile(checkpointer=self.checkpointer)
    
    # Core Nodes
    def _planner_node(self, state: AgentPlanExecuteState) -> AgentPlanExecuteState:
        """Generate execution plan for the agent's task."""
        self.logger.info("planner_node_start",
                        component=self.agent_name.lower(),
                        operation="planning",
                        original_request=state["original_request"][:100])
        
        try:
            # Generate plan using domain-specific planning
            plan = self._generate_plan(state)
            
            self.logger.info("plan_generated",
                           component=self.agent_name.lower(),
                           plan_id=plan.id,
                           task_count=len(plan.tasks),
                           plan_description=plan.description)
            
            return update_agent_execution_state(
                state,
                plan=plan,
                execution_started=True,
                messages=state["messages"] + [
                    AIMessage(content=f"Plan created: {plan.description}")
                ]
            )
            
        except Exception as e:
            self.logger.error("planning_error",
                            component=self.agent_name.lower(),
                            error=str(e))
            return update_agent_execution_state(
                state,
                last_error=str(e),
                final_response=f"Planning failed: {str(e)}"
            )
    
    def _executor_node(self, state: AgentPlanExecuteState) -> AgentPlanExecuteState:
        """Execute the current task in the plan."""
        plan = state["plan"]
        if not plan:
            return update_agent_execution_state(
                state,
                last_error="No plan available for execution"
            )
        
        current_task = plan.get_current_task()
        if not current_task:
            return update_agent_execution_state(
                state,
                execution_completed=True
            )
        
        self.logger.info("executor_node_start",
                        component=self.agent_name.lower(),
                        task_id=current_task.id,
                        tool_name=current_task.tool_name,
                        task_description=current_task.description)
        
        try:
            # Execute the current task
            result = self._execute_task(current_task, state)
            
            # Update task with result
            current_task.mark_completed(result)
            
            # Advance to next task
            has_more = plan.advance_to_next_task()
            
            self.logger.info("task_executed_successfully",
                           component=self.agent_name.lower(),
                           task_id=current_task.id,
                           has_more_tasks=has_more)
            
            return update_agent_execution_state(
                state,
                current_task=current_task,
                messages=state["messages"] + [
                    AIMessage(content=f"Completed: {current_task.description}")
                ]
            )
            
        except Exception as e:
            # Mark task as failed
            current_task.mark_failed(str(e))
            
            self.logger.error("task_execution_failed",
                            component=self.agent_name.lower(),
                            task_id=current_task.id,
                            error=str(e),
                            can_retry=current_task.can_retry())
            
            # Determine if we should replan
            should_replan = self._should_replan_after_failure(current_task, state)
            
            return update_agent_execution_state(
                state,
                current_task=current_task,
                last_error=str(e),
                should_replan=should_replan,
                replan_reason=f"Task {current_task.id} failed: {str(e)}"
            )
    
    def _replanner_node(self, state: AgentPlanExecuteState) -> AgentPlanExecuteState:
        """Replan after failures or changes."""
        plan = state["plan"]
        if not plan or not plan.can_replan():
            return update_agent_execution_state(
                state,
                final_response="Maximum replanning attempts reached"
            )
        
        self.logger.info("replanner_node_start",
                        component=self.agent_name.lower(),
                        replan_reason=state.get("replan_reason", "Unknown"),
                        replan_count=plan.replan_count)
        
        try:
            # Generate new plan based on current state
            new_plan = self._replan(state)
            
            self.logger.info("replan_generated",
                           component=self.agent_name.lower(),
                           new_plan_id=new_plan.id,
                           new_task_count=len(new_plan.tasks))
            
            return update_agent_execution_state(
                state,
                plan=new_plan,
                should_replan=False,
                replan_reason=None,
                messages=state["messages"] + [
                    AIMessage(content=f"Replanned: {new_plan.description}")
                ]
            )
            
        except Exception as e:
            self.logger.error("replanning_error",
                            component=self.agent_name.lower(),
                            error=str(e))
            return update_agent_execution_state(
                state,
                last_error=str(e),
                final_response=f"Replanning failed: {str(e)}"
            )
    
    def _finalizer_node(self, state: AgentPlanExecuteState) -> AgentPlanExecuteState:
        """Generate final response based on execution results."""
        plan = state["plan"]
        
        self.logger.info("finalizer_node_start",
                        component=self.agent_name.lower(),
                        has_plan=bool(plan))
        
        try:
            # Generate final response
            final_response = self._generate_final_response(state)
            
            self.logger.info("final_response_generated",
                           component=self.agent_name.lower(),
                           response_length=len(final_response))
            
            return update_agent_execution_state(
                state,
                execution_completed=True,
                final_response=final_response,
                messages=state["messages"] + [
                    AIMessage(content=final_response)
                ]
            )
            
        except Exception as e:
            self.logger.error("finalization_error",
                            component=self.agent_name.lower(),
                            error=str(e))
            return update_agent_execution_state(
                state,
                final_response=f"Task completed with errors: {str(e)}"
            )
    
    # Routing Functions
    def _route_after_planning(self, state: AgentPlanExecuteState) -> str:
        """Route after planning phase."""
        if state.get("last_error") or not state.get("plan"):
            return "end"
        return "execute"
    
    def _route_after_execution(self, state: AgentPlanExecuteState) -> str:
        """Route after executing a task."""
        if state.get("should_replan"):
            return "replan"
        
        plan = state.get("plan")
        if plan and plan.has_more_tasks():
            return "continue"
        
        return "finalize"
    
    def _route_after_replanning(self, state: AgentPlanExecuteState) -> str:
        """Route after replanning."""
        if state.get("last_error") or not state.get("plan"):
            return "end"
        return "execute"
    
    # Abstract Methods - Must be implemented by domain agents
    @abstractmethod
    def _generate_plan(self, state: AgentPlanExecuteState) -> AgentPlan:
        """Generate domain-specific execution plan."""
        pass
    
    @abstractmethod
    def _execute_task(self, task: AgentTask, state: AgentPlanExecuteState) -> Dict[str, Any]:
        """Execute a specific task using domain tools."""
        pass
    
    @abstractmethod
    def _generate_final_response(self, state: AgentPlanExecuteState) -> str:
        """Generate final response based on execution results."""
        pass
    
    # Optional methods - Can be overridden by domain agents
    def _replan(self, state: AgentPlanExecuteState) -> AgentPlan:
        """Default replanning logic - can be overridden."""
        # Simple approach: retry failed tasks with modifications
        plan = state["plan"]
        failed_tasks = plan.get_failed_tasks()
        
        # Create new plan with retry tasks
        new_tasks = []
        for task in failed_tasks:
            if task.can_retry():
                retry_task = create_agent_task(
                    task_id=f"{task.id}_retry_{task.retry_count + 1}",
                    description=f"Retry: {task.description}",
                    tool_name=task.tool_name,
                    tool_args=task.tool_args
                )
                retry_task.retry_count = task.retry_count + 1
                new_tasks.append(retry_task)
        
        return create_agent_plan(
            plan_id=f"{plan.id}_replan_{plan.replan_count + 1}",
            description=f"Replan: {plan.description}",
            tasks=new_tasks
        )
    
    def _should_replan_after_failure(self, failed_task: AgentTask, state: AgentPlanExecuteState) -> bool:
        """Determine if replanning is needed after task failure."""
        plan = state["plan"]
        return (
            plan and 
            plan.can_replan() and 
            failed_task.can_retry() and
            not plan.has_more_tasks()  # Only replan if no more tasks
        )
    
    # Utility Methods
    def _create_planning_prompt(self, state: AgentPlanExecuteState) -> str:
        """Create domain-specific planning prompt."""
        return f"""
Analyze this request and create an execution plan using available tools.

Original Request: {state['original_request']}
Available Tools: {', '.join(state['tools_available'])}
Agent Context: {state.get('task_context', {})}

Create a step-by-step plan to complete this request effectively.
Consider tool dependencies and optimal execution order.
        """.strip()
    
    async def ainvoke(self, initial_state: Dict[str, Any], config: Optional[RunnableConfig] = None) -> AgentPlanExecuteState:
        """Async invoke wrapper for the agent graph."""
        return await self.graph.ainvoke(initial_state, config)
    
    def invoke(self, initial_state: Dict[str, Any], config: Optional[RunnableConfig] = None) -> AgentPlanExecuteState:
        """Sync invoke wrapper for the agent graph."""
        return self.graph.invoke(initial_state, config)