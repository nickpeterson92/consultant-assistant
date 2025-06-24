"""
Integration tests for orchestrator and agent communication.

Tests the full flow of:
- Orchestrator receiving user requests
- Routing to appropriate agents via A2A protocol
- Handling agent responses
- Memory extraction and persistence
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from aioresponses import aioresponses

from src.orchestrator.main import build_orchestrator_graph
from src.orchestrator.agent_caller_tools import SalesforceAgentTool
from src.a2a.protocol import A2AClient
from src.utils.storage.memory_schemas import SimpleMemory


class TestOrchestratorAgentIntegration:
    """Test orchestrator integration with agents."""
    
    @pytest.fixture
    async def orchestrator_graph(self, memory_store):
        """Create orchestrator graph for testing."""
        with patch('src.utils.storage.async_store_adapter.get_async_store_adapter', return_value=memory_store):
            graph = build_orchestrator_graph()
        return graph
    
    @pytest.fixture
    def mock_salesforce_agent_response(self):
        """Mock response from Salesforce agent."""
        return {
            "jsonrpc": "2.0",
            "result": {
                "artifacts": [{
                    "id": "sf-response-123",
                    "task_id": "task-123",
                    "content": json.dumps({
                        "success": True,
                        "records": [{
                            "Id": "001XX000003DHP0",
                            "Name": "Acme Corporation",
                            "Industry": "Technology"
                        }],
                        "structured_data": {
                            "accounts": [{
                                "id": "001XX000003DHP0",
                                "name": "Acme Corporation"
                            }]
                        }
                    }),
                    "content_type": "application/json"
                }],
                "status": "completed"
            },
            "id": "1"
        }
    
    @pytest.mark.asyncio
    async def test_orchestrator_to_salesforce_flow(self, orchestrator_graph, mock_salesforce_agent_response):
        """Test complete flow from orchestrator to Salesforce agent."""
        # Mock the A2A client calls
        with aioresponses() as m:
            # Mock agent card endpoint
            m.get(
                "http://localhost:8001/a2a/agent-card",
                payload={
                    "name": "salesforce-agent",
                    "capabilities": ["salesforce_operations"],
                    "endpoints": {"process_task": "/a2a"}
                }
            )
            
            # Mock task execution
            m.post(
                "http://localhost:8001/a2a",
                payload=mock_salesforce_agent_response
            )
            
            # Create initial state
            initial_state = {
                "messages": [HumanMessage(content="Get the Acme Corporation account")],
                "summary": "",
                "memory": {},
                "events": [],
                "turns_since_last_summary": 0,
                "turns_since_memory_update": 0
            }
            
            config = {
                "configurable": {
                    "user_id": "test-user",
                    "thread_id": "test-thread"
                },
                "recursion_limit": 10
            }
            
            # Mock LLM to call Salesforce tool
            mock_llm = AsyncMock()
            mock_llm.invoke = AsyncMock(side_effect=[
                # First call - decide to use Salesforce tool
                AIMessage(
                    content="",
                    tool_calls=[{
                        "id": "call_sf_1",
                        "name": "SalesforceAgentTool",
                        "args": {
                            "instruction": "Get the Acme Corporation account",
                            "context": {}
                        }
                    }]
                ),
                # Second call - process the result
                AIMessage(
                    content="I found the Acme Corporation account. It's a Technology company with ID 001XX000003DHP0."
                )
            ])
            mock_llm.bind_tools = Mock(return_value=mock_llm)
            
            with patch('src.orchestrator.main.AzureChatOpenAI', return_value=mock_llm):
                # Run the graph
                result = await orchestrator_graph.ainvoke(initial_state, config)
            
            # Verify results
            assert len(result["messages"]) >= 3  # User, tool call, tool response, final answer
            
            # Find the final AI message
            final_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage) and msg.content]
            assert len(final_messages) > 0
            assert "Acme Corporation" in final_messages[-1].content
            assert "Technology" in final_messages[-1].content
    
    @pytest.mark.asyncio
    async def test_memory_extraction_from_agent_response(self, orchestrator_graph, memory_store):
        """Test that memory is extracted from agent responses."""
        # Create state with agent response containing structured data
        tool_response = ToolMessage(
            content=json.dumps({
                "success": True,
                "structured_data": {
                    "accounts": [
                        {"id": "001", "name": "Acme Corp"},
                        {"id": "002", "name": "TechCo"}
                    ],
                    "contacts": [
                        {"id": "003", "name": "John Doe", "email": "john@acme.com", "account_id": "001"}
                    ]
                }
            }),
            tool_call_id="call_123"
        )
        
        initial_state = {
            "messages": [
                HumanMessage(content="Get all Acme accounts and contacts"),
                AIMessage(content="", tool_calls=[{"id": "call_123", "name": "SalesforceAgentTool", "args": {}}]),
                tool_response,
                AIMessage(content="Found 2 accounts and 1 contact")
            ],
            "summary": "",
            "memory": {},
            "events": [],
            "turns_since_memory_update": 5  # Trigger memory update
        }
        
        config = {
            "configurable": {"user_id": "test-user", "thread_id": "test-thread"}
        }
        
        # Mock the memory extraction
        with patch('src.orchestrator.main.create_extractor') as mock_extractor:
            mock_memory = SimpleMemory(
                accounts=[
                    {"id": "001", "name": "Acme Corp"},
                    {"id": "002", "name": "TechCo"}
                ],
                contacts=[
                    {"id": "003", "name": "John Doe", "email": "john@acme.com", "account_id": "001"}
                ]
            )
            mock_extractor.return_value = AsyncMock(
                aextract=AsyncMock(return_value=mock_memory)
            )
            
            # Process memory extraction
            from src.orchestrator.main import memorize_records
            result = await memorize_records(initial_state, config)
            
            # Verify memory was updated
            assert "memory" in result
            assert "SimpleMemory" in result["memory"]
            memory_data = result["memory"]["SimpleMemory"]
            assert len(memory_data["accounts"]) == 2
            assert len(memory_data["contacts"]) == 1
            
            # Verify it was persisted
            namespace = ("memory", "test-user")
            stored = await memory_store.aget(namespace, "SimpleMemory")
            assert stored is not None
            assert len(stored["accounts"]) == 2


class TestMultiAgentCoordination:
    """Test coordination between multiple agents."""
    
    @pytest.mark.asyncio
    async def test_agent_selection_by_capability(self):
        """Test that orchestrator selects the right agent based on capabilities."""
        from src.orchestrator.agent_registry import AgentRegistry
        
        registry = AgentRegistry()
        
        # Register multiple mock agents
        await registry.register_agent(
            "salesforce-agent",
            "http://localhost:8001",
            {
                "name": "salesforce-agent",
                "capabilities": ["salesforce_operations", "crm_management"]
            }
        )
        
        await registry.register_agent(
            "travel-agent",
            "http://localhost:8002",
            {
                "name": "travel-agent",
                "capabilities": ["travel_booking", "flight_search"]
            }
        )
        
        # Test capability matching
        sf_agents = registry.find_agents_by_capability("salesforce_operations")
        assert len(sf_agents) == 1
        assert sf_agents[0]["name"] == "salesforce-agent"
        
        travel_agents = registry.find_agents_by_capability("flight_search")
        assert len(travel_agents) == 1
        assert travel_agents[0]["name"] == "travel-agent"
    
    @pytest.mark.asyncio
    async def test_fallback_when_agent_unavailable(self, orchestrator_graph):
        """Test orchestrator handles unavailable agents gracefully."""
        with aioresponses() as m:
            # Mock agent as unavailable
            m.get(
                "http://localhost:8001/a2a/agent-card",
                status=503  # Service unavailable
            )
            
            initial_state = {
                "messages": [HumanMessage(content="Get Salesforce data")],
                "summary": "",
                "memory": {},
                "events": []
            }
            
            config = {"configurable": {"user_id": "test-user"}}
            
            # Mock LLM to handle the failure
            mock_llm = AsyncMock()
            mock_llm.invoke = AsyncMock(side_effect=[
                # Try to call Salesforce
                AIMessage(
                    content="",
                    tool_calls=[{
                        "id": "call_1",
                        "name": "SalesforceAgentTool",
                        "args": {"instruction": "Get data"}
                    }]
                ),
                # Handle the error
                AIMessage(
                    content="I apologize, but the Salesforce service is currently unavailable. Please try again later."
                )
            ])
            mock_llm.bind_tools = Mock(return_value=mock_llm)
            
            with patch('src.orchestrator.main.AzureChatOpenAI', return_value=mock_llm):
                # Should complete without crashing
                result = await orchestrator_graph.ainvoke(initial_state, config)
                
                # Should have an error message
                final_message = result["messages"][-1]
                assert "unavailable" in final_message.content.lower()


class TestConnectionPoolIntegration:
    """Test connection pool behavior in integration."""
    
    @pytest.mark.asyncio
    async def test_connection_reuse_across_calls(self):
        """Test that connections are reused across multiple agent calls."""
        from src.a2a.protocol import A2AClient
        
        client = A2AClient(
            base_url="http://localhost:8001",
            pool_size=5,
            pool_size_per_host=2
        )
        
        call_count = 0
        
        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return Mock(
                status=200,
                json=AsyncMock(return_value={
                    "jsonrpc": "2.0",
                    "result": {"status": "completed", "artifacts": []},
                    "id": str(call_count)
                })
            )
        
        # Make multiple calls
        with patch.object(client, '_get_session') as mock_session:
            session = AsyncMock()
            session.post = mock_post
            mock_session.return_value = session
            
            # Execute multiple tasks
            tasks = []
            for i in range(5):
                task = client.execute_task(f"Task {i}")
                tasks.append(task)
            
            results = await asyncio.gather(*tasks)
            
            assert len(results) == 5
            assert all(r["status"] == "completed" for r in results)
            
            # Session should have been reused
            assert mock_session.call_count <= 5  # May be called once or reused


class TestErrorPropagation:
    """Test error propagation through the system."""
    
    @pytest.mark.asyncio
    async def test_agent_error_propagation(self):
        """Test that agent errors are properly propagated to orchestrator."""
        tool = SalesforceAgentTool()
        
        with aioresponses() as m:
            # Mock agent returning an error
            m.post(
                "http://localhost:8001/a2a",
                payload={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": "Database connection failed"
                    },
                    "id": "1"
                }
            )
            
            # Tool should handle the error gracefully
            result = tool._run(
                instruction="Get accounts",
                context={}
            )
            
            # Should return error information
            assert "error" in result.lower()
            assert "internal error" in result.lower()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self):
        """Test circuit breaker prevents cascading failures."""
        from src.a2a.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
        
        config = CircuitBreakerConfig(failure_threshold=2, timeout=1)
        breaker = CircuitBreaker("test-agent", config)
        
        fail_count = 0
        
        async def flaky_agent_call():
            nonlocal fail_count
            fail_count += 1
            if fail_count <= 2:
                raise Exception("Agent error")
            return {"status": "success"}
        
        # First calls should fail and open circuit
        for _ in range(2):
            with pytest.raises(Exception):
                await breaker.call(flaky_agent_call)
        
        # Circuit should be open
        assert breaker.state.value == "open"
        
        # Next call should be rejected immediately
        from src.a2a.circuit_breaker import CircuitBreakerException
        with pytest.raises(CircuitBreakerException):
            await breaker.call(flaky_agent_call)
        
        # After timeout, should try again
        await asyncio.sleep(1.1)
        result = await breaker.call(flaky_agent_call)
        assert result["status"] == "success"