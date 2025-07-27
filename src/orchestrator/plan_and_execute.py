"""Exact canonical plan-and-execute implementation from LangGraph tutorial.

Reference: https://langchain-ai.github.io/langgraph/tutorials/plan-and-execute/plan-and-execute/#create-the-graph
"""

import asyncio
import time
from datetime import datetime
from typing import List, Union
from pydantic import BaseModel, Field, validator

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from langchain_core.messages import HumanMessage, AIMessage
from src.utils.logging.framework import SmartLogger, log_execution
from src.orchestrator.workflow.event_decorators import emit_coordinated_events
from src.orchestrator.workflow.memory_context_builder import MemoryContextBuilder
from src.orchestrator.core.state import PlanExecute, StepExecution

# Initialize logger
logger = SmartLogger("orchestrator")


# ================================
# Models - EXACT from tutorial
# ================================


class Plan(BaseModel):
    """Plan to follow in future"""

    steps: List[str] = Field(
        description="different steps to follow, should be in sorted order"
    )

    @validator("steps", each_item=True)
    def validate_steps(cls, v):
        if v is None or v == "":
            raise ValueError("Plan step cannot be None or empty")
        return v


class Response(BaseModel):
    """Response to user."""

    response: str


class Act(BaseModel):
    """Action to perform."""

    action: Union[Response, Plan] = Field(
        description="CRITICAL: Only use Response when ALL original plan steps are completed. "
        "Use Plan if ANY steps remain unfinished. "
        "Count completed steps vs total original plan steps - if completed < total, use Plan."
    )


# ================================
# Prompts - EXACT from tutorial
# ================================

# Prompts are now generated dynamically with agent context in setup function


# ================================
# Node Functions - EXACT from tutorial
# ================================


