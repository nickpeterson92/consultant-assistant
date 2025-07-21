"""Exact canonical plan-and-execute implementation from LangGraph tutorial.

Reference: https://langchain-ai.github.io/langgraph/tutorials/plan-and-execute/plan-and-execute/#create-the-graph
"""

import operator
from typing import Annotated, List, Union
from typing_extensions import TypedDict
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import tools_condition
from langgraph.checkpoint.memory import MemorySaver

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from src.utils.logging.framework import SmartLogger, log_execution

# Initialize logger
logger = SmartLogger("orchestrator")


# ================================
# State Schema - EXACT from tutorial
# ================================

class PlanExecute(TypedDict):
    input: str
    plan: List[str]
    past_steps: Annotated[List[tuple], operator.add]
    response: str
    user_visible_responses: Annotated[List[str], operator.add]  # Responses that should be shown to user immediately


# ================================
# Models - EXACT from tutorial
# ================================

class Plan(BaseModel):
    """Plan to follow in future"""
    steps: List[str] = Field(
        description="different steps to follow, should be in sorted order"
    )


class Response(BaseModel):
    """Response to user."""
    response: str


class Act(BaseModel):
    """Action to perform."""
    action: Union[Response, Plan] = Field(
        description="Action to perform. If you want to respond to user, use Response. "
        "If you need to further use tools to get the answer, use Plan."
    )


# ================================
# Prompts - EXACT from tutorial
# ================================

# Prompts are now generated dynamically with agent context in setup function


# ================================
# Node Functions - EXACT from tutorial
# ================================

@log_execution("orchestrator", "execute_step", include_args=True, include_result=True)
def execute_step(state: PlanExecute):
    import asyncio
    from .observers import get_observer_registry, SearchResultsEvent
    
    plan = state["plan"]
    plan_str = "\n".join(f"{i + 1}. {step}" for i, step in enumerate(plan))
    task = plan[0]
    task_formatted = f"""For the following plan:
{plan_str}

You are tasked with executing step {1}, {task}."""
    
    # Use ReAct agent executor which handles tool execution automatically
    agent_response = asyncio.run(agent_executor.ainvoke(
        {"messages": [("user", task_formatted)]}
    ))
    
    final_response = agent_response["messages"][-1].content
    
    # Check if any tools used during execution produce user data
    # We need to get the available tools to check their metadata
    from src.tools.salesforce import UNIFIED_SALESFORCE_TOOLS
    from src.tools.jira import UNIFIED_JIRA_TOOLS
    from src.tools.servicenow import UNIFIED_SERVICENOW_TOOLS
    
    # Build a lookup of all available tools using the unified constants
    all_tools = list(UNIFIED_SALESFORCE_TOOLS) + list(UNIFIED_JIRA_TOOLS) + list(UNIFIED_SERVICENOW_TOOLS)
    
    tool_lookup = {tool.name: tool for tool in all_tools}
    
    # Check actual tool calls made during execution
    produced_user_data = False
    for message in agent_response["messages"]:
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tool_call in message.tool_calls:
                tool_name = tool_call.get("name", "")
                
                # Look up the tool to check its metadata
                if tool_name in tool_lookup:
                    tool = tool_lookup[tool_name]
                    if getattr(tool, 'produces_user_data', False):
                        produced_user_data = True
                        break
    
    # Notify observers if user data was produced
    if produced_user_data:
        registry = get_observer_registry()
        event = SearchResultsEvent(
            step_name=task,
            results=final_response,
            tool_name="data_producing_operation",
            is_user_selectable=True
        )
        registry.notify_search_results(event)
    
    return {
        "past_steps": [(task, final_response)],
    }


@log_execution("orchestrator", "plan_step", include_args=True, include_result=True)
def plan_step(state: PlanExecute):
    import asyncio
    from langchain_core.messages import HumanMessage
    plan = asyncio.run(planner.ainvoke({"messages": [HumanMessage(content=state["input"])]}))
    return {"plan": plan.steps}


@log_execution("orchestrator", "replan_step", include_args=True, include_result=True)
def replan_step(state: PlanExecute):
    import asyncio
    
    # Format past_steps for the template
    past_steps_str = ""
    for i, (step, result) in enumerate(state["past_steps"]):
        past_steps_str += f"Step {i + 1}: {step}\nResult: {result}\n\n"
    
    # Format the template variables
    template_vars = {
        "input": state["input"],
        "plan": "\n".join(f"{i + 1}. {step}" for i, step in enumerate(state["plan"])),
        "past_steps": past_steps_str.strip()
    }
    
    output = asyncio.run(replanner.ainvoke(template_vars))
    if isinstance(output.action, Response):
        return {"response": output.action.response}
    else:
        # Check if the new plan includes human_input - if so, show the most recent result to user
        new_plan = output.action.steps
        user_visible_responses = []
        
        # If any plan step mentions human_input, show the most recent past step result to user
        if any("human_input" in step.lower() for step in new_plan) and state.get("past_steps"):
            last_step, last_result = state["past_steps"][-1]
            user_visible_responses.append(last_result)
        
        return {
            "plan": new_plan,
            "user_visible_responses": user_visible_responses
        }


