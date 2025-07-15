"""Conversation handling logic for the orchestrator."""

import asyncio
# Remove unused import
from datetime import datetime

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig

from src.utils.config import (
    get_conversation_config, get_database_config,
    MEMORY_NAMESPACE_PREFIX, SIMPLE_MEMORY_KEY,
    SUMMARY_KEY, NO_SUMMARY_TEXT,
    SUMMARY_USER_MESSAGE_THRESHOLD, SUMMARY_TIME_THRESHOLD_SECONDS,
    MEMORY_TOOL_CALL_THRESHOLD, MEMORY_AGENT_CALL_THRESHOLD
)
from src.utils.logging import get_logger
from src.utils.storage import get_async_store_adapter
from src.utils.storage.memory_schemas import SimpleMemory
from .state import OrchestratorState, should_trigger_summary, should_trigger_memory_update
from .llm_handler import get_orchestrator_system_message
from .background_tasks import (
    _run_background_summary_async,
    _run_background_memory_async
)

logger = get_logger()



async def orchestrator(
    state: OrchestratorState, 
    config: RunnableConfig,
    memory_store,
    agent_registry,
    invoke_llm,
    summarize_func,
    memorize_func,
    trustcall_extractor
):
    """Main conversation handler node."""
    try:
        msg_count = len(state.get('messages', []))
        last_msg = state.get('messages', [])[-1] if state.get('messages') else None
        
        logger.info("orchestrator_state_entry",
            component="orchestrator",
            operation="conversation_processing",
            message_count=msg_count,
            has_summary=bool(state.get('summary')),
            has_memory=bool(state.get('memory')),
            thread_id=config.get("configurable", {}).get("thread_id", "default")
        )
        
        # Log message types
        if hasattr(last_msg, 'content'):
            if isinstance(last_msg, HumanMessage):
                logger.info("user_request", component="orchestrator", 
                    user_message=str(last_msg.content)[:200],
                    message_count=msg_count)
            elif isinstance(last_msg, AIMessage):
                logger.info("ai_response_processing", component="orchestrator", 
                    ai_message=str(last_msg.content)[:200],
                    message_count=msg_count)
                    
        # Load persistent memory
        user_id = config.get("configurable", {}).get("user_id", "default")
        namespace = (MEMORY_NAMESPACE_PREFIX, user_id)
        key = SIMPLE_MEMORY_KEY
        
        logger.info("memory_load_start",
            component="orchestrator",
            operation="load_memory",
            user_id=user_id,
            namespace=str(namespace),
            key=key
        )
        
        existing_memory_data = memory_store.sync_get(namespace, key)
        
        if existing_memory_data:
            try:
                validated_data = SimpleMemory(**existing_memory_data)
                existing_memory = {SIMPLE_MEMORY_KEY: validated_data.model_dump()}
                logger.info("memory_load_success",
                    component="orchestrator",
                    operation="load_memory",
                    memory_size=len(str(existing_memory))
                )
            except Exception as e:
                logger.error("memory_validation_error",
                    component="orchestrator",
                    operation="load_memory",
                    error=str(e),
                    error_type=type(e).__name__
                )
                existing_memory = {SIMPLE_MEMORY_KEY: SimpleMemory().model_dump()}
        else:
            existing_memory = {SIMPLE_MEMORY_KEY: SimpleMemory().model_dump()}
        
        state["memory"] = existing_memory
        
        # Load summary from persistent store
        summary = state.get(SUMMARY_KEY, NO_SUMMARY_TEXT)
        if summary == NO_SUMMARY_TEXT:
            conv_config = get_conversation_config()
            user_id = config.get("configurable", {}).get("user_id", conv_config.default_user_id)
            thread_id = config.get("configurable", {}).get("thread_id", conv_config.default_thread_id)
            namespace = (conv_config.memory_namespace_prefix, user_id)
            key = f"summary_{thread_id}"
            
            try:
                stored_summary = memory_store.sync_get(namespace, key)
                if stored_summary and "summary" in stored_summary:
                    state["summary"] = stored_summary["summary"]
                    summary = stored_summary["summary"]
                    logger.info("summary_loaded_from_store", component="orchestrator", summary_preview=summary[:200],
                                            thread_id=thread_id,
                                            timestamp=stored_summary.get("timestamp"))
            except Exception as e:
                logger.info("summary_load_error", component="orchestrator", error=str(e), thread_id=thread_id)
        
        logger.info("summary_state_check", component="orchestrator", operation="conversation_node_entry",
                                has_summary=bool(summary and summary != "No summary available"),
                                summary_length=len(str(summary)) if summary else 0,
                                summary_preview=str(summary)[:200] if summary else "NO_SUMMARY")
        
        # Note: Old workflow interruption logic removed - now handled by plan-and-execute system
        
        system_message = get_orchestrator_system_message(state, agent_registry)
        
        # Get all messages from state
        state_messages = state.get("messages", [])
        
        # Check if we need to trim messages for LLM context window
        conv_config = get_conversation_config()
        if len(state_messages) > conv_config.max_conversation_length:
            logger.info("message_trimming_for_llm",
                component="orchestrator",
                operation="trim_for_llm_context",
                total_messages=len(state_messages),
                max_allowed=conv_config.max_conversation_length,
                thread_id=config.get("configurable", {}).get("thread_id", "default")
            )
            
            # Import trimming utility
            from src.utils.agents.message_processing import trim_messages_for_context
            
            # Trim messages ONLY for LLM call, not in state
            llm_messages = trim_messages_for_context(
                state_messages,
                max_tokens=80000,   # More conservative limit (was 100k)
                keep_system=False,  # System message is added separately
                keep_first_n=2,     # Keep first couple messages for context
                keep_last_n=15,     # Keep recent conversation
                use_smart_trimming=True  # Use LangChain's official trimming
            )
            
            logger.info("message_trimming_complete",
                component="orchestrator",
                operation="trim_for_llm_context",
                trimmed_count=len(llm_messages),
                thread_id=config.get("configurable", {}).get("thread_id", "default")
            )
        else:
            # Use all messages if under limit
            llm_messages = state_messages
        
        # Get latest human message for execution logic
        human_messages = [msg for msg in state.get("messages", []) if isinstance(msg, HumanMessage)]
        if human_messages:
            content = human_messages[-1].content
            # Handle both string and list content types
            if isinstance(content, list):
                latest_input = " ".join(str(item) for item in content if isinstance(item, str))
            else:
                latest_input = str(content) if content else ""
        else:
            latest_input = ""
        
        # Check if we have an existing plan that should be executed
        current_plan = state.get("current_plan")
        execution_mode = state.get("execution_mode")
        
        # Priority 1: Handle existing plan execution
        if current_plan and execution_mode == "executing":
            # First check if user provided new requirements that need replanning
            if await _should_replan(latest_input, state, invoke_llm):
                logger.info("replanning_detected",
                           component="orchestrator",
                           plan_id=current_plan.get("id", "unknown"),
                           user_input=latest_input[:100])
                return await _handle_replanning(latest_input, state, invoke_llm)
            
            # Then check if user wants to execute the current plan
            if await _should_execute_plan(latest_input, current_plan, invoke_llm):  # type: ignore
                logger.info("executing_existing_plan",
                           component="orchestrator",
                           plan_id=current_plan.get("id", "unknown"),
                           user_input=latest_input[:100])
                return await _handle_plan_execution(state, invoke_llm, config)
            
            # Default: continue executing the plan
            logger.info("continuing_plan_execution",
                       component="orchestrator",
                       plan_id=current_plan.get("id", "unknown"))
            return await _handle_plan_execution(state, invoke_llm, config)
        
        # Priority 2: Check if we should create a NEW plan (only if no existing plan)
        if await _should_create_plan(state, invoke_llm):
            return await _handle_plan_creation(state, invoke_llm)
        
        messages = [SystemMessage(content=system_message)] + llm_messages
        
        logger.info("llm_invocation_start",
            component="orchestrator",
            operation="invoke_llm",
            message_count=len(messages),
            system_message_length=len(system_message),
            use_tools=True
        )
        
        response = invoke_llm(messages, use_tools=True)
        
        # Track tool/agent calls for memory triggers
        tool_calls_increment = 0
        agent_calls_increment = 0
        
        if hasattr(response, 'tool_calls') and response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call.get('name', 'unknown')
                logger.info("tool_call", component="orchestrator", 
                    tool_name=tool_name,
                    tool_args=tool_call.get('args', {}))
                
                # Increment counters
                if tool_name.endswith('_agent'):
                    agent_calls_increment += 1
                else:
                    tool_calls_increment += 1
        
        response_content = str(response.content) if hasattr(response, 'content') else ""
        
        # Estimate token usage
        message_chars = sum(len(str(m.content)) if hasattr(m, 'content') else len(str(m)) for m in messages)
        response_chars = len(response_content)
        estimated_tokens = (message_chars + response_chars) // 4
        
        logger.info("llm_generation_complete", component="orchestrator", 
            response_length=len(response_content),
            response_content=response_content[:500],
            has_tool_calls=bool(hasattr(response, 'tool_calls') and response.tool_calls))
        
        logger.track_cost("ORCHESTRATOR_LLM", tokens=estimated_tokens, 
                        message_count=len(messages))
        
        # Preserve all existing state fields and only update specific ones
        updated_state = dict(state)
        updated_state.update({
            "messages": [response],  # LangGraph expects a list of new messages to append
            "memory": existing_memory,
            # Update tool/agent call counters
            "tool_calls_since_memory": state.get("tool_calls_since_memory", 0) + tool_calls_increment,
            "agent_calls_since_memory": state.get("agent_calls_since_memory", 0) + agent_calls_increment
        })
        
        if "summary" not in state or not state.get("summary"):
            updated_state["summary"] = "No summary available"
            logger.info("summary_initialized", component="orchestrator", operation="setting_default_summary")
        
        # Note: Old workflow state management removed - now using plan-and-execute system
        
        # Check for background task triggers
        conv_config = get_conversation_config()
        
        # Calculate total message count (existing + new response)
        total_message_count = len(state.get("messages", [])) + 1  # +1 for the new response
        
        # Check summary trigger using simple logic
        if should_trigger_summary(updated_state, 
                                 user_message_threshold=SUMMARY_USER_MESSAGE_THRESHOLD,
                                 time_threshold_seconds=SUMMARY_TIME_THRESHOLD_SECONDS):
            
            trigger_reason = f"Message count or time threshold reached"
            
            logger.info("summary_trigger", 
                component="orchestrator", 
                operation="summary_triggered",
                total_message_count=total_message_count,
                trigger_reason=trigger_reason)
            
            user_id = config.get("configurable", {}).get("user_id", "default")
            thread_id = config.get("configurable", {}).get("thread_id", "default")
            
            # Update last summary trigger
            updated_state["last_summary_trigger"] = {
                "timestamp": datetime.now().isoformat(),
                "message_count": total_message_count
            }
            
            # Get all messages for background task
            all_messages = state.get("messages", []) + [response]
            asyncio.create_task(
                _run_background_summary_async(
                    all_messages, 
                    updated_state.get("summary", ""), 
                    existing_memory, 
                    user_id, 
                    thread_id,
                    summarize_func,
                    invoke_llm
                )
            )
        
        # Check memory trigger
        if should_trigger_memory_update(updated_state,
                                      tool_call_threshold=MEMORY_TOOL_CALL_THRESHOLD,
                                      agent_call_threshold=MEMORY_AGENT_CALL_THRESHOLD):
            
            logger.info("memory_trigger", component="orchestrator", 
                message_count=total_message_count,  # Use the calculated total
                tool_calls=updated_state.get("tool_calls_since_memory", 0),
                agent_calls=updated_state.get("agent_calls_since_memory", 0))
            
            user_id = config.get("configurable", {}).get("user_id", "default")
            
            # Update last memory trigger and reset counters
            updated_state["last_memory_trigger"] = {
                "timestamp": datetime.now().isoformat(),
                "message_count": total_message_count
            }
            updated_state["tool_calls_since_memory"] = 0
            updated_state["agent_calls_since_memory"] = 0
            
            # Create new store instance for async context
            async_memory_store = get_async_store_adapter(
                db_path=get_database_config().path
            )
            
            # Get all messages for background task
            all_messages = state.get("messages", []) + [response]
            asyncio.create_task(
                _run_background_memory_async(
                    all_messages, 
                    updated_state.get("summary", ""), 
                    existing_memory,
                    user_id,
                    memorize_func,
                    async_memory_store,
                    trustcall_extractor
                )
            )
        
        return updated_state
        
    except Exception as e:
        logger.error("request_processing_error",
            component="orchestrator",
            operation="process_request",
            error=str(e),
            error_type=type(e).__name__
        )
        raise


