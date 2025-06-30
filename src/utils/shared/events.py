"""Event-based tracking system for the orchestrator.

This module provides event models and utilities for tracking orchestrator activities
instead of using the confusing "turns" counter. Events provide better debugging,
analytics, and allow for more intelligent triggering of background tasks.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List, cast
from dataclasses import dataclass, field
from enum import Enum


class EventType(Enum):
    """Types of events that can occur in the orchestrator."""
    # Message events
    USER_MESSAGE = "user_message"
    AI_RESPONSE = "ai_response"
    SYSTEM_MESSAGE = "system_message"
    
    # Tool events
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    AGENT_CALL = "agent_call"
    AGENT_RESPONSE = "agent_response"
    
    # Background task events
    SUMMARY_TRIGGERED = "summary_triggered"
    SUMMARY_COMPLETED = "summary_completed"
    MEMORY_UPDATE_TRIGGERED = "memory_update_triggered"
    MEMORY_UPDATE_COMPLETED = "memory_update_completed"
    
    # System events
    ORCHESTRATOR_START = "orchestrator_start"
    ORCHESTRATOR_END = "orchestrator_end"
    ERROR = "error"
    
    # Cost tracking events
    TOKEN_USAGE = "token_usage"


@dataclass
class OrchestratorEvent:
    """Represents a single event in the orchestrator's execution.
    
    Attributes:
        event_type: The type of event that occurred
        timestamp: When the event occurred
        details: Event-specific data
        message_count: Total messages in conversation at event time
        token_count: Estimated tokens used (if applicable)
        cost_estimate: Estimated cost in USD (if applicable)
    """
    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)
    message_count: int = 0
    token_count: Optional[int] = None
    cost_estimate: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for storage/serialization."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "message_count": self.message_count,
            "token_count": self.token_count,
            "cost_estimate": self.cost_estimate
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrchestratorEvent':
        """Create event from dictionary."""
        return cls(
            event_type=EventType(data["event_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            details=data.get("details", {}),
            message_count=data.get("message_count", 0),
            token_count=data.get("token_count"),
            cost_estimate=data.get("cost_estimate")
        )


class EventAnalyzer:
    """Utilities for analyzing event streams."""
    
    @staticmethod
    def count_events_by_type(events: List[OrchestratorEvent], event_type: EventType) -> int:
        """Count how many events of a specific type have occurred."""
        return sum(1 for e in events if e.event_type == event_type)
    
    @staticmethod
    def get_last_event_of_type(events: List[OrchestratorEvent], event_type: EventType) -> Optional[OrchestratorEvent]:
        """Get the most recent event of a specific type."""
        for event in reversed(events):
            if event.event_type == event_type:
                return event
        return None
    
    @staticmethod
    def time_since_last_event(events: List[OrchestratorEvent], event_type: EventType) -> Optional[float]:
        """Get seconds since the last event of a specific type."""
        last_event = EventAnalyzer.get_last_event_of_type(events, event_type)
        if last_event:
            return (datetime.now() - last_event.timestamp).total_seconds()
        return None
    
    @staticmethod
    def should_trigger_summary(events: List[OrchestratorEvent], 
                             user_message_threshold: int = 5,
                             time_threshold_seconds: float = 300) -> bool:
        """Determine if a summary should be triggered based on events.
        
        Triggers when:
        - N user messages since last summary
        - OR X seconds since last summary (if any messages exist)
        """
        last_summary = EventAnalyzer.get_last_event_of_type(events, EventType.SUMMARY_TRIGGERED)
        
        if last_summary:
            # Count user messages since last summary
            messages_since = sum(1 for e in events 
                               if e.timestamp > last_summary.timestamp 
                               and e.event_type == EventType.USER_MESSAGE)
            
            # Check time since last summary
            time_since = (datetime.now() - last_summary.timestamp).total_seconds()
            
            return (messages_since >= user_message_threshold or 
                   (time_since >= time_threshold_seconds and messages_since > 0))
        else:
            # No summary yet, check total user messages
            total_messages = EventAnalyzer.count_events_by_type(events, EventType.USER_MESSAGE)
            return total_messages >= user_message_threshold
    
    @staticmethod
    def should_trigger_memory_update(events: List[OrchestratorEvent],
                                   tool_call_threshold: int = 3,
                                   agent_call_threshold: int = 2) -> bool:
        """Determine if memory should be updated based on events.
        
        Triggers when:
        - N tool calls since last memory update
        - OR N agent calls since last memory update
        """
        last_update = EventAnalyzer.get_last_event_of_type(events, EventType.MEMORY_UPDATE_TRIGGERED)
        
        if last_update:
            # Count relevant events since last update
            tool_calls = sum(1 for e in events 
                           if e.timestamp > last_update.timestamp 
                           and e.event_type == EventType.TOOL_CALL)
            
            agent_calls = sum(1 for e in events 
                            if e.timestamp > last_update.timestamp 
                            and e.event_type == EventType.AGENT_CALL)
            
            return tool_calls >= tool_call_threshold or agent_calls >= agent_call_threshold
        else:
            # No memory update yet, check total counts
            total_tools = EventAnalyzer.count_events_by_type(events, EventType.TOOL_CALL)
            total_agents = EventAnalyzer.count_events_by_type(events, EventType.AGENT_CALL)
            return total_tools >= tool_call_threshold or total_agents >= agent_call_threshold
    
    @staticmethod
    def calculate_total_cost(events: List[OrchestratorEvent]) -> float:
        """Calculate total cost from all events."""
        return sum(e.cost_estimate for e in events if e.cost_estimate is not None)
    
    @staticmethod
    def calculate_total_tokens(events: List[OrchestratorEvent]) -> int:
        """Calculate total tokens used from all events."""
        return sum(e.token_count for e in events if e.token_count is not None)
    
    @staticmethod
    def get_event_summary(events: List[OrchestratorEvent]) -> Dict[str, Any]:
        """Generate a summary of all events."""
        summary: Dict[str, Any] = {
            "total_events": len(events),
            "event_counts": {},
            "total_cost": EventAnalyzer.calculate_total_cost(events),
            "total_tokens": EventAnalyzer.calculate_total_tokens(events),
            "duration_seconds": 0,
            "first_event": None,
            "last_event": None
        }
        
        # Count events by type
        for event_type in EventType:
            count = EventAnalyzer.count_events_by_type(events, event_type)
            if count > 0:
                summary["event_counts"][event_type.value] = count
        
        # Calculate duration
        if events:
            summary["first_event"] = events[0].timestamp.isoformat()
            summary["last_event"] = events[-1].timestamp.isoformat()
            summary["duration_seconds"] = (events[-1].timestamp - events[0].timestamp).total_seconds()
        
        return summary


# Helper functions for creating common events
def create_user_message_event(message: str, message_count: int, **kwargs) -> OrchestratorEvent:
    """Create a user message event."""
    return OrchestratorEvent(
        event_type=EventType.USER_MESSAGE,
        details={"message_preview": message[:200], **kwargs},
        message_count=message_count
    )


def create_ai_response_event(response: str, message_count: int, token_count: int, **kwargs) -> OrchestratorEvent:
    """Create an AI response event."""
    cost_estimate = token_count * 0.00001  # Example cost calculation
    return OrchestratorEvent(
        event_type=EventType.AI_RESPONSE,
        details={"response_preview": response[:200], **kwargs},
        message_count=message_count,
        token_count=token_count,
        cost_estimate=cost_estimate
    )


def create_tool_call_event(tool_name: str, tool_args: Dict[str, Any], message_count: int, **kwargs) -> OrchestratorEvent:
    """Create a tool call event."""
    return OrchestratorEvent(
        event_type=EventType.TOOL_CALL,
        details={"tool_name": tool_name, "tool_args": tool_args, **kwargs},
        message_count=message_count
    )


def create_summary_triggered_event(message_count: int, reason: str, **kwargs) -> OrchestratorEvent:
    """Create a summary triggered event."""
    return OrchestratorEvent(
        event_type=EventType.SUMMARY_TRIGGERED,
        details={"reason": reason, **kwargs},
        message_count=message_count
    )


def create_memory_update_triggered_event(message_count: int, reason: str, **kwargs) -> OrchestratorEvent:
    """Create a memory update triggered event."""
    return OrchestratorEvent(
        event_type=EventType.MEMORY_UPDATE_TRIGGERED,
        details={"reason": reason, **kwargs},
        message_count=message_count
    )