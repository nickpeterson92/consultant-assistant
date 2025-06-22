"""Tests for the agent registry module."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio
from datetime import datetime, timedelta

from src.orchestrator.agent_registry import AgentRegistry, RegisteredAgent
from src.a2a import AgentCard


class TestAgentRegistry:
    """Test the agent registry functionality."""
    
    @pytest.fixture
    def registry(self, tmp_path):
        """Create a fresh agent registry for each test."""
        # Use a temporary file for each test to avoid persistence
        config_file = tmp_path / "test_registry.json"
        return AgentRegistry(config_path=str(config_file))
    
    def test_register_agent(self, registry):
        """Test agent registration."""
        agent_card = AgentCard(
            name="salesforce-agent",
            version="1.0.0",
            description="Salesforce CRM agent",
            capabilities=["salesforce_operations", "crm_management"],
            endpoints={},
            communication_modes=["synchronous"]
        )
        
        registry.register_agent(
            name="salesforce-agent",
            endpoint="http://localhost:8001",
            agent_card=agent_card
        )
        
        # Verify agent is registered
        agents = registry.list_agents()
        assert len(agents) == 1
        assert agents[0].name == "salesforce-agent"
        assert agents[0].endpoint == "http://localhost:8001"
        assert "salesforce_operations" in agents[0].agent_card.capabilities
    
    def test_get_agent_by_name(self, registry):
        """Test retrieving agent by name."""
        agent_card = AgentCard(
            name="test-agent",
            version="1.0.0",
            description="Test agent",
            capabilities=["test_capability"],
            endpoints={},
            communication_modes=["synchronous"]
        )
        
        registry.register_agent(
            name="test-agent",
            endpoint="http://localhost:8002",
            agent_card=agent_card
        )
        
        # Get existing agent
        agent = registry.get_agent("test-agent")
        assert agent is not None
        assert agent.name == "test-agent"
        
        # Get non-existent agent
        agent = registry.get_agent("non-existent")
        assert agent is None
    
    def test_find_agents_by_capability(self, registry):
        """Test finding agents by capability."""
        # Register multiple agents
        agent_card_sf = AgentCard(
            name="salesforce-agent",
            version="1.0.0",
            description="Salesforce agent",
            capabilities=["salesforce", "crm"],
            endpoints={},
            communication_modes=["synchronous"]
        )
        registry.register_agent(
            name="salesforce-agent",
            endpoint="http://localhost:8001",
            agent_card=agent_card_sf
        )
        
        agent_card_hr = AgentCard(
            name="hr-agent",
            version="1.0.0",
            description="HR agent",
            capabilities=["hr", "employee_management"],
            endpoints={},
            communication_modes=["synchronous"]
        )
        registry.register_agent(
            name="hr-agent",
            endpoint="http://localhost:8002",
            agent_card=agent_card_hr
        )
        
        agent_card_multi = AgentCard(
            name="multi-agent",
            version="1.0.0",
            description="Multi-capability agent",
            capabilities=["salesforce", "hr", "reporting"],
            endpoints={},
            communication_modes=["synchronous"]
        )
        registry.register_agent(
            name="multi-agent",
            endpoint="http://localhost:8003",
            agent_card=agent_card_multi
        )
        
        # Find agents with salesforce capability
        salesforce_agents = registry.find_agents_by_capability("salesforce")
        assert len(salesforce_agents) == 2
        assert any(a.name == "salesforce-agent" for a in salesforce_agents)
        assert any(a.name == "multi-agent" for a in salesforce_agents)
        
        # Find agents with hr capability
        hr_agents = registry.find_agents_by_capability("hr")
        assert len(hr_agents) == 2
        
        # Find agents with non-existent capability
        none_agents = registry.find_agents_by_capability("non_existent")
        assert len(none_agents) == 0
    
    def test_update_agent_status(self, registry):
        """Test updating agent status."""
        agent_card = AgentCard(
            name="test-agent",
            version="1.0.0",
            description="Test agent",
            capabilities=[],
            endpoints={},
            communication_modes=["synchronous"]
        )
        
        registry.register_agent(
            name="test-agent",
            endpoint="http://localhost:8001",
            agent_card=agent_card
        )
        
        # Update status
        registry.update_agent_status("test-agent", "offline")
        
        agent = registry.get_agent("test-agent")
        assert agent.status == "offline"
        assert agent.last_health_check is not None
        
        # Update non-existent agent
        registry.update_agent_status("non-existent", "online")  # Should not raise
    
    def test_remove_agent(self, registry):
        """Test removing an agent."""
        agent_card = AgentCard(
            name="test-agent",
            version="1.0.0",
            description="Test agent",
            capabilities=[],
            endpoints={},
            communication_modes=["synchronous"]
        )
        
        registry.register_agent(
            name="test-agent",
            endpoint="http://localhost:8001",
            agent_card=agent_card
        )
        assert len(registry.list_agents()) == 1
        
        # Remove agent
        result = registry.remove_agent("test-agent")
        assert result is True
        assert len(registry.list_agents()) == 0
        
        # Remove non-existent agent
        result = registry.remove_agent("non-existent")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_health_check_single_agent(self, registry):
        """Test health checking a single agent."""
        agent_card = AgentCard(
            name="test-agent",
            version="1.0.0",
            description="Test agent",
            capabilities=[],
            endpoints={},
            communication_modes=["synchronous"]
        )
        registry.register_agent(
            name="test-agent",
            endpoint="http://localhost:8001",
            agent_card=agent_card
        )
        
        # Mock the A2AClient
        with patch('src.orchestrator.agent_registry.A2AClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Mock get_agent_card to return the same agent card
            mock_client.get_agent_card = AsyncMock(return_value=agent_card)
            
            result = await registry.health_check_agent("test-agent")
            assert result is True
            
            # Check that status was updated
            agent = registry.get_agent("test-agent")
            assert agent.status == "online"
    
    @pytest.mark.asyncio
    async def test_health_check_agent_offline(self, registry):
        """Test health check when agent is offline."""
        agent_card = AgentCard(
            name="test-agent",
            version="1.0.0",
            description="Test agent",
            capabilities=[],
            endpoints={},
            communication_modes=["synchronous"]
        )
        registry.register_agent(
            name="test-agent",
            endpoint="http://localhost:8001",
            agent_card=agent_card
        )
        
        # Mock the A2AClient to raise a generic exception (not A2AException)
        with patch('src.orchestrator.agent_registry.A2AClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Mock get_agent_card to raise a generic exception
            mock_client.get_agent_card = AsyncMock(side_effect=Exception("Connection refused"))
            
            result = await registry.health_check_agent("test-agent")
            assert result is False
            
            # Check that status was updated to offline
            agent = registry.get_agent("test-agent")
            assert agent.status == "offline"
    
    @pytest.mark.asyncio
    async def test_health_check_all_agents(self, registry):
        """Test health checking all agents."""
        # Register multiple agents
        agent_card1 = AgentCard(
            name="agent1",
            version="1.0.0",
            description="Agent 1",
            capabilities=[],
            endpoints={},
            communication_modes=["synchronous"]
        )
        registry.register_agent(
            name="agent1",
            endpoint="http://localhost:8001",
            agent_card=agent_card1
        )
        
        agent_card2 = AgentCard(
            name="agent2",
            version="1.0.0",
            description="Agent 2",
            capabilities=[],
            endpoints={},
            communication_modes=["synchronous"]
        )
        registry.register_agent(
            name="agent2",
            endpoint="http://localhost:8002",
            agent_card=agent_card2
        )
        
        # Mock mixed responses
        with patch('src.orchestrator.agent_registry.A2AClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Mock different responses for different endpoints
            async def mock_get_agent_card(endpoint):
                if "8001" in endpoint:
                    return agent_card1
                else:
                    raise Exception("Connection refused")
            
            mock_client.get_agent_card = mock_get_agent_card
            
            results = await registry.health_check_all_agents()
            
            assert results["agent1"] is True
            assert results["agent2"] is False
    
    def test_get_online_agents(self, registry):
        """Test getting only online agents."""
        # Register agents with different statuses
        for i, status in enumerate([("online1", "online"), ("offline1", "offline"), ("online2", "online")]):
            agent_card = AgentCard(
                name=status[0],
                version="1.0.0",
                description=f"Agent {status[0]}",
                capabilities=[],
                endpoints={},
                communication_modes=["synchronous"]
            )
            registry.register_agent(
                name=status[0],
                endpoint=f"http://localhost:800{i+1}",
                agent_card=agent_card
            )
            registry.update_agent_status(status[0], status[1])
        
        online_agents = registry.get_online_agents()
        assert len(online_agents) == 2
        assert all(a.status == "online" for a in online_agents)
        assert any(a.name == "online1" for a in online_agents)
        assert any(a.name == "online2" for a in online_agents)
    
    def test_get_registry_stats(self, registry):
        """Test getting registry statistics."""
        # Register agents with various states
        agents_data = [
            ("salesforce", "online", ["salesforce", "crm"]),
            ("hr", "offline", ["hr", "payroll"]),
            ("multi", "online", ["salesforce", "reporting"])
        ]
        
        for name, status, capabilities in agents_data:
            agent_card = AgentCard(
                name=name,
                version="1.0.0",
                description=f"{name} agent",
                capabilities=capabilities,
                endpoints={},
                communication_modes=["synchronous"]
            )
            registry.register_agent(
                name=name,
                endpoint=f"http://localhost:800{len(registry.agents) + 1}",
                agent_card=agent_card
            )
            registry.update_agent_status(name, status)
        
        stats = registry.get_registry_stats()
        
        assert stats["total_agents"] == 3
        assert stats["online_agents"] == 2
        assert stats["offline_agents"] == 1
        assert len(stats["capabilities"]) == 5  # salesforce, crm, hr, payroll, reporting
        assert stats["agents_by_capability"]["salesforce"] == 2
        assert stats["agents_by_capability"]["hr"] == 1
    
    @pytest.mark.asyncio
    async def test_discover_agent(self, registry):
        """Test agent auto-discovery."""
        with patch('src.orchestrator.agent_registry.A2AClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            # Create a discovered agent card
            discovered_card = AgentCard(
                name="discovered-agent",
                version="1.0.0",
                description="Auto-discovered agent",
                capabilities=["test_capability"],
                endpoints={},
                communication_modes=["synchronous"]
            )
            
            # Mock get_agent_card to return the discovered card
            mock_client.get_agent_card = AsyncMock(return_value=discovered_card)
            
            discovered = await registry.discover_agent("http://localhost:9999")
            assert discovered is True
            
            # Check agent was registered
            agent = registry.get_agent("discovered-agent")
            assert agent is not None
            assert agent.endpoint == "http://localhost:9999"
            assert "test_capability" in agent.agent_card.capabilities
    
    @pytest.mark.asyncio
    async def test_discover_agent_failure(self, registry):
        """Test failed agent discovery."""
        with patch('aiohttp.ClientSession') as mock_session:
            # Mock failed request
            mock_session.return_value.__aenter__.return_value.get.side_effect = Exception("Connection refused")
            
            discovered = await registry.discover_agent("http://localhost:9999")
            assert discovered is False
            
            # Check agent was not registered
            assert len(registry.list_agents()) == 0
    
    def test_registered_agent_creation(self):
        """Test RegisteredAgent dataclass creation and defaults."""
        # Minimal creation
        agent_card = AgentCard(
            name="test",
            version="1.0.0",
            description="Test agent",
            capabilities=[],
            endpoints={},
            communication_modes=["synchronous"]
        )
        
        agent = RegisteredAgent(
            name="test",
            endpoint="http://localhost:8000",
            agent_card=agent_card
        )
        
        assert agent.name == "test"
        assert agent.endpoint == "http://localhost:8000"
        assert agent.agent_card.capabilities == []
        assert agent.status == "unknown"
        assert agent.last_health_check is None
        
        # Full creation
        agent_card_full = AgentCard(
            name="full-agent",
            version="2.0.0",
            description="Test agent",
            capabilities=["cap1", "cap2"],
            endpoints={},
            communication_modes=["synchronous"]
        )
        
        agent = RegisteredAgent(
            name="full-agent",
            endpoint="http://localhost:8001",
            agent_card=agent_card_full,
            status="online",
            last_health_check="2024-01-01T00:00:00"
        )
        
        assert len(agent.agent_card.capabilities) == 2
        assert agent.agent_card.version == "2.0.0"
        assert agent.agent_card.description == "Test agent"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])