async def _should_create_plan(state: OrchestratorState, invoke_llm) -> bool:
    """Check if we should create a plan for the current request."""
    
    # CRITICAL: If we already have a plan, don't create a new one!
    # Check if we're in execution mode or have an existing plan
    if state.get("execution_mode") == "executing" or state.get("current_plan"):
        logger.info("plan_already_exists",
                   component="orchestrator",
                   execution_mode=state.get("execution_mode"),
                   has_plan=bool(state.get("current_plan")),
                   decision="SKIP_PLANNING")
        return False
    
    # Get latest human message
    human_messages = [msg for msg in state.get("messages", []) if isinstance(msg, HumanMessage)]
    if not human_messages:
        return False
    
    content = human_messages[-1].content
    # Handle both string and list content types
    if isinstance(content, list):
        latest_instruction = " ".join(str(item) for item in content if isinstance(item, str))
    else:
        latest_instruction = str(content) if content else ""
    
    
    # LLM-based routing decision - be very explicit with examples
    routing_prompt = f"""You are determining if a user request needs structured execution planning or normal conversation.

USER REQUEST: "{latest_instruction}"

Look at this request carefully:

DEFINITELY NORMAL (respond immediately, no planning):
- "hello" / "hi" / "hey" / "thanks" 
- "what" / "why" / "how" / "when"
- "proceed" / "start" / "continue" / "yes" / "no"
- Simple single queries like "get account X" or "find Y"
- Status checks and basic questions

DEFINITELY PLAN (create structured todo list):
- Customer onboarding workflows ("onboard X customer")
- Multi-step business processes that span systems
- Complex analysis or reporting tasks
- Project-like work with dependencies

Answer with exactly one word: NORMAL or PLAN"""
    
    try:
        messages = [
            SystemMessage(content=routing_prompt),
            HumanMessage(content="Classify this request")
        ]
        
        response = invoke_llm(messages, use_tools=False)
        decision = response.content.strip().upper()
        
        logger.info("planning_routing_decision",
                   component="orchestrator",
                   decision=decision,
                   instruction_preview=latest_instruction[:100])
        
        return decision == "PLAN"
        
    except Exception as e:
        logger.error("planning_routing_error",
                    component="orchestrator",
                    error=str(e),
                    defaulting_to=False)
        return False


