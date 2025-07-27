"""Simplified human input tool that passes messages directly to users."""

from typing import Dict, Any, Annotated
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from langgraph.types import interrupt
from langgraph.prebuilt import InjectedState
from src.utils.logging.framework import SmartLogger

logger = SmartLogger("orchestrator")


class HumanInputRequest(BaseModel):
    """Simple schema for human input requests."""
    
    question: str = Field(
        description="The complete message to show the user, including any options or context"
    )
    
    state: Annotated[dict, InjectedState] = Field(
        description="Injected state from LangGraph for accessing conversation context"
    )


class HumanInputTool(BaseTool):
    """Simplified human input tool that shows messages and waits for responses.
    
    This tool simply displays whatever message the agent wants to show to the user
    and returns their response. The message should include all necessary context,
    options, and formatting.
    """
    
    name: str = "human_input"
    description: str = """Request human input by showing a message and waiting for response.
    
    Simply pass the complete message you want to show the user, including:
    - The question or request
    - Any data or options they should choose from (already formatted)
    - Any context they need
    
    The tool will display your message exactly as provided and return the user's response.
    
    IMPORTANT: Format your message nicely for human readability. Include all relevant
    information from previous steps in a clean, readable format."""
    
    args_schema: type[BaseModel] = HumanInputRequest
    
    def _run(
        self,
        question: str,
        state: Annotated[Dict[str, Any], InjectedState] = None
    ) -> str:
        """Request human input with a simple message.
        
        Args:
            question: The complete message to show the user
            state: Injected state from LangGraph
            
        Returns:
            User's response as string
        """
        # Log the request
        logger.info(
            "human_input_request",
            message_preview=question[:200],
            message_length=len(question),
            has_state=state is not None,
            thread_id=state.get("task_id") if state else None,
            component="orchestrator"
        )
        
        # Execute interrupt with the message - this will raise GraphInterrupt
        # The interrupt function doesn't return - it raises GraphInterrupt
        # which should be caught by the orchestrator
        logger.info(
            "human_input_raising_interrupt",
            message_length=len(question),
            component="orchestrator"
        )
        
        try:
            response = interrupt(question)
            
            # This code will only run if interrupt() somehow doesn't raise
            # (which shouldn't happen in normal operation)
            logger.warning(
                "human_input_interrupt_did_not_raise",
                response=str(response)[:100],
                component="orchestrator"
            )
            
            return str(response)
        except Exception as e:
            # Log the exception type for debugging
            logger.info(
                "human_input_interrupt_exception",
                exception_type=type(e).__name__,
                exception_message=str(e)[:200],
                component="orchestrator"
            )
            # Re-raise the exception (likely GraphInterrupt)
            raise
    
    async def _arun(
        self,
        question: str,
        state: Annotated[Dict[str, Any], InjectedState] = None
    ) -> str:
        """Async version - just calls sync version since interrupt is sync."""
        return self._run(question, state=state)