@log_execution(
    "orchestrator", "execute_step", include_args=True, include_result=False
)  # Don't log full result due to size
@emit_coordinated_events(["task_lifecycle", "plan_updated"])
async def execute_step(state: PlanExecute):
    import asyncio
    from src.orchestrator.observers import get_observer_registry, SearchResultsEvent
    from src.memory import (
        get_user_memory,
        get_memory_manager,
        ContextType,
        RelationshipType,
    )
    from langgraph.errors import GraphInterrupt

    # Check for user-initiated interrupt flag (escape key) FIRST
    # This takes precedence over any agent interrupts
    if state.get("user_interrupted", False):
        interrupt_reason = state.get(
            "interrupt_reason", "User requested plan modification"
        )
        logger.info(
            "execution_interrupted_by_user",
            component="orchestrator",
            operation="execute_step",
            reason=interrupt_reason,
            note="User interrupt takes precedence over agent interrupts",
        )
        # Raise GraphInterrupt with special marker for user interrupts
        raise GraphInterrupt({"type": "user_escape", "reason": interrupt_reason})

    # Get memory for this conversation thread
    thread_id = state.get("thread_id", "default-thread")
    # Use user_id for memory isolation if available
    user_id = state.get("user_id")
    memory_key = user_id if user_id else thread_id

    # Get memory asynchronously
    memory = await get_user_memory(memory_key)

    # Get conversation summary from SQLite if available and not already in state
    if "summary" not in state:
        from src.utils.storage import get_global_sqlite_store

        global_sqlite_store = get_global_sqlite_store()
        if global_sqlite_store:
            user_id = state.get("user_id", "default_user")
            namespace = ("memory", user_id)
            key = "conversation_summary"
            summary_data = global_sqlite_store.get(namespace, key)
            if summary_data and isinstance(summary_data, dict):
                state["summary"] = summary_data.get("summary")

    # DEBUG: Log memory integration
    logger.info(
        "MEMORY_INTEGRATION_DEBUG",
        component="orchestrator",
        operation="execute_step",
        thread_id=thread_id,
        using_memory_system=True,
        memory_nodes_count=memory.node_manager.get_node_count(),
    )

    plan = state["plan"]

    # Check if plan is empty
    if not plan:
        logger.error(
            "execute_step_no_plan",
            operation="execute_step",
            thread_id=thread_id,
            state_keys=list(state.keys()),
        )
        return {
            "messages": [
                HumanMessage(content="Error: No plan steps available to execute")
            ]
        }

    plan_str = "\n".join(f"{i + 1}. {step}" for i, step in enumerate(plan))
    task = plan[0]

    # Calculate current step number dynamically - relative to current plan
    plan_offset = state.get("plan_step_offset", 0)
    current_plan_steps = state.get("past_steps", [])[plan_offset:]
    current_step_num = len(current_plan_steps) + 1

    # Include past_steps context - only from current plan
    past_steps_context = ""

    if current_plan_steps:
        past_steps_context = "\n\nPREVIOUS STEPS COMPLETED:\n"
        for step in current_plan_steps:
            past_steps_context += f"Step {step['step_seq_no']}: {step['step_description']}\nResult: {step['result']}\n\n"

    # MEMORY ENHANCEMENT: Use advanced memory context builder
    # Use user_id for memory retrieval (user-scoped memory)
    user_id = state.get("user_id", "default_user")
    memory_context, memory_metadata = await MemoryContextBuilder.build_enhanced_context(
        thread_id=user_id,  # Using user_id for user-scoped memory
        query_text=f"{task} {state['input']}",
        context_type="execution",
        max_age_hours=2,
        min_relevance=0.3,
        max_results=10,
    )

    logger.info(
        "memory_context_built",
        component="orchestrator",
        operation="execute_step",
        relevant_count=memory_metadata.get("relevant_count", 0),
        important_count=memory_metadata.get("important_count", 0),
        cluster_count=memory_metadata.get("cluster_count", 0),
        bridge_count=memory_metadata.get("bridge_count", 0),
        thread_id=thread_id,
    )

    # Get execution insights using memory analyzer
    try:
        from src.orchestrator.workflow.memory_analyzer import MemoryAnalyzer

        execution_insights = await MemoryAnalyzer.get_execution_insights(
            user_id, task
        )  # Use user_id instead of thread_id

        if execution_insights["potential_pitfalls"]:
            memory_context += "\n\nCAUTION:\n"
            for pitfall in execution_insights["potential_pitfalls"]:
                memory_context += f"- {pitfall['warning']}\n"

        if execution_insights["similar_past_tasks"]:
            memory_context += "\n\nSIMILAR PAST TASKS:\n"
            for past_task in execution_insights["similar_past_tasks"][:2]:
                memory_context += f"- {past_task['task']} ({past_task['time_ago']})\n"

        logger.info(
            "execution_insights_added",
            pitfalls=len(execution_insights["potential_pitfalls"]),
            similar_tasks=len(execution_insights["similar_past_tasks"]),
        )
    except Exception as e:
        logger.warning("execution_insights_failed", error=str(e))

    # SCHEMA INJECTION: Add relevant schemas based on task
    from src.utils.schema_knowledge import get_schema_knowledge

    schema_kb = get_schema_knowledge()

    # Get schemas relevant to this task
    schema_context = schema_kb.get_schema_context(
        query=f"{task} {state.get('input', '')}",
        max_schemas=2,  # Don't overwhelm context
    )

    # Format the clean task instruction for the user message
    task_instruction = f"""For the following plan:
{plan_str}

You are tasked with executing step {current_step_num}: {task}"""

    # Format the context as a system message
    context_system_message = f"""RELEVANT CONTEXT for this task execution:
{memory_context}
{schema_context}
{past_steps_context}

Remember: This context is for reference only. Focus on executing the specific task requested."""

    # Skip emitting execution context to UI - only show planning contexts
    # This simplifies the UI by showing only the initial planning context

    logger.info(
        "TASK_FORMATTING_DEBUG",
        component="orchestrator",
        operation="execute_step",
        thread_id=thread_id,
        task_instruction_length=len(task_instruction),
        context_system_length=len(context_system_message),
        has_past_steps_context=bool(past_steps_context),
        has_memory_context=bool(memory_context),
        memory_context_preview=memory_context[:200] if memory_context else "None",
    )

    # Use ReAct agent executor with full conversation context
    # Merge persistent conversation messages with current task
    persistent_messages = state.get("messages", [])

    # Create agent messages by combining conversation history with current task
    agent_messages = list(persistent_messages)  # Copy conversation history

    # Add context as system message first, then the task as user message
    agent_messages.append(("system", context_system_message))  # Add context as system
    agent_messages.append(("user", task_instruction))  # Add clean task instruction

    # Trim for ReAct agent context to prevent bloat
    from src.utils.agents.message_processing.helpers import trim_messages_for_context

    if len(agent_messages) > 15:  # Keep ReAct agent context focused
        agent_messages = trim_messages_for_context(
            agent_messages,
            max_tokens=40000,  # Conservative for execution context
            keep_last_n=15,  # Recent conversation + current task
        )

    logger.info(
        "react_agent_context",
        operation="execute_step",
        conversation_messages=len(persistent_messages),
        agent_messages=len(agent_messages),
        current_task=task[:100],
    )

    # Log ReAct agent invocation start
    react_start_time = time.time()
    logger.info(
        "react_agent_start",
        operation="execute_step",
        thread_id=thread_id,
        step_number=current_step_num,
        agent_input_messages=len(agent_messages),
        task_description=task[:150],
    )

    try:
        # Final check for user interrupt before agent execution
        if state.get("user_interrupted", False):
            logger.info(
                "user_interrupt_preempts_agent",
                component="orchestrator",
                operation="execute_step",
                note="User interrupt detected - skipping agent execution",
            )
            raise GraphInterrupt(
                {
                    "type": "user_escape",
                    "reason": state.get(
                        "interrupt_reason", "User requested modification"
                    ),
                }
            )

        agent_executor = globals().get("agent_executor")
        if not agent_executor:
            raise RuntimeError("Agent executor not initialized")

        # Pass full state to agent so tools can access it via InjectedState
        agent_input = {
            "messages": agent_messages,
            "thread_id": thread_id,
            "user_id": state.get("user_id"),
            "task_id": state.get("task_id"),
            "memory_context": memory_context,
            "schema_context": schema_context,
            "past_steps": state.get("past_steps", []),
        }

        agent_response = asyncio.run(agent_executor.ainvoke(agent_input))

        # Log ReAct agent completion
        react_duration = time.time() - react_start_time
        response_messages = agent_response.get("messages", [])
        logger.info(
            "react_agent_complete",
            operation="execute_step",
            thread_id=thread_id,
            duration_seconds=round(react_duration, 3),
            response_messages=len(response_messages),
            has_tool_calls=any(
                hasattr(msg, "tool_calls") and msg.tool_calls
                for msg in response_messages
            ),
            success=True,
        )

    except Exception as e:
        react_duration = time.time() - react_start_time

        # Check if this is a GraphInterrupt (agent asking for clarification)
        from langgraph.errors import GraphInterrupt

        if isinstance(e, GraphInterrupt):
            # This is expected behavior - log as INFO, not ERROR
            # Extract actual interrupt type from the interrupt data
            interrupt_type_value = "unknown"
            try:
                if e.args and len(e.args) > 0:
                    interrupt_data = e.args[0]
                    if hasattr(interrupt_data, "value") and isinstance(
                        interrupt_data.value, dict
                    ):
                        interrupt_type_value = interrupt_data.value.get(
                            "interrupt_type", "unknown"
                        )
            except Exception:
                pass

            logger.info(
                "react_agent_interrupt",
                operation="execute_step",
                thread_id=thread_id,
                duration_seconds=round(react_duration, 3),
                interrupt_value=str(e.args[0]) if e.args else "",
                interrupt_type=interrupt_type_value,
            )
        else:
            # This is an actual error
            logger.error(
                "react_agent_error",
                operation="execute_step",
                thread_id=thread_id,
                duration_seconds=round(react_duration, 3),
                error=str(e),
                error_type=type(e).__name__,
            )
        raise

    # Simple background task check - ReAct agent maintains own message context
    try:
        messages = agent_response.get("messages", [])
        # Access the LLM from globals (set in create_graph)
        planning_llm = globals().get("planner", {})
        if hasattr(planning_llm, "llm"):  # Extract LLM from planner chain
            # Run background task in background thread since execute_step is sync
            user_id = state.get("user_id", "default_user")
            asyncio.create_task(
                trigger_background_summary_if_needed(
                    messages, planning_llm.llm, user_id
                )
            )
        else:
            logger.debug(
                "no_llm_for_background_tasks",
                component="orchestrator",
                note="Background summarization skipped - no LLM reference available",
            )
    except Exception as e:
        logger.debug(
            "background_task_error",
            component="orchestrator",
            error=str(e),
            note="Background task check failed - continuing execution",
        )

    # Check if agent response has messages before accessing
    messages = agent_response.get("messages", [])
    if not messages:
        logger.error(
            "Agent response has no messages",
            component="orchestrator",
            operation="execute_step",
        )
        final_response = "Error: No response received from agent"
    else:
        # Extract tool response data if present
        tool_response_data = None
        for message in messages:
            # Check for tool response messages (ToolMessage type)
            if hasattr(message, "name") and hasattr(message, "content"):
                # This is a tool response message
                try:
                    import json

                    # First try to parse as JSON
                    if message.content.startswith("{") or message.content.startswith(
                        "["
                    ):
                        try:
                            tool_result = json.loads(message.content)
                            if isinstance(tool_result, dict):
                                if tool_result.get("success", False):
                                    tool_response_data = tool_result.get("data")
                        except (json.JSONDecodeError, ValueError):
                            # If not JSON, it might be plain text response
                            pass

                    # For agent tool responses, the content might be a string representation
                    # Let's save the raw content for entity extraction
                    if (
                        "salesforce_agent" in getattr(message, "name", "")
                        or "jira_agent" in getattr(message, "name", "")
                        or "servicenow_agent" in getattr(message, "name", "")
                    ):
                        # This is an agent response (entity extraction handled elsewhere)
                        pass
                except (AttributeError, TypeError):
                    pass

        # Get the agent's final message
        agent_final_message = messages[-1].content

        # If we have tool response data from a GET operation, include it in the response
        if (
            tool_response_data
            and task
            and any(
                word in task.lower()
                for word in [
                    "get",
                    "retrieve",
                    "fetch",
                    "show",
                    "display",
                    "find",
                    "search",
                ]
            )
        ):
            # Format the data nicely if it's a dict/list
            if isinstance(tool_response_data, (dict, list)):
                import json

                formatted_data = json.dumps(tool_response_data, indent=2)
                final_response = f"{agent_final_message}\n\nHere's the data:\n```json\n{formatted_data}\n```"
            else:
                final_response = (
                    f"{agent_final_message}\n\nHere's the data:\n{tool_response_data}"
                )
        else:
            final_response = agent_final_message

    # Check if any tools used during execution produce user data
    # We need to get the available tools to check their metadata
    from src.agents.salesforce.tools.unified import UNIFIED_SALESFORCE_TOOLS
    from src.agents.jira.tools.unified import UNIFIED_JIRA_TOOLS
    from src.agents.servicenow.tools.unified import UNIFIED_SERVICENOW_TOOLS

    # Build a lookup of all available tools using the unified constants
    all_tools = (
        list(UNIFIED_SALESFORCE_TOOLS)
        + list(UNIFIED_JIRA_TOOLS)
        + list(UNIFIED_SERVICENOW_TOOLS)
    )

    tool_lookup = {tool.name: tool for tool in all_tools}

    # Check actual tool calls made during execution
    produced_user_data = False
    for message in agent_response["messages"]:
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tool_call in message.tool_calls:
                tool_name = tool_call.get("name", "")

                # Look up the tool to check its metadata
                if tool_name in tool_lookup:
                    tool = tool_lookup[tool_name]
                    if getattr(tool, "produces_user_data", False):
                        produced_user_data = True
                        break

    # Notify observers if user data was produced
    if produced_user_data:
        registry = get_observer_registry()
        event = SearchResultsEvent(
            step_name=task,
            results=final_response,
            tool_name="data_producing_operation",
            is_user_selectable=True,
        )
        registry.notify_search_results(event)

    # MEMORY INTEGRATION: Store execution results in memory (with noise reduction)
    try:
        # Determine context type based on what the agent did
        if produced_user_data:
            context_type = (
                ContextType.SEARCH_RESULT
            )  # User will need to interact with this data
        else:
            # Filter out routine actions to reduce memory noise
            # Only store significant completed actions that modify state or contain entity references
            import re

            significant_patterns = [
                r"created.*(account|contact|opportunity|case|ticket|issue|project)",
                r"updated.*(status|stage|priority|assignment)",
                r"resolved|closed|completed|fixed",
                r"assigned.*to",
                r"deployed|migrated|configured",
                r"deleted|removed|archived",
                r"approved|rejected|escalated",
                r"merged|integrated|synchronized",
            ]

            # Combine task and response for pattern matching
            task_and_response = f"{task} {final_response}".lower()
            is_significant = any(
                re.search(pattern, task_and_response)
                for pattern in significant_patterns
            )

            # Also check for entity IDs which indicate significant operations
            entity_patterns = [
                r"\b[a-zA-Z0-9]{15,18}\b",  # Salesforce IDs
                r"\b[A-Z]+-\d+\b",  # Jira keys
                r"\b(INC|CHG|PRB)\d{7}\b",  # ServiceNow numbers
            ]
            has_entity_refs = any(
                re.search(pattern, final_response) for pattern in entity_patterns
            )

            if not is_significant and not has_entity_refs:
                # Don't store routine actions
                logger.debug(
                    "skipping_routine_action",
                    task=task[:50] if task else "none",
                    reason="not_significant",
                )
                return {"agent_response": final_response}

            # Skip storing completed actions - focus on domain entities only
            logger.info(
                "skipping_completed_action_storage",
                task=task[:50] if task else "none",
                reason="focusing_on_domain_entities_only",
            )
            return {"agent_response": final_response}

        # Use intelligent entity extraction

        # Initialize variables for memory storage
        semantic_tags = set()
        relates_to = []

        # Add semantic tags based on the operation type
        if produced_user_data:
            semantic_tags.add("search_result")
            semantic_tags.add("user_data")

        # Add tags based on agent used
        extraction_context = {"task": task, "agent": "unknown"}

        # Identify which agent was used
        for message in agent_response.get("messages", []):
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_name = tool_call.get("name", "").lower()
                    if "salesforce" in tool_name:
                        extraction_context["agent"] = "salesforce"
                        extraction_context["system"] = "salesforce"
                        break
                    elif "jira" in tool_name:
                        extraction_context["agent"] = "jira"
                        extraction_context["system"] = "jira"
                        break
                    elif "servicenow" in tool_name:
                        extraction_context["agent"] = "servicenow"
                        extraction_context["system"] = "servicenow"
                        break

        # Add agent-specific tags
        if extraction_context["agent"] != "unknown":
            semantic_tags.add(extraction_context["agent"])
            semantic_tags.add(f"{extraction_context['agent']}_operation")

        # Entity extraction now happens at the agent level
        # Agents extract entities from tool results and store them directly in memory
        # The orchestrator can simply query for DOMAIN_ENTITY nodes when needed

        # Get recently created domain entities from memory
        # With user_id based memory, all entities are in the same memory space
        related_entities = []

        # Get previous step node IDs for creating relationships
        past_steps = state.get("past_steps", [])
        if past_steps and len(past_steps) > 0:
            # Find the memory node ID from the most recent step
            # This assumes past steps contain memory_node_ids
            # For now, we'll leave relates_to empty since we'd need to query memory
            # to find the actual node IDs from previous steps
            pass
        try:
            # Query for recent domain entities created during this task
            recent_entities = memory.retrieve_relevant(
                query_text="",
                context_filter={ContextType.DOMAIN_ENTITY},
                max_age_hours=0.1,  # Last 6 minutes
                max_results=20,
            )
            for entity_node in recent_entities:
                related_entities.append(entity_node.node_id)
                # Update access time
                entity_node.access()

            logger.info(
                "found_agent_created_entities",
                component="orchestrator",
                operation="execute_step",
                entity_count=len(related_entities),
            )

        except Exception as e:
            logger.debug(f"Could not retrieve recent entities: {e}")

        # Store in memory (auto-summary will be generated from actual content)
        # Get memory manager for async operations
        memory_manager = get_memory_manager()
        memory_node_id = await memory_manager.store_memory(
            memory_key,  # Use the same key (user_id or thread_id)
            content={
                "task": task,
                "response": final_response,
                "plan_context": plan,
                "step_number": current_step_num,
                "produced_user_data": produced_user_data,
                "tool_calls": [
                    {"tool": tc.get("name"), "args": tc.get("args", {})}
                    for msg in agent_response["messages"]
                    if hasattr(msg, "tool_calls") and msg.tool_calls
                    for tc in msg.tool_calls
                ],
            },
            context_type=context_type,
            summary=f"Step {current_step_num}: {task[:50]}{'...' if len(task) > 50 else ''} - {context_type.value}",
            tags=semantic_tags,
            confidence=0.9 if produced_user_data else 0.7,
            relates_to=relates_to,  # Create relationship to previous step
        )

        # Create relationships
        # 1. Led-to relationship with previous step
        if relates_to and len(relates_to) > 0:
            await memory_manager.add_relationship(
                memory_key,
                relates_to[0],  # Previous step
                memory_node_id,  # Current step
                RelationshipType.LED_TO,
            )

            # Notify observer about the edge
            try:
                from src.orchestrator.observers.memory_observer import (
                    notify_memory_edge,
                )

                notify_memory_edge(
                    thread_id,
                    relates_to[0],
                    memory_node_id,
                    RelationshipType.LED_TO,
                    state.get("task_id"),
                )
            except Exception as e:
                logger.warning("memory_edge_notification_failed", error=str(e))

        # 2. Relationships with entities this action interacted with
        for entity_id in related_entities:
            # Determine relationship type based on action
            if produced_user_data:
                # This action retrieved/searched for the entity
                rel_type = RelationshipType.ANSWERS  # Action answers query about entity
                memory.add_relationship(memory_node_id, entity_id, rel_type)
            else:
                # This action modified or worked with the entity
                rel_type = RelationshipType.REFINES  # Action refines/updates entity
                await memory_manager.add_relationship(
                    memory_key, memory_node_id, entity_id, rel_type
                )

            # No reverse relationship needed - actions lead to entities, not vice versa

            # Notify about relationships
            try:
                from src.orchestrator.observers.memory_observer import (
                    notify_memory_edge,
                )

                notify_memory_edge(
                    thread_id, memory_node_id, entity_id, rel_type, state.get("task_id")
                )
                # Removed backwards edge - entity shouldn't point back to action
            except Exception as e:
                logger.debug(f"Memory edge notification failed: {e}")
                pass

        # 3. If we detected tool calls, create tool_output nodes
        tool_calls = [
            {"tool": tc.get("name"), "args": tc.get("args", {})}
            for msg in agent_response["messages"]
            if hasattr(msg, "tool_calls") and msg.tool_calls
            for tc in msg.tool_calls
        ]

        for tool_call in tool_calls:
            tool_node_id = memory.store(
                content={
                    "tool": tool_call["tool"],
                    "args": tool_call["args"],
                    "timestamp": datetime.now().isoformat(),
                },
                context_type=ContextType.TOOL_OUTPUT,
                tags={tool_call["tool"].lower()} if tool_call["tool"] else set(),
                confidence=0.6,
                summary=f"Tool call: {tool_call['tool']}",
            )

            # Action depends on the tool/agent to execute it
            memory.add_relationship(
                memory_node_id, tool_node_id, RelationshipType.DEPENDS_ON
            )

            # Notify
            try:
                from src.orchestrator.observers.memory_observer import (
                    notify_memory_update,
                    notify_memory_edge,
                )

                node = memory.node_manager.get_node(tool_node_id)
                if node:
                    await notify_memory_update(
                        thread_id,
                        tool_node_id,
                        node,
                        state.get("task_id"),
                        state.get("user_id"),
                    )
                notify_memory_edge(
                    thread_id,
                    memory_node_id,
                    tool_node_id,
                    RelationshipType.DEPENDS_ON,
                    state.get("task_id"),
                )
            except Exception as e:
                logger.debug(f"Memory tool notification failed: {e}")
                pass

        logger.info(
            "stored_execution_result_in_memory",
            component="orchestrator",
            operation="execute_step",
            memory_node_id=memory_node_id,
            context_type=context_type.value,
            tags=list(semantic_tags),
            produced_user_data=produced_user_data,
            linked_to_previous=bool(relates_to),
        )

        # Notify observers about memory update
        try:
            from src.orchestrator.observers.memory_observer import notify_memory_update

            node = memory.node_manager.get_node(memory_node_id)
            if node:
                await notify_memory_update(
                    thread_id,
                    memory_node_id,
                    node,
                    state.get("task_id"),
                    state.get("user_id"),
                )
        except Exception as e:
            logger.warning("memory_observer_notification_failed", error=str(e))

    except Exception as e:
        logger.error(
            "failed_to_store_execution_result",
            component="orchestrator",
            operation="execute_step",
            error=str(e),
        )
        # Don't fail the whole execution if memory storage fails

    # Extract new messages from ReAct agent response to merge with conversation
    agent_messages = agent_response.get("messages", [])
    new_messages = []

    # Find messages that weren't in our original conversation
    original_count = len(persistent_messages)
    if (
        len(agent_messages) > original_count + 1
    ):  # More than conversation + current task
        # Get the new AI messages (tool calls, responses, etc.)
        new_messages = agent_messages[original_count + 1 :]  # Skip conversation + task

        logger.info(
            "merging_react_agent_messages",
            component="orchestrator",
            operation="execute_step",
            new_messages_count=len(new_messages),
            final_response_preview=final_response[:100],
        )

    # Create StepExecution entry
    step_execution: StepExecution = {
        "step_seq_no": current_step_num,
        "step_description": task,
        "status": "completed",  # Will be updated by event decorators if failed
        "result": final_response,
    }

    # Append the current step execution to existing past_steps
    existing_past_steps = state.get("past_steps", [])
    updated_past_steps = existing_past_steps + [step_execution]
    
    return {
        "past_steps": updated_past_steps,
        "messages": new_messages,  # Merge ReAct agent's new messages into conversation
    }


