"""Simple A2A handler for the orchestrator."""

import uuid
from typing import Dict, Any
from datetime import datetime

from src.utils.logging import get_logger
from src.a2a import AgentCard
from .plan_and_execute import create_plan_execute_graph

logger = get_logger("orchestrator")


class OrchestratorA2AHandler:
    """Simple A2A handler for the orchestrator."""
    
    def __init__(self):
        """Initialize the A2A handler."""
        self.graph = None
        self.active_tasks = {}
        
    def set_graph(self, graph):
        """Set the plan-execute graph instance."""
        self.graph = graph
    
    async def process_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process A2A task using plan-execute graph."""
        task_id = "unknown"
        
        try:
            # Extract task data
            task_data = params.get("task", params)
            task_id = task_data.get("id", task_data.get("task_id", str(uuid.uuid4())[:8]))
            instruction = task_data.get("instruction", "")
            context = task_data.get("context", {})
            
            logger.info("a2a_task_start", 
                       component="orchestrator",
                       task_id=task_id,
                       instruction=instruction)
            
            # Create thread ID for the graph
            thread_id = context.get("thread_id", f"a2a-{task_id}-{str(uuid.uuid4())[:8]}")
            
            # Configuration for the graph
            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "user_id": context.get("user_id", "a2a_user")
                }
            }
            
            # Track this task
            self.active_tasks[task_id] = {
                "thread_id": thread_id,
                "instruction": instruction,
                "status": "processing",
                "started_at": datetime.now().isoformat()
            }
            
            # Create initial state
            initial_state = {
                "input": instruction,
                "plan": [],
                "past_steps": [],
                "response": ""
            }
            
            # Execute the graph
            result = await self.graph.ainvoke(initial_state, config)
            
            # Extract response and plan data
            response_content = self._extract_response_content(result)
            plan_data = result.get("plan", []) if isinstance(result, dict) else []
            
            # Mark task as complete
            self.active_tasks[task_id]["status"] = "completed"
            self.active_tasks[task_id]["completed_at"] = datetime.now().isoformat()
            
            logger.info("a2a_task_complete",
                       component="orchestrator",
                       task_id=task_id,
                       success=True)
            
            return {
                "artifacts": [{
                    "id": f"orchestrator-{task_id}",
                    "task_id": task_id,
                    "content": response_content,
                    "content_type": "text/plain"
                }],
                "status": "completed",
                "metadata": {
                    "task_id": task_id,
                    "thread_id": thread_id,
                    "execution_time": self.active_tasks[task_id].get("completed_at"),
                    "plan": plan_data
                },
                "error": None
            }
            
        except Exception as e:
            logger.error("a2a_task_error",
                        component="orchestrator",
                        task_id=task_id,
                        error=str(e))
            
            # Mark task as failed
            if task_id in self.active_tasks:
                self.active_tasks[task_id]["status"] = "failed"
                self.active_tasks[task_id]["error"] = str(e)
            
            return {
                "artifacts": [{
                    "id": f"orchestrator-error-{task_id}",
                    "task_id": task_id,
                    "content": f"Error: {str(e)}",
                    "content_type": "text/plain"
                }],
                "status": "failed",
                "metadata": {
                    "task_id": task_id,
                    "error": str(e)
                },
                "error": str(e)
            }
    
    def _extract_response_content(self, result: Dict[str, Any]) -> str:
        """Extract meaningful response content from graph result."""
        if not isinstance(result, dict):
            return "Task completed"
        
        # Try to get response from the result
        response = result.get("response", "")
        if response:
            return response
        
        # Fallback: get input if no response
        input_text = result.get("input", "")
        if input_text:
            return f"Processed: {input_text}"
        
        return "Task completed"
    
    async def get_agent_card(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return orchestrator agent card."""
        return {
            "name": "orchestrator",
            "version": "1.0.0",
            "description": "Multi-agent orchestrator with plan-and-execute workflow",
            "capabilities": [
                "orchestration",
                "task_planning",
                "task_execution",
                "multi_agent_coordination"
            ],
            "endpoints": {
                "process_task": "/a2a",
                "agent_card": "/a2a/agent-card"
            },
            "communication_modes": ["sync"],
            "metadata": {
                "framework": "langgraph-plan-execute",
                "active_tasks": len(self.active_tasks)
            }
        }
    
    async def get_task_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get status of a specific task."""
        task_id = params.get("task_id")
        
        if not task_id or task_id not in self.active_tasks:
            return {
                "success": False,
                "data": {},
                "message": "Task not found"
            }
        
        return {
            "success": True,
            "data": self.active_tasks[task_id],
            "message": "Task status retrieved"
        }