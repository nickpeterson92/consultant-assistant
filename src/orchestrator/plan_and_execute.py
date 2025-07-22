"""Exact canonical plan-and-execute implementation from LangGraph tutorial.

Reference: https://langchain-ai.github.io/langgraph/tutorials/plan-and-execute/plan-and-execute/#create-the-graph
"""

import operator
import time
from datetime import datetime
from typing import Annotated, List, Union
from typing_extensions import TypedDict
from pydantic import BaseModel, Field, validator

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import tools_condition
from langgraph.checkpoint.memory import MemorySaver

from langchain_core.messages import HumanMessage, AIMessage
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
    messages: Annotated[List, add_messages]  # Persistent conversation history across requests
    thread_id: str  # Thread ID for memory context
    task_id: str  # Task ID for SSE event correlation
    plan_step_offset: int  # Track where current plan starts in past_steps


# ================================
# Models - EXACT from tutorial
# ================================

class Plan(BaseModel):
    """Plan to follow in future"""
    steps: List[str] = Field(
        description="different steps to follow, should be in sorted order"
    )
    
    @validator('steps', each_item=True)
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

@log_execution("orchestrator", "execute_step", include_args=True, include_result=False)  # Don't log full result due to size
@emit_coordinated_events(["task_lifecycle", "plan_updated"])
def execute_step(state: PlanExecute):
    import asyncio
    from datetime import datetime
    from .observers import get_observer_registry, SearchResultsEvent
    from src.memory import get_thread_memory, ContextType, create_memory_node, RelationshipType
    
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
        logger.error("execute_step_no_plan", 
                    operation="execute_step",
                    thread_id=thread_id,
                    state_keys=list(state.keys()))
        return {"messages": [HumanMessage(content="Error: No plan steps available to execute")]}
    
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
        for i, (step_desc, result) in enumerate(current_plan_steps, 1):
            past_steps_context += f"Step {i}: {step_desc}\nResult: {result}\n\n"
    
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
    
    # Use ReAct agent executor with full conversation context
    # Merge persistent conversation messages with current task
    persistent_messages = state.get("messages", [])
    
    # Create agent messages by combining conversation history with current task
    agent_messages = list(persistent_messages)  # Copy conversation history
    agent_messages.append(("user", task_formatted))  # Add current execution step
    
    # Trim for ReAct agent context to prevent bloat
    from src.utils.agents.message_processing.helpers import trim_messages_for_context
    if len(agent_messages) > 15:  # Keep ReAct agent context focused
        agent_messages = trim_messages_for_context(
            agent_messages,
            max_tokens=40000,  # Conservative for execution context
            keep_last_n=15     # Recent conversation + current task
        )
    
    logger.info("react_agent_context",
               operation="execute_step",
               conversation_messages=len(persistent_messages),
               agent_messages=len(agent_messages),
               current_task=task[:100])
    
    # Log ReAct agent invocation start
    react_start_time = time.time()
    logger.info("react_agent_start",
               operation="execute_step",
               thread_id=thread_id,
               step_number=current_step_num,
               agent_input_messages=len(agent_messages),
               task_description=task[:150])
    
    try:
        agent_response = asyncio.run(agent_executor.ainvoke(
            {"messages": agent_messages}
        ))
        
        # Log ReAct agent completion  
        react_duration = time.time() - react_start_time
        response_messages = agent_response.get("messages", [])
        logger.info("react_agent_complete",
                   operation="execute_step",
                   thread_id=thread_id,
                   duration_seconds=round(react_duration, 3),
                   response_messages=len(response_messages),
                   has_tool_calls=any(hasattr(msg, 'tool_calls') and msg.tool_calls for msg in response_messages),
                   success=True)
                   
    except Exception as e:
        react_duration = time.time() - react_start_time
        logger.error("react_agent_error",
                    operation="execute_step",
                    thread_id=thread_id,
                    duration_seconds=round(react_duration, 3),
                    error=str(e),
                    error_type=type(e).__name__)
        raise
    
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
        # Extract tool response data if present
        tool_response_data = None
        for message in messages:
            # Check for tool response messages (ToolMessage type)
            if hasattr(message, 'name') and hasattr(message, 'content'):
                # This is a tool response message
                try:
                    import json
                    tool_result = json.loads(message.content)
                    if isinstance(tool_result, dict) and tool_result.get('success', False):
                        tool_response_data = tool_result.get('data')
                except:
                    pass
        
        # Get the agent's final message
        agent_final_message = messages[-1].content
        
        # If we have tool response data from a GET operation, include it in the response
        if tool_response_data and task and any(word in task.lower() for word in ['get', 'retrieve', 'fetch', 'show', 'display', 'find', 'search']):
            # Format the data nicely if it's a dict/list
            if isinstance(tool_response_data, (dict, list)):
                import json
                formatted_data = json.dumps(tool_response_data, indent=2)
                final_response = f"{agent_final_message}\n\nHere's the data:\n```json\n{formatted_data}\n```"
            else:
                final_response = f"{agent_final_message}\n\nHere's the data:\n{tool_response_data}"
        else:
            final_response = agent_final_message
    
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
        task_words = set(task.lower().split()) if task else set()
        input_text = state.get("input", "")
        input_words = set(input_text.lower().split()) if input_text else set()
        semantic_tags = task_words.union(input_words)
        
        # Clean up tags (remove common words)
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        semantic_tags = {tag for tag in semantic_tags if len(tag) > 2 and tag not in stop_words}
        
        # Find previous nodes to relate to (previous steps in execution)
        relates_to = []
        related_entities = []
        
        # Get all nodes and find recent execution steps
        recent_nodes = memory.retrieve_relevant(
            query_text="",
            max_age_hours=0.5,  # Last 30 minutes
            min_relevance=0,
            max_results=20
        )
        
        # Link to the most recent execution step if any
        previous_step = None
        for node in recent_nodes:
            if node.context_type in {ContextType.COMPLETED_ACTION, ContextType.SEARCH_RESULT}:
                relates_to.append(node.node_id)
                previous_step = node
                break  # Just link to the most recent one
        
        # Use intelligent entity extraction
        from .entity_extractor import extract_entities_intelligently
        
        # Determine context from the task
        extraction_context = {
            'task': task,
            'agent': 'unknown'
        }
        
        # Identify which agent was used
        for message in agent_response.get("messages", []):
            if hasattr(message, 'tool_calls') and message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_name = tool_call.get("name", "").lower()
                    if 'salesforce' in tool_name:
                        extraction_context['agent'] = 'salesforce'
                        extraction_context['system'] = 'salesforce'
                        break
                    elif 'jira' in tool_name:
                        extraction_context['agent'] = 'jira'
                        extraction_context['system'] = 'jira'
                        break
                    elif 'servicenow' in tool_name:
                        extraction_context['agent'] = 'servicenow'
                        extraction_context['system'] = 'servicenow'
                        break
        
        # Extract entities from all available data
        all_data_sources = []
        
        # 1. Tool response data
        if tool_response_data:
            all_data_sources.append(tool_response_data)
        
        # 2. Message contents
        for message in agent_response.get("messages", []):
            if hasattr(message, 'content'):
                try:
                    import json
                    content = json.loads(message.content) if isinstance(message.content, str) else message.content
                    if isinstance(content, dict) and content.get('success'):
                        if 'data' in content:
                            all_data_sources.append(content['data'])
                except:
                    pass
        
        # 3. Even check the final response text for entity IDs
        all_data_sources.append(final_response)
        
        # Extract entities intelligently
        extracted_entities = []
        for data_source in all_data_sources:
            entities = extract_entities_intelligently(data_source, extraction_context)
            extracted_entities.extend(entities)
        
        # Deduplicate by ID
        entity_map = {}
        for entity_info in extracted_entities:
            entity_id = entity_info['id']
            if entity_id not in entity_map or entity_info['confidence'] > entity_map[entity_id]['confidence']:
                entity_map[entity_id] = entity_info
        
        logger.info("INTELLIGENT_ENTITY_EXTRACTION",
                   component="orchestrator",
                   operation="execute_step",
                   total_entities_found=len(entity_map),
                   extraction_context=extraction_context,
                   entity_types=list(set(e['type'] for e in entity_map.values())),
                   systems=list(set(e['system'] for e in entity_map.values())))
        
        # Create or link to domain entity nodes
        for entity_key, entity_info in entity_map.items():
            # Check if we already have this entity in memory
            entity_node = None
            for node in recent_nodes:
                if node.context_type == ContextType.DOMAIN_ENTITY:
                    node_content = node.content if isinstance(node.content, dict) else {}
                    if (entity_info['id'] and node_content.get('entity_id') == entity_info['id']) or \
                       (entity_info['name'] and node_content.get('entity_name') == entity_info['name']):
                        entity_node = node
                        break
            
            if not entity_node and (entity_info['id'] or entity_info['name']):
                # Create new domain entity node
                entity_tags = set()
                if entity_info['name']:
                    # Extract meaningful words from name for tags
                    name_words = entity_info['name'].lower().split() if entity_info['name'] else []
                    entity_tags.update(word for word in name_words if len(word) > 2 and word not in stop_words)
                if entity_info.get('type'):
                    entity_tags.add(entity_info['type'].lower())
                if entity_info['system']:
                    entity_tags.add(entity_info['system'])
                
                # Add confidence to relevance
                base_relevance = 0.6 + (entity_info['confidence'] * 0.3)
                
                # Debug logging for entity storage
                logger.info("storing_entity_in_memory",
                          entity_id=entity_info['id'],
                          entity_name=entity_info['name'],
                          entity_type=entity_info['type'],
                          has_name=bool(entity_info['name']),
                          data_keys=list(entity_info.get('data', {}).keys()) if isinstance(entity_info.get('data'), dict) else None)
                
                entity_node_id = memory.store(
                    content={
                        "entity_id": entity_info['id'],
                        "entity_name": entity_info['name'],
                        "entity_type": entity_info['type'],
                        "entity_system": entity_info['system'],
                        "entity_data": entity_info['data'],
                        "entity_relationships": entity_info.get('relationships', []),
                        "extraction_confidence": entity_info['confidence'],
                        "first_seen": datetime.now().isoformat(),
                        "last_accessed": datetime.now().isoformat()
                    },
                    context_type=ContextType.DOMAIN_ENTITY,
                    tags=entity_tags,
                    base_relevance=base_relevance,
                    summary=f"{entity_info['type']}: {entity_info['name'] or entity_info['id']}"
                )
                related_entities.append(entity_node_id)
                
                # Create relationships to other entities
                for related_id, rel_type in entity_info.get('relationships', []):
                    # Check if related entity exists in our current batch
                    if related_id in entity_map:
                        # We'll create this relationship after all entities are stored
                        pass
                    else:
                        # Create a placeholder relationship that can be resolved later
                        logger.debug("entity_relationship_found",
                                   from_entity=entity_info['id'],
                                   to_entity=related_id,
                                   relationship=rel_type)
                
                # Notify about new entity
                try:
                    from .memory_observer import notify_memory_update
                    node = memory.nodes.get(entity_node_id)
                    if node:
                        notify_memory_update(thread_id, entity_node_id, node, state.get("task_id"))
                except:
                    pass
            elif entity_node:
                related_entities.append(entity_node.node_id)
                # Update last accessed time
                entity_node.access()
        
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
            auto_summarize=True,
            relates_to=relates_to  # Create relationship to previous step
        )
        
        # Create relationships
        # 1. Led-to relationship with previous step
        if relates_to and len(relates_to) > 0:
            memory.add_relationship(
                relates_to[0],  # Previous step
                memory_node_id,  # Current step
                RelationshipType.LED_TO
            )
            
            # Notify observer about the edge
            try:
                from .memory_observer import notify_memory_edge
                notify_memory_edge(
                    thread_id,
                    relates_to[0],
                    memory_node_id,
                    RelationshipType.LED_TO,
                    state.get("task_id")
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
                memory.add_relationship(memory_node_id, entity_id, rel_type)
            
            # Also create reverse relationship - entity relates to this action
            memory.add_relationship(entity_id, memory_node_id, RelationshipType.RELATES_TO)
            
            # Notify about relationships
            try:
                from .memory_observer import notify_memory_edge
                notify_memory_edge(thread_id, memory_node_id, entity_id, rel_type, state.get("task_id"))
                notify_memory_edge(thread_id, entity_id, memory_node_id, RelationshipType.RELATES_TO, state.get("task_id"))
            except:
                pass
        
        # 3. If we detected tool calls, create tool_output nodes
        tool_calls = [
            {"tool": tc.get("name"), "args": tc.get("args", {})} 
            for msg in agent_response["messages"] 
            if hasattr(msg, 'tool_calls') and msg.tool_calls
            for tc in msg.tool_calls
        ]
        
        for tool_call in tool_calls:
            tool_node_id = memory.store(
                content={
                    "tool": tool_call["tool"],
                    "args": tool_call["args"],
                    "timestamp": datetime.now().isoformat()
                },
                context_type=ContextType.TOOL_OUTPUT,
                tags={tool_call["tool"].lower()} if tool_call["tool"] else set(),
                base_relevance=0.6,
                summary=f"Tool call: {tool_call['tool']}"
            )
            
            # Tool output depends on the action
            memory.add_relationship(tool_node_id, memory_node_id, RelationshipType.DEPENDS_ON)
            
            # Notify
            try:
                from .memory_observer import notify_memory_update, notify_memory_edge
                node = memory.nodes.get(tool_node_id)
                if node:
                    notify_memory_update(thread_id, tool_node_id, node, state.get("task_id"))
                notify_memory_edge(thread_id, tool_node_id, memory_node_id, RelationshipType.DEPENDS_ON, state.get("task_id"))
            except:
                pass
        
        logger.info("stored_execution_result_in_memory",
                   component="orchestrator",
                   operation="execute_step",
                   memory_node_id=memory_node_id,
                   context_type=context_type.value,
                   tags=list(semantic_tags),
                   produced_user_data=produced_user_data,
                   linked_to_previous=bool(relates_to))
        
        # Notify observers about memory update
        try:
            from .memory_observer import notify_memory_update
            node = memory.nodes.get(memory_node_id)
            if node:
                notify_memory_update(thread_id, memory_node_id, node, state.get("task_id"))
        except Exception as e:
            logger.warning("memory_observer_notification_failed", error=str(e))
        
    except Exception as e:
        logger.error("failed_to_store_execution_result",
                    component="orchestrator", 
                    operation="execute_step",
                    error=str(e))
        # Don't fail the whole execution if memory storage fails
    
    # Extract new messages from ReAct agent response to merge with conversation
    agent_messages = agent_response.get("messages", [])
    new_messages = []
    
    # Find messages that weren't in our original conversation
    original_count = len(persistent_messages)
    if len(agent_messages) > original_count + 1:  # More than conversation + current task
        # Get the new AI messages (tool calls, responses, etc.)
        new_messages = agent_messages[original_count + 1:]  # Skip conversation + task
        
        logger.info("merging_react_agent_messages",
                   component="orchestrator",
                   operation="execute_step", 
                   new_messages_count=len(new_messages),
                   final_response_preview=final_response[:100])
    
    return {
        "past_steps": [(task, final_response)],
        "messages": new_messages  # Merge ReAct agent's new messages into conversation
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
    
    # Get conversation messages for context and trim if needed
    conversation_messages = state.get("messages", [])
    
    # Trim messages to prevent bloat while preserving context
    from src.utils.agents.message_processing.helpers import trim_messages_for_context
    if len(conversation_messages) > 20:  # Only trim if conversation is getting long
        conversation_messages = trim_messages_for_context(
            conversation_messages,
            max_tokens=60000,  # Conservative limit for planning context
            keep_last_n=20     # Keep recent conversation flow
        )
    
    logger.info("planning_with_conversation_context",
               component="orchestrator",
               operation="plan_step",
               original_length=len(state.get("messages", [])),
               trimmed_length=len(conversation_messages),
               current_input=state["input"][:100])
    
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
    
    # Enhanced planning prompt with conversation + memory context
    planning_input = f"{state['input']}{context_for_planning}"
    
    logger.info("planning_with_memory_context",
               component="orchestrator",
               operation="plan_step",
               context_items=len(planning_context),
               input_length=len(planning_input))
    
    # Use conversation messages for planning context instead of just current input
    planning_messages = list(conversation_messages)  # Copy existing conversation
    planning_messages.append(HumanMessage(content=planning_input))  # Add enhanced planning request
    
    plan = asyncio.run(planner.ainvoke({"messages": planning_messages}))
    
    # Emit memory graph snapshot after plan creation
    try:
        from .memory_observer import get_memory_observer
        observer = get_memory_observer()
        observer.emit_graph_snapshot(thread_id, state.get("task_id"))
    except Exception as e:
        logger.warning("memory_snapshot_emission_failed", error=str(e))
    
    # Set the offset to mark where this plan starts in past_steps
    current_past_steps_length = len(state.get("past_steps", []))
    
    return {
        "plan": plan.steps,
        "plan_step_offset": current_past_steps_length
    }


@log_execution("orchestrator", "replan_step", include_args=True, include_result=True)
@emit_coordinated_events(["plan_modified", "plan_updated"])
def replan_step(state: PlanExecute):
    import asyncio
    from src.memory import get_thread_memory, ContextType
    
    # Get memory for context-aware replanning
    thread_id = state.get("thread_id", "default-thread")
    memory = get_thread_memory(thread_id)
    
    # Format past_steps for the template - only include steps from current plan
    plan_offset = state.get("plan_step_offset", 0)
    current_plan_steps = state["past_steps"][plan_offset:]  # Only steps from current plan
    
    past_steps_str = ""
    for i, (step, result) in enumerate(current_plan_steps):
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
    
    # Log critical decision point
    logger.info("replan_decision",
               operation="replan_step", 
               thread_id=thread_id,
               decision_type="Response" if isinstance(output.action, Response) else "Plan",
               will_end_workflow=isinstance(output.action, Response),
               completed_vs_total=f"{len(current_plan_steps)}/{len(state.get('plan', []))}")
    
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
        
        # Add AI response to conversation history when task completes
        ai_response = AIMessage(content=output.action.response)
        
        # Trim the overall conversation state to prevent bloat
        current_messages = state.get("messages", [])
        from src.utils.agents.message_processing.helpers import trim_messages_for_context
        
        # Add the new AI response
        updated_messages = current_messages + [ai_response]
        
        # Trim if conversation is getting too long
        if len(updated_messages) > 50:  # Trim when conversation exceeds 50 messages
            updated_messages = trim_messages_for_context(
                updated_messages,
                max_tokens=80000,  # Keep substantial conversation history
                keep_last_n=30     # Preserve recent conversation flow
            )
            
            logger.info("trimmed_conversation_state",
                       component="orchestrator",
                       operation="replan_step",
                       original_count=len(current_messages) + 1,
                       trimmed_count=len(updated_messages))
        
        return {
            "response": output.action.response,
            "messages": [ai_response] if len(updated_messages) <= 50 else updated_messages
        }
    else:
        # Check if the new plan includes human_input - if so, show the most recent result to user
        new_plan = output.action.steps
        
        # Log if we have None values in the plan
        if any(step is None for step in new_plan):
            logger.warning("plan_contains_none_steps",
                          component="orchestrator",
                          operation="replan_step",
                          plan=new_plan,
                          none_indices=[i for i, step in enumerate(new_plan) if step is None])
        
        user_visible_responses = []
        
        # If any plan step mentions human_input, show the most recent past step result to user
        past_steps = state.get("past_steps", [])
        if any("human_input" in step.lower() for step in new_plan if step is not None) and past_steps:
            last_step, last_result = past_steps[-1]
            user_visible_responses.append(last_result)
        
        return {
            "plan": new_plan,
            "user_visible_responses": user_visible_responses
        }


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