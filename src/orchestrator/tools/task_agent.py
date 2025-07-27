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
    state: Annotated[dict, InjectedState] = Field(
        description="Injected state from LangGraph for accessing conversation context"
    )


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
            # Create a fresh message list with just the task to avoid tool_call_id conflicts
            from langchain_core.messages import HumanMessage
            fresh_messages = [HumanMessage(content=task)]
            
            plan_execute_input = {
                "input": task,
                "messages": fresh_messages,  # Fresh messages with just the task
                "thread_id": parent_state.get("thread_id", "default-thread"),
                "user_id": parent_state.get("user_id", "default_user"),
                "task_id": parent_state.get("task_id", f"task_{hash(task)}"),
                "past_steps": [],  # Initialize empty past_steps
                "plan": [],  # Initialize empty plan
                "response": "",  # Initialize empty response
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
            logger.info("task_agent_invoking_graph",
                       input=task[:100],
                       has_messages=bool(fresh_messages),
                       thread_id=plan_execute_input.get("thread_id"))
            
            result = await graph.ainvoke(plan_execute_input, config)
            
            logger.info("task_agent_graph_complete",
                       result_keys=list(result.keys()),
                       has_response="response" in result,
                       response_preview=result.get("response", "")[:100] if "response" in result else None)
            
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
                       interrupt_value=str(e)[:200],
                       has_args=hasattr(e, 'args'),
                       args_count=len(e.args) if hasattr(e, 'args') else 0,
                       first_arg_type=type(e.args[0]).__name__ if hasattr(e, 'args') and e.args else None,
                       is_dict=isinstance(e.args[0], dict) if hasattr(e, 'args') and e.args else False)
            raise e  # Let the orchestrator handle the interrupt
        except Exception as e:
            logger.error("task_agent_error",
                        error=str(e),
                        error_type=type(e).__name__)
            return f"Error executing task: {str(e)}"