@log_execution("orchestrator", "plan_step", include_args=True, include_result=True)
@emit_coordinated_events(["plan_created", "plan_updated"])
async def plan_step(state: PlanExecute):
    from langchain_core.messages import HumanMessage
    from src.memory import get_user_memory
    from langgraph.errors import GraphInterrupt

    # Check for user-initiated interrupt flag (escape key)
    if state.get("user_interrupted", False):
        interrupt_reason = state.get(
            "interrupt_reason", "User requested plan modification"
        )
        logger.info(
            "planning_interrupted_by_user",
            component="orchestrator",
            operation="plan_step",
            reason=interrupt_reason,
        )
        # Raise GraphInterrupt with special marker for user interrupts
        raise GraphInterrupt({"type": "user_escape", "reason": interrupt_reason})

    # Get memory for context-aware planning
    thread_id = state.get("thread_id", "default-thread")
    # Use user_id for memory isolation if available
    user_id = state.get("user_id")
    memory_key = user_id if user_id else thread_id
    memory = await get_user_memory(memory_key)

    # Get conversation summary from SQLite if available
    conversation_summary = None
    from src.utils.storage import get_global_sqlite_store

    global_sqlite_store = get_global_sqlite_store()
    if global_sqlite_store:
        user_id = state.get("user_id", "default_user")
        namespace = ("memory", user_id)
        key = "conversation_summary"
        summary_data = global_sqlite_store.get(namespace, key)
        if summary_data and isinstance(summary_data, dict):
            conversation_summary = summary_data.get("summary")
            logger.info(
                "retrieved_conversation_summary",
                component="orchestrator",
                thread_id=thread_id,
                summary_length=len(conversation_summary) if conversation_summary else 0,
                summary_timestamp=summary_data.get("timestamp"),
            )

    # Update state with summary for agent context
    if conversation_summary:
        state["summary"] = conversation_summary

    # Get conversation messages for context and trim if needed
    conversation_messages = state.get("messages", [])

    # Trim messages to prevent bloat while preserving context
    from src.utils.agents.message_processing.helpers import trim_messages_for_context

    if len(conversation_messages) > 20:  # Only trim if conversation is getting long
        conversation_messages = trim_messages_for_context(
            conversation_messages,
            max_tokens=60000,  # Conservative limit for planning context
            keep_last_n=20,  # Keep recent conversation flow
        )

    logger.info(
        "planning_with_conversation_context",
        component="orchestrator",
        operation="plan_step",
        original_length=len(state.get("messages", [])),
        trimmed_length=len(conversation_messages),
        current_input=state["input"][:100],
    )

    # Use enhanced memory context for planning
    (
        planning_context,
        planning_metadata,
    ) = await MemoryContextBuilder.build_enhanced_context(
        thread_id=memory_key,  # Use memory_key (user_id if available)
        query_text=state["input"],
        context_type="planning",
        max_age_hours=4,
        min_relevance=0.2,
        max_results=15,
    )

    # Get conversation summary using important memories
    if memory.node_manager.get_node_count() > 5:
        conversation_summary = await MemoryContextBuilder.get_conversation_summary(
            memory_key
        )

    # Format memory context for planner
    context_for_planning = ""

    # Add conversation summary if available
    if conversation_summary:
        context_for_planning = "\n\n" + conversation_summary + "\n"

    # Add enhanced planning context
    if planning_context:
        context_for_planning += planning_context

    # Clean user request without any context
    planning_input = state["input"]

    logger.info(
        "planning_with_memory_context",
        component="orchestrator",
        operation="plan_step",
        relevant_count=planning_metadata.get("relevant_count", 0),
        important_count=planning_metadata.get("important_count", 0),
        cluster_count=planning_metadata.get("cluster_count", 0),
        has_conversation_summary=bool(conversation_summary),
        input_length=len(planning_input),
    )

    # Emit LLM context event for UI visualization
    try:
        from src.orchestrator.workflow.emit_llm_context import emit_llm_context

        emit_llm_context(
            context_type="planning",
            context_text=context_for_planning,
            metadata=planning_metadata,
            full_prompt=planning_input,
            task_id=state.get("task_id"),
            thread_id=thread_id,
            step_name="plan_step",
        )
    except Exception as e:
        logger.warning("llm_context_emission_failed", error=str(e))

    # Use conversation messages for planning context instead of just current input
    planning_messages = list(conversation_messages)  # Copy existing conversation

    # Add context as system message if we have any
    if context_for_planning:
        from langchain_core.messages import SystemMessage

        planning_messages.append(
            SystemMessage(content=f"PLANNING CONTEXT:\n{context_for_planning}")
        )

    # Add clean user request
    planning_messages.append(HumanMessage(content=planning_input))

    planner = globals().get("planner")
    if not planner:
        raise RuntimeError("Planner not initialized")

    plan = await planner.ainvoke({"messages": planning_messages})

    # DEBUG: Log what the planner returned
    logger.info(
        "PLANNER_OUTPUT_DEBUG",
        component="orchestrator",
        operation="plan_step",
        plan_type=type(plan).__name__,
        is_plan=hasattr(plan, "steps"),
        is_response=hasattr(plan, "response"),
        plan_steps=plan.steps if hasattr(plan, "steps") else None,
        response_text=plan.response if hasattr(plan, "response") else None,
        input_preview=state["input"][:200],
    )

    # Emit plan created event for live UI updates
    try:
        from src.orchestrator.observers import get_observer_registry, PlanCreatedEvent

        registry = get_observer_registry()
        event = PlanCreatedEvent(
            step_name="plan_creation",
            task_id=state.get("task_id", thread_id),
            plan_steps=plan.steps,
            total_steps=len(plan.steps),
        )
        registry.notify_plan_created(event)
        logger.info(
            "plan_created_event_emitted",
            component="orchestrator",
            thread_id=thread_id,
            total_steps=len(plan.steps),
        )
    except Exception as e:
        logger.error("failed_to_emit_plan_created", error=str(e))

    # Emit memory graph snapshot after plan creation
    try:
        from src.orchestrator.observers.memory_observer import get_memory_observer

        observer = get_memory_observer()
        await observer.emit_graph_snapshot(
            thread_id, state.get("task_id"), state.get("user_id")
        )
    except Exception as e:
        logger.warning("memory_snapshot_emission_failed", error=str(e))

    # Intelligent culling: Keep only recent plan history
    past_steps = state.get("past_steps", [])
    current_past_steps_length = len(past_steps)

    # If we have too many steps accumulated, keep only the most recent ones
    if current_past_steps_length > 50:  # Threshold for culling
        # Keep last 30 steps (roughly 2-3 plans worth)
        steps_to_keep = 30
        past_steps = past_steps[-steps_to_keep:]

        logger.info(
            "culled_past_steps",
            operation="plan_step",
            original_count=current_past_steps_length,
            new_count=len(past_steps),
            culled_count=current_past_steps_length - len(past_steps),
        )

        # After culling, the new plan starts at the current length
        return {
            "plan": plan.steps,
            "plan_step_offset": len(past_steps),  # New plan starts after culled steps
            "past_steps": past_steps,
        }

    # No culling needed
    return {"plan": plan.steps, "plan_step_offset": current_past_steps_length}


