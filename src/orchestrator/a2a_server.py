"""Simple A2A server for the orchestrator."""

import asyncio
import argparse
from typing import Dict, Any

from src.a2a import A2AServer, AgentCard
from src.utils.logging import get_logger
from .a2a_handler import OrchestratorA2AHandler
from .plan_and_execute import create_plan_execute_graph
from .observers import get_observer_registry, SSEObserver
import json
from aiohttp import web
from aiohttp.web_response import StreamResponse

logger = get_logger("orchestrator")

# Global SSE observer instance
sse_observer: SSEObserver = None

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
               component="orchestrator", 
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
                        component="orchestrator", 
                        error=str(e))
    
    # Set up client callback for new messages
    async def send_message(message: Dict):
        logger.info("SSE_CALLBACK_ENTRY",
                   component="orchestrator",
                   event_type=message.get('event'),
                   message_keys=list(message.keys()))
        try:
            logger.info("sse_callback_triggered",
                       component="orchestrator",
                       event_type=message.get('event'),
                       response_closed=response._closed if hasattr(response, '_closed') else False)
            
            # Use the formatted payload that matches main branch format
            sse_payload = message.get('sse_payload', {"event": message['event'], "data": message['data']})
            sse_data = f"data: {json.dumps(sse_payload)}\n\n"
            
            logger.info("sse_writing_data",
                       component="orchestrator",
                       event_type=message.get('event'),
                       data_length=len(sse_data))
            
            await response.write(sse_data.encode())
            await response.drain()  # Ensure data is flushed to client
            
            logger.info("sse_message_sent",
                       component="orchestrator",
                       event_type=message.get('event'),
                       client_count=len(sse_observer._observers) if sse_observer else 0)
        except Exception as e:
            logger.error("sse_message_send_failed",
                        component="orchestrator",
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
                   component="orchestrator",
                   client_ip=request.remote,
                   reason=str(e))
    finally:
        # Clean up client callback
        if sse_observer:
            sse_observer.remove_client(send_message)
    
    return response


async def create_orchestrator_a2a_server(host: str = "0.0.0.0", port: int = 8000):
    """Create and configure the orchestrator A2A server."""
    
    logger.info("orchestrator_a2a_starting",
                component="orchestrator",
                host=host,
                port=port)
    
    # Initialize SSE observer BEFORE creating the graph
    global sse_observer
    sse_observer = SSEObserver()
    registry = get_observer_registry()
    registry.add_observer(sse_observer)
    
    logger.info("sse_observer_registered",
               component="orchestrator")
    
    # Create the plan-execute graph (with observer already registered)
    logger.info("creating_plan_execute_graph",
                component="orchestrator")
    
    try:
        graph = await create_plan_execute_graph()
        logger.info("plan_execute_graph_created",
                    component="orchestrator",
                    success=True)
    except Exception as e:
        logger.error("plan_execute_graph_creation_failed",
                     component="orchestrator",
                     error=str(e))
        raise
    
    # Create A2A handler
    handler = OrchestratorA2AHandler()
    handler.set_graph(graph)
    
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
    
    # Add SSE route directly to the server app
    server.app.router.add_get("/a2a/stream", handle_sse_stream)
    
    logger.info("orchestrator_a2a_configured",
                component="orchestrator",
                endpoints=list(agent_card.endpoints.keys()))
    
    return server


async def main(host: str = "0.0.0.0", port: int = 8000):
    """Main function to run the orchestrator A2A server."""
    
    try:
        # Create server
        server = await create_orchestrator_a2a_server(host, port)
        
        # Start the server
        runner = await server.start()
        
        logger.info("orchestrator_a2a_started",
                    component="orchestrator",
                    host=host,
                    port=port,
                    endpoint=f"http://{host}:{port}")
        
        # Keep the server running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("orchestrator_a2a_shutdown",
                    component="orchestrator")
        await server.stop(runner)
        
        # Clean up any connections
        from src.a2a.protocol import get_connection_pool
        try:
            pool = get_connection_pool()
            await pool.close_all()
        except Exception as e:
            logger.warning("connection_pool_cleanup_error",
                          component="orchestrator",
                          error=str(e))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Orchestrator A2A Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", 
                       help="Host to bind server (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000,
                       help="Port to bind server (default: 8000)")
    
    args = parser.parse_args()
    
    asyncio.run(main(args.host, args.port))