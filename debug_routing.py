#!/usr/bin/env python3
"""Debug script to trace routing decisions in plan-execute graph."""

import asyncio
import sys
import os
sys.path.insert(0, '/Users/nick.peterson/consultant-assistant')

from dotenv import load_dotenv
load_dotenv()

from src.orchestrator.plan_execute_graph import PlanExecuteGraph
from src.orchestrator.plan_execute_state import create_initial_state, is_plan_complete
from langchain_core.messages import HumanMessage

async def debug_routing():
    """Debug the routing decisions step by step."""
    print("🔍 Debugging routing decisions...")
    
    # Create graph
    graph = PlanExecuteGraph()
    
    # Create initial state
    initial_state = create_initial_state("hello")
    initial_state["messages"] = [HumanMessage(content="hello")]
    
    print("1️⃣ Testing planner routing...")
    planner_result = await graph._planner_node(initial_state)
    routing_decision = graph._route_after_planning(planner_result)
    print(f"   Planner result: plan={bool(planner_result.get('plan'))}")
    print(f"   Routing decision: {routing_decision}")
    
    print("\n2️⃣ Testing approver routing...")
    approver_result = await graph._approver_node(planner_result)
    routing_decision = graph._route_after_approval(approver_result)
    print(f"   Plan status: {approver_result['plan']['status'] if approver_result.get('plan') else 'None'}")
    print(f"   Routing decision: {routing_decision}")
    
    print("\n3️⃣ Testing executor routing...")
    executor_result = await graph._executor_node(approver_result)
    routing_decision = graph._route_after_execution(executor_result)
    print(f"   Plan complete: {is_plan_complete(executor_result)}")
    print(f"   Task results: {len(executor_result.get('task_results', {}))}")
    if executor_result.get('plan'):
        for task in executor_result['plan']['tasks']:
            print(f"     Task: {task['content'][:50]} - Status: {task['status']}")
    print(f"   Routing decision: {routing_decision}")
    
    print("\n4️⃣ Testing progress tracker routing...")
    progress_result = await graph._progress_tracker_node(executor_result)
    routing_decision = graph._route_after_progress(progress_result)
    print(f"   Plan complete after progress: {is_plan_complete(progress_result)}")
    print(f"   Routing decision: {routing_decision}")
    
    if routing_decision == "next_task":
        print("   ⚠️  This will loop back to executor!")
        print("   This is likely the source of the infinite loop!")

if __name__ == "__main__":
    asyncio.run(debug_routing())