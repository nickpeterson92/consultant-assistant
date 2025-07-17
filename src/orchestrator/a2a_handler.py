"""Clean A2A handler for pure plan-execute orchestrator."""

import uuid
import json
import asyncio
import weakref
from typing import Dict, Any, AsyncGenerator
from datetime import datetime
from aiohttp import web, WSMsgType

from langchain_core.messages import HumanMessage
# Command will be imported when needed

from src.utils.logging import get_logger
from src.utils.config import get_conversation_config
from .types import A2AResponse, A2AMetadata

logger = get_logger("orchestrator")


class CleanOrchestratorA2AHandler:
    """Clean A2A handler that delegates to pure plan-execute graph."""
    
    def __init__(self, plan_execute_graph, agent_registry, plan_modification_extractor=None):
        """Initialize with plan-execute graph and agent registry."""
        self.graph = plan_execute_graph
        self.agent_registry = agent_registry
        self.plan_modification_extractor = plan_modification_extractor
        self.active_tasks = {}  # Track active tasks for progress
        self.streaming_clients = {}  # Track SSE clients by task_id
        self.task_status_cache = {}  # Cache task statuses to detect changes
        self.websocket_clients = {}  # Track WebSocket clients by thread_id
        self.client_threads = {}  # Track thread_id by client_id for cleanup
        
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
                from langgraph.types import Command
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
    
    async def interrupt_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Interrupt a running task thread."""
        try:
            thread_id = params.get("thread_id")
            reason = params.get("reason", "user_interrupt")
            
            if not thread_id:
                return {
                    "success": False,
                    "message": "thread_id is required"
                }
            
            logger.info("interrupt_task_request",
                       component="orchestrator",
                       thread_id=thread_id,
                       reason=reason)
            
            # Use LangGraph's interrupt mechanism
            config = {"configurable": {"thread_id": thread_id}}
            
            # Update the thread state to set an interrupt flag
            self.graph.graph.update_state(
                config,
                {
                    "interrupted": True,
                    "interrupt_data": {
                        "interrupt_type": "user_escape",
                        "reason": reason,
                        "created_at": datetime.now().isoformat()
                    }
                }
            )
            
            # Broadcast interrupt to all connected agents via WebSocket
            await self._broadcast_agent_interrupt(thread_id, reason)
            
            logger.info("interrupt_task_success",
                       component="orchestrator", 
                       thread_id=thread_id)
            
            return {
                "success": True,
                "message": "Task interrupted successfully"
            }
            
        except Exception as e:
            logger.error("interrupt_task_error",
                        component="orchestrator",
                        error=str(e))
            return {
                "success": False,
                "message": f"Error interrupting task: {str(e)}"
            }
    
    async def _broadcast_agent_interrupt(self, thread_id: str, reason: str):
        """Broadcast interrupt to all registered agents via WebSocket.
        
        Args:
            thread_id: The orchestrator thread ID
            reason: Reason for the interrupt
        """
        try:
            from src.orchestrator.agent_registry import get_agent_registry
            registry = get_agent_registry()
            
            if not registry:
                logger.warning("agent_interrupt_broadcast_no_registry",
                              component="orchestrator",
                              thread_id=thread_id)
                return
            
            # Get all registered agents
            agents = registry.get_all_agents()
            logger.info("agent_interrupt_broadcast_start",
                       component="orchestrator",
                       thread_id=thread_id,
                       reason=reason,
                       agent_count=len(agents))
            
            # Broadcast to each agent's interrupt WebSocket
            import asyncio
            import aiohttp
            import json
            
            async def send_interrupt_to_agent(agent):
                """Send interrupt to a single agent."""
                try:
                    # Parse agent endpoint to get WebSocket URL
                    endpoint = agent.endpoints.get("process_task", "")
                    if not endpoint:
                        return
                    
                    # Convert HTTP endpoint to WebSocket interrupt endpoint
                    ws_url = endpoint.replace("http://", "ws://").replace("/a2a", "/a2a/interrupt")
                    
                    # Connect to agent's interrupt WebSocket
                    session = aiohttp.ClientSession()
                    try:
                        async with session.ws_connect(ws_url, timeout=aiohttp.ClientTimeout(total=5)) as ws:
                            # Send interrupt message
                            await ws.send_str(json.dumps({
                                "jsonrpc": "2.0",
                                "method": "interrupt_task", 
                                "params": {
                                    "task_id": thread_id,  # Use thread_id as task_id
                                    "reason": reason
                                }
                            }))
                            
                            # Wait for acknowledgment
                            async for msg in ws:
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    data = json.loads(msg.data)
                                    if data.get("method") == "interrupt_ack":
                                        logger.info("agent_interrupt_ack",
                                                   component="orchestrator",
                                                   agent_id=agent.id,
                                                   thread_id=thread_id)
                                        break
                                elif msg.type == aiohttp.WSMsgType.ERROR:
                                    break
                    finally:
                        await session.close()
                        
                except Exception as e:
                    logger.warning("agent_interrupt_send_failed",
                                  component="orchestrator",
                                  agent_id=agent.id,
                                  error=str(e))
            
            # Send interrupts to all agents concurrently
            if agents:
                await asyncio.gather(*[send_interrupt_to_agent(agent) for agent in agents], 
                                   return_exceptions=True)
            
            logger.info("agent_interrupt_broadcast_complete",
                       component="orchestrator",
                       thread_id=thread_id,
                       agents_notified=len(agents))
                       
        except Exception as e:
            logger.error("agent_interrupt_broadcast_error",
                        component="orchestrator",
                        thread_id=thread_id,
                        error=str(e))
    
    async def resume_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Resume an interrupted task with user input."""
        try:
            thread_id = params.get("thread_id")
            user_input = params.get("user_input", "")
            
            if not thread_id:
                return {
                    "success": False,
                    "message": "thread_id is required"
                }
            
            logger.info("resume_task_request",
                       component="orchestrator",
                       thread_id=thread_id,
                       user_input_length=len(user_input))
            
            # Store the resume data for the next streaming request
            # This allows the client to pick up where it left off
            if not hasattr(self, 'resume_data'):
                self.resume_data = {}
            
            import time
            self.resume_data[thread_id] = {
                "user_input": user_input,
                "timestamp": time.time()
            }
            
            logger.info("resume_task_stored",
                       component="orchestrator",
                       thread_id=thread_id,
                       status="Resume data stored for next streaming request")
            
            return {
                "success": True,
                "message": "Resume request stored. Client should reinitiate streaming to continue.",
                "resume_stored": True
            }
            
        except Exception as e:
            logger.error("resume_task_error",
                        component="orchestrator",
                        error=str(e))
            return {
                "success": False,
                "message": f"Error resuming task: {str(e)}"
            }
    
    async def handle_websocket(self, request):
        """Handle WebSocket connections for control messages."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        client_id = str(uuid.uuid4())[:8]
        thread_id = None
        
        logger.info("websocket_client_connected",
                   component="orchestrator",
                   client_id=client_id)
        
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        message_type = data.get("type")
                        payload = data.get("payload", {})
                        
                        logger.info("websocket_message_received",
                                   component="orchestrator",
                                   client_id=client_id,
                                   message_type=message_type)
                        
                        if message_type == "register":
                            # Register client for a specific thread
                            thread_id = payload.get("thread_id")
                            if thread_id:
                                self.websocket_clients[thread_id] = ws
                                self.client_threads[client_id] = thread_id
                                
                                await ws.send_str(json.dumps({
                                    "type": "registration_ack",
                                    "payload": {
                                        "client_id": client_id,
                                        "thread_id": thread_id,
                                        "status": "registered"
                                    }
                                }))
                                
                                logger.info("websocket_client_registered",
                                           component="orchestrator",
                                           client_id=client_id,
                                           thread_id=thread_id)
                        
                        elif message_type == "interrupt":
                            # Handle interrupt request
                            thread_id = payload.get("thread_id")
                            reason = payload.get("reason", "user_interrupt")
                            
                            if thread_id:
                                # Use existing interrupt logic
                                result = await self.interrupt_task({
                                    "thread_id": thread_id,
                                    "reason": reason
                                })
                                
                                await ws.send_str(json.dumps({
                                    "type": "interrupt_ack",
                                    "payload": {
                                        "thread_id": thread_id,
                                        "success": result["success"],
                                        "message": result["message"]
                                    }
                                }))
                                
                                logger.info("websocket_interrupt_processed",
                                           component="orchestrator",
                                           client_id=client_id,
                                           thread_id=thread_id,
                                           success=result["success"])
                        
                        elif message_type == "resume":
                            # Handle resume request
                            thread_id = payload.get("thread_id")
                            user_input = payload.get("user_input", "")
                            
                            if thread_id:
                                # Use existing resume logic
                                result = await self.resume_task({
                                    "thread_id": thread_id,
                                    "user_input": user_input
                                })
                                
                                await ws.send_str(json.dumps({
                                    "type": "resume_ack", 
                                    "payload": {
                                        "thread_id": thread_id,
                                        "success": result["success"],
                                        "message": result["message"]
                                    }
                                }))
                                
                                logger.info("websocket_resume_processed",
                                           component="orchestrator",
                                           client_id=client_id,
                                           thread_id=thread_id,
                                           success=result["success"])
                        
                        elif message_type == "ping":
                            # Handle keepalive ping
                            await ws.send_str(json.dumps({
                                "type": "pong",
                                "payload": {"timestamp": datetime.now().isoformat()}
                            }))
                        
                        else:
                            logger.warning("websocket_unknown_message_type",
                                         component="orchestrator",
                                         client_id=client_id,
                                         message_type=message_type)
                    
                    except json.JSONDecodeError as e:
                        logger.error("websocket_json_decode_error",
                                   component="orchestrator",
                                   client_id=client_id,
                                   error=str(e))
                        
                        await ws.send_str(json.dumps({
                            "type": "error",
                            "payload": {"message": "Invalid JSON format"}
                        }))
                    
                    except Exception as e:
                        logger.error("websocket_message_handling_error",
                                   component="orchestrator",
                                   client_id=client_id,
                                   error=str(e))
                        
                        await ws.send_str(json.dumps({
                            "type": "error",
                            "payload": {"message": f"Error processing message: {str(e)}"}
                        }))
                
                elif msg.type == WSMsgType.ERROR:
                    logger.error("websocket_error_received",
                               component="orchestrator",
                               client_id=client_id,
                               error=str(ws.exception()))
                
        except Exception as e:
            logger.error("websocket_connection_error",
                        component="orchestrator",
                        client_id=client_id,
                        error=str(e))
        
        finally:
            # Clean up client registration
            if client_id in self.client_threads:
                thread_id = self.client_threads[client_id]
                if thread_id in self.websocket_clients:
                    del self.websocket_clients[thread_id]
                del self.client_threads[client_id]
            
            logger.info("websocket_client_disconnected",
                       component="orchestrator",
                       client_id=client_id,
                       thread_id=thread_id)
        
        return ws
    
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
            
            # Check if we're resuming from an interrupt (either from context or stored resume data)
            resume_data = context.get("resume_data")
            plan_modification = None
            
            if not resume_data and hasattr(self, 'resume_data') and thread_id in self.resume_data:
                # Use stored resume data from WebSocket
                stored_resume = self.resume_data[thread_id]
                resume_data = stored_resume["user_input"]
                # Clear the stored resume data after using it
                del self.resume_data[thread_id]
                logger.info("using_stored_resume_data", 
                           component="orchestrator",
                           thread_id=thread_id,
                           resume_data_preview=resume_data[:100])
                
                # Use LLM to parse user modification intent
                if self.plan_modification_extractor:
                    logger.info("plan_modification_extractor_available", 
                               component="orchestrator",
                               thread_id=thread_id,
                               resume_data=resume_data)
                    try:
                        plan_modification = await self._parse_plan_modification(resume_data, thread_id)
                        if plan_modification:
                            logger.info("plan_modification_parsed", 
                                       component="orchestrator",
                                       thread_id=thread_id,
                                       modification_type=plan_modification.modification_type,
                                       target_step=plan_modification.target_step_number,
                                       confidence=plan_modification.confidence)
                        else:
                            logger.warning("plan_modification_returned_none",
                                         component="orchestrator",
                                         thread_id=thread_id,
                                         resume_data=resume_data)
                    except Exception as e:
                        logger.error("plan_modification_parse_error",
                                   component="orchestrator", 
                                   thread_id=thread_id,
                                   error=str(e),
                                   resume_data=resume_data)
                        # Fallback to original instruction
                        resume_data = None
                        plan_modification = None
                else:
                    logger.error("plan_modification_extractor_not_available",
                               component="orchestrator",
                               thread_id=thread_id)
            
            if plan_modification:
                # Handle intelligent plan modification
                from langgraph.types import Command
                
                logger.info("applying_plan_modification",
                           component="orchestrator",
                           thread_id=thread_id,
                           modification_type=plan_modification.modification_type,
                           target_step=plan_modification.target_step_number)
                
                if plan_modification.modification_type == "cancel_and_new":
                    # Start completely new plan
                    instruction = plan_modification.new_plan_description or "continue"
                    logger.info("plan_cancelled_starting_new",
                               component="orchestrator",
                               thread_id=thread_id,
                               new_instruction=instruction)
                    # Start fresh - fall through to normal execution
                    
                elif plan_modification.modification_type == "replace_plan":
                    # Replace current plan with new approach
                    instruction = plan_modification.new_plan_description or "continue" 
                    logger.info("plan_replaced",
                               component="orchestrator", 
                               thread_id=thread_id,
                               new_instruction=instruction)
                    # Start fresh - fall through to normal execution
                    
                elif plan_modification.modification_type == "conversation_only":
                    # Just respond, don't modify plan
                    logger.info("conversation_only_no_plan_change",
                               component="orchestrator",
                               thread_id=thread_id)
                    # Continue with original instruction - fall through
                    
                else:
                    # Step-based modifications - use Command with proper state updates
                    command_update = self._create_plan_state_update(plan_modification)
                    logger.info("plan_state_update_created",
                               component="orchestrator",
                               thread_id=thread_id,
                               update_keys=list(command_update.keys()) if command_update else [],
                               current_task_index=command_update.get("current_task_index"),
                               skipped_task_indices=command_update.get("skipped_task_indices"))
                    
                    # Get current state to include plan data
                    try:
                        current_state = self.graph.graph.get_state(config)
                        current_plan = current_state.values.get("plan") if current_state and current_state.values else None
                    except Exception as e:
                        logger.warning("failed_to_get_current_state_for_plan_modified",
                                     component="orchestrator",
                                     thread_id=thread_id,
                                     error=str(e))
                        current_plan = None
                    
                    # Send plan modification event to client with plan data
                    event_data = {
                        "task_id": task_id,
                        "modification_type": plan_modification.modification_type,
                        "current_task_index": command_update.get("current_task_index"),
                        "skipped_task_indices": command_update.get("skipped_task_indices", []),
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Include plan data if available
                    if current_plan:
                        event_data["plan"] = current_plan
                    
                    yield self._format_sse_event("plan_modified", event_data)
                    
                    # Stream the execution with state updates
                    async for event in self.graph.graph.astream(
                        Command(update=command_update, resume=resume_data),
                        config,
                        stream_mode="updates"
                    ):
                        yield self._process_graph_event(event, task_id)
                    return
                        
            elif resume_data:
                # Fallback: old resume behavior if LLM parsing failed
                from langgraph.types import Command
                
                # Stream the execution
                async for event in self.graph.graph.astream(
                    Command(resume=resume_data),
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
                    # Replanning occurred - include plan data for UI updates
                    event_data = {
                        "task_id": task_id,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Include plan data if available for UI updates
                    if isinstance(node_output, dict) and "plan" in node_output:
                        event_data["plan"] = node_output["plan"]
                        # Include execution state for proper display
                        if "current_task_index" in node_output:
                            event_data["current_task_index"] = node_output["current_task_index"]
                        if "skipped_task_indices" in node_output:
                            event_data["skipped_task_indices"] = node_output["skipped_task_indices"]
                    
                    return self._format_sse_event("plan_updated", event_data)
                    
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
    
    async def _parse_plan_modification(self, user_input: str, thread_id: str):
        """Parse user input into structured plan modification using LLM."""
        try:
            # Get current plan context if available
            current_state = self.graph.graph.get_state({"configurable": {"thread_id": thread_id}})
            current_plan_info = ""
            if current_state and current_state.values:
                plan = current_state.values.get("plan", {})
                if plan and plan.get("tasks"):
                    current_plan_info = f"Current plan has {len(plan['tasks'])} steps: " + \
                                      ", ".join([f"{i+1}. {task.get('content', 'Unknown')}" 
                                               for i, task in enumerate(plan["tasks"])])
            
            # Create extraction prompt
            extraction_prompt = f"""
            The user is modifying an active plan execution. Here's the context:
            
            {current_plan_info}
            
            User input: "{user_input}"
            
            Parse the user's intent and determine what plan modification they want.
            """
            
            # Extract structured plan modification
            result = self.plan_modification_extractor.invoke({
                "messages": [("human", extraction_prompt)],
                "user_input": user_input
            })
            
            # Log to extraction.log for detailed TrustCall debugging
            from src.utils.logging.multi_file_logger import StructuredLogger
            extraction_logger = StructuredLogger()
            
            extraction_logger.info("trustcall_plan_modification_invoked",
                                 component="extraction",
                                 thread_id=thread_id,
                                 user_input=user_input,
                                 extraction_prompt_preview=extraction_prompt[:300],
                                 result_type=type(result).__name__)
            
            # Extract PlanModification tool call result from LangChain message structure (same pattern as instruction extractor)
            plan_modification_result = None
            
            if isinstance(result, dict) and 'messages' in result:
                messages = result['messages']
                extraction_logger.info("trustcall_result_structure",
                                     component="extraction",
                                     thread_id=thread_id,
                                     has_messages=True,
                                     message_count=len(messages))
                
                if messages and len(messages) > 0:
                    message = messages[0]
                    extraction_logger.info("trustcall_first_message",
                                         component="extraction",
                                         thread_id=thread_id,
                                         message_type=type(message).__name__,
                                         has_additional_kwargs=hasattr(message, 'additional_kwargs'),
                                         additional_kwargs_keys=list(message.additional_kwargs.keys()) if hasattr(message, 'additional_kwargs') else [])
                    
                    if hasattr(message, 'additional_kwargs') and 'tool_calls' in message.additional_kwargs:
                        tool_calls = message.additional_kwargs['tool_calls']
                        extraction_logger.info("trustcall_tool_calls_found",
                                             component="extraction",
                                             thread_id=thread_id,
                                             tool_call_count=len(tool_calls),
                                             tool_names=[tc.get('function', {}).get('name', 'unknown') for tc in tool_calls])
                        
                        # Find the PlanModification tool call
                        for i, tool_call in enumerate(tool_calls):
                            tool_name = tool_call.get('function', {}).get('name')
                            extraction_logger.info("trustcall_examining_tool_call",
                                                 component="extraction",
                                                 thread_id=thread_id,
                                                 tool_call_index=i,
                                                 tool_name=tool_name,
                                                 has_arguments=bool(tool_call.get('function', {}).get('arguments')))
                            
                            if tool_name == 'PlanModification':
                                import json
                                try:
                                    args_str = tool_call['function']['arguments']
                                    plan_modification_result = json.loads(args_str)
                                    extraction_logger.info("trustcall_plan_modification_extracted",
                                                         component="extraction",
                                                         thread_id=thread_id,
                                                         extracted_data=plan_modification_result)
                                    break
                                except json.JSONDecodeError as e:
                                    extraction_logger.error("trustcall_json_parse_error",
                                                           component="extraction",
                                                           thread_id=thread_id,
                                                           error=str(e),
                                                           raw_arguments=args_str)
                                    continue
                    else:
                        extraction_logger.warning("trustcall_no_tool_calls",
                                                component="extraction",
                                                thread_id=thread_id,
                                                message_content=message.content if hasattr(message, 'content') else 'no_content')
            else:
                extraction_logger.warning("trustcall_unexpected_result_format",
                                        component="extraction",
                                        thread_id=thread_id,
                                        result_structure=str(result)[:500])
            
            if plan_modification_result:
                from .llm_handler import PlanModification
                modification_obj = PlanModification(**plan_modification_result)
                extraction_logger.info("trustcall_plan_modification_created",
                                     component="extraction",
                                     thread_id=thread_id,
                                     modification_type=modification_obj.modification_type,
                                     target_step=modification_obj.target_step_number,
                                     confidence=modification_obj.confidence)
                return modification_obj
            
            extraction_logger.error("trustcall_plan_modification_extraction_failed",
                                   component="extraction",
                                   thread_id=thread_id,
                                   result_type=type(result).__name__,
                                   result_preview=str(result)[:500])
            return None
            
        except Exception as e:
            logger.error("plan_modification_extraction_error",
                        component="orchestrator",
                        thread_id=thread_id,
                        error=str(e))
            raise
    
    def _create_plan_state_update(self, plan_modification) -> Dict[str, Any]:
        """Create state update dictionary based on plan modification."""
        update = {}
        
        if plan_modification.modification_type == "skip_to_step" and plan_modification.target_step_number:
            # Skip to specific step
            update["current_task_index"] = plan_modification.target_step_number - 1
            # Mark skipped steps as completed
            skipped_steps = list(range(0, plan_modification.target_step_number - 1))
            update["skipped_task_indices"] = skipped_steps
            
        elif plan_modification.modification_type == "skip_steps" and plan_modification.steps_to_skip:
            # Skip specific steps
            update["skipped_task_indices"] = [i - 1 for i in plan_modification.steps_to_skip]  # Convert to 0-indexed
            
        # Add modification metadata
        update["plan_modification_applied"] = {
            "type": plan_modification.modification_type,
            "reasoning": plan_modification.reasoning,
            "confidence": plan_modification.confidence,
            "applied_at": datetime.now().isoformat()
        }
        
        return update