@log_execution("orchestrator", "replan_step", include_args=True, include_result=True)
@emit_coordinated_events(["plan_modified", "plan_updated"])
async def replan_step(state: PlanExecute):
    import asyncio
    from src.orchestrator.workflow.interrupt_handler import InterruptHandler

    # Check if this is a user-initiated replan (escape key)
    is_user_replan = state.get("should_force_replan", False) or state.get(
        "user_interrupted", False
    )
    user_modification_request = state.get("user_modification_request", "")

    if is_user_replan:
        logger.info(
            "user_initiated_replan",
            component="orchestrator",
            operation="replan_step",
            reason=state.get("interrupt_reason", "User requested modification"),
            user_request=user_modification_request[:100]
            if user_modification_request
            else "",
        )

    # Get memory for context-aware replanning
    thread_id = state.get("thread_id", "default-thread")
    # Use user_id for memory isolation if available
    user_id = state.get("user_id")
    memory_key = user_id if user_id else thread_id
    # Memory is accessed through MemoryContextBuilder

    # Format past_steps for the template - only include steps from current plan
    plan_offset = state.get("plan_step_offset", 0)
    current_plan_steps = state["past_steps"][
        plan_offset:
    ]  # Only steps from current plan

    past_steps_str = ""
    for step in current_plan_steps:
        past_steps_str += f"Step {step['step_seq_no']}: {step['step_description']}\nResult: {step['result']}\n\n"

    # MEMORY ENHANCEMENT: Use advanced context for replanning
    # Use the original input plus recent step descriptions for better matching
    recent_steps = " ".join(
        [step["step_description"] for step in current_plan_steps[-3:]]
    )
    query_for_memory = f"{state['input']} {recent_steps}".strip()

    memory_context, replan_metadata = await MemoryContextBuilder.build_enhanced_context(
        thread_id=memory_key,  # Use memory_key (user_id if available)
        query_text=query_for_memory,
        context_type="replanning",
        max_age_hours=1,
        min_relevance=0.3,
        max_results=10,
    )

    logger.info(
        "replan_with_memory_context",
        component="orchestrator",
        operation="replan_step",
        relevant_count=replan_metadata.get("relevant_count", 0),
        important_count=replan_metadata.get("important_count", 0),
        cluster_count=replan_metadata.get("cluster_count", 0),
        bridge_count=replan_metadata.get("bridge_count", 0),
        thread_id=thread_id,
    )

    # Add user modification context if this is a user-initiated replan
    additional_context = ""
    if user_modification_request:
        additional_context = InterruptHandler.prepare_replan_context(state)

    # Build context for replanner
    full_context = ""
    if memory_context:
        full_context = f"REPLANNING CONTEXT:\n{memory_context}"
    if additional_context:
        full_context += f"\n\n{additional_context}"

    # Format the template variables WITHOUT context in input
    template_vars = {
        "input": state["input"],  # Clean input only
        "plan": "\n".join(f"{i + 1}. {step}" for i, step in enumerate(state["plan"])),
        "past_steps": past_steps_str.strip(),
        "context": full_context,  # Always provide context (may be empty string)
    }

    # Skip emitting replanning context to UI - only show planning contexts
    # This reduces noise since replanning contexts are often empty or not meaningful
    # The planning context will persist in the UI until a new plan is created

    replanner = globals().get("replanner")
    if not replanner:
        raise RuntimeError("Replanner not initialized")

    output = asyncio.run(replanner.ainvoke(template_vars))

    # Log critical decision point
    logger.info(
        "replan_decision",
        operation="replan_step",
        thread_id=thread_id,
        decision_type="Response" if isinstance(output.action, Response) else "Plan",
        will_end_workflow=isinstance(output.action, Response),
        completed_vs_total=f"{len(current_plan_steps)}/{len(state.get('plan', []))}",
    )

    if isinstance(output.action, Response):
        # CRITICAL: Task is completing - trigger memory decay for task-specific context
        try:
            # Extract task-related tags from the original input and plan
            input_text = state.get("input", "")
            input_words = set(input_text.lower().split()) if input_text else set()
            plan_words = set()
            for step in state["plan"]:
                if step is not None:  # Guard against None steps
                    plan_words.update(step.lower().split())

            task_tags = input_words.union(plan_words)
            # Clean up tags
            stop_words = {
                "the",
                "a",
                "an",
                "and",
                "or",
                "but",
                "in",
                "on",
                "at",
                "to",
                "for",
                "of",
                "with",
                "by",
                "step",
            }
            task_tags = {
                tag for tag in task_tags if len(tag) > 2 and tag not in stop_words
            }

            # TODO: Implement task completion decay in new memory API
            # The old API had mark_task_completed() which would decay relevance
            # of nodes related to completed tasks. The new API handles decay
            # automatically based on time, but we could enhance it with task-based decay.

            logger.info(
                "task_completion_detected",
                component="orchestrator",
                operation="replan_step",
                thread_id=thread_id,
                task_tags=list(task_tags),
            )

        except Exception as e:
            logger.error(
                "failed_to_mark_task_completed",
                component="orchestrator",
                operation="replan_step",
                error=str(e),
            )

        # Add AI response to conversation history when task completes
        ai_response = AIMessage(content=output.action.response)

        # Trim the overall conversation state to prevent bloat
        current_messages = state.get("messages", [])
        from src.utils.agents.message_processing.helpers import (
            trim_messages_for_context,
        )

        # Add the new AI response
        updated_messages = current_messages + [ai_response]

        # Trim if conversation is getting too long
        if len(updated_messages) > 50:  # Trim when conversation exceeds 50 messages
            updated_messages = trim_messages_for_context(
                updated_messages,
                max_tokens=80000,  # Keep substantial conversation history
                keep_last_n=30,  # Preserve recent conversation flow
            )

            logger.info(
                "trimmed_conversation_state",
                component="orchestrator",
                operation="replan_step",
                original_count=len(current_messages) + 1,
                trimmed_count=len(updated_messages),
            )

        state_updates = {
            "response": output.action.response,
            "messages": [ai_response]
            if len(updated_messages) <= 50
            else updated_messages,
        }

        # Clear interrupt flags if they were set
        if is_user_replan:
            state_updates["user_interrupted"] = False
            state_updates["interrupt_reason"] = None
            state_updates["should_force_replan"] = False

        return state_updates
    else:
        # Check if the new plan includes human_input - if so, show the most recent result to user
        new_plan = output.action.steps

        # Log if we have None values in the plan
        if any(step is None for step in new_plan):
            logger.warning(
                "plan_contains_none_steps",
                component="orchestrator",
                operation="replan_step",
                plan=new_plan,
                none_indices=[i for i, step in enumerate(new_plan) if step is None],
            )

        user_visible_responses = []

        # Don't automatically show past results when adding human_input steps
        # The human_input tool itself will handle showing the appropriate data

        state_updates = {
            "plan": new_plan,
            "user_visible_responses": user_visible_responses,
        }

        # Clear interrupt flags if they were set
        if is_user_replan:
            state_updates["user_interrupted"] = False
            state_updates["interrupt_reason"] = None
            state_updates["should_force_replan"] = False

        return state_updates


