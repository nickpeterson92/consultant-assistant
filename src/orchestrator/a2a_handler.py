"""Clean A2A handler for pure plan-execute orchestrator."""

import uuid
from typing import Dict, Any

from langchain_core.messages import HumanMessage
# Command will be imported when needed

from src.utils.logging import get_logger
from src.utils.config import get_conversation_config
from .types import A2AResponse, A2AMetadata

logger = get_logger("orchestrator")


class CleanOrchestratorA2AHandler:
    """Clean A2A handler that delegates to pure plan-execute graph."""
    
    def __init__(self, plan_execute_graph, agent_registry):
        """Initialize with plan-execute graph and agent registry."""
        self.graph = plan_execute_graph
        self.agent_registry = agent_registry
        self.active_tasks = {}  # Track active tasks for progress
        
    async def process_task(self, params: Dict[str, Any]) -> A2AResponse:
        """Process A2A task using pure plan-execute graph."""
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
            
            # Create thread ID
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
                "status": "processing"
            }
            
            # Check if we're resuming from an interrupt
            if context.get("resume_data"):
                # Resume from interrupt
                from langgraph.pregel import Command #type: ignore[import]
                result = await self.graph.graph.ainvoke(
                    Command(resume=context["resume_data"]),
                    config
                )
            else:
                # Load existing state or create fresh state
                try:
                    # Try to get existing state from the graph checkpointer
                    existing_state = self.graph.graph.get_state(config)
                    
                    if existing_state and existing_state.values:
                        # Continue existing conversation
                        logger.info("continuing_conversation", 
                                   component="orchestrator",
                                   task_id=task_id,
                                   thread_id=thread_id,
                                   existing_messages=len(existing_state.values.get("messages", [])),
                                   existing_plan=bool(existing_state.values.get("plan")))
                        
                        # Add new message to existing state
                        new_message = HumanMessage(content=instruction)
                        updated_state = existing_state.values.copy()
                        updated_state["messages"] = updated_state.get("messages", []) + [new_message]
                        updated_state["original_request"] = instruction  # Update with latest request
                        
                        result = await self.graph.graph.ainvoke(updated_state, config)
                        
                    else:
                        # Start new conversation with fresh state
                        logger.info("starting_new_conversation", 
                                   component="orchestrator",
                                   task_id=task_id,
                                   thread_id=thread_id,
                                   instruction=instruction)
                        
                        from .plan_execute_state import create_initial_state
                        initial_state = create_initial_state(instruction)
                        initial_state["messages"] = [HumanMessage(content=instruction)]
                        
                        result = await self.graph.graph.ainvoke(initial_state, config)
                        
                except Exception as state_error:
                    logger.warning("state_loading_error", 
                                 component="orchestrator",
                                 task_id=task_id,
                                 error=str(state_error),
                                 fallback_to_fresh_state=True)
                    
                    # Fallback to fresh state if state loading fails
                    from .plan_execute_state import create_initial_state
                    initial_state = create_initial_state(instruction)
                    initial_state["messages"] = [HumanMessage(content=instruction)]
                    
                    result = await self.graph.graph.ainvoke(initial_state, config)
                
                logger.info("graph_invoke_start", 
                           component="orchestrator",
                           task_id=task_id,
                           instruction=instruction)
                
                print("🚀 DEBUG: About to invoke graph - this should appear in console")
                logger.info("about_to_invoke_graph", result_plan=result.get("plan"))
                print("✅ DEBUG: Graph invocation returned - this should appear in console")
                logger.info("graph_invocation_returned", result_plan=result.get("plan"))
                
                logger.info("graph_invoke_complete", 
                           component="orchestrator",
                           task_id=task_id,
                           plan_status=result.get("plan", {}).get("status", "no_plan"))
            
            # Extract response
            response_content = self._extract_response_content(result)
            
            # Mark task as complete
            self.active_tasks[task_id]["status"] = "completed"
            
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
                "metadata": {},
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
            
            return {
                "artifacts": [{
                    "id": f"orchestrator-error-{task_id}",
                    "task_id": task_id,
                    "content": f"Error: {str(e)}",
                    "content_type": "text/plain"
                }],
                "status": "failed",
                "metadata": {},
                "error": str(e)
            }
    
    def _extract_response_content(self, result: Dict[str, Any]) -> str:
        """Extract meaningful response content from graph result."""
        if not isinstance(result, dict):
            return "Task completed"
        
        messages = result.get("messages", [])
        if not messages:
            return "Task completed"
        
        # Debug: Log all messages to understand the structure
        logger.info("extracting_response_content", 
                   component="orchestrator",
                   message_count=len(messages),
                   message_types=[type(msg).__name__ for msg in messages])
        
        # Find the last AI message (should be the final result)
        for msg in reversed(messages):
            logger.info("examining_message", 
                       component="orchestrator",
                       message_type=type(msg).__name__,
                       has_content=hasattr(msg, 'content'),
                       content_preview=msg.content[:100] if hasattr(msg, 'content') and msg.content else "NO_CONTENT")
            
            if hasattr(msg, 'content') and msg.content:
                # Check if this is an AI message
                is_ai_message = type(msg).__name__ == "AIMessage"
                has_tool_calls = hasattr(msg, 'tool_calls') and msg.tool_calls
                is_system_message = msg.content.startswith("You are")
                
                logger.info("message_analysis",
                           component="orchestrator",
                           message_type=type(msg).__name__,
                           is_ai_message=is_ai_message,
                           has_tool_calls=has_tool_calls,
                           is_system_message=is_system_message)
                
                # Skip system messages and tool calls, but focus on AI messages
                if (not has_tool_calls and 
                    not is_system_message and
                    is_ai_message):
                    logger.info("selected_response_message", 
                               component="orchestrator",
                               message_type=type(msg).__name__,
                               content=msg.content)
                    return msg.content
        
        logger.warning("no_ai_message_found", component="orchestrator")
        return "Task completed"
    
    async def get_agent_card(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return orchestrator agent card."""
        stats = self.agent_registry.get_registry_stats()
        
        # Get online agent capabilities
        all_capabilities = ["orchestration", "task_routing", "multi_agent_coordination"]
        online_agents = []
        
        for agent in self.agent_registry.list_agents():
            if agent.status == "online" and agent.agent_card:
                online_agents.append(agent.name)
                all_capabilities.extend(agent.agent_card.capabilities)
        
        return {
            "name": "orchestrator",
            "version": "2.0.0",
            "description": "Pure plan-and-execute orchestrator for multi-agent coordination",
            "capabilities": list(set(all_capabilities)),
            "endpoints": {
                "process_task": "/a2a",
                "agent_card": "/a2a/agent-card"
            },
            "communication_modes": ["sync"],
            "metadata": {
                "framework": "langgraph-pure-plan-execute",
                "registered_agents": stats["total_agents"],
                "online_agents": stats["online_agents"],
                "online_agent_names": online_agents
            }
        }
    
    async def get_progress(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get progress for active task."""
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
            "message": "Progress retrieved"
        }
    
    def cleanup_task(self, task_id: str):
        """Clean up completed task."""
        if task_id in self.active_tasks:
            del self.active_tasks[task_id]