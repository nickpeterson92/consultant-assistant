"""Enhanced human input tool with structured interrupt types and better error handling."""

from typing import Dict, Any, Annotated, Optional, List
from enum import Enum
from datetime import datetime
import re
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from langgraph.types import interrupt
from langgraph.prebuilt import InjectedState
from langgraph.errors import GraphInterrupt
from src.utils.logging.framework import SmartLogger
from src.orchestrator.observers.direct_call_events import (
    emit_agent_call_event,
    DirectCallEventTypes
)

logger = SmartLogger("orchestrator")


class InterruptType(Enum):
    """Types of human input interrupts for better UI/UX handling."""
    CLARIFICATION = "clarification"      # Agent needs clarification
    CONFIRMATION = "confirmation"        # Agent needs yes/no confirmation
    SELECTION = "selection"             # Agent needs user to select from options
    FREEFORM = "freeform"               # Agent needs open-ended input
    APPROVAL = "approval"               # Agent needs explicit approval to proceed


class HumanInputRequest(BaseModel):
    """Enhanced schema for human input requests with structured context."""
    
    interrupt_type: InterruptType = Field(
        default=InterruptType.CLARIFICATION,
        description="Type of interrupt to help UI render appropriately"
    )
    
    question: str = Field(
        description="The specific question to ask the user"
    )
    
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured context to help user understand the situation"
    )
    
    options: Optional[List[str]] = Field(
        default=None,
        description="For SELECTION type, list of valid options"
    )
    
    default_value: Optional[str] = Field(
        default=None,
        description="Default value if user doesn't respond (timeout not enforced by LangGraph)"
    )
    
    validation_regex: Optional[str] = Field(
        default=None,
        description="Regex pattern to validate user input"
    )
    
    timeout_seconds: int = Field(
        default=300,
        description="Timeout for user response (informational only)"
    )
    
    retry_on_invalid: bool = Field(
        default=True,
        description="Whether to retry on invalid input"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata for UI/logging"
    )
    
    state: Annotated[dict, InjectedState] = Field(
        description="Injected state from LangGraph for accessing conversation context"
    )


