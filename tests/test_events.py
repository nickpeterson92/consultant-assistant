"""Tests for the event-based tracking system."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.utils.events import (
    EventType, OrchestratorEvent, EventAnalyzer,
    create_user_message_event, create_ai_response_event,
    create_tool_call_event, create_summary_triggered_event,
    create_memory_update_triggered_event
)


class TestOrchestratorEvent:
    """Test the OrchestratorEvent class."""
    
    def test_event_creation(self):
        """Test basic event creation."""
        event = OrchestratorEvent(
            event_type=EventType.USER_MESSAGE,
            details={"message": "Hello"},
            message_count=5,
            token_count=10
        )
        
        assert event.event_type == EventType.USER_MESSAGE
        assert event.details["message"] == "Hello"
        assert event.message_count == 5
        assert event.token_count == 10
        assert isinstance(event.timestamp, datetime)
    
    def test_event_to_dict(self):
        """Test event serialization."""
        event = OrchestratorEvent(
            event_type=EventType.AI_RESPONSE,
            details={"response": "Hi there"},
            message_count=6,
            token_count=15,
            cost_estimate=0.0001
        )
        
        event_dict = event.to_dict()
        assert event_dict["event_type"] == "ai_response"
        assert event_dict["details"]["response"] == "Hi there"
        assert event_dict["message_count"] == 6
        assert event_dict["token_count"] == 15
        assert event_dict["cost_estimate"] == 0.0001
        assert "timestamp" in event_dict
    
    def test_event_from_dict(self):
        """Test event deserialization."""
        event_dict = {
            "event_type": "tool_call",
            "timestamp": datetime.now().isoformat(),
            "details": {"tool_name": "get_account"},
            "message_count": 10,
            "token_count": 50
        }
        
        event = OrchestratorEvent.from_dict(event_dict)
        assert event.event_type == EventType.TOOL_CALL
        assert event.details["tool_name"] == "get_account"
        assert event.message_count == 10
        assert event.token_count == 50


class TestEventHelpers:
    """Test helper functions for creating events."""
    
    def test_create_user_message_event(self):
        """Test user message event creation."""
        event = create_user_message_event("Hello, assistant!", 5)
        
        assert event.event_type == EventType.USER_MESSAGE
        assert event.details["message_preview"] == "Hello, assistant!"
        assert event.message_count == 5
    
    def test_create_ai_response_event(self):
        """Test AI response event creation."""
        event = create_ai_response_event("I can help with that", 6, 100)
        
        assert event.event_type == EventType.AI_RESPONSE
        assert event.details["response_preview"] == "I can help with that"
        assert event.message_count == 6
        assert event.token_count == 100
        assert event.cost_estimate == 0.001  # 100 * 0.00001
    
    def test_create_tool_call_event(self):
        """Test tool call event creation."""
        event = create_tool_call_event(
            "salesforce_agent",
            {"instruction": "get accounts"},
            7
        )
        
        assert event.event_type == EventType.TOOL_CALL
        assert event.details["tool_name"] == "salesforce_agent"
        assert event.details["tool_args"]["instruction"] == "get accounts"
        assert event.message_count == 7


class TestEventAnalyzer:
    """Test the EventAnalyzer utility class."""
    
    def setup_method(self):
        """Set up test events."""
        self.events = []
        
        # Add some user messages
        for i in range(3):
            self.events.append(OrchestratorEvent(
                event_type=EventType.USER_MESSAGE,
                timestamp=datetime.now() - timedelta(minutes=10-i),
                message_count=i*2 + 1
            ))
        
        # Add tool calls
        self.events.append(OrchestratorEvent(
            event_type=EventType.TOOL_CALL,
            timestamp=datetime.now() - timedelta(minutes=5),
            details={"tool_name": "get_account"}
        ))
        
        # Add AI response
        self.events.append(OrchestratorEvent(
            event_type=EventType.AI_RESPONSE,
            timestamp=datetime.now() - timedelta(minutes=4),
            token_count=150,
            cost_estimate=0.0015
        ))
    
    def test_count_events_by_type(self):
        """Test counting events by type."""
        assert EventAnalyzer.count_events_by_type(self.events, EventType.USER_MESSAGE) == 3
        assert EventAnalyzer.count_events_by_type(self.events, EventType.TOOL_CALL) == 1
        assert EventAnalyzer.count_events_by_type(self.events, EventType.AI_RESPONSE) == 1
        assert EventAnalyzer.count_events_by_type(self.events, EventType.SUMMARY_TRIGGERED) == 0
    
    def test_get_last_event_of_type(self):
        """Test getting the last event of a specific type."""
        last_user_msg = EventAnalyzer.get_last_event_of_type(self.events, EventType.USER_MESSAGE)
        assert last_user_msg is not None
        assert last_user_msg.message_count == 5  # The third user message
        
        last_summary = EventAnalyzer.get_last_event_of_type(self.events, EventType.SUMMARY_TRIGGERED)
        assert last_summary is None
    
    def test_time_since_last_event(self):
        """Test calculating time since last event."""
        # Should be around 8 minutes for last user message
        time_since = EventAnalyzer.time_since_last_event(self.events, EventType.USER_MESSAGE)
        assert time_since is not None
        assert 450 < time_since < 510  # Between 7.5 and 8.5 minutes
        
        # No summary events
        time_since = EventAnalyzer.time_since_last_event(self.events, EventType.SUMMARY_TRIGGERED)
        assert time_since is None
    
    def test_should_trigger_summary_no_previous(self):
        """Test summary triggering with no previous summary."""
        # With 3 user messages, should not trigger (threshold is 5)
        assert not EventAnalyzer.should_trigger_summary(self.events, user_message_threshold=5)
        
        # But should trigger with threshold of 3
        assert EventAnalyzer.should_trigger_summary(self.events, user_message_threshold=3)
    
    def test_should_trigger_summary_with_previous(self):
        """Test summary triggering with previous summary."""
        # Add a summary event 6 minutes ago
        summary_event = OrchestratorEvent(
            event_type=EventType.SUMMARY_TRIGGERED,
            timestamp=datetime.now() - timedelta(minutes=6)
        )
        self.events.append(summary_event)
        
        # Add 2 user messages AFTER the summary (4 and 3 minutes ago)
        for i in range(2):
            self.events.append(OrchestratorEvent(
                event_type=EventType.USER_MESSAGE,
                timestamp=datetime.now() - timedelta(minutes=4-i)
            ))
        
        # Should not trigger with 2 messages since summary (threshold is 5)
        # Also set time threshold high so it doesn't trigger on time
        assert not EventAnalyzer.should_trigger_summary(self.events, 
                                                       user_message_threshold=5,
                                                       time_threshold_seconds=600)  # 10 minutes
        
        # Should trigger based on time (6 minutes > 5 minutes threshold)
        assert EventAnalyzer.should_trigger_summary(
            self.events, 
            user_message_threshold=10,
            time_threshold_seconds=300  # 5 minutes
        )
    
    def test_should_trigger_memory_update(self):
        """Test memory update triggering."""
        # Currently has 1 tool call, should not trigger (threshold is 3)
        assert not EventAnalyzer.should_trigger_memory_update(self.events, tool_call_threshold=3)
        
        # Add more tool calls
        for i in range(2):
            self.events.append(OrchestratorEvent(
                event_type=EventType.TOOL_CALL,
                timestamp=datetime.now() - timedelta(minutes=2-i)
            ))
        
        # Now should trigger with 3 tool calls
        assert EventAnalyzer.should_trigger_memory_update(self.events, tool_call_threshold=3)
        
        # Test agent call threshold
        self.events.append(OrchestratorEvent(
            event_type=EventType.AGENT_CALL,
            timestamp=datetime.now() - timedelta(minutes=1)
        ))
        self.events.append(OrchestratorEvent(
            event_type=EventType.AGENT_CALL,
            timestamp=datetime.now()
        ))
        
        assert EventAnalyzer.should_trigger_memory_update(self.events, agent_call_threshold=2)
    
    def test_calculate_total_cost(self):
        """Test total cost calculation."""
        events = [
            OrchestratorEvent(event_type=EventType.AI_RESPONSE, cost_estimate=0.001),
            OrchestratorEvent(event_type=EventType.AI_RESPONSE, cost_estimate=0.002),
            OrchestratorEvent(event_type=EventType.TOKEN_USAGE, cost_estimate=0.0005),
        ]
        
        assert EventAnalyzer.calculate_total_cost(events) == 0.0035
    
    def test_calculate_total_tokens(self):
        """Test total token calculation."""
        events = [
            OrchestratorEvent(event_type=EventType.AI_RESPONSE, token_count=100),
            OrchestratorEvent(event_type=EventType.AI_RESPONSE, token_count=200),
            OrchestratorEvent(event_type=EventType.TOOL_CALL, token_count=None),
        ]
        
        assert EventAnalyzer.calculate_total_tokens(events) == 300
    
    def test_get_event_summary(self):
        """Test event summary generation."""
        summary = EventAnalyzer.get_event_summary(self.events)
        
        assert summary["total_events"] == len(self.events)
        assert summary["event_counts"]["user_message"] == 3
        assert summary["event_counts"]["tool_call"] == 1
        assert summary["event_counts"]["ai_response"] == 1
        assert summary["total_cost"] == 0.0015
        assert summary["total_tokens"] == 150
        assert summary["duration_seconds"] > 0
        assert summary["first_event"] is not None
        assert summary["last_event"] is not None


class TestEventIntegration:
    """Test event system integration scenarios."""
    
    def test_conversation_flow_events(self):
        """Test a typical conversation flow."""
        events = []
        
        # User asks a question
        events.append(create_user_message_event("Get all accounts for Acme Corp", 1))
        
        # AI decides to call a tool
        events.append(create_tool_call_event(
            "salesforce_agent",
            {"instruction": "get all accounts for Acme Corp"},
            2
        ))
        
        # AI responds with results
        events.append(create_ai_response_event(
            "I found 3 accounts for Acme Corp...",
            3,
            250
        ))
        
        # Verify event sequence
        assert len(events) == 3
        assert events[0].event_type == EventType.USER_MESSAGE
        assert events[1].event_type == EventType.TOOL_CALL
        assert events[2].event_type == EventType.AI_RESPONSE
        
        # Check if memory update should trigger
        assert not EventAnalyzer.should_trigger_memory_update(
            events, 
            tool_call_threshold=2  # Only 1 tool call so far
        )
    
    def test_background_task_events(self):
        """Test background task triggering and completion."""
        events = []
        
        # Simulate conversation with enough user messages
        for i in range(5):
            events.append(OrchestratorEvent(
                event_type=EventType.USER_MESSAGE,
                timestamp=datetime.now() - timedelta(minutes=10-i*2)
            ))
            events.append(OrchestratorEvent(
                event_type=EventType.AI_RESPONSE,
                timestamp=datetime.now() - timedelta(minutes=9-i*2)
            ))
        
        # Should trigger summary
        assert EventAnalyzer.should_trigger_summary(events, user_message_threshold=5)
        
        # Add summary triggered event
        events.append(create_summary_triggered_event(10, "User message threshold reached"))
        
        # Simulate summary completion
        events.append(OrchestratorEvent(
            event_type=EventType.SUMMARY_COMPLETED,
            details={"messages_preserved": 3, "messages_deleted": 7}
        ))
        
        # Verify summary events
        summary_events = [e for e in events if e.event_type in (EventType.SUMMARY_TRIGGERED, EventType.SUMMARY_COMPLETED)]
        assert len(summary_events) == 2
        assert summary_events[1].details["messages_deleted"] == 7


if __name__ == "__main__":
    pytest.main([__file__, "-v"])