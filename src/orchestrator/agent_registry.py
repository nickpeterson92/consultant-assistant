"""Agent registry for service discovery and health monitoring.

Handles dynamic agent registration, health checks, and capability-based routing.
Uses circuit breakers and exponential backoff for resilience.
"""

import json
import os
import asyncio
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from ..a2a import AgentCard, A2AClient, A2AException
from ..utils.logging import get_logger

# Initialize logger
logger = get_logger()

@dataclass
class RegisteredAgent:
    """Service record for a registered agent in the distributed system.
    
    Maintains the service endpoint, capabilities, and health status for
    each agent following the service instance pattern from microservices
    architecture.
    """
    name: str
    endpoint: str
    agent_card: AgentCard
    status: str = "unknown"  # Service states: unknown, online, offline, error
    last_health_check: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "endpoint": self.endpoint,
            "agent_card": self.agent_card.to_dict(),
            "status": self.status,
            "last_health_check": self.last_health_check
        }

class AgentRegistry:
    """Enterprise service registry implementing dynamic discovery and health monitoring.
    
    This registry serves as the central nervous system for the multi-agent architecture,
    providing service discovery, health monitoring, and capability-based routing similar
    to Consul, Eureka, or Kubernetes service discovery.
    
    Key responsibilities:
    - Service registration and deregistration
    - Health monitoring with circuit breaker integration
    - Capability-based service selection
    - Persistent configuration for disaster recovery
    - Concurrent health checks for scalability
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.agents: Dict[str, RegisteredAgent] = {}
        from ..utils.config import get_system_config
        system_config = get_system_config()
        self.config_path = config_path or system_config.agent_registry_path
        self.client = None
        self._load_config()
    
    def _load_config(self):
        """Load persistent service registry from disk for disaster recovery."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    
                for agent_config in config.get("agents", []):
                    agent_card = AgentCard(**agent_config["agent_card"])
                    registered_agent = RegisteredAgent(
                        name=agent_config["name"],
                        endpoint=agent_config["endpoint"],
                        agent_card=agent_card,
                        status=agent_config.get("status", "unknown"),
                        last_health_check=agent_config.get("last_health_check")
                    )
                    self.agents[agent_config["name"]] = registered_agent
                    
                logger.info(f"Loaded {len(self.agents)} agents from registry config")
                
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Error loading agent registry config: {e}")
        else:
            logger.info("No agent registry config found, starting with empty registry")
    
    def save_config(self):
        """Persist registry state for disaster recovery and GitOps workflows."""
        config = {
            "agents": [agent.to_dict() for agent in self.agents.values()]
        }
        
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info("agent_registry_saved",
                component="orchestrator",
                operation="save_config",
                agent_count=len(self.agents)
            )
        except Exception as e:
            logger.error("agent_registry_save_error",
                component="orchestrator",
                operation="save_config",
                error=str(e),
                error_type=type(e).__name__
            )
    
    def register_agent(self, name: str, endpoint: str, agent_card: Optional[AgentCard] = None):
        """Register a service instance with the discovery system.
        
        Implements the service registration pattern, allowing agents to
        advertise their capabilities and endpoints for dynamic discovery.
        """
        if agent_card is None:
            agent_card = AgentCard(
                name=name,
                version="unknown",
                description="",
                capabilities=[],
                endpoints={},
                communication_modes=[]
            )
        
        registered_agent = RegisteredAgent(
            name=name,
            endpoint=endpoint,
            agent_card=agent_card
        )
        
        self.agents[name] = registered_agent
        
        logger.info("agent_registered", component="orchestrator",
                                agent_name=name,
                                endpoint=endpoint,
                                capabilities=agent_card.capabilities if agent_card else [])
        logger.info("agent_registered_success",
            component="orchestrator",
            operation="register_agent",
            agent_name=name,
            endpoint=endpoint
        )
        self.save_config()
    
    def unregister_agent(self, name: str):
        """Remove an agent from the registry"""
        if name in self.agents:
            del self.agents[name]
            logger.info("agent_unregistered_success",
                component="orchestrator",
                operation="unregister_agent",
                agent_name=name
            )
            self.save_config()
    
    def remove_agent(self, name: str) -> bool:
        """Remove an agent from the registry (alias for unregister_agent)"""
        if name in self.agents:
            self.unregister_agent(name)
            return True
        return False
    
    def update_agent_status(self, name: str, status: str):
        """Update the status of a registered agent"""
        agent = self.get_agent(name)
        if agent:
            agent.status = status
            agent.last_health_check = datetime.now().isoformat()
            logger.info(f"Updated agent {name} status to {status}")
            # Don't save config here - let caller decide when to persist
    
    def get_agent(self, name: str) -> Optional[RegisteredAgent]:
        """Get a registered agent by name"""
        return self.agents.get(name)
    
    def list_agents(self) -> List[RegisteredAgent]:
        """Get all registered agents"""
        return list(self.agents.values())
    
    def find_agents_by_capability(self, capability: str) -> List[RegisteredAgent]:
        """Capability-based service discovery for load distribution.
        
        Enables horizontal scaling by finding all agents that can
        handle a specific capability, supporting load balancing and
        failover scenarios.
        """
        matching_agents = []
        for agent in self.agents.values():
            if capability in agent.agent_card.capabilities:
                matching_agents.append(agent)
        
        # Log capability query
        logger.info(json.dumps({
            "timestamp": time.time(),
            "operation": "CAPABILITY_QUERY",
            "capability": capability,
            "agents_found": len(matching_agents),
            "agent_names": [agent.name for agent in matching_agents]
        }))
        
        return matching_agents
    
    def find_best_agent_for_task(self, task_description: str, required_capabilities: Optional[List[str]] = None) -> Optional[RegisteredAgent]:
        """Intelligent service selection using capability matching.
        
        Implements smart routing by selecting the most appropriate
        agent based on capabilities and health status, similar to
        service mesh routing policies.
        """
        if required_capabilities:
            candidates = []
            for agent in self.agents.values():
                if agent.status == "online" and all(cap in agent.agent_card.capabilities for cap in required_capabilities):
                    candidates.append(agent)
            
            if candidates:
                selected = candidates[0]
                logger.info(json.dumps({
                    "timestamp": time.time(),
                    "operation": "AGENT_SELECTED",
                    "selection_method": "required_capabilities",
                    "task_description": task_description[:100],
                    "required_capabilities": required_capabilities,
                    "selected_agent": selected.name,
                    "candidates_count": len(candidates)
                }))
                return selected
        
        task_lower = task_description.lower()
        for agent in self.agents.values():
            if agent.status == "online":
                agent_keywords = [cap.lower() for cap in agent.agent_card.capabilities]
                agent_keywords.extend([agent.name.lower(), agent.agent_card.description.lower()])
                
                if any(keyword in task_lower for keyword in agent_keywords):
                    return agent
        
        return None
    
    async def health_check_agent(self, agent_name: str) -> bool:
        """Execute health probe for a specific service instance.
        
        Implements the health check pattern with configurable timeouts,
        updating service status for circuit breaker integration and
        ensuring only healthy instances receive traffic.
        """
        agent = self.get_agent(agent_name)
        if not agent:
            logger.warning(f"Health check failed: agent {agent_name} not found in registry")
            return False
        
        start_time = asyncio.get_event_loop().time()
        previous_status = agent.status
        
        # Get config before try block so it's available in except blocks
        from src.utils.config import get_a2a_config
        a2a_config = get_a2a_config()
        
        try:
            logger.info("health_check_start",
                component="orchestrator",
                operation="health_check_agent",
                agent_name=agent_name,
                endpoint=agent.endpoint,
                current_status=previous_status
            )
            
            async with A2AClient(timeout=a2a_config.health_check_timeout) as client:
                agent_card = await client.get_agent_card(agent.endpoint + "/a2a")
                
                agent.agent_card = agent_card
                agent.status = "online"
                agent.last_health_check = datetime.now().isoformat()
                
                elapsed = asyncio.get_event_loop().time() - start_time
                logger.info("health_check_success",
                    component="orchestrator",
                    operation="health_check_agent",
                    agent_name=agent_name,
                    duration_seconds=round(elapsed, 3),
                    previous_status=previous_status,
                    new_status="online",
                    capabilities=agent_card.capabilities,
                    version=agent_card.version
                )
                return True
                
        except A2AException as e:
            agent.status = "error"
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.warning("health_check_failed",
                component="orchestrator",
                operation="health_check_agent",
                agent_name=agent_name,
                duration_seconds=round(elapsed, 3),
                previous_status=previous_status,
                new_status="error",
                error_type="A2AException",
                error=str(e)
            )
            return False
        except asyncio.TimeoutError:
            agent.status = "offline"
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.warning("health_check_timeout",
                component="orchestrator",
                operation="health_check_agent",
                agent_name=agent_name,
                duration_seconds=round(elapsed, 3),
                previous_status=previous_status,
                new_status="offline",
                error_type="Timeout",
                timeout_value=a2a_config.health_check_timeout
            )
            return False
        except Exception as e:
            agent.status = "offline"
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.warning("health_check_error",
                component="orchestrator",
                operation="health_check_agent",
                agent_name=agent_name,
                duration_seconds=round(elapsed, 3),
                previous_status=previous_status,
                new_status="offline",
                error_type=type(e).__name__,
                error=str(e)
            )
            return False
    
    async def health_check_all_agents(self) -> Dict[str, bool]:
        """Concurrent health monitoring for all service instances.
        
        Executes parallel health checks to minimize discovery latency,
        essential for maintaining real-time service availability in
        distributed systems.
        """
        results = {}
        
        logger.info("health_check_all_start",
            component="orchestrator",
            operation="health_check_all_agents",
            agent_count=len(self.agents)
        )
        start_time = asyncio.get_event_loop().time()
        
        tasks = []
        for agent_name in self.agents.keys():
            task = asyncio.create_task(self.health_check_agent(agent_name))
            tasks.append((agent_name, task))
        
        for agent_name, task in tasks:
            try:
                results[agent_name] = await task
            except Exception as e:
                logger.error("health_check_unexpected_error",
                    component="orchestrator",
                    operation="health_check_all_agents",
                    agent_name=agent_name,
                    error=str(e),
                    error_type=type(e).__name__
                )
                results[agent_name] = False
        
        self.save_config()
        
        elapsed = asyncio.get_event_loop().time() - start_time
        online_count = sum(1 for status in results.values() if status)
        logger.info("health_check_all_complete",
            component="orchestrator",
            operation="health_check_all_agents",
            duration_seconds=round(elapsed, 2),
            total_agents=len(results),
            online_count=online_count,
            offline_count=len(results) - online_count,
            success_rate=round(online_count / len(results) * 100, 1) if results else 0
        )
        
        return results
    
    async def discover_agent(self, endpoint: str) -> bool:
        """Discover and register a single agent from an endpoint"""
        try:
            async with A2AClient() as client:
                agent_card = await client.get_agent_card(endpoint + "/a2a")
                self.register_agent(
                    name=agent_card.name,
                    endpoint=endpoint,
                    agent_card=agent_card
                )
                logger.info(f"Discovered agent: {agent_card.name} at {endpoint}")
                self.save_config()
                return True
        except Exception as e:
            logger.debug(f"Failed to discover agent at {endpoint}: {e}")
            return False
    
    async def discover_agents(self, discovery_endpoints: List[str]) -> int:
        """Dynamic service discovery from potential endpoints.
        
        Implements pull-based discovery by probing endpoints for
        agent capabilities, supporting environments where agents
        cannot self-register (e.g., firewalled networks).
        """
        discovered_count = 0
        
        async with A2AClient() as client:
            for endpoint in discovery_endpoints:
                try:
                    agent_card = await client.get_agent_card(endpoint + "/a2a")
                    self.register_agent(
                        name=agent_card.name,
                        endpoint=endpoint,
                        agent_card=agent_card
                    )
                    
                    discovered_count += 1
                    logger.info(f"Discovered agent: {agent_card.name} at {endpoint}")
                    
                except A2AException as e:
                    logger.debug(f"No agent found at {endpoint}: {e}")
                except Exception as e:
                    logger.warning(f"Error discovering agent at {endpoint}: {e}")
        
        if discovered_count > 0:
            self.save_config()
        
        return discovered_count
    
    def get_online_agents(self) -> List[RegisteredAgent]:
        """Get all agents with 'online' status"""
        return [agent for agent in self.agents.values() if agent.status == "online"]
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Service mesh observability metrics for monitoring.
        
        Provides key metrics for APM integration, supporting
        SRE practices and operational dashboards.
        """
        total_agents = len(self.agents)
        online_agents = len([a for a in self.agents.values() if a.status == "online"])
        offline_agents = len([a for a in self.agents.values() if a.status == "offline"])
        error_agents = len([a for a in self.agents.values() if a.status == "error"])
        unknown_agents = len([a for a in self.agents.values() if a.status == "unknown"])
        
        all_capabilities = set()
        agents_by_capability = {}
        
        for agent in self.agents.values():
            all_capabilities.update(agent.agent_card.capabilities)
            for capability in agent.agent_card.capabilities:
                if capability not in agents_by_capability:
                    agents_by_capability[capability] = 0
                agents_by_capability[capability] += 1
        
        return {
            "total_agents": total_agents,
            "online_agents": online_agents,
            "offline_agents": offline_agents,
            "error_agents": error_agents,
            "unknown_agents": unknown_agents,
            "capabilities": sorted(list(all_capabilities)),
            "available_capabilities": sorted(list(all_capabilities)),
            "agents_by_capability": agents_by_capability
        }