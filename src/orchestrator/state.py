"""Orchestrator state management."""

from typing import Annotated, Dict, Any, List, Optional
import operator
from typing_extensions import TypedDict
from datetime import datetime

from langgraph.graph.message import add_messages

from src.utils.logging import get_logger

logger = get_logger()


class SimpleTriggerState(TypedDict):
    """Minimal state for triggering background tasks."""
    timestamp: str  # ISO format timestamp
    message_count: int  # Message count at trigger time


class OrchestratorState(TypedDict):
    """State schema for orchestrator graph."""
    messages: Annotated[list, add_messages]
    summary: str
    memory: dict
    # Simple trigger tracking - no more events!
    last_summary_trigger: Optional[SimpleTriggerState]
    last_memory_trigger: Optional[SimpleTriggerState]
    tool_calls_since_memory: int
    agent_calls_since_memory: int
    # Existing fields
    active_agents: List[str]
    last_agent_interaction: Dict[str, Any]
    background_operations: Annotated[List[str], operator.add]
    background_results: Annotated[Dict[str, Any], lambda x, y: {**x, **y}]
    interrupted_workflow: Optional[Dict[str, Any]]  # Track interrupted workflow state
    _workflow_human_response: Optional[str]  # Human response for interrupted workflow


def should_trigger_summary(state: Dict[str, Any], 
                          user_message_threshold: int = 5,
                          time_threshold_seconds: float = 300) -> bool:
    """Determine if a summary should be triggered based on simple counters.
    
    Triggers when:
    - N user messages since last summary
    - OR X seconds since last summary (if any messages exist)
    """
    current_message_count = len(state.get("messages", []))
    last_trigger = state.get("last_summary_trigger")
    
    if last_trigger:
        # Calculate messages since last summary
        messages_since = current_message_count - last_trigger["message_count"]
        
        # Check time since last summary
        last_time = datetime.fromisoformat(last_trigger["timestamp"])
        time_since = (datetime.now() - last_time).total_seconds()
        
        return (messages_since >= user_message_threshold or 
               (time_since >= time_threshold_seconds and messages_since > 0))
    else:
        # No summary yet, check total messages
        return current_message_count >= user_message_threshold


def should_trigger_memory_update(state: Dict[str, Any],
                               tool_call_threshold: int = 3,
                               agent_call_threshold: int = 2) -> bool:
    """Determine if memory should be updated based on simple counters.
    
    Triggers when:
    - N tool calls since last memory update
    - OR N agent calls since last memory update
    """
    tool_calls = state.get("tool_calls_since_memory", 0)
    agent_calls = state.get("agent_calls_since_memory", 0)
    
    return tool_calls >= tool_call_threshold or agent_calls >= agent_call_threshold