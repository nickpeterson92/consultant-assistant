"""Human input tool for LangGraph workflows using interrupt functionality."""

from typing import Dict, Any
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from langgraph.types import interrupt
from src.utils.logging.framework import SmartLogger

logger = SmartLogger("orchestrator")


class HumanInputRequest(BaseModel):
    """Schema for human input requests."""
    question: str = Field(description="The question or clarification request to present to the user")
    context: str = Field(default="", description="Additional context about why input is needed")
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
    
    The tool will pause execution and wait for the human to provide the requested input."""
    
    args_schema: type[BaseModel] = HumanInputRequest
    
    def _run(self, question: str, context: str = "", timeout_seconds: int = 300) -> str:
        """Request human input using LangGraph interrupt functionality.
        
        Args:
            question: The question to ask the user
            context: Additional context about why input is needed
            timeout_seconds: How long to wait for input (not enforced by interrupt)
            
        Returns:
            The user's response as a string
        """
        logger.info(
            "human_input_request",
            question_preview=question[:100],
            has_context=bool(context),
            component="orchestrator"
        )
        
        # Format the request for clarity
        if context:
            formatted_request = f"CLARIFICATION NEEDED:\n\nContext: {context}\n\nQuestion: {question}\n\nPlease provide your response:"
        else:
            formatted_request = f"CLARIFICATION NEEDED:\n\n{question}\n\nPlease provide your response:"
        
        try:
            # Use LangGraph's interrupt to pause execution and wait for user input
            user_response = interrupt(formatted_request)
            
            logger.info(
                "human_input_received", 
                response_preview=str(user_response)[:100],
                response_length=len(str(user_response)),
                component="orchestrator"
            )
            
            return str(user_response)
            
        except Exception as e:
            logger.error(
                "human_input_error",
                error=str(e),
                error_type=type(e).__name__,
                component="orchestrator"
            )
            # Return a helpful fallback message
            return f"Unable to get human input: {str(e)}. Please rephrase your request with more specific details."
    
    async def _arun(self, question: str, context: str = "", timeout_seconds: int = 300) -> str:
        """Async version - just calls the sync version since interrupt is sync."""
        return self._run(question, context, timeout_seconds)