"""
End-to-end tests for complete Salesforce workflows.

These tests simulate real user interactions through the entire system,
from natural language input to Salesforce operations to memory persistence.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from aioresponses import aioresponses

from src.orchestrator.main import build_orchestrator_graph
from src.utils.storage.memory_schemas import SimpleMemory


@pytest.mark.e2e
class TestSalesforceWorkflowsE2E:
    """Test complete Salesforce workflows end-to-end."""
    
    @pytest.fixture
    async def system(self, memory_store):
        """Set up the complete system for E2E testing."""
        # Build orchestrator graph
        with patch('src.orchestrator.main.memory_store', memory_store):
            graph = build_orchestrator_graph()
        
        # Configuration for tests
        config = {
            "configurable": {
                "user_id": "e2e-test-user",
                "thread_id": "e2e-test-thread"
            },
            "recursion_limit": 20
        }
        
        return graph, config, memory_store
    
    @pytest.fixture
    def mock_salesforce_responses(self):
        """Mock Salesforce agent responses for various operations."""
        return {
            "create_lead": {
                "jsonrpc": "2.0",
                "result": {
                    "artifacts": [{
                        "id": "sf-lead-created",
                        "content": json.dumps({
                            "success": True,
                            "id": "00Q1234567890ABC",
                            "message": "Lead created successfully",
                            "structured_data": {
                                "leads": [{
                                    "id": "00Q1234567890ABC",
                                    "name": "John Smith",
                                    "email": "john@techcorp.com",
                                    "company": "TechCorp",
                                    "status": "New"
                                }]
                            }
                        }),
                        "content_type": "application/json"
                    }],
                    "status": "completed"
                },
                "id": "1"
            },
            "convert_lead": {
                "jsonrpc": "2.0",
                "result": {
                    "artifacts": [{
                        "id": "sf-lead-converted",
                        "content": json.dumps({
                            "success": True,
                            "message": "Lead converted to opportunity",
                            "structured_data": {
                                "accounts": [{
                                    "id": "0011234567890ABC",
                                    "name": "TechCorp"
                                }],
                                "contacts": [{
                                    "id": "0031234567890ABC",
                                    "name": "John Smith",
                                    "email": "john@techcorp.com",
                                    "account_id": "0011234567890ABC"
                                }],
                                "opportunities": [{
                                    "id": "0061234567890ABC",
                                    "name": "TechCorp Opportunity",
                                    "amount": 50000,
                                    "stage": "Prospecting",
                                    "account_id": "0011234567890ABC"
                                }]
                            }
                        }),
                        "content_type": "application/json"
                    }],
                    "status": "completed"
                },
                "id": "2"
            },
            "close_opportunity": {
                "jsonrpc": "2.0",
                "result": {
                    "artifacts": [{
                        "id": "sf-opp-closed",
                        "content": json.dumps({
                            "success": True,
                            "message": "Opportunity updated to Closed Won",
                            "structured_data": {
                                "opportunities": [{
                                    "id": "0061234567890ABC",
                                    "name": "TechCorp Opportunity",
                                    "amount": 50000,
                                    "stage": "Closed Won",
                                    "account_id": "0011234567890ABC"
                                }]
                            }
                        }),
                        "content_type": "application/json"
                    }],
                    "status": "completed"
                },
                "id": "3"
            }
        }
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_complete_lead_to_close_workflow(self, system, mock_salesforce_responses):
        """Test the complete workflow from lead creation to closing a deal."""
        graph, config, memory_store = system
        
        # Mock LLM responses for the conversation
        llm_responses = [
            # Response to "Create a new lead..."
            AIMessage(
                content="",
                tool_calls=[{
                    "id": "call_1",
                    "name": "SalesforceAgentTool",
                    "args": {
                        "instruction": "Create a new lead for John Smith at TechCorp, email john@techcorp.com",
                        "context": {}
                    }
                }]
            ),
            AIMessage(content="I've successfully created a new lead for John Smith at TechCorp with email john@techcorp.com. The lead ID is 00Q1234567890ABC."),
            
            # Response to "Convert this lead..."
            AIMessage(
                content="",
                tool_calls=[{
                    "id": "call_2",
                    "name": "SalesforceAgentTool",
                    "args": {
                        "instruction": "Convert lead 00Q1234567890ABC to an opportunity worth $50,000",
                        "context": {"lead_id": "00Q1234567890ABC", "lead_name": "John Smith"}
                    }
                }]
            ),
            AIMessage(content="I've successfully converted the lead to an opportunity worth $50,000. The opportunity ID is 0061234567890ABC, and I've also created an account for TechCorp and a contact for John Smith."),
            
            # Response to "Update the opportunity..."
            AIMessage(
                content="",
                tool_calls=[{
                    "id": "call_3",
                    "name": "SalesforceAgentTool",
                    "args": {
                        "instruction": "Update opportunity 0061234567890ABC to Closed Won",
                        "context": {"opportunity_id": "0061234567890ABC", "opportunity_name": "TechCorp Opportunity"}
                    }
                }]
            ),
            AIMessage(content="Excellent! I've successfully updated the TechCorp opportunity to Closed Won. The deal for $50,000 has been closed.")
        ]
        
        mock_llm = AsyncMock()
        mock_llm.invoke = AsyncMock(side_effect=llm_responses)
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        
        with patch('src.orchestrator.main.create_azure_openai_chat', return_value=mock_llm):
            with aioresponses() as m:
                # Mock Salesforce agent endpoints
                base_url = "http://localhost:8001"
                
                # Mock agent card
                m.get(f"{base_url}/a2a/agent-card", payload={
                    "name": "salesforce-agent",
                    "capabilities": ["salesforce_operations"]
                }, repeat=True)
                
                # Mock the three Salesforce operations
                m.post(f"{base_url}/a2a", payload=mock_salesforce_responses["create_lead"])
                m.post(f"{base_url}/a2a", payload=mock_salesforce_responses["convert_lead"])
                m.post(f"{base_url}/a2a", payload=mock_salesforce_responses["close_opportunity"])
                
                # User interaction 1: Create lead
                state1 = {
                    "messages": [HumanMessage(content="Create a new lead for John Smith at TechCorp, email john@techcorp.com")],
                    "summary": "",
                    "memory": {},
                    "events": [],
                    "turns_since_last_summary": 0,
                    "turns_since_memory_update": 0
                }
                
                result1 = await graph.ainvoke(state1, config)
                
                # Verify lead creation
                assert len(result1["messages"]) >= 3
                assert any("successfully created" in str(msg.content).lower() for msg in result1["messages"])
                
                # User interaction 2: Convert lead
                state2 = {
                    "messages": result1["messages"] + [HumanMessage(content="Convert this lead to an opportunity worth $50,000")],
                    "summary": result1.get("summary", ""),
                    "memory": result1.get("memory", {}),
                    "events": result1.get("events", []),
                    "turns_since_last_summary": 1,
                    "turns_since_memory_update": 1
                }
                
                result2 = await graph.ainvoke(state2, config)
                
                # Verify conversion
                assert any("converted" in str(msg.content).lower() for msg in result2["messages"])
                
                # User interaction 3: Close deal
                state3 = {
                    "messages": result2["messages"] + [HumanMessage(content="Update the opportunity to Closed Won")],
                    "summary": result2.get("summary", ""),
                    "memory": result2.get("memory", {}),
                    "events": result2.get("events", []),
                    "turns_since_last_summary": 2,
                    "turns_since_memory_update": 2
                }
                
                result3 = await graph.ainvoke(state3, config)
                
                # Verify closure
                assert any("closed won" in str(msg.content).lower() for msg in result3["messages"])
                
                # Verify memory contains all entities
                await asyncio.sleep(0.1)  # Let background memory extraction complete
                
                namespace = ("memory", "e2e-test-user")
                stored_memory = await memory_store.aget(namespace, "SimpleMemory")
                
                if stored_memory:
                    assert len(stored_memory.get("leads", [])) >= 1
                    assert len(stored_memory.get("accounts", [])) >= 1
                    assert len(stored_memory.get("contacts", [])) >= 1
                    assert len(stored_memory.get("opportunities", [])) >= 1
                    
                    # Verify specific data
                    accounts = stored_memory.get("accounts", [])
                    assert any(acc.get("name") == "TechCorp" for acc in accounts)
                    
                    opportunities = stored_memory.get("opportunities", [])
                    assert any(opp.get("stage") == "Closed Won" and opp.get("amount") == 50000 for opp in opportunities)
    
    @pytest.mark.asyncio
    async def test_account_research_workflow(self, system, mock_salesforce_responses):
        """Test researching an account and creating related tasks."""
        graph, config, memory_store = system
        
        # Mock response for account research
        account_research_response = {
            "jsonrpc": "2.0",
            "result": {
                "artifacts": [{
                    "id": "sf-account-research",
                    "content": json.dumps({
                        "success": True,
                        "account": {
                            "Id": "001XX000003DHP0",
                            "Name": "GenePoint",
                            "Industry": "Biotechnology",
                            "AnnualRevenue": 30000000
                        },
                        "contacts": [
                            {
                                "Id": "003XX000004TMM2",
                                "Name": "Edna Frank",
                                "Title": "VP Technology",
                                "Email": "efrank@genepoint.com"
                            }
                        ],
                        "opportunities": [
                            {
                                "Id": "006XX000002kJgS",
                                "Name": "GenePoint Lab Generators",
                                "Amount": 150000,
                                "StageName": "Closed Won"
                            }
                        ],
                        "cases": [
                            {
                                "Id": "500XX000003DHP0",
                                "Subject": "Generator maintenance issue",
                                "Status": "Open"
                            }
                        ],
                        "structured_data": {
                            "accounts": [{"id": "001XX000003DHP0", "name": "GenePoint"}],
                            "contacts": [{"id": "003XX000004TMM2", "name": "Edna Frank", "email": "efrank@genepoint.com", "account_id": "001XX000003DHP0"}],
                            "opportunities": [{"id": "006XX000002kJgS", "name": "GenePoint Lab Generators", "amount": 150000, "stage": "Closed Won"}],
                            "cases": [{"id": "500XX000003DHP0", "subject": "Generator maintenance issue", "status": "Open"}]
                        }
                    }),
                    "content_type": "application/json"
                }],
                "status": "completed"
            },
            "id": "1"
        }
        
        create_task_response = {
            "jsonrpc": "2.0",
            "result": {
                "artifacts": [{
                    "id": "sf-task-created",
                    "content": json.dumps({
                        "success": True,
                        "id": "00TXX000004TMM2",
                        "message": "Task created successfully",
                        "structured_data": {
                            "tasks": [{
                                "id": "00TXX000004TMM2",
                                "subject": "Follow up with Edna Frank",
                                "who_id": "003XX000004TMM2",
                                "status": "Not Started"
                            }]
                        }
                    }),
                    "content_type": "application/json"
                }],
                "status": "completed"
            },
            "id": "2"
        }
        
        llm_responses = [
            # Get all information about GenePoint
            AIMessage(
                content="",
                tool_calls=[{
                    "id": "call_1",
                    "name": "SalesforceAgentTool",
                    "args": {
                        "instruction": "Get all information about GenePoint including account details, contacts, opportunities, and cases",
                        "context": {}
                    }
                }]
            ),
            AIMessage(content="""I found comprehensive information about GenePoint:

