"""
Agent Caller Tools for the Orchestrator
These tools enable the orchestrator to communicate with specialized agents via A2A protocol
"""

import uuid
import json
import asyncio
# import nest_asyncio  # Removed for Python 3.13 compatibility
from typing import Dict, Any, Optional, List
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
import logging
from pathlib import Path

# Note: Removed nest_asyncio.apply() for Python 3.13 compatibility
# Python 3.13 has improved async handling that conflicts with nest_asyncio

from .agent_registry import AgentRegistry
from ..a2a import A2AClient, A2ATask, A2AException

logger = logging.getLogger(__name__)

# Import centralized logging
from src.utils.logging import log_orchestrator_activity


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

class SalesforceAgentTool(BaseTool):
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
    
    def _extract_relevant_context(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant context from global state for the agent"""
        context = {}
        
        # Include conversation summary if available
        if "conversation_summary" in state:
            context["conversation_summary"] = state["conversation_summary"]
        
        # Include recent messages (last 5 for better context)
        if "messages" in state and len(state["messages"]) > 0:
            # Extract the last 5 messages to provide context for references like "this account"
            recent_messages = []
            for msg in state["messages"][-5:]:
                if hasattr(msg, 'content'):
                    recent_messages.append({
                        "role": getattr(msg, '__class__', type(msg)).__name__,
                        "content": msg.content
                    })
            context["recent_messages"] = recent_messages
        
        # Include relevant memory
        if "memory" in state:
            memory = state["memory"]
            if isinstance(memory, dict):
                # Include Salesforce-related memory
                salesforce_memory = {}
                for key, value in memory.items():
                    if any(keyword in key.lower() for keyword in ["account", "lead", "opportunity", "contact", "case", "task", "salesforce"]):
                        salesforce_memory[key] = value
                if salesforce_memory:
                    context["salesforce_memory"] = salesforce_memory
        
        # Include user context
        if "user_context" in state:
            context["user_context"] = state["user_context"]
        
        return context
    
    def _create_state_snapshot(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Create a state snapshot to send to the agent"""
        snapshot = {}
        
        # Include essential state elements
        if "messages" in state:
            snapshot["messages"] = state["messages"]
        
        if "memory" in state:
            snapshot["memory"] = state["memory"]
        
        if "turns" in state:
            snapshot["turns"] = state["turns"]
        
        return snapshot
    
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
            extracted_context = self._extract_relevant_context(state)
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
        """Synchronous wrapper for async execution
        
        Note: This is a compatibility workaround for LangGraph 0.4.x with Python 3.13
        """
        # For Python 3.13 compatibility, avoid using nest_asyncio
        # Instead, check if we're in an async context and handle appropriately
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in a running event loop, but sync code called us
                # Create a new thread to run the async code
                import concurrent.futures
                import threading
                
                result = None
                exception = None
                
                def run_async():
                    nonlocal result, exception
                    try:
                        # Create a new event loop in this thread
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            result = new_loop.run_until_complete(
                                self._arun(instruction, context, **kwargs)
                            )
                        finally:
                            new_loop.close()
                    except Exception as e:
                        exception = e
                
                thread = threading.Thread(target=run_async)
                thread.start()
                thread.join()
                
                if exception:
                    raise exception
                return result
            else:
                # Event loop exists but not running, we can run normally
                return loop.run_until_complete(self._arun(instruction, context, **kwargs))
        except RuntimeError:
            # No event loop at all, create one
            return asyncio.run(self._arun(instruction, context, **kwargs))

class GenericAgentTool(BaseTool):
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
    
    def _extract_relevant_context(self, state: Dict[str, Any], agent_capabilities: List[str]) -> Dict[str, Any]:
        """Extract relevant context based on agent capabilities"""
        context = {}
        
        # Always include conversation summary
        if "conversation_summary" in state:
            context["conversation_summary"] = state["conversation_summary"]
        
        # Include recent messages
        if "messages" in state and len(state["messages"]) > 0:
            context["recent_messages"] = state["messages"][-3:]
        
        # Include relevant memory based on capabilities
        if "memory" in state and isinstance(state["memory"], dict):
            relevant_memory = {}
            for key, value in state["memory"].items():
                # Check if memory key relates to agent capabilities
                if any(capability.lower() in key.lower() for capability in agent_capabilities):
                    relevant_memory[key] = value
            if relevant_memory:
                context["relevant_memory"] = relevant_memory
        
        # Include user context
        if "user_context" in state:
            context["user_context"] = state["user_context"]
        
        return context
    
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
        extracted_context = self._extract_relevant_context(state, agent.agent_card.capabilities)
        if context:
            extracted_context.update(context)
        
        state_snapshot = {
            "messages": state.get("messages", []),
            "memory": state.get("memory", {}),
            "turns": state.get("turns", 0)
        }
        
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
        """Synchronous wrapper for async execution
        
        Note: This is a compatibility workaround for LangGraph 0.4.x with Python 3.13
        """
        # For Python 3.13 compatibility, avoid using nest_asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Run in a new thread with its own event loop
                import threading
                result = None
                exception = None
                
                def run_async():
                    nonlocal result, exception
                    try:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            result = new_loop.run_until_complete(
                                self._arun(instruction, context, agent_name, required_capabilities, **kwargs)
                            )
                        finally:
                            new_loop.close()
                    except Exception as e:
                        exception = e
                
                thread = threading.Thread(target=run_async)
                thread.start()
                thread.join()
                
                if exception:
                    raise exception
                return result
            else:
                return loop.run_until_complete(self._arun(instruction, context, agent_name, required_capabilities, **kwargs))
        except RuntimeError:
            return asyncio.run(self._arun(instruction, context, agent_name, required_capabilities, **kwargs))
            raise

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
        """Synchronous wrapper for async execution
        
        Note: This is a compatibility workaround for LangGraph 0.4.x with Python 3.13
        """
        # For Python 3.13 compatibility, avoid using nest_asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Run in a new thread with its own event loop
                import threading
                result = None
                exception = None
                
                def run_async():
                    nonlocal result, exception
                    try:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            result = new_loop.run_until_complete(
                                self._arun(action, agent_name)
                            )
                        finally:
                            new_loop.close()
                    except Exception as e:
                        exception = e
                
                thread = threading.Thread(target=run_async)
                thread.start()
                thread.join()
                
                if exception:
                    raise exception
                return result
            else:
                return loop.run_until_complete(self._arun(action, agent_name))
        except RuntimeError:
            return asyncio.run(self._arun(action, agent_name))