async def _should_execute_plan(user_input: str, current_plan: dict, invoke_llm) -> bool:
    """Check if user input indicates they want to execute the existing plan."""
    
    # Simple LLM-based decision with safe terminology
    execution_prompt = f"""User said: "{user_input}"
    
Question: Does this mean run the plan?
Answer: RUN or WAIT"""
    
    try:
        messages = [
            SystemMessage(content=execution_prompt),
            HumanMessage(content="Make execution decision")
        ]
        
        response = invoke_llm(messages, use_tools=False)
        decision = response.content.strip().upper()
        
        logger.info("plan_start_decision",
                   component="orchestrator",
                   decision=decision,
                   user_input=user_input[:100])
        
        return decision == "RUN"
        
    except Exception as e:
        logger.error("execution_decision_error",
                    component="orchestrator",
                    error=str(e))
        return False


async def _route_task_to_agent(task_content: str, invoke_llm):
    """Use LLM intelligence to route tasks to the correct agent based on intent and capabilities."""
    
    routing_prompt = f"""You are a task router for a multi-agent system. Analyze this task and determine which specialized agent should handle it.

TASK: "{task_content}"

AVAILABLE AGENTS AND THEIR CAPABILITIES:

**SALESFORCE AGENT** - Handles:
- CRM operations (accounts, contacts, leads, opportunities) 
- Sales pipeline management
- Customer relationship data
- Salesforce-specific operations
- Cases and tasks in Salesforce CRM

**JIRA AGENT** - Handles:
- Project management and tracking
- Issue creation and management  
- Task management for development/work
- Sprint and epic management
- Project planning and organization

**SERVICENOW AGENT** - Handles:
- IT Service Management (ITSM)
- Incident and problem management
- Company/organization records in ServiceNow
- Change management processes
- CMDB and configuration items
- Service requests and workflows

ROUTING RULES:
- If task mentions creating a "company" → ServiceNow (companies are managed in ServiceNow CMDB)
- If task mentions Salesforce "accounts" → Salesforce (CRM customer records)
- If task mentions "projects" or development tasks → Jira
- If task mentions "incidents" or IT services → ServiceNow
- If task explicitly names a system → Route to that system

Respond with exactly one word: SALESFORCE, JIRA, or SERVICENOW"""

    try:
        messages = [
            SystemMessage(content=routing_prompt),
            HumanMessage(content="Route this task")
        ]
        
        response = invoke_llm(messages, use_tools=False)
        routing_decision = response.content.strip().upper()
        
        # Import agent tools here to avoid circular imports
        from .agent_caller_tools import SalesforceAgentTool, JiraAgentTool, ServiceNowAgentTool
        from .agent_registry import get_agent_registry
        
        agent_registry = get_agent_registry()
        
        if routing_decision == "SALESFORCE":
            logger.info("task_execution_routing", component="orchestrator", 
                       task=task_content[:100], routed_to="salesforce_agent", 
                       routing_method="llm_intelligent")
            return SalesforceAgentTool(agent_registry)
        elif routing_decision == "JIRA":
            logger.info("task_execution_routing", component="orchestrator",
                       task=task_content[:100], routed_to="jira_agent",
                       routing_method="llm_intelligent")
            return JiraAgentTool(agent_registry)
        elif routing_decision == "SERVICENOW":
            logger.info("task_execution_routing", component="orchestrator",
                       task=task_content[:100], routed_to="servicenow_agent",
                       routing_method="llm_intelligent")
            return ServiceNowAgentTool(agent_registry)
        else:
            logger.warning("task_routing_fallback", component="orchestrator",
                          task=task_content[:100], decision=routing_decision,
                          fallback_to="salesforce_agent")
            return SalesforceAgentTool(agent_registry)  # Fallback
            
    except Exception as e:
        logger.error("task_routing_error", component="orchestrator",
                    task=task_content[:100], error=str(e),
                    fallback_to="salesforce_agent")
        # Fallback to Salesforce if routing fails
        from .agent_caller_tools import SalesforceAgentTool
        from .agent_registry import get_agent_registry
        return SalesforceAgentTool(get_agent_registry())


