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
from pathlib import Path

from .agent_registry import AgentRegistry
from ..a2a import A2AClient, A2ATask, A2AException

logger = logging.getLogger(__name__)

# Direct orchestrator logging
def log_orchestrator_activity(operation_type, **data):
    """Direct orchestrator logging for A2A calls"""
    try:
        import json
        from datetime import datetime
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "operation_type": operation_type,
            **data
        }
        
        log_file = Path(__file__).parent.parent.parent / "logs" / "orchestrator.log"
        log_file.parent.mkdir(exist_ok=True)
        
        with open(log_file, 'a') as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - orchestrator - INFO - {json.dumps(log_entry)}\n")
            f.flush()
    except:
        pass


class AgentCallInput(BaseModel):
    """Input schema for agent calls"""
    instruction: str = Field(description="The instruction to send to the specialized agent")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context for the agent")
    agent_name: Optional[str] = Field(default=None, description="Specific agent name to call (optional)")
    required_capabilities: Optional[List[str]] = Field(default=None, description="Required capabilities for agent selection")

class SalesforceAgentTool(BaseTool):
    """Tool for calling the Salesforce specialized agent"""
    name: str = "salesforce_agent"
    description: str = """Call the Salesforce specialized agent for CRM operations including:
    - Lead management (create, get, update leads)
    - Account operations (create, get, update accounts) 
    - Opportunity tracking (create, get, update opportunities)
    - Contact management (create, get, update contacts)
    - Case handling (create, get, update cases)
    - Task management (create, get, update tasks)
    
    Use this tool for any Salesforce CRM related queries or operations."""
    
    args_schema: type = AgentCallInput
    
    def __init__(self, registry: AgentRegistry, debug_mode: bool = False):
        super().__init__(metadata={"registry": registry, "debug_mode": debug_mode})
    
    def _extract_relevant_context(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant context from global state for the agent"""
        context = {}
        
        # Include conversation summary if available
        if "conversation_summary" in state:
            context["conversation_summary"] = state["conversation_summary"]
        
        # Include recent messages (last 3 for context)
        if "messages" in state and len(state["messages"]) > 0:
            context["recent_messages"] = state["messages"][-3:]
        
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
        debug_mode = self.metadata.get("debug_mode", False)
        try:
            if debug_mode:
                logger.info(f"Salesforce agent tool: {instruction[:100]}...")
            
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
                if debug_mode:
                    logger.info(f"Found {len(agent)} agents")
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
            
            if debug_mode:
                print(f"🔥 ORCHESTRATOR A2A TASK DEBUG:")
                print(f"  Task ID: {task_id}")
                print(f"  Instruction: {instruction}")
                print(f"  Context: {extracted_context}")
                print(f"  State snapshot: {state_snapshot}")
            async with A2AClient(debug_mode=debug_mode) as client:
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
                
                
                # Extract the response
                if "artifacts" in result:
                    response = result["artifacts"]
                    
                    if isinstance(response, list) and len(response) > 0:
                        if debug_mode:
                            logger.info(f"Artifacts is list with {len(response)} items")
                        response = response[0]
                        
                    if isinstance(response, dict) and "content" in response:
                        if debug_mode:
                            logger.info("Extracting content from artifact dict")
                        response = response["content"]
                        
                    final_response = str(response)
                    if debug_mode:
                        logger.info(f"Final response length: {len(final_response)}")
                        logger.info(f"Final response preview: {final_response[:200]}...")
                        logger.info(f"=== SALESFORCE AGENT TOOL SUCCESS ===")
                    log_orchestrator_activity("A2A_RESPONSE_SUCCESS",
                                            agent="salesforce-agent", 
                                            task_id=task_id,
                                            response_length=len(final_response))
                    return final_response
                
                fallback_response = str(result.get("result", "No response from Salesforce agent"))
                if debug_mode:
                    logger.info(f"Using fallback response: {fallback_response[:200]}...")
                    logger.info(f"=== SALESFORCE AGENT TOOL SUCCESS (FALLBACK) ===")
                return fallback_response
        
        except A2AException as e:
            if debug_mode:
                logger.error(f"=== SALESFORCE AGENT TOOL A2A ERROR ===")
                logger.error(f"A2AException: {str(e)}")
                logger.error(f"A2AException type: {type(e)}")
            else:
                logger.error(f"Failed to communicate with Salesforce agent: {e}")
            return f"Error: Failed to communicate with Salesforce agent - {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in Salesforce agent tool: {type(e).__name__}: {e}")
            if debug_mode:
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
            return f"Error: Unexpected error - {str(e)}"
    
    def _run(self, instruction: str, context: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        """Synchronous wrapper for async execution"""
        return asyncio.run(self._arun(instruction, context, **kwargs))

class GenericAgentTool(BaseTool):
    """Generic tool for calling any specialized agent"""
    name: str = "call_agent"
    description: str = """Call a specialized agent to handle specific tasks. The orchestrator will automatically 
    select the best agent based on the instruction and required capabilities. Use this for:
    - Travel booking and management
    - Expense reporting and receipt processing  
    - HR tasks and feedback submission
    - Document processing and OCR
    - Any other specialized enterprise system operations"""
    
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
            async with A2AClient(debug_mode=debug_mode) as client:
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
    """Tool for managing the agent registry"""
    name: str = "manage_agents"
    description: str = """Manage the agent registry including:
    - List available agents and their capabilities
    - Check agent health status
    - Get registry statistics
    Use this to understand what agents are available and their current status."""
    
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