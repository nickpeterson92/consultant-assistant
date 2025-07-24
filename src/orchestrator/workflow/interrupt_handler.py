"""Improved interrupt handling for orchestrator.

This module provides better handling for different types of interrupts:
1. HumanInputTool interrupts - Agent needs clarification
2. User escape interrupts - User wants to modify/abort plan
"""

from typing import Dict, Any
from langgraph.errors import GraphInterrupt
from src.utils.logging.framework import SmartLogger

logger = SmartLogger("orchestrator")


class InterruptHandler:
    """Handles different types of interrupts in the orchestrator."""
    
    @staticmethod
    def is_user_escape_interrupt(interrupt: GraphInterrupt) -> bool:
        """Check if this is a user escape interrupt."""
        if hasattr(interrupt, 'value') and isinstance(interrupt.value, dict):
            return interrupt.value.get("type") == "user_escape"
        return False
    
    @staticmethod
    def is_human_input_interrupt(interrupt: GraphInterrupt) -> bool:
        """Check if this is a HumanInputTool interrupt."""
        if hasattr(interrupt, 'value'):
            if isinstance(interrupt.value, dict):
                return interrupt.value.get("type") != "user_escape"
            return True  # String interrupts are from HumanInputTool
        return False
    
    @staticmethod
    def detect_interrupt_clash(state: Dict[str, Any], interrupt: GraphInterrupt) -> bool:
        """Detect if there's a clash between user and agent interrupts.
        
        Returns True if user has interrupted while agent was trying to interrupt.
        """
        # Check if user has interrupted
        user_interrupted = state.get("user_interrupted", False)
        
        # Check if this is an agent interrupt
        is_agent_interrupt = InterruptHandler.is_human_input_interrupt(interrupt)
        
        if user_interrupted and is_agent_interrupt:
            logger.warning("interrupt_clash_detected",
                         component="orchestrator",
                         user_interrupt_reason=state.get("interrupt_reason"),
                         agent_interrupt_value=str(interrupt.value)[:100] if hasattr(interrupt, 'value') else "")
            return True
        
        return False
    
    @staticmethod
    def handle_resume(state: Dict[str, Any], user_input: str, interrupt_type: str) -> Dict[str, Any]:
        """Handle resume based on interrupt type.
        
        Args:
            state: Current graph state
            user_input: User's input when resuming
            interrupt_type: Type of interrupt ("user_escape" or "human_input")
            
        Returns:
            Updated state dict
        """
        updates = {}
        
        if interrupt_type == "user_escape":
            # User wants to modify the plan
            logger.info("handling_user_escape_resume",
                       component="orchestrator",
                       user_input=user_input[:100])
            
            # Set flags for replanner to know this is a user-requested modification
            updates = {
                "user_modification_request": user_input,
                "should_force_replan": True,
                "user_interrupted": False,  # Clear the flag
                "interrupt_reason": None
            }
            
        elif interrupt_type == "human_input":
            # Agent needed clarification - just continue
            logger.info("handling_human_input_resume",
                       component="orchestrator",
                       user_input=user_input[:100])
            
            # No special handling needed - the agent will receive the input
            updates = {}
        
        return updates
    
    @staticmethod
    def should_skip_to_replan(state: Dict[str, Any]) -> bool:
        """Check if we should skip directly to replanning.
        
        This is used when user has requested plan modification via escape key.
        """
        return state.get("should_force_replan", False)
    
    @staticmethod
    def prepare_replan_context(state: Dict[str, Any]) -> str:
        """Prepare context for the replanner when user requested modification."""
        user_request = state.get("user_modification_request", "")
        if not user_request:
            return ""
        
        context = f"""
The user has interrupted the execution and requested the following modification:
"{user_request}"

Please update the plan to accommodate this request. Consider:
1. What parts of the current plan are still valid
2. What needs to be changed or added
3. Whether the user wants to abort current approach entirely
"""
        return context