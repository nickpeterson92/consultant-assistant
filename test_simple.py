#!/usr/bin/env python3
"""
Simple test for the multi-agent system without circular references
"""

import os
import sys
import asyncio

# Disable LangSmith tracing
os.environ["LANGCHAIN_TRACING_V2"] = "false"

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def test_basic_orchestrator():
    """Test basic orchestrator functionality"""
    print("Testing basic orchestrator startup...")
    
    try:
        from src.orchestrator.agent_registry import AgentRegistry
        print("✓ Agent registry imported successfully")
        
        registry = AgentRegistry()
        agents = registry.list_agents()
        print(f"✓ Loaded {len(agents)} agents")
        
        if agents:
            for agent in agents:
                print(f"  - {agent.name}: {agent.status}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

async def test_simple_graph():
    """Test a simple LangGraph without complex state"""
    print("\nTesting simple LangGraph creation...")
    
    try:
        from dotenv import load_dotenv
        from langchain_core.messages import HumanMessage
        from langchain_openai import AzureChatOpenAI
        
        load_dotenv()
        
        # Create a simple LLM call
        llm = AzureChatOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            azure_deployment=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"],
            openai_api_version=os.environ["AZURE_OPENAI_API_VERSION"],
            openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
            temperature=0.0,
        )
        
        response = llm.invoke([HumanMessage(content="Hello, just say 'test successful'")])
        print(f"✓ LLM response: {response.content}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

async def main():
    """Run simple tests"""
    print("=== Simple Multi-Agent System Tests ===\n")
    
    # Test 1: Basic imports and registry
    test1_passed = await test_basic_orchestrator()
    
    # Test 2: Simple LangGraph
    test2_passed = await test_simple_graph()
    
    print(f"\n=== Results ===")
    print(f"Registry test: {'✓ PASSED' if test1_passed else '✗ FAILED'}")
    print(f"LangGraph test: {'✓ PASSED' if test2_passed else '✗ FAILED'}")
    
    if test1_passed and test2_passed:
        print("\n✓ Basic components are working!")
        print("Next steps:")
        print("1. Start Salesforce agent: python3 salesforce_agent.py")
        print("2. Test A2A communication")
        print("3. Start full orchestrator")
    else:
        print("\n✗ Basic components need fixing before proceeding")

if __name__ == "__main__":
    asyncio.run(main())