@log_execution("orchestrator", "should_end", include_args=True, include_result=True)
def should_end(state: PlanExecute):
    # End if replanner decided to provide final response
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
    globals()["agent_executor"] = agent_executor
    globals()["planner"] = planner
    globals()["replanner"] = replanner

    # Import sync wrappers for LangGraph compatibility
    from src.orchestrator.workflow_sync_wrappers import (
        plan_step as sync_plan_step,
        execute_step as sync_execute_step,
        replan_step as sync_replan_step,
    )

    workflow = StateGraph(PlanExecute)

    # Add the plan node - use sync wrapper
    workflow.add_node("planner", sync_plan_step)

    # Add the execution step - use sync wrapper
    workflow.add_node("agent", sync_execute_step)

    # Add a replan node - use sync wrapper
    workflow.add_node("replan", sync_replan_step)

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
    # Use MemorySaver for in-memory checkpointing
    # Configure to allow interrupts to bubble up from nested tool calls
    app = workflow.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["agent"],  # Allow interrupts before agent execution
        interrupt_after=[]  # Don't interrupt after nodes
    )
    return app


# ================================
# Factory function for easy setup
# ================================

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
    if (
        current_time - _last_summary_time >= time_threshold
        and message_count > _last_summary_message_count
    ):
        return True

    return False


