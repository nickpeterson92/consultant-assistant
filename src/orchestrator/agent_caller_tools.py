"""
Agent Caller Tools for the Orchestrator
These tools enable the orchestrator to communicate with specialized agents via A2A protocol
"""

import uuid
import json
import asyncio
from typing import Dict, Any, Optional, List, Annotated, Union
from langchain_core.tools import BaseTool
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import BaseModel, Field

from .agent_registry import AgentRegistry
from ..a2a import A2AClient, A2ATask, A2AException

# Import unified logger
from src.utils.logging import get_logger

# Initialize structured logger
logger = get_logger()
from src.utils.config import (
    MESSAGES_KEY, MEMORY_KEY, RECENT_MESSAGES_COUNT
)
from src.utils.agents.message_processing import serialize_recent_messages


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
    """Input schema for delegating tasks to agents."""
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
    
    CRM Capabilities:
    - Lead Management: Lead generation, qualification, conversion tracking
    - Account Operations: Customer account lifecycle, relationship mapping
    - Opportunity Pipeline: Sales forecasting, deal progression, revenue tracking  
    - Contact Management: Customer relationship coordination, communication history
    - Case Management: Customer service tickets, issue resolution, SLA tracking
    - Task Management: Activity coordination, follow-up scheduling, productivity tracking
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
    
    def _run(self, instruction: str, context: Optional[Dict[str, Any]] = None, 
            state: Annotated[Dict[str, Any], InjectedState] = None, **kwargs) -> Union[str, Command]:
        """Synchronous wrapper for async execution."""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self._arun(instruction, context, state, **kwargs)
            )
        finally:
            loop.close()
    
    async def _arun(self, instruction: str, context: Optional[Dict[str, Any]] = None, state: Annotated[Dict[str, Any], InjectedState] = None, **kwargs) -> Command:
        """Execute the Salesforce agent call using Command pattern.
        
        This method orchestrates the entire flow but delegates specific responsibilities
        to focused helper methods for better maintainability.
        """
        # Debug logging to understand state passing
        logger.info("salesforce_tool_debug",
            component="orchestrator",
            operation="salesforce_agent_tool",
            state_type=type(state).__name__ if state else "None",
            state_keys=list(state.keys()) if state and isinstance(state, dict) else [],
            has_messages=bool(state and "messages" in state) if isinstance(state, dict) else False,
            message_count=len(state.get("messages", [])) if state and isinstance(state, dict) else 0
        )
        
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

