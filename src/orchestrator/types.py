"""Type definitions for orchestrator A2A communication."""

from typing import TypedDict, Optional, Dict, Any, List


class WorkflowState(TypedDict):
    """Workflow state information."""
    workflow_name: str
    thread_id: str
    step_id: Optional[str]
    context: Optional[Dict[str, Any]]


class A2AArtifact(TypedDict):
    """A2A response artifact."""
    id: str
    task_id: str
    content: str
    content_type: str


class A2AMetadata(TypedDict, total=False):
    """A2A response metadata."""
    interrupted_workflow: Optional[WorkflowState]
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
    interrupted_workflow: Optional[WorkflowState]
    state_snapshot: Optional[Dict[str, Any]]