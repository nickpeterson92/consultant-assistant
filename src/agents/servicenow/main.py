"""ServiceNow specialized agent for ITSM operations via A2A protocol."""

import os
import asyncio
from typing import Dict, Any, List, TypedDict, Annotated
import operator
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver

from src.agents.servicenow.tools.unified import UNIFIED_SERVICENOW_TOOLS
from src.a2a import A2AServer, AgentCard
from src.utils.config import config
from src.utils.logging.framework import SmartLogger, log_execution
from src.utils.prompt_templates import create_servicenow_agent_prompt, ContextInjectorServiceNow

# Load environment variables
load_dotenv()

logger = SmartLogger("servicenow")

# Agent state definition
class ServiceNowAgentState(TypedDict):
    """State for the ServiceNow agent."""
    messages: Annotated[List[Any], operator.add]
    current_task: str
    tool_results: List[Dict[str, Any]]
    error: str
    task_context: Dict[str, Any]
    external_context: Dict[str, Any]
    orchestrator_state: Dict[str, Any]  # Include orchestrator state for merging

# Create the prompt template once at module level
servicenow_prompt = create_servicenow_agent_prompt()

def create_azure_openai_chat():
    """Create Azure OpenAI chat instance using global config"""
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
    return AzureChatOpenAI(**llm_kwargs)

def build_servicenow_graph():
    """Build the ServiceNow agent graph using LangGraph."""
    
    # Initialize LLM
    llm = create_azure_openai_chat()
    
    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(UNIFIED_SERVICENOW_TOOLS)
    
    # Define agent function
    @log_execution("servicenow", "servicenow_agent", include_args=False, include_result=False)
    def servicenow_agent(state: ServiceNowAgentState):
        """Main agent logic for ServiceNow operations using LangChain prompt templates."""
        task_id = state.get("task_context", {}).get("task_id", "unknown")
        
        logger.info("servicenow_agent_processing",
                   task_id=task_id,
                   user_message=state["messages"][-1].content if state["messages"] else "No message",
                   message_count=len(state.get("messages", [])),
                   has_messages=bool(state.get("messages")))
        
        try:
            task_context = state.get("task_context", {})
            external_context = state.get("external_context", {})
            
            # Prepare context using the new ContextInjector for ServiceNow
            context_dict = ContextInjectorServiceNow.prepare_context(task_context, external_context)
            
            # Use the prompt template to format messages
            # This leverages LangChain's prompt template features
            formatted_prompt = servicenow_prompt.format_prompt(
                messages=state["messages"],
                **context_dict
            )
            
            # Convert to messages for the LLM
            messages = formatted_prompt.to_messages()
            
            # Call LLM with tools
            logger.info("servicenow_agent_llm_call", task_id=task_id, message_count=len(messages))
            response = llm_with_tools.invoke(messages)
            
            logger.info("servicenow_agent_llm_response",
                       task_id=task_id,
                       response_type=type(response).__name__,
                       has_tool_calls=bool(getattr(response, 'tool_calls', None)))
            
            return {"messages": [response]}
            
        except Exception as e:
            logger.error("servicenow_agent_error", task_id=task_id, error=str(e))
            error_msg = AIMessage(content=f"I encountered an error processing your ServiceNow request: {str(e)}")
            return {"messages": [error_msg], "error": str(e)}
    
    # Create tool node
    tool_node = ToolNode(UNIFIED_SERVICENOW_TOOLS)
    
    # Build the graph
    graph_builder = StateGraph(ServiceNowAgentState)
    
    # Add nodes
    graph_builder.add_node("agent", servicenow_agent)
    graph_builder.add_node("tools", tool_node)
    
    # Add edges
    graph_builder.set_entry_point("agent")
    graph_builder.add_conditional_edges(
        "agent",
        tools_condition,
        {
            "tools": "tools",
            "__end__": END
        }
    )
    graph_builder.add_edge("tools", "agent")
    
    # Compile with memory
    memory = MemorySaver()
    return graph_builder.compile(checkpointer=memory)