async def _should_replan(user_input: str, state: OrchestratorState, invoke_llm) -> bool:
    """Check if user input requires replanning."""
    
    current_plan = state.get("current_plan")
    if not current_plan:
        return False
    
    # Simple LLM-based decision
    replan_prompt = f"""You are analyzing if a user input during plan execution requires modifying the plan.

CURRENT PLAN: {current_plan.get('original_instruction', 'N/A')}
USER INPUT: {user_input}

USER INPUT REQUIRES REPLANNING if it:
- Adds new requirements or tasks
- Changes priorities or scope
- Modifies the approach
- Requests different actions

USER INPUT DOES NOT require replanning if it:
- Asks for status or progress
- Makes general comments
- Asks clarifying questions
- Says "continue" or "proceed"

Respond with only: "REPLAN" or "CONTINUE"
"""
    
    try:
        messages = [
            SystemMessage(content=replan_prompt),
            HumanMessage(content="Make replanning decision")
        ]
        
        response = invoke_llm(messages, use_tools=False)
        decision = response.content.strip().upper()
        
        logger.info("replanning_decision",
                   component="orchestrator",
                   decision=decision,
                   user_input=user_input[:100])
        
        return decision == "REPLAN"
        
    except Exception as e:
        logger.error("replanning_decision_error",
                    component="orchestrator",
                    error=str(e))
        return False


