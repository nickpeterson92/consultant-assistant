"""Simple A2A server for the orchestrator."""

import asyncio
import argparse
from typing import Dict, Any

from src.a2a import A2AServer, AgentCard
from src.utils.logging import get_logger
from .a2a_handler import OrchestratorA2AHandler
from .plan_and_execute import create_plan_execute_graph

logger = get_logger("orchestrator")


async def create_orchestrator_a2a_server(host: str = "0.0.0.0", port: int = 8000):
    """Create and configure the orchestrator A2A server."""
    
    logger.info("orchestrator_a2a_starting",
                component="orchestrator",
                host=host,
                port=port)
    
    # Create the plan-execute graph
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
            "task_status": f"http://{host}:{port}/a2a/status"
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