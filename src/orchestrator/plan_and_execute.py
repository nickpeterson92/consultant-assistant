"""Exact canonical plan-and-execute implementation from LangGraph tutorial.

Reference: https://langchain-ai.github.io/langgraph/tutorials/plan-and-execute/plan-and-execute/#create-the-graph
"""

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
logger = SmartLogger("plan_execute")


# ================================
# State Schema - EXACT from tutorial
# ================================

class PlanExecute(TypedDict):
    input: str
    plan: List[str]
    past_steps: Annotated[List[tuple], add_messages]
    response: str


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

@log_execution("plan_execute", "execute_step", include_args=True, include_result=True)
async def execute_step(state: PlanExecute):
    plan = state["plan"]
    plan_str = "\n".join(f"{i + 1}. {step}" for i, step in enumerate(plan))
    task = plan[0]
    task_formatted = f"""For the following plan:
{plan_str}

You are tasked with executing step {1}, {task}."""
    agent_response = await agent_executor.ainvoke(
        {
            "messages": [HumanMessage(content=task_formatted)],
            "background_operations": [],
            "background_results": {}
        }
    )
    return {
        "past_steps": [
            HumanMessage(content=task),
            agent_response["messages"][-1]
        ],
    }


@log_execution("plan_execute", "plan_step", include_args=True, include_result=True)
async def plan_step(state: PlanExecute):
    plan = await planner.ainvoke({"input": state["input"]})
    return {"plan": plan.steps}


@log_execution("plan_execute", "replan_step", include_args=True, include_result=True)
async def replan_step(state: PlanExecute):
    output = await replanner.ainvoke(state)
    if isinstance(output.action, Response):
        return {"response": output.action.response}
    else:
        return {"plan": output.action.steps}


@log_execution("plan_execute", "should_end", include_args=True, include_result=True)
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

def setup_canonical_plan_execute(llm_with_tools, llm_for_planning, agent_registry=None):
    """Set up the canonical plan-and-execute graph with LLMs and tool context."""
    
    # Get agent context from orchestrator system message generation (reuse existing logic)
    agent_context = ""
    if agent_registry:
        from .llm_handler import get_orchestrator_system_message
        
        # Create mock state to get agent context from orchestrator
        mock_state = {"summary": "", "memory": "", "active_agents": []}
        full_system_msg = get_orchestrator_system_message(mock_state, agent_registry)
        
        # Extract the ORCHESTRATOR TOOLS section for planning
        if "ORCHESTRATOR TOOLS:" in full_system_msg:
            tools_section = full_system_msg.split("ORCHESTRATOR TOOLS:")[1].split("\n\n")[0]
            agent_context = f"=== CURRENTLY AVAILABLE TOOLS ===\nORCHESTRATOR TOOLS:{tools_section}"
    
    # Import centralized prompt functions
    from src.utils.sys_msg import orchestrator_planner_sys_msg, orchestrator_replanner_sys_msg
    
    # Create prompts with dynamic agent context
    planner_prompt = ChatPromptTemplate.from_template(
        orchestrator_planner_sys_msg(agent_context)
    )
    replanner_prompt = ChatPromptTemplate.from_template(
        orchestrator_replanner_sys_msg(agent_context)
    )
    
    # Create planner and replanner with structured output and agent context
    planner = planner_prompt | llm_for_planning.with_structured_output(Plan)
    replanner = replanner_prompt | llm_for_planning.with_structured_output(Act)
    
    # Agent executor is the LLM with tools
    agent_executor = llm_with_tools
    
    # Create and return the graph
    return create_graph(agent_executor, planner, replanner)