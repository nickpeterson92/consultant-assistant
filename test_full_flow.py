#!/usr/bin/env python3
"""Test the full plan-execute flow end-to-end."""

import asyncio
import sys
import os
sys.path.insert(0, '/Users/nick.peterson/consultant-assistant')

from dotenv import load_dotenv
load_dotenv()

from src.orchestrator.plan_execute_graph import create_plan_execute_graph
from src.orchestrator.plan_execute_state import create_initial_state
from langchain_core.messages import HumanMessage

async def test_full_flow():
    """Test the complete plan-execute flow."""
    print("🚀 Testing full plan-execute flow...")
    
    try:
        # Create the graph
        graph = create_plan_execute_graph()
        
        # Create initial state
        initial_state = create_initial_state("hello")
        initial_state["messages"] = [HumanMessage(content="hello")]
        
        print("✅ Graph created successfully")
        print(f"Initial state: {initial_state['original_request']}")
        
        # Test the full flow
        config = {
            "configurable": {
                "thread_id": "test-thread",
                "user_id": "test-user"
            }
        }
        
        print("🔄 Running full graph execution...")
        result = await graph.graph.ainvoke(initial_state, config)
        
        print(f"✅ Graph execution completed!")
        print(f"Final result keys: {list(result.keys())}")
        
        # Check the plan
        if result.get("plan"):
            plan = result["plan"]
            print(f"📋 Plan created with {len(plan['tasks'])} tasks:")
            for i, task in enumerate(plan["tasks"], 1):
                print(f"  {i}. {task['content']} (Agent: {task['agent']}, Status: {task['status']})")
        else:
            print("❌ No plan was created")
            
        # Check messages
        if result.get("messages"):
            print(f"💬 Messages: {len(result['messages'])} total")
            for msg in result["messages"]:
                print(f"  - {type(msg).__name__}: {msg.content[:100]}...")
        else:
            print("❌ No messages found")
            
        # Check if execution completed
        if result.get("plan") and result["plan"].get("status"):
            print(f"📊 Final plan status: {result['plan']['status']}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error in full flow test: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    asyncio.run(test_full_flow())