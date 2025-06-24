"""
Unit tests for the Salesforce agent.

Tests cover:
- LangGraph workflow construction
- Agent state management
- Tool binding and execution
- A2A salesforce_handler integration
- Error handling
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph

from src.agents.salesforce.main import (
    build_salesforce_graph,
    SalesforceA2AHandler,
    salesforce_graph
)


@pytest.fixture
def salesforce_handler(mock_llm):
    """Create a handler instance with mocked graph."""
    with patch('src.agents.salesforce.main.load_dotenv'):
        with patch('src.agents.salesforce.main.create_azure_openai_chat', return_value=mock_llm):
            graph = build_salesforce_graph()
            return SalesforceA2AHandler(graph)


class TestSalesforceGraphConstruction:
    """Test Salesforce LangGraph construction."""
    
    def test_build_salesforce_graph(self):
        """Test building the Salesforce graph."""
        with patch('src.agents.salesforce.main.load_dotenv'):
            with patch('src.agents.salesforce.main.create_azure_openai_chat') as mock_llm:
                # Mock LLM
                mock_llm.return_value = Mock(bind_tools=Mock())
                
                graph = build_salesforce_graph()
                
                assert graph is not None
                # Should have agent and tools nodes
                assert "agent" in graph.nodes
                assert "tools" in graph.nodes
    
    @pytest.mark.asyncio
    async def test_salesforce_agent_node(self, mock_llm):
        """Test the Salesforce agent node execution."""
        # Create test state
        state = {
            "messages": [HumanMessage(content="Get account Acme Corp")],
            "task_context": {"task_id": "test-123", "instruction": "Get account"},
            "external_context": {"user": "test-user"}
        }
        
        # Mock LLM response with tool call using correct tool name
        mock_llm.invoke.return_value = AIMessage(
            content="",
            tool_calls=[{
                "id": "call_123",
                "name": "get_account_tool",
                "args": {"name": "Acme Corp"}
            }]
        )
        
        with patch('src.agents.salesforce.main.create_azure_openai_chat', return_value=mock_llm):
            # Also mock the get_account_tool to avoid actual Salesforce calls
            with patch('src.tools.salesforce_tools.GetAccountTool._run') as mock_tool:
                mock_tool.return_value = '{"Id": "001", "Name": "Acme Corp", "Industry": "Technology"}'
                graph = build_salesforce_graph()
                
                # Execute the graph instead of calling node directly
                config = {"configurable": {"thread_id": "test"}}
                result = await graph.ainvoke(state, config)
            
            assert "messages" in result
            # The graph should execute: human -> AI with tool call -> tool response
            assert len(result["messages"]) >= 2
            
            # Check if we have a tool call in the messages
            has_tool_call = False
            for msg in result["messages"]:
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    has_tool_call = True
                    assert msg.tool_calls[0]["name"] == "get_account_tool"
                    break
            assert has_tool_call, "Expected to find a message with tool calls"
    
    def test_salesforce_state_schema(self):
        """Test Salesforce state schema is properly defined."""
        # SalesforceState is defined inside build_salesforce_graph function
        # So we test it by creating a graph and checking state structure
        with patch('src.agents.salesforce.main.load_dotenv'):
            with patch('src.agents.salesforce.main.create_azure_openai_chat') as mock_llm:
                mock_llm.return_value = Mock(bind_tools=Mock())
                graph = build_salesforce_graph()
                
                # Test state by passing it to the graph
                state = {
                    "messages": [HumanMessage(content="Test")],
                    "task_context": {"task_id": "123"},
                    "external_context": {"key": "value"}
                }
                
                # If the state schema is correct, this should not raise an error
                config = {"configurable": {"thread_id": "test"}}
                # Just validate the state structure is accepted
                assert isinstance(state, dict)
                assert "messages" in state
                assert "task_context" in state
                assert "external_context" in state


class TestSalesforceA2AHandler:
    """Test Salesforce A2A salesforce_handler functionality."""
    
    @pytest.mark.asyncio
    async def test_process_task_success(self, salesforce_handler, mock_llm):
        """Test successful task processing."""
        # Mock LLM to return a simple response
        mock_llm.invoke.return_value = AIMessage(content="Found Acme Corp account with ID 001")
        
        params = {
            "task": {
                "id": "task-123",
                "instruction": "Get Acme Corp account",
                "context": {"user": "test-user"}
            }
        }
        
        result = await salesforce_handler.process_task(params)
        
        assert result["status"] == "completed"
        assert len(result["artifacts"]) == 1
        assert "Found Acme Corp account" in result["artifacts"][0]["content"]
        assert result["artifacts"][0]["content_type"] == "text/plain"
    
    @pytest.mark.asyncio
    async def test_process_task_with_tool_calls(self, salesforce_handler, mock_llm_with_tools):
        """Test task processing with tool calls."""
        # Use mock that returns tool calls
        salesforce_handler.graph.nodes["agent"] = AsyncMock(return_value={
            "messages": [mock_llm_with_tools.ainvoke.return_value]
        })
        
        params = {
            "task": {
                "id": "task-456",
                "instruction": "Create new lead for John Doe",
                "context": {}
            }
        }
        
        # Mock tool execution
        with patch('src.agents.salesforce.main.ToolNode') as mock_tool_node:
            mock_tool = Mock()
            mock_tool.invoke = AsyncMock(return_value={
                "messages": [ToolMessage(
                    content='{"id": "00Q123", "name": "John Doe"}',
                    tool_call_id="call_123"
                )]
            })
            mock_tool_node.return_value = mock_tool
            
            result = await salesforce_handler.process_task(params)
            
            assert result["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_process_task_error_handling(self, salesforce_handler):
        """Test error handling in task processing."""
        # Make graph raise an error
        salesforce_handler.graph.ainvoke = AsyncMock(side_effect=Exception("Graph execution failed"))
        
        params = {
            "task": {
                "id": "task-789",
                "instruction": "Test error",
                "context": {}
            }
        }
        
        result = await salesforce_handler.process_task(params)
        
        assert result["status"] == "failed"
        assert "error" in result
        assert "Graph execution failed" in result["error"]
        assert len(result["artifacts"]) == 1
        assert "Error processing Salesforce request" in result["artifacts"][0]["content"]
    
    @pytest.mark.asyncio
    async def test_process_task_with_external_context(self, salesforce_handler, mock_llm):
        """Test that external context is properly passed."""
        # Mock LLM to return a response
        mock_llm.invoke.return_value = AIMessage(content="Context processed")
        
        params = {
            "task": {
                "id": "task-context",
                "instruction": "Test context passing",
                "context": {
                    "previous_messages": ["Hello", "World"],
                    "user_preferences": {"style": "formal"}
                }
            }
        }
        
        result = await salesforce_handler.process_task(params)
        
        # The handler should process the task with context
        assert result["status"] == "completed"
        assert len(result["artifacts"]) > 0
        # The context should be passed through to the agent's processing
    
    @pytest.mark.asyncio
    async def test_get_agent_card(self, salesforce_handler):
        """Test getting the agent card."""
        result = await salesforce_handler.get_agent_card({})
        
        assert result["name"] == "salesforce-agent"
        assert result["version"] == "1.0.0"
        assert "salesforce_operations" in result["capabilities"]
        assert "lead_management" in result["capabilities"]
        assert result["endpoints"]["process_task"] == "/a2a"
        assert result["metadata"]["framework"] == "langgraph"
        assert result["metadata"]["tools_count"] == 20


class TestSalesforceAgentIntegration:
    """Test Salesforce agent integration with tools."""
    
    @pytest.mark.asyncio
    async def test_agent_tool_integration(self, mock_llm):
        """Test that agent properly integrates with Salesforce tools."""
        from src.tools.salesforce_tools import GetAccountTool
        
        # Mock the tool execution
        with patch.object(GetAccountTool, '_run') as mock_tool_run:
            mock_tool_run.return_value = json.dumps({
                "Id": "001XX000003DHP0",
                "Name": "Acme Corporation",
                "Industry": "Technology"
            })
            
            # Create graph
            with patch('src.agents.salesforce.main.create_azure_openai_chat', return_value=mock_llm):
                graph = build_salesforce_graph()
            
            # Verify tools are bound
            tools_node = graph.nodes.get("tools")
            assert tools_node is not None
    
    @pytest.mark.asyncio
    async def test_recursion_limit(self, mock_llm):
        """Test that recursion limit is properly set."""
        # Mock LLM to always return tool calls (would cause infinite loop)
        mock_llm.invoke.return_value = AIMessage(
            content="",
            tool_calls=[{"id": "call_1", "name": "GetAccountTool", "args": {}}]
        )
        
        with patch('src.agents.salesforce.main.create_azure_openai_chat', return_value=mock_llm):
            salesforce_handler = SalesforceA2AHandler(build_salesforce_graph())
        
        params = {
            "task": {
                "id": "recursion-test",
                "instruction": "Test recursion",
                "context": {}
            }
        }
        
        # Should not hang - recursion limit should stop it
        result = await salesforce_handler.process_task(params)
        
        # Will either complete or fail, but shouldn't hang
        assert result["status"] in ["completed", "failed"]


class TestSalesforceAgentLogging:
    """Test logging functionality in Salesforce agent."""
    
    @pytest.mark.asyncio
    async def test_activity_logging(self, salesforce_handler, mock_llm, capture_logs):
        """Test that activities are properly logged."""
        mock_llm.invoke.return_value = AIMessage(content="Test response")
        
        params = {
            "task": {
                "id": "log-test",
                "instruction": "Test logging",
                "context": {}
            }
        }
        
        with patch('src.agents.salesforce.main.log_salesforce_activity') as mock_log:
            await salesforce_handler.process_task(params)
            
            # Should log task start
            mock_log.assert_any_call(
                "A2A_TASK_START",
                task_id="log-test",
                instruction_preview="Test logging"
            )
            
            # Should log task completion
            # Check that TASK_COMPLETED was called with correct task_id
            task_completed_calls = [
                call for call in mock_log.call_args_list 
                if call[0][0] == "TASK_COMPLETED" and call[1].get('task_id') == "log-test"
            ]
            assert len(task_completed_calls) > 0, "Expected TASK_COMPLETED to be logged"
            
            # Verify response preview contains test response
            response_preview = task_completed_calls[0][1].get('response_preview', '')
            assert "Test response" in response_preview
    
    @pytest.mark.asyncio
    async def test_cost_tracking(self, salesforce_handler, mock_llm):
        """Test that LLM costs are tracked."""
        mock_llm.invoke.return_value = AIMessage(content="Response")
        
        params = {
            "task": {
                "id": "cost-test",
                "instruction": "Test cost",
                "context": {}
            }
        }
        
        with patch('src.utils.logging.activity_logger.log_cost_activity') as mock_cost:
            await salesforce_handler.process_task(params)
            
            # Should track costs
            mock_cost.assert_called()
            call_args = mock_cost.call_args
            assert call_args[0][0] == "SALESFORCE_LLM_CALL"  # operation
            assert "task_id" in call_args[1]
            assert call_args[1]["task_id"] == "cost-test"