def update_background_summary_tracking(message_count: int):
    """Update background summary tracking."""
    global _last_summary_time, _last_summary_message_count
    _last_summary_time = time.time()
    _last_summary_message_count = message_count


async def trigger_background_summary_if_needed(
    messages: list, llm, user_id: str = "default_user"
):
    """Simple background summarization trigger for ReAct agent."""
    if not should_trigger_background_summary(len(messages)):
        return

    logger.info(
        "triggering_background_summary",
        component="orchestrator",
        message_count=len(messages),
    )

    # Update tracking
    update_background_summary_tracking(len(messages))

    try:
        # Get thread_id from the first message's additional_kwargs if available
        thread_id = "default-thread"
        if messages and hasattr(messages[0], "additional_kwargs"):
            thread_id = messages[0].additional_kwargs.get("thread_id", "default-thread")

        # Get existing summary for context
        existing_summary = None
        from src.utils.storage import get_global_sqlite_store

        global_sqlite_store = get_global_sqlite_store()
        if global_sqlite_store:
            # Use user_id passed to the function
            namespace = ("memory", user_id)
            key = "conversation_summary"
            existing_data = global_sqlite_store.get(namespace, key)
            if existing_data:
                existing_summary = existing_data.get("summary")

        # Use the conversation summary prompt from our framework
        from src.utils.prompt_templates import CONVERSATION_SUMMARY_PROMPT
        from langchain_core.messages import HumanMessage

        # Format recent messages as text (matching old_main approach)
        # Take last 10 messages for the prompt
        recent_messages = messages[-10:] if len(messages) > 10 else messages
        formatted_messages = []
        for msg in recent_messages:
            role = "User" if msg.type == "human" else "Assistant"
            content = str(msg.content)[:500]  # Truncate long messages
            formatted_messages.append(f"{role}: {content}")

        recent_conversation_text = "\n".join(formatted_messages)

        # Create the summary prompt with formatted conversation text
        summary_prompt = CONVERSATION_SUMMARY_PROMPT.format(
            previous_summary=existing_summary if existing_summary else "None",
            recent_conversation=recent_conversation_text,
        )

        # Generate summary using LLM with ONLY the summary prompt (matching old_main)
        # This is more token-efficient than sending all messages
        summary_response = await llm.ainvoke([HumanMessage(content=summary_prompt)])
        summary_text = (
            summary_response.content
            if hasattr(summary_response, "content")
            else str(summary_response)
        )

        # Store summary in SQLite for persistence across threads
        from src.utils.storage import get_global_sqlite_store

        global_sqlite_store = get_global_sqlite_store()
        if global_sqlite_store:
            # Use user_id passed to the function
            namespace = ("memory", user_id)
            key = "conversation_summary"

            # Get existing summary to potentially merge
            existing_summary = global_sqlite_store.get(namespace, key)

            # Store the new summary with metadata
            summary_data = {
                "summary": summary_text,
                "message_count": len(messages),
                "timestamp": time.time(),
                "previous_summary": existing_summary.get("summary")
                if existing_summary
                else None,
            }

            global_sqlite_store.put(namespace, key, summary_data)

            logger.info(
                "conversation_summary_stored",
                component="orchestrator",
                thread_id=thread_id,
                summary_length=len(summary_text),
                message_count=len(messages),
            )
        else:
            logger.warning(
                "no_sqlite_store_for_summary",
                component="orchestrator",
                note="Summary generated but not stored",
            )

    except Exception as e:
        logger.error(
            "background_summary_error",
            component="orchestrator",
            error=str(e),
            error_type=type(e).__name__,
        )


