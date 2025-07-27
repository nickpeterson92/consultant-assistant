"""A2A handler for the orchestrator using main orchestrator architecture."""

import uuid
from typing import Dict, Any
from datetime import datetime
import asyncio

from src.utils.logging.framework import SmartLogger, log_execution
from src.utils.thread_validation import ThreadValidator
from src.orchestrator.core.thread_context import set_thread_context, clear_thread_context
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from src.orchestrator.observers.direct_call_events import (
    emit_direct_response_event
)

logger = SmartLogger("orchestrator")


class OrchestratorA2AHandler:
    """A2A handler that uses the main orchestrator (ReAct agent with direct response capability)."""
    
    def __init__(self):
        """Initialize the A2A handler."""
        self.active_tasks = {}
        self._graph = None
        self._checkpointer = None
        self._initialize_checkpointer()
    
    def _initialize_checkpointer(self):
        """Initialize the checkpointer for interrupt support."""
        # Use MemorySaver for in-memory checkpointing
        from langgraph.checkpoint.memory import MemorySaver
        self._checkpointer = MemorySaver()
        logger.info("checkpointer_initialized",
                   type="MemorySaver")
    
    def _ensure_graph_initialized(self) -> Any:
        """Ensure the orchestrator graph is initialized (thread-safe)."""
        if self._graph is None:
            # Use threading lock instead of async lock
            import threading
            if not hasattr(self, '_sync_lock'):
                self._sync_lock = threading.Lock()
            
            with self._sync_lock:
                # Double-check pattern
                if self._graph is None:
                    logger.info("orchestrator_graph_initializing")
                    
                    # Get the checkpointer
                    from langgraph.prebuilt import create_react_agent
                    from src.utils.prompt_templates import create_react_orchestrator_prompt, ContextInjectorOrchestrator
                    from src.orchestrator.core.agent_registry import AgentRegistry
                    from src.orchestrator.tools.agent_caller_tools import (
                        SalesforceAgentTool, 
                        JiraAgentTool, 
                        ServiceNowAgentTool, 
                        AgentRegistryTool
                    )
                    from src.orchestrator.tools.web_search import WebSearchTool
                    from src.orchestrator.tools.human_input import HumanInputTool
                    from src.orchestrator.tools.task_agent import TaskAgentTool
                    from src.utils.cost_tracking_decorator import create_cost_tracking_azure_openai
                    import os
                    
                    # Create agent registry
                    agent_registry = AgentRegistry()
                    
                    # Create tools list
                    tools = [
                        SalesforceAgentTool(agent_registry),
                        JiraAgentTool(agent_registry),
                        ServiceNowAgentTool(agent_registry),
                        AgentRegistryTool(agent_registry),
                        WebSearchTool(),
                        HumanInputTool(),
                        TaskAgentTool()
                    ]
                    
                    # Create LLM
                    llm = create_cost_tracking_azure_openai(
                        component="main_orchestrator",
                        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                        azure_deployment=os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4o-mini"),
                        openai_api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01"),
                        openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
                        temperature=0.1,
                        max_tokens=4000,
                    )
                    
                    # Get prompt
                    prompt = create_react_orchestrator_prompt()
                    
                    # Prepare context
                    registry_stats = agent_registry.get_registry_stats()
                    agent_context = f"""AVAILABLE SPECIALIZED AGENTS:
{', '.join(registry_stats['available_capabilities']) if registry_stats['available_capabilities'] else 'None currently available'}

ORCHESTRATOR TOOLS:
1. salesforce_agent: For Salesforce CRM operations
2. jira_agent: For project management
3. servicenow_agent: For incident management
4. agent_registry: To check agent status
5. web_search: Search the web
6. task_agent: Execute complex multi-step tasks
7. human_input: Request human clarification"""
                    
                    context_dict = ContextInjectorOrchestrator.prepare_context(
                        summary=None,
                        memory=None,
                        agent_context=agent_context
                    )
                    
                    # Format prompt
                    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
                    formatted_messages = prompt.format_messages(
                        messages=[],
                        **context_dict
                    )
                    system_message_content = formatted_messages[0].content
                    
                    formatted_prompt = ChatPromptTemplate.from_messages([
                        ("system", system_message_content),
                        MessagesPlaceholder(variable_name="messages")
                    ])
                    
                    # Log the system prompt to verify task_agent is included
                    logger.info("orchestrator_system_prompt",
                               prompt_length=len(system_message_content),
                               has_task_agent="task_agent" in system_message_content,
                               task_agent_mentions=system_message_content.count("task_agent"))
                    
                    # Create ReAct agent WITH checkpointer
                    # Tools will access state via InjectedState annotation
                    from src.orchestrator.core.state import OrchestratorState
                    # create_react_agent returns a compiled graph directly
                    self._graph = create_react_agent(
                        llm, 
                        tools, 
                        prompt=formatted_prompt,
                        checkpointer=self._checkpointer,  # Enable interrupt support
                        state_schema=OrchestratorState  # Use our extended state schema
                    )
                    
                    # Store tools reference
                    self._graph._tools = tools
                    
                    logger.info("orchestrator_graph_initialized",
                               has_checkpointer=self._checkpointer is not None)
                    
        return self._graph
    
    @property
    def graph(self):
        """Property to access the graph synchronously for WebSocket handler."""
        if self._graph is None:
            # This is not ideal but needed for backward compatibility
            # The WebSocket handler expects synchronous access
            logger.warning("graph_accessed_before_initialization")
        return self._graph
    
    @log_execution("orchestrator", "process_task", include_args=False, include_result=False)
    async def process_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process A2A task using main orchestrator."""
        task_id = "unknown"
        
        try:
            # Extract task data
            task_data = params.get("task", params)
            task_id = task_data.get("id", task_data.get("task_id", str(uuid.uuid4())[:8]))
            instruction = task_data.get("instruction", "")
            context = task_data.get("context", {})
            
            logger.info("main_orchestrator_processing",
                       task_id=task_id,
                       instruction=instruction[:100],
                       has_context=bool(context),
                       context_keys=list(context.keys()) if context else [],
                       thread_id_in_context=context.get("thread_id") if context else None)
            
            # Validate thread context
            is_valid, error_msg = ThreadValidator.validate_thread_context(context) if context else (False, "No context provided")
            if not is_valid:
                logger.warning("invalid_thread_context", 
                             task_id=task_id,
                             error=error_msg,
                             context=context)
            
            # Track this task - use validated thread_id or generate fallback
            thread_id = ThreadValidator.ensure_thread_id(context.get("thread_id") if context else None, source='api')
            user_id = context.get("user_id", "default_user")
            
            logger.info("thread_id_resolution",
                       task_id=task_id,
                       resolved_thread_id=thread_id,
                       from_context=context.get("thread_id") is not None)
            
            self.active_tasks[task_id] = {
                "thread_id": thread_id,
                "instruction": instruction,
                "status": "processing",
                "started_at": datetime.now().isoformat()
            }
            
            # Ensure graph is initialized
            graph = self._ensure_graph_initialized()
            
            # Configuration for checkpointing
            config = {
                "configurable": {
                    "thread_id": thread_id
                }
            }
            
            # Load existing state if available
            existing_state = None
            pending_tool_call_id = None
            try:
                existing_state = graph.get_state(config)
                if existing_state and existing_state.values:
                    logger.info("loaded_existing_state",
                               thread_id=thread_id,
                               message_count=len(existing_state.values.get("messages", [])))
                    
                    # Check if the last message has a pending tool call (interrupt case)
                    messages = existing_state.values.get("messages", [])
                    if messages:
                        last_msg = messages[-1]
                        # Check if last message is an AIMessage with tool_calls
                        if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                            # Check if there's a human_input tool call
                            for tool_call in last_msg.tool_calls:
                                if tool_call.get("name") == "human_input":
                                    pending_tool_call_id = tool_call.get("id")
                                    logger.info("found_pending_human_input_tool_call",
                                               thread_id=thread_id,
                                               tool_call_id=pending_tool_call_id)
                                    break
            except Exception as e:
                logger.warning("failed_to_load_state",
                              thread_id=thread_id,
                              error=str(e))
            
            # Prepare messages based on whether we're resuming from interrupt
            if pending_tool_call_id and existing_state and existing_state.values:
                # This is a response to a human_input interrupt
                # Add the user's response as a ToolMessage
                messages = existing_state.values["messages"]
                tool_message = ToolMessage(
                    content=instruction,
                    tool_call_id=pending_tool_call_id
                )
                messages.append(tool_message)
                
                logger.info("added_tool_message_for_human_input",
                           thread_id=thread_id,
                           tool_call_id=pending_tool_call_id,
                           response_preview=instruction[:100])
            elif existing_state and existing_state.values and "messages" in existing_state.values:
                # Continue the conversation normally
                messages = existing_state.values["messages"]
                messages.append(HumanMessage(content=instruction))
            else:
                # Start fresh conversation
                messages = [HumanMessage(content=instruction)]
            
            # Prepare input for graph
            graph_input = {
                "messages": messages,
                "thread_id": thread_id,
                "user_id": user_id,
                "task_id": task_id
            }
            
            logger.info("invoking_graph",
                       thread_id=thread_id,
                       has_checkpointer=self._checkpointer is not None,
                       is_tool_response=pending_tool_call_id is not None)
            
            # Log instruction analysis for debugging tool selection
            if instruction:
                logger.info("instruction_analysis_for_tool_selection",
                           task_id=task_id,
                           instruction_preview=instruction[:100],
                           has_onboard="onboard" in instruction.lower(),
                           has_then="then" in instruction.lower(),
                           has_and_then="and then" in instruction.lower(),
                           has_create_case="create a case" in instruction.lower() or "need a case" in instruction.lower(),
                           has_create_company="create a company" in instruction.lower(),
                           has_create_project="create a project" in instruction.lower() or "project in jira" in instruction.lower(),
                           systems_mentioned=[sys for sys in ["salesforce", "servicenow", "jira"] if sys in instruction.lower()],
                           multi_step_indicators=sum([
                               "then" in instruction.lower(),
                               "and then" in instruction.lower(),
                               instruction.lower().count("create") > 1,
                               len([sys for sys in ["salesforce", "servicenow", "jira"] if sys in instruction.lower()]) > 1
                           ]))
            
            # Set thread context for tools to access
            set_thread_context(thread_id=thread_id, user_id=user_id, task_id=task_id)
            
            try:
                # Invoke the graph
                result = await graph.ainvoke(graph_input, config)
            finally:
                # Clear thread context after execution
                clear_thread_context()
            
            # Extract response from messages
            response_messages = result.get("messages", [])
            
            # Check if this was a direct response or tool-mediated response
            was_direct_response = True
            if len(response_messages) >= 2:
                # Check if there are any tool messages in the conversation
                for msg in response_messages:
                    if isinstance(msg, ToolMessage) or (hasattr(msg, 'type') and msg.type == 'tool'):
                        was_direct_response = False
                        break
                    # Also check for tool calls in AI messages
                    if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                        was_direct_response = False
                        break
            
            # Check if the last message is a human input tool call (interrupt case)
            human_input_interrupt = False
            interrupt_message = ""
            
            if response_messages:
                last_msg = response_messages[-1]
                # Check if the last message has tool calls for human_input
                if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                    for tool_call in last_msg.tool_calls:
                        if tool_call.get("name") == "human_input":
                            human_input_interrupt = True
                            # Extract the message from the tool call arguments
                            if "args" in tool_call and "full_message" in tool_call["args"]:
                                interrupt_message = tool_call["args"]["full_message"]
                            break
            
            if human_input_interrupt and interrupt_message:
                # This is a human input interrupt - return it properly
                logger.info("human_input_interrupt_detected",
                           thread_id=thread_id,
                           message_preview=interrupt_message[:100])
                
                # Record the interrupt
                from src.orchestrator.observers.interrupt_observer import get_interrupt_observer
                interrupt_observer = get_interrupt_observer()
                interrupt_observer.record_interrupt(
                    thread_id=thread_id,
                    interrupt_type="human_input",
                    reason=interrupt_message,
                    current_plan=[],  # ReAct doesn't have explicit plans
                    state=graph_input,
                    interrupt_payload=None  # This path doesn't have structured payload
                )
                
                # Mark task as interrupted
                if task_id in self.active_tasks:
                    self.active_tasks[task_id]["status"] = "interrupted"
                    self.active_tasks[task_id]["interrupt_reason"] = interrupt_message
                    self.active_tasks[task_id]["interrupted_at"] = datetime.now().isoformat()
                
                # Return interrupt response
                return {
                    "artifacts": [{
                        "id": f"orchestrator-interrupt-{task_id}",
                        "task_id": task_id,
                        "content": interrupt_message,
                        "content_type": "text/plain"
                    }],
                    "status": "interrupted",
                    "metadata": {
                        "task_id": task_id,
                        "thread_id": thread_id,
                        "user_id": user_id,
                        "interrupt_type": "human_input",
                        "interrupt_reason": interrupt_message
                    },
                    "error": None
                }
            
            # Normal response processing
            if response_messages and hasattr(response_messages[-1], 'content'):
                response = response_messages[-1].content
            else:
                response = "I completed the task but couldn't generate a response."
            
            # Emit appropriate event based on response type
            if was_direct_response:
                # This was a direct response without tool usage
                emit_direct_response_event(
                    response_type="conversational",
                    response_content=response,
                    confidence=1.0  # ReAct agent is confident enough to respond directly
                )
            
            # Mark task as complete
            self.active_tasks[task_id]["status"] = "completed"
            self.active_tasks[task_id]["completed_at"] = datetime.now().isoformat()
            
            logger.info("graph_invocation_complete",
                       thread_id=thread_id,
                       response_length=len(response),
                       was_direct_response=was_direct_response)
            
            # Return response
            return {
                "artifacts": [{
                    "id": f"orchestrator-response-{task_id}",
                    "task_id": task_id,
                    "content": response,
                    "content_type": "text/plain"
                }],
                "status": "success",
                "metadata": {
                    "task_id": task_id,
                    "thread_id": thread_id,
                    "user_id": user_id
                },
                "error": None
            }
            
        except Exception as e:
            # Check if this is a GraphInterrupt (expected behavior for human input)
            from langgraph.errors import GraphInterrupt
            if isinstance(e, GraphInterrupt):
                # This is expected - an agent is requesting human input
                logger.info("orchestrator_interrupted",
                           task_id=task_id,
                           thread_id=thread_id,
                           interrupt_value=str(e.args[0]) if e.args else "",
                           error_type=type(e).__name__)
                
                # Record the interrupt
                from src.orchestrator.observers.interrupt_observer import get_interrupt_observer
                interrupt_observer = get_interrupt_observer()
                
                # Determine interrupt type
                interrupt_type = "human_input"
                interrupt_reason = "Agent requested clarification"
                interrupt_payload = None
                
                # Extract the actual interrupt value from the GraphInterrupt
                if hasattr(e, 'args') and e.args:
                    # GraphInterrupt wraps the payload, we need to extract it
                    arg = e.args[0] if e.args else None
                    
                    # Simple approach - just convert to string
                    interrupt_reason = str(arg) if arg else interrupt_reason
                    
                    logger.info("extracted_interrupt_message",
                               message_length=len(interrupt_reason),
                               message_preview=interrupt_reason[:100])
                
                # Record interrupt with observer
                interrupt_observer.record_interrupt(
                    thread_id=thread_id,
                    interrupt_type=interrupt_type,
                    reason=interrupt_reason,
                    current_plan=[],  # ReAct doesn't have explicit plans
                    state=graph_input,
                    interrupt_payload=interrupt_payload
                )
                
                # Mark task as interrupted (not failed)
                if task_id in self.active_tasks:
                    self.active_tasks[task_id]["status"] = "interrupted"
                    self.active_tasks[task_id]["interrupt_reason"] = interrupt_reason
                    self.active_tasks[task_id]["interrupted_at"] = datetime.now().isoformat()
                
                # Return success with interrupt information
                metadata = {
                    "task_id": task_id,
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "interrupt_type": interrupt_type,
                    "interrupt_reason": interrupt_reason
                }
                
                # Include the full interrupt payload if available
                if interrupt_payload:
                    metadata["interrupt_payload"] = interrupt_payload
                    # Also include key fields at top level for easy access
                    if "question" in interrupt_payload:
                        metadata["question"] = interrupt_payload["question"]
                    if "options" in interrupt_payload:
                        metadata["options"] = interrupt_payload["options"]
                    if "context" in interrupt_payload:
                        metadata["context"] = interrupt_payload["context"]
                
                return {
                    "artifacts": [{
                        "id": f"orchestrator-interrupt-{task_id}",
                        "task_id": task_id,
                        "content": interrupt_reason,
                        "content_type": "text/plain"
                    }],
                    "status": "interrupted",
                    "metadata": metadata,
                    "error": None
                }
            else:
                # This is an actual error
                logger.error("orchestrator_error",
                            task_id=task_id,
                            error=str(e),
                            error_type=type(e).__name__)
                
                # Mark task as failed
                if task_id in self.active_tasks:
                    self.active_tasks[task_id]["status"] = "failed"
                    self.active_tasks[task_id]["error"] = str(e)
            
            return {
                "artifacts": [{
                    "id": f"orchestrator-error-{task_id}",
                    "task_id": task_id,
                    "content": f"Error: {str(e)}",
                    "content_type": "text/plain"
                }],
                "status": "failed",
                "metadata": {
                    "task_id": task_id,
                    "error": str(e)
                },
                "error": str(e)
            }
    
    @log_execution("orchestrator", "get_agent_card", include_args=True, include_result=True)
    async def get_agent_card(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return orchestrator agent card."""
        return {
            "name": "orchestrator",
            "version": "2.0.0",
            "description": "AI orchestrator with direct response capability and task delegation",
            "capabilities": [
                "conversational_ai",
                "direct_response",
                "task_planning",
                "task_execution",
                "multi_agent_coordination"
            ],
            "endpoints": {
                "process_task": "/a2a",
                "agent_card": "/a2a/agent-card"
            },
            "communication_modes": ["sync"],
            "metadata": {
                "framework": "langgraph-react-with-task-delegation",
                "active_tasks": len(self.active_tasks),
                "architecture": "main_orchestrator"
            }
        }
    
    async def get_task_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get status of a specific task."""
        task_id = params.get("task_id")
        
        if not task_id or task_id not in self.active_tasks:
            return {
                "success": False,
                "data": {},
                "message": "Task not found"
            }
        
        return {
            "success": True,
            "data": self.active_tasks[task_id],
            "message": "Task found"
        }
    
    async def interrupt_task(self, thread_id: str, reason: str = "user_interrupt") -> Dict[str, Any]:
        """Handle interrupt request for a task.
        
        Note: With the ReAct agent architecture, interrupts are handled differently.
        The actual interruption happens when HumanInputTool is called.
        """
        try:
            logger.info("interrupt_task_requested",
                       thread_id=thread_id,
                       reason=reason)
            
            # Find task by thread_id
            task_id = None
            for tid, task_info in self.active_tasks.items():
                if task_info.get("thread_id") == thread_id:
                    task_id = tid
                    break
            
            if not task_id:
                logger.warning("interrupt_task_not_found",
                              thread_id=thread_id)
                return {
                    "success": False,
                    "message": f"No active task found for thread {thread_id}"
                }
            
            # Update task status
            self.active_tasks[task_id]["status"] = "interrupted"
            self.active_tasks[task_id]["interrupt_reason"] = reason
            
            # With ReAct agent, we can't directly interrupt
            # The interrupt will happen when HumanInputTool is called
            logger.info("interrupt_task_marked",
                       task_id=task_id,
                       thread_id=thread_id)
            
            return {
                "success": True,
                "message": "Task marked for interrupt",
                "task_id": task_id,
                "thread_id": thread_id
            }
            
        except Exception as e:
            logger.error("interrupt_task_error",
                        thread_id=thread_id,
                        error=str(e))
            return {
                "success": False,
                "message": f"Failed to interrupt task: {str(e)}"
            }
    
    async def forward_events(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle forwarded events from agents.
        
        Agents send batches of SSE events to be forwarded to web clients.
        This enables cross-process event visibility.
        
        Args:
            params: Contains 'events' list and 'agent_name'
            
        Returns:
            Status response with event count
        """
        try:
            events = params.get("events", [])
            agent_name = params.get("agent_name", "unknown")
            batch_id = params.get("batch_id", "unknown")
            
            logger.info("forwarded_events_received",
                       agent_name=agent_name,
                       event_count=len(events),
                       batch_id=batch_id)
            
            # Get SSE observer
            from src.orchestrator.observers import get_observer_registry
            registry = get_observer_registry()
            sse_observer = registry.get_observer("SSEObserver")
            
            if sse_observer:
                # Forward each event to SSE clients
                for event in events:
                    # Ensure event has proper structure
                    if "event" in event and "data" in event:
                        # Add agent context if not present
                        if "agent_name" not in event["data"]:
                            event["data"]["agent_name"] = agent_name
                        
                        sse_observer.notify(event)
                    else:
                        logger.warning("malformed_forwarded_event",
                                     agent_name=agent_name,
                                     event=event)
            else:
                logger.warning("sse_observer_not_found",
                             agent_name=agent_name)
            
            return {
                "success": True,
                "status": "accepted",
                "count": len(events),
                "batch_id": batch_id
            }
            
        except Exception as e:
            logger.error("forward_events_failed",
                        error=str(e),
                        agent_name=params.get("agent_name", "unknown"))
            
            return {
                "success": False,
                "status": "error",
                "message": f"Failed to forward events: {str(e)}"
            }