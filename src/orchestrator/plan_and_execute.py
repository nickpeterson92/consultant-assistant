"""Exact canonical plan-and-execute implementation from LangGraph tutorial.

Reference: https://langchain-ai.github.io/langgraph/tutorials/plan-and-execute/plan-and-execute/#create-the-graph
"""

import operator
from datetime import datetime
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
from .event_decorators import emit_coordinated_events

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
    thread_id: str  # Thread ID for memory context
    task_id: str  # Task ID for SSE event correlation


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
@emit_coordinated_events(["task_lifecycle", "plan_updated"])
def execute_step(state: PlanExecute):
    import asyncio
    from .observers import get_observer_registry, SearchResultsEvent
    from src.memory import get_thread_memory, ContextType, create_memory_node
    
    # Get memory for this conversation thread
    thread_id = state.get("thread_id", "default-thread")
    memory = get_thread_memory(thread_id)
    
    # DEBUG: Log memory integration
    logger.info("MEMORY_INTEGRATION_DEBUG",
               component="orchestrator",
               operation="execute_step",
               thread_id=thread_id,
               using_memory_system=True,
               memory_nodes_count=len(memory.nodes))
    
    plan = state["plan"]
    
    # Check if plan is empty
    if not plan:
        logger.error("Empty plan received in execute_step", 
                    component="orchestrator",
                    operation="execute_step")
        return {"messages": [HumanMessage(content="Error: No plan steps available to execute")]}
    
    plan_str = "\n".join(f"{i + 1}. {step}" for i, step in enumerate(plan))
    task = plan[0]
    
    # Calculate current step number dynamically
    current_step_num = len(state.get("past_steps", [])) + 1
    
    # Include past_steps context (preserve original LangGraph structure)
    past_steps_context = ""
    past_steps = state.get("past_steps", [])
    
    logger.info(f"DEBUG: past_steps available: {len(past_steps)} steps", 
               component="orchestrator", operation="execute_step")
    
    if past_steps:
        past_steps_context = "\n\nPREVIOUS STEPS COMPLETED:\n"
        for i, (step_desc, result) in enumerate(past_steps, 1):
            past_steps_context += f"Step {i}: {step_desc}\nResult: {result}\n\n"
            logger.info(f"DEBUG: Added past step {i}: {step_desc[:50]}...", 
                       component="orchestrator", operation="execute_step")
    else:
        logger.warning("DEBUG: No past_steps found in state!", 
                      component="orchestrator", operation="execute_step")
    
    # MEMORY ENHANCEMENT: Add intelligent memory context as supplementary information
    memory_context = ""
    
    # Retrieve relevant context from memory for this task
    relevant_memories = memory.retrieve_relevant(
        query_text=f"{task} {state['input']}",
        max_age_hours=2,  # Recent context only
        min_relevance=0.3,
        max_results=5
    )
    
    logger.info("MEMORY_RETRIEVAL_DEBUG",
               component="orchestrator", 
               operation="execute_step",
               thread_id=thread_id,
               relevant_memories_count=len(relevant_memories),
               query_text=f"{task} {state['input']}"[:100])
    
    if relevant_memories:
        memory_context = "\n\nCONVERSATION CONTEXT:\n"
        
        for i, memory_node in enumerate(relevant_memories, 1):
            relevance = memory_node.current_relevance()
            memory_context += f"{i}. {memory_node.summary}\n"
            
            # Include actual content only for high-relevance items  
            if relevance > 0.7:
                content_preview = str(memory_node.content)[:200]
                memory_context += f"   {content_preview}{'...' if len(str(memory_node.content)) > 200 else ''}\n"
        
        memory_context += "\nGUIDANCE: When user requests are ambiguous, connect them to recent conversation context above - they likely reference items they just discussed.\n"
    else:
        logger.info("DEBUG: No relevant memory context found for this task", 
                   component="orchestrator", operation="execute_step")
    
    task_formatted = f"""For the following plan:
{plan_str}

You are tasked with executing step {current_step_num}: {task}.
{memory_context}
{past_steps_context}"""
    
    logger.info("TASK_FORMATTING_DEBUG",
               component="orchestrator", 
               operation="execute_step",
               thread_id=thread_id,
               task_formatted_length=len(task_formatted),
               has_past_steps_context=bool(past_steps_context),
               has_memory_context=bool(memory_context),
               memory_context_preview=memory_context[:200] if memory_context else "None")
    
    # Use ReAct agent executor which handles tool execution automatically
    agent_response = asyncio.run(agent_executor.ainvoke(
        {"messages": [("user", task_formatted)]}
    ))
    
    # Simple background task check - ReAct agent maintains own message context
    try:
        messages = agent_response.get("messages", [])
        # Access the LLM from globals (set in create_graph)
        planning_llm = globals().get('planner', {})
        if hasattr(planning_llm, 'llm'):  # Extract LLM from planner chain
            # Run background task in background thread since execute_step is sync
            asyncio.create_task(trigger_background_summary_if_needed(messages, planning_llm.llm))
        else:
            logger.debug("no_llm_for_background_tasks", 
                        component="orchestrator",
                        note="Background summarization skipped - no LLM reference available")
    except Exception as e:
        logger.debug("background_task_error",
                    component="orchestrator", 
                    error=str(e),
                    note="Background task check failed - continuing execution")
    
    # Check if agent response has messages before accessing
    messages = agent_response.get("messages", [])
    if not messages:
        logger.error("Agent response has no messages", 
                    component="orchestrator",
                    operation="execute_step")
        final_response = "Error: No response received from agent"
    else:
        final_response = messages[-1].content
    
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
    
    # MEMORY INTEGRATION: Store execution results in memory
    try:
        # Determine context type based on what the agent did
        if produced_user_data:
            context_type = ContextType.SEARCH_RESULT  # User will need to interact with this data
        else:
            context_type = ContextType.COMPLETED_ACTION  # This task is done
        
        # Extract semantic tags from the task and response
        task_words = set(task.lower().split())
        input_words = set(state["input"].lower().split())
        semantic_tags = task_words.union(input_words)
        
        # Clean up tags (remove common words)
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        semantic_tags = {tag for tag in semantic_tags if len(tag) > 2 and tag not in stop_words}
        
        # Store in memory (auto-summary will be generated from actual content)
        memory_node_id = memory.store(
            content={
                "task": task,
                "response": final_response,
                "plan_context": plan,
                "step_number": current_step_num,
                "produced_user_data": produced_user_data,
                "tool_calls": [
                    {"tool": tc.get("name"), "args": tc.get("args", {})} 
                    for msg in agent_response["messages"] 
                    if hasattr(msg, 'tool_calls') and msg.tool_calls
                    for tc in msg.tool_calls
                ]
            },
            context_type=context_type,
            tags=semantic_tags,
            base_relevance=0.9 if produced_user_data else 0.7,
            auto_summarize=True
        )
        
        logger.info("stored_execution_result_in_memory",
                   component="orchestrator",
                   operation="execute_step",
                   memory_node_id=memory_node_id,
                   context_type=context_type.value,
                   tags=list(semantic_tags),
                   produced_user_data=produced_user_data)
        
    except Exception as e:
        logger.error("failed_to_store_execution_result",
                    component="orchestrator", 
                    operation="execute_step",
                    error=str(e))
        # Don't fail the whole execution if memory storage fails
    
    return {
        "past_steps": [(task, final_response)],
    }