class ContextBuilder:
    """Builds enhanced context for human input requests."""
    
    def build(
        self,
        question: str,
        context: Dict[str, Any],
        state: Optional[Dict[str, Any]],
        interrupt_type: InterruptType
    ) -> Dict[str, Any]:
        """Build comprehensive context for the user."""
        
        enhanced_context = {
            "question": question,
            "interrupt_type": interrupt_type.value,
            "timestamp": datetime.now().isoformat(),
            **context
        }
        
        if state:
            # Add conversation history if available
            if "messages" in state:
                enhanced_context["recent_messages"] = self._get_recent_messages(
                    state["messages"], 
                    limit=5
                )
            
            # Add current plan status if available
            if "plan" in state:
                enhanced_context["current_plan"] = self._get_plan_summary(state)
            
            # Add past steps if available
            if "past_steps" in state:
                enhanced_context["completed_steps"] = self._get_completed_steps(state)
        
        return enhanced_context
    
    def _get_recent_messages(self, messages: List[Any], limit: int = 5) -> List[Dict[str, str]]:
        """Extract recent messages for context."""
        recent = []
        for msg in messages[-limit:]:
            if hasattr(msg, 'content') and hasattr(msg, 'type'):
                recent.append({
                    "type": getattr(msg, 'type', 'unknown'),
                    "content": str(msg.content)[:200]  # Truncate long messages
                })
        return recent
    
    def _get_plan_summary(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Get summary of current plan."""
        plan = state.get("plan", [])
        return {
            "total_steps": len(plan),
            "current_step": len(state.get("past_steps", [])),
            "remaining_steps": len(plan) - len(state.get("past_steps", []))
        }
    
    def _get_completed_steps(self, state: Dict[str, Any]) -> List[str]:
        """Get list of completed steps."""
        past_steps = state.get("past_steps", [])
        # Get last 3 completed steps
        return [str(step)[:100] for step in past_steps[-3:]]


class ResponseValidator:
    """Validates user responses based on interrupt type and constraints."""
    
    def validate(
        self,
        response: str,
        interrupt_type: InterruptType,
        options: Optional[List[str]] = None,
        validation_regex: Optional[str] = None
    ) -> str:
        """Validate and potentially transform user response."""
        
        if not response:
            raise ValueError("Empty response received")
        
        response = response.strip()
        
        # Type-specific validation
        if interrupt_type == InterruptType.SELECTION and options:
            if response not in options:
                # Try case-insensitive match first
                for option in options:
                    if option.lower() == response.lower():
                        return option
                
                # Try fuzzy matching
                matched = self._fuzzy_match(response, options)
                if matched:
                    return matched
                    
                raise ValueError(f"Invalid selection '{response}'. Must be one of: {', '.join(options)}")
        
        elif interrupt_type == InterruptType.CONFIRMATION:
            # Normalize yes/no responses
            return self._normalize_confirmation(response)
        
        elif interrupt_type == InterruptType.APPROVAL:
            # Strict approval validation
            return self._validate_approval(response)
        
        # Regex validation if provided
        if validation_regex:
            if not re.match(validation_regex, response):
                raise ValueError(f"Response does not match required format: {validation_regex}")
        
        return response
    
    def _fuzzy_match(self, response: str, options: List[str]) -> Optional[str]:
        """Simple fuzzy matching for options."""
        response_lower = response.lower()
        
        # Check if response starts with any option
        for option in options:
            if option.lower().startswith(response_lower) or response_lower.startswith(option.lower()):
                return option
        
        # Check if response is contained in any option
        for option in options:
            if response_lower in option.lower():
                return option
                
        return None
    
    def _normalize_confirmation(self, response: str) -> str:
        """Normalize yes/no responses."""
        response_lower = response.lower()
        
        yes_variants = ["yes", "y", "yeah", "yep", "sure", "ok", "okay", "confirm", "proceed", "approve"]
        no_variants = ["no", "n", "nope", "nah", "cancel", "abort", "stop", "deny", "reject"]
        
        if any(variant in response_lower for variant in yes_variants):
            return "yes"
        elif any(variant in response_lower for variant in no_variants):
            return "no"
        else:
            raise ValueError(f"Please respond with 'yes' or 'no'. Got: '{response}'")
    
    def _validate_approval(self, response: str) -> str:
        """Validate approval responses."""
        # For approval, we typically want exact matches
        if response.upper() == "APPROVE":
            return "APPROVE"
        elif response.upper() == "DENY":
            return "DENY"
        else:
            raise ValueError("Please respond with 'APPROVE' or 'DENY'")


class HumanInputTool(BaseTool):
    """Enhanced human input tool with structured interrupts and validation.
    
    This tool uses LangGraph's interrupt() function to pause execution and wait for human input.
    It provides structured interrupt types, validation, and error recovery.
    """
    
    name: str = "human_input"
    description: str = """Request human input with structured context and validation.
    
    Supports different interrupt types:
    - CLARIFICATION: When you need to clarify ambiguous instructions
    - CONFIRMATION: When you need user to confirm an action (yes/no)
    - SELECTION: When user needs to choose from provided options
    - FREEFORM: When you need open-ended input
    - APPROVAL: When you need explicit permission to proceed (APPROVE/DENY)
    
    Use the appropriate interrupt_type to help the UI render the best interface for the user.
    Always provide clear context about why you're asking and what information you need.
    
    MANDATORY: Include relevant context from previous steps and current state."""
    
    args_schema: type[BaseModel] = HumanInputRequest
    
    def __init__(self):
        super().__init__()
        self._context_builder = ContextBuilder()
        self._response_validator = ResponseValidator()
    
    def _run(
        self,
        interrupt_type: InterruptType = InterruptType.CLARIFICATION,
        question: str = "",
        context: Dict[str, Any] = None,
        options: List[str] = None,
        default_value: str = None,
        validation_regex: str = None,
        timeout_seconds: int = 300,
        retry_on_invalid: bool = True,
        metadata: Dict[str, Any] = None,
        state: Annotated[Dict[str, Any], InjectedState] = None
    ) -> str:
        """Request human input with enhanced context and validation.
        
        Args:
            interrupt_type: Type of interrupt for UI rendering
            question: The specific question to ask
            context: Additional context to help user understand
            options: For SELECTION type, list of valid options
            default_value: Default if no response (not enforced by LangGraph)
            validation_regex: Regex pattern to validate response
            timeout_seconds: Timeout hint for UI (not enforced)
            retry_on_invalid: Whether to retry on invalid input
            metadata: Additional metadata for UI/logging
            state: Injected state from LangGraph
            
        Returns:
            Validated user response as string
        """
        # Log the request
        logger.info(
            "human_input_request_enhanced",
            interrupt_type=interrupt_type.value,
            question_preview=question[:100],
            has_options=bool(options),
            has_validation=bool(validation_regex),
            has_default=bool(default_value),
            has_state=state is not None,
            component="orchestrator"
        )
        
        # Build enhanced context
        enhanced_context = self._context_builder.build(
            question=question,
            context=context or {},
            state=state,
            interrupt_type=interrupt_type
        )
        
        # Create interrupt payload
        interrupt_payload = {
            "type": "human_input",
            "interrupt_type": interrupt_type.value,
            "question": question,
            "context": enhanced_context,
            "options": options,
            "default_value": default_value,
            "timeout_seconds": timeout_seconds,
            "metadata": metadata or {},
            "thread_id": state.get("task_id") if state else None,
            "timestamp": datetime.now().isoformat()
        }
        
        # Emit request event
        emit_agent_call_event(
            DirectCallEventTypes.HUMAN_INPUT_REQUESTED,
            agent_name="human_input",
            task_id=interrupt_payload.get("thread_id", f"input_{hash(question)}"),
            instruction=question,
            additional_data={
                "interrupt_type": interrupt_type.value,
                "has_options": bool(options),
                "timeout_seconds": timeout_seconds
            }
        )
        
        # Record interrupt with observer
        self._record_interrupt(interrupt_payload, state)
        
        max_retries = 3 if retry_on_invalid else 1
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Execute interrupt with just the formatted message string
                response = interrupt(formatted_message)
                
                # Validate response
                validated_response = self._response_validator.validate(
                    response=str(response),
                    interrupt_type=interrupt_type,
                    options=options,
                    validation_regex=validation_regex
                )
                
                # Record successful response
                self._record_response(validated_response, interrupt_payload, state)
                
                # Emit success event
                emit_agent_call_event(
                    DirectCallEventTypes.HUMAN_INPUT_RECEIVED,
                    agent_name="human_input",
                    task_id=interrupt_payload.get("thread_id", f"input_{hash(question)}"),
                    instruction=question,
                    additional_data={
                        "response_preview": validated_response[:100],
                        "response_length": len(validated_response),
                        "attempts": attempt + 1
                    }
                )
                
                logger.info(
                    "human_input_received_enhanced",
                    interrupt_type=interrupt_type.value,
                    response_preview=validated_response[:100],
                    attempts=attempt + 1,
                    component="orchestrator"
                )
                
                return validated_response
                
            except GraphInterrupt:
                # This is expected - re-raise to let LangGraph handle
                raise
                
            except ValueError as e:
                last_error = e
                logger.warning(
                    "human_input_validation_error",
                    error=str(e),
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    component="orchestrator"
                )
                
                if attempt < max_retries - 1:
                    # Update payload for retry with error context
                    interrupt_payload["context"]["previous_error"] = str(e)
                    interrupt_payload["context"]["attempt"] = attempt + 2
                    interrupt_payload["question"] = f"Invalid response: {e}\n\nPlease try again: {question}"
                    
        # If we get here, all retries failed
        if default_value and last_error:
            logger.info(
                "human_input_using_default",
                default_value=default_value,
                last_error=str(last_error),
                component="orchestrator"
            )
            return default_value
        
        # Re-raise the last error
        if last_error:
            raise last_error
        
        raise RuntimeError("Failed to get valid human input")
    
    async def _arun(
        self,
        interrupt_type: InterruptType = InterruptType.CLARIFICATION,
        question: str = "",
        context: Dict[str, Any] = None,
        options: List[str] = None,
        default_value: str = None,
        validation_regex: str = None,
        timeout_seconds: int = 300,
        retry_on_invalid: bool = True,
        metadata: Dict[str, Any] = None,
        state: Annotated[Dict[str, Any], InjectedState] = None
    ) -> str:
        """Async version - just calls sync version since interrupt is sync."""
        return self._run(
            interrupt_type=interrupt_type,
            question=question,
            context=context,
            options=options,
            default_value=default_value,
            validation_regex=validation_regex,
            timeout_seconds=timeout_seconds,
            retry_on_invalid=retry_on_invalid,
            metadata=metadata,
            state=state
        )
    
    def _record_interrupt(self, payload: Dict[str, Any], state: Optional[Dict[str, Any]]) -> None:
        """Record interrupt with observer for tracking."""
        try:
            from src.orchestrator.observers import get_interrupt_observer
            
            observer = get_interrupt_observer()
            observer.record_interrupt(
                thread_id=payload.get("thread_id", "unknown"),
                interrupt_type=payload['interrupt_type'],  # Use actual interrupt type
                reason=f"{payload['interrupt_type']}: {payload['question']}",
                current_plan=state.get("plan", []) if state else [],
                state=state,
                interrupt_payload=payload  # Pass the full payload for SSE emission
            )
        except Exception as e:
            logger.error("failed_to_record_interrupt", error=str(e), component="orchestrator")
    
    def _record_response(
        self, 
        response: str, 
        payload: Dict[str, Any], 
        state: Optional[Dict[str, Any]]
    ) -> None:
        """Record successful response with observer."""
        try:
            from src.orchestrator.observers import get_interrupt_observer
            
            observer = get_interrupt_observer()
            observer.record_resume(
                thread_id=payload.get("thread_id", "unknown"),
                user_input=response,
                interrupt_type="human_input"
            )
        except Exception as e:
            logger.error("failed_to_record_response", error=str(e), component="orchestrator")