async def _handle_plan_creation(state: OrchestratorState, invoke_llm) -> OrchestratorState:
    """Handle creation of a new execution plan."""
    
    # Import here to avoid circular imports
    from .plan_and_execute import PlanAndExecuteManager
    
    # Get latest human message
    human_messages = [msg for msg in state.get("messages", []) if isinstance(msg, HumanMessage)]
    if not human_messages:
        return state
    
    content = human_messages[-1].content
    # Handle both string and list content types
    if isinstance(content, list):
        latest_instruction = " ".join(str(item) for item in content if isinstance(item, str))
    else:
        latest_instruction = str(content) if content else ""
    
    try:
        # Create a simple wrapper for invoke_llm to match LLM interface
        class LLMWrapper:
            def __init__(self, invoke_func):
                self.invoke_func = invoke_func
            
            async def ainvoke(self, messages, **_kwargs):
                return self.invoke_func(messages, use_tools=False)
        
        # Create plan manager with wrapped LLM
        plan_manager = PlanAndExecuteManager(LLMWrapper(invoke_llm))
        
        # Build context with recent conversation history for context preservation
        recent_messages = state.get("messages", [])[-10:]  # Include recent context
        context = {
            "messages": recent_messages,
            "memory": state.get("memory", {}),
            "summary": state.get("summary", ""),
            "active_agents": state.get("active_agents", []),
            "conversation_context": f"Recent conversation about: {latest_instruction}"
        }
        
        # Create execution plan
        execution_plan = await plan_manager.create_plan(latest_instruction, context)
        
        # Create plan summary with todo list
        todo_list = _format_todo_list(execution_plan["tasks"])
        
        plan_summary = f"""I've created an execution plan for your request:

**Original Request:** {latest_instruction}

**Proposed Todo List:**
{todo_list}

**Next Steps:**
- Say "proceed" or "start" to begin execution
- Say "modify" to request changes to the plan  
- Ask me to "add", "remove", or "change" specific tasks
- Or just tell me what you'd like different

What would you like to do?"""
        
        logger.info("plan_created",
                   component="orchestrator",
                   plan_id=execution_plan["id"],
                   task_count=len(execution_plan["tasks"]))
        
        # Update state
        updated_state = dict(state)
        updated_state.update({
            "messages": [AIMessage(content=plan_summary)],
            "current_plan": execution_plan,
            "execution_mode": "executing"
        })
        
        return updated_state  # type: ignore
        
    except Exception as e:
        logger.error("plan_creation_error",
                    component="orchestrator",
                    error=str(e))
        
        # Fall back to normal processing
        error_message = f"I had trouble creating the plan: {str(e)}. I'll handle your request normally."
        
        updated_state = dict(state)
        updated_state.update({
            "messages": [AIMessage(content=error_message)],
            "execution_mode": "normal"
        })
        
        return updated_state  # type: ignore


async def _handle_replanning(user_input: str, state: OrchestratorState, invoke_llm) -> OrchestratorState:
    """Handle replanning based on user input."""
    
    # Import here to avoid circular imports
    from .plan_and_execute import PlanAndExecuteManager
    
    current_plan = state.get("current_plan")
    if not current_plan:
        return state
    
    try:
        # Create a simple wrapper for invoke_llm to match LLM interface
        class LLMWrapper:
            def __init__(self, invoke_func):
                self.invoke_func = invoke_func
            
            async def ainvoke(self, messages, **_kwargs):
                return self.invoke_func(messages, use_tools=False)
        
        # Create plan manager with wrapped LLM
        plan_manager = PlanAndExecuteManager(LLMWrapper(invoke_llm))
        
        # Build context
        context = {
            "messages": state.get("messages", []),
            "memory": state.get("memory", {}),
            "summary": state.get("summary", ""),
            "active_agents": state.get("active_agents", [])
        }
        
        # Update the plan
        updated_plan = await plan_manager.replan(current_plan, user_input, context)
        
        # Create replan summary with updated todo list
        pending_tasks = [task for task in updated_plan["tasks"] if task["status"] == "pending"]
        completed_tasks = [task for task in updated_plan["tasks"] if task["status"] == "completed"]
        
        todo_list = _format_todo_list(pending_tasks, show_status=False)
        
        replan_summary = f"""I've updated the plan based on your request:

**Your Request:** {user_input}

**Updated Todo List:**
{todo_list}

**Progress:** {len(completed_tasks)} completed, {len(pending_tasks)} remaining

Continuing with the updated plan..."""
        
        logger.info("plan_updated",
                   component="orchestrator",
                   plan_id=updated_plan["id"],
                   modification=user_input[:100])
        
        # Update state
        updated_state = dict(state)
        updated_state.update({
            "messages": [AIMessage(content=replan_summary)],
            "current_plan": updated_plan,
            "execution_mode": "executing"
        })
        
        return updated_state  # type: ignore
        
    except Exception as e:
        logger.error("replanning_error",
                    component="orchestrator",
                    error=str(e))
        
        # Continue with current plan
        error_message = f"I had trouble updating the plan: {str(e)}. Continuing with the current plan."
        
        updated_state = dict(state)
        updated_state.update({
            "messages": [AIMessage(content=error_message)],
            "execution_mode": "executing"
        })
        
        return updated_state  # type: ignore


