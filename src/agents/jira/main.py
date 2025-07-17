"""Jira specialized agent for issue tracking and agile management via A2A protocol."""

import os
import json
import logging
from typing import Dict, Any, List, TypedDict, Annotated, Optional
import operator
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver

from src.tools.jira import UNIFIED_JIRA_TOOLS
from src.a2a import A2AServer, A2AArtifact, AgentCard
from src.utils.config import get_llm_config
from src.utils.logging import get_logger
from src.utils.agents.prompts import jira_agent_sys_msg

logger = get_logger("jira")

# Unified Jira tools
jira_tools = UNIFIED_JIRA_TOOLS

# Agent state definition
class JiraAgentState(TypedDict):
    """State for the Jira agent."""
    messages: Annotated[List[Any], operator.add]
    current_task: str
    tool_results: List[Dict[str, Any]]
    error: str
    task_context: Dict[str, Any]
    external_context: Dict[str, Any]

def get_jira_system_message(task_context: Optional[Dict[Any, Any]] = None, external_context: Optional[Dict[Any, Any]] = None) -> str:
    """Generate the system message that defines the Jira agent's behavior and capabilities.
    
    Args:
        task_context: Optional task-specific context to include
        external_context: Optional external context from orchestrator
    
    Returns:
        str: Comprehensive system prompt including capabilities, best practices,
             and JQL examples for effective Jira operations.
             
    Note:
        This message is injected at the start of each conversation to ensure
        consistent behavior and proper tool usage guidance.
    """
    return jira_agent_sys_msg(task_context=task_context, external_context=external_context)

def build_jira_agent():
    """Build and compile the Jira agent LangGraph workflow.

    Returns:
        CompiledGraph: Compiled LangGraph with memory checkpointing enabled
        
    Architecture Notes:
        - Uses prebuilt tools_condition for standard tool routing
        - Implements MemorySaver for conversation persistence
        - Binds all 15 Jira tools to the LLM for function calling
    """
    
    # Initialize LLM with Azure OpenAI configuration
    llm_config = get_llm_config()
    llm = AzureChatOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=llm_config.azure_deployment,
        api_version=llm_config.api_version,
        api_key=os.environ["AZURE_OPENAI_API_KEY"],  # pyright: ignore[reportArgumentType]
        temperature=llm_config.temperature,
        max_tokens=llm_config.max_tokens,
        timeout=llm_config.timeout,
    )
    
    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(jira_tools)
    
    # Create workflow
    workflow = StateGraph(JiraAgentState)
    
    def agent_node(state: JiraAgentState):
        """Main agent logic node that processes messages and generates responses.
        
        Args:
            state: Current agent state containing messages and context
            
        Returns:
            dict: Updated state with new AI response message
            
        Processing Flow:
            1. Ensures system message is present for consistent behavior
            2. Invokes LLM with bound tools for function calling
            3. Returns response for conditional routing to tools or end
        """
        task_id = state.get("current_task", "unknown")
        
        # Log agent node entry
        logger.info("jira_agent_node_entry",
            component="jira",
            operation="process_messages",
            task_id=task_id,
            message_count=len(state.get("messages", [])),
            has_tool_results=bool(state.get("tool_results")),
            has_task_context=bool(state.get("task_context")),
            has_external_context=bool(state.get("external_context"))
        )
        
        # Get contexts for system message
        task_context = state.get("task_context", {})
        external_context = state.get("external_context", {})
        
        # Generate system message
        system_message_content = get_jira_system_message(task_context=task_context, external_context=external_context)
        
        # Import trimming utility
        from src.utils.agents.message_processing import trim_messages_for_context, estimate_message_tokens
        
        # Trim messages to prevent token limit issues
        state_messages = state.get("messages", [])
        trimmed_messages = trim_messages_for_context(
            state_messages,
            max_tokens=70000,  # Conservative limit for agent
            keep_system=False,  # System message added separately
            keep_first_n=2,     # Keep original request context
            keep_last_n=10,     # Keep recent tool interactions
            use_smart_trimming=True
        )
        
        # Log token usage
        system_tokens = estimate_message_tokens([SystemMessage(content=system_message_content)])
        message_tokens = estimate_message_tokens(trimmed_messages)
        total_tokens = system_tokens + message_tokens
        
        logger.info("jira_token_usage",
            component="jira",
            operation="prepare_messages",
            task_id=task_id,
            original_message_count=len(state_messages),
            trimmed_message_count=len(trimmed_messages),
            system_tokens=system_tokens,
            message_tokens=message_tokens,
            total_tokens=total_tokens,
            token_limit=128000
        )
        
        # Prepare messages with system message
        messages = [SystemMessage(content=system_message_content)] + trimmed_messages
        
        # Log LLM invocation
        logger.info("jira_llm_invocation_start",
            component="jira",
            operation="invoke_llm",
            task_id=task_id,
            message_count=len(messages)
        )
        
        # Get response from LLM with tool bindings
        response = llm_with_tools.invoke(messages)
        
        # Log LLM response
        logger.info("jira_llm_invocation_complete",
            component="jira",
            operation="invoke_llm",
            task_id=task_id,
            has_tool_calls=bool(hasattr(response, 'tool_calls') and response.tool_calls),  # pyright: ignore[reportAttributeAccessIssue]
            response_length=len(str(response.content)) if hasattr(response, 'content') else 0
        )
        
        return {"messages": [response]}
    
    # Build graph following 2024 best practices
    graph_builder = StateGraph(JiraAgentState)
    
    # Add nodes
    graph_builder.add_node("agent", agent_node)
    graph_builder.add_node("tools", ToolNode(jira_tools))
    
    # Modern routing using prebuilt tools_condition
    graph_builder.set_entry_point("agent")
    graph_builder.add_conditional_edges(
        "agent",
        tools_condition,  # Use prebuilt condition like Salesforce agent
        {
            "tools": "tools",
            "__end__": END,  # Note: double underscore for END
        }
    )
    graph_builder.add_edge("tools", "agent")
    
    # Compile with memory
    memory = MemorySaver()
    return graph_builder.compile(checkpointer=memory)

