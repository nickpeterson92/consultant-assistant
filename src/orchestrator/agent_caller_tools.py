"""
Agent Caller Tools for the Orchestrator
These tools enable the orchestrator to communicate with specialized agents via A2A protocol
"""

import uuid
import json
import asyncio
from typing import Dict, Any, Optional, List
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
import logging

from .agent_registry import AgentRegistry
from ..a2a import A2AClient, A2ATask, A2AException

logger = logging.getLogger(__name__)

# Import centralized logging
from src.utils.logging import log_orchestrator_activity
from src.utils.config import (
    CONVERSATION_SUMMARY_KEY, USER_CONTEXT_KEY, 
    MESSAGES_KEY, MEMORY_KEY, RECENT_MESSAGES_COUNT
)


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
        if CONVERSATION_SUMMARY_KEY in state:
            context[CONVERSATION_SUMMARY_KEY] = state[CONVERSATION_SUMMARY_KEY]
        
        # Include recent messages
        if MESSAGES_KEY in state and state[MESSAGES_KEY]:
            recent_messages = []
            for msg in state[MESSAGES_KEY][-message_count:]:
                if hasattr(msg, 'content'):
                    recent_messages.append({
                        "role": getattr(msg, '__class__', type(msg)).__name__,
                        "content": msg.content
                    })
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
        
        # Include user context
        if USER_CONTEXT_KEY in state:
            context[USER_CONTEXT_KEY] = state[USER_CONTEXT_KEY]
        
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
        default_keys = [CONVERSATION_SUMMARY_KEY, "events", MEMORY_KEY, USER_CONTEXT_KEY]
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
        description="Natural language task instruction for the specialized agent. "
        "Be specific about desired outcomes. Examples: 'get all contacts for Acme Corp', "
        "'create a new lead for John Smith at TechCorp', 'book flight to NYC next Tuesday'"
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
    
    OPTIMAL USE CASES:
    - Basic account lookup: "get the [account]" or "find [account] account"
    - Individual record queries: "find account/lead/opportunity by [criteria]"
    - Record creation: "create new lead/opportunity/case/task"
    - Comprehensive account data: "get all contacts/opportunities/cases/tasks for [account]"
    - Pipeline analysis: "show me all opportunities for [account]"
    - Customer service: "get all cases for [customer]"
    
    Returns structured CRM data with Salesforce IDs for downstream processing."""
    
    args_schema: type = AgentCallInput
    
    def __init__(self, registry: AgentRegistry):
        super().__init__(metadata={"registry": registry})
    
    
    async def _arun(self, instruction: str, context: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        """Execute the Salesforce agent call"""
        try:
            
            # Create a minimal state to avoid circular references
            state = {
                "messages": [],
                "memory": {},
                "turns": 0
            }
            
            # Find the Salesforce agent
            registry = self.metadata["registry"]
            agent = registry.find_agents_by_capability("salesforce_operations")
            if not agent:
                logger.warning("Salesforce agent not found by capability, trying by name...")
                agent = registry.get_agent("salesforce-agent")
            
            if isinstance(agent, list) and agent:
                agent = agent[0]
            
            if not agent:
                logger.error("Salesforce agent not available")
                return "Error: Salesforce agent not available. Please ensure the Salesforce agent is running and registered."
            
            # Extract context and create state snapshot
            # Use base class method with Salesforce-specific keywords
            salesforce_keywords = ["account", "lead", "opportunity", "contact", "case", "task", "salesforce"]
            extracted_context = self._extract_relevant_context(state, filter_keywords=salesforce_keywords)
            
            # Rename filtered_memory to salesforce_memory for clarity
            if "filtered_memory" in extracted_context:
                extracted_context["salesforce_memory"] = extracted_context.pop("filtered_memory")
            if context:
                extracted_context.update(context)
            
            state_snapshot = self._create_state_snapshot(state)
            
            # Create A2A task
            task_id = str(uuid.uuid4())
            task = A2ATask(
                id=task_id,
                instruction=instruction,
                context=extracted_context,
                state_snapshot=state_snapshot
            )
            
            async with A2AClient() as client:
                endpoint = agent.endpoint + "/a2a"
                
                                
                # Log A2A dispatch
                log_orchestrator_activity("A2A_DISPATCH",
                                        agent="salesforce-agent",
                                        task_id=task_id,
                                        instruction_preview=instruction[:100],
                                        endpoint=endpoint)
                result = await client.process_task(
                    endpoint=endpoint,
                    task=task
                )
                
                
                # Extract the response and any tool results
                response_content = ""
                tool_results_data = None
                
                if "artifacts" in result:
                    response = result["artifacts"]
                    
                    if isinstance(response, list) and len(response) > 0:
                        response = response[0]
                        
                    if isinstance(response, dict) and "content" in response:
                        response_content = response["content"]
                    else:
                        response_content = str(response)
                
                # Check for tool results in state_updates
                if "state_updates" in result and "tool_results" in result["state_updates"]:
                    tool_results_data = result["state_updates"]["tool_results"]
                
                # Combine conversational response with structured tool data for better summaries
                if tool_results_data:
                    final_response = response_content + "\n\n[STRUCTURED_TOOL_DATA]:\n" + json.dumps(tool_results_data, indent=2)
                else:
                    final_response = response_content
                log_orchestrator_activity("A2A_RESPONSE_SUCCESS",
                                        agent="salesforce-agent", 
                                        task_id=task_id,
                                        response_length=len(final_response))
                return final_response
        
        except A2AException as e:
            logger.error(f"Failed to communicate with Salesforce agent: {e}")
            return f"Error: Failed to communicate with Salesforce agent - {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in Salesforce agent tool: {type(e).__name__}: {e}")
            return f"Error: Unexpected error - {str(e)}"
    
    def _run(self, instruction: str, context: Optional[Dict[str, Any]] = None, **kwargs) -> str:
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
    
    OPTIMAL USE CASES:
    - "Book a flight to San Francisco next week"
    - "Process this expense report and submit for approval" 
    - "Extract data from this PDF document"
    - "Submit employee feedback for Q4 review"
    - "Schedule a team meeting and send calendar invites"
    
    ADVANCED FEATURES:
    - Multi-agent workflows: Complex tasks requiring multiple specialized systems
    - Context awareness: Maintains conversation state across agent handoffs
    - Error recovery: Automatic failover and retry mechanisms
    - Enterprise integration: Connects to existing business process workflows
    
    Returns structured responses with agent identification and task completion status."""
    
    args_schema: type = AgentCallInput
    
    def __init__(self, registry: AgentRegistry):
        super().__init__(metadata={"registry": registry})
    
    
    async def _arun(self, instruction: str, context: Optional[Dict[str, Any]] = None, 
                   agent_name: Optional[str] = None, required_capabilities: Optional[List[str]] = None, **kwargs) -> str:
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
            return f"Error: No suitable agent found for the task. Available agents: {', '.join(available_agents) if available_agents else 'None'}"
        
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
                
                # Extract the response
                if "artifacts" in result:
                    response = result["artifacts"]
                    if isinstance(response, list) and len(response) > 0:
                        response = response[0]
                    if isinstance(response, dict) and "content" in response:
                        response = response["content"]
                    return str(response)
                
                return str(result.get("result", f"No response from {agent.name}"))
        
        except A2AException as e:
            logger.error(f"Error calling agent {agent.name}: {e}")
            return f"Error: Failed to communicate with {agent.name} - {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error calling agent {agent.name}: {e}")
            logger.exception("Full traceback:")
            return f"Error: Unexpected error - {str(e)}"
    
    def _run(self, instruction: str, context: Optional[Dict[str, Any]] = None, 
           agent_name: Optional[str] = None, required_capabilities: Optional[List[str]] = None, **kwargs) -> str:
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