async def _handle_plan_execution(state: OrchestratorState, invoke_llm, config=None) -> OrchestratorState:
    """Handle execution of the current plan."""
    
    # Import here to avoid circular imports
    from .plan_and_execute import PlanAndExecuteManager
    
    current_plan = state.get("current_plan")
    if not current_plan:
        logger.error("plan_execution_no_plan", component="orchestrator")
        return dict(state, execution_mode="normal")  # type: ignore
    
    # Get progress tracking functions from module-level global state
    from .progress_state import get_progress_functions
    update_progressive_step, complete_current_step = get_progress_functions()
    
    if update_progressive_step and complete_current_step:
        logger.info("found_progress_functions_from_global_state", 
                   component="orchestrator",
                   has_both_functions=True)
    else:
        logger.warning("no_progress_functions_available", 
                      component="orchestrator",
                      update_func_available=bool(update_progressive_step),
                      complete_func_available=bool(complete_current_step))
        
        # For A2A mode, create enhanced progress tracking functions
        def a2a_update_progressive_step(step_text, completed_steps=None, failed_steps=None):
            logger.info("a2a_progressive_step_called", 
                       component="orchestrator",
                       step_text=step_text,
                       completed_count=len(completed_steps) if completed_steps else 0,
                       failed_count=len(failed_steps) if failed_steps else 0)
            
            # Store step progress in state for potential streaming/response inclusion
            if config and "configurable" in config:
                config["configurable"]["current_step"] = step_text
                config["configurable"]["completed_steps"] = completed_steps or []
                config["configurable"]["failed_steps"] = failed_steps or []
                
                # Also update A2A handler progress if available
                thread_id = config.get("configurable", {}).get("thread_id")
                handler = config.get("configurable", {}).get("_a2a_handler")
                if thread_id and handler:
                    handler.update_progress(thread_id, {
                        "current_step": step_text,
                        "completed_steps": completed_steps or [],
                        "total_steps": current_plan.get("tasks", []) if current_plan else [],
                        "progress_percent": int((len(completed_steps or []) / len(current_plan.get("tasks", [1]))) * 100) if current_plan else 0
                    })
        
        def a2a_complete_current_step(success=True):
            logger.info("a2a_complete_step_called", component="orchestrator", success=success)
            
            # Mark step as completed or failed in config
            if config and "configurable" in config:
                current_step = config["configurable"].get("current_step")
                if current_step:
                    completed_steps = config["configurable"].get("completed_steps", [])
                    failed_steps = config["configurable"].get("failed_steps", [])
                    
                    if success:
                        completed_steps.append(current_step)
                        config["configurable"]["completed_steps"] = completed_steps
                    else:
                        failed_steps.append(current_step)
                        config["configurable"]["failed_steps"] = failed_steps
                    
                    config["configurable"]["current_step"] = None
                    
                    # Also update A2A handler progress if available
                    thread_id = config.get("configurable", {}).get("thread_id")
                    handler = config.get("configurable", {}).get("_a2a_handler")
                    if thread_id and handler:
                        total_steps = len(current_plan.get("tasks", [])) if current_plan else 1
                        total_completed = len(completed_steps) + len(failed_steps)
                        handler.update_progress(thread_id, {
                            "current_step": None,
                            "completed_steps": completed_steps,
                            "failed_steps": failed_steps,
                            "total_steps": current_plan.get("tasks", []) if current_plan else [],
                            "progress_percent": int((total_completed / total_steps) * 100) if total_steps > 0 else 0
                        })
        
        update_progressive_step = a2a_update_progressive_step
        complete_current_step = a2a_complete_current_step
    
    try:
        # Create a simple wrapper for invoke_llm to match LLM interface
        class LLMWrapper:
            def __init__(self, invoke_func):
                self.invoke_func = invoke_func
            
            async def ainvoke(self, messages, **_kwargs):
                return self.invoke_func(messages, use_tools=False)
        
        # Create plan manager with wrapped LLM
        plan_manager = PlanAndExecuteManager(LLMWrapper(invoke_llm))
        
        # Get next task
        next_task = plan_manager.get_next_task(current_plan)
        
        if not next_task:
            # Plan is complete
            return await _handle_plan_completion(current_plan, state)  # type: ignore
        
        # Update UI with current step
        if update_progressive_step:
            # Get all tasks and their status for progress tracking
            total_tasks = len(current_plan["tasks"])
            completed_tasks = sum(1 for t in current_plan["tasks"] if t["status"] in ["completed", "failed"])
            completed_steps = [t["content"] for t in current_plan["tasks"] if t["status"] == "completed"]
            failed_steps = [t["content"] for t in current_plan["tasks"] if t["status"] == "failed"]
            
            current_step_text = f"Step {completed_tasks + 1}/{total_tasks}: {next_task['content']}"
            logger.info("updating_progressive_step", 
                       component="orchestrator",
                       step_text=current_step_text,
                       completed_count=len(completed_steps),
                       failed_count=len(failed_steps),
                       total_count=total_tasks)
            update_progressive_step(current_step_text, completed_steps, failed_steps)
        else:
            logger.warning("no_progressive_step_function", 
                          component="orchestrator",
                          config_available=bool(config),
                          configurable_available=bool(config and "configurable" in config) if config else False)
        
        # Mark task as in progress
        plan_manager.mark_task_in_progress(current_plan, next_task["id"])
        
        # Execute the task using existing tools
        task_result_data = await _execute_task_with_existing_tools(next_task, state, invoke_llm)  # type: ignore
        
        # Determine success/failure from Command object structure
        task_success = True
        task_result = str(task_result_data)
        
        # Check if this is an error Command by examining message content for error patterns
        if hasattr(task_result_data, 'update') and task_result_data.update:
            messages = task_result_data.update.get('messages', [])
            logger.info("task_success_debug",
                component="orchestrator",
                has_messages=bool(messages),
                message_count=len(messages) if messages else 0,
                first_message_type=type(messages[0]).__name__ if messages else "none",
                first_message_content=messages[0].content[:100] if messages and hasattr(messages[0], 'content') else "no_content"
            )
            if messages:
                first_message = messages[0]
                if hasattr(first_message, 'content') and first_message.content.startswith('Error:'):
                    task_success = False
                    logger.info("task_failure_detected",
                        component="orchestrator",
                        error_content=first_message.content[:200]
                    )
        
        # Mark task status based on execution result
        if task_success:
            plan_manager.mark_task_completed(current_plan, next_task["id"], {"result": task_result})
            status_emoji = "✓"
        else:
            plan_manager.mark_task_failed(current_plan, next_task["id"], task_result)
            status_emoji = "✗"
        
        # Complete the current step in UI with success/failure status
        if complete_current_step:
            complete_current_step(task_success)
        
        # Get progress for internal logging
        total_tasks = len(current_plan["tasks"])
        completed_tasks = sum(1 for t in current_plan["tasks"] if t["status"] in ["completed", "failed"])
        
        # Log progress internally (don't show to user during execution)
        logger.info("task_execution_complete",
                   component="orchestrator",
                   plan_id=current_plan.get("id", "unknown"),
                   task_id=next_task["id"],
                   task_content=next_task['content'][:100],
                   status=status_emoji,
                   progress=f"{completed_tasks}/{total_tasks}",
                   progress_percent=f"{(completed_tasks/total_tasks)*100:.0f}%",
                   task_result_preview=task_result[:200])
        
        # Check if plan is complete
        if plan_manager.is_plan_complete(current_plan):
            # Plan complete - show final summary
            completion_message = await _create_plan_completion_message(current_plan)  # type: ignore
            
            updated_state = dict(state)
            updated_state.update({
                "messages": [completion_message],
                "current_plan": current_plan,
                "execution_mode": "normal"
            })
            return updated_state  # type: ignore
        else:
            # Plan not complete - continue automatically with next task
            # Update state internally but don't show progress message
            updated_state = dict(state)
            updated_state.update({
                "current_plan": current_plan,
                "execution_mode": "executing"
            })
            
            # Recursively continue execution without user input
            return await _handle_plan_execution(updated_state, invoke_llm, config)  # type: ignore
        
    except Exception as e:
        logger.error("plan_execution_error",
                    component="orchestrator",
                    error=str(e))
        
        # Determine if this error requires user intervention
        error_str = str(e).lower()
        critical_errors = ["authentication", "permission", "network", "timeout", "connection"]
        
        if any(critical_error in error_str for critical_error in critical_errors):
            # Critical error - pause and ask for user input
            error_message = f"✗ **Critical Error**: {str(e)}\n\nThis error requires attention. Please resolve the issue and say 'continue' to proceed with the plan."
            
            updated_state = dict(state)
            updated_state.update({
                "messages": [AIMessage(content=error_message)],
                "execution_mode": "executing"  # This will pause for user input
            })
            return updated_state  # type: ignore
        else:
            # Non-critical error - log and continue automatically
            logger.warning("non_critical_error_auto_continuing",
                          component="orchestrator",
                          plan_id=current_plan.get("id", "unknown"),
                          error=str(e))
            
            # Mark current task as failed and continue with next task
            # Variables may not be defined if error occurs early
            next_task = locals().get('next_task')
            plan_manager = locals().get('plan_manager')
            if next_task and plan_manager:
                try:
                    plan_manager.mark_task_failed(current_plan, next_task["id"], f"Error: {str(e)}")
                except Exception:
                    # Skip task marking if error occurs
                    pass
            
            # Update state and continue automatically
            updated_state = dict(state)
            updated_state.update({
                "current_plan": current_plan,
                "execution_mode": "executing"
            })
            
            # Continue with next task
            return await _handle_plan_execution(updated_state, invoke_llm, config)  # type: ignore