# Global agent instance
jira_agent = build_jira_agent()

async def handle_a2a_request(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle incoming A2A protocol requests for Jira operations.
    
    Args:
        params: A2A parameters containing:
            - task: Dictionary with task data including:
                - id: Task identifier
                - instruction: Natural language request
                - context: Optional context dictionary
                - state_snapshot: Optional orchestrator state
            
    Returns:
        Dict[str, Any]: A2A result with:
            - task_id: Original task ID
            - status: "completed" or "failed"
            - result: Success/error information
            - artifacts: Response data including issue keys
            - metadata: Agent name, tools used, timestamp
    """
    # Initialize task_id for use in except block
    task_id = "unknown"
    
    try:
        # Extract task data from params (following Salesforce pattern)
        task_data = params.get("task", {})
        task_id = task_data.get("id", "unknown")
        instruction = task_data.get("instruction", "")
        context = task_data.get("context", {})
        state_snapshot = task_data.get("state_snapshot", {})
        
        # Merge state_snapshot into context for full orchestrator state access
        merged_context = {
            **context,
            "orchestrator_state": state_snapshot
        }
        
        # Log task processing start
        logger.info("jira_a2a_task_start",
            component="jira",
            operation="process_a2a_task",
            task_id=task_id,
            instruction_preview=instruction[:100] if instruction else "",
            instruction_length=len(instruction) if instruction else 0,
            has_context=bool(context),
            context_keys=list(context.keys()) if context else [],
            context_size=len(str(context)) if context else 0,
            has_state_snapshot=bool(state_snapshot),
            state_snapshot_keys=list(state_snapshot.keys()) if state_snapshot else []
        )
        
        # Prepare initial state
        initial_state = {
            "messages": [HumanMessage(content=instruction)],
            "current_task": task_id,
            "tool_results": [],
            "error": "",
            "task_context": {"task_id": task_id, "instruction": instruction},
            "external_context": merged_context
        }
        
        # Log agent invocation
        logger.info("jira_agent_invocation_start",
            component="jira",
            operation="invoke_agent",
            task_id=task_id,
            message_count=len(initial_state["messages"]),
            thread_id=task_id
        )
        
        # Run the agent
        llm_config = get_llm_config()
        config = RunnableConfig(
            configurable={"thread_id": task_id},
            recursion_limit=llm_config.recursion_limit
        )
        result = await jira_agent.ainvoke(initial_state, config)
        
        # Log agent invocation complete
        logger.info("jira_agent_invocation_complete",
            component="jira",
            operation="invoke_agent",
            task_id=task_id,
            tool_results_count=len(result.get("tool_results", [])),
            message_count=len(result.get("messages", [])),
            has_error=bool(result.get("error"))
        )
        
        # Extract the final response
        final_message = result["messages"][-1]
        response_content = final_message.content
        
        # Check final tool outcome - agents may retry multiple times before succeeding
        final_tool_success = None
        from langchain_core.messages import ToolMessage
        
        # Find the LAST ToolMessage result to determine final outcome
        for msg in reversed(result["messages"]):
            if isinstance(msg, ToolMessage) and hasattr(msg, 'content'):
                # Try to parse tool result as JSON to check success field
                try:
                    if isinstance(msg.content, str) and (msg.content.startswith('{') or msg.content.startswith('[')):
                        tool_result = json.loads(msg.content)
                        if isinstance(tool_result, dict) and 'success' in tool_result:
                            # Check for nested success structure (Jira tools have this pattern)
                            if 'data' in tool_result and isinstance(tool_result['data'], dict) and 'success' in tool_result['data']:
                                # Use the inner business logic success, not the outer API success
                                final_tool_success = tool_result['data'].get('success')
                            else:
                                # Use the direct success field
                                final_tool_success = tool_result.get('success')
                            break
                except (json.JSONDecodeError, AttributeError):
                    # If not valid JSON, continue checking other messages
                    pass
        
        # Determine actual task success based on final tool execution result
        # If no tool results found, assume success (agent completed without tools)
        task_success = final_tool_success is not False
        status = "completed" if task_success else "failed"
        
        # Check for tool results to include
        tool_data = None
        if result.get("tool_results"):
            tool_data = result["tool_results"]
        
        # Create A2A result
        artifact = A2AArtifact(
            id=f"artifact_{task_id}",
            task_id=task_id,
            content=response_content,
            content_type="text/plain",
            metadata={"agent": "jira-agent"}
        )
        
        # Log task completion with actual success status
        logger.info("jira_a2a_task_complete",
            component="jira",
            operation="process_a2a_task",
            task_id=task_id,
            success=task_success,
            response_length=len(response_content),
            tool_results_count=len(result.get("tool_results", [])),
            issue_keys=extract_issue_keys(response_content),
            final_tool_success=final_tool_success
        )
        
        # Create response with computed status
        result_dict = {
            "artifacts": [artifact.to_dict()],
            "status": status
        }
        
        # Include error information if task failed
        if not task_success:
            result_dict["error"] = "Task execution encountered tool errors"
            
        return result_dict
        
    except Exception as e:
        # Log task failure
        logger.error("jira_a2a_task_error",
            component="jira",
            operation="process_a2a_task",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__
        )
        # Return error in expected format
        return {
            "artifacts": [],
            "status": "failed",
            "error": str(e)
        }

def extract_issue_keys(text: str) -> List[str]:
    """Extract Jira issue keys from text using regex pattern matching.
    
    Args:
        text: Input text that may contain issue keys
        
    Returns:
        List[str]: Unique list of issue keys found (e.g., ['PROJ-123', 'TEST-456'])
        
    Pattern:
        Matches standard Jira issue key format: PROJECT-NUMBER
        where PROJECT is uppercase letters and NUMBER is digits
    """
    import re
    pattern = r'[A-Z]+-\d+'
    return list(set(re.findall(pattern, text)))

def get_agent_card() -> Dict[str, Any]:
    """Generate the agent card for A2A protocol capability advertisement.
    
    Returns:
        Dict[str, Any]: Serialized AgentCard containing:
            - name: Agent identifier
            - version: Semantic version
            - description: Human-readable purpose
            - capabilities: List of capability tags
            - endpoints: Available API endpoints
            - metadata: Tool information
            
    Note:
        This card is used by the orchestrator for agent discovery
        and capability-based routing decisions.
    """
    card = AgentCard(
        name="jira-agent",
        version="1.0.0",
        description="Specialized agent for Jira issue tracking and project management",
        capabilities=[
            "jira_operations",
            "issue_management",
            "jql_search",
            "epic_tracking",
            "sprint_management",
            "agile_workflows",
            "project_analytics"
        ],
        endpoints={
            "a2a": "/a2a",
            "health": "/health",
            "agent_card": "/a2a/agent-card"
        },
        communication_modes=["a2a", "async"],
        metadata={
            "tools_count": len(jira_tools),
            "tool_names": [tool.name for tool in jira_tools]
        }
    )
    return card.to_dict()

async def main():
    """Main entry point for Jira agent."""
    import argparse
    import asyncio
    
    parser = argparse.ArgumentParser(description="Jira Agent - A2A Protocol Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8002, help="Port to listen on")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    
    # Create agent card
    agent_card = AgentCard(
        name="jira-agent",
        version="1.0.0",
        description="Specialized agent for Jira issue tracking and project management",
        capabilities=[
            "jira_operations",
            "issue_management", 
            "jql_search",
            "epic_tracking",
            "sprint_management",
            "agile_workflows",
            "project_analytics"
        ],
        endpoints={
            "process_task": "/a2a",
            "agent_card": "/a2a/agent-card"
        },
        communication_modes=["sync", "streaming"],
        metadata={
            "framework": "langgraph",
            "tools_count": len(jira_tools),
            "tool_names": [tool.name for tool in jira_tools]
        }
    )
    
    # Create A2A server
    server = A2AServer(agent_card, args.host, args.port)
    
    # Register handlers
    server.register_handler("process_task", handle_a2a_request)
    async def get_agent_card_handler(params):
        return agent_card.to_dict()
    
    server.register_handler("get_agent_card", get_agent_card_handler)
    
    # Start the server
    logger.info("agent_starting",
        component="system",
        agent="jira",
        host=args.host,
        port=args.port,
        operation="startup"
    )
    runner = await server.start()
    
    logger.info("jira_agent_started",
        component="system",
        operation="startup",
        agent="jira",
        host=args.host,
        port=args.port,
        endpoint=f"http://{args.host}:{args.port}"
    )
    logger.info("agent_capabilities",
        component="system",
        agent="jira",
        capabilities=agent_card.capabilities,
        capability_count=len(agent_card.capabilities)
    )
    logger.info("agent_ready",
        component="system",
        agent="jira",
        operation="ready"
    )
    
    try:
        # Keep the server running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("agent_shutdown",
            component="system",
            agent="jira",
            operation="shutdown"
        )
        await server.stop(runner)
        
        # Clean up the global connection pool
        from src.a2a.protocol import get_connection_pool
        pool = get_connection_pool()
        await pool.close_all()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())