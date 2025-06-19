#!/usr/bin/env python3
"""
Quick test of orchestrator without full CLI
"""

import os
import sys
import asyncio

# Disable tracing
os.environ["LANGCHAIN_TRACING_V2"] = "false"

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
agent_path = os.path.join(os.path.dirname(__file__), 'src', 'agent')
sys.path.insert(0, agent_path)

async def test_orchestrator_build():
    """Test if orchestrator graph builds without errors"""
    print("Testing orchestrator graph build...")
    
    try:
        from src.orchestrator.main import build_orchestrator_graph
        
        print("Building orchestrator graph...")
        graph = build_orchestrator_graph(debug_mode=True)
        print("✓ Orchestrator graph built successfully")
        
        # Test a simple invocation
        test_input = {"messages": [{"role": "user", "content": "hello"}]}
        config = {"configurable": {"thread_id": "test-1", "user_id": "test-user"}}
        
        print("Testing graph invocation...")
        result = await graph.ainvoke(test_input, config)
        print(f"✓ Graph invocation successful")
        print(f"Response type: {type(result.get('messages', []))}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Test orchestrator"""
    print("=== Orchestrator Quick Test ===\n")
    
    success = await test_orchestrator_build()
    
    if success:
        print("\n✓ Orchestrator is working!")
        print("You can now safely use: python3 orchestrator.py")
    else:
        print("\n✗ Orchestrator needs more fixes")

if __name__ == "__main__":
    asyncio.run(main())