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
    except RuntimeError as e:
        # Only catch RuntimeError related to event loop issues
        if "no running event loop" in str(e) or "There is no current event loop" in str(e):
            # Create new event loop and run
            return asyncio.run(coro)
        else:
            # Re-raise other RuntimeErrors (including wrapped exceptions)
            raise

def execute_step(state: PlanExecute) -> Dict[str, Any]:
    """Synchronous wrapper for async execute_step."""
    # DEBUG logging
    from src.utils.logging.framework import SmartLogger
    logger = SmartLogger("orchestrator")
    logger.info("DEBUG_sync_execute_step_called",
               has_plan=bool(state.get("plan")),
               plan_length=len(state.get("plan", [])),
               has_response="response" in state)
    
    try:
        result = run_async(async_execute_step(state))
        logger.info("DEBUG_sync_execute_step_returning",
                   result_keys=list(result.keys()) if isinstance(result, dict) else "not_dict")
        return result
    except Exception as e:
        # IMPORTANT: Log but re-raise all exceptions, especially GraphInterrupt
        from langgraph.errors import GraphInterrupt
        if isinstance(e, GraphInterrupt):
            logger.info("DEBUG_sync_execute_step_interrupt_propagating",
                       interrupt_type=type(e).__name__,
                       has_args=bool(e.args))
        else:
            logger.error("DEBUG_sync_execute_step_error_propagating",
                        error_type=type(e).__name__,
                        error=str(e))
        raise

def plan_step(state: PlanExecute) -> Dict[str, Any]:
    """Synchronous wrapper for async plan_step."""
    # DEBUG logging
    from src.utils.logging.framework import SmartLogger
    logger = SmartLogger("orchestrator")
    logger.info("DEBUG_sync_plan_step_called",
               has_plan=bool(state.get("plan")),
               has_response="response" in state)
    result = run_async(async_plan_step(state))
    logger.info("DEBUG_sync_plan_step_returning",
               result_keys=list(result.keys()) if isinstance(result, dict) else "not_dict",
               has_plan="plan" in result if isinstance(result, dict) else False)
    return result

def replan_step(state: PlanExecute) -> Dict[str, Any]:
    """Synchronous wrapper for async replan_step."""
    return run_async(async_replan_step(state))