"""Task Agent Tool - Executes complex multi-step tasks using plan-and-execute workflow."""

import asyncio
from typing import Type, Optional, Dict, Any, Annotated, List
from langchain_core.tools import BaseTool
from langgraph.prebuilt import InjectedState
from langgraph.errors import GraphInterrupt
from pydantic import BaseModel, Field
from src.utils.logging.framework import SmartLogger

logger = SmartLogger("orchestrator")


class TaskAgentInput(BaseModel):
    """Input schema for TaskAgentTool."""
    task: str = Field(description="The complex task to plan and execute")
    context: Optional[str] = Field(default=None, description="Additional context for the task")
    state: Annotated[dict, InjectedState] = Field(
        description="Injected state from LangGraph for accessing conversation context"
    )


class TaskAgentTool(BaseTool):
    """Routing tool that flags complex tasks for plan-execute workflow.
    
    This lightweight tool simply sets a flag for tasks that:
    - Require multiple steps
    - Need coordination across different agents
    - Involve complex data retrieval or updates
    - Require planning and replanning
    
    The actual plan-execute workflow runs as a separate node in the graph.
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
    
    ⚠️ NEVER create a task to save a record after creating or updating it!
    ⚠️ NEVER use task_agent for simple lookups or single-step tasks!
    ⚠️ NEVER use a system agent directly for complex workflows!
    """
    args_schema: Type[BaseModel] = TaskAgentInput
    
    def __init__(self):
        """Initialize routing tool."""
        super().__init__()
    
    
    
    def _run(self, task: str, context: Optional[str] = None, state: Annotated[Dict[str, Any], InjectedState] = None) -> str:
        """Execute the tool synchronously."""
        # Simply delegate to async version
        import asyncio
        result = asyncio.run(self._arun(task, context, state=state))
        # Return the routing message for display
        return result.get("routing_message", "Routing to plan-execute workflow...")
    
    async def _arun(self, task: str, context: Optional[str] = None, state: Annotated[Dict[str, Any], InjectedState] = None) -> Dict[str, Any]:
        """Set routing flag for plan-execute workflow.
        
        This tool doesn't execute the task itself - it just signals
        that the task should be routed to the plan-execute node.
        
        Returns a dict with routing info that the tools_node will process.
        """
        logger.info("task_agent_routing",
                   task=task[:100],
                   has_context=bool(context))
        
        # Get current state from the injected state
        parent_state = state if state else {}
        
        # Return a message indicating routing and the state updates
        # The actual state updates will be handled by the tools_node
        routing_message = f"Routing task to plan-execute workflow: {task[:100]}{'...' if len(task) > 100 else ''}"
        
        # Store the task and context in the parent state for the plan-execute node
        # This is done through the tool result which the tools_node will process
        return {
            "needs_plan_execute": True,
            "plan_execute_task": task,
            "plan_execute_context": context,
            "routing_message": routing_message
        }