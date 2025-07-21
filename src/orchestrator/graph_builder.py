"""Graph builder for the multi-agent orchestrator system."""

from dotenv import load_dotenv
from functools import partial

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import tools_condition

from src.utils.logging import get_logger
from src.utils.storage import get_async_store_adapter
from src.utils.tool_execution import create_tool_node

from .agent_registry import AgentRegistry
from .agent_caller_tools import SalesforceAgentTool, JiraAgentTool, ServiceNowAgentTool, AgentRegistryTool
from .state import OrchestratorState
from src.tools.utility import WebSearchTool
from .llm_handler import create_llm_instances
from .conversation_handler import orchestrator as orchestrator_node
from .background_tasks import summarize_conversation, memorize_records

logger = get_logger()

# Initialize global agent registry
agent_registry = AgentRegistry()

# Initialize global memory store
global_memory_store = None


def build_orchestrator_graph():
    """Build and compile the orchestrator LangGraph."""
    load_dotenv()
    
    # Configure persistent storage
    memory = MemorySaver()
    memory_store = get_async_store_adapter(
        db_path="memory_store.db",
        max_workers=4
    )
    
    # Set global store
    global global_memory_store
    global_memory_store = memory_store
    
    graph_builder = StateGraph(OrchestratorState)
    
    # Initialize orchestrator tools
    tools = [
        SalesforceAgentTool(agent_registry),
        JiraAgentTool(agent_registry),
        ServiceNowAgentTool(agent_registry),
        AgentRegistryTool(agent_registry),
        WebSearchTool()  # New utility tool for web search
    ]
    
    # Create LLM instances and invoke function
    llm_with_tools, deterministic_llm, trustcall_extractor, invoke_llm = create_llm_instances(tools)
    
    # Create partial function for orchestrator node with dependencies
    orchestrator_with_deps = partial(
        orchestrator_node,
        memory_store=memory_store,
        agent_registry=agent_registry,
        invoke_llm=invoke_llm,
        summarize_func=partial(summarize_conversation, invoke_llm=invoke_llm),
        memorize_func=memorize_records,
        trustcall_extractor=trustcall_extractor
    )
    
    # Build graph with tool integration
    tool_node = create_tool_node(tools)
    graph_builder.add_node("tools", tool_node)
    graph_builder.add_node("conversation", orchestrator_with_deps)
    
    graph_builder.set_entry_point("conversation")
    
    # Route to tools when needed
    graph_builder.add_conditional_edges(
        "conversation",
        tools_condition,
        {
            "tools": "tools",
            "__end__": END,
        }
    )
    
    # Return to conversation after tool execution
    graph_builder.add_edge("tools", "conversation")
    
    graph_builder.set_finish_point("conversation")
    
    return graph_builder.compile(checkpointer=memory, store=memory_store)


# Note: orchestrator_graph is created on-demand to avoid initialization issues
# Use build_orchestrator_graph() to create the graph when needed
orchestrator_graph = None


def get_global_memory_store():
    """Get the global memory store instance."""
    return global_memory_store


def get_agent_registry():
    """Get the global agent registry instance."""
    return agent_registry