**Account Details:**
- Company: GenePoint
- Industry: Biotechnology
- Annual Revenue: $30,000,000

**Key Contact:**
- Edna Frank, VP Technology (efrank@genepoint.com)

**Opportunities:**
- GenePoint Lab Generators: $150,000 (Closed Won)

**Open Cases:**
- Generator maintenance issue (Status: Open)

They appear to be an important biotechnology client with significant revenue and ongoing support needs."""),
            
            # Create follow-up task
            AIMessage(
                content="",
                tool_calls=[{
                    "id": "call_2",
                    "name": "SalesforceAgentTool",
                    "args": {
                        "instruction": "Create a follow-up task for Edna Frank (contact ID 003XX000004TMM2) to discuss the generator maintenance issue",
                        "context": {"contact_id": "003XX000004TMM2", "contact_name": "Edna Frank", "case_subject": "Generator maintenance issue"}
                    }
                }]
            ),
            AIMessage(content="I've created a follow-up task for Edna Frank to discuss the generator maintenance issue. This will help ensure the open case is addressed promptly.")
        ]
        
        mock_llm = AsyncMock()
        mock_llm.invoke = AsyncMock(side_effect=llm_responses)
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        
        with patch('src.orchestrator.main.create_azure_openai_chat', return_value=mock_llm):
            with aioresponses() as m:
                base_url = "http://localhost:8001"
                
                m.get(f"{base_url}/a2a/agent-card", payload={
                    "name": "salesforce-agent",
                    "capabilities": ["salesforce_operations"]
                }, repeat=True)
                
                m.post(f"{base_url}/a2a", payload=account_research_response)
                m.post(f"{base_url}/a2a", payload=create_task_response)
                
                # First request
                state1 = {
                    "messages": [HumanMessage(content="Get all information about GenePoint")],
                    "summary": "",
                    "memory": {},
                    "events": [],
                    "turns_since_last_summary": 0,
                    "turns_since_memory_update": 0
                }
                
                result1 = await graph.ainvoke(state1, config)
                
                # Verify comprehensive data returned
                response_content = str(result1["messages"][-1].content)
                assert "GenePoint" in response_content
                assert "Biotechnology" in response_content
                assert "Edna Frank" in response_content
                assert "maintenance issue" in response_content
                
                # Second request - create task
                state2 = {
                    "messages": result1["messages"] + [HumanMessage(content="Create a follow-up task for their main contact about the open case")],
                    "summary": result1.get("summary", ""),
                    "memory": result1.get("memory", {}),
                    "events": result1.get("events", []),
                    "turns_since_last_summary": 1,
                    "turns_since_memory_update": 1
                }
                
                result2 = await graph.ainvoke(state2, config)
                
                # Verify task creation
                assert any("created a follow-up task" in str(msg.content).lower() for msg in result2["messages"])


@pytest.mark.e2e
class TestMultiTurnConversationE2E:
    """Test multi-turn conversations with context preservation."""
    
    @pytest.mark.asyncio
    async def test_context_preservation_across_turns(self, memory_store):
        """Test that context is preserved across multiple conversation turns."""
        with patch('src.orchestrator.main.memory_store', memory_store):
            graph = build_orchestrator_graph()
        
        config = {
            "configurable": {
                "user_id": "context-test-user",
                "thread_id": "context-test-thread"
            },
            "recursion_limit": 15
        }
        
        # Simulate finding an account, then asking follow-up questions
        find_account_response = {
            "jsonrpc": "2.0",
            "result": {
                "artifacts": [{
                    "id": "sf-account-found",
                    "content": json.dumps({
                        "success": True,
                        "records": [{
                            "Id": "001XX000003DHP0",
                            "Name": "GenePoint",
                            "Industry": "Biotechnology",
                            "NumberOfEmployees": 265
                        }]
                    }),
                    "content_type": "application/json"
                }],
                "status": "completed"
            },
            "id": "1"
        }
        
        get_opportunities_response = {
            "jsonrpc": "2.0",
            "result": {
                "artifacts": [{
                    "id": "sf-opps-found",
                    "content": json.dumps({
                        "success": True,
                        "records": [
                            {"Id": "006XX001", "Name": "Lab Equipment", "Amount": 75000, "StageName": "Proposal"},
                            {"Id": "006XX002", "Name": "Annual Service", "Amount": 25000, "StageName": "Negotiation"}
                        ],
                        "total_value": 100000
                    }),
                    "content_type": "application/json"
                }],
                "status": "completed"
            },
            "id": "2"
        }
        
        create_opportunity_response = {
            "jsonrpc": "2.0",
            "result": {
                "artifacts": [{
                    "id": "sf-opp-created",
                    "content": json.dumps({
                        "success": True,
                        "id": "006XX003",
                        "message": "Opportunity 'Q2 2024 Expansion' created for GenePoint"
                    }),
                    "content_type": "application/json"
                }],
                "status": "completed"
            },
            "id": "3"
        }
        
        # LLM responses that maintain context
        llm_responses = [
            # Find GenePoint
            AIMessage(
                content="",
                tool_calls=[{
                    "id": "call_1",
                    "name": "SalesforceAgentTool",
                    "args": {"instruction": "Find the GenePoint account", "context": {}}
                }]
            ),
            AIMessage(content="I found the GenePoint account. They're a Biotechnology company with 265 employees."),
            
            # What opportunities do they have? (using context)
            AIMessage(
                content="",
                tool_calls=[{
                    "id": "call_2",
                    "name": "SalesforceAgentTool",
                    "args": {
                        "instruction": "Get all opportunities for GenePoint account (ID: 001XX000003DHP0)",
                        "context": {"account_name": "GenePoint", "account_id": "001XX000003DHP0"}
                    }
                }]
            ),
            AIMessage(content="GenePoint has 2 active opportunities totaling $100,000:\n1. Lab Equipment - $75,000 (Proposal stage)\n2. Annual Service - $25,000 (Negotiation stage)"),
            
            # Create new opportunity (using context)
            AIMessage(
                content="",
                tool_calls=[{
                    "id": "call_3",
                    "name": "SalesforceAgentTool",
                    "args": {
                        "instruction": "Create a new opportunity called 'Q2 2024 Expansion' for GenePoint (account ID: 001XX000003DHP0) worth $50,000 closing next quarter",
                        "context": {"account_name": "GenePoint", "account_id": "001XX000003DHP0", "existing_opportunities_value": 100000}
                    }
                }]
            ),
            AIMessage(content="I've successfully created a new opportunity 'Q2 2024 Expansion' for GenePoint worth $50,000. This brings their total pipeline to $150,000.")
        ]
        
        mock_llm = AsyncMock()
        mock_llm.invoke = AsyncMock(side_effect=llm_responses)
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        
        with patch('src.orchestrator.main.create_azure_openai_chat', return_value=mock_llm):
            with aioresponses() as m:
                base_url = "http://localhost:8001"
                m.get(f"{base_url}/a2a/agent-card", payload={"name": "salesforce-agent", "capabilities": ["salesforce_operations"]}, repeat=True)
                
                m.post(f"{base_url}/a2a", payload=find_account_response)
                m.post(f"{base_url}/a2a", payload=get_opportunities_response)
                m.post(f"{base_url}/a2a", payload=create_opportunity_response)
                
                # Turn 1: Find account
                state = {
                    "messages": [HumanMessage(content="Find the GenePoint account")],
                    "summary": "",
                    "memory": {},
                    "events": [],
                    "turns_since_last_summary": 0,
                    "turns_since_memory_update": 0
                }
                
                result1 = await graph.ainvoke(state, config)
                assert "GenePoint" in str(result1["messages"][-1].content)
                
                # Turn 2: Ask about opportunities (context should know "they" = GenePoint)
                state["messages"] = result1["messages"] + [HumanMessage(content="What opportunities do they have?")]
                state["turns_since_last_summary"] = 1
                
                result2 = await graph.ainvoke(state, config)
                response = str(result2["messages"][-1].content)
                assert "Lab Equipment" in response
                assert "$100,000" in response or "100,000" in response
                
                # Turn 3: Create new opportunity (context should still know we're talking about GenePoint)
                state["messages"] = result2["messages"] + [HumanMessage(content="Create a new opportunity for next quarter worth $50k")]
                state["turns_since_last_summary"] = 2
                
                result3 = await graph.ainvoke(state, config)
                response = str(result3["messages"][-1].content)
                assert "created" in response.lower()
                assert "Q2 2024 Expansion" in response or "50,000" in response
                assert "150,000" in response  # Total pipeline value