"""Jira specialized agent for issue tracking and agile management via A2A protocol."""

import os
import logging
from typing import Dict, Any, List, TypedDict, Annotated
import operator
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from src.utils.cost_tracking_decorator import create_cost_tracking_azure_openai
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import tools_condition
from langgraph.checkpoint.memory import MemorySaver

from src.agents.jira.tools.unified import UNIFIED_JIRA_TOOLS
from src.a2a import A2AServer, A2AArtifact, AgentCard
from src.agents.shared.memory_writer import write_tool_result_to_memory
from src.agents.shared.entity_extracting_tool_node import create_entity_extracting_tool_node
from src.utils.thread_utils import create_thread_id
from src.utils.config import config
from src.utils.logging.framework import SmartLogger, log_execution
from src.utils.prompt_templates import create_jira_agent_prompt, ContextInjector

# Load environment variables
load_dotenv()

logger = SmartLogger("jira")

# Unified Jira tools
jira_tools = UNIFIED_JIRA_TOOLS

# Agent state definition
class JiraAgentState(TypedDict):
    """State for the Jira agent."""
    messages: Annotated[List[Any], operator.add]
    current_task: str
    error: str
    task_context: Dict[str, Any]
    external_context: Dict[str, Any]
    orchestrator_state: Dict[str, Any]  # Receive state from orchestrator (one-way)

# Create the prompt template once at module level
jira_prompt = create_jira_agent_prompt()

def create_azure_openai_chat():
    """Create Azure OpenAI chat instance with cost tracking"""
    llm_config = config
    llm_kwargs = {
        "azure_endpoint": os.environ["AZURE_OPENAI_ENDPOINT"],
        "azure_deployment": os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4o-mini"),
        "openai_api_version": os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01"),
        "openai_api_key": os.environ["AZURE_OPENAI_API_KEY"],
        "temperature": llm_config.llm_temperature,
        "max_tokens": llm_config.llm_max_tokens,
        "timeout": llm_config.llm_timeout,
    }
    if llm_config.get('llm.top_p') is not None:
        llm_kwargs["top_p"] = llm_config.get('llm.top_p')
    # Use cost-tracking LLM (decorator pattern)
    return create_cost_tracking_azure_openai(component="jira", **llm_kwargs)

# Create LLM with tools at module level (like Salesforce)
llm = create_azure_openai_chat()
llm_with_tools = llm.bind_tools(jira_tools)

async def build_jira_agent():
    """Build and compile the Jira agent LangGraph workflow.

    Returns:
        CompiledGraph: Compiled LangGraph with memory checkpointing enabled
        
    Architecture Notes:
        - Uses prebuilt tools_condition for standard tool routing
        - Implements SqliteSaver for persistent conversation state
        - Binds all 15 Jira tools to the LLM for function calling
    """
    
    # Define agent node inside async function (like Salesforce pattern)
    @log_execution("jira", "agent_node", include_args=False, include_result=False)
    def agent_node(state: JiraAgentState, config: RunnableConfig):
        """Main agent logic node that processes messages and generates responses.
        
        Args:
            state: Current agent state containing messages and context
            
        Returns:
            dict: Updated state with new AI response message
            
        Processing Flow:
            1. Uses LangChain prompt template for consistent behavior
            2. Invokes LLM with bound tools for function calling
            3. Returns response for conditional routing to tools or end
        """
        state.get("current_task", "unknown")
        
        try:
            task_context = state.get("task_context", {})
            external_context = state.get("external_context", {})
            
            # Prepare context using the new ContextInjector
            context_dict = ContextInjector.prepare_jira_context(task_context, external_context)
            
            # Use the prompt template to format messages
            # This leverages LangChain's prompt template features
            formatted_prompt = jira_prompt.format_prompt(
                messages=state["messages"],
                **context_dict
            )
            
            # Convert to messages for the LLM
            messages = formatted_prompt.to_messages()
            
            # Get response from LLM with tool bindings (uses module-level llm_with_tools)
            response = llm_with_tools.invoke(messages)
            
            return {"messages": [response]}
            
        except Exception:
            raise
    
    # Create custom tool node using the shared implementation
    custom_tool_node = await create_entity_extracting_tool_node(jira_tools, "jira")
    
    # Build graph following 2024 best practices
    graph_builder = StateGraph(JiraAgentState)
    
    # Add nodes
    graph_builder.add_node("agent", agent_node)
    graph_builder.add_node("tools", custom_tool_node)
    
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
    
    # Compile with MemorySaver for in-memory checkpointing
    return graph_builder.compile(checkpointer=MemorySaver())