# A2A Server implementation
async def handle_a2a_request(params: dict) -> dict:
    """Process a ServiceNow task via A2A protocol."""
    try:
        # Extract task data from params (support both wrapped and unwrapped formats)
        task_data = params.get("task", params)  # Support both wrapped and unwrapped
        task_id = task_data.get("id", task_data.get("task_id", "unknown"))
        instruction = task_data.get("instruction", "")
        context = task_data.get("context", {})
        state_snapshot = task_data.get("state_snapshot", {})
        
        
        logger.info("handle_a2a_request_received",
                   task_id=task_id,
                   instruction=instruction,
                   has_context=bool(context))
        
        # Build the graph
        app = build_servicenow_graph()
        
        # Prepare initial state with orchestrator state
        initial_state = {
            "messages": [HumanMessage(content=instruction)],
            "current_task": instruction,
            "tool_results": [],
            "error": "",
            "task_context": {"task_id": task_id},
            "external_context": context or {},
            "orchestrator_state": state_snapshot  # Include for state merging
        }
        
        logger.info("initial_state_prepared",
                   task_id=task_id,
                   message_content=initial_state["messages"][0].content,
                   message_count=len(initial_state["messages"]))
        
        # Configure thread
        config = {
            "configurable": {
                "thread_id": f"servicenow_{task_id}"
            }
        }
        
        # Run the graph
        final_state = await app.ainvoke(initial_state, config)
        
        # Extract response
        messages = final_state.get("messages", [])
        last_message = messages[-1] if messages else None
        
        if last_message:
            response_content = last_message.content
            
            
            # Return with state merging capability
            response = {
                "artifacts": [{
                    "type": "text",
                    "content": response_content
                }],
                "status": "completed"
            }
            
            # Include final agent state for orchestrator merging
            if final_state:
                # Serialize messages before including in response
                serialized_state = dict(final_state)
                if "messages" in serialized_state:
                    from src.utils.agents.message_processing.unified_serialization import serialize_messages_for_json
                    serialized_state["messages"] = serialize_messages_for_json(serialized_state["messages"])
                
                response["state_updates"] = {
                    "agent_final_state": serialized_state,
                    "orchestrator_state": final_state.get("orchestrator_state", {})
                }
            
            return response
        else:
            raise ValueError("No response generated")
            
    except Exception as e:
        
        # Return error in expected format
        return {
            "artifacts": [],
            "status": "failed",
            "error": str(e)
        }

def create_servicenow_agent_card() -> AgentCard:
    """Create the agent card for ServiceNow agent."""
    return AgentCard(
        name="servicenow-agent",
        version="1.0.0",
        description="Specialized agent for ServiceNow IT Service Management operations",
        capabilities=[
            "servicenow_operations",
            "incident_management",
            "change_management", 
            "problem_management",
            "task_management",
            "cmdb_operations",
            "user_management",
            "itsm_workflows",
            "encoded_queries"
        ],
        endpoints={
            "process_task": "/a2a",
            "agent_card": "/a2a/agent-card"
        },
        communication_modes=["sync", "streaming"],
        metadata={
            "framework": "langgraph",
            "tools_count": len(UNIFIED_SERVICENOW_TOOLS),
            "tool_names": [tool.name for tool in UNIFIED_SERVICENOW_TOOLS]
        }
    )

async def main(port: int = 8003):
    """Main entry point for ServiceNow agent."""
    agent_card = create_servicenow_agent_card()
    
    logger.info("servicenow_agent_startup",
        component="servicenow",
        operation="startup",
        port=port,
        tools_count=len(UNIFIED_SERVICENOW_TOOLS),
        capabilities=agent_card.capabilities
    )
    
    # Create A2A server
    server = A2AServer(agent_card, "0.0.0.0", port)
    
    # Register handlers
    server.register_handler("process_task", handle_a2a_request)
    
    async def get_agent_card_handler(params):
        return agent_card.to_dict()
    
    server.register_handler("get_agent_card", get_agent_card_handler)
    
    # Start the server
    runner = await server.start()
    
    try:
        # Keep the server running
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        await server.stop(runner)
        
        # Clean up the global connection pool
        from src.a2a.protocol import get_connection_pool
        pool = get_connection_pool()
        await pool.close_all()

if __name__ == "__main__":
    import asyncio
    import argparse
    
    parser = argparse.ArgumentParser(description="ServiceNow Agent")
    parser.add_argument("--port", type=int, default=8003, help="Port to run on")
    args = parser.parse_args()
    
    asyncio.run(main(port=args.port))