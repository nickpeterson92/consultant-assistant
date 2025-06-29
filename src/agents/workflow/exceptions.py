"""Workflow Agent Exceptions"""

class WorkflowExecutionError(Exception):
    """Base exception for workflow execution errors"""
    pass


class WorkflowInterruptError(WorkflowExecutionError):
    """Exception for workflow interrupts requiring human input"""
    def __init__(self, value=None):
        self.value = value or {}
        super().__init__("Workflow interrupted for human input")


class StepExecutionError(WorkflowExecutionError):
    """Error executing a specific workflow step"""
    def __init__(self, step_id: str, original_error: Exception):
        self.step_id = step_id
        self.original_error = original_error
        super().__init__(f"Error executing step {step_id}: {str(original_error)}")


class WorkflowNotFoundError(WorkflowExecutionError):
    """Workflow definition not found"""
    pass


class InvalidWorkflowStateError(WorkflowExecutionError):
    """Invalid workflow state or configuration"""
    pass