async def create_plan_execute_graph():
    """Create a simple plan-execute graph for A2A usage."""
    from src.orchestrator.core.llm_handler import get_orchestrator_system_message
    from src.orchestrator.core.agent_registry import AgentRegistry
    from src.orchestrator.tools.agent_caller_tools import (
        SalesforceAgentTool,
        JiraAgentTool,
        ServiceNowAgentTool,
        AgentRegistryTool,
    )
    from src.orchestrator.tools.web_search import WebSearchTool
    from src.orchestrator.tools.human_input import HumanInputTool
    from langgraph.prebuilt import create_react_agent
    from src.orchestrator.core.state import OrchestratorState
    from src.utils.cost_tracking_decorator import create_cost_tracking_azure_openai
    import os

    # Create agent registry and LLM instances
    agent_registry = AgentRegistry()

    # Initialize the UX observer for tracking user-visible data
    from src.orchestrator.observers import get_observer_registry, UXObserver

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
        HumanInputTool(),
    ]

    # Create LLM for the ReAct agent with cost tracking (decorator pattern)
    llm = create_cost_tracking_azure_openai(
        component="orchestrator",
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=os.environ.get(
            "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4o-mini"
        ),
        openai_api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01"),
        openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
        temperature=0.1,
        max_tokens=4000,
    )

    # Get orchestrator system message for the ReAct agent
    mock_state = {"summary": "", "memory": "", "active_agents": []}
    orchestrator_prompt = get_orchestrator_system_message(mock_state, agent_registry)

    # Create ReAct agent executor with our orchestrator prompt
    # Tools will access state via InjectedState annotation
    # Use OrchestratorState as the state schema to ensure proper state handling
    agent_executor = create_react_agent(
        llm, tools, prompt=orchestrator_prompt, state_schema=OrchestratorState
    )

    # Use the canonical setup with proper prompts and agent context
    return setup_canonical_plan_execute(agent_executor, llm, agent_registry)