async def _execute_task_with_existing_tools(task: dict, state: OrchestratorState, invoke_llm):
    """Execute a task using existing agent tools."""
    
    task_content = task["content"]
    # Get the agent registry (should be available globally)
    try:
        from .graph_builder import get_agent_registry
        get_agent_registry()
    except Exception:
        return f"Task failed: Agent registry not available"
    
    # Intelligent LLM-based routing instead of brittle keyword matching
    agent_tool = await _route_task_to_agent(task_content, invoke_llm)
    instruction = task_content
    
    # If we found a matching agent tool, use it
    if agent_tool:
        try:
            logger.info("task_execution_start", component="orchestrator",
                       task=task_content[:100], agent=agent_tool.__class__.__name__)
            
            # Call the agent tool async method directly to avoid event loop conflicts
            result = await agent_tool._arun(instruction, state)  # type: ignore
            
            logger.info("task_execution_complete", component="orchestrator", 
                       task=task_content[:100], result_length=len(str(result)))
            
            return result
            
        except Exception as e:
            logger.error("task_execution_error", component="orchestrator",
                        task=task_content[:100], error=str(e))
            return f"Task failed: {str(e)}"
    
    # Fallback: Use LLM with tools for general tasks
    try:
        logger.info("task_execution_fallback", component="orchestrator",
                   task=task_content[:100], method="llm_with_tools")
        
        messages = [
            SystemMessage(content=f"Execute this specific task: {task_content}"),
            HumanMessage(content=task_content)
        ]
        
        response = invoke_llm(messages, use_tools=True)
        return str(response.content) if response.content else "Task completed"
        
    except Exception as e:
        logger.error("task_execution_fallback_error", component="orchestrator",
                    task=task_content[:100], error=str(e))
        return f"Task failed: {str(e)}"


