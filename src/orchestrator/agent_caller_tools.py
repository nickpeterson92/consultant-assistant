"""
Agent Caller Tools for the Orchestrator
These tools enable the orchestrator to communicate with specialized agents via A2A protocol
"""

import uuid
import json
import asyncio
from typing import Dict, Any, Optional, List, Annotated
from langchain_core.tools import BaseTool, tool
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import BaseModel, Field
import logging

from .agent_registry import AgentRegistry
from ..a2a import A2AClient, A2ATask, A2AException

# Import unified logger
from src.utils.logging import get_logger

# Initialize structured logger
logger = get_logger()
from src.utils.config import (
    CONVERSATION_SUMMARY_KEY, USER_CONTEXT_KEY, 
    MESSAGES_KEY, MEMORY_KEY, RECENT_MESSAGES_COUNT
)
from src.utils.message_serialization import serialize_recent_messages


class BaseAgentTool(BaseTool):
    """Base class for agent tools with common functionality."""
    
    def _extract_relevant_context(self, state: Dict[str, Any], 
                                 filter_keywords: Optional[List[str]] = None,
                                 message_count: int = RECENT_MESSAGES_COUNT) -> Dict[str, Any]:
        """Extract relevant context from global state.
        
        Args:
            state: The global orchestrator state
            filter_keywords: Optional keywords to filter memory items
            message_count: Number of recent messages to include
            
        Returns:
            Dictionary containing relevant context for the agent
        """
        context = {}
        
        # Include conversation summary if available
        if "summary" in state:
            context["conversation_summary"] = state["summary"]
        
        # Include recent messages using centralized serialization utility
        if MESSAGES_KEY in state and state[MESSAGES_KEY]:
            recent_messages = serialize_recent_messages(state[MESSAGES_KEY], message_count)
            if recent_messages:
                context["recent_messages"] = recent_messages
        
        # Include filtered memory if keywords provided
        if MEMORY_KEY in state and filter_keywords:
            memory = state[MEMORY_KEY]
            if isinstance(memory, dict):
                filtered_memory = {}
                for key, value in memory.items():
                    if any(keyword.lower() in key.lower() for keyword in filter_keywords):
                        filtered_memory[key] = value
                if filtered_memory:
                    context["filtered_memory"] = filtered_memory
        
        # Include user context if it exists
        if "user_context" in state:
            context["user_context"] = state["user_context"]
        
        return context
    
    def _create_state_snapshot(self, state: Dict[str, Any], 
                             include_keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create a minimal state snapshot for the agent.
        
        Args:
            state: The global orchestrator state
            include_keys: Optional list of specific keys to include
            
        Returns:
            Minimal state snapshot
        """
        default_keys = ["summary", "events", "memory"]
        keys_to_include = include_keys or default_keys
        
        return {
            key: state.get(key) 
            for key in keys_to_include 
            if key in state
        }


class AgentCallInput(BaseModel):
    """Input Schema for Multi-Agent Task Delegation.
    
    Defines the interface contract for orchestrator-to-agent communication
    following enterprise integration patterns and loose coupling principles.
    Supports both explicit agent targeting and capability-based auto-selection.
    
    Architecture Benefits:
    - Loose coupling: Agents selected by capability, not hard-coded names
    - Context preservation: Maintains conversation state across agent boundaries
    - Flexibility: Supports both specific targeting and intelligent routing
    - Extensibility: New agents automatically discoverable via capabilities
    """
    instruction: str = Field(
        description="The user's EXACT request in their own words. "
        "DO NOT translate or modify. Pass through exactly as the user stated it."
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Additional context data for enhanced agent decision-making. "
        "Includes conversation history, user preferences, business rules, or "
        "cross-system integration data for more intelligent processing"
    )
    agent_name: Optional[str] = Field(
        default=None, 
        description="Explicit agent targeting (optional). Use only when you need "
        "a specific agent. Leave empty for automatic capability-based selection. "
        "Examples: 'salesforce-agent', 'travel-agent', 'hr-agent'"
    )
    required_capabilities: Optional[List[str]] = Field(
        default=None, 
        description="Required agent capabilities for intelligent agent selection. "
        "Used when multiple agents might handle a task. Examples: "
        "['salesforce_operations'], ['travel_booking', 'expense_reporting']"
    )

class SalesforceAgentTool(BaseAgentTool):
    """Orchestrator Tool for Salesforce CRM Agent Communication.
    
    Implements loose coupling between the orchestrator and specialized Salesforce agent
    via A2A (Agent-to-Agent) protocol. Provides enterprise CRM capabilities through
    distributed agent architecture with state management and context preservation.
    
    Architecture Pattern:
    - Follows Service-Oriented Architecture (SOA) principles
    - Implements Event-Driven Multi-Agent communication
    - Maintains conversation context across agent boundaries
    - Preserves memory state for session continuity
    
    CRM Capabilities:
    - Lead Management: Lead generation, qualification, conversion tracking
    - Account Operations: Customer account lifecycle, relationship mapping
    - Opportunity Pipeline: Sales forecasting, deal progression, revenue tracking  
    - Contact Management: Customer relationship coordination, communication history
    - Case Management: Customer service tickets, issue resolution, SLA tracking
    - Task Management: Activity coordination, follow-up scheduling, productivity tracking
    
    Integration Patterns:
    - Individual lookups: "get [specific record]" or "find [record] by [criteria]"
    - Bulk operations: "get all [records] for [account]" (when explicitly requested)
    - CRUD operations: create, read, update workflows
    - Cross-object relationships: account→contacts→opportunities→cases→tasks
    
    Business Intelligence:
    - Pipeline analysis and revenue forecasting
    - Customer relationship mapping and account health
    - Service level tracking and customer satisfaction
    - Sales activity monitoring and team productivity
    """
    name: str = "salesforce_agent"
    description: str = """Delegates Salesforce CRM operations to specialized agent via A2A protocol.
    
    PRIMARY CAPABILITIES:
    - Lead Management: Lead generation, qualification, conversion (create/get/update leads)
    - Account Operations: Customer lifecycle, relationship mapping (create/get/update accounts)
    - Opportunity Pipeline: Sales forecasting, deal tracking (create/get/update opportunities)
    - Contact Management: Customer relationships, communication (create/get/update contacts)
    - Case Management: Service tickets, issue resolution (create/get/update cases)
    - Task Management: Activity coordination, follow-ups (create/get/update tasks)
    - ANALYTICS & INSIGHTS: Business metrics, KPIs, revenue analysis, pipeline analytics
    
    CRITICAL - NATURAL LANGUAGE PASSTHROUGH:
    Pass the user's EXACT words to the Salesforce agent without translation or modification.
    The Salesforce agent understands natural language in CRM context.
    
    EXAMPLES OF CORRECT PASSTHROUGH:
    - User: "whats the lowdown on this account" → Pass: "whats the lowdown on this account"
    - User: "gimme the scoop on our pipeline" → Pass: "gimme the scoop on our pipeline"
    - User: "get the genepoint account" → Pass: "get the genepoint account"
    
    The Salesforce agent handles ALL CRM operations and will interpret the user's intent.
    
    Returns structured CRM data with Salesforce IDs for downstream processing."""
    
    # Note: Removed args_schema to fix InjectedState detection bug in LangGraph
    # See: https://github.com/langchain-ai/langgraph/issues/2220
    
    def __init__(self, registry: AgentRegistry):
        super().__init__(metadata={"registry": registry})
    
    
    def _extract_conversation_context(self, state: Optional[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extract and serialize conversation context from LangGraph state.
        
        Args:
            state: LangGraph injected state containing messages, memory, etc.
            context: Additional context to merge
            
        Returns:
            Dictionary of serialized context ready for A2A transmission
        """
        messages = state.get("messages", []) if state else []
        memory = state.get("memory", {}) if state else {}
        
        extracted_context = {}
        
        # Include recent messages using centralized serialization
        if messages:
            recent_messages = serialize_recent_messages(messages, count=5)
            if recent_messages:
                extracted_context["recent_messages"] = recent_messages
        
        # Include memory data
        if memory:
            extracted_context["memory"] = memory
        
        # Include conversation summary if available  
        if state and "summary" in state:
            extracted_context["conversation_summary"] = state["summary"]
        
        # Merge any additional context
        if context:
            extracted_context.update(context)
        
        return extracted_context
    
    def _serialize_state_snapshot(self, state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Serialize LangGraph state for A2A transmission.
        
        Args:
            state: Raw LangGraph state that may contain LangChain objects
            
        Returns:
            JSON-serializable state snapshot
        """
        serialized_state = {}
        if state:
            for key, value in state.items():
                if key == "messages" and isinstance(value, list):
                    # Serialize messages using centralized utility
                    serialized_state[key] = serialize_recent_messages(value)
                else:
                    # Keep other state as-is
                    serialized_state[key] = value
        return serialized_state
    
    def _find_salesforce_agent(self):
        """Locate the Salesforce agent in the registry.
        
        Returns:
            Agent instance or None if not found
        """
        registry = self.metadata["registry"]
        agent = registry.find_agents_by_capability("salesforce_operations")
        
        if not agent:
            logger.warning("Salesforce agent not found by capability, trying by name...")
            agent = registry.get_agent("salesforce-agent")
        
        # Handle list return from find_agents_by_capability
        if isinstance(agent, list) and agent:
            agent = agent[0]
        
        return agent
    
    def _create_error_command(self, error_message: str, tool_call_id: Optional[str] = None):
        """Create a standardized error Command response.
        
        Args:
            error_message: Error description for the user
            tool_call_id: Optional tool call identifier for response tracking
            
        Returns:
            Command object with error message or plain error string
        """
        if tool_call_id:
            return Command(
                update={
                    "messages": [ToolMessage(
                        content=error_message,
                        tool_call_id=tool_call_id
                    )]
                }
            )
        else:
            # Return plain error message when no tool_call_id
            return error_message
    
    def _extract_response_content(self, result: Dict[str, Any]) -> str:
        """Extract response content from A2A result.
        
        Args:
            result: Raw A2A response result
            
        Returns:
            Extracted content string
        """
        response_content = ""
        
        if "artifacts" in result:
            response = result["artifacts"]
            
            if isinstance(response, list) and len(response) > 0:
                response = response[0]
                
            if isinstance(response, dict) and "content" in response:
                response_content = response["content"]
            else:
                response_content = str(response)
        
        return response_content
    
    def _process_tool_results(self, result: Dict[str, Any], response_content: str, task_id: str) -> str:
        """Process and augment response with structured tool data.
        
        Args:
            result: A2A response containing potential tool results
            response_content: Base response content
            task_id: Task identifier for logging
            
        Returns:
            Final response content with structured data if available
        """
        # Check for tool results in state_updates
        tool_results_data = None
        if "state_updates" in result and "tool_results" in result["state_updates"]:
            tool_results_data = result["state_updates"]["tool_results"]
        
        if tool_results_data:
            final_response = response_content + "\n\n[STRUCTURED_TOOL_DATA]:\n" + json.dumps(tool_results_data, indent=2)
            
            # Log structured data addition
            logger.info("structured_data_found",
                component="orchestrator",
                tool_name="salesforce_agent",
                data_preview=str(tool_results_data)[:200],
                data_size=len(json.dumps(tool_results_data)),
                record_count=len(tool_results_data) if isinstance(tool_results_data, list) else 1,
                agent="salesforce-agent",
                task_id=task_id
            )
            return final_response
        else:
            return response_content
    
    async def _arun(self, instruction: str, context: Optional[Dict[str, Any]] = None, state: Annotated[Dict[str, Any], InjectedState] = None, **kwargs) -> Command:
        """Execute the Salesforce agent call using Command pattern.
        
        This method orchestrates the entire flow but delegates specific responsibilities
        to focused helper methods for better maintainability.
        """
        # Log tool invocation start
        tool_call_id = kwargs.get("tool_call_id", None)
        logger.info("tool_invocation_start",
            component="orchestrator",
            operation="salesforce_agent_tool",
            tool_name="salesforce_agent",
            tool_call_id=tool_call_id,
            instruction_preview=instruction[:100] if instruction else "",
            has_context=bool(context),
            has_state=bool(state)
        )
        
        try:
            # Extract and serialize conversation context
            extracted_context = self._extract_conversation_context(state, context)
            
            # Find the Salesforce agent
            agent = self._find_salesforce_agent()
            if not agent:
                logger.error("agent_not_found",
                    component="orchestrator",
                    operation="salesforce_agent_tool",
                    agent_type="salesforce",
                    tool_call_id=tool_call_id,
                    error="Salesforce agent not available"
                )
                return self._create_error_command(
                    "Error: Salesforce agent not available. Please ensure the Salesforce agent is running and registered.",
                    tool_call_id
                )
            
            # Create A2A task with serialized state
            task_id = str(uuid.uuid4())
            serialized_state = self._serialize_state_snapshot(state)
            
            task = A2ATask(
                id=task_id,
                instruction=instruction,
                context=extracted_context,
                state_snapshot=serialized_state
            )
            
            # Execute A2A call
            async with A2AClient() as client:
                endpoint = agent.endpoint + "/a2a"
                
                # Log A2A dispatch
                logger.info("a2a_dispatch", 
                    component="orchestrator",
                    agent="salesforce-agent",
                    task_id=task_id,
                    instruction_preview=instruction[:100],
                    endpoint=endpoint,
                    context_keys=list(extracted_context.keys()),
                    context_size=len(str(extracted_context))
                )
                
                result = await client.process_task(endpoint=endpoint, task=task)
                
                # Process response
                response_content = self._extract_response_content(result)
                final_response = self._process_tool_results(result, response_content, task_id)
                
                logger.info("a2a_response_success",
                    component="orchestrator",
                    agent="salesforce-agent", 
                    task_id=task_id,
                    response_length=len(final_response)
                )
                
                # Log successful tool completion
                logger.info("tool_invocation_complete",
                    component="orchestrator",
                    operation="salesforce_agent_tool",
                    tool_name="salesforce_agent",
                    tool_call_id=tool_call_id,
                    response_length=len(final_response),
                    success=True
                )
                
                # Return Command with processed response
                # If we have a tool_call_id, return a ToolMessage, otherwise return the content directly
                if tool_call_id:
                    return Command(
                        update={
                            "messages": [ToolMessage(
                                content=final_response,
                                tool_call_id=tool_call_id,
                                name="salesforce_agent"
                            )]
                        }
                    )
                else:
                    # Return plain response when called without tool_call_id
                    return final_response
        
        except A2AException as e:
            logger.error("tool_invocation_error",
                component="orchestrator",
                operation="salesforce_agent_tool",
                tool_name="salesforce_agent",
                tool_call_id=tool_call_id,
                error_type="A2AException",
                error=str(e)
            )
            return self._create_error_command(
                f"Error: Failed to communicate with Salesforce agent - {str(e)}",
                tool_call_id
            )
        except Exception as e:
            logger.error("tool_invocation_error",
                component="orchestrator",
                operation="salesforce_agent_tool",
                tool_name="salesforce_agent",
                tool_call_id=tool_call_id,
                error_type=type(e).__name__,
                error=str(e)
            )
            return self._create_error_command(
                f"Error: Unexpected error - {str(e)}",
                tool_call_id
            )
    
    def _run(self, instruction: str, context: Optional[Dict[str, Any]] = None, **kwargs) -> Command:
        """Synchronous wrapper for async execution"""
        return asyncio.run(self._arun(instruction, context, **kwargs))

class GenericAgentTool(BaseAgentTool):
    """Orchestrator Tool for Dynamic Multi-Agent Task Delegation.
    
    Implements intelligent agent selection and task routing through capability-based
    discovery and automatic agent matching. Provides extensible architecture for
    enterprise system integration via distributed specialized agents.
    
    Agent Discovery Architecture:
    - Capability-based agent selection using registry pattern
    - Dynamic agent health monitoring and failover
    - Load balancing across multiple agent instances
    - Real-time agent capability advertisement and discovery
    
    Supported Enterprise Systems:
    - Travel Management: Booking platforms, expense integration, itinerary coordination
    - Human Resources: Employee onboarding, feedback systems, policy management
    - Document Processing: OCR, content extraction, workflow automation
    - Financial Systems: Expense reporting, approval workflows, budget management
    - Communication Platforms: Email automation, notification systems, team coordination
    
    Extensibility Patterns:
    - Plugin architecture for new agent types
    - Capability inheritance and composition
    - Cross-agent workflow orchestration
    - Enterprise service bus integration
    
    Task Routing Intelligence:
    - Natural language requirement analysis
    - Capability matching algorithms
    - Multi-agent coordination for complex workflows
    - Context preservation across agent boundaries
    """
    name: str = "call_agent"
    description: str = """Intelligently routes tasks to specialized enterprise agents based on capability matching.
    
    AUTOMATIC AGENT SELECTION:
    The orchestrator analyzes your request and selects the best specialized agent automatically.
    No need to specify which agent - just describe what you need.
    
    ENTERPRISE CAPABILITIES:
    - Travel Management: Flight/hotel booking, itinerary planning, expense integration
    - Human Resources: Employee feedback, onboarding workflows, policy queries
    - Document Processing: OCR, PDF extraction, content analysis, workflow automation
    - Financial Systems: Expense reporting, receipt processing, approval workflows
    - Communication: Email automation, notification systems, team coordination
    
    CRITICAL - NATURAL LANGUAGE PASSTHROUGH:
    Pass the user's EXACT words to the selected agent without translation or modification.
    Each specialized agent understands natural language in its domain context.
    
    DO NOT translate user requests - pass them through verbatim.
    
    ADVANCED FEATURES:
    - Multi-agent workflows: Complex tasks requiring multiple specialized systems
    - Context awareness: Maintains conversation state across agent handoffs
    - Error recovery: Automatic failover and retry mechanisms
    - Enterprise integration: Connects to existing business process workflows
    
    Returns structured responses with agent identification and task completion status."""
    
    # Note: Removed args_schema to fix InjectedState detection bug in LangGraph
    # See: https://github.com/langchain-ai/langgraph/issues/2220
    
    def __init__(self, registry: AgentRegistry):
        super().__init__(metadata={"registry": registry})
    
    
    async def _arun(self, instruction: str, context: Optional[Dict[str, Any]] = None, 
                   agent_name: Optional[str] = None, required_capabilities: Optional[List[str]] = None, **kwargs) -> Command:
        """Execute a call to a specialized agent"""
        # Create a minimal state to avoid circular references
        state = {
            "messages": [],
            "memory": {},
            "turns": 0
        }
        
        # Find the appropriate agent
        registry = self.metadata["registry"]
        if agent_name:
            agent = registry.get_agent(agent_name)
        else:
            agent = registry.find_best_agent_for_task(instruction, required_capabilities)
        
        if not agent:
            available_agents = [a.name for a in registry.list_agents() if a.status == "online"]
            error_msg = f"Error: No suitable agent found for the task. Available agents: {', '.join(available_agents) if available_agents else 'None'}"
            tool_call_id = kwargs.get("tool_call_id", None)
            if tool_call_id:
                return Command(
                    update={
                        "messages": [ToolMessage(
                            content=error_msg,
                            tool_call_id=tool_call_id
                        )]
                    }
                )
            else:
                return error_msg
        
        # Extract context and create state snapshot
        # Use base class method with agent-specific capabilities as filter
        extracted_context = self._extract_relevant_context(
            state, 
            filter_keywords=agent.agent_card.capabilities,
            message_count=3  # Use fewer messages for generic agents
        )
        
        # Rename filtered_memory to relevant_memory for clarity
        if "filtered_memory" in extracted_context:
            extracted_context["relevant_memory"] = extracted_context.pop("filtered_memory")
        if context:
            extracted_context.update(context)
        
        # Use base class method to create state snapshot
        state_snapshot = self._create_state_snapshot(
            state, 
            include_keys=["messages", "memory", "turns"]
        )
        
        # Create A2A task
        task = A2ATask(
            id=str(uuid.uuid4()),
            instruction=instruction,
            context=extracted_context,
            state_snapshot=state_snapshot
        )
        
        try:
            async with A2AClient() as client:
                result = await client.process_task(
                    endpoint=agent.endpoint + "/a2a",
                    task=task
                )
                
                # Extract the response and convert to Command
                response_content = ""
                if "artifacts" in result:
                    response = result["artifacts"]
                    if isinstance(response, list) and len(response) > 0:
                        response = response[0]
                    if isinstance(response, dict) and "content" in response:
                        response_content = response["content"]
                    else:
                        response_content = str(response)
                else:
                    response_content = str(result.get("result", f"No response from {agent.name}"))
                
                tool_call_id = kwargs.get("tool_call_id", None)
                if tool_call_id:
                    return Command(
                        update={
                            "messages": [ToolMessage(
                                content=response_content,
                                tool_call_id=tool_call_id,
                                name="generic_agent"
                            )]
                        }
                    )
                else:
                    return response_content
        
        except A2AException as e:
            logger.error(f"Error calling agent {agent.name}: {e}")
            error_msg = f"Error: Failed to communicate with {agent.name} - {str(e)}"
            tool_call_id = kwargs.get("tool_call_id", None)
            if tool_call_id:
                return Command(
                    update={
                        "messages": [ToolMessage(
                            content=error_msg,
                            tool_call_id=tool_call_id
                        )]
                    }
                )
            else:
                return error_msg
        except Exception as e:
            logger.error(f"Unexpected error calling agent {agent.name}: {e}")
            logger.exception("Full traceback:")
            error_msg = f"Error: Unexpected error - {str(e)}"
            tool_call_id = kwargs.get("tool_call_id", None)
            if tool_call_id:
                return Command(
                    update={
                        "messages": [ToolMessage(
                            content=error_msg,
                            tool_call_id=tool_call_id
                        )]
                    }
                )
            else:
                return error_msg
    
    def _run(self, instruction: str, context: Optional[Dict[str, Any]] = None, 
           agent_name: Optional[str] = None, required_capabilities: Optional[List[str]] = None, **kwargs) -> Command:
        """Synchronous wrapper for async execution"""
        return asyncio.run(self._arun(instruction, context, agent_name, required_capabilities, **kwargs))

class AgentRegistryTool(BaseTool):
    """Orchestrator Tool for Multi-Agent System Management and Monitoring.
    
    Provides comprehensive agent lifecycle management, health monitoring, and
    system observability for distributed agent architectures. Implements
    service discovery patterns and operational intelligence for agent ecosystems.
    
    Registry Management Capabilities:
    - Agent discovery and registration management
    - Real-time health monitoring and status tracking  
    - Capability mapping and service advertisement
    - Load balancing and failover coordination
    
    Operational Intelligence:
    - Agent performance metrics and analytics
    - System capacity planning and resource utilization
    - Service level agreement monitoring
    - Distributed system health dashboard
    
    Enterprise Operations:
    - Multi-environment agent deployment tracking
    - Version management and rolling updates
    - Configuration management and policy enforcement
    - Audit trails and compliance monitoring
    
    Monitoring Patterns:
    - Heartbeat detection and liveness probes
    - Circuit breaker status and failure tracking
    - Response time analytics and performance tuning
    - Resource consumption and scaling triggers
    """
    name: str = "manage_agents"
    description: str = """Manages multi-agent system registry with health monitoring and operational intelligence.
    
    REGISTRY OPERATIONS:
    - 'list': Display all registered agents with capabilities and current status
    - 'health_check': Monitor agent availability and response times (specify agent_name for individual check)
    - 'stats': System-wide analytics including capacity, utilization, and performance metrics
    
    OPERATIONAL USE CASES:
    - System Health: "Check if all agents are running properly"
    - Capacity Planning: "Show me current system utilization and available agents"
    - Troubleshooting: "Which agents are offline or experiencing issues?"
    - Service Discovery: "What capabilities are available in the current agent pool?"
    
    MONITORING INTELLIGENCE:
    - Agent availability and response time tracking
    - Capability coverage and redundancy analysis
    - System load distribution and bottleneck identification
    - Performance trending and capacity forecasting
    
    Returns structured operational data for system administration and monitoring dashboards."""
    
    class AgentRegistryInput(BaseModel):
        action: str = Field(description="Action to perform: 'list', 'health_check', 'stats'")
        agent_name: Optional[str] = Field(default=None, description="Specific agent name for health check")
    
    args_schema: type = AgentRegistryInput
    
    def __init__(self, registry: AgentRegistry):
        super().__init__(metadata={"registry": registry})
    
    async def _arun(self, action: str, agent_name: Optional[str] = None) -> str:
        """Execute registry management action"""
        registry = self.metadata["registry"]
        if action == "list":
            agents = registry.list_agents()
            if not agents:
                return "No agents registered in the system."
            
            agent_list = []
            for agent in agents:
                capabilities = ", ".join(agent.agent_card.capabilities) if agent.agent_card.capabilities else "None"
                agent_list.append(f"- {agent.name} ({agent.status}): {capabilities}")
            
            return f"Registered Agents:\n" + "\n".join(agent_list)
        
        elif action == "health_check":
            if agent_name:
                result = await registry.health_check_agent(agent_name)
                return f"Health check for {agent_name}: {'✓ Online' if result else '✗ Offline/Error'}"
            else:
                results = await registry.health_check_all_agents()
                status_list = []
                for name, status in results.items():
                    status_list.append(f"- {name}: {'✓ Online' if status else '✗ Offline/Error'}")
                return f"Agent Health Status:\n" + "\n".join(status_list)
        
        elif action == "stats":
            stats = registry.get_registry_stats()
            return f"""Agent Registry Statistics:
- Total Agents: {stats['total_agents']}
- Online: {stats['online_agents']}
- Offline: {stats['offline_agents']}
- Error: {stats['error_agents']}
- Unknown: {stats['unknown_agents']}
- Available Capabilities: {', '.join(stats['available_capabilities'])}"""
        
        else:
            return f"Unknown action: {action}. Available actions: list, health_check, stats"
    
    def _run(self, action: str, agent_name: Optional[str] = None) -> str:
        """Synchronous wrapper for async execution"""
        return asyncio.run(self._arun(action, agent_name))