@log_execution("orchestrator", "should_end", include_args=True, include_result=True)
def should_end(state: PlanExecute):
    if "response" in state and state["response"]:
        return END
    else:
        return "agent"


# ================================
# Graph Creation - EXACT from tutorial
# ================================

def create_graph(agent_executor, planner, replanner):
    """Create the canonical plan-and-execute graph."""
    
    # Store globally for node functions to access
    globals()['agent_executor'] = agent_executor
    globals()['planner'] = planner
    globals()['replanner'] = replanner
    
    workflow = StateGraph(PlanExecute)

    # Add the plan node
    workflow.add_node("planner", plan_step)

    # Add the execution step
    workflow.add_node("agent", execute_step)

    # Add a replan node
    workflow.add_node("replan", replan_step)

    workflow.add_edge(START, "planner")

    # From plan we go to agent
    workflow.add_edge("planner", "agent")

    # From agent, we replan
    workflow.add_edge("agent", "replan")

    workflow.add_conditional_edges(
        "replan",
        # Next, we pass in the function that will determine which node is called next.
        should_end,
        ["agent", END],
    )

    # Finally, we compile it!
    # This compiles it into a LangChain Runnable,
    # meaning you can use it as you would any other runnable
    app = workflow.compile(checkpointer=MemorySaver())
    return app


# ================================
# Factory function for easy setup
# ================================

async def create_plan_execute_graph():
    """Create a simple plan-execute graph for A2A usage."""
    from src.orchestrator.llm_handler import create_llm_instances, get_orchestrator_system_message
    from src.orchestrator.agent_registry import AgentRegistry
    from src.orchestrator.agent_caller_tools import SalesforceAgentTool, JiraAgentTool, ServiceNowAgentTool, AgentRegistryTool
    from src.tools.utility import WebSearchTool
    from src.tools.human_input import HumanInputTool
    from langgraph.prebuilt import create_react_agent
    from langchain_openai import AzureChatOpenAI
    import os
    
    # Create agent registry and LLM instances
    agent_registry = AgentRegistry()
    
    # Initialize the UX observer for tracking user-visible data
    from .observers import get_observer_registry, UXObserver
    registry = get_observer_registry()
    ux_observer = UXObserver()
    registry.add_observer(ux_observer)
    
    # Create tools list with agent caller tools
    tools = [
        SalesforceAgentTool(agent_registry),
        JiraAgentTool(agent_registry),
        ServiceNowAgentTool(agent_registry),
        AgentRegistryTool(agent_registry),
        WebSearchTool(),
        HumanInputTool()
    ]
    
    # Create LLM for the ReAct agent
    llm = AzureChatOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4o-mini"),
        openai_api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01"),
        openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
        temperature=0.1,
        max_tokens=4000,
    )
    
    # Get orchestrator system message for the ReAct agent
    mock_state = {"summary": "", "memory": "", "active_agents": []}
    orchestrator_prompt = get_orchestrator_system_message(mock_state, agent_registry)
    
    # Create ReAct agent executor with our orchestrator prompt
    agent_executor = create_react_agent(llm, tools, prompt=orchestrator_prompt)
    
    # Use the canonical setup with proper prompts and agent context
    return setup_canonical_plan_execute(agent_executor, llm, agent_registry)


def setup_canonical_plan_execute(llm_with_tools, llm_for_planning, agent_registry=None):
    """Set up the canonical plan-and-execute graph with LLMs and tool context."""
    
    # Get agent context from orchestrator system message generation (reuse existing logic)
    agent_context = ""
    if agent_registry:
        from .llm_handler import get_orchestrator_system_message
        
        # Create mock state to get agent context from orchestrator
        mock_state = {"summary": "", "memory": "", "active_agents": []}
        full_system_msg = get_orchestrator_system_message(mock_state, agent_registry)
        
        # Extract only agent tools for planning (exclude management tools)
        if "ORCHESTRATOR TOOLS:" in full_system_msg:
            tools_section = full_system_msg.split("ORCHESTRATOR TOOLS:")[1].split("\n\n")[0]
            
            # Filter out management tools, keep only agent tools
            agent_tools = []
            for line in tools_section.split("\n"):
                if line.strip() and not any(mgmt_tool in line.lower() for mgmt_tool in ["manage_agents", "agent_registry", "health_check"]):
                    agent_tools.append(line)
            
            if agent_tools:
                agent_context = f"=== AVAILABLE AGENT TOOLS ===\n" + "\n".join(agent_tools)
    
    # Import centralized prompt functions
    from src.utils.sys_msg import planner_sys_msg, replanner_sys_msg
    
    # Create prompts with dynamic agent context  
    planner_prompt = ChatPromptTemplate.from_messages([
        ("system", planner_sys_msg(agent_context)),
        ("placeholder", "{messages}")
    ])
    replanner_prompt = ChatPromptTemplate.from_template(
        replanner_sys_msg()
    )
    
    # Create planner and replanner with structured output and agent context
    planner = planner_prompt | llm_for_planning.with_structured_output(Plan)
    replanner = replanner_prompt | llm_for_planning.with_structured_output(Act)
    
    # Agent executor is the LLM with tools
    agent_executor = llm_with_tools
    
    # Create and return the graph
    return create_graph(agent_executor, planner, replanner)