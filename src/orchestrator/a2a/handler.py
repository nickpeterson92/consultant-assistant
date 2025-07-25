"""Simple A2A handler for the orchestrator."""

import uuid
from typing import Dict, Any
from datetime import datetime

from langgraph.errors import GraphInterrupt
from src.utils.logging.framework import SmartLogger, log_execution
from src.utils.thread_utils import create_thread_id

logger = SmartLogger("orchestrator")


class OrchestratorA2AHandler:
    """Simple A2A handler for the orchestrator."""
    
    def __init__(self):
        """Initialize the A2A handler."""
        self.graph = None
        self.active_tasks = {}
        
    def set_graph(self, graph):
        """Set the plan-execute graph instance."""
        self.graph = graph
    
    @log_execution("orchestrator", "process_task", include_args=False, include_result=False)  # Sensitive data
    async def process_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process A2A task using plan-execute graph."""
        task_id = "unknown"
        
        try:
            # Extract task data
            task_data = params.get("task", params)
            task_id = task_data.get("id", task_data.get("task_id", str(uuid.uuid4())[:8]))
            instruction = task_data.get("instruction", "")
            context = task_data.get("context", {})
            
            # Check if this is resuming from an interrupt
            is_resume = context.get("resume_from_interrupt", False)
            user_response = context.get("user_response", "")
            
            logger.info("a2a_task_start", 
                       component="orchestrator",
                       task_id=task_id,
                       instruction=instruction[:100],
                       is_resume=is_resume,
                       has_user_response=bool(user_response),
                       context_thread_id=context.get("thread_id"))
            
            # Create thread ID for the graph
            # CRITICAL: For resume operations, preserve the original thread_id
            # For new operations, use a unique thread_id to avoid stale interrupt state
            if is_resume:
                thread_id = context.get("thread_id")
                if not thread_id:
                    logger.error("resume_missing_thread_id", component="orchestrator", task_id=task_id)
                    raise ValueError("Resume operation requires thread_id in context")
            else:
                thread_id = context.get("thread_id", create_thread_id("orchestrator", task_id))
            
            # Configuration for the graph
            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "user_id": context.get("user_id", "default_user")  # Use default_user as fallback
                }
            }
            
            logger.info("using_thread_id",
                       component="orchestrator", 
                       task_id=task_id,
                       final_thread_id=thread_id,
                       context_provided_thread_id=context.get("thread_id"))
            
            # Track this task
            self.active_tasks[task_id] = {
                "thread_id": thread_id,
                "instruction": instruction,
                "status": "processing",
                "started_at": datetime.now().isoformat(),
                "is_resume": is_resume
            }
            
            if is_resume and user_response:
                # Resume interrupted graph with user response
                logger.info("resuming_graph_execution",
                           component="orchestrator",
                           task_id=task_id,
                           user_response=user_response[:100])
                
                # Resume the graph with the user's input using LangGraph Command
                from langgraph.types import Command
                result = await self.graph.ainvoke(Command(resume=user_response), config)
                
            else:
                # For new requests, we want to:
                # 1. Preserve conversation messages (persistent across requests)
                # 2. Reset plan state (fresh planning for each request)
                # 3. Add current user message to conversation
                initial_state = {
                    "input": instruction,
                    "plan": [],  # Fresh plan state
                    "past_steps": [],  # Fresh execution state
                    "response": "",
                    "user_visible_responses": [],
                    "messages": [("user", instruction)],  # Current user message (LangGraph will merge with existing)
                    "thread_id": thread_id,  # Add thread_id to state for memory integration
                    "task_id": task_id,  # Add actual task_id for SSE events
                    "user_id": context.get("user_id", "default_user")  # Add user_id to state
                }
                
                # Execute the graph
                result = await self.graph.ainvoke(initial_state, config)
            
            # Check if the graph was interrupted (LangGraph with checkpointing)
            if isinstance(result, dict) and "__interrupt__" in result:
                interrupt_value = result["__interrupt__"]
                
                # Convert Interrupt object to JSON-serializable format
                if hasattr(interrupt_value, 'value'):
                    # Extract the actual value from the Interrupt object
                    interrupt_content = str(interrupt_value.value)
                elif isinstance(interrupt_value, list) and interrupt_value:
                    # Handle list of Interrupt objects
                    interrupt_content = str(interrupt_value[0].value if hasattr(interrupt_value[0], 'value') else interrupt_value[0])
                else:
                    # Fallback: convert to string
                    interrupt_content = str(interrupt_value)
                
                logger.info("graph_interrupted",
                           component="orchestrator", 
                           task_id=task_id,
                           interrupt_value=interrupt_content[:200])
                
                # Mark task as interrupted
                if task_id in self.active_tasks:
                    self.active_tasks[task_id]["status"] = "interrupted"
                    self.active_tasks[task_id]["interrupt_value"] = interrupt_content
                
                # Check if there are user_visible_responses that should be shown before the interrupt
                artifacts = []
                
                # Add any user-visible responses first (like search results)
                if isinstance(result, dict) and "user_visible_responses" in result:
                    for i, visible_response in enumerate(result["user_visible_responses"]):
                        artifacts.append({
                            "id": f"orchestrator-visible-{task_id}-{i}",
                            "task_id": task_id,
                            "content": visible_response,
                            "content_type": "text/plain"
                        })
                
                # Then add the interrupt/clarification request
                artifacts.append({
                    "id": f"orchestrator-interrupt-{task_id}",
                    "task_id": task_id,
                    "content": interrupt_content,
                    "content_type": "text/plain"
                })
                
                return {
                    "artifacts": artifacts,
                    "status": "interrupted",
                    "metadata": {
                        "task_id": task_id,
                        "thread_id": thread_id,
                        "interrupt_value": interrupt_content,
                        "resumable": True
                    },
                    "error": None
                }
            
            # Extract response and plan data
            response_content = self._extract_response_content(result)
            plan_data = result.get("plan", []) if isinstance(result, dict) else []
            
            # Mark task as complete and clear any interrupt state
            self.active_tasks[task_id]["status"] = "completed"
            self.active_tasks[task_id]["completed_at"] = datetime.now().isoformat()
            
            # Clear interrupt state if this was a resumed task
            if "interrupt_value" in self.active_tasks[task_id]:
                del self.active_tasks[task_id]["interrupt_value"]
                logger.info("interrupt_state_cleared",
                           component="orchestrator",
                           task_id=task_id,
                           was_resume=is_resume)
            
            
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
            
        except GraphInterrupt as gi:
            # This is an expected interrupt - not an error
            from src.orchestrator.workflow.interrupt_handler import InterruptHandler
            
            # Get current state to check for interrupt clashes
            current_state = self.graph.get_state(config)
            
            # Check if this is a clash between user and agent interrupts
            if InterruptHandler.detect_interrupt_clash(current_state.values, gi):
                # User interrupt takes precedence
                interrupt_type = "user_escape"
                interrupt_content = current_state.values.get("interrupt_reason", "User requested plan modification")
                is_user_interrupt = True
                logger.info("interrupt_clash_resolved_user_wins",
                           component="orchestrator",
                           task_id=task_id,
                           note="User interrupt takes precedence over agent interrupt")
            else:
                # Normal interrupt handling
                interrupt_value = gi.value
                is_user_interrupt = False
                interrupt_type = "model"
                
                if isinstance(interrupt_value, dict) and interrupt_value.get("type") == "user_escape":
                    is_user_interrupt = True
                    interrupt_type = "user_escape"
                    interrupt_content = interrupt_value.get("reason", "User requested plan modification")
                else:
                    # This is a HumanInputTool interrupt
                    interrupt_content = str(interrupt_value)
            
            logger.info("graph_interrupted",
                       component="orchestrator",
                       task_id=task_id,
                       interrupt_type=interrupt_type,
                       interrupt_value=interrupt_content[:200])
            
            # Mark task as interrupted
            if task_id in self.active_tasks:
                self.active_tasks[task_id]["status"] = "interrupted"
                self.active_tasks[task_id]["interrupt_value"] = interrupt_content
                self.active_tasks[task_id]["interrupt_type"] = interrupt_type
            
            # Record interrupt in observer
            from src.orchestrator.observers.interrupt_observer import get_interrupt_observer
            interrupt_observer = get_interrupt_observer()
            
            # Get current state for context
            config = {"configurable": {"thread_id": thread_id}}
            current_state = self.graph.get_state(config)
            
            # Determine the actual interrupt type for the observer
            observer_interrupt_type = "user_escape" if is_user_interrupt else "human_input"
            
            interrupt_observer.record_interrupt(
                thread_id=thread_id,
                interrupt_type=observer_interrupt_type,
                reason=interrupt_content,
                current_plan=current_state.values.get("plan", []),
                state=current_state.values
            )
            
            return {
                "artifacts": [{
                    "id": f"orchestrator-interrupt-{task_id}",
                    "task_id": task_id,
                    "content": interrupt_content,
                    "content_type": "text/plain"
                }],
                "status": "interrupted",
                "metadata": {
                    "task_id": task_id,
                    "thread_id": thread_id,
                    "interrupt_value": interrupt_content,
                    "interrupt_type": interrupt_type,
                    "resumable": True
                },
                "error": None
            }
            
        except Exception as e:
            
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
    
    @log_execution("orchestrator", "get_agent_card", include_args=True, include_result=True)
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
    
    async def interrupt_task(self, thread_id: str, reason: str = "user_escape") -> Dict[str, Any]:
        """Interrupt a running task thread using LangGraph's state update."""
        try:
            if not thread_id:
                return {
                    "success": False,
                    "message": "thread_id is required"
                }
            
            logger.info("interrupt_task_request",
                       thread_id=thread_id,
                       reason=reason)
            
            # Use LangGraph's interrupt mechanism
            config = {"configurable": {"thread_id": thread_id}}
            
            # Check current state to see if there's already an interrupt
            current_state = self.graph.get_state(config)
            if current_state.values.get("user_interrupted", False):
                logger.info("interrupt_already_pending",
                           thread_id=thread_id,
                           existing_reason=current_state.values.get("interrupt_reason"))
                return {
                    "success": True,
                    "message": "Interrupt already pending"
                }
            
            # Update the thread state to set user interrupt flag
            # This distinguishes user interrupts from HumanInputTool interrupts
            self.graph.update_state(
                config,
                {
                    "user_interrupted": True,
                    "interrupt_reason": reason,
                    "interrupt_timestamp": datetime.now().isoformat()
                }
            )
            
            # Record interrupt in observer for persistent tracking
            from src.orchestrator.observers.interrupt_observer import get_interrupt_observer
            interrupt_observer = get_interrupt_observer()
            interrupt_observer.record_interrupt(
                thread_id=thread_id,
                interrupt_type="user_escape",
                reason=reason,
                current_plan=current_state.values.get("plan", []),
                state=current_state.values
            )
            
            logger.info("interrupt_task_success",
                       thread_id=thread_id)
            
            return {
                "success": True,
                "message": "Task interrupted successfully"
            }
            
        except Exception as e:
            logger.error("interrupt_task_error",
                        error=str(e),
                        thread_id=thread_id)
            return {
                "success": False,
                "message": f"Error interrupting task: {str(e)}"
            }