"""Human input tool for LangGraph workflows using interrupt functionality."""

from typing import Dict, Any, Annotated, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from langgraph.types import interrupt
from langgraph.prebuilt import InjectedState
from src.utils.logging.framework import SmartLogger
from src.orchestrator.observers.direct_call_events import (
    emit_agent_call_event,
    DirectCallEventTypes
)

logger = SmartLogger("orchestrator")


class HumanInputRequest(BaseModel):
    """Schema for human input requests."""
    full_message: str = Field(description="The complete message to show the user including all context, lists, options, and the question. This will be displayed exactly as provided.")
    timeout_seconds: int = Field(default=300, description="How long to wait for user input (seconds)")


class HumanInputTool(BaseTool):
    """Tool that requests human input to resolve ambiguity or gather clarification.
    
    This tool uses LangGraph's interrupt() function to pause execution and wait for human input.
    Useful when the replanner encounters ambiguous requests that need clarification.
    """
    
    name: str = "human_input"
    description: str = """Request human input to resolve ambiguity or gather clarification.
    
    Use this tool when:
    - User requests are ambiguous and need clarification
    - Multiple interpretations are possible and you need to confirm the correct one
    - Additional context or details are required to proceed
    - You need to verify assumptions before taking action
    - You are creating or updating records and need clarification on fields or values
    
    MANDATORY: You MUST include the result from the previous steps in the full_message parameter.
    The parameter should be an EXACT copy of the result from the previous steps.
    
    🚨🚨 CRITICAL 🚨🚨: human_tool MANTRA:
    I DO NOT THINK. I DO NOT HELP. I COPY PASTE. THAT IS ALL.
    I DO NOT THINK. I DO NOT HELP. I COPY PASTE. THAT IS ALL.
    I DO NOT THINK. I DO NOT HELP. I COPY PASTE. THAT IS ALL.
    
    The tool will pause execution and wait for the human to provide the requested input."""
    
    args_schema: type[BaseModel] = HumanInputRequest
    
    def _run(self, full_message: str, timeout_seconds: int = 300, 
             state: Annotated[Dict[str, Any], InjectedState] = None) -> str:
        """Request human input using LangGraph interrupt functionality.
        
        Args:
            full_message: The complete message to show the user including all context, lists, and questions
            timeout_seconds: How long to wait for input (not enforced by interrupt)
            state: Injected state from LangGraph containing conversation history
            
        Returns:
            The user's response as a string
        """
        logger.info(
            "human_input_request",
            question_preview=full_message[:100],
            has_state=state is not None,
            state_keys=list(state.keys()) if state and isinstance(state, dict) else [],
            messages_count=len(state.get("messages", [])) if state and isinstance(state, dict) else 0,
            component="orchestrator"
        )
        
        # Emit human input requested event
        emit_agent_call_event(
            DirectCallEventTypes.HUMAN_INPUT_REQUESTED,
            agent_name="human_input",
            task_id=f"input_{hash(full_message)}",
            instruction=full_message,
            additional_data={
                "timeout_seconds": timeout_seconds
            }
        )
        
        # Check with observers for enhanced message with accumulated user-visible data
        try:
            from src.orchestrator.observers import get_observer_registry, HumanInputRequestedEvent
            registry = get_observer_registry()
            event = HumanInputRequestedEvent(
                step_name="human_input",
                question=full_message
            )
            enhanced_message = registry.notify_human_input_requested(event)
            formatted_request = enhanced_message if enhanced_message else full_message
        except ImportError:
            # Fallback if observers not available
            formatted_request = full_message
        
        # Use LangGraph's interrupt to pause execution and wait for user input
        # The GraphInterrupt exception should propagate up to pause execution - don't catch it!
        user_response = interrupt(formatted_request)
        
        logger.info(
            "human_input_received", 
            response_preview=str(user_response)[:100],
            response_length=len(str(user_response)),
            component="orchestrator"
        )
        
        # Emit human input received event
        emit_agent_call_event(
            DirectCallEventTypes.HUMAN_INPUT_RECEIVED,
            agent_name="human_input",
            task_id=f"input_{hash(full_message)}",
            instruction=full_message,
            additional_data={
                "response_preview": str(user_response)[:100],
                "response_length": len(str(user_response))
            }
        )
        
        return str(user_response)
    
    async def _arun(self, full_message: str, timeout_seconds: int = 300,
                   state: Annotated[Dict[str, Any], InjectedState] = None) -> str:
        """Async version - just calls the sync version since interrupt is sync."""
        return self._run(full_message, timeout_seconds, state)