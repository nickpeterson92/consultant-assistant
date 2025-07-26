"""Simple A2A server for the orchestrator."""

import asyncio
import argparse
from typing import Dict

from src.a2a import A2AServer, AgentCard
from src.utils.logging import get_smart_logger, log_execution
from src.orchestrator.a2a.handler import OrchestratorA2AHandler
from src.orchestrator.observers import get_observer_registry, SSEObserver
import json
from aiohttp import web
from aiohttp.web_response import StreamResponse

logger = get_smart_logger("orchestrator")

# Global SSE observer instance
sse_observer: SSEObserver = None

# Global handler instance for interrupt access
orchestrator_handler: OrchestratorA2AHandler = None


@log_execution(component="orchestrator", operation="periodic_cleanup")
async def periodic_cleanup():
    """Periodically clean up idle A2A connections."""
    from src.a2a.protocol import get_connection_pool
    
    while True:
        try:
            # Wait 60 seconds between cleanups
            await asyncio.sleep(60)
            
            # Clean up idle sessions
            pool = get_connection_pool()
            await pool.cleanup_idle_sessions()
            
            logger.info("periodic_cleanup_completed",
                       component="orchestrator",
                       cleanup_type="a2a_connection_pool")
                       
        except asyncio.CancelledError:
            # Task was cancelled, exit gracefully
            raise
        except Exception as e:
            logger.error("periodic_cleanup_error",
                        component="orchestrator",
                        error=str(e),
                        error_type=type(e).__name__)
            # Continue running even if cleanup fails
            await asyncio.sleep(60)

async def handle_sse_stream(request: web.Request) -> StreamResponse:
    """SSE endpoint for streaming plan updates to clients."""
    global sse_observer
    
    # Set up SSE response
    response = StreamResponse()
    response.headers['Content-Type'] = 'text/event-stream'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['Access-Control-Allow-Origin'] = '*'
    
    await response.prepare(request)
    
    logger.info("sse_client_connected",
               client_ip=request.remote)
    
    # Send any queued messages first
    if sse_observer and sse_observer.sse_queue:
        try:
            for message in sse_observer.sse_queue:
                # Use the formatted payload that matches main branch format
                sse_payload = message.get('sse_payload', {"event": message['event'], "data": message['data']})
                sse_data = f"data: {json.dumps(sse_payload)}\n\n"
                await response.write(sse_data.encode())
                await response.drain()  # Ensure data is flushed to client
        except Exception as e:
            logger.error("sse_queue_replay_failed",
                        error=str(e))
    
    # Set up client callback for new messages
    async def send_message(message: Dict):
        logger.info("SSE_CALLBACK_ENTRY",
                   event_type=message.get('event'),
                   message_keys=list(message.keys()))
        try:
            logger.info("sse_callback_triggered",
                       event_type=message.get('event'),
                       response_closed=response._closed if hasattr(response, '_closed') else False)
            
            # Use the formatted payload that matches main branch format
            sse_payload = message.get('sse_payload', {"event": message['event'], "data": message['data']})
            sse_data = f"data: {json.dumps(sse_payload)}\n\n"
            
            logger.info("sse_writing_data",
                       event_type=message.get('event'),
                       data_length=len(sse_data))
            
            await response.write(sse_data.encode())
            await response.drain()  # Ensure data is flushed to client
            
            logger.info("sse_message_sent",
                       event_type=message.get('event'),
                       client_count=len(sse_observer._observers) if sse_observer else 0)
        except Exception as e:
            logger.error("sse_message_send_failed",
                        error=str(e),
                        error_type=type(e).__name__)
            # Remove this callback since it's broken
            if sse_observer:
                sse_observer.remove_client(send_message)
    
    # Add client to SSE observer
    if sse_observer:
        sse_observer.add_client(send_message)
    
    try:
        # Keep connection alive until client disconnects
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        logger.info("sse_client_disconnected",
                   client_ip=request.remote,
                   reason=str(e))
    finally:
        # Clean up client callback
        if sse_observer:
            sse_observer.remove_client(send_message)
    
    return response


