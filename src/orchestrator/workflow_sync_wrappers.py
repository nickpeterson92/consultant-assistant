"""Synchronous wrappers for async workflow functions to work with LangGraph."""

import asyncio
from typing import Dict, Any
from src.orchestrator.core.state import PlanExecute

# Import the async functions
from src.orchestrator.plan_and_execute import (
    execute_step as async_execute_step,
    plan_step as async_plan_step,
    replan_step as async_replan_step
)

def run_async(coro):
    """Run an async coroutine in a sync context."""
    import nest_asyncio
    nest_asyncio.apply()
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Use nest_asyncio to allow nested event loops
            return loop.run_until_complete(coro)
        else:
            # No running loop, use asyncio.run
            return asyncio.run(coro)
    except RuntimeError:
        # Create new event loop and run
        return asyncio.run(coro)

def execute_step(state: PlanExecute) -> Dict[str, Any]:
    """Synchronous wrapper for async execute_step."""
    return run_async(async_execute_step(state))

def plan_step(state: PlanExecute) -> Dict[str, Any]:
    """Synchronous wrapper for async plan_step."""
    return run_async(async_plan_step(state))

def replan_step(state: PlanExecute) -> Dict[str, Any]:
    """Synchronous wrapper for async replan_step."""
    return run_async(async_replan_step(state))