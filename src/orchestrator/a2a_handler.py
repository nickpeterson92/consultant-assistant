"""A2A handler for the orchestrator agent."""

import uuid
from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage

from src.utils.logging import get_logger
from src.utils.config import get_conversation_config, get_llm_config
from src.utils.agents.prompts import orchestrator_a2a_sys_msg

logger = get_logger("orchestrator")


class OrchestratorA2AHandler:
    """Handles A2A protocol requests for the Orchestrator agent"""
    
    def __init__(self, graph, agent_registry):
        self.graph = graph
        self.agent_registry = agent_registry
        
    async def process_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process A2A task using the orchestrator graph"""
        try:
            # A2A protocol wraps task in "task" key
            task_data = params.get("task", params)  # Support both wrapped and unwrapped
            task_id = task_data.get("id", task_data.get("task_id", "unknown"))
            instruction = task_data.get("instruction", "")
            context = task_data.get("context", {})
            
            # Log task start
            logger.info("orchestrator_a2a_task_start",
                component="orchestrator",
                operation="process_a2a_task",
                task_id=task_id,
                instruction_preview=instruction[:100] if instruction else "",
                instruction_length=len(instruction) if instruction else 0,
                context_keys=list(context.keys()) if context else [],
                context_size=len(str(context)) if context else 0,
                source=context.get("source", "unknown")
            )
            
            # Get configuration
            conv_config = get_conversation_config()
            llm_config = get_llm_config()
            
            # Create thread ID for this task - use from context if provided
            thread_id = context.get("thread_id", f"a2a-{task_id}-{str(uuid.uuid4())[:8]}")
            
            # Debug logging
            logger.info("thread_id_debug",
                component="orchestrator",
                operation="process_a2a_task",
                context_thread_id=context.get("thread_id"),
                final_thread_id=thread_id,
                task_id=task_id
            )
            
            # Configuration for the graph
            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "user_id": context.get("user_id", conv_config.default_user_id)
                },
                "recursion_limit": llm_config.recursion_limit
            }
            
            # Get agent registry stats for context
            stats = self.agent_registry.get_registry_stats()
            
            # Check if this is an interactive CLI session or a true A2A task
            is_interactive_cli = context.get("source") == "cli_client"
            
            if is_interactive_cli:
                # Use the regular orchestrator system message for interactive sessions
                from src.orchestrator.llm_handler import get_orchestrator_system_message
                
                # Create a minimal state for system message generation
                state = {
                    "summary": "No summary available",
                    "memory": {},
                    "active_agents": []
                }
                
                system_message_content = get_orchestrator_system_message(state, self.agent_registry)
                
                logger.info("using_interactive_system_message",
                    component="orchestrator",
                    operation="process_a2a_task",
                    task_id=task_id,
                    mode="interactive_cli"
                )
            else:
                # Use A2A-specific message for true A2A tasks
                system_message_content = orchestrator_a2a_sys_msg(
                    task_context={"task_id": task_id, "instruction": instruction},
                    external_context=context,
                    agent_stats=stats
                )
                
                logger.info("using_a2a_system_message",
                    component="orchestrator",
                    operation="process_a2a_task",
                    task_id=task_id,
                    mode="single_task"
                )
            
            # Check if we have existing state for this thread
            existing_state = None
            try:
                # Get the current state snapshot
                existing_state = await self.graph.aget_state(config)
                if existing_state and existing_state.values:
                    logger.info("existing_state_found",
                        component="orchestrator",
                        operation="process_a2a_task",
                        thread_id=thread_id,
                        message_count=len(existing_state.values.get("messages", [])),
                        has_memory=bool(existing_state.values.get("memory"))
                    )
            except Exception as e:
                logger.info("get_state_error",
                    component="orchestrator",
                    operation="process_a2a_task",
                    thread_id=thread_id,
                    error=str(e),
                    error_type=type(e).__name__
                )
            
            if existing_state and existing_state.values and existing_state.values.get("messages"):
                # Continue existing conversation
                initial_state = {
                    "messages": [HumanMessage(content=instruction)],
                    "background_operations": [],
                    "background_results": {}
                }
            else:
                # Start new conversation
                initial_state = {
                    "messages": [
                        SystemMessage(content=system_message_content),
                        HumanMessage(content=instruction)
                    ],
                    "background_operations": [],
                    "background_results": {}
                }
            
            # Execute graph
            result = await self.graph.ainvoke(initial_state, config)
            
            # Debug the result structure
            logger.info("graph_invoke_result",
                component="orchestrator",
                operation="process_a2a_task",
                task_id=task_id,
                result_keys=list(result.keys()) if isinstance(result, dict) else "not_dict",
                message_count=len(result.get("messages", [])) if isinstance(result, dict) else 0,
                has_memory="memory" in result if isinstance(result, dict) else False
            )
            
            # Extract response content
            messages = result.get("messages", [])
            response_content = "Task completed successfully"
            
            # Workflow interrupts are now handled by LangGraph's native interrupt functionality
            
            if messages:
                # Check for workflow tool messages first
                for msg in reversed(messages):
                    if hasattr(msg, 'name') and msg.name == 'workflow_agent' and hasattr(msg, 'content'):
                        logger.info("found_workflow_tool_message",
                            component="orchestrator",
                            operation="process_a2a_task",
                            content_preview=msg.content[:100]
                        )
                        response_content = msg.content
                        break
                else:
                    # If no workflow tool message, find the last AI message
                    for msg in reversed(messages):
                        if hasattr(msg, 'content') and msg.content and not hasattr(msg, 'tool_calls'):
                            response_content = msg.content
                            break
            
            # Log tool calls found in messages
            for msg in messages:
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        # Handle both dict and object access patterns
                        if isinstance(tool_call, dict):
                            tool_name = tool_call.get("name", "unknown")
                            tool_args = tool_call.get("args", {})
                        else:
                            tool_name = getattr(tool_call, "name", "unknown")
                            tool_args = getattr(tool_call, "args", {})
                        
                        logger.info("tool_call",
                            component="orchestrator",
                            task_id=task_id,
                            tool_name=tool_name,
                            tool_args=tool_args
                        )
            
            # Log task completion
            logger.info("orchestrator_a2a_task_complete",
                component="orchestrator",
                operation="process_a2a_task",
                task_id=task_id,
                success=True,
                response_preview=response_content[:200]
            )
            
            # Return response in standard format
            response = {
                "artifacts": [{
                    "id": f"orchestrator-response-{task_id}",
                    "task_id": task_id,
                    "content": response_content,
                    "content_type": "text/plain"
                }],
                "status": "completed"
            }
            
            # Workflow state is handled by LangGraph checkpointer
            
            return response
            
        except Exception as e:
            error_msg = str(e)
            # Check for specific error types
            if "GraphRecursionError" in type(e).__name__ or "recursion limit" in error_msg.lower():
                error_msg = "Task complexity exceeded maximum iterations. Please try breaking down the request into smaller tasks."
            elif "GRAPH_RECURSION_LIMIT" in error_msg:
                error_msg = "Too many tool calls required. Please simplify your request."
                
            logger.error("orchestrator_a2a_task_error",
                component="orchestrator",
                operation="process_a2a_task",
                task_id=task_id,
                error=str(e),
                error_type=type(e).__name__
            )
            
            return {
                "artifacts": [{
                    "id": f"orchestrator-error-{task_id}",
                    "task_id": task_id,
                    "content": f"Error processing orchestrator request: {error_msg}",
                    "content_type": "text/plain"
                }],
                "status": "failed",
                "error": error_msg
            }
    
    async def get_agent_card(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return the Orchestrator agent card with current agent status"""
        # Get fresh stats to ensure we have the latest state
        stats = self.agent_registry.get_registry_stats()
        
        # Get capabilities from all registered agents
        all_capabilities = []
        capabilities_by_agent = {}
        online_agent_names = []
        
        # Get detailed agent info for better metadata
        for agent in self.agent_registry.list_agents():
            logger.debug(f"Checking agent {agent.name}: status={agent.status}, has_card={agent.agent_card is not None}")
            if agent.status == "online":
                agent_caps = agent.agent_card.capabilities
                capabilities_by_agent[agent.name] = agent_caps
                all_capabilities.extend(agent_caps)
                online_agent_names.append(agent.name)
        
        # Add orchestrator-specific capabilities
        orchestrator_capabilities = [
            "orchestration",
            "task_routing", 
            "multi_agent_coordination",
            "context_management",
            "conversation_memory",
            "web_search"
        ]
        all_capabilities.extend(orchestrator_capabilities)
        capabilities_by_agent["orchestrator"] = orchestrator_capabilities
        
        # Log the current state for debugging
        logger.info("agent_card_requested",
            component="orchestrator",
            operation="get_agent_card",
            total_agents=stats['total_agents'],
            online_agents=stats['online_agents'],
            online_agent_names=online_agent_names
        )
        
        return {
            "name": "orchestrator",
            "version": "1.0.0",
            "description": "Multi-agent orchestrator that coordinates between specialized agents for complex tasks",
            "capabilities": list(set(all_capabilities)),  # Deduplicate
            "endpoints": {
                "process_task": "/a2a",
                "agent_card": "/a2a/agent-card"
            },
            "communication_modes": ["sync", "streaming"],
            "metadata": {
                "framework": "langgraph",
                "registered_agents": stats['total_agents'],
                "online_agents": stats['online_agents'],
                "offline_agents": stats['offline_agents'],
                "memory_type": "sqlite_with_background_tasks",
                "capabilities_by_agent": capabilities_by_agent,
                "online_agent_names": online_agent_names
            }
        }