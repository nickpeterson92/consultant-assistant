#!/usr/bin/env python3
"""Debug script to test the planner node with 'hello' request."""

import asyncio
import sys
import os
sys.path.insert(0, '/Users/nick.peterson/consultant-assistant')

from src.orchestrator.plan_execute_graph import PlanExecuteGraph
from src.orchestrator.plan_execute_state import create_initial_state
from langchain_core.messages import HumanMessage

async def test_planner():
    """Test the planner with a simple 'hello' request."""
    print("Testing planner with 'hello' request...")
    
    # Create graph
    graph = PlanExecuteGraph()
    
    # Create initial state
    initial_state = create_initial_state("hello")
    initial_state["messages"] = [HumanMessage(content="hello")]
    
    print(f"Initial state: {initial_state}")
    
    # Test planner node directly
    try:
        result = await graph._planner_node(initial_state)
        print(f"Planner result: {result}")
        
        # Check if plan was created
        if result.get("plan"):
            plan = result["plan"]
            print(f"Plan created successfully:")
            print(f"  - ID: {plan['id']}")
            print(f"  - Tasks: {len(plan['tasks'])}")
            for i, task in enumerate(plan['tasks'], 1):
                print(f"    {i}. {task['content']} (Agent: {task['agent']})")
        else:
            print("❌ No plan was created!")
            
    except Exception as e:
        print(f"❌ Error in planner: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_planner())