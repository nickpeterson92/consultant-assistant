"""Conversation handling logic for the orchestrator."""

import asyncio
import json
import uuid

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig

from src.utils.config import (
    get_conversation_config, get_database_config,
    MEMORY_NAMESPACE_PREFIX, SIMPLE_MEMORY_KEY,
    SUMMARY_KEY, NO_SUMMARY_TEXT,
    SUMMARY_USER_MESSAGE_THRESHOLD, SUMMARY_TIME_THRESHOLD_SECONDS,
    MEMORY_TOOL_CALL_THRESHOLD, MEMORY_AGENT_CALL_THRESHOLD
)
from src.utils.shared import (
    EventAnalyzer,
    create_user_message_event, create_ai_response_event,
    create_tool_call_event, create_summary_triggered_event,
    create_memory_update_triggered_event
)
from src.utils.logging import get_logger
from src.utils.storage import get_async_store_adapter
from src.utils.storage.memory_schemas import SimpleMemory
from .state import OrchestratorState, load_events_with_limit
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
        
        events = load_events_with_limit(state)
        
        logger.info("orchestrator_state_entry",
            component="orchestrator",
            operation="conversation_processing",
            message_count=msg_count,
            has_summary=bool(state.get('summary')),
            has_memory=bool(state.get('memory')),
            thread_id=config["configurable"].get("thread_id", "default")
        )
        
        # Log message types
        if hasattr(last_msg, 'content'):
            if isinstance(last_msg, HumanMessage):
                event = create_user_message_event(
                    str(last_msg.content), 
                    msg_count
                )
                events.append(event)
                logger.info("user_request", component="orchestrator", user_message=str(last_msg.content)[:200],
                                         message_count=msg_count,
                                         event_count=len(events))
            elif isinstance(last_msg, AIMessage):
                logger.info("ai_response_processing", component="orchestrator", ai_message=str(last_msg.content)[:200],
                                         message_count=msg_count,
                                         event_count=len(events))
                    
        # Load persistent memory
        user_id = config["configurable"].get("user_id", "default")
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
            user_id = config["configurable"].get("user_id", conv_config.default_user_id)
            thread_id = config["configurable"].get("thread_id", conv_config.default_thread_id)
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
                                summary_length=len(summary) if summary else 0,
                                summary_preview=summary[:200] if summary else "NO_SUMMARY")
        
        # Check if there's an interrupted workflow that needs the user's response
        interrupted_workflow = state.get("interrupted_workflow")
        workflow_human_response = state.get("_workflow_human_response")
        
        # If we have both, we need to automatically call workflow_agent
        if interrupted_workflow and workflow_human_response:
            logger.info("auto_calling_workflow_for_interrupted_response",
                component="orchestrator",
                operation="conversation_node",
                workflow_name=interrupted_workflow.get("workflow_name"),
                thread_id=interrupted_workflow.get("thread_id"),
                human_response_preview=workflow_human_response[:50] if workflow_human_response else ""
            )
            
            # Create a properly formatted tool call following LangChain standards
            tool_call_id = f"call_{uuid.uuid4().hex[:24]}"
            
            # Create AI message with tool call using dict format (as expected by execute_command_tools)
            ai_msg = AIMessage(
                content="",  # Empty content as per LangChain standards when using tools
                tool_calls=[{
                    "name": "workflow_agent",
                    "args": {"instruction": workflow_human_response},
                    "id": tool_call_id
                }]
            )
            
            # Log the auto-generated tool call
            logger.info("auto_tool_call_created",
                component="orchestrator", 
                tool_name="workflow_agent",
                tool_call_id=tool_call_id,
                tool_args={"instruction": workflow_human_response[:100]},
                event_count=len(state.get("events", [])) + 1
            )
            
            # Clear the human response flag after using it
            updated_state = {
                "messages": [ai_msg],
                "events": state.get("events", []),
                "_workflow_human_response": None
            }
            
            # Return early with this tool call
            return updated_state
        
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
                thread_id=config["configurable"].get("thread_id", "default")
            )
            
            # Import trimming utility
            from src.utils.agents.message_processing import trim_messages_for_context
            
            # Trim messages ONLY for LLM call, not in state
            llm_messages = trim_messages_for_context(
                state_messages,
                max_tokens=100000,  # Conservative token limit
                keep_system=False,  # System message is added separately
                keep_first_n=5,     # Keep first few messages for context
                keep_last_n=conv_config.max_conversation_length - 10  # Keep most recent
            )
            
            logger.info("message_trimming_complete",
                component="orchestrator",
                operation="trim_for_llm_context",
                trimmed_count=len(llm_messages),
                thread_id=config["configurable"].get("thread_id", "default")
            )
        else:
            # Use all messages if under limit
            llm_messages = state_messages
        
        messages = [SystemMessage(content=system_message)] + llm_messages
        
        logger.info("llm_invocation_start",
            component="orchestrator",
            operation="invoke_llm",
            message_count=len(messages),
            system_message_length=len(system_message),
            use_tools=True
        )
        
        response = invoke_llm(messages, use_tools=True)
        
        if hasattr(response, 'tool_calls') and response.tool_calls:
            for tool_call in response.tool_calls:
                tool_event = create_tool_call_event(
                    tool_call.get('name', 'unknown'),
                    tool_call.get('args', {}),
                    msg_count
                )
                events.append(tool_event)
                logger.info("tool_call", component="orchestrator", tool_name=tool_call.get('name', 'unknown'),
                                         tool_args=tool_call.get('args', {}),
                                         event_count=len(events))
        
        response_content = str(response.content) if hasattr(response, 'content') else ""
        
        # Estimate token usage
        message_chars = sum(len(str(m.content if hasattr(m, 'content') else m)) for m in messages)
        response_chars = len(response_content)
        estimated_tokens = (message_chars + response_chars) // 4
        
        ai_event = create_ai_response_event(
            response_content,
            msg_count,
            estimated_tokens
        )
        events.append(ai_event)
        
        logger.info("llm_generation_complete", component="orchestrator", response_length=len(response_content),
                                 response_content=response_content[:500],
                                 has_tool_calls=bool(hasattr(response, 'tool_calls') and response.tool_calls),
                                 event_count=len(events))
        
        logger.track_cost("ORCHESTRATOR_LLM", tokens=estimated_tokens, 
                        message_count=len(messages),
                        event_count=len(events))
        
        # Trim events to prevent unbounded growth
        conv_config = get_conversation_config()
        max_events = conv_config.max_event_history
        recent_events = events[-max_events:] if len(events) > max_events else events
        event_dicts = [e.to_dict() for e in recent_events]
        
        if len(events) > max_events:
            logger.info("event_history_trimmed", component="orchestrator", total_events=len(events),
                                    kept_events=max_events,
                                    trimmed_events=len(events) - max_events)
        
        # Preserve all existing state fields and only update specific ones
        updated_state = state.copy()
        updated_state.update({
            "messages": response,
            "memory": existing_memory,
            "events": event_dicts
        })
        
        if "summary" not in state or not state.get("summary"):
            updated_state["summary"] = "No summary available"
            logger.info("summary_initialized", component="orchestrator", operation="setting_default_summary")
        
        # Check if we need to clear completed workflow state
        # This happens when workflow agent returns a completion (handled by tool)
        if "interrupted_workflow" in state and state.get("interrupted_workflow") is None:
            # Workflow was explicitly cleared by the tool, preserve this
            updated_state["interrupted_workflow"] = None
            logger.info("workflow_state_cleared",
                component="orchestrator",
                operation="clear_completed_workflow",
                reason="workflow_completed"
            )
        elif "interrupted_workflow" in state:
            # Preserve existing interrupted workflow state if not explicitly cleared
            updated_state["interrupted_workflow"] = state["interrupted_workflow"]
        
        # Check for background task triggers
        conv_config = get_conversation_config()
        
        # Check summary trigger based on total message count OR event-based triggers
        total_messages = len(state.get("messages", []))
        should_trigger_by_count = total_messages >= conv_config.summary_threshold
        should_trigger_by_events = EventAnalyzer.should_trigger_summary(events, 
                                               user_message_threshold=SUMMARY_USER_MESSAGE_THRESHOLD,
                                               time_threshold_seconds=SUMMARY_TIME_THRESHOLD_SECONDS)
        
        if should_trigger_by_count or should_trigger_by_events:
            
            # Determine trigger reason
            if should_trigger_by_count and should_trigger_by_events:
                trigger_reason = f"Message count ({total_messages}) exceeded threshold ({conv_config.summary_threshold}) and event-based triggers"
            elif should_trigger_by_count:
                trigger_reason = f"Message count ({total_messages}) reached threshold ({conv_config.summary_threshold})"
            else:
                trigger_reason = "Event-based triggers (user messages or time threshold)"
            
            summary_event = create_summary_triggered_event(
                msg_count,
                trigger_reason
            )
            events.append(summary_event)
            event_dicts.append(summary_event.to_dict())
            
            logger.info("summary_trigger", 
                component="orchestrator", 
                operation="summary_triggered",
                total_message_count=total_messages,
                summary_threshold=conv_config.summary_threshold,
                triggered_by_count=should_trigger_by_count,
                triggered_by_events=should_trigger_by_events,
                trigger_reason=trigger_reason,
                event_count=len(events))
            
            user_id = config["configurable"].get("user_id", "default")
            thread_id = config["configurable"].get("thread_id", "default")
            
            asyncio.create_task(
                _run_background_summary_async(
                    state["messages"], 
                    state.get("summary", ""), 
                    events, 
                    existing_memory, 
                    user_id, 
                    thread_id,
                    summarize_func,
                    invoke_llm
                )
            )
        
        # Check memory trigger
        if EventAnalyzer.should_trigger_memory_update(events,
                                                    tool_call_threshold=MEMORY_TOOL_CALL_THRESHOLD,
                                                    agent_call_threshold=MEMORY_AGENT_CALL_THRESHOLD):
            
            memory_event = create_memory_update_triggered_event(
                msg_count,
                "Threshold reached based on tool/agent calls"
            )
            events.append(memory_event)
            event_dicts.append(memory_event.to_dict())
            
            logger.info("memory_trigger", component="orchestrator", event_count=len(events),
                                    message_count=len(state["messages"]))
            
            user_id = config["configurable"].get("user_id", "default")
            
            # Create new store instance for async context
            async_memory_store = get_async_store_adapter(
                db_path=get_database_config().path
            )
            
            asyncio.create_task(
                _run_background_memory_async(
                    state["messages"], 
                    state.get("summary", ""), 
                    events, 
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