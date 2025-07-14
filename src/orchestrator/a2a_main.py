"""A2A mode for the multi-agent orchestrator."""

import asyncio
import logging
from typing import Dict, Any
from langchain_core.messages import HumanMessage

from src.a2a import A2AServer, AgentCard
from src.utils.logging import get_logger, init_session_tracking
from src.utils.config import get_conversation_config, get_llm_config
from .graph_builder import get_orchestrator_graph, get_agent_registry
from .a2a_handler import OrchestratorA2AHandler

# Initialize logger
logger = get_logger("orchestrator")


async def initialize_orchestrator_a2a():
    """Initialize orchestrator in A2A mode."""
    logger.info("orchestrator_a2a_initialization_start",
        component="system",
        operation="startup",
        mode="a2a"
    )
    
    agent_registry = get_agent_registry()
    
    # Attempt auto-discovery if no agents registered
    if not agent_registry.list_agents():
        logger.info("No agents registered, attempting auto-discovery...")
        discovery_endpoints = [
            "http://localhost:8001",  # Salesforce agent
            "http://localhost:8002",  # Jira agent
            "http://localhost:8003",  # ServiceNow agent
            # Note: Workflow agent (port 8004) removed - functionality moved to plan-and-execute
        ]
        
        discovered = await agent_registry.discover_agents(discovery_endpoints)
        if discovered > 0:
            logger.info("agents_discovered",
                component="system",
                operation="agent_discovery",
                count=discovered
            )
        else:
            logger.warning("No agents discovered - specialized agents may need to be started manually")
    
    logger.info("Checking agent health...")
    health_results = await agent_registry.health_check_all_agents()
    
    online_agents = [name for name, status in health_results.items() if status]
    offline_agents = [name for name, status in health_results.items() if not status]
    
    if online_agents:
        logger.info("agents_online",
            component="system",
            operation="agent_discovery",
            agents=online_agents,
            count=len(online_agents)
        )
    if offline_agents:
        logger.warning("agents_offline",
            component="system",
            operation="agent_discovery",
            agents=offline_agents,
            count=len(offline_agents)
        )
    
    # Get updated stats after health checks
    stats = agent_registry.get_registry_stats()
    logger.info("orchestrator_a2a_initialization_complete",
        component="system",
        operation="startup",
        total_agents=stats['total_agents'],
        online_agents=stats['online_agents'],
        offline_agents=stats['offline_agents']
    )
    
    return agent_registry


async def main(host: str, port: int):
    """Main function to run the orchestrator in A2A mode."""
    # Setup logging
    init_session_tracking()
    
    log_level = logging.WARNING
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Suppress verbose logging
    for logger_name in [
        'httpx', 'urllib3', 'requests', 'aiohttp', 'simple_salesforce',
        'openai._base_client', 'httpcore', 'httpcore.connection', 'httpcore.http11',
        'src.a2a.circuit_breaker', 'src.utils.config', 'src.orchestrator.agent_registry',
        'src.a2a.protocol'
    ]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    logger.info("orchestrator_a2a_starting",
        component="system",
        operation="startup",
        host=host,
        port=port
    )
    
    # Initialize orchestrator and get the registry
    agent_registry = await initialize_orchestrator_a2a()
    
    # Get current stats after initialization
    stats = agent_registry.get_registry_stats()
    
    # Get capabilities from all registered agents
    all_capabilities = []
    capabilities_by_agent = {}
    
    # Collect capabilities from online agents
    for agent in agent_registry.list_agents():
        if agent.status == "online" and agent.agent_card:
            agent_caps = agent.agent_card.capabilities
            capabilities_by_agent[agent.name] = agent_caps
            all_capabilities.extend(agent_caps)
    
    # Add orchestrator-specific capabilities
    orchestrator_capabilities = [
        "orchestration",
        "task_routing",
        "multi_agent_coordination",
        "context_management",
        "conversation_memory",
        "web_search"
    ]
    all_capabilities.extend(orchestrator_capabilities)
    capabilities_by_agent["orchestrator"] = orchestrator_capabilities
    
    agent_card = AgentCard(
        name="orchestrator",
        version="1.0.0",
        description="Multi-agent orchestrator that coordinates between specialized agents for complex tasks",
        capabilities=list(set(all_capabilities)),  # Deduplicate
        endpoints={
            "process_task": f"http://{host}:{port}/a2a",
            "agent_card": f"http://{host}:{port}/a2a/agent-card"
        },
        communication_modes=["sync", "streaming"],
        metadata={
            "framework": "langgraph",
            "registered_agents": stats['total_agents'],
            "online_agents": stats['online_agents'],
            "capabilities_by_agent": capabilities_by_agent
        }
    )
    
    # Build the graph
    logger.info("graph_building",
        component="system",
        agent="orchestrator",
        operation="build_graph"
    )
    local_graph = get_orchestrator_graph()
    logger.info("graph_built",
        component="system",
        agent="orchestrator",
        operation="build_graph",
        success=True
    )
    
    # Create A2A handler
    handler = OrchestratorA2AHandler(local_graph, agent_registry)
    
    # Create and configure A2A server
    server = A2AServer(agent_card, host, port)
    server.register_handler("process_task", handler.process_task)
    server.register_handler("get_agent_card", handler.get_agent_card)
    server.register_handler("get_progress", handler.get_progress)
    
    # Start the server
    runner = await server.start()
    
    logger.info("orchestrator_a2a_started",
        component="system",
        operation="startup",
        agent="orchestrator",
        host=host,
        port=port,
        endpoint=f"http://{host}:{port}",
        registered_agents=stats['total_agents'],
        online_agents=stats['online_agents']
    )
    
    try:
        # Keep the server running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("orchestrator_a2a_shutdown",
            component="system",
            agent="orchestrator",
            operation="shutdown"
        )
        await server.stop(runner)
        
        # Clean up the global connection pool
        from src.a2a.protocol import get_connection_pool
        pool = get_connection_pool()
        await pool.close_all()


if __name__ == "__main__":
    asyncio.run(main("0.0.0.0", 8000))