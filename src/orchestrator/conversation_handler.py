"""Clean conversation handler for pure plan-and-execute orchestrator."""

from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime
import asyncio

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.runnables import RunnableConfig

from src.orchestrator.plan_execute_state import PlanExecuteState, create_initial_state
from src.utils.logging.framework import SmartLogger

logger = SmartLogger("orchestrator")


class CleanConversationHandler:
    """Clean conversation handler that delegates to pure plan-and-execute graph."""
    
    def __init__(self, plan_execute_graph):
        """Initialize with a plan-execute graph."""
        self.graph = plan_execute_graph
        self.current_thread_id = None
        self.current_config = None
    
    async def handle_message(self, 
                           user_input: str, 
                           thread_id: str,
                           config: Optional[RunnableConfig] = None) -> List[BaseMessage]:
        """Handle a user message through the plan-execute graph."""
        
        self.current_thread_id = thread_id
        self.current_config = config or {"configurable": {"thread_id": thread_id}}
        
        try:
            # Create user message
            user_message = HumanMessage(content=user_input)
            
            # Stream through the graph
            response_messages = []
            
            async for event in self.graph.graph.astream(
                {"messages": [user_message], "original_request": user_input},
                config=self.current_config
            ):
                # Process graph events
                if "messages" in event:
                    for message in event["messages"]:
                        if isinstance(message, (AIMessage, SystemMessage)):
                            response_messages.append(message)
                
                # Handle progress updates
                if "progress_state" in event:
                    progress_message = AIMessage(
                        content="",
                        additional_kwargs={"progress_update": event["progress_state"]}
                    )
                    response_messages.append(progress_message)
            
            return response_messages
            
        except Exception as e:
            logger.error("message_handling_error", error=str(e), thread_id=thread_id)
            return [AIMessage(content=f"Error processing message: {str(e)}")]
    
    async def handle_interrupt_resume(self, 
                                    user_input: str, 
                                    thread_id: str,
                                    config: Optional[RunnableConfig] = None) -> List[BaseMessage]:
        """Handle resuming from an interrupt."""
        
        self.current_thread_id = thread_id
        self.current_config = config or {"configurable": {"thread_id": thread_id}}
        
        try:
            from langgraph.types import Command
            
            # Resume with user input
            response_messages = []
            
            async for event in self.graph.graph.astream(
                Command(resume=user_input),
                config=self.current_config
            ):
                # Process graph events
                if "messages" in event:
                    for message in event["messages"]:
                        if isinstance(message, (AIMessage, SystemMessage)):
                            response_messages.append(message)
                
                # Handle progress updates
                if "progress_state" in event:
                    progress_message = AIMessage(
                        content="",
                        additional_kwargs={"progress_update": event["progress_state"]}
                    )
                    response_messages.append(progress_message)
            
            return response_messages
            
        except Exception as e:
            logger.error("interrupt_resume_error", error=str(e), thread_id=thread_id)
            return [AIMessage(content=f"Error resuming: {str(e)}")]
    
    def get_thread_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get current thread state."""
        try:
            config = {"configurable": {"thread_id": thread_id}}
            state = self.graph.graph.get_state(config)
            return state.values if state else None
        except Exception as e:
            logger.error("get_thread_state_error", error=str(e), thread_id=thread_id)
            return None
    
    def interrupt_thread(self, thread_id: str, reason: str = "user_interrupt"):
        """Interrupt a running thread."""
        try:
            config = {"configurable": {"thread_id": thread_id}}
            self.graph.graph.update_state(
                config, 
                {
                    "interrupted": True,
                    "interrupt_data": {
                        "interrupt_type": "user_escape",
                        "reason": reason,
                        "created_at": datetime.now().isoformat()
                    }
                }
            )
            logger.info("thread_interrupted", thread_id=thread_id, reason=reason)
        except Exception as e:
            logger.error("thread_interrupt_error", error=str(e), thread_id=thread_id)


def create_clean_conversation_handler(plan_execute_graph) -> CleanConversationHandler:
    """Factory function to create a clean conversation handler."""
    return CleanConversationHandler(plan_execute_graph)