class JiraAgentTool(BaseAgentTool):
    """Orchestrator Tool for Jira Issue Tracking Agent Communication.
    
    Implements loose coupling between the orchestrator and specialized Jira agent
    via A2A (Agent-to-Agent) protocol. Provides enterprise issue tracking capabilities through
    distributed agent architecture with state management and context preservation.
    
    Jira Capabilities:
    - Issue Management: Create, read, update, transition issues across all types (bug, story, task, epic)
    - JQL Search: Advanced query language for complex searches and filtering
    - Epic Tracking: Parent-child relationships, epic management, story mapping
    - Sprint Management: Active sprint monitoring, velocity tracking, burndown analytics
    - Project Analytics: Dashboard metrics, team velocity, cycle time analysis
    - Agile Workflows: Kanban boards, scrum ceremonies, workflow automation
    """
    name: str = "jira_agent"
    description: str = """Delegates Jira issue tracking operations to specialized agent via A2A protocol.
    
    PRIMARY CAPABILITIES:
    - Issue Management: Create, read, update all issue types (create/get/update issues)
    - JQL Search: Advanced queries for complex filtering (search with JQL syntax)
    - Epic Tracking: Parent-child relationships, story mapping (manage epics and stories)
    - Sprint Management: Active sprint monitoring, velocity (track sprint progress)
    - Project Analytics: Dashboards, team metrics, cycle time (analyze project health)
    - Agile Workflows: Kanban/Scrum boards, transitions (manage workflow states)
    - Bug Tracking: Find bugs, track resolution, monitor SLAs
    
    CRITICAL - NATURAL LANGUAGE PASSTHROUGH:
    Pass the user's EXACT words to the Jira agent without translation or modification.
    The Jira agent understands natural language in issue tracking context.
    
    EXAMPLES OF CORRECT PASSTHROUGH:
    - User: "find bugs in the IM project" → Pass: "find bugs in the IM project"
    - User: "show me critical issues" → Pass: "show me critical issues"
    - User: "what's in the current sprint" → Pass: "what's in the current sprint"
    
    The Jira agent handles ALL issue tracking operations and will interpret the user's intent.
    
    Returns structured issue data with Jira IDs for downstream processing."""
    
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
    
    def _find_jira_agent(self):
        """Locate the Jira agent in the registry.
        
        Returns:
            Agent instance or None if not found
        """
        registry = self.metadata["registry"]
        agent = registry.find_agents_by_capability("jira_operations")
        
        if not agent:
            logger.warning("Jira agent not found by capability, trying by name...")
            agent = registry.get_agent("jira-agent")
        
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
                tool_name="jira_agent",
                data_preview=str(tool_results_data)[:200],
                data_size=len(json.dumps(tool_results_data)),
                record_count=len(tool_results_data) if isinstance(tool_results_data, list) else 1,
                agent="jira-agent",
                task_id=task_id
            )
            return final_response
        else:
            return response_content
    
    def _run(self, instruction: str, context: Optional[Dict[str, Any]] = None, 
            state: Annotated[Dict[str, Any], InjectedState] = None, **kwargs) -> Union[str, Command]:
        """Synchronous wrapper for async execution."""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self._arun(instruction, context, state, **kwargs)
            )
        finally:
            loop.close()
    
    async def _arun(self, instruction: str, context: Optional[Dict[str, Any]] = None, state: Annotated[Dict[str, Any], InjectedState] = None, **kwargs) -> Command:
        """Execute the Jira agent call using Command pattern.
        
        This method orchestrates the entire flow but delegates specific responsibilities
        to focused helper methods for better maintainability.
        """
        # Debug logging to understand state passing
        logger.info("jira_tool_debug",
            component="orchestrator",
            operation="jira_agent_tool",
            state_type=type(state).__name__ if state else "None",
            state_keys=list(state.keys()) if state and isinstance(state, dict) else [],
            has_messages=bool(state and "messages" in state) if isinstance(state, dict) else False,
            message_count=len(state.get("messages", [])) if state and isinstance(state, dict) else 0
        )
        
        # Log tool invocation start
        tool_call_id = kwargs.get("tool_call_id", None)
        logger.info("tool_invocation_start",
            component="orchestrator",
            operation="jira_agent_tool",
            tool_name="jira_agent",
            tool_call_id=tool_call_id,
            instruction_preview=instruction[:100] if instruction else "",
            has_context=bool(context),
            has_state=bool(state)
        )
        
        try:
            # Extract and serialize conversation context
            extracted_context = self._extract_conversation_context(state, context)
            
            # Find the Jira agent
            agent = self._find_jira_agent()
            if not agent:
                logger.error("agent_not_found",
                    component="orchestrator",
                    operation="jira_agent_tool",
                    agent_type="jira",
                    tool_call_id=tool_call_id,
                    error="Jira agent not available"
                )
                return self._create_error_command(
                    "Error: Jira agent not available. Please ensure the Jira agent is running and registered.",
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
                    agent="jira-agent",
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
                    agent="jira-agent", 
                    task_id=task_id,
                    response_length=len(final_response)
                )
                
                # Log successful tool completion
                logger.info("tool_invocation_complete",
                    component="orchestrator",
                    operation="jira_agent_tool",
                    tool_name="jira_agent",
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
                                name="jira_agent"
                            )]
                        }
                    )
                else:
                    # Return plain response when called without tool_call_id
                    return final_response
        
        except A2AException as e:
            logger.error("tool_invocation_error",
                component="orchestrator",
                operation="jira_agent_tool",
                tool_name="jira_agent",
                tool_call_id=tool_call_id,
                error_type="A2AException",
                error=str(e)
            )
            return self._create_error_command(
                f"Error: Failed to communicate with Jira agent - {str(e)}",
                tool_call_id
            )
        except Exception as e:
            logger.error("tool_invocation_error",
                component="orchestrator",
                operation="jira_agent_tool",
                tool_name="jira_agent",
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


class ServiceNowAgentTool(BaseAgentTool):
    """Orchestrator Tool for ServiceNow ITSM Agent Communication.
    
    Implements loose coupling between the orchestrator and specialized ServiceNow agent
    via A2A (Agent-to-Agent) protocol. Provides enterprise IT Service Management capabilities
    through distributed agent architecture with state management and context preservation.
    
    ITSM Capabilities:
    - Incident Management: Create, read, update incidents with full lifecycle support
    - Change Management: Handle standard, normal, and emergency changes
    - Problem Management: Root cause analysis and known error tracking
    - Task Management: Generic task operations across all tables
    - User & CMDB: User lookups and configuration item management
    - Global Search: Flexible queries with encoded query support
    """
    name: str = "servicenow_agent"
    description: str = """Delegates ServiceNow ITSM operations to specialized agent via A2A protocol.
    
    PRIMARY CAPABILITIES:
    - Incident Management: Create, read, update incidents (create/get/update incidents)
    - Change Management: Handle change requests through lifecycle (create/get/update changes)
    - Problem Management: Root cause analysis, known errors (create/get/update problems)
    - Task Management: Generic task operations (create/get/update tasks)
    - User & CMDB: User lookups and CI management (get users, get CIs)
    - Global Search: Flexible queries across any table with encoded queries
    
    CRITICAL - NATURAL LANGUAGE PASSTHROUGH:
    Pass the user's EXACT words to the ServiceNow agent without translation or modification.
    The ServiceNow agent understands natural language in ITSM context.
    
    EXAMPLES OF CORRECT PASSTHROUGH:
    - User: "show me all P1 incidents" → Pass: "show me all P1 incidents"
    - User: "create emergency change for server restart" → Pass: "create emergency change for server restart"
    - User: "find problems related to email" → Pass: "find problems related to email"
    
    The ServiceNow agent handles ALL ITSM operations and will interpret the user's intent.
    
    Returns structured ITSM data with record numbers for downstream processing."""
    
    def __init__(self, registry: AgentRegistry):
        super().__init__(metadata={"registry": registry})
    
    def _run(self, instruction: str, context: Optional[Dict[str, Any]] = None, 
            state: Annotated[Dict[str, Any], InjectedState] = None, **kwargs) -> Union[str, Command]:
        """Synchronous wrapper for async execution."""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self._arun(instruction, context, state, **kwargs)
            )
        finally:
            loop.close()
    
    async def _arun(self, instruction: str, context: Optional[Dict[str, Any]] = None, 
                    state: Annotated[Dict[str, Any], InjectedState] = None, **kwargs) -> Command:
        """Execute the ServiceNow agent call using Command pattern."""
        # Log tool invocation start
        tool_call_id = kwargs.get("tool_call_id", None)
        logger.info("tool_invocation_start",
            component="orchestrator",
            operation="servicenow_agent_tool",
            tool_name="servicenow_agent",
            tool_call_id=tool_call_id,
            instruction_preview=instruction[:100] if instruction else "",
            has_context=bool(context),
            has_state=bool(state)
        )
        
        try:
            # Extract relevant context
            extracted_context = self._extract_relevant_context(
                state, 
                filter_keywords=["incident", "change", "problem", "task", "cmdb", "user"],
                message_count=5
            )
            
            # Merge with provided context
            if context:
                extracted_context.update(context)
            
            # Find the ServiceNow agent
            registry = self.metadata["registry"]
            agent = registry.find_agents_by_capability("servicenow_operations")
            
            if not agent:
                logger.warning("ServiceNow agent not found by capability, trying by name...")
                agent = registry.get_agent("servicenow-agent")
            
            # Handle list return from find_agents_by_capability
            if isinstance(agent, list) and agent:
                agent = agent[0]
            
            if not agent:
                logger.error("agent_not_found",
                    component="orchestrator",
                    operation="servicenow_agent_tool",
                    agent_type="servicenow",
                    tool_call_id=tool_call_id,
                    error="ServiceNow agent not available"
                )
                return self._create_error_command(
                    "Error: ServiceNow agent not available. Please ensure the ServiceNow agent is running and registered.",
                    tool_call_id
                )
            
            # Create A2A task
            task_id = str(uuid.uuid4())
            state_snapshot = self._create_state_snapshot(state) if state else {}
            
            task = A2ATask(
                id=task_id,
                instruction=instruction,
                context=extracted_context,
                state_snapshot=state_snapshot
            )
            
            # Execute A2A call
            async with A2AClient() as client:
                endpoint = agent.endpoint + "/a2a"
                
                # Log A2A dispatch
                logger.info("a2a_dispatch", 
                    component="orchestrator",
                    agent="servicenow-agent",
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
                    agent="servicenow-agent", 
                    task_id=task_id,
                    response_length=len(final_response)
                )
                
                # Log successful tool completion
                logger.info("tool_invocation_complete",
                    component="orchestrator",
                    operation="servicenow_agent_tool",
                    tool_name="servicenow_agent",
                    tool_call_id=tool_call_id,
                    response_length=len(final_response),
                    success=True
                )
                
                # Return Command with processed response
                if tool_call_id:
                    return Command(
                        update={
                            "messages": [ToolMessage(
                                content=final_response,
                                tool_call_id=tool_call_id,
                                name="servicenow_agent"
                            )]
                        }
                    )
                else:
                    return final_response
        
        except A2AException as e:
            logger.error("tool_invocation_error",
                component="orchestrator",
                operation="servicenow_agent_tool",
                tool_name="servicenow_agent",
                tool_call_id=tool_call_id,
                error_type="A2AException",
                error=str(e)
            )
            return self._create_error_command(
                f"Error: Failed to communicate with ServiceNow agent - {str(e)}",
                tool_call_id
            )
        except Exception as e:
            logger.error("tool_invocation_error",
                component="orchestrator",
                operation="servicenow_agent_tool",
                tool_name="servicenow_agent",
                tool_call_id=tool_call_id,
                error_type=type(e).__name__,
                error=str(e)
            )
            return self._create_error_command(
                f"Error: Unexpected error - {str(e)}",
                tool_call_id
            )
    
    def _create_error_command(self, error_message: str, tool_call_id: Optional[str] = None):
        """Create a standardized error Command response."""
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
            return error_message
    
    def _extract_response_content(self, result: Dict[str, Any]) -> str:
        """Extract response content from A2A result."""
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
        """Process and augment response with structured tool data."""
        # Check for tool results in state_updates
        tool_results_data = None
        if "state_updates" in result and "tool_results" in result["state_updates"]:
            tool_results_data = result["state_updates"]["tool_results"]
        
        if tool_results_data:
            final_response = response_content + "\n\n[STRUCTURED_TOOL_DATA]:\n" + json.dumps(tool_results_data, indent=2)
            
            # Log structured data addition
            logger.info("structured_data_found",
                component="orchestrator",
                tool_name="servicenow_agent",
                data_preview=str(tool_results_data)[:200],
                data_size=len(json.dumps(tool_results_data)),
                record_count=len(tool_results_data) if isinstance(tool_results_data, list) else 1,
                agent="servicenow-agent",
                task_id=task_id
            )
            return final_response
        else:
            return response_content