async def handle_websocket(request: web.Request) -> web.WebSocketResponse:
    """WebSocket endpoint for interrupt handling."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    logger.info("websocket_client_connected",
               client_ip=request.remote)
    
    # Track background tasks for this connection
    background_tasks = set()
    
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    msg_type = data.get("type")
                    payload = data.get("payload", {})
                    msg_id = data.get("id")
                    
                    logger.info("websocket_message_received",
                               msg_type=msg_type,
                               msg_id=msg_id,
                               thread_id=payload.get("thread_id"))
                    
                    if msg_type == "interrupt":
                        # Handle interrupt request
                        thread_id = payload.get("thread_id")
                        reason = payload.get("reason", "user_interrupt")
                        
                        logger.info("interrupt_request_received",
                                   thread_id=thread_id,
                                   reason=reason)
                        
                        # Call the handler's interrupt method
                        result = await orchestrator_handler.interrupt_task(thread_id, reason)
                        
                        # Send acknowledgment
                        await ws.send_json({
                            "type": "interrupt_ack",
                            "payload": {
                                "success": result.get("success", False),
                                "thread_id": thread_id,
                                "message": result.get("message", "")
                            },
                            "id": msg_id
                        })
                        
                    elif msg_type == "resume":
                        # Handle resume request
                        thread_id = payload.get("thread_id")
                        user_input = payload.get("user_input")
                        
                        logger.info("resume_request_received",
                                   thread_id=thread_id,
                                   user_input=user_input[:100] if user_input else "")
                        
                        # Resume the interrupted graph execution
                        if orchestrator_handler and thread_id:
                            try:
                                # Check the interrupt type
                                config = {"configurable": {"thread_id": thread_id}}
                                current_state = orchestrator_handler.graph.get_state(config)
                                
                                # Use interrupt observer to get persistent interrupt context
                                from src.orchestrator.observers.interrupt_observer import get_interrupt_observer
                                interrupt_observer = get_interrupt_observer()
                                interrupt_context = interrupt_observer.get_interrupt_context(thread_id)
                                
                                # Determine interrupt type from observer or state
                                if interrupt_context:
                                    interrupt_type = interrupt_context.get("interrupt_type", "human_input")
                                    logger.info("resume_using_observer_context",
                                               thread_id=thread_id,
                                               interrupt_type=interrupt_type,
                                               interrupt_time=interrupt_context.get("interrupt_time"))
                                else:
                                    # Fallback to state check
                                    interrupt_type = "user_escape" if current_state.values.get("user_interrupted", False) else "human_input"
                                    logger.info("resume_using_state_check",
                                               thread_id=thread_id,
                                               interrupt_type=interrupt_type,
                                               user_interrupted=current_state.values.get("user_interrupted"))
                                
                                # Import the interrupt handler
                                from src.orchestrator.workflow.interrupt_handler import InterruptHandler
                                
                                # Get state updates based on interrupt type
                                state_updates = InterruptHandler.handle_resume(
                                    current_state.values,
                                    user_input,
                                    interrupt_type
                                )
                                
                                # Now resume the graph with the user's input
                                # This is the proper way to resume after GraphInterrupt
                                from langgraph.types import Command
                                
                                logger.info("resuming_graph_with_command",
                                           thread_id=thread_id,
                                           user_input=user_input[:100] if user_input else "",
                                           interrupt_type=interrupt_type,
                                           has_state_updates=bool(state_updates))
                                
                                # Create Command with both resume value and state updates
                                if state_updates:
                                    # For user_escape, include state updates in the Command
                                    resume_command = Command(
                                        resume=user_input,
                                        update=state_updates
                                    )
                                else:
                                    # For human_input, just resume with the input
                                    resume_command = Command(resume=user_input)
                                
                                # Resume the graph execution in the background
                                # The proper way to resume a ReAct agent is to pass the resume value
                                # LangGraph will handle creating the ToolMessage internally
                                async def resume_graph():
                                    try:
                                        result = await orchestrator_handler.graph.ainvoke(
                                            resume_command,
                                            config
                                        )
                                        logger.info("graph_resume_completed",
                                                   thread_id=thread_id)
                                    except Exception as e:
                                        logger.error("graph_resume_error",
                                                    thread_id=thread_id,
                                                    error=str(e),
                                                    error_type=type(e).__name__)
                                
                                # Create background task that we can track
                                task = asyncio.create_task(resume_graph())
                                background_tasks.add(task)
                                task.add_done_callback(background_tasks.discard)
                                
                                logger.info("graph_resume_triggered",
                                           thread_id=thread_id)
                                
                                # Record resume in observer
                                interrupt_observer.record_resume(thread_id, user_input, interrupt_type)
                                
                                # Clear interrupt state after successful resume
                                interrupt_observer.clear_interrupt(thread_id)
                                
                                # Send acknowledgment
                                await ws.send_json({
                                    "type": "resume_ack",
                                    "payload": {
                                        "success": True,
                                        "thread_id": thread_id,
                                        "message": "Execution resumed with modifications"
                                    },
                                    "id": msg_id
                                })
                                
                            except Exception as e:
                                logger.error("resume_error", error=str(e))
                                await ws.send_json({
                                    "type": "resume_ack",
                                    "payload": {
                                        "success": False,
                                        "thread_id": thread_id,
                                        "message": f"Failed to resume: {str(e)}"
                                    },
                                    "id": msg_id
                                })
                        else:
                            await ws.send_json({
                                "type": "resume_ack",
                                "payload": {
                                    "success": False,
                                    "thread_id": thread_id,
                                    "message": "No handler available or missing thread_id"
                                },
                                "id": msg_id
                            })
                    
                    else:
                        logger.warning("unknown_websocket_message_type",
                                     msg_type=msg_type)
                        
                except json.JSONDecodeError as e:
                    logger.error("websocket_json_decode_error",
                               error=str(e))
                except Exception as e:
                    logger.error("websocket_message_error",
                               error=str(e))
                    
            elif msg.type == web.WSMsgType.ERROR:
                logger.error("websocket_error",
                           error=ws.exception())
            
    except Exception as e:
        logger.error("websocket_handler_error",
                    error=str(e))
    finally:
        # Clean up background tasks
        if background_tasks:
            for task in background_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*background_tasks, return_exceptions=True)
        
        logger.info("websocket_client_disconnected",
                   client_ip=request.remote)
    
    return ws


@log_execution(component="orchestrator", operation="create_a2a_server")
async def create_orchestrator_a2a_server(host: str = "0.0.0.0", port: int = 8000):
    """Create and configure the orchestrator A2A server."""
    
    logger.info("orchestrator_a2a_starting",
                host=host,
                port=port)
    
    # Initialize SSE observer BEFORE creating the graph
    global sse_observer
    sse_observer = SSEObserver()
    
    # Capture the main event loop for SSE emissions from threads
    sse_observer.set_main_loop()
    
    registry = get_observer_registry()
    registry.add_observer(sse_observer)
    
    logger.info("sse_observer_registered")
    
    # Create A2A handler and store globally
    logger.info("creating_orchestrator_handler")
    global orchestrator_handler
    handler = OrchestratorA2AHandler()
    orchestrator_handler = handler
    
    # Create agent card
    agent_card = AgentCard(
        name="orchestrator",
        version="1.0.0",
        description="Multi-agent orchestrator with plan-and-execute workflow",
        capabilities=[
            "orchestration",
            "task_planning", 
            "task_execution",
            "multi_agent_coordination"
        ],
        endpoints={
            "process_task": f"http://{host}:{port}/a2a",
            "agent_card": f"http://{host}:{port}/a2a/agent-card",
            "task_status": f"http://{host}:{port}/a2a/status",
            "stream": f"http://{host}:{port}/a2a/stream"
        },
        communication_modes=["sync"],
        metadata={
            "framework": "langgraph-plan-execute"
        }
    )
    
    # Create and configure A2A server
    server = A2AServer(agent_card, host, port)
    server.register_handler("process_task", handler.process_task)
    server.register_handler("get_agent_card", handler.get_agent_card)
    server.register_handler("get_task_status", handler.get_task_status)
    server.register_handler("forward_events", handler.forward_events)
    
    # Add SSE route directly to the server app
    server.app.router.add_get("/a2a/stream", handle_sse_stream)
    
    # Add WebSocket route for interrupt handling
    server.app.router.add_get("/ws", handle_websocket)
    
    logger.info("orchestrator_a2a_configured",
                endpoints=list(agent_card.endpoints.keys()))
    
    return server


@log_execution(component="orchestrator", operation="main_server")
async def main(host: str = "0.0.0.0", port: int = 8000):
    """Main function to run the orchestrator A2A server."""
    
    try:
        # Create server
        server = await create_orchestrator_a2a_server(host, port)
        
        # Start the server
        runner = await server.start()
        
        logger.info("orchestrator_a2a_started",
                    host=host,
                    port=port,
                    endpoint=f"http://{host}:{port}")
        
        # Create background tasks
        cleanup_task = asyncio.create_task(periodic_cleanup())
        
        # Keep the server running
        try:
            while True:
                await asyncio.sleep(1)
        finally:
            # Cancel background tasks
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
            
    except KeyboardInterrupt:
        logger.info("orchestrator_a2a_shutdown")
    finally:
        # Always clean up resources on exit
        logger.info("cleanup_starting")
        
        try:
            await server.stop(runner)
        except Exception as e:
            logger.warning("server_stop_error", error=str(e))
        
        # Clean up A2A connection pool
        from src.a2a.protocol import get_connection_pool
        try:
            pool = get_connection_pool()
            await pool.close_all()
            logger.info("connection_pool_closed")
        except Exception as e:
            logger.warning("connection_pool_cleanup_error",
                          error=str(e))
        
        # Give a moment for cleanup to complete
        await asyncio.sleep(0.1)
        
        logger.info("cleanup_complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Orchestrator A2A Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", 
                       help="Host to bind server (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000,
                       help="Port to bind server (default: 8000)")
    
    args = parser.parse_args()
    
    asyncio.run(main(args.host, args.port))