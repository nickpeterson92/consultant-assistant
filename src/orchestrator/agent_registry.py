"""
Agent Registry and Discovery System for Multi-Agent Architecture
"""

import json
import os
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging

from ..a2a import AgentCard, A2AClient, A2AException

logger = logging.getLogger(__name__)

@dataclass
class RegisteredAgent:
    """Represents a registered agent in the system"""
    name: str
    endpoint: str
    agent_card: AgentCard
    status: str = "unknown"  # unknown, online, offline, error
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
    """Central registry for discovering and managing specialized agents"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.agents: Dict[str, RegisteredAgent] = {}
        self.config_path = config_path or "agent_registry.json"
        self.client = None
        self._load_config()
    
    def _load_config(self):
        """Load agent registry configuration from file"""
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
                        status=agent_config.get("status", "unknown")
                    )
                    self.agents[agent_config["name"]] = registered_agent
                    
                logger.info(f"Loaded {len(self.agents)} agents from registry config")
                
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Error loading agent registry config: {e}")
        else:
            logger.info("No agent registry config found, starting with empty registry")
    
    def save_config(self):
        """Save current registry state to file"""
        config = {
            "agents": [agent.to_dict() for agent in self.agents.values()]
        }
        
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"Saved agent registry config with {len(self.agents)} agents")
        except Exception as e:
            logger.error(f"Error saving agent registry config: {e}")
    
    def register_agent(self, name: str, endpoint: str, agent_card: Optional[AgentCard] = None):
        """Register a new agent or update existing registration"""
        if agent_card is None:
            # We'll fetch the agent card during health check
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
        
        # Log agent registration
        log_orchestrator_activity("AGENT_REGISTERED",
                                agent_name=name,
                                endpoint=endpoint,
                                capabilities=agent_card.capabilities if agent_card else [])
        logger.info(f"Registered agent: {name} at {endpoint}")
        
        # Save to config
        self.save_config()
    
    def unregister_agent(self, name: str):
        """Remove an agent from the registry"""
        if name in self.agents:
            del self.agents[name]
            logger.info(f"Unregistered agent: {name}")
            self.save_config()
    
    def get_agent(self, name: str) -> Optional[RegisteredAgent]:
        """Get a registered agent by name"""
        return self.agents.get(name)
    
    def list_agents(self) -> List[RegisteredAgent]:
        """Get all registered agents"""
        return list(self.agents.values())
    
    def find_agents_by_capability(self, capability: str) -> List[RegisteredAgent]:
        """Find agents that have a specific capability"""
        matching_agents = []
        for agent in self.agents.values():
            if capability in agent.agent_card.capabilities:
                matching_agents.append(agent)
        return matching_agents
    
    def find_best_agent_for_task(self, task_description: str, required_capabilities: List[str] = None) -> Optional[RegisteredAgent]:
        """Find the best agent to handle a specific task"""
        if required_capabilities:
            # Find agents that have all required capabilities
            candidates = []
            for agent in self.agents.values():
                if agent.status == "online" and all(cap in agent.agent_card.capabilities for cap in required_capabilities):
                    candidates.append(agent)
            
            if candidates:
                # For now, just return the first online candidate
                # Could implement more sophisticated selection logic
                return candidates[0]
        
        # Fallback: simple keyword matching
        task_lower = task_description.lower()
        for agent in self.agents.values():
            if agent.status == "online":
                agent_keywords = [cap.lower() for cap in agent.agent_card.capabilities]
                agent_keywords.extend([agent.name.lower(), agent.agent_card.description.lower()])
                
                if any(keyword in task_lower for keyword in agent_keywords):
                    return agent
        
        return None
    
    async def health_check_agent(self, agent_name: str) -> bool:
        """Check if an agent is healthy and update its status"""
        agent = self.get_agent(agent_name)
        if not agent:
            logger.warning(f"Health check failed: agent {agent_name} not found in registry")
            return False
        
        start_time = asyncio.get_event_loop().time()
        previous_status = agent.status
        
        try:
            logger.info(f"Starting health check for agent {agent_name} at {agent.endpoint} (current status: {previous_status})")
            
            # Get health check timeout from config
            from src.utils.config import get_a2a_config
            a2a_config = get_a2a_config()
            
            async with A2AClient(timeout=a2a_config.health_check_timeout) as client:
                # Try to get agent card to verify it's responding
                agent_card = await client.get_agent_card(agent.endpoint + "/a2a")
                
                # Update agent card with latest info
                agent.agent_card = agent_card
                agent.status = "online"
                agent.last_health_check = asyncio.get_event_loop().time()
                
                elapsed = asyncio.get_event_loop().time() - start_time
                logger.info(f"Health check PASSED for agent {agent_name} in {elapsed:.2f}s (status: {previous_status} -> online)")
                return True
                
        except A2AException as e:
            agent.status = "error"
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.warning(f"Health check FAILED for agent {agent_name} in {elapsed:.2f}s (status: {previous_status} -> error): A2A error - {e}")
            return False
        except asyncio.TimeoutError:
            agent.status = "offline"
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.warning(f"Health check FAILED for agent {agent_name} in {elapsed:.2f}s (status: {previous_status} -> offline): Timeout")
            return False
        except Exception as e:
            agent.status = "offline"
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.warning(f"Health check FAILED for agent {agent_name} in {elapsed:.2f}s (status: {previous_status} -> offline): {type(e).__name__} - {e}")
            return False
    
    async def health_check_all_agents(self) -> Dict[str, bool]:
        """Check health of all registered agents"""
        results = {}
        
        logger.info(f"Starting health check for {len(self.agents)} registered agents")
        start_time = asyncio.get_event_loop().time()
        
        # Run health checks concurrently
        tasks = []
        for agent_name in self.agents.keys():
            task = asyncio.create_task(self.health_check_agent(agent_name))
            tasks.append((agent_name, task))
        
        for agent_name, task in tasks:
            try:
                results[agent_name] = await task
            except Exception as e:
                logger.error(f"Unexpected error during health check for {agent_name}: {e}")
                results[agent_name] = False
        
        # Save updated statuses
        self.save_config()
        
        elapsed = asyncio.get_event_loop().time() - start_time
        online_count = sum(1 for status in results.values() if status)
        logger.info(f"Health check completed in {elapsed:.2f}s: {online_count}/{len(results)} agents online")
        
        return results
    
    async def discover_agents(self, discovery_endpoints: List[str]) -> int:
        """Discover agents from a list of potential endpoints"""
        discovered_count = 0
        
        async with A2AClient() as client:
            for endpoint in discovery_endpoints:
                try:
                    agent_card = await client.get_agent_card(endpoint + "/a2a")
                    
                    # Register the discovered agent
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
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get statistics about the agent registry"""
        total_agents = len(self.agents)
        online_agents = len([a for a in self.agents.values() if a.status == "online"])
        offline_agents = len([a for a in self.agents.values() if a.status == "offline"])
        error_agents = len([a for a in self.agents.values() if a.status == "error"])
        unknown_agents = len([a for a in self.agents.values() if a.status == "unknown"])
        
        # Get all unique capabilities
        all_capabilities = set()
        for agent in self.agents.values():
            all_capabilities.update(agent.agent_card.capabilities)
        
        return {
            "total_agents": total_agents,
            "online_agents": online_agents,
            "offline_agents": offline_agents,
            "error_agents": error_agents,
            "unknown_agents": unknown_agents,
            "available_capabilities": sorted(list(all_capabilities))
        }