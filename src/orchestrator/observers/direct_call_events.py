"""SSE event types and emitters for direct agent calls."""

from typing import Dict, Any, Optional
from datetime import datetime
from src.utils.logging.framework import SmartLogger

logger = SmartLogger("orchestrator.observers.direct_call")


class DirectCallEventTypes:
    """Event types for direct agent calls."""
    AGENT_CALL_STARTED = "agent_call_started"
    AGENT_CALL_COMPLETED = "agent_call_completed" 
    AGENT_CALL_FAILED = "agent_call_failed"
    TOOL_SELECTED = "tool_selected"
    DIRECT_RESPONSE = "direct_response"
    WEB_SEARCH_STARTED = "web_search_started"
    WEB_SEARCH_COMPLETED = "web_search_completed"
    HUMAN_INPUT_REQUESTED = "human_input_requested"
    HUMAN_INPUT_RECEIVED = "human_input_received"


def emit_agent_call_event(
    event_type: str,
    agent_name: str,
    task_id: str,
    instruction: str,
    additional_data: Optional[Dict[str, Any]] = None
) -> None:
    """Emit SSE event for agent calls.
    
    Args:
        event_type: Type of event (from DirectCallEventTypes)
        agent_name: Name of the agent being called
        task_id: Task identifier
        instruction: The instruction sent to the agent
        additional_data: Additional event data
    """
    from src.orchestrator.observers import get_observer_registry
    
    # For human input events, send full instruction; for others, truncate for performance
    is_human_input = event_type in [
        DirectCallEventTypes.HUMAN_INPUT_REQUESTED,
        DirectCallEventTypes.HUMAN_INPUT_RECEIVED
    ]
    
    event_data = {
        "agent_name": agent_name,
        "task_id": task_id,
        "instruction": instruction if is_human_input else instruction[:200],
        "timestamp": datetime.now().isoformat(),
    }
    
    if additional_data:
        event_data.update(additional_data)
    
    # Get SSE observer and emit event
    registry = get_observer_registry()
    sse_observer = registry.get_observer("SSEObserver")
    
    if sse_observer:
        # Format for SSE
        sse_event = {
            "event": event_type,
            "data": event_data,
            "sse_payload": {
                "event": event_type,
                "data": event_data
            }
        }
        sse_observer.notify(sse_event)
        
        logger.info("direct_call_event_emitted",
                   event_type=event_type,
                   agent_name=agent_name,
                   task_id=task_id)


def emit_tool_selected_event(
    tool_name: str,
    tool_args: Dict[str, Any],
    task_context: Optional[str] = None
) -> None:
    """Emit event when a tool is selected for execution.
    
    Args:
        tool_name: Name of the tool being used
        tool_args: Arguments passed to the tool
        task_context: Optional context about why tool was selected
    """
    from src.orchestrator.observers import get_observer_registry
    
    event_data = {
        "tool_name": tool_name,
        "tool_args": tool_args,
        "task_context": task_context,
        "timestamp": datetime.now().isoformat(),
    }
    
    registry = get_observer_registry()
    sse_observer = registry.get_observer("SSEObserver")
    
    if sse_observer:
        sse_event = {
            "event": DirectCallEventTypes.TOOL_SELECTED,
            "data": event_data,
            "sse_payload": {
                "event": DirectCallEventTypes.TOOL_SELECTED,
                "data": event_data
            }
        }
        sse_observer.notify(sse_event)


def emit_direct_response_event(
    response_type: str,
    response_content: str,
    confidence: Optional[float] = None
) -> None:
    """Emit event for direct responses without tool calls.
    
    Args:
        response_type: Type of response (greeting, answer, etc.)
        response_content: The actual response
        confidence: Optional confidence score
    """
    from src.orchestrator.observers import get_observer_registry
    
    event_data = {
        "agent_name": "orchestrator",  # Direct responses come from the orchestrator itself
        "response_type": response_type,
        "response_preview": response_content[:200],
        "response_length": len(response_content),
        "confidence": confidence,
        "timestamp": datetime.now().isoformat(),
        "instruction": "Direct response to user",  # Provide a meaningful instruction text
        "task_id": "",  # No specific task ID for direct responses
    }
    
    registry = get_observer_registry()
    sse_observer = registry.get_observer("SSEObserver")
    
    if sse_observer:
        sse_event = {
            "event": DirectCallEventTypes.DIRECT_RESPONSE,
            "data": event_data,
            "sse_payload": {
                "event": DirectCallEventTypes.DIRECT_RESPONSE,
                "data": event_data
            }
        }
        sse_observer.notify(sse_event)