# Global agent instance (will be created in main)
jira_agent = None

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
    try:
        # Extract task data from params (following Salesforce pattern)
        task_data = params.get("task", {})
        task_id = task_data.get("id", "unknown")
        instruction = task_data.get("instruction", "")
        context = task_data.get("context", {})
        state_snapshot = task_data.get("state_snapshot", {})
        
        
        # Prepare initial state with orchestrator state
        initial_state = {
            "messages": [HumanMessage(content=instruction)],
            "current_task": task_id,
            "error": "",
            "task_context": {"task_id": task_id, "instruction": instruction},
            "external_context": context or {},
            "orchestrator_state": state_snapshot  # Receive state from orchestrator
        }
        
        
        # Run the agent
        config = {"configurable": {"thread_id": create_thread_id("jira", task_id)}}
        result = await jira_agent.ainvoke(initial_state, config)
        
        
        # Write tool results to memory
        thread_id = create_thread_id("jira", task_id)
        # Extract user_id from context for memory isolation
        user_id = context.get("user_id")
        messages = result["messages"]
        for i, msg in enumerate(messages):
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    # Look for the corresponding tool result in the next message
                    if i + 1 < len(messages):
                        next_msg = messages[i + 1]
                        if hasattr(next_msg, 'name') and hasattr(next_msg, 'content'):
                            # This is likely the tool result
                            try:
                                import json
                                
                                # Parse tool result if it's JSON
                                tool_result = next_msg.content
                                if isinstance(tool_result, str) and tool_result.strip().startswith('{'):
                                    try:
                                        tool_result = json.loads(tool_result)
                                    except:
                                        pass
                                
                                await write_tool_result_to_memory(
                                    thread_id=thread_id,
                                    tool_name=tool_call.get("name", "unknown"),
                                    tool_args=tool_call.get("args", {}),
                                    tool_result=tool_result,
                                    task_id=task_id,
                                    agent_name="jira",
                                    user_id=user_id
                                )
                            except Exception as e:
                                logger.warning("failed_to_write_tool_result",
                                             error=str(e),
                                             tool_name=tool_call.get("name"))
        
        # Extract the final response
        final_message = result["messages"][-1]
        response_content = final_message.content
        
        # Check for tool results to include
        tool_data = None
        if result.get("tool_results"):
            tool_data = result["tool_results"]
        
        # Create A2A result
        artifact = A2AArtifact(
            id=f"artifact_{task_id}",
            task_id=task_id,
            content={
                "response": response_content,
                "tool_results": tool_data,
                "issue_keys": extract_issue_keys(response_content)
            },
            content_type="jira_response",
            metadata={"agent": "jira-agent"}
        )
        
        
        # Create successful response
        response = {
            "artifacts": [artifact.to_dict()],
            "status": "completed"
        }
        
        # No need to pass state back - we use persistent memory for tool results
        
        return response
        
    except Exception as e:
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

@log_execution("jira", "get_agent_card", include_args=True, include_result=True)
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
        metadata={
            "tools_count": len(jira_tools),
            "tool_names": [tool.name for tool in jira_tools]
        }
    )
    return card.model_dump()

async def main():
    global jira_agent
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
    
    # Build the Jira agent
    jira_agent = await build_jira_agent()
    
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