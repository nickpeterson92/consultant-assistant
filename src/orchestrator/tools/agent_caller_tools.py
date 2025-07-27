"""
Agent Caller Tools for the Orchestrator
These tools enable the orchestrator to communicate with specialized agents via A2A protocol
"""

import uuid
import json
import asyncio
from typing import Dict, Any, Optional, List, Annotated, Union, Type
from langchain_core.tools import BaseTool
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import BaseModel, Field

from src.orchestrator.core.agent_registry import AgentRegistry
from src.a2a import A2AClient, A2ATask, A2AException

# Import smart logger
from src.utils.logging import get_smart_logger, log_execution
from src.utils.config import (
    MESSAGES_KEY, MEMORY_KEY, RECENT_MESSAGES_COUNT
)
from src.utils.agents.message_processing.unified_serialization import serialize_messages_for_json
from src.orchestrator.observers.direct_call_events import (
    emit_agent_call_event, 
    DirectCallEventTypes
)

# Initialize structured logger
logger = get_smart_logger("orchestrator")


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
            recent_messages = serialize_messages_for_json(state[MESSAGES_KEY], limit=message_count)
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
        
        # Include user_id from configurable if available
        if "configurable" in state and "user_id" in state["configurable"]:
            context["user_id"] = state["configurable"]["user_id"]
        
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
    
    def _extract_memory_insights(self, memory_context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant memory insights for agent consumption.
        
        Args:
            memory_context: Memory context from MemoryContextBuilder
            
        Returns:
            Formatted memory insights for agents
        """
        insights = {}
        
        # Extract relevant entities with importance scores
        if "entities" in memory_context:
            insights["relevant_entities"] = [
                {
                    "type": entity.get("type", "unknown"),
                    "name": entity.get("name", ""),
                    "id": entity.get("id", ""),
                    "importance_score": entity.get("importance", 0.0),
                    "last_accessed": entity.get("timestamp", ""),
                    "related_items": entity.get("related", [])
                }
                for entity in memory_context["entities"][:10]  # Limit to top 10
            ]
        
        # Extract execution patterns
        if "patterns" in memory_context:
            insights["execution_patterns"] = memory_context["patterns"]
        
        # Extract memory clusters
        if "clusters" in memory_context:
            insights["memory_clusters"] = [
                {
                    "cluster_id": f"cluster_{i}",
                    "members": cluster.get("nodes", [])[:5],  # Limit members
                    "theme": cluster.get("theme", "related entities")
                }
                for i, cluster in enumerate(memory_context["clusters"][:5])  # Limit clusters
            ]
        
        # Extract bridge nodes
        if "bridges" in memory_context:
            insights["bridge_nodes"] = [
                {
                    "node": bridge.get("node", ""),
                    "connects": bridge.get("connects", []),
                    "importance": bridge.get("importance", 0.0)
                }
                for bridge in memory_context["bridges"][:5]  # Limit bridges
            ]
        
        return insights
    
    def _get_agent_schema_context(self) -> Dict[str, Any]:
        """Get schema context relevant to this specific agent.
        
        Override in subclasses for agent-specific schema.
        
        Returns:
            Schema knowledge relevant to the agent
        """
        # Base implementation returns empty
        # Subclasses should override with their specific schema
        return {}
    
    def _extract_execution_insights(self, execution_history: Any) -> Dict[str, Any]:
        """Extract execution insights from history.
        
        Args:
            execution_history: Execution history from state
            
        Returns:
            Formatted execution insights
        """
        insights = {
            "recent_successes": [],
            "recent_failures": [],
            "user_preferences": {}
        }
        
        # This is a placeholder - actual implementation would extract
        # real execution patterns from the history
        return insights


class AgentCallInput(BaseModel):
    """Input schema for delegating tasks to agents."""
    instruction: str = Field(
        description="Clear, optimized instruction for the target agent based on user intent. "
        "Analyze the user's request and enhance it with relevant context, specific parameters, and actionable details."
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
    state: Annotated[dict, InjectedState] = Field(
        description="Injected state from LangGraph for accessing conversation context"
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
    
    INTELLIGENT COORDINATION:
    Analyze the user's request and provide clear, optimized instructions to the Salesforce agent.
    Transform vague requests into specific, actionable instructions while respecting operation boundaries.
    
    The Salesforce agent benefits from specific, well-structured instructions that leverage conversation context.
    
    Returns structured CRM data with Salesforce IDs for downstream processing."""
    
    # Re-enabled args_schema with proper InjectedState field
    # Fixed according to: https://github.com/langchain-ai/langgraph/issues/2220
    args_schema: Type[BaseModel] = AgentCallInput
    
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
        # State should always be provided now with proper InjectedState
        if state is None:
            logger.error("state_is_none",
                        component="orchestrator",
                        note="InjectedState not working properly")
            state = {}
        
        messages = state.get("messages", [])
        memory = state.get("memory", {})
        
        extracted_context = {}
        
        # Include recent messages using centralized serialization
        if messages:
            recent_messages = serialize_messages_for_json(messages, limit=5)
            if recent_messages:
                extracted_context["recent_messages"] = recent_messages
        
        # Include memory data
        if memory:
            extracted_context["memory"] = memory
        
        # Include conversation summary if available  
        if state and "summary" in state:
            extracted_context["conversation_summary"] = state["summary"]
        
        # Include user_id if available in state (check both direct and configurable)
        if state:
            if "user_id" in state:
                extracted_context["user_id"] = state["user_id"]
                logger.debug("found_user_id_in_state", user_id=state["user_id"])
            elif "configurable" in state and "user_id" in state["configurable"]:
                extracted_context["user_id"] = state["configurable"]["user_id"]
                logger.debug("found_user_id_in_configurable", user_id=state["configurable"]["user_id"])
            else:
                logger.warning("no_user_id_found", 
                    has_configurable="configurable" in state,
                    configurable_keys=list(state.get("configurable", {}).keys()) if "configurable" in state else [])
            
            # Include thread_id if available in state
            if "thread_id" in state:
                extracted_context["thread_id"] = state["thread_id"]
                logger.debug("found_thread_id_in_state", thread_id=state["thread_id"])
            elif "configurable" in state and "thread_id" in state["configurable"]:
                extracted_context["thread_id"] = state["configurable"]["thread_id"]
                logger.debug("found_thread_id_in_configurable", thread_id=state["configurable"]["thread_id"])
            else:
                logger.warning("no_thread_id_found",
                    has_configurable="configurable" in state,
                    configurable_keys=list(state.get("configurable", {}).keys()) if "configurable" in state else [],
                    state_keys=list(state.keys()) if state else [])
        else:
            # State should not be None with proper InjectedState
            logger.error("state_is_none_in_extract",
                        component="orchestrator",
                        method="_extract_conversation_context")
        
        # Merge any additional context
        if context:
            extracted_context.update(context)
        
        # NEW: Add enhanced memory context if available
        if state and "memory_context" in state:
            extracted_context["memory_insights"] = self._extract_memory_insights(state["memory_context"])
            logger.debug("added_memory_insights", 
                        entities_count=len(extracted_context["memory_insights"].get("relevant_entities", [])))
        
        # NEW: Add schema knowledge relevant to this agent
        schema_context = self._get_agent_schema_context()
        if schema_context:
            extracted_context["schema_knowledge"] = schema_context
            logger.debug("added_schema_knowledge", agent=getattr(self, 'agent_name', 'unknown'))
        
        # NEW: Add execution insights if available
        if state and "execution_history" in state:
            extracted_context["execution_insights"] = self._extract_execution_insights(state["execution_history"])
            logger.debug("added_execution_insights")
        
        return extracted_context
    
    def _get_agent_schema_context(self) -> Dict[str, Any]:
        """Get Salesforce-specific schema context using existing schema knowledge.
        
        Returns:
            Schema knowledge for Salesforce objects and relationships
        """
        try:
            from src.utils.schema_knowledge import get_schema_knowledge
            schema_knowledge = get_schema_knowledge()
            
            # Get Salesforce-specific schemas
            salesforce_schemas = {}
            for obj_type in ["Account", "Contact", "Opportunity", "Lead", "Case", "Task"]:
                schema_entry = schema_knowledge.lookup_schema("salesforce", obj_type.lower())
                if schema_entry:
                    salesforce_schemas[obj_type] = schema_entry.schema
            
            return salesforce_schemas
        except Exception as e:
            logger.warning("failed_to_get_schema_context", error=str(e))
            return {}
    
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
                    serialized_state[key] = serialize_messages_for_json(value, limit=5)
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
                content = response["content"]
                
                # Handle structured response formats from different agents
                if isinstance(content, dict):
                    # Jira agent returns {"response": "text", "tool_results": data, "issue_keys": []}
                    if "response" in content:
                        response_content = content["response"]
                    else:
                        # Fallback to JSON string representation
                        response_content = str(content)
                else:
                    response_content = content
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
        # Tool results are now stored in persistent memory, not in state_updates
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
    
    @log_execution(component="orchestrator", operation="salesforce_agent_call")
    async def _arun(self, instruction: str, context: Optional[Dict[str, Any]] = None, state: Annotated[Dict[str, Any], InjectedState] = None, **kwargs) -> Command:
        """Execute the Salesforce agent call using Command pattern.
        
        This method orchestrates the entire flow but delegates specific responsibilities
        to focused helper methods for better maintainability.
        """
        # Debug logging to understand state passing
        logger.info("salesforce_tool_debug",
            operation="salesforce_agent_tool",
            state_type=type(state).__name__ if state else "None",
            state_keys=list(state.keys()) if state and isinstance(state, dict) else [],
            has_messages=bool(state and "messages" in state) if isinstance(state, dict) else False,
            message_count=len(state.get("messages", [])) if state and isinstance(state, dict) else 0
        )
        
        # Log tool invocation start
        tool_call_id = kwargs.get("tool_call_id", None)
        task_id = str(uuid.uuid4())
        
        logger.info("tool_invocation_start",
            operation="salesforce_agent_tool",
            tool_name="salesforce_agent",
            tool_call_id=tool_call_id,
            instruction_preview=instruction[:100] if instruction else "",
            has_context=bool(context),
            has_state=bool(state)
        )
        
        # Emit agent call started event
        emit_agent_call_event(
            DirectCallEventTypes.AGENT_CALL_STARTED,
            agent_name="salesforce_agent",
            task_id=task_id,
            instruction=instruction,
            additional_data={
                "tool_call_id": tool_call_id,
                "has_context": bool(context)
            }
        )
        
        try:
            # Extract and serialize conversation context
            extracted_context = self._extract_conversation_context(state, context)
            
            # Find the Salesforce agent
            agent = self._find_salesforce_agent()
            if not agent:
                logger.error("agent_not_found",
                    operation="salesforce_agent_tool",
                    agent_type="salesforce",
                    tool_call_id=tool_call_id,
                    error="Salesforce agent not available"
                )
                # Emit failure event
                emit_agent_call_event(
                    DirectCallEventTypes.AGENT_CALL_FAILED,
                    agent_name="salesforce_agent",
                    task_id=task_id,
                    instruction=instruction,
                    additional_data={
                        "error": "Salesforce agent not available",
                        "tool_call_id": tool_call_id
                    }
                )
                return self._create_error_command(
                    "Error: Salesforce agent not available. Please ensure the Salesforce agent is running and registered.",
                    tool_call_id
                )
            
            # Create A2A task with serialized state (reuse task_id from above)
            serialized_state = self._serialize_state_snapshot(state)
            
            task = A2ATask(
                id=task_id,
                instruction=instruction,
                context=extracted_context,
                state_snapshot=serialized_state
            )
            
            # Execute A2A call using connection pool
            async with A2AClient(use_pool=True) as client:
                endpoint = agent.endpoint + "/a2a"
                
                # Log A2A dispatch
                logger.info("a2a_dispatch", 
                    agent="salesforce-agent",
                    task_id=task_id,
                    instruction_preview=instruction[:100],
                    endpoint=endpoint,
                    context_keys=list(extracted_context.keys()),
                    context_size=len(str(extracted_context))
                )
                
                result = await client.process_task(endpoint=endpoint, task=task)
                
                # Log the raw A2A response
                logger.info("a2a_raw_response",
                    agent="salesforce-agent",
                    task_id=task_id,
                    raw_response=result,
                    artifacts=result.get("artifacts") if isinstance(result, dict) else None,
                    state_updates=result.get("state_updates") if isinstance(result, dict) else None
                )
                
                # Process response
                response_content = self._extract_response_content(result)
                final_response = self._process_tool_results(result, response_content, task_id)
                
                logger.info("a2a_response_success",
                    agent="salesforce-agent", 
                    task_id=task_id,
                    response_length=len(final_response),
                    final_response_preview=final_response[:500] if len(final_response) > 500 else final_response
                )
                
                # Log successful tool completion
                logger.info("tool_invocation_complete",
                    operation="salesforce_agent_tool",
                    tool_name="salesforce_agent",
                    tool_call_id=tool_call_id,
                    response_length=len(final_response),
                    success=True
                )
                
                # Emit agent call completed event
                emit_agent_call_event(
                    DirectCallEventTypes.AGENT_CALL_COMPLETED,
                    agent_name="salesforce_agent",
                    task_id=task_id,
                    instruction=instruction,
                    additional_data={
                        "tool_call_id": tool_call_id,
                        "response_length": len(final_response),
                        "response_preview": final_response[:200] if final_response else ""
                    }
                )
                
                # No state merging needed - tool results are in persistent memory
                state_update = {}
                
                # Return Command with processed response and merged state
                # If we have a tool_call_id, return a ToolMessage, otherwise return the content directly
                if tool_call_id:
                    state_update["messages"] = [ToolMessage(
                        content=final_response,
                        tool_call_id=tool_call_id,
                        name="salesforce_agent"
                    )]
                    return Command(update=state_update)
                else:
                    # Return plain response when called without tool_call_id
                    return final_response
        
        except A2AException as e:
            logger.error("tool_invocation_error",
                operation="salesforce_agent_tool",
                tool_name="salesforce_agent",
                tool_call_id=tool_call_id,
                error_type="A2AException",
                error=str(e)
            )
            # Emit failure event
            emit_agent_call_event(
                DirectCallEventTypes.AGENT_CALL_FAILED,
                agent_name="salesforce_agent",
                task_id=task_id,
                instruction=instruction,
                additional_data={
                    "error": str(e),
                    "error_type": "A2AException",
                    "tool_call_id": tool_call_id
                }
            )
            return self._create_error_command(
                f"Error: Failed to communicate with Salesforce agent - {str(e)}",
                tool_call_id
            )
        except Exception as e:
            logger.error("tool_invocation_error",
                operation="salesforce_agent_tool",
                tool_name="salesforce_agent",
                tool_call_id=tool_call_id,
                error_type=type(e).__name__,
                error=str(e)
            )
            # Emit failure event
            emit_agent_call_event(
                DirectCallEventTypes.AGENT_CALL_FAILED,
                agent_name="salesforce_agent",
                task_id=task_id,
                instruction=instruction,
                additional_data={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "tool_call_id": tool_call_id
                }
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
    
    INTELLIGENT COORDINATION:
    Analyze the user's request and provide clear, optimized instructions to the Jira agent.
    Transform vague requests into specific, actionable instructions while respecting operation boundaries.
    
    The Jira agent benefits from specific, well-structured instructions that leverage conversation context.
    
    Returns structured issue data with Jira IDs for downstream processing."""
    
    # Re-enabled args_schema with proper InjectedState field
    # Fixed according to: https://github.com/langchain-ai/langgraph/issues/2220
    args_schema: Type[BaseModel] = AgentCallInput
    
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
        # State should always be provided now with proper InjectedState
        if state is None:
            logger.error("state_is_none",
                        component="orchestrator",
                        note="InjectedState not working properly")
            state = {}
        
        messages = state.get("messages", [])
        memory = state.get("memory", {})
        
        extracted_context = {}
        
        # Include recent messages using centralized serialization
        if messages:
            recent_messages = serialize_messages_for_json(messages, limit=5)
            if recent_messages:
                extracted_context["recent_messages"] = recent_messages
        
        # Include memory data
        if memory:
            extracted_context["memory"] = memory
        
        # Include conversation summary if available  
        if state and "summary" in state:
            extracted_context["conversation_summary"] = state["summary"]
        
        # Include user_id if available in state (check both direct and configurable)
        if state:
            if "user_id" in state:
                extracted_context["user_id"] = state["user_id"]
                logger.debug("found_user_id_in_state", user_id=state["user_id"])
            elif "configurable" in state and "user_id" in state["configurable"]:
                extracted_context["user_id"] = state["configurable"]["user_id"]
                logger.debug("found_user_id_in_configurable", user_id=state["configurable"]["user_id"])
            else:
                logger.warning("no_user_id_found", 
                    has_configurable="configurable" in state,
                    configurable_keys=list(state.get("configurable", {}).keys()) if "configurable" in state else [])
            
            # Include thread_id if available in state
            if "thread_id" in state:
                extracted_context["thread_id"] = state["thread_id"]
                logger.debug("found_thread_id_in_state", thread_id=state["thread_id"])
            elif "configurable" in state and "thread_id" in state["configurable"]:
                extracted_context["thread_id"] = state["configurable"]["thread_id"]
                logger.debug("found_thread_id_in_configurable", thread_id=state["configurable"]["thread_id"])
            else:
                logger.warning("no_thread_id_found",
                    has_configurable="configurable" in state,
                    configurable_keys=list(state.get("configurable", {}).keys()) if "configurable" in state else [],
                    state_keys=list(state.keys()) if state else [])
        else:
            # State should not be None with proper InjectedState
            logger.error("state_is_none_in_extract",
                        component="orchestrator",
                        method="_extract_conversation_context")
        
        # Merge any additional context
        if context:
            extracted_context.update(context)
        
        # NEW: Add enhanced memory context if available
        if state and "memory_context" in state:
            extracted_context["memory_insights"] = self._extract_memory_insights(state["memory_context"])
            logger.debug("added_memory_insights", 
                        entities_count=len(extracted_context["memory_insights"].get("relevant_entities", [])))
        
        # NEW: Add schema knowledge relevant to this agent
        schema_context = self._get_agent_schema_context()
        if schema_context:
            extracted_context["schema_knowledge"] = schema_context
            logger.debug("added_schema_knowledge", agent=getattr(self, 'agent_name', 'unknown'))
        
        # NEW: Add execution insights if available
        if state and "execution_history" in state:
            extracted_context["execution_insights"] = self._extract_execution_insights(state["execution_history"])
            logger.debug("added_execution_insights")
        
        return extracted_context
    
    def _get_agent_schema_context(self) -> Dict[str, Any]:
        """Get Jira-specific schema context using existing schema knowledge.
        
        Returns:
            Schema knowledge for Jira objects and relationships
        """
        try:
            from src.utils.schema_knowledge import get_schema_knowledge
            schema_knowledge = get_schema_knowledge()
            
            # Get Jira-specific schemas
            jira_schemas = {}
            for obj_type in ["issue", "project", "sprint", "epic"]:
                schema_entry = schema_knowledge.lookup_schema("jira", obj_type)
                if schema_entry:
                    jira_schemas[obj_type] = schema_entry.schema
            
            return jira_schemas
        except Exception as e:
            logger.warning("failed_to_get_schema_context", error=str(e))
            return {}
    
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
                    serialized_state[key] = serialize_messages_for_json(value, limit=5)
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
                content = response["content"]
                
                # Handle structured response formats from different agents
                if isinstance(content, dict):
                    # Jira agent returns {"response": "text", "tool_results": data, "issue_keys": []}
                    if "response" in content:
                        response_content = content["response"]
                    else:
                        # Fallback to JSON string representation
                        response_content = str(content)
                else:
                    response_content = content
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
    
    @log_execution(component="orchestrator", operation="jira_agent_call")
    async def _arun(self, instruction: str, context: Optional[Dict[str, Any]] = None, state: Annotated[Dict[str, Any], InjectedState] = None, **kwargs) -> Command:
        """Execute the Jira agent call using Command pattern.
        
        This method orchestrates the entire flow but delegates specific responsibilities
        to focused helper methods for better maintainability.
        """
        # Debug logging to understand state passing
        logger.info("jira_tool_debug",
            operation="jira_agent_tool",
            state_type=type(state).__name__ if state else "None",
            state_keys=list(state.keys()) if state and isinstance(state, dict) else [],
            has_messages=bool(state and "messages" in state) if isinstance(state, dict) else False,
            message_count=len(state.get("messages", [])) if state and isinstance(state, dict) else 0
        )
        
        # Log tool invocation start
        tool_call_id = kwargs.get("tool_call_id", None)
        task_id = str(uuid.uuid4())
        
        logger.info("tool_invocation_start",
            operation="jira_agent_tool",
            tool_name="jira_agent",
            tool_call_id=tool_call_id,
            instruction_preview=instruction[:100] if instruction else "",
            has_context=bool(context),
            has_state=bool(state)
        )
        
        # Emit agent call started event
        emit_agent_call_event(
            DirectCallEventTypes.AGENT_CALL_STARTED,
            agent_name="jira_agent",
            task_id=task_id,
            instruction=instruction,
            additional_data={
                "tool_call_id": tool_call_id,
                "has_context": bool(context)
            }
        )
        
        try:
            # Extract and serialize conversation context
            extracted_context = self._extract_conversation_context(state, context)
            
            # Find the Jira agent
            agent = self._find_jira_agent()
            if not agent:
                logger.error("agent_not_found",
                    operation="jira_agent_tool",
                    agent_type="jira",
                    tool_call_id=tool_call_id,
                    error="Jira agent not available"
                )
                # Emit failure event
                emit_agent_call_event(
                    DirectCallEventTypes.AGENT_CALL_FAILED,
                    agent_name="jira_agent",
                    task_id=task_id,
                    instruction=instruction,
                    additional_data={
                        "error": "Jira agent not available",
                        "tool_call_id": tool_call_id
                    }
                )
                return self._create_error_command(
                    "Error: Jira agent not available. Please ensure the Jira agent is running and registered.",
                    tool_call_id
                )
            
            # Create A2A task with serialized state (reuse task_id from above)
            serialized_state = self._serialize_state_snapshot(state)
            
            task = A2ATask(
                id=task_id,
                instruction=instruction,
                context=extracted_context,
                state_snapshot=serialized_state
            )
            
            # Execute A2A call using connection pool
            async with A2AClient(use_pool=True) as client:
                endpoint = agent.endpoint + "/a2a"
                
                # Log A2A dispatch
                logger.info("a2a_dispatch", 
                    agent="jira-agent",
                    task_id=task_id,
                    instruction_preview=instruction[:100],
                    endpoint=endpoint,
                    context_keys=list(extracted_context.keys()),
                    context_size=len(str(extracted_context))
                )
                
                result = await client.process_task(endpoint=endpoint, task=task)
                
                # Log the raw A2A response
                logger.info("a2a_raw_response",
                    agent="jira-agent",
                    task_id=task_id,
                    raw_response=result,
                    artifacts=result.get("artifacts") if isinstance(result, dict) else None,
                    state_updates=result.get("state_updates") if isinstance(result, dict) else None
                )
                
                # Process response
                response_content = self._extract_response_content(result)
                final_response = self._process_tool_results(result, response_content, task_id)
                
                logger.info("a2a_response_success",
                    agent="jira-agent", 
                    task_id=task_id,
                    response_length=len(final_response),
                    final_response_preview=final_response[:500] if len(final_response) > 500 else final_response
                )
                
                # Log successful tool completion
                logger.info("tool_invocation_complete",
                    operation="jira_agent_tool",
                    tool_name="jira_agent",
                    tool_call_id=tool_call_id,
                    response_length=len(final_response),
                    success=True
                )
                
                # Emit agent call completed event
                emit_agent_call_event(
                    DirectCallEventTypes.AGENT_CALL_COMPLETED,
                    agent_name="jira_agent",
                    task_id=task_id,
                    instruction=instruction,
                    additional_data={
                        "tool_call_id": tool_call_id,
                        "response_length": len(final_response),
                        "response_preview": final_response[:200] if final_response else ""
                    }
                )
                
                # Handle state merging from agent
                state_update = {}
                
                # Check for agent state to merge back
                if isinstance(result, dict) and "state_updates" in result:
                    state_updates = result["state_updates"]
                    if "agent_final_state" in state_updates:
                        agent_state = state_updates["agent_final_state"]
                        
                        # Extract tool results from agent messages for entity extraction
                        if "messages" in agent_state:
                            tool_results = []
                            for msg in agent_state["messages"]:
                                # Handle both serialized (dict) and non-serialized (object) messages
                                msg_name = None
                                msg_content = None
                                msg_type = None
                                
                                if isinstance(msg, dict):
                                    # Serialized message - check for kwargs structure
                                    if 'kwargs' in msg:
                                        kwargs = msg['kwargs']
                                        msg_name = kwargs.get('name')
                                        msg_content = kwargs.get('content', '')
                                        kwargs.get('tool_call_id')
                                        msg_type = kwargs.get('type')
                                    else:
                                        # Direct serialized format
                                        msg_name = msg.get('name')
                                        msg_content = msg.get('content', '')
                                        msg.get('tool_call_id')
                                        msg_type = msg.get('type')
                                else:
                                    # Non-serialized message object
                                    msg_name = getattr(msg, 'name', None)
                                    msg_content = getattr(msg, 'content', '')
                                    getattr(msg, 'tool_call_id', None)
                                    msg_type = getattr(msg, 'type', None)
                                
                                # Extract tool response messages (ToolMessage type)
                                if msg_type == 'tool' and msg_name and msg_content:
                                    try:
                                        import json
                                        if msg_content.startswith('{') or msg_content.startswith('['):
                                            tool_data = json.loads(msg_content)
                                            if isinstance(tool_data, dict) and tool_data.get('success'):
                                                tool_results.append({
                                                    'tool_name': msg_name,
                                                    'data': tool_data.get('data'),
                                                    'success': tool_data.get('success')
                                                })
                                    except (json.JSONDecodeError, ValueError, AttributeError):
                                        pass
                            
                            if tool_results:
                                state_update["tool_results"] = tool_results
                                logger.info("merged_agent_tool_results",
                                           task_id=task_id,
                                           tool_results_count=len(tool_results),
                                           agent="jira-agent")
                
                # Return Command with processed response and merged state
                # If we have a tool_call_id, return a ToolMessage, otherwise return the content directly
                if tool_call_id:
                    state_update["messages"] = [ToolMessage(
                        content=final_response,
                        tool_call_id=tool_call_id,
                        name="jira_agent"
                    )]
                    return Command(update=state_update)
                else:
                    # Return plain response when called without tool_call_id
                    return final_response
        
        except A2AException as e:
            logger.error("tool_invocation_error",
                operation="jira_agent_tool",
                tool_name="jira_agent",
                tool_call_id=tool_call_id,
                error_type="A2AException",
                error=str(e)
            )
            # Emit failure event
            emit_agent_call_event(
                DirectCallEventTypes.AGENT_CALL_FAILED,
                agent_name="jira_agent",
                task_id=task_id,
                instruction=instruction,
                additional_data={
                    "error": str(e),
                    "error_type": "A2AException",
                    "tool_call_id": tool_call_id
                }
            )
            return self._create_error_command(
                f"Error: Failed to communicate with Jira agent - {str(e)}",
                tool_call_id
            )
        except Exception as e:
            logger.error("tool_invocation_error",
                operation="jira_agent_tool",
                tool_name="jira_agent",
                tool_call_id=tool_call_id,
                error_type=type(e).__name__,
                error=str(e)
            )
            # Emit failure event
            emit_agent_call_event(
                DirectCallEventTypes.AGENT_CALL_FAILED,
                agent_name="jira_agent",
                task_id=task_id,
                instruction=instruction,
                additional_data={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "tool_call_id": tool_call_id
                }
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
    
    INTELLIGENT COORDINATION:
    Analyze the user's request and provide clear, optimized instructions to the ServiceNow agent.
    Transform vague requests into specific, actionable instructions while respecting operation boundaries.
    
    The ServiceNow agent benefits from specific, well-structured instructions that leverage conversation context.
    
    Returns structured ITSM data with record numbers for downstream processing."""
    
    # Re-enabled args_schema with proper InjectedState field
    # Fixed according to: https://github.com/langchain-ai/langgraph/issues/2220
    args_schema: Type[BaseModel] = AgentCallInput
    
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
        # State should always be provided now with proper InjectedState
        if state is None:
            logger.error("state_is_none",
                        component="orchestrator",
                        note="InjectedState not working properly")
            state = {}
        
        messages = state.get("messages", [])
        memory = state.get("memory", {})
        
        extracted_context = {}
        
        # Include recent messages using centralized serialization
        if messages:
            recent_messages = serialize_messages_for_json(messages, limit=5)
            if recent_messages:
                extracted_context["recent_messages"] = recent_messages
        
        # Include memory data
        if memory:
            extracted_context["memory"] = memory
        
        # Include conversation summary if available  
        if state and "summary" in state:
            extracted_context["conversation_summary"] = state["summary"]
        
        # Include user_id if available in state (check both direct and configurable)
        if state:
            if "user_id" in state:
                extracted_context["user_id"] = state["user_id"]
                logger.debug("found_user_id_in_state", user_id=state["user_id"])
            elif "configurable" in state and "user_id" in state["configurable"]:
                extracted_context["user_id"] = state["configurable"]["user_id"]
                logger.debug("found_user_id_in_configurable", user_id=state["configurable"]["user_id"])
            else:
                logger.warning("no_user_id_found", 
                    has_configurable="configurable" in state,
                    configurable_keys=list(state.get("configurable", {}).keys()) if "configurable" in state else [])
            
            # Include thread_id if available in state
            if "thread_id" in state:
                extracted_context["thread_id"] = state["thread_id"]
                logger.debug("found_thread_id_in_state", thread_id=state["thread_id"])
            elif "configurable" in state and "thread_id" in state["configurable"]:
                extracted_context["thread_id"] = state["configurable"]["thread_id"]
                logger.debug("found_thread_id_in_configurable", thread_id=state["configurable"]["thread_id"])
            else:
                logger.warning("no_thread_id_found",
                    has_configurable="configurable" in state,
                    configurable_keys=list(state.get("configurable", {}).keys()) if "configurable" in state else [],
                    state_keys=list(state.keys()) if state else [])
        else:
            # State should not be None with proper InjectedState
            logger.error("state_is_none_in_extract",
                        component="orchestrator",
                        method="_extract_conversation_context")
        
        # Merge any additional context
        if context:
            extracted_context.update(context)
        
        # NEW: Add enhanced memory context if available
        if state and "memory_context" in state:
            extracted_context["memory_insights"] = self._extract_memory_insights(state["memory_context"])
            logger.debug("added_memory_insights", 
                        entities_count=len(extracted_context["memory_insights"].get("relevant_entities", [])))
        
        # NEW: Add schema knowledge relevant to this agent
        schema_context = self._get_agent_schema_context()
        if schema_context:
            extracted_context["schema_knowledge"] = schema_context
            logger.debug("added_schema_knowledge", agent=getattr(self, 'agent_name', 'unknown'))
        
        # NEW: Add execution insights if available
        if state and "execution_history" in state:
            extracted_context["execution_insights"] = self._extract_execution_insights(state["execution_history"])
            logger.debug("added_execution_insights")
        
        return extracted_context
    
    def _get_agent_schema_context(self) -> Dict[str, Any]:
        """Get ServiceNow-specific schema context using existing schema knowledge.
        
        Returns:
            Schema knowledge for ServiceNow objects and relationships
        """
        try:
            from src.utils.schema_knowledge import get_schema_knowledge
            schema_knowledge = get_schema_knowledge()
            
            # Get ServiceNow-specific schemas
            servicenow_schemas = {}
            for obj_type in ["incident", "change_request", "problem", "sys_user", "core_company"]:
                schema_entry = schema_knowledge.lookup_schema("servicenow", obj_type)
                if schema_entry:
                    servicenow_schemas[obj_type] = schema_entry.schema
            
            return servicenow_schemas
        except Exception as e:
            logger.warning("failed_to_get_schema_context", error=str(e))
            return {}
    
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
                    serialized_state[key] = serialize_messages_for_json(value, limit=5)
                else:
                    # Keep other state as-is
                    serialized_state[key] = value
        return serialized_state
    
    def _find_servicenow_agent(self):
        """Locate the ServiceNow agent in the registry.
        
        Returns:
            Agent instance or None if not found
        """
        registry = self.metadata["registry"]
        agent = registry.find_agents_by_capability("servicenow_operations")
        
        if not agent:
            logger.warning("ServiceNow agent not found by capability, trying by name...")
            agent = registry.get_agent("servicenow-agent")
        
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
                content = response["content"]
                
                # Handle structured response formats from different agents
                if isinstance(content, dict):
                    # Jira agent returns {"response": "text", "tool_results": data, "issue_keys": []}
                    if "response" in content:
                        response_content = content["response"]
                    else:
                        # Fallback to JSON string representation
                        response_content = str(content)
                else:
                    response_content = content
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
    
    @log_execution(component="orchestrator", operation="servicenow_agent_call")
    async def _arun(self, instruction: str, context: Optional[Dict[str, Any]] = None, 
                    state: Annotated[Dict[str, Any], InjectedState] = None, **kwargs) -> Command:
        """Execute the ServiceNow agent call using Command pattern.
        
        This method orchestrates the entire flow but delegates specific responsibilities
        to focused helper methods for better maintainability.
        """
        # Debug logging to understand state passing
        logger.info("servicenow_tool_debug",
            operation="servicenow_agent_tool",
            state_type=type(state).__name__ if state else "None",
            state_keys=list(state.keys()) if state and isinstance(state, dict) else [],
            has_messages=bool(state and "messages" in state) if isinstance(state, dict) else False,
            message_count=len(state.get("messages", [])) if state and isinstance(state, dict) else 0
        )
        
        # Log tool invocation start
        tool_call_id = kwargs.get("tool_call_id", None)
        task_id = str(uuid.uuid4())
        
        logger.info("tool_invocation_start",
            operation="servicenow_agent_tool",
            tool_name="servicenow_agent",
            tool_call_id=tool_call_id,
            instruction_preview=instruction[:100] if instruction else "",
            has_context=bool(context),
            has_state=bool(state)
        )
        
        # Emit agent call started event
        emit_agent_call_event(
            DirectCallEventTypes.AGENT_CALL_STARTED,
            agent_name="servicenow_agent",
            task_id=task_id,
            instruction=instruction,
            additional_data={
                "tool_call_id": tool_call_id,
                "has_context": bool(context)
            }
        )
        
        try:
            # Extract and serialize conversation context
            extracted_context = self._extract_conversation_context(state, context)
            
            # Find the ServiceNow agent
            agent = self._find_servicenow_agent()
            if not agent:
                logger.error("agent_not_found",
                    operation="servicenow_agent_tool",
                    agent_type="servicenow",
                    tool_call_id=tool_call_id,
                    error="ServiceNow agent not available"
                )
                # Emit failure event
                emit_agent_call_event(
                    DirectCallEventTypes.AGENT_CALL_FAILED,
                    agent_name="servicenow_agent",
                    task_id=task_id,
                    instruction=instruction,
                    additional_data={
                        "error": "ServiceNow agent not available",
                        "tool_call_id": tool_call_id
                    }
                )
                return self._create_error_command(
                    "Error: ServiceNow agent not available. Please ensure the ServiceNow agent is running and registered.",
                    tool_call_id
                )
            
            # Create A2A task with serialized state (reuse task_id from above)
            serialized_state = self._serialize_state_snapshot(state)
            
            task = A2ATask(
                id=task_id,
                instruction=instruction,
                context=extracted_context,
                state_snapshot=serialized_state
            )
            
            # Execute A2A call using connection pool
            async with A2AClient(use_pool=True) as client:
                endpoint = agent.endpoint + "/a2a"
                
                # Log A2A dispatch
                logger.info("a2a_dispatch", 
                    agent="servicenow-agent",
                    task_id=task_id,
                    instruction_preview=instruction[:100],
                    endpoint=endpoint,
                    context_keys=list(extracted_context.keys()),
                    context_size=len(str(extracted_context))
                )
                
                result = await client.process_task(endpoint=endpoint, task=task)
                
                # Log the raw A2A response
                logger.info("a2a_raw_response",
                    agent="servicenow-agent",
                    task_id=task_id,
                    raw_response=result,
                    artifacts=result.get("artifacts") if isinstance(result, dict) else None,
                    state_updates=result.get("state_updates") if isinstance(result, dict) else None
                )
                
                # Process response
                response_content = self._extract_response_content(result)
                final_response = self._process_tool_results(result, response_content, task_id)
                
                logger.info("a2a_response_success",
                    agent="servicenow-agent", 
                    task_id=task_id,
                    response_length=len(final_response),
                    final_response_preview=final_response[:500] if len(final_response) > 500 else final_response
                )
                
                # Log successful tool completion
                logger.info("tool_invocation_complete",
                    operation="servicenow_agent_tool",
                    tool_name="servicenow_agent",
                    tool_call_id=tool_call_id,
                    response_length=len(final_response),
                    success=True
                )
                
                # Emit agent call completed event
                emit_agent_call_event(
                    DirectCallEventTypes.AGENT_CALL_COMPLETED,
                    agent_name="servicenow_agent",
                    task_id=task_id,
                    instruction=instruction,
                    additional_data={
                        "tool_call_id": tool_call_id,
                        "response_length": len(final_response),
                        "response_preview": final_response[:200] if final_response else ""
                    }
                )
                
                # Handle state merging from agent
                state_update = {}
                
                # Check for agent state to merge back
                if isinstance(result, dict) and "state_updates" in result:
                    state_updates = result["state_updates"]
                    if "agent_final_state" in state_updates:
                        agent_state = state_updates["agent_final_state"]
                        
                        # Extract tool results from agent messages for entity extraction
                        if "messages" in agent_state:
                            tool_results = []
                            for msg in agent_state["messages"]:
                                # Handle both serialized (dict) and non-serialized (object) messages
                                msg_name = None
                                msg_content = None
                                msg_type = None
                                
                                if isinstance(msg, dict):
                                    # Serialized message - check for kwargs structure
                                    if 'kwargs' in msg:
                                        kwargs = msg['kwargs']
                                        msg_name = kwargs.get('name')
                                        msg_content = kwargs.get('content', '')
                                        kwargs.get('tool_call_id')
                                        msg_type = kwargs.get('type')
                                    else:
                                        # Direct serialized format
                                        msg_name = msg.get('name')
                                        msg_content = msg.get('content', '')
                                        msg.get('tool_call_id')
                                        msg_type = msg.get('type')
                                else:
                                    # Non-serialized message object
                                    msg_name = getattr(msg, 'name', None)
                                    msg_content = getattr(msg, 'content', '')
                                    getattr(msg, 'tool_call_id', None)
                                    msg_type = getattr(msg, 'type', None)
                                
                                # Extract tool response messages (ToolMessage type)
                                if msg_type == 'tool' and msg_name and msg_content:
                                    try:
                                        import json
                                        if msg_content.startswith('{') or msg_content.startswith('['):
                                            tool_data = json.loads(msg_content)
                                            if isinstance(tool_data, dict) and tool_data.get('success'):
                                                tool_results.append({
                                                    'tool_name': msg_name,
                                                    'data': tool_data.get('data'),
                                                    'success': tool_data.get('success')
                                                })
                                    except (json.JSONDecodeError, ValueError, AttributeError):
                                        pass
                            
                            if tool_results:
                                state_update["tool_results"] = tool_results
                                logger.info("merged_agent_tool_results",
                                           task_id=task_id,
                                           tool_results_count=len(tool_results),
                                           agent="servicenow-agent")
                
                # Return Command with processed response and merged state
                # If we have a tool_call_id, return a ToolMessage, otherwise return the content directly
                if tool_call_id:
                    state_update["messages"] = [ToolMessage(
                        content=final_response,
                        tool_call_id=tool_call_id,
                        name="servicenow_agent"
                    )]
                    return Command(update=state_update)
                else:
                    # Return plain response when called without tool_call_id
                    return final_response
        
        except A2AException as e:
            logger.error("tool_invocation_error",
                operation="servicenow_agent_tool",
                tool_name="servicenow_agent",
                tool_call_id=tool_call_id,
                error_type="A2AException",
                error=str(e)
            )
            # Emit failure event
            emit_agent_call_event(
                DirectCallEventTypes.AGENT_CALL_FAILED,
                agent_name="servicenow_agent",
                task_id=task_id,
                instruction=instruction,
                additional_data={
                    "error": str(e),
                    "error_type": "A2AException",
                    "tool_call_id": tool_call_id
                }
            )
            return self._create_error_command(
                f"Error: Failed to communicate with ServiceNow agent - {str(e)}",
                tool_call_id
            )
        except Exception as e:
            logger.error("tool_invocation_error",
                operation="servicenow_agent_tool",
                tool_name="servicenow_agent",
                tool_call_id=tool_call_id,
                error_type=type(e).__name__,
                error=str(e)
            )
            # Emit failure event
            emit_agent_call_event(
                DirectCallEventTypes.AGENT_CALL_FAILED,
                agent_name="servicenow_agent",
                task_id=task_id,
                instruction=instruction,
                additional_data={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "tool_call_id": tool_call_id
                }
            )
            return self._create_error_command(
                f"Error: Unexpected error - {str(e)}",
                tool_call_id
            )
    


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
        state: Annotated[dict, InjectedState] = Field(
            description="Injected state from LangGraph for accessing conversation context"
        )
    
    args_schema: type = AgentRegistryInput
    
    def __init__(self, registry: AgentRegistry):
        super().__init__(metadata={"registry": registry})
    
    @log_execution(component="orchestrator", operation="agent_registry_action")
    async def _arun(self, action: str, agent_name: Optional[str] = None, state: Annotated[Dict[str, Any], InjectedState] = None) -> str:
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
            
            return "Registered Agents:\n" + "\n".join(agent_list)
        
        elif action == "health_check":
            if agent_name:
                result = await registry.health_check_agent(agent_name)
                return f"Health check for {agent_name}: {'✓ Online' if result else '✗ Offline/Error'}"
            else:
                results = await registry.health_check_all_agents()
                status_list = []
                for name, status in results.items():
                    status_list.append(f"- {name}: {'✓ Online' if status else '✗ Offline/Error'}")
                return "Agent Health Status:\n" + "\n".join(status_list)
        
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
    
    def _run(self, action: str, agent_name: Optional[str] = None, state: Annotated[Dict[str, Any], InjectedState] = None) -> str:
        """Synchronous wrapper for async execution"""
        return asyncio.run(self._arun(action, agent_name, state))