"""Clean A2A handler for pure plan-execute orchestrator."""

import uuid
import json
import asyncio
from typing import Dict, Any, AsyncGenerator
from datetime import datetime

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
        self.streaming_clients = {}  # Track SSE clients by task_id
        self.task_status_cache = {}  # Cache task statuses to detect changes
        
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
        
        # Extract the last meaningful AI message for the response
        ai_message = None
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
                
                # Take the last meaningful AI message (skip system messages and tool calls)
                if (not has_tool_calls and 
                    not is_system_message and
                    is_ai_message):
                    ai_message = msg.content
                    break
        
        if ai_message:
            # Return the last meaningful AI message
            logger.info("selected_ai_message", 
                       component="orchestrator",
                       message_length=len(ai_message))
            return ai_message
        
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
            "communication_modes": ["sync", "streaming"],
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
        if task_id in self.streaming_clients:
            del self.streaming_clients[task_id]
        if task_id in self.task_status_cache:
            del self.task_status_cache[task_id]
    
    async def process_task_with_streaming(self, params: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Process A2A task with SSE streaming support."""
        task_id = "unknown"
        
        try:
            # Extract task data
            task_data = params.get("task", params)
            task_id = task_data.get("id", task_data.get("task_id", str(uuid.uuid4())[:8]))
            instruction = task_data.get("instruction", "")
            context = task_data.get("context", {})
            
            logger.info("a2a_streaming_task_start", 
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
            
            # Send initial task start event
            yield self._format_sse_event("task_started", {
                "task_id": task_id,
                "instruction": instruction,
                "thread_id": thread_id,
                "timestamp": datetime.now().isoformat()
            })
            
            # Check if we're resuming from an interrupt
            if context.get("resume_data"):
                # Resume from interrupt
                from langgraph.pregel import Command #type: ignore[import]
                
                # Stream the execution
                async for event in self.graph.graph.astream(
                    Command(resume=context["resume_data"]),
                    config,
                    stream_mode="updates"
                ):
                    yield self._process_graph_event(event, task_id)
                    
            else:
                # Load existing state or create fresh state
                try:
                    # Try to get existing state from the graph checkpointer
                    existing_state = self.graph.graph.get_state(config)
                    
                    if existing_state and existing_state.values:
                        # Continue existing conversation
                        logger.info("continuing_conversation_streaming", 
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
                        
                        # Stream the execution
                        async for event in self.graph.graph.astream(
                            updated_state,
                            config,
                            stream_mode="updates"
                        ):
                            yield self._process_graph_event(event, task_id)
                            
                    else:
                        # Start new conversation with fresh state
                        logger.info("starting_new_conversation_streaming", 
                                   component="orchestrator",
                                   task_id=task_id,
                                   thread_id=thread_id,
                                   instruction=instruction)
                        
                        from .plan_execute_state import create_initial_state
                        initial_state = create_initial_state(instruction)
                        initial_state["messages"] = [HumanMessage(content=instruction)]
                        
                        # Stream the execution
                        async for event in self.graph.graph.astream(
                            initial_state,
                            config,
                            stream_mode="updates"
                        ):
                            yield self._process_graph_event(event, task_id)
                            
                except Exception as state_error:
                    logger.warning("state_loading_error_streaming", 
                                 component="orchestrator",
                                 task_id=task_id,
                                 error=str(state_error),
                                 fallback_to_fresh_state=True)
                    
                    # Fallback to fresh state if state loading fails
                    from .plan_execute_state import create_initial_state
                    initial_state = create_initial_state(instruction)
                    initial_state["messages"] = [HumanMessage(content=instruction)]
                    
                    # Stream the execution
                    async for event in self.graph.graph.astream(
                        initial_state,
                        config,
                        stream_mode="updates"
                    ):
                        yield self._process_graph_event(event, task_id)
            
            # Mark task as complete
            self.active_tasks[task_id]["status"] = "completed"
            
            # Send completion event
            yield self._format_sse_event("task_completed", {
                "task_id": task_id,
                "status": "completed",
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info("a2a_streaming_task_complete",
                       component="orchestrator", 
                       task_id=task_id,
                       success=True)
                       
        except Exception as e:
            logger.error("a2a_streaming_task_error",
                        component="orchestrator",
                        task_id=task_id,
                        error=str(e))
            
            # Mark task as failed
            if task_id in self.active_tasks:
                self.active_tasks[task_id]["status"] = "failed"
            
            # Send error event
            yield self._format_sse_event("task_error", {
                "task_id": task_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    def _process_graph_event(self, event: Dict[str, Any], task_id: str) -> str:
        """Process a graph streaming event and convert to SSE format."""
        try:
            # LangGraph streaming events come as {node_name: node_output}
            for node_name, node_output in event.items():
                logger.info("processing_graph_event",
                           component="orchestrator",
                           task_id=task_id,
                           node_name=node_name,
                           output_type=type(node_output).__name__,
                           output_keys=list(node_output.keys()) if isinstance(node_output, dict) else "not_dict")
                
                if node_name == "planner" and "plan" in node_output:
                    # Plan was created
                    plan = node_output["plan"]
                    return self._format_sse_event("plan_created", {
                        "task_id": task_id,
                        "plan": plan,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                elif node_name == "agent":
                    # Agent node execution - check for task progress and plan updates
                    if "plan" in node_output:
                        plan = node_output["plan"]
                        tasks = plan.get("tasks", [])
                        
                        # Get cached task statuses for this task_id to detect changes
                        cached_statuses = self.task_status_cache.get(task_id, {})
                        
                        # Check each task for status changes FIRST
                        for task in tasks:
                            task_internal_id = task.get("id", "")
                            current_status = task.get("status", "")
                            previous_status = cached_statuses.get(task_internal_id, "")
                            
                            # Update cache
                            cached_statuses[task_internal_id] = current_status
                            
                            # Only emit events for newly changed statuses
                            if current_status != previous_status:
                                if current_status == "in_progress":
                                    self.task_status_cache[task_id] = cached_statuses
                                    return self._format_sse_event("task_started", {
                                        "task_id": task_id,
                                        "task": task,
                                        "timestamp": datetime.now().isoformat()
                                    })
                                elif current_status == "completed":
                                    self.task_status_cache[task_id] = cached_statuses
                                    return self._format_sse_event("task_completed", {
                                        "task_id": task_id,
                                        "task": task,
                                        "success": True,
                                        "content": task.get("content", ""),
                                        "timestamp": datetime.now().isoformat()
                                    })
                                elif current_status == "failed":
                                    self.task_status_cache[task_id] = cached_statuses
                                    return self._format_sse_event("task_error", {
                                        "task_id": task_id,
                                        "task": task,
                                        "content": task.get("content", ""),
                                        "error": task.get("error", "Task failed"),
                                        "timestamp": datetime.now().isoformat()
                                    })
                        
                        # Update cache even if no events were emitted
                        self.task_status_cache[task_id] = cached_statuses
                        
                        # Check if all tasks are completed/failed (plan is done) AFTER processing individual tasks
                        all_done = all(task.get("status") in ["completed", "failed"] for task in tasks)
                        if all_done and tasks:
                            # Include the LLM-generated summary in the plan completion event
                            plan_summary = plan.get("summary", "")
                            return self._format_sse_event("plan_completed", {
                                "task_id": task_id,
                                "plan": plan,
                                "summary": plan_summary,
                                "timestamp": datetime.now().isoformat()
                            })
                    
                    # Check for completed task results with response content
                    if "task_results" in node_output:
                        task_results = node_output["task_results"]
                        if task_results:
                            # Find the most recent completed task with a response
                            for task_result in reversed(task_results):
                                if (task_result.get("success") and 
                                    "result" in task_result and 
                                    isinstance(task_result["result"], dict) and 
                                    "response" in task_result["result"]):
                                    response_content = task_result["result"]["response"]
                                    if response_content:
                                        return self._format_sse_event("agent_response", {
                                            "task_id": task_id,
                                            "content": str(response_content),
                                            "timestamp": datetime.now().isoformat()
                                        })
                    
                    # Also handle agent messages (fallback)
                    if "messages" in node_output:
                        messages = node_output["messages"]
                        if messages:
                            # Find the last AI message with content
                            for msg in reversed(messages):
                                if hasattr(msg, 'content') and msg.content:
                                    msg_type = type(msg).__name__
                                    msg_content = str(msg.content)
                                    # Skip tool messages and system messages
                                    if (msg_type != "ToolMessage" and 
                                        msg_type != "SystemMessage" and 
                                        not msg_content.startswith("You are")):
                                        return self._format_sse_event("agent_response", {
                                            "task_id": task_id,
                                            "content": msg_content,
                                            "timestamp": datetime.now().isoformat()
                                        })
                            
                elif node_name == "replan":
                    # Replanning occurred
                    return self._format_sse_event("plan_updated", {
                        "task_id": task_id,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                elif node_name == "plan_summary":
                    # Summary generation occurred
                    if "plan" in node_output and node_output["plan"].get("summary"):
                        return self._format_sse_event("summary_generated", {
                            "task_id": task_id,
                            "summary": node_output["plan"]["summary"],
                            "timestamp": datetime.now().isoformat()
                        })
                    else:
                        return self._format_sse_event("summary_started", {
                            "task_id": task_id,
                            "timestamp": datetime.now().isoformat()
                        })
            
            # Generic node update
            return self._format_sse_event("node_update", {
                "task_id": task_id,
                "node_name": list(event.keys())[0] if event else "unknown",
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error("graph_event_processing_error",
                        component="orchestrator",
                        task_id=task_id,
                        error=str(e))
            # Return a generic update event instead of failing
            return self._format_sse_event("node_update", {
                "task_id": task_id,
                "node_name": list(event.keys())[0] if event else "unknown",
                "timestamp": datetime.now().isoformat()
            })
    
    def _format_sse_event(self, event_type: str, data: Dict[str, Any]) -> str:
        """Format data as SSE event."""
        # Import here to avoid circular dependency
        from src.utils.agents.message_processing.unified_serialization import serialize_messages_for_json
        from langchain_core.messages import BaseMessage
        
        # Deep copy and serialize any LangChain objects in the data
        def serialize_nested_data(obj):
            """Recursively serialize nested data structures containing LangChain objects."""
            if isinstance(obj, BaseMessage):
                return serialize_messages_for_json(obj)
            elif isinstance(obj, list):
                return [serialize_nested_data(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: serialize_nested_data(v) for k, v in obj.items()}
            else:
                return obj
        
        serialized_data = serialize_nested_data(data)
        
        event_data = {
            "event": event_type,
            "data": serialized_data
        }
        
        try:
            return f"data: {json.dumps(event_data)}\n\n"
        except TypeError as e:
            # Fallback: log the error and return a safe event
            logger.error("sse_event_serialization_error",
                        component="orchestrator",
                        event_type=event_type,
                        error=str(e),
                        data_keys=list(data.keys()))
            return f"data: {json.dumps({'event': event_type, 'data': {'error': 'serialization_failed'}})}\n\n"