class WorkflowAgentTool(BaseAgentTool):
    """Tool for executing complex multi-step workflows across systems."""
    
    name: str = "workflow_agent"
    description: str = """Delegates workflow orchestration to the specialized Workflow Agent via A2A protocol.
    
    PRIMARY USE CASES:
    - Multi-step processes spanning multiple systems (Salesforce + Jira + ServiceNow)
    - Complex workflows with conditional logic and dependencies
    - Automated recurring analysis and reporting
    - Operations requiring coordinated actions across agents
    
    AVAILABLE WORKFLOWS:
    - Deal Risk Assessment: Check for at-risk deals/opportunities and create action plans
    - Incident to Resolution: Full incident lifecycle from creation to resolution
    - Customer 360 Report: Comprehensive customer data from all systems
    - Weekly Account Health Check: Analyze key account health metrics
    - New Customer Onboarding: Automated setup across all systems
    
    KEY PHRASES THAT TRIGGER WORKFLOWS:
    - "check for at-risk deals" → Deal Risk Assessment
    - "analyze deal risks" → Deal Risk Assessment
    - "handle incident resolution" → Incident to Resolution
    - "customer 360" or "everything about [customer]" → Customer 360 Report
    - "account health check" → Weekly Account Health Check
    - "onboard new customer" → New Customer Onboarding
    
    EXAMPLES:
    - "Check for at-risk deals and create action plans"
    - "Run the incident to resolution workflow for case 12345"
    - "Generate a customer 360 report for Acme Corp"
    - "Perform health check on our key accounts"
    - "Start onboarding workflow for new customer TechCorp"
    """
    
    args_schema: type = AgentCallInput
    return_direct: bool = False
    
    def __init__(self, agent_registry: AgentRegistry):
        super().__init__(metadata={"registry": agent_registry})
    
    async def _arun(self, instruction: str, context: Optional[Dict[str, Any]] = None, 
                   state: Annotated[Dict[str, Any], InjectedState] = None, **kwargs) -> Union[str, Command]:
        """Execute the workflow agent call asynchronously."""
        # Extract tool_call_id if provided
        tool_call_id = kwargs.get("tool_call_id")
        
        # Find workflow agent
        registry = self.metadata.get("registry")
        if not registry:
            return self._create_error_command(
                "Error: Agent registry not available",
                tool_call_id
            )
        
        agent = registry.get_agent("workflow-agent")
        if not agent:
            # Try finding by capability
            agents = registry.find_agents_by_capability("workflow_orchestration")
            if agents and isinstance(agents, list):
                agent = agents[0]
        
        if not agent:
            return self._create_error_command(
                "Error: Workflow agent is not available",
                tool_call_id
            )
        
        # Extract context from state
        extracted_context = {}
        if state:
            # Include recent messages
            if "messages" in state and state["messages"]:
                recent_messages = serialize_recent_messages(state["messages"], count=5)
                if recent_messages:
                    extracted_context["recent_messages"] = recent_messages
            
            # Include memory
            if "memory" in state:
                extracted_context["memory"] = state["memory"]
            
            # Include summary
            if "summary" in state:
                extracted_context["conversation_summary"] = state["summary"]
        
        # Merge provided context
        if context:
            extracted_context.update(context)
        
        # Check if we're resuming an interrupted workflow
        interrupted_workflow = state.get("interrupted_workflow") if state else None
        if interrupted_workflow:
            # Use the existing thread_id to resume
            task_id = interrupted_workflow.get("thread_id", interrupted_workflow.get("task_id"))
            logger.info("resuming_interrupted_workflow_from_orchestrator",
                component="orchestrator",
                tool_name="workflow_agent",
                workflow_name=interrupted_workflow.get("workflow_name"),
                original_task_id=interrupted_workflow.get("task_id"),
                thread_id=task_id,
                instruction_preview=instruction[:100]
            )
        else:
            # Create new task ID for new workflow
            task_id = f"workflow-{uuid.uuid4().hex[:8]}"
        
        # Create state snapshot for A2A transmission
        state_snapshot = self._create_state_snapshot(state) if state else {}
        
        task = A2ATask(
            id=task_id,
            instruction=instruction,
            context=extracted_context,
            state_snapshot=state_snapshot
        )
        
        logger.info("workflow_agent_call",
            component="orchestrator",
            agent="workflow-agent",
            task_id=task_id,
            instruction_preview=instruction[:100],
            context_keys=list(extracted_context.keys())
        )
        
        try:
            async with A2AClient() as client:
                endpoint = agent.endpoint + "/a2a"
                result = await client.process_task(endpoint=endpoint, task=task)
                
                # Log raw result for debugging
                logger.info("workflow_agent_raw_result",
                    component="orchestrator",
                    tool_name="workflow_agent",
                    task_id=task_id,
                    result_keys=list(result.keys()) if isinstance(result, dict) else "not_dict",
                    has_artifacts="artifacts" in result if isinstance(result, dict) else False
                )
                
                # Extract response - workflow agent now returns content directly
                response_content = ""
                if "artifacts" in result:
                    artifacts = result["artifacts"]
                    if isinstance(artifacts, list) and artifacts:
                        artifact = artifacts[0]
                        if isinstance(artifact, dict) and "content" in artifact:
                            # Workflow agent returns the report directly as content
                            response_content = artifact["content"]
                            logger.info("workflow_content_extracted",
                                component="orchestrator",
                                tool_name="workflow_agent",
                                content_preview=response_content[:100],
                                starts_with_human_input=response_content.startswith("WORKFLOW_HUMAN_INPUT_REQUIRED:")
                            )
                        else:
                            response_content = str(artifact)
                    else:
                        response_content = str(artifacts)
                elif "response" in result:
                    response_content = result["response"]
                else:
                    response_content = str(result)
                
                # Check if workflow needs human input
                if response_content.startswith("WORKFLOW_HUMAN_INPUT_REQUIRED:"):
                    logger.info("workflow_human_input_detected",
                        component="orchestrator",
                        tool_name="workflow_agent",
                        response_preview=response_content[:100]
                    )
                    # Parse the human interaction data
                    try:
                        interaction_json = response_content.replace("WORKFLOW_HUMAN_INPUT_REQUIRED:", "", 1)
                        interaction_data = json.loads(interaction_json) if interaction_json else {}
                        
                        # Get metadata from result if available
                        metadata = result.get("metadata", {})
                        workflow_name = metadata.get("workflow_name", "")
                        thread_id = metadata.get("thread_id", task_id)
                        
                        # Extract the context for better formatting
                        step_desc = interaction_data.get("description", "Human input required")
                        context = interaction_data.get("context", {})
                        workflow_id = interaction_data.get("workflow_id", workflow_name)
                        
                        # Build a user-friendly message based on context
                        message = step_desc
                        
                        # If we have step results, include the most recent one
                        if context.get("step_results"):
                            # Get the last step result for context
                            step_results = context["step_results"]
                            if step_results:
                                # Find the most recent result
                                for key in reversed(list(step_results.keys())):
                                    if step_results[key]:
                                        message += f"\n\n{step_results[key]}"
                                        break
                        
                        # Add any additional instruction from context
                        if context.get("instruction"):
                            message += f"\n\n{context['instruction']}"
                        
                        # Store workflow state for resume
                        interrupt_state = {
                            "workflow_name": workflow_name,
                            "thread_id": thread_id,
                            "task_id": task_id,
                            "interrupt_data": interaction_data
                        }
                        
                        logger.info("workflow_interrupt_command_check",
                            component="orchestrator",
                            tool_name="workflow_agent",
                            has_tool_call_id=bool(tool_call_id),
                            tool_call_id=tool_call_id,
                            interrupt_state=interrupt_state
                        )
                        
                        if tool_call_id:
                            # When called through tool node with tool_call_id
                            logger.info("workflow_command_created",
                                component="orchestrator",
                                tool_name="workflow_agent",
                                workflow_id=workflow_id,
                                has_tool_call_id=True,
                                interrupted_workflow=interrupt_state
                            )
                            return Command(
                                update={
                                    "messages": [ToolMessage(
                                        content=message,
                                        tool_call_id=tool_call_id,
                                        name="workflow_agent"
                                    )],
                                    "interrupted_workflow": interrupt_state
                                }
                            )
                        else:
                            # When called directly without tool_call_id, still return Command
                            # but without ToolMessage (just the content)
                            logger.info("workflow_command_created_no_tool_id",
                                component="orchestrator",
                                tool_name="workflow_agent",
                                workflow_id=workflow_id,
                                interrupted_workflow=interrupt_state
                            )
                            return Command(
                                update={
                                    "messages": [message],
                                    "interrupted_workflow": interrupt_state
                                }
                            )
                    except Exception as e:
                        logger.error("workflow_human_input_parse_error",
                            component="orchestrator",
                            error=str(e),
                            response_preview=response_content[:200]
                        )
                        # Fall through to normal response handling
                
                logger.info("workflow_agent_response",
                    component="orchestrator",
                    agent="workflow-agent",
                    task_id=task_id,
                    response_length=len(response_content)
                )
                
                # Check if workflow completed (not interrupted)
                workflow_update = {}
                if interrupted_workflow and not response_content.startswith("WORKFLOW_HUMAN_INPUT_REQUIRED:"):
                    # Workflow completed, clear the interrupted state
                    workflow_update["interrupted_workflow"] = None
                    logger.info("clearing_completed_workflow",
                        component="orchestrator",
                        tool_name="workflow_agent",
                        workflow_name=interrupted_workflow.get("workflow_name"),
                        task_id=task_id
                    )
                
                # Return response
                if tool_call_id:
                    return Command(
                        update={
                            "messages": [ToolMessage(
                                content=response_content,
                                tool_call_id=tool_call_id,
                                name="workflow_agent"
                            )],
                            **workflow_update
                        }
                    )
                else:
                    return response_content
                    
        except Exception as e:
            logger.error("workflow_agent_error",
                component="orchestrator",
                agent="workflow-agent",
                task_id=task_id,
                error=str(e),
                error_type=type(e).__name__
            )
            return self._create_error_command(
                f"Error communicating with workflow agent: {str(e)}",
                tool_call_id
            )
    
    def _run(self, instruction: str, context: Optional[Dict[str, Any]] = None, 
            state: Annotated[Dict[str, Any], InjectedState] = None, **kwargs) -> Union[str, Command]:
        """Synchronous wrapper for async execution."""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self._arun(instruction, context, state, **kwargs)
            )
        finally:
            loop.close()
    
    def _create_error_command(self, error_message: str, tool_call_id: Optional[str] = None):
        """Create a standardized error Command response."""
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
            return error_message


class AgentRegistryTool(BaseTool):
    """Orchestrator Tool for Multi-Agent System Management and Monitoring.
    
    Provides comprehensive agent lifecycle management, health monitoring, and
    system observability for distributed agent architectures. Implements
    service discovery patterns and operational intelligence for agent ecosystems.
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
    
    async def _arun(self, action: str, agent_name: Optional[str] = None, state: Optional[Dict[str, Any]] = None) -> str:
        """Execute registry management action"""
        # Note: state is passed by the tool execution framework but not needed for registry operations
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
    
    def _run(self, action: str, agent_name: Optional[str] = None, state: Optional[Dict[str, Any]] = None) -> str:
        """Synchronous wrapper for async execution"""
        return asyncio.run(self._arun(action, agent_name, state))