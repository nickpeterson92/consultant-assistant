"""Orchestrator state management and event handling."""

from typing import Annotated, Dict, Any, List, Optional
import operator
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages

from src.utils.shared import OrchestratorEvent
from src.utils.config import get_conversation_config
from src.utils.logging import get_logger

logger = get_logger()


class OrchestratorState(TypedDict):
    """State schema for orchestrator graph."""
    messages: Annotated[list, add_messages]
    summary: str
    memory: dict
    events: Annotated[List[Dict[str, Any]], operator.add]
    active_agents: List[str]
    last_agent_interaction: Dict[str, Any]
    background_operations: Annotated[List[str], operator.add]
    background_results: Annotated[Dict[str, Any], lambda x, y: {**x, **y}]
    workflow_waiting: Optional[Dict[str, Any]]  # Add workflow waiting state


def load_events_with_limit(state: dict, limit: Optional[int] = None) -> List[OrchestratorEvent]:
    """Load events from state with automatic limiting to prevent unbounded growth.
    
    Args:
        state: Orchestrator state containing events
        limit: Maximum number of recent events to keep (default: from config)
        
    Returns:
        List of OrchestratorEvent objects, limited to most recent events
    """
    if limit is None:
        limit = get_conversation_config().max_event_history
        
    stored_events = state.get('events', [])
    if len(stored_events) > limit:
        # Keep only recent events
        stored_events = stored_events[-limit:]
        logger.info("event_history_trimmed",
            component="orchestrator",
            operation="trim_events",
            original_count=len(state.get('events', [])),
            new_count=limit
        )
    return [OrchestratorEvent.from_dict(e) for e in stored_events]