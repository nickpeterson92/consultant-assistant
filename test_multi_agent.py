#!/usr/bin/env python3
"""
Quick test script for the multi-agent system
"""

import asyncio
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.orchestrator.agent_registry import AgentRegistry
from src.a2a import A2AClient, A2ATask

async def test_agent_registry():
    """Test the agent registry functionality"""
    print("Testing Agent Registry...")
    
    registry = AgentRegistry()
    
    # Test loading configuration
    agents = registry.list_agents()
    print(f"Loaded {len(agents)} agents from configuration")
    
    for agent in agents:
        print(f"- {agent.name}: {', '.join(agent.agent_card.capabilities)}")
    
    return registry

async def test_agent_discovery():
    """Test agent discovery"""
    print("\nTesting Agent Discovery...")
    
    registry = AgentRegistry()
    
    # Test discovery endpoints
    discovery_endpoints = [
        "http://localhost:8002",  # Salesforce agent (updated port)
        "http://localhost:8003",  # Future agents
    ]
    
    discovered = await registry.discover_agents(discovery_endpoints)
    print(f"Discovered {discovered} agents")
    
    return registry

async def test_a2a_communication():
    """Test A2A protocol communication"""
    print("\nTesting A2A Communication...")
    
    # Test if Salesforce agent is running
    try:
        async with A2AClient() as client:
            agent_card = await client.get_agent_card("http://localhost:8002/a2a")
            print(f"Successfully connected to: {agent_card.name}")
            print(f"Capabilities: {', '.join(agent_card.capabilities)}")
            
            # Test a simple task
            task = A2ATask(
                id="test-task-1",
                instruction="List available Salesforce operations",
                context={"test": True},
                state_snapshot={"messages": [], "memory": {}}
            )
            
            result = await client.process_task("http://localhost:8002/a2a", task)
            print(f"Task result: {result}")
            
    except Exception as e:
        print(f"A2A Communication failed: {e}")
        print("Make sure the Salesforce agent is running with: python3 salesforce_agent.py")

async def test_orchestrator_tools():
    """Test orchestrator tools (without full orchestrator)"""
    print("\nTesting Orchestrator Tools...")
    
    from src.orchestrator.agent_registry import AgentRegistry
    from src.orchestrator.agent_caller_tools import SalesforceAgentTool
    
    registry = AgentRegistry()
    tool = SalesforceAgentTool(registry)
    
    # Mock state for testing
    mock_state = {
        "messages": [{"role": "user", "content": "test"}],
        "memory": {},
        "turns": 1
    }
    
    try:
        # This will fail if agent is not running, but tests the tool logic
        result = await tool._arun("test instruction", state=mock_state)
        print(f"Tool result: {result}")
    except Exception as e:
        print(f"Tool test failed (expected if agent not running): {e}")

async def main():
    """Run all tests"""
    print("=== Multi-Agent System Test Suite ===\n")
    
    # Test 1: Agent Registry
    await test_agent_registry()
    
    # Test 2: Agent Discovery
    await test_agent_discovery()
    
    # Test 3: A2A Communication
    await test_a2a_communication()
    
    # Test 4: Orchestrator Tools
    await test_orchestrator_tools()
    
    print("\n=== Test Suite Complete ===")
    print("To run the full system:")
    print("1. python3 start_system.py")
    print("2. Or start agents individually and then the orchestrator")

if __name__ == "__main__":
    asyncio.run(main())