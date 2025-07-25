"""Decorator-based cost tracking for LLM instances.

This module provides decorators that can wrap any LLM instance to add
cost tracking without inheritance issues.
"""

import functools
from typing import Any, Dict, List, Optional, Union
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult

from src.utils.cost_tracking import CostTracker
from src.utils.logging.framework import SmartLogger

logger = SmartLogger("cost_tracking_decorator")


def with_cost_tracking(component: str):
    """Decorator to add cost tracking to an LLM instance.
    
    Args:
        component: The component using this LLM (e.g., "orchestrator", "salesforce")
    
    Returns:
        Decorator function
    """
    def decorator(llm_instance):
        """Apply cost tracking to the LLM instance."""
        # Store original methods
        original_generate = llm_instance._generate
        original_agenerate = llm_instance._agenerate
        
        # Get deployment name from the instance
        deployment_name = getattr(llm_instance, 'deployment_name', 'unknown')
        
        def _generate_with_tracking(messages: List[BaseMessage], 
                                   stop: Optional[List[str]] = None,
                                   run_manager: Optional[Any] = None,
                                   **kwargs: Any) -> ChatResult:
            """Wrap _generate with cost tracking."""
            # Call original method
            result = original_generate(messages, stop, run_manager, **kwargs)
            
            # Extract operation and thread_id from run_manager if available
            operation = "unknown"
            thread_id = None
            
            if run_manager and hasattr(run_manager, 'extra'):
                extra = run_manager.extra or {}
                operation = extra.get("operation", operation)
                thread_id = extra.get("thread_id", thread_id)
                
            # Track the cost using the result
            if result.generations and len(result.generations) > 0:
                response_message = result.generations[0].message
                
                metadata = {
                    "thread_id": thread_id,
                    "deployment": deployment_name,
                }
                
                # Remove None values from metadata
                metadata = {k: v for k, v in metadata.items() if v is not None}
                
                try:
                    CostTracker.track_messages(
                        messages=messages,
                        response=response_message,
                        model=deployment_name,
                        component=component,
                        operation=operation,
                        metadata=metadata
                    )
                except Exception as e:
                    logger.error("cost_tracking_failed",
                                error=str(e),
                                component=component,
                                operation=operation)
            
            return result
        
        async def _agenerate_with_tracking(messages: List[BaseMessage],
                                          stop: Optional[List[str]] = None,
                                          run_manager: Optional[Any] = None,
                                          **kwargs: Any) -> ChatResult:
            """Wrap _agenerate with cost tracking."""
            # Call original method
            result = await original_agenerate(messages, stop, run_manager, **kwargs)
            
            # Extract operation and thread_id from run_manager if available
            operation = "unknown"
            thread_id = None
            
            if run_manager and hasattr(run_manager, 'extra'):
                extra = run_manager.extra or {}
                operation = extra.get("operation", operation)
                thread_id = extra.get("thread_id", thread_id)
                
            # Track the cost using the result
            if result.generations and len(result.generations) > 0:
                response_message = result.generations[0].message
                
                metadata = {
                    "thread_id": thread_id,
                    "deployment": deployment_name,
                }
                
                # Remove None values from metadata
                metadata = {k: v for k, v in metadata.items() if v is not None}
                
                try:
                    CostTracker.track_messages(
                        messages=messages,
                        response=response_message,
                        model=deployment_name,
                        component=component,
                        operation=operation,
                        metadata=metadata
                    )
                except Exception as e:
                    logger.error("cost_tracking_failed",
                                error=str(e),
                                component=component,
                                operation=operation)
            
            return result
        
        # Replace the methods on the instance
        llm_instance._generate = _generate_with_tracking
        llm_instance._agenerate = _agenerate_with_tracking
        
        # Add a marker so we know this instance has cost tracking
        llm_instance._has_cost_tracking = True
        llm_instance._cost_tracking_component = component
        
        return llm_instance
    
    return decorator


def create_cost_tracking_azure_openai(component: str, **kwargs):
    """Create an Azure OpenAI instance with cost tracking applied via decorator.
    
    Args:
        component: Component name for tracking (e.g., "orchestrator", "salesforce")
        **kwargs: All standard AzureChatOpenAI arguments
        
    Returns:
        Azure OpenAI instance with cost tracking decorator applied
    """
    from langchain_openai import AzureChatOpenAI
    
    # Create the base LLM instance
    llm = AzureChatOpenAI(**kwargs)
    
    # Apply cost tracking decorator
    return with_cost_tracking(component)(llm)