def setup_canonical_plan_execute(llm_with_tools, llm_for_planning, agent_registry=None):
    """Set up the canonical plan-and-execute graph with LLMs and tool context."""

    # Get agent context from orchestrator system message generation (reuse existing logic)
    agent_context = ""
    if agent_registry:
        from src.orchestrator.core.llm_handler import get_orchestrator_system_message

        # Create mock state to get agent context from orchestrator
        mock_state = {"summary": "", "memory": "", "active_agents": []}
        full_system_msg = get_orchestrator_system_message(mock_state, agent_registry)

        # Extract only agent tools for planning (exclude management tools)
        if "ORCHESTRATOR TOOLS:" in full_system_msg:
            tools_section = full_system_msg.split("ORCHESTRATOR TOOLS:")[1].split(
                "\n\n"
            )[0]

            # Filter out management tools, keep only agent tools
            agent_tools = []
            for line in tools_section.split("\n"):
                if line.strip() and not any(
                    mgmt_tool in line.lower()
                    for mgmt_tool in ["manage_agents", "agent_registry", "health_check"]
                ):
                    agent_tools.append(line)

            if agent_tools:
                agent_context = "=== AVAILABLE AGENT TOOLS ===\n" + "\n".join(
                    agent_tools
                )

    # Import centralized prompt functions
    from src.utils.prompt_templates import (
        create_planner_prompt,
        create_replanner_prompt,
    )

    # Create prompts with dynamic agent context
    planner_prompt = create_planner_prompt(agent_context)
    replanner_prompt = create_replanner_prompt()

    # Create planner and replanner with structured output and agent context
    planner = planner_prompt | llm_for_planning.with_structured_output(Plan)
    replanner = replanner_prompt | llm_for_planning.with_structured_output(Act)

    # Agent executor is the LLM with tools
    agent_executor = llm_with_tools

    # Create and return the graph
    return create_graph(agent_executor, planner, replanner)


# Global instance for reuse
_plan_execute_graph = None


def get_plan_execute_graph():
    """Get the singleton plan-execute graph instance."""
    global _plan_execute_graph
    if _plan_execute_graph is None:
        _plan_execute_graph = asyncio.run(create_plan_execute_graph())
    return _plan_execute_graph
