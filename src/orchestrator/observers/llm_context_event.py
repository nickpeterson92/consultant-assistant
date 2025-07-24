"""LLM context event for showing exact prompts in the UI."""

from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class LLMContextEvent:
    """Event emitted when context is built for LLM requests."""
    step_name: str
    task_id: Optional[str]
    timestamp: str
    context_type: str  # "execution", "planning", "replanning"
    context_text: str  # The actual context that will be sent
    metadata: Dict[str, Any]  # Stats about the context
    full_prompt: Optional[str] = None  # The complete prompt if available
    thread_id: Optional[str] = None