@log_execution("orchestrator", "plan_step", include_args=True, include_result=True)
@emit_coordinated_events(["plan_created", "plan_updated"])
def plan_step(state: PlanExecute):
    import asyncio
    from langchain_core.messages import HumanMessage
    from src.memory import get_thread_memory, ContextType
    
    # Get memory for context-aware planning
    thread_id = state.get("thread_id", "default-thread")
    memory = get_thread_memory(thread_id)
    
    # Get relevant context for planning
    planning_context = memory.retrieve_relevant(
        query_text=state["input"],
        max_age_hours=4,  # Broader context for planning
        min_relevance=0.2,
        max_results=8
    )
    
    # Format memory context for planner
    context_for_planning = ""
    if planning_context:
        context_for_planning = "\n\nRELEVANT CONTEXT:\n"
        for memory_node in planning_context:
            context_for_planning += f"- {memory_node.summary}\n"
            
            # Include domain entities and recent search results for better planning
            if memory_node.context_type in {ContextType.DOMAIN_ENTITY, ContextType.SEARCH_RESULT}:
                content_preview = str(memory_node.content)[:150]
                context_for_planning += f"  Data: {content_preview}{'...' if len(str(memory_node.content)) > 150 else ''}\n"
            context_for_planning += "\n"
    
    # Enhanced planning prompt with memory context
    planning_input = f"{state['input']}{context_for_planning}"
    
    logger.info("planning_with_memory_context",
               component="orchestrator",
               operation="plan_step",
               context_items=len(planning_context),
               input_length=len(planning_input))
    
    plan = asyncio.run(planner.ainvoke({"messages": [HumanMessage(content=planning_input)]}))
    return {"plan": plan.steps}


