"""Helper to emit LLM context events."""

from datetime import datetime
from typing import Dict, Any, Optional

from src.orchestrator.observers import get_observer_registry, LLMContextEvent
from src.utils.logging.framework import SmartLogger

logger = SmartLogger("orchestrator")


def emit_llm_context(
    context_type: str,
    context_text: str,
    metadata: Dict[str, Any],
    full_prompt: Optional[str] = None,
    task_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    step_name: str = "memory_context"
):
    """
    Emit an LLM context event for UI visualization.
    
    Args:
        context_type: Type of context ("execution", "planning", "replanning")
        context_text: The memory context being added to the prompt
        metadata: Stats about the context (counts, etc)
        full_prompt: The complete prompt if available
        task_id: Current task ID
        thread_id: Current thread ID
        step_name: Name of the step (default: "memory_context")
    """
    try:
        registry = get_observer_registry()
        
        event = LLMContextEvent(
            step_name=step_name,
            task_id=task_id,
            timestamp=datetime.now().isoformat(),
            context_type=context_type,
            context_text=context_text,
            metadata=metadata,
            full_prompt=full_prompt,
            thread_id=thread_id
        )
        
        registry.notify_llm_context(event)
        
        logger.info("llm_context_emitted",
                   context_type=context_type,
                   metadata=metadata,
                   context_length=len(context_text),
                   has_full_prompt=bool(full_prompt))
                   
    except Exception as e:
        logger.error("llm_context_emission_failed", error=str(e))