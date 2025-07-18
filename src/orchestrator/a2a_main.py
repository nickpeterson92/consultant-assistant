"""A2A mode for the multi-agent orchestrator."""

import asyncio
import logging

from src.a2a import A2AServer, AgentCard
from src.utils.logging.framework import SmartLogger
from .agent_registry import AgentRegistry
from .plan_execute_graph import create_plan_execute_graph
from .a2a_handler import CleanOrchestratorA2AHandler

# Initialize logger
logger = SmartLogger("orchestrator")


async def initialize_orchestrator_a2a():
    """Initialize orchestrator in A2A mode."""
    logger.info("orchestrator_a2a_initialization_start",
        operation="startup",
        mode="a2a"
    )
    
    # Create agent registry instance
    agent_registry = AgentRegistry()
    
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
            operation="agent_discovery",
            agents=online_agents,
            count=len(online_agents)
        )
    if offline_agents:
        logger.warning("agents_offline",
            operation="agent_discovery",
            agents=offline_agents,
            count=len(offline_agents)
        )
    
    # Get updated stats after health checks
    stats = agent_registry.get_registry_stats()
    logger.info("orchestrator_a2a_initialization_complete",
        operation="startup",
        total_agents=stats['total_agents'],
        online_agents=stats['online_agents'],
        offline_agents=stats['offline_agents']
    )
    
    return agent_registry


async def main(host: str, port: int):
    """Main function to run the orchestrator in A2A mode."""
    # Setup logging
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
            "process_task_streaming": f"http://{host}:{port}/a2a/stream",
            "agent_card": f"http://{host}:{port}/a2a/agent-card",
            "interrupt_task": f"http://{host}:{port}/a2a",
            "resume_task": f"http://{host}:{port}/a2a"
        },
        communication_modes=["sync", "streaming"],
        metadata={
            "framework": "langgraph",
            "registered_agents": stats['total_agents'],
            "online_agents": stats['online_agents'],
            "capabilities_by_agent": capabilities_by_agent
        }
    )
    
    # Build the graph with LLM support
    logger.info("graph_building",
        agent="orchestrator",
        operation="build_graph"
    )
    
    # Set up agent tools for task execution
    from .agent_caller_tools import SalesforceAgentTool, JiraAgentTool, ServiceNowAgentTool
    agent_tools = {
        "salesforce_agent": SalesforceAgentTool(agent_registry),
        "jira_agent": JiraAgentTool(agent_registry),
        "servicenow_agent": ServiceNowAgentTool(agent_registry),
    }
    
    # Create LLM instances using existing infrastructure
    from .llm_handler import create_llm_instances
    tools = list(agent_tools.values())  # Use agent tools as LLM tools
    llm_with_tools, deterministic_llm, trustcall_extractor, plan_modification_extractor, plan_extractor, invoke_llm = create_llm_instances(tools)
    
    # Create pure plan-execute graph with LLM support and structured planning
    local_graph = create_plan_execute_graph(invoke_llm=invoke_llm, plan_extractor=plan_extractor)
    local_graph.set_agent_tools(agent_tools)
    logger.info("graph_built",
        agent="orchestrator",
        operation="build_graph",
        success=True
    )
    
    # Create A2A handler
    handler = CleanOrchestratorA2AHandler(local_graph, agent_registry, plan_modification_extractor)
    
    # Create and configure A2A server
    server = A2AServer(agent_card, host, port)
    server.register_handler("process_task", handler.process_task)
    server.register_handler("process_task_streaming", handler.process_task_with_streaming)
    server.register_handler("get_agent_card", handler.get_agent_card)
    server.register_handler("get_progress", handler.get_progress)
    server.register_handler("interrupt_task", handler.interrupt_task)
    server.register_handler("resume_task", handler.resume_task)
    
    # Register WebSocket endpoint for control messages
    server.register_websocket_handler("/a2a/ws", handler.handle_websocket)
    
    # Start the server
    runner = await server.start()
    
    logger.info("orchestrator_a2a_started",
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