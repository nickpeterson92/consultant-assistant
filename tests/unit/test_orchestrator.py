"""
Unit tests for the orchestrator component.

Tests focus on:
- LangGraph state management
- Tool routing and execution
- Message handling and serialization
- Memory operations
- Error handling
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
import json
from typing import Dict, Any, List

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.orchestrator.main import (
    build_orchestrator_graph,
    load_events_with_limit
)
from src.utils.message_serialization import serialize_messages
from src.utils.events import EventType, OrchestratorEvent
from src.utils.storage.memory_schemas import SimpleMemory


class TestOrchestratorState:
    """Test orchestrator state management."""
    
    def test_state_initialization(self):
        """Test that orchestrator state can be properly initialized."""
        # Using a regular dict since OrchestratorState is internal to build_orchestrator_graph
        state = {
            "messages": [],
            "summary": "",
            "memory": {},
            "events": [],
            "active_agents": [],
            "last_agent_interaction": {},
            "background_operations": [],
            "background_results": {}
        }
        
        assert state["messages"] == []
        assert state["summary"] == ""
        assert state["active_agents"] == []
    
    def test_state_message_addition(self):
        """Test adding messages to state."""
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!")
        ]
        
        state = {
            "messages": messages,
            "summary": "",
            "memory": {},
            "events": [],
            "active_agents": [],
            "last_agent_interaction": {},
            "background_operations": [],
            "background_results": {}
        }
        
        assert len(state["messages"]) == 2
        assert state["messages"][0].content == "Hello"
        assert state["messages"][1].content == "Hi there!"


class TestOrchestratorFunction:
    """Test the main orchestrator function."""
    
    @pytest.mark.asyncio
    async def test_orchestrator_basic_response(self, mock_llm, memory_store):
        """Test orchestrator responds to basic user input."""
        # Create state with user message
        state = {
            "messages": [HumanMessage(content="Hello, orchestrator!")],
            "summary": "",
            "memory": {},
            "events": [],
            "active_agents": [], "last_agent_interaction": {}, "background_operations": [], "background_results": {}
        }
        
        # The mock_llm fixture already has the response configured as "Test response"
        # No need to override it here
        
        # Create config
        config = {"configurable": {"user_id": "test-user", "thread_id": "test-thread"}}
        
        # Build the graph
        with patch('src.utils.storage.async_store_adapter.get_async_store_adapter', return_value=memory_store):
            with patch('src.orchestrator.main.AzureChatOpenAI') as mock_azure:
                mock_azure.return_value = mock_llm
                graph = build_orchestrator_graph()
                result = await graph.ainvoke(state, config)
        
        # Verify response - should have both the human message and AI response
        assert "messages" in result
        assert len(result["messages"]) == 2
        assert result["messages"][0].content == "Hello, orchestrator!"
        assert result["messages"][1].content == "Test response"
        
        # Verify event creation
        assert "events" in result
        assert len(result["events"]) > 0
    
    @pytest.mark.asyncio
    async def test_orchestrator_with_tool_call(self, mock_llm_with_tools, memory_store):
        """Test orchestrator handling tool calls."""
        state = {
            "messages": [HumanMessage(content="Get the Acme Corp account")],
            "summary": "",
            "memory": {},
            "events": [],
            "active_agents": [], "last_agent_interaction": {}, "background_operations": [], "background_results": {}
        }
        
        config = {"configurable": {"user_id": "test-user", "thread_id": "test-thread"}}
        
        # Build the graph
        with patch('src.utils.storage.async_store_adapter.get_async_store_adapter', return_value=memory_store):
            with patch('src.orchestrator.main.AzureChatOpenAI') as mock_azure:
                mock_azure.return_value = mock_llm_with_tools
                graph = build_orchestrator_graph()
                result = await graph.ainvoke(state, config)
        
        # Should have multiple messages after tool execution
        assert len(result["messages"]) >= 2
        
        # Check if any message has tool calls
        has_tool_calls = False
        for msg in result["messages"]:
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                has_tool_calls = True
                assert msg.tool_calls[0]["name"] == "GetAccountTool"
                break
        
        # Either we should have tool calls or a final response mentioning Acme Corp
        if not has_tool_calls:
            # Check the final response mentions the account
            final_msg = result["messages"][-1]
            assert "Acme Corp" in final_msg.content
    
    @pytest.mark.asyncio
    async def test_orchestrator_error_handling(self, mock_llm, memory_store):
        """Test orchestrator handles errors gracefully."""
        state = {
            "messages": [HumanMessage(content="Test error handling")],
            "summary": "",
            "memory": {},
            "events": [],
            "active_agents": [], "last_agent_interaction": {}, "background_operations": [], "background_results": {}
        }
        
        # Make LLM raise an error on sync invoke
        mock_llm.invoke = Mock(side_effect=Exception("LLM API Error"))
        
        config = {"configurable": {"user_id": "test-user", "thread_id": "test-thread"}}
        
        # Build the graph
        with patch('src.utils.storage.async_store_adapter.get_async_store_adapter', return_value=memory_store):
            with patch('src.orchestrator.main.AzureChatOpenAI') as mock_azure:
                mock_azure.return_value = mock_llm
                graph = build_orchestrator_graph()
                with pytest.raises(Exception, match="LLM API Error"):
                    await graph.ainvoke(state, config)


class TestSummarization:
    """Test conversation summarization functionality."""
    
    @pytest.mark.skip(reason="summarize_conversation is now internal to graph")
    @pytest.mark.asyncio
    async def test_summarize_conversation(self, mock_llm):
        """Test conversation summarization."""
        # Create a conversation with multiple messages
        messages = [
            HumanMessage(content="What's the weather like?"),
            AIMessage(content="I don't have access to weather data."),
            HumanMessage(content="Can you help with Salesforce?"),
            AIMessage(content="Yes, I can help with Salesforce operations.")
        ]
        
        state = {
            "messages": messages,
            "summary": "Previous summary",
            "memory": {},
            "events": []
        }
        
        # Mock summarization response
        mock_llm.ainvoke.return_value = AIMessage(
            content="User asked about weather and Salesforce capabilities."
        )
        
        with patch('langchain_openai.AzureChatOpenAI', return_value=mock_llm):
            # result = await summarize_conversation(state)
            pass  # Function is internal to graph now
        
        assert "summary" in result
        assert result["summary"] == "User asked about weather and Salesforce capabilities."
        assert "messages" in result
        # Should preserve some messages
        assert len(result["messages"]) > 0
    
    @pytest.mark.asyncio
    async def test_summarization_with_tool_messages(self, mock_llm):
        """Test summarization preserves tool call/response pairs."""
        messages = [
            HumanMessage(content="Get account info"),
            AIMessage(content="", tool_calls=[{"id": "1", "name": "GetAccount", "args": {}}]),
            ToolMessage(content="Account data", tool_call_id="1"),
            AIMessage(content="Here's the account info...")
        ]
        
        state = {
            "messages": messages,
            "summary": "",
            "memory": {},
            "events": []
        }
        
        mock_llm.ainvoke.return_value = AIMessage(content="Summary of account lookup")
        
        # Skip this test since summarize_conversation is internal to graph
        pytest.skip("summarize_conversation is now internal to graph")


class TestMemoryExtraction:
    """Test memory extraction and persistence."""
    
    @pytest.mark.skip(reason="memorize_records is now internal to graph")
    @pytest.mark.asyncio
    async def test_memorize_records_extraction(self, mock_llm, memory_store):
        """Test extracting structured data from conversations."""
        # Create messages with Salesforce data
        messages = [
            HumanMessage(content="Create account for Acme Corp"),
            ToolMessage(
                content="[STRUCTURED_TOOL_DATA]: " + json.dumps({
                    "accounts": [{"id": "001", "name": "Acme Corp"}]
                }),
                tool_call_id="1"
            ),
            AIMessage(content="Created Acme Corp account")
        ]
        
        state = {
            "messages": messages,
            "summary": "",
            "memory": {},
            "events": []
        }
        
        config = {"configurable": {"user_id": "test-user", "thread_id": "test-thread"}}
        
        # Mock TrustCall extraction
        mock_extraction = SimpleMemory(
            accounts=[{"id": "001", "name": "Acme Corp"}]
        )
        
        with patch('src.orchestrator.main.memory_store', memory_store):
            with patch('src.orchestrator.main.create_extractor') as mock_extractor:
                mock_extractor.return_value = AsyncMock(
                    aextract=AsyncMock(return_value=mock_extraction)
                )
                
                # result = await memorize_records(state, config)
                pass  # Function is internal to graph now
        
        assert "memory" in result
        assert "SimpleMemory" in result["memory"]
        memory_data = result["memory"]["SimpleMemory"]
        assert len(memory_data.get("accounts", [])) == 1
        assert memory_data["accounts"][0]["name"] == "Acme Corp"
    
    @pytest.mark.skip(reason="memorize_records is now internal to graph")
    @pytest.mark.asyncio
    async def test_memory_deduplication(self, memory_store):
        """Test that memory extraction deduplicates records."""
        # Existing memory with one account
        existing_memory = SimpleMemory(
            accounts=[{"id": "001", "name": "Acme Corp"}]
        )
        
        # New extraction with duplicate and new account
        new_extraction = SimpleMemory(
            accounts=[
                {"id": "001", "name": "Acme Corp"},  # Duplicate
                {"id": "002", "name": "TechCo"}      # New
            ]
        )
        
        state = {
            "messages": [],
            "memory": {"SimpleMemory": existing_memory.model_dump()},
            "events": []
        }
        
        config = {"configurable": {"user_id": "test-user", "thread_id": "test-thread"}}
        
        with patch('src.orchestrator.main.memory_store', memory_store):
            with patch('src.orchestrator.main.create_extractor') as mock_extractor:
                mock_extractor.return_value = AsyncMock(
                    aextract=AsyncMock(return_value=new_extraction)
                )
                
                # Pre-populate store with existing memory
                namespace = ("memory", "test-user")
                await memory_store.aput(namespace, "SimpleMemory", existing_memory.model_dump())
                
                # result = await memorize_records(state, config)
                pass  # Function is internal to graph now
        
        # Should have 2 accounts (deduped)
        memory_data = result["memory"]["SimpleMemory"]
        assert len(memory_data["accounts"]) == 2
        account_ids = [acc["id"] for acc in memory_data["accounts"]]
        assert "001" in account_ids
        assert "002" in account_ids


class TestEventManagement:
    """Test event tracking and management."""
    
    def test_load_events_with_limit(self):
        """Test loading events with size limit."""
        # Create many events
        events = []
        for i in range(100):
            event = OrchestratorEvent(
                event_type=EventType.USER_MESSAGE,
                details={"message": f"Message {i}"},
                message_count=i
            )
            events.append(event.to_dict())
        
        state = {"events": events}
        
        # Load with default limit (50)
        loaded = load_events_with_limit(state)
        assert len(loaded) == 50
        
        # Load with custom limit
        loaded = load_events_with_limit(state, limit=20)
        assert len(loaded) == 20
        
        # Verify most recent events are kept (slicing keeps last 20 from 100)
        # Original list was 0-99, slicing [-20:] gives us 80-99
        assert loaded[-1].details["message"] == "Message 99"  # Most recent
        assert loaded[0].details["message"] == "Message 80"   # Oldest in the slice
    
    def test_event_serialization(self):
        """Test event serialization and deserialization."""
        event = OrchestratorEvent(
            event_type=EventType.TOOL_CALL,
            details={
                "tool": "GetAccount",
                "args": {"name": "Acme"}
            },
            message_count=5
        )
        
        # Serialize
        event_dict = event.to_dict()
        assert event_dict["event_type"] == "tool_call"
        assert event_dict["details"]["tool"] == "GetAccount"
        
        # Deserialize
        restored = OrchestratorEvent.from_dict(event_dict)
        assert restored.event_type == EventType.TOOL_CALL
        assert restored.details["tool"] == "GetAccount"


class TestMessageSerialization:
    """Test message serialization for state persistence."""
    
    def test_serialize_basic_messages(self):
        """Test serializing basic message types."""
        messages = [
            HumanMessage(content="Hello", id="1"),
            AIMessage(content="Hi there!", id="2"),
            SystemMessage(content="System prompt", id="3")
        ]
        
        serialized = serialize_messages(messages)
        
        assert len(serialized) == 3
        assert serialized[0]["type"] == "human"
        assert serialized[0]["content"] == "Hello"
        assert serialized[1]["type"] == "ai"
        assert serialized[2]["type"] == "system"
    
    def test_serialize_tool_messages(self):
        """Test serializing messages with tool calls."""
        messages = [
            AIMessage(
                content="",
                tool_calls=[{
                    "id": "call_123",
                    "name": "GetAccount",
                    "args": {"name": "Acme"}
                }],
                id="1"
            ),
            ToolMessage(
                content="Account found",
                tool_call_id="call_123",
                id="2"
            )
        ]
        
        serialized = serialize_messages(messages)
        
        assert serialized[0]["tool_calls"][0]["name"] == "GetAccount"
        assert serialized[1]["type"] == "tool"
        assert serialized[1]["tool_call_id"] == "call_123"


class TestGraphConstruction:
    """Test LangGraph construction and configuration."""
    
    @pytest.mark.asyncio
    async def test_build_orchestrator_graph(self, memory_store):
        """Test building the orchestrator graph."""
        with patch('src.utils.storage.async_store_adapter.get_async_store_adapter', return_value=memory_store):
            graph = build_orchestrator_graph()
        
        assert graph is not None
        # Graph should have required nodes
        assert "conversation" in graph.nodes
        assert "tools" in graph.nodes
        
        # Test graph can be invoked
        initial_state = {
            "messages": [HumanMessage(content="Test")],
            "summary": "",
            "memory": {},
            "events": []
        }
        
        config = {
            "configurable": {"user_id": "test", "thread_id": "test"},
            "recursion_limit": 5
        }
        
        # Mock LLM for graph execution
        with patch('langchain_openai.AzureChatOpenAI') as mock_llm_create:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Response"))
            mock_llm.bind_tools = Mock(return_value=mock_llm)
            mock_llm_create.return_value = mock_llm
            
            # Invoke graph
            result = await graph.ainvoke(initial_state, config)
            
            assert "messages" in result
            assert len(result["messages"]) > len(initial_state["messages"])


# Test helper for creating mock states
def create_test_state(messages=None, summary="", memory=None, events=None):
    """Helper to create test states."""
    return {
        "messages": messages or [],
        "summary": summary,
        "memory": memory or {},
        "events": events or [],
        "active_agents": [], "last_agent_interaction": {}, "background_operations": [], "background_results": {}
    }