async def _handle_plan_completion(current_plan: dict, state: OrchestratorState) -> OrchestratorState:
    """Handle completion of the execution plan."""
    
    completion_message = await _create_plan_completion_message(current_plan)
    
    updated_state = dict(state)
    updated_state.update({
        "messages": [completion_message],
        "current_plan": current_plan,
        "execution_mode": "normal"
    })
    
    return updated_state  # type: ignore


async def _create_plan_completion_message(current_plan: dict) -> AIMessage:
    """Create completion message for the plan."""
    
    # Update plan status
    current_plan["status"] = "completed"
    current_plan["completed_at"] = datetime.now().isoformat()
    
    # Get task summary
    completed_tasks = [t for t in current_plan["tasks"] if (t["status"].value if hasattr(t["status"], "value") else t["status"]) == "completed"]
    failed_tasks = [t for t in current_plan["tasks"] if (t["status"].value if hasattr(t["status"], "value") else t["status"]) == "failed"]
    
    # Show completed tasks with more detail
    task_summary = ""
    if completed_tasks:
        task_summary += "**Completed Tasks:**\n" + "\n".join([
            f"✓ {task['content']}" for task in completed_tasks[:7]  # Show more tasks
        ])
        if len(completed_tasks) > 7:
            task_summary += f"\n... and {len(completed_tasks) - 7} more"
    
    if failed_tasks:
        task_summary += "\n\n**Failed Tasks:**\n" + "\n".join([
            f"✗ {task['content']}" for task in failed_tasks[:3]  # Show first 3
        ])
        if len(failed_tasks) > 3:
            task_summary += f"\n... and {len(failed_tasks) - 3} more failed tasks"
    
    completion_text = f"""🎉 **Plan Execution Complete!**

**Original Request:** {current_plan.get('original_instruction', 'N/A')}

**Summary:**
- Total Tasks: {len(current_plan['tasks'])}
- Completed: {len(completed_tasks)}
- Failed: {len(failed_tasks)}
- Success Rate: {(len(completed_tasks)/len(current_plan['tasks']))*100:.0f}%

{task_summary}

All tasks have been executed. What would you like to do next?"""
    
    return AIMessage(content=completion_text)


def _format_todo_list(tasks: list, show_status: bool = True) -> str:
    """Format tasks as a todo list with clean checkmarks and styling."""
    
    if not tasks:
        return "No tasks"
    
    todo_items = []
    for i, task in enumerate(tasks, 1):
        status_icon = ""
        if show_status:
            # Handle both enum objects and string values
            status_value = task["status"].value if hasattr(task["status"], "value") else task["status"]
            if status_value == "completed":
                status_icon = "✓ "
            elif status_value == "failed":
                status_icon = "✗ "
            elif status_value == "in_progress":
                status_icon = "→ "
            else:
                status_icon = "□ "
        
        priority_indicator = ""
        # Handle both enum objects and string values
        priority_value = task["priority"].value if hasattr(task["priority"], "value") else task["priority"]
        if priority_value == "high":
            priority_indicator = " (HIGH)"
        elif priority_value == "urgent":
            priority_indicator = " (URGENT)"
        
        todo_items.append(f"{status_icon}{i}. {task['content']}{priority_indicator}")
    
    return "\n".join(todo_items)