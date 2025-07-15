"""Background task handling for conversation summarization and memory extraction."""

import asyncio
import time
import traceback
from typing import Dict, Any, cast, List

from langchain_core.messages import SystemMessage, RemoveMessage

from src.utils.config import (
    get_conversation_config, get_database_config,
    DETERMINISTIC_TEMPERATURE, DETERMINISTIC_TOP_P,
    STATE_KEY_PREFIX
)
from src.utils.agents.prompts import TRUSTCALL_INSTRUCTION
from src.utils.agents.message_processing import smart_preserve_messages
from src.utils.logging import get_logger
from src.utils.storage import get_async_store_adapter
from src.utils.storage.memory_schemas import SimpleMemory
from src.utils.agents.prompts import orchestrator_summary_sys_msg, get_fallback_summary
from .state import OrchestratorState

logger = get_logger()


async def summarize_conversation(state: OrchestratorState, invoke_llm):
    """Summarize conversation with intelligent message preservation."""
    start_time = time.time()
    messages_count = len(state.get('messages', []))
    
    summary = state.get("summary", "No summary available")
    memory_val = state.get("memory", "No memory available")
    
    logger.info("summary_request",
        component="orchestrator",
        messages_count=messages_count,
        current_summary=summary,
        memory_context=memory_val
    )
    
    system_message = orchestrator_summary_sys_msg(summary, memory_val if isinstance(memory_val, dict) else {})
    messages = [SystemMessage(content=system_message)] + state["messages"]
    
    response = invoke_llm(messages, use_tools=False, temperature=DETERMINISTIC_TEMPERATURE, top_p=DETERMINISTIC_TOP_P)
    
    response_content = str(response.content) if hasattr(response, 'content') else ""
    
    # Validate summary format
    has_technical_section = "TECHNICAL/SYSTEM INFORMATION:" in response_content
    has_user_section = "USER INTERACTION:" in response_content
    has_agent_section = "AGENT COORDINATION CONTEXT:" in response_content
    is_valid_format = has_technical_section and has_user_section and has_agent_section
    
    has_conversational_intro = any(phrase in response_content.lower() for phrase in [
        "here are", "the records", "i found", "the details", "let me", 
        "based on", "according to", "shows that", "indicates"
    ])
    
    logger.info("summary_format_validation", component="orchestrator", operation="format_check",
                is_valid_format=is_valid_format,
                has_technical_section=has_technical_section,
                has_user_section=has_user_section,
                has_agent_section=has_agent_section,
                has_conversational_intro=has_conversational_intro,
                response_preview=response_content[:300],
                response_length=len(response_content))
    
    if not is_valid_format or has_conversational_intro:
        logger.debug("summary_format_fallback",
            component="orchestrator",
            operation="format_validation",
            reason="Invalid summary format detected"
        )
        logger.info("summary_format_error", component="orchestrator", error="Invalid summary format",
                    response_content=response_content[:500])
        
        # Generate fallback summary
        messages = state.get('messages', [])
        message_count = len(messages)
        
        has_tool_calls = any(
            hasattr(msg, 'tool_calls') and msg.tool_calls 
            for msg in messages if hasattr(msg, 'tool_calls')
        )
        
        agent_names = []
        for msg in messages:
            if hasattr(msg, 'name') and msg.name:
                if 'salesforce' in msg.name.lower():
                    agent_names.append('salesforce-agent')
                elif 'agent' in msg.name.lower():
                    agent_names.append(msg.name)
        agent_names = list(set(agent_names))
        
        # Simple error count tracking (no events)
        error_count = 0
        
        response_content = get_fallback_summary(
            message_count=message_count,
            has_tool_calls=has_tool_calls,
            agent_names=agent_names,
            error_count=error_count
        )
    
    # Preserve more messages after summarization
    # Keep enough to maintain context but not overwhelm the system
    conv_config = get_conversation_config()
    preserve_count = min(20, len(state["messages"]) // 3)  # Keep 1/3 of messages or 20, whichever is less
    preserve_count = max(preserve_count, 5)  # But always keep at least 5 messages
    
    messages_to_preserve = smart_preserve_messages(state["messages"], keep_count=preserve_count)
    messages_to_delete = []
    
    preserved_ids = {getattr(msg, 'id', None) for msg in messages_to_preserve if hasattr(msg, 'id')}
    for msg in state["messages"]:
        if hasattr(msg, 'id') and msg.id not in preserved_ids:
            messages_to_delete.append(RemoveMessage(id=msg.id))
    
    logger.info("llm_generation_complete", component="orchestrator", response_length=len(response_content),
                response_content=response_content[:500],
                operation="SUMMARIZATION")
    
    message_chars = sum(len(str(m.content if hasattr(m, 'content') else m)) for m in messages)
    estimated_tokens = message_chars // 4
    logger.track_cost("ORCHESTRATOR_LLM_CALL", tokens=estimated_tokens, 
                     message_count=len(messages_to_preserve),
                     response_length=len(str(response.content)) if hasattr(response, 'content') else 0)
    
    processing_time = time.time() - start_time
    logger.info("summary_response",
        component="orchestrator",
        new_summary=response_content,
        messages_preserved=len(messages_to_preserve),
        messages_deleted=len(messages_to_delete),
        processing_time=processing_time
    )
    
    return {
        "summary": response_content,
        "messages": messages_to_delete
    }


async def memorize_records(state: OrchestratorState, config: Dict[str, Any], memory_store, trustcall_extractor):
    """Extract and persist structured data from conversation."""
    conv_config = get_conversation_config()
    user_id = config.get("configurable", {}).get("user_id", conv_config.default_user_id)
    thread_id = config.get("configurable", {}).get("thread_id")
    namespace = (conv_config.memory_namespace_prefix, user_id)
    key = conv_config.memory_key
    
    extraction_start_time = time.time()
    logger.info("memory_extraction_start",
        component="orchestrator",
        operation="extract_records",
        message_count=len(state.get("messages", [])),
        user_id=user_id,
        thread_id=thread_id
    )
    
    try:
        stored = memory_store.sync_get(namespace, key)
    except Exception as e:
        logger.error("memory_load_error",
            component="orchestrator",
            operation="load_existing_memory",
            error=str(e),
            error_type=type(e).__name__
        )
        stored = None
    
    current_memory = SimpleMemory(**stored) if stored else SimpleMemory()
    
    tool_messages = [
        (i, msg) for i, msg in enumerate(state.get("messages", []))
        if (hasattr(msg, 'name') and msg.name and 
            hasattr(msg, 'content') and msg.content and
            ('salesforce' in msg.name.lower() or 'agent' in msg.name.lower()))
    ]
    
    if tool_messages:
        logger.info("memory_extraction_tool_messages",
            component="orchestrator",
            operation="filter_tool_messages",
            tool_message_count=len(tool_messages),
            total_message_count=len(state.get("messages", []))
        )
        
        for idx, (msg_idx, tool_msg) in enumerate(tool_messages):
            try:
                msg_extraction_start = time.time()
                
                extraction_prompt = f"""{TRUSTCALL_INSTRUCTION}

Tool Message {idx + 1} of {len(tool_messages)}:
{str(tool_msg.content)[:2000]}"""
                
                result = trustcall_extractor.invoke({
                    "messages": [("human", extraction_prompt)],
                    "existing": {"SimpleMemory": current_memory.model_dump()}
                }, tool_choice="SimpleMemory")
                
                if result and hasattr(result, 'model_dump'):
                    result_data = result.model_dump()
                    
                    for field in ['accounts', 'contacts', 'opportunities', 'cases', 'tasks', 'leads']:
                        if hasattr(result, field) and getattr(result, field):
                            current_items = getattr(current_memory, field, [])
                            new_items = getattr(result, field, [])
                            
                            for new_item in new_items:
                                exists = any(
                                    item.id == new_item.id 
                                    for item in current_items 
                                    if hasattr(item, 'id') and hasattr(new_item, 'id')
                                )
                                if not exists:
                                    current_items.append(new_item)
                            
                            setattr(current_memory, field, current_items)
                
                msg_extraction_time = time.time() - msg_extraction_start
                logger.info("memory_extraction_message_complete",
                    component="orchestrator",
                    operation="extract_from_message",
                    message_index=msg_idx,
                    extraction_time=msg_extraction_time,
                    has_result=bool(result)
                )
                
            except Exception as e:
                logger.error("memory_extraction_message_error",
                    component="orchestrator",
                    operation="extract_from_message",
                    message_index=msg_idx,
                    error=str(e),
                    error_type=type(e).__name__
                )
                continue
    
    try:
        memory_store.sync_put(namespace, key, current_memory.model_dump())
        
        extraction_time = time.time() - extraction_start_time
        logger.info("memory_extraction_complete",
            component="orchestrator",
            operation="save_memory",
            user_id=user_id,
            thread_id=thread_id,
            extraction_time=extraction_time,
            accounts=len(current_memory.accounts),
            contacts=len(current_memory.contacts),
            opportunities=len(current_memory.opportunities),
            cases=len(current_memory.cases),
            tasks=len(current_memory.tasks),
            leads=len(current_memory.leads)
        )
        
    except Exception as e:
        logger.error("memory_save_error",
            component="orchestrator",
            operation="save_memory",
            error=str(e),
            error_type=type(e).__name__
        )
    
    updated_memory = {conv_config.memory_key: current_memory.model_dump()}
    
    # Log completion
    logger.info("memory_extraction_summary",
        component="orchestrator",
        entities_extracted=sum([
            len(current_memory.accounts),
            len(current_memory.contacts),
            len(current_memory.opportunities),
            len(current_memory.cases),
            len(current_memory.tasks),
            len(current_memory.leads)
        ]),
        extraction_time=time.time() - extraction_start_time
    )
    
    return {
        "memory": updated_memory
    }


async def _run_background_summary_async(messages, summary, memory, user_id, thread_id, summarize_func, invoke_llm):
    """Execute summarization in background using async."""
    try:
        memory_store = get_async_store_adapter(
            db_path=get_database_config().path
        )
        
        mock_state = {
            "messages": messages,  # Don't serialize here - summarize_conversation expects actual messages
            "summary": summary,
            "memory": memory
        }
        
        result = await summarize_func(mock_state, invoke_llm)
        
        if result and "summary" in result:
            new_summary = result["summary"]
            logger.info("background_summary_save", 
                component="orchestrator", 
                operation="saving_summary_to_store",
                summary_preview=new_summary[:200] if new_summary else "NO_SUMMARY"
            )
            
            conv_config = get_conversation_config()
            namespace = (conv_config.memory_namespace_prefix, user_id)
            key = f"{STATE_KEY_PREFIX}{thread_id}"
            
            mock_state["summary"] = new_summary
            
            # Serialize messages before saving
            from src.utils.agents.message_processing.unified_serialization import serialize_messages_for_json
            
            serialized_state = {
                "messages": serialize_messages_for_json(mock_state["messages"]),
                "summary": mock_state["summary"],
                "memory": mock_state["memory"]
            }
            
            await memory_store.put(namespace, key, {
                "state": serialized_state,
                "thread_id": thread_id,
                "timestamp": time.time()
            })
            
    except Exception as e:
        logger.error("background_summary_error",
            component="system",
            operation="background_summary",
            error=str(e),
            error_type=type(e).__name__
        )


async def _run_background_memory_async(messages, summary, memory, user_id, memorize_func, memory_store, trustcall_extractor):
    """Execute memory extraction in background using async."""
    try:
        mock_state = {
            "messages": messages,  # Don't serialize here - memorize_records expects actual message objects
            "summary": summary,
            "memory": memory
        }
        conv_config = get_conversation_config()
        mock_config = {"configurable": {"user_id": user_id}}
        
        result = await memorize_func(mock_state, mock_config, memory_store, trustcall_extractor)
        
        logger.info("background_memory_complete",
            component="orchestrator",
            operation="background_memory",
            success=True
        )
        
    except Exception as e:
        logger.error("background_memory_error",
            component="system",
            operation="background_memory",
            error=str(e),
            error_type=type(e).__name__
        )

