"""Type definitions for orchestrator A2A communication."""

from typing import TypedDict, Optional, Dict, Any, List


# WorkflowState removed - workflow functionality moved to plan-and-execute


class A2AArtifact(TypedDict):
    """A2A response artifact."""
    id: str
    task_id: str
    content: str
    content_type: str


class A2AMetadata(TypedDict, total=False):
    """A2A response metadata."""
    state_sync: Optional[Dict[str, Any]]


class A2AResponse(TypedDict):
    """A2A response structure."""
    artifacts: List[A2AArtifact]
    status: str
    metadata: A2AMetadata  # Always present for state synchronization
    error: Optional[str]


class A2AContext(TypedDict, total=False):
    """A2A request context."""
    thread_id: str
    source: str
    state_snapshot: Optional[Dict[str, Any]]