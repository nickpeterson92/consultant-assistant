"""Data models for workflow orchestration"""

from typing import Dict, Any, List, Optional
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


class WorkflowStatus(str, Enum):
    """Workflow execution states"""
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"  # Waiting for external input/time
    WAITING_FOR_HUMAN = "waiting_for_human"  # Waiting for human decision
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepType(str, Enum):
    """Types of workflow steps"""
    ACTION = "action"        # Call an agent/tool
    CONDITION = "condition"  # Evaluate condition
    WAIT = "wait"           # Wait for time/event
    PARALLEL = "parallel"   # Execute steps in parallel
    HUMAN = "human"         # Human approval needed
    SWITCH = "switch"       # Multiple conditional branches
    FOR_EACH = "for_each"   # Iterate over a collection
    EXTRACT = "extract"     # Extract/parse data from previous steps


class WorkflowStep(BaseModel):
    """Single step in a workflow"""
    id: str
    type: StepType
    name: str
    description: Optional[str] = None
    
    # For ACTION steps
    agent: Optional[str] = None
    instruction: Optional[str] = None
    
    # For CONDITION steps
    condition: Optional[Dict[str, Any]] = None
    true_next: Optional[str] = None
    false_next: Optional[str] = None
    
    # For WAIT steps
    wait_until: Optional[datetime] = None
    wait_for_event: Optional[str] = None
    
    # For PARALLEL steps
    parallel_steps: Optional[List[str]] = None
    
    # For SWITCH steps (multiple conditions)
    switch_conditions: Optional[List[Dict[str, Any]]] = None
    default_next: Optional[str] = None
    
    # For FOR_EACH steps
    iterate_over: Optional[str] = None  # Variable name containing list
    iterator_variable: Optional[str] = None  # Variable name for current item
    loop_steps: Optional[List[str]] = None  # Steps to execute for each item
    max_iterations: Optional[int] = None  # Safety limit
    
    # For EXTRACT steps
    extract_from: Optional[str] = None  # Variable/step result to extract from
    extract_prompt: Optional[str] = None  # Prompt for LLM-based extraction
    extract_model: Optional[str] = None  # Pydantic model name for structured extraction
    
    # For ACTION steps with conditional completion
    on_complete: Optional[Dict[str, Any]] = None  # Conditional next step
    
    # Skip conditions
    skip_if: Optional[Dict[str, Any]] = None  # Skip this step if condition is true
    
    # Common fields
    next_step: Optional[str] = None
    retry_policy: Optional[Dict[str, Any]] = None
    timeout: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    critical: bool = False  # If True, workflow fails if this step fails


class WorkflowDefinition(BaseModel):
    """Complete workflow definition"""
    id: str
    name: str
    description: str
    trigger: Dict[str, Any]  # What starts this workflow
    steps: Dict[str, WorkflowStep]  # Step ID -> Step
    variables: Dict[str, Any] = {}  # Workflow variables
    metadata: Dict[str, Any] = {}
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    version: str = "1.0.0"


class WorkflowInstance(BaseModel):
    """Running instance of a workflow"""
    id: str
    workflow_id: str
    workflow_name: str
    status: WorkflowStatus
    current_step: Optional[str] = None
    variables: Dict[str, Any] = {}
    history: List[Dict[str, Any]] = []
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    triggered_by: Optional[str] = None
    parent_workflow_id: Optional[str] = None  # For nested workflows