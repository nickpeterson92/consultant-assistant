"""
End-to-end tests for system resilience and error recovery.

Tests cover:
- Agent failure recovery
- Partial success handling
- Circuit breaker behavior
- Graceful degradation
- State consistency during failures
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
import aiohttp
from aioresponses import aioresponses

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from src.orchestrator.main import build_orchestrator_graph
from src.a2a.circuit_breaker import CircuitBreakerState


@pytest.mark.e2e
class TestResilienceE2E:
    """Test system resilience in end-to-end scenarios."""
    
    @pytest.fixture
    async def system(self, memory_store):
        """Set up system for resilience testing."""
        with patch('src.orchestrator.main.memory_store', memory_store):
            graph = build_orchestrator_graph()
        
        config = {
            "configurable": {
                "user_id": "resilience-test-user",
                "thread_id": "resilience-test-thread"
            },
            "recursion_limit": 10
        }
        
        return graph, config, memory_store
    
    @pytest.mark.asyncio
    async def test_agent_failure_recovery(self, system):
        """Test system behavior when Salesforce agent fails and recovers."""
        graph, config, memory_store = system
        
        # LLM responses
        llm_responses = [
            # First attempt - agent will fail
            AIMessage(
                content="",
                tool_calls=[{
                    "id": "call_1",
                    "name": "SalesforceAgentTool",
                    "args": {"instruction": "Get all accounts", "context": {}}
                }]
            ),
            AIMessage(content="I apologize, but I'm having trouble connecting to Salesforce right now. The service appears to be unavailable. Please try again in a moment."),
            
            # Second attempt - agent recovered
            AIMessage(
                content="",
                tool_calls=[{
                    "id": "call_2",
                    "name": "SalesforceAgentTool",
                    "args": {"instruction": "Get all accounts", "context": {}}
                }]
            ),
            AIMessage(content="I successfully retrieved the accounts. Here are 3 accounts in your Salesforce: Acme Corp, TechCo, and GlobalTrade Inc.")
        ]
        
        mock_llm = AsyncMock()
        mock_llm.invoke = AsyncMock(side_effect=llm_responses)
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        
        with patch('src.orchestrator.main.create_azure_openai_chat', return_value=mock_llm):
            with aioresponses() as m:
                base_url = "http://localhost:8001"
                
                # First request - agent is down
                m.get(f"{base_url}/a2a/agent-card", status=503)  # Service unavailable
                m.post(f"{base_url}/a2a", status=503)
                
                # Second request - agent recovered
                m.get(f"{base_url}/a2a/agent-card", payload={
                    "name": "salesforce-agent",
                    "capabilities": ["salesforce_operations"]
                })
                m.post(f"{base_url}/a2a", payload={
                    "jsonrpc": "2.0",
                    "result": {
                        "artifacts": [{
                            "id": "sf-accounts",
                            "content": json.dumps({
                                "success": True,
                                "records": [
                                    {"Id": "001XX001", "Name": "Acme Corp"},
                                    {"Id": "001XX002", "Name": "TechCo"},
                                    {"Id": "001XX003", "Name": "GlobalTrade Inc"}
                                ]
                            }),
                            "content_type": "application/json"
                        }],
                        "status": "completed"
                    },
                    "id": "2"
                })
                
                # First attempt - should fail gracefully
                state1 = {
                    "messages": [HumanMessage(content="Get all accounts")],
                    "summary": "",
                    "memory": {},
                    "events": []
                }
                
                result1 = await graph.ainvoke(state1, config)
                
                # Should have error message
                error_response = str(result1["messages"][-1].content)
                assert "unavailable" in error_response.lower() or "trouble" in error_response.lower()
                
                # Second attempt - should succeed
                state2 = {
                    "messages": result1["messages"] + [HumanMessage(content="Let me try again - get all accounts")],
                    "summary": result1.get("summary", ""),
                    "memory": result1.get("memory", {}),
                    "events": result1.get("events", [])
                }
                
                result2 = await graph.ainvoke(state2, config)
                
                # Should succeed this time
                success_response = str(result2["messages"][-1].content)
                assert "successfully" in success_response.lower()
                assert "Acme Corp" in success_response
                assert "3 accounts" in success_response
    
    @pytest.mark.asyncio
    async def test_partial_success_handling(self, system):
        """Test handling of partial successes in bulk operations."""
        graph, config, memory_store = system
        
        # Mock response with partial success
        partial_success_response = {
            "jsonrpc": "2.0",
            "result": {
                "artifacts": [{
                    "id": "sf-bulk-create",
                    "content": json.dumps({
                        "success": False,
                        "message": "Partial success: 3 of 5 leads created",
                        "created": [
                            {"id": "00Q001", "name": "John Doe", "email": "john@example.com"},
                            {"id": "00Q002", "name": "Jane Smith", "email": "jane@example.com"},
                            {"id": "00Q003", "name": "Bob Wilson", "email": "bob@example.com"}
                        ],
                        "failed": [
                            {"name": "Invalid Email", "email": "not-an-email", "error": "Invalid email format"},
                            {"name": "", "email": "missing@name.com", "error": "Last name is required"}
                        ],
                        "structured_data": {
                            "leads": [
                                {"id": "00Q001", "name": "John Doe", "email": "john@example.com"},
                                {"id": "00Q002", "name": "Jane Smith", "email": "jane@example.com"},
                                {"id": "00Q003", "name": "Bob Wilson", "email": "bob@example.com"}
                            ]
                        }
                    }),
                    "content_type": "application/json"
                }],
                "status": "completed"
            },
            "id": "1"
        }
        
        llm_responses = [
            AIMessage(
                content="",
                tool_calls=[{
                    "id": "call_1",
                    "name": "SalesforceAgentTool",
                    "args": {
                        "instruction": "Create 5 new leads from the list: John Doe (john@example.com), Jane Smith (jane@example.com), Bob Wilson (bob@example.com), Invalid Email (not-an-email), Missing Name (missing@name.com)",
                        "context": {}
                    }
                }]
            ),
            AIMessage(content="""I attempted to create 5 leads, but encountered some issues:

**Successfully Created (3 leads):**
- John Doe (john@example.com) - ID: 00Q001
- Jane Smith (jane@example.com) - ID: 00Q002
- Bob Wilson (bob@example.com) - ID: 00Q003

**Failed to Create (2 leads):**
- Invalid Email (not-an-email) - Error: Invalid email format
- Missing Name (missing@name.com) - Error: Last name is required

Would you like me to help fix the failed entries?""")
        ]
        
        mock_llm = AsyncMock()
        mock_llm.invoke = AsyncMock(side_effect=llm_responses)
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        
        with patch('src.orchestrator.main.create_azure_openai_chat', return_value=mock_llm):
            with aioresponses() as m:
                base_url = "http://localhost:8001"
                m.get(f"{base_url}/a2a/agent-card", payload={"name": "salesforce-agent", "capabilities": ["salesforce_operations"]}, repeat=True)
                m.post(f"{base_url}/a2a", payload=partial_success_response)
                
                state = {
                    "messages": [HumanMessage(content="Create these 5 new leads: John Doe (john@example.com), Jane Smith (jane@example.com), Bob Wilson (bob@example.com), Invalid Email (not-an-email), Missing Name (missing@name.com)")],
                    "summary": "",
                    "memory": {},
                    "events": []
                }
                
                result = await graph.ainvoke(state, config)
                
                # Verify partial success is communicated clearly
                response = str(result["messages"][-1].content)
                assert "3 leads" in response or "Successfully Created" in response
                assert "2 leads" in response or "Failed" in response
                assert "Invalid email format" in response
                assert "Last name is required" in response
                
                # Verify only successful leads are in memory
                await asyncio.sleep(0.1)  # Let memory extraction complete
                namespace = ("memory", "resilience-test-user")
                stored_memory = await memory_store.aget(namespace, "SimpleMemory")
                
                if stored_memory and "leads" in stored_memory:
                    leads = stored_memory["leads"]
                    assert len(leads) == 3  # Only successful ones
                    lead_emails = [lead.get("email") for lead in leads]
                    assert "john@example.com" in lead_emails
                    assert "not-an-email" not in lead_emails
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_behavior(self, system):
        """Test circuit breaker protecting against repeated failures."""
        graph, config, memory_store = system
        
        # Simulate multiple failures that should trigger circuit breaker
        failure_count = 0
        
        llm_responses = []
        for i in range(6):  # More than circuit breaker threshold
            llm_responses.extend([
                AIMessage(
                    content="",
                    tool_calls=[{
                        "id": f"call_{i}",
                        "name": "SalesforceAgentTool",
                        "args": {"instruction": f"Attempt {i+1}", "context": {}}
                    }]
                ),
                AIMessage(content=f"I'm having trouble with request {i+1}. The service seems to be experiencing issues.")
            ])
        
        mock_llm = AsyncMock()
        mock_llm.invoke = AsyncMock(side_effect=llm_responses)
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        
        with patch('src.orchestrator.main.create_azure_openai_chat', return_value=mock_llm):
            with aioresponses() as m:
                base_url = "http://localhost:8001"
                
                # All requests fail
                m.get(f"{base_url}/a2a/agent-card", status=500, repeat=True)
                m.post(f"{base_url}/a2a", status=500, repeat=True)
                
                # Make multiple requests
                state = {
                    "messages": [HumanMessage(content="Try to get data")],
                    "summary": "",
                    "memory": {},
                    "events": []
                }
                
                for i in range(3):
                    result = await graph.ainvoke(state, config)
                    state["messages"] = result["messages"] + [HumanMessage(content=f"Try again (attempt {i+2})")]
                
                # After multiple failures, circuit breaker should be mentioned or behavior should change
                final_response = str(result["messages"][-1].content)
                assert "service" in final_response.lower() or "issue" in final_response.lower()
    
    @pytest.mark.asyncio
    async def test_state_consistency_during_failure(self, system):
        """Test that state remains consistent even during failures."""
        graph, config, memory_store = system
        
        # Pre-populate memory with some data
        namespace = ("memory", "resilience-test-user")
        initial_memory = {
            "accounts": [
                {"id": "001", "name": "Existing Corp"},
                {"id": "002", "name": "Current Co"}
            ],
            "contacts": [
                {"id": "003", "name": "Alice", "email": "alice@existing.com", "account_id": "001"}
            ]
        }
        await memory_store.aput(namespace, "SimpleMemory", initial_memory)
        
        # Response that includes new data but will partially fail
        mixed_response = {
            "jsonrpc": "2.0",
            "result": {
                "artifacts": [{
                    "id": "sf-mixed",
                    "content": json.dumps({
                        "success": True,
                        "message": "Retrieved some data before connection issues",
                        "structured_data": {
                            "accounts": [
                                {"id": "004", "name": "New Corp"}  # New account
                            ]
                        }
                    }),
                    "content_type": "application/json"
                }],
                "status": "completed"
            },
            "id": "1"
        }
        
        llm_responses = [
            AIMessage(
                content="",
                tool_calls=[{
                    "id": "call_1",
                    "name": "SalesforceAgentTool",
                    "args": {"instruction": "Get new accounts and update existing", "context": {}}
                }]
            ),
            AIMessage(content="I retrieved some new data but encountered connection issues. I found one new account: New Corp."),
            
            # Verify memory query
            AIMessage(content=f"Looking at your stored data, you have {len(initial_memory['accounts'])} existing accounts: Existing Corp and Current Co, plus the new account New Corp I just found.")
        ]
        
        mock_llm = AsyncMock()
        mock_llm.invoke = AsyncMock(side_effect=llm_responses)
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        
        with patch('src.orchestrator.main.create_azure_openai_chat', return_value=mock_llm):
            with aioresponses() as m:
                base_url = "http://localhost:8001"
                m.get(f"{base_url}/a2a/agent-card", payload={"name": "salesforce-agent", "capabilities": ["salesforce_operations"]}, repeat=True)
                m.post(f"{base_url}/a2a", payload=mixed_response)
                
                # First request - partial success
                state1 = {
                    "messages": [HumanMessage(content="Get new accounts and update existing")],
                    "summary": "",
                    "memory": {"SimpleMemory": initial_memory},
                    "events": []
                }
                
                result1 = await graph.ainvoke(state1, config)
                
                # Verify partial data was communicated
                assert "New Corp" in str(result1["messages"][-1].content)
                assert "connection issues" in str(result1["messages"][-1].content).lower()
                
                # Second request - verify memory consistency
                state2 = {
                    "messages": result1["messages"] + [HumanMessage(content="How many accounts do I have in total now?")],
                    "summary": result1.get("summary", ""),
                    "memory": result1.get("memory", {}),
                    "events": result1.get("events", [])
                }
                
                result2 = await graph.ainvoke(state2, config)
                
                # Should report consistent state
                response = str(result2["messages"][-1].content)
                assert "Existing Corp" in response
                assert "Current Co" in response
                assert "New Corp" in response
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_timeout_handling(self, system):
        """Test system behavior with slow/timing out requests."""
        graph, config, memory_store = system
        
        llm_responses = [
            AIMessage(
                content="",
                tool_calls=[{
                    "id": "call_1",
                    "name": "SalesforceAgentTool",
                    "args": {"instruction": "Run complex report", "context": {}}
                }]
            ),
            AIMessage(content="The request is taking longer than expected. Large reports can take some time to generate. Would you like me to try a simpler query instead?")
        ]
        
        mock_llm = AsyncMock()
        mock_llm.invoke = AsyncMock(side_effect=llm_responses)
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        
        async def slow_response(*args, **kwargs):
            # Simulate slow response
            await asyncio.sleep(5)  # Longer than typical timeout
            return aiohttp.ClientTimeout(total=1)
        
        with patch('src.orchestrator.main.create_azure_openai_chat', return_value=mock_llm):
            with aioresponses() as m:
                base_url = "http://localhost:8001"
                m.get(f"{base_url}/a2a/agent-card", payload={"name": "salesforce-agent", "capabilities": ["salesforce_operations"]})
                
                # Set up timeout
                m.post(f"{base_url}/a2a", exception=asyncio.TimeoutError())
                
                state = {
                    "messages": [HumanMessage(content="Run a complex analysis report on all accounts")],
                    "summary": "",
                    "memory": {},
                    "events": []
                }
                
                result = await graph.ainvoke(state, config)
                
                # Should handle timeout gracefully
                response = str(result["messages"][-1].content)
                assert "longer than expected" in response.lower() or "timeout" in response.lower()
                assert "simpler" in response.lower() or "try" in response.lower()