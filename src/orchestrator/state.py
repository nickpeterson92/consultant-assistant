"""Simplified orchestrator state management."""

from typing import Annotated, Dict, Any, List
import operator
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages

from src.utils.config import config
from src.utils.logging import get_logger

logger = get_logger()


class OrchestratorState(TypedDict):
    """Simplified state schema for orchestrator graph."""
    messages: Annotated[list, add_messages]
    summary: str
    active_agents: List[str]
    last_agent_interaction: Dict[str, Any]