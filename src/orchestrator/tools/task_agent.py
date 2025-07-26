"""Task Agent Tool - Executes complex multi-step tasks using plan-and-execute workflow."""

import asyncio
from typing import Type, Optional, Dict, Any, Annotated
from langchain_core.tools import BaseTool
from langgraph.prebuilt import InjectedState
from langgraph.errors import GraphInterrupt
from pydantic import BaseModel, Field
from src.utils.logging.framework import SmartLogger

logger = SmartLogger("orchestrator.tools.task_agent")


class TaskAgentInput(BaseModel):
    """Input schema for TaskAgentTool."""
    task: str = Field(description="The complex task to plan and execute")
    context: Optional[str] = Field(default=None, description="Additional context for the task")


class TaskAgentTool(BaseTool):
    """Execute complex multi-step tasks that require planning and coordination.
    
    This tool delegates to the plan-and-execute workflow for tasks that:
    - Require multiple steps
    - Need coordination across different agents
    - Involve complex data retrieval or updates
    - Require planning and replanning
    """
    
    name: str = "task_agent"
    description: str = """⚠️ MANDATORY: Use task_agent for these cases:
    
    🔴 CRITICAL - MUST USE task_agent FOR:
    - UPDATE by NAME: "update the XYZ opportunity" → task_agent
    - ONBOARD: "onboard XYZ company" → task_agent  
    - Any update/change/modify using a NAME (not ID) → task_agent
    - Multi-step operations ("do X and then Y") → task_agent
    - Process workflows (resolve, setup, configure) → task_agent
    
    ✅ Direct agent calls ONLY for:
    - Simple lookups with IDs
    - Single-step operations
    - Direct questions with no actions
    
    ⚠️ NEVER use a system agent directly for complex workflows!
    """
    args_schema: Type[BaseModel] = TaskAgentInput
    
    def __init__(self):
        """Initialize without plan-execute graph (lazy loading)."""
        super().__init__()
        self._plan_execute_graph = None
        self._initialization_lock = asyncio.Lock()
    
    async def _ensure_graph_initialized(self):
        """Ensure the plan-execute graph is initialized (thread-safe)."""
        if self._plan_execute_graph is None:
            async with self._initialization_lock:
                # Double-check pattern
                if self._plan_execute_graph is None:
                    logger.info("task_agent_initializing_graph")
                    # Import here to avoid circular imports
                    from src.orchestrator.plan_and_execute import create_plan_execute_graph
                    self._plan_execute_graph = await create_plan_execute_graph()
                    logger.info("task_agent_graph_initialized")
        return self._plan_execute_graph
    
    def _run(self, task: str, context: Optional[str] = None, state: Annotated[Dict[str, Any], InjectedState] = None) -> str:
        """Execute the task synchronously."""
        return asyncio.run(self._arun(task, context, state=state))
    
    async def _arun(self, task: str, context: Optional[str] = None, state: Annotated[Dict[str, Any], InjectedState] = None) -> str:
        """Execute the task using plan-and-execute workflow."""
        try:
            logger.info("task_agent_invoked",
                       task=task[:100],
                       has_context=bool(context))
            
            # Ensure graph is initialized
            graph = await self._ensure_graph_initialized()
            
            # Get current state from the injected state
            parent_state = state if state else {}
            
            # Prepare input for plan-execute graph
            plan_execute_input = {
                "input": task,
                "messages": parent_state.get("messages", []),
                "thread_id": parent_state.get("thread_id", "default-thread"),
                "user_id": parent_state.get("user_id", "default_user"),
                "task_id": parent_state.get("task_id", f"task_{hash(task)}"),
            }
            
            # Add context if provided
            if context:
                plan_execute_input["context"] = context
            
            # Create config for checkpointer to maintain state
            config = {
                "configurable": {
                    "thread_id": parent_state.get("thread_id", "default-thread")
                }
            }
            
            # Execute the plan-execute workflow with config
            result = await graph.ainvoke(plan_execute_input, config)
            
            # Extract the response
            if "response" in result:
                response = result["response"]
                logger.info("task_agent_completed",
                           response_length=len(response))
                return response
            else:
                logger.warning("task_agent_no_response",
                              result_keys=list(result.keys()))
                return "Task completed but no response was generated."
                
        except GraphInterrupt as e:
            # Re-raise GraphInterrupt so orchestrator can handle it properly
            logger.info("task_agent_interrupt_propagating",
                       task=task[:100],
                       interrupt_type=type(e).__name__,
                       interrupt_value=str(e)[:200])
            raise e  # Let the orchestrator handle the interrupt
        except Exception as e:
            logger.error("task_agent_error",
                        error=str(e),
                        error_type=type(e).__name__)
            return f"Error executing task: {str(e)}"