@log_execution("orchestrator", "replan_step", include_args=True, include_result=True)
@emit_coordinated_events(["plan_modified", "plan_updated"])
def replan_step(state: PlanExecute):
    import asyncio
    from src.memory import get_thread_memory, ContextType
    
    # Get memory for context-aware replanning
    thread_id = state.get("thread_id", "default-thread")
    memory = get_thread_memory(thread_id)
    
    # Format past_steps for the template
    past_steps_str = ""
    for i, (step, result) in enumerate(state["past_steps"]):
        past_steps_str += f"Step {i + 1}: {step}\nResult: {result}\n\n"
    
    # MEMORY ENHANCEMENT: Add recent context for replanning decisions
    replan_context = memory.retrieve_relevant(
        query_text=f"{state['input']} plan replan",
        max_age_hours=1,  # Recent context for replanning
        min_relevance=0.3,
        max_results=6
    )
    
    # Format memory context for replanner
    memory_context = ""
    if replan_context:
        memory_context = "\n\nRECENT CONTEXT:\n"
        for memory_node in replan_context:
            memory_context += f"- {memory_node.summary}\n"
            # Include high-relevance content details
            if memory_node.current_relevance() > 0.7:
                content_preview = str(memory_node.content)[:100]
                memory_context += f"  Details: {content_preview}{'...' if len(str(memory_node.content)) > 100 else ''}\n"
    
    logger.info("replan_with_memory_context",
               component="orchestrator",
               operation="replan_step", 
               context_items=len(replan_context),
               thread_id=thread_id)
    
    # Format the template variables with memory context
    template_vars = {
        "input": state["input"] + memory_context,
        "plan": "\n".join(f"{i + 1}. {step}" for i, step in enumerate(state["plan"])),
        "past_steps": past_steps_str.strip()
    }
    
    output = asyncio.run(replanner.ainvoke(template_vars))
    if isinstance(output.action, Response):
        # CRITICAL: Task is completing - trigger memory decay for task-specific context
        try:
            # Extract task-related tags from the original input and plan
            input_words = set(state["input"].lower().split())
            plan_words = set()
            for step in state["plan"]:
                plan_words.update(step.lower().split())
            
            task_tags = input_words.union(plan_words)
            # Clean up tags
            stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "step"}
            task_tags = {tag for tag in task_tags if len(tag) > 2 and tag not in stop_words}
            
            # Mark task as completed to trigger decay
            decayed_nodes = memory.mark_task_completed(task_related_tags=task_tags)
            
            logger.info("task_completion_detected",
                       component="orchestrator",
                       operation="replan_step",
                       thread_id=thread_id,
                       task_tags=list(task_tags),
                       decayed_nodes=decayed_nodes)
            
        except Exception as e:
            logger.error("failed_to_mark_task_completed",
                        component="orchestrator",
                        operation="replan_step", 
                        error=str(e))
        
        return {"response": output.action.response}
    else:
        # Check if the new plan includes human_input - if so, show the most recent result to user
        new_plan = output.action.steps
        user_visible_responses = []
        
        # If any plan step mentions human_input, show the most recent past step result to user
        past_steps = state.get("past_steps", [])
        if any("human_input" in step.lower() for step in new_plan) and past_steps:
            last_step, last_result = past_steps[-1]
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

import time

# Background task tracking - simple approach
_last_summary_time = 0
_last_summary_message_count = 0

def should_trigger_background_summary(message_count: int) -> bool:
    """Simple background summary trigger - aligned with main branch approach."""
    global _last_summary_time, _last_summary_message_count
    
    current_time = time.time()
    
    # Trigger every 10 messages (configurable)
    message_threshold = 10
    if message_count - _last_summary_message_count >= message_threshold:
        return True
    
    # Trigger every 5 minutes if there are new messages
    time_threshold = 300  # 5 minutes
    if current_time - _last_summary_time >= time_threshold and message_count > _last_summary_message_count:
        return True
    
    return False

def update_background_summary_tracking(message_count: int):
    """Update background summary tracking."""
    global _last_summary_time, _last_summary_message_count
    _last_summary_time = time.time()
    _last_summary_message_count = message_count

async def trigger_background_summary_if_needed(messages: list, llm):
    """Simple background summarization trigger for ReAct agent."""
    if not should_trigger_background_summary(len(messages)):
        return
    
    logger.info("triggering_background_summary",
               component="orchestrator",
               message_count=len(messages))
    
    # Update tracking
    update_background_summary_tracking(len(messages))
    
    # Simple background summary - could be enhanced later
    # For now, just log that we would summarize
    logger.info("background_summary_triggered",
               component="orchestrator", 
               message_count=len(messages),
               note="ReAct agent maintains own context - summary would be stored externally")

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