# Workflow Engine Architecture

The Workflow Engine is the core execution system that powers complex multi-step business processes across the multi-agent platform. It provides stateful, resilient, and intelligent orchestration of tasks spanning multiple systems.

## Overview

The Workflow Engine operates as a state machine that executes predefined workflow templates, managing variables, handling errors, and coordinating between multiple specialized agents while maintaining full auditability and resumption capabilities.

## Core Architecture

### Engine Components

```python
# Main Engine Class
class WorkflowEngine:
    def __init__(self, store_adapter: AsyncStoreAdapter):
        self.store = store_adapter
        self.a2a_client = A2AClient()
        
    async def execute_workflow(self, workflow_def: WorkflowDefinition, variables: Dict[str, Any]) -> WorkflowInstance
    async def resume_workflow(self, instance_id: str) -> WorkflowInstance
    async def get_workflow_status(self, instance_id: str) -> WorkflowStatus
```

### State Management

The engine maintains persistent state across workflow executions:

```python
@dataclass
class WorkflowInstance:
    id: str                          # Unique instance identifier
    workflow_id: str                 # Template ID
    name: str                        # Human-readable name
    status: WorkflowStatus           # Current execution status
    variables: Dict[str, Any]        # Runtime variables
    current_step_id: Optional[str]   # Current execution point
    step_history: List[StepResult]   # Execution history
    created_at: datetime
    updated_at: datetime
    error_info: Optional[ErrorInfo]  # Error details if failed
```

## Step Types and Execution

### ACTION Steps

Execute operations via agent communication:

```python
# Step Definition
{
    "id": "get_salesforce_data",
    "type": "action",
    "name": "Retrieve account information",
    "agent": "salesforce-agent",
    "instruction": "Find account {account_name} with opportunities",
    "timeout": 30,
    "retry_count": 3,
    "on_complete": "analyze_data"
}

# Engine Processing
async def _handle_action_step(self, instance: WorkflowInstance, step: WorkflowStep) -> StepResult:
    # 1. Variable substitution
    instruction = self._substitute_variables(step.instruction, instance.variables)
    
    # 2. Agent communication via A2A
    result = await self.a2a_client.call_agent(
        agent_name=step.agent,
        instruction=instruction,
        context=self._build_context(instance),
        timeout=step.timeout
    )
    
    # 3. Store result and update state
    instance.variables[f"{step.id}_result"] = result
    return StepResult(step_id=step.id, status="completed", result=result)
```

### CONDITION Steps

Implement branching logic with typed conditions:

```python
# Condition Types
CONDITION_TYPES = {
    "count_greater_than": lambda value, target: len(value) > target,
    "response_contains": lambda response, text: text.lower() in str(response).lower(),
    "has_error": lambda value: isinstance(value, dict) and "error" in value,
    "is_empty": lambda value: not value or len(value) == 0,
    "value_equals": lambda value, target: value == target
}

# Step Processing
async def _handle_condition_step(self, instance: WorkflowInstance, step: WorkflowStep) -> StepResult:
    condition = step.condition
    variable_value = instance.variables.get(condition["variable"])
    
    # Evaluate condition
    condition_func = CONDITION_TYPES[condition["type"]]
    result = condition_func(variable_value, condition.get("value"))
    
    # Determine next step
    next_step = step.on_complete["if_true"] if result else step.on_complete["if_false"]
    
    return StepResult(
        step_id=step.id,
        status="completed", 
        result=result,
        next_step_id=next_step
    )
```

### PARALLEL Steps

Execute multiple steps concurrently:

```python
async def _handle_parallel_step(self, instance: WorkflowInstance, step: WorkflowStep) -> StepResult:
    # Launch all parallel steps
    tasks = []
    for parallel_step_id in step.parallel_steps:
        parallel_step = self._get_step_by_id(parallel_step_id)
        task = asyncio.create_task(
            self._execute_single_step(instance, parallel_step)
        )
        tasks.append((parallel_step_id, task))
    
    # Wait for all to complete
    results = {}
    for step_id, task in tasks:
        try:
            result = await task
            results[step_id] = result
        except Exception as e:
            results[step_id] = {"error": str(e)}
    
    # Aggregate results
    instance.variables[f"{step.id}_results"] = results
    return StepResult(step_id=step.id, status="completed", result=results)
```

### WAIT Steps

Handle compilation and timed delays:

```python
async def _handle_wait_step(self, instance: WorkflowInstance, step: WorkflowStep) -> StepResult:
    if step.metadata and "compile_fields" in step.metadata:
        # Result compilation
        compiled_result = self._compile_results(
            instance, 
            step.metadata["compile_fields"],
            step.metadata.get("summary_template")
        )
        instance.variables[f"{step.id}_compiled"] = compiled_result
        
    elif step.duration:
        # Timed wait
        await asyncio.sleep(step.duration)
        
    return StepResult(step_id=step.id, status="completed")
```

### FOR_EACH Steps

Iterate over collections with safety limits:

```python
async def _handle_for_each_step(self, instance: WorkflowInstance, step: WorkflowStep) -> StepResult:
    collection = instance.variables.get(step.collection_variable, [])
    
    # Safety limit
    if len(collection) > 50:
        logger.warning(f"FOR_EACH collection size {len(collection)} exceeds safety limit")
        collection = collection[:50]
    
    results = []
    for item in collection:
        # Create iteration context
        iteration_vars = instance.variables.copy()
        iteration_vars[step.item_variable] = item
        
        # Execute iteration step
        iteration_step = self._get_step_by_id(step.iteration_step_id)
        result = await self._execute_single_step_with_vars(iteration_step, iteration_vars)
        results.append(result)
    
    instance.variables[f"{step.id}_results"] = results
    return StepResult(step_id=step.id, status="completed", result=results)
```

## Variable Management

### Variable Substitution

The engine supports sophisticated variable templating:

```python
def _substitute_variables(self, template: str, variables: Dict[str, Any]) -> str:
    """
    Supports:
    - Simple: {variable_name}
    - Nested: {opportunity.account.name}
    - Error handling: [Previous step failed: {missing_var}]
    """
    def replacer(match):
        var_path = match.group(1)
        try:
            value = self._get_nested_value(variables, var_path)
            return str(value) if value is not None else f"[Variable not found: {var_path}]"
        except Exception:
            return f"[Previous step failed: {var_path}]"
    
    return re.sub(r'\{([^}]+)\}', replacer, template)
```

### Context Propagation

Maintains conversation context across agent calls:

```python
def _build_context(self, instance: WorkflowInstance) -> Dict[str, Any]:
    """Build context for agent calls including orchestrator state."""
    return {
        "workflow_id": instance.id,
        "workflow_name": instance.name,
        "step_id": instance.current_step_id,
        "step_name": self._get_current_step_name(instance),
        "workflow_variables": instance.variables,
        "orchestrator_state_snapshot": instance.variables.get("orchestrator_state_snapshot")
    }
```

## Error Handling and Resilience

### Retry Logic

Implements exponential backoff for transient failures:

```python
async def _execute_with_retry(self, operation: Callable, max_retries: int = 3) -> Any:
    for attempt in range(max_retries + 1):
        try:
            return await operation()
        except Exception as e:
            if attempt == max_retries:
                raise
            
            # Exponential backoff
            delay = 2 ** attempt
            logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
            await asyncio.sleep(delay)
```

### Error Classification

Categorizes errors for appropriate handling:

```python
def _classify_error(self, error: Exception) -> ErrorType:
    """Classify errors for appropriate retry/failure handling."""
    if isinstance(error, (ConnectionError, TimeoutError)):
        return ErrorType.TRANSIENT
    elif isinstance(error, ValidationError):
        return ErrorType.PERMANENT
    elif "rate limit" in str(error).lower():
        return ErrorType.RATE_LIMIT
    else:
        return ErrorType.UNKNOWN
```

### Graceful Degradation

Continues execution where possible when non-critical steps fail:

```python
async def _handle_step_failure(self, instance: WorkflowInstance, step: WorkflowStep, error: Exception):
    """Handle step failures with appropriate escalation."""
    if step.critical:
        # Critical step failure - abort workflow
        instance.status = WorkflowStatus.FAILED
        instance.error_info = ErrorInfo(
            step_id=step.id,
            error_type=type(error).__name__,
            error_message=str(error),
            timestamp=datetime.utcnow()
        )
    else:
        # Non-critical step - continue with error marker
        instance.variables[f"{step.id}_error"] = str(error)
        logger.warning(f"Non-critical step {step.id} failed, continuing: {error}")
```

## State Persistence

### Storage Strategy

Uses AsyncStoreAdapter for durable state management:

```python
async def _save_instance(self, instance: WorkflowInstance):
    """Persist workflow instance state."""
    await self.store.set(
        namespace=("workflow", "instances"),
        key=instance.id,
        value=instance.model_dump()
    )

async def _load_instance(self, instance_id: str) -> WorkflowInstance:
    """Load workflow instance from storage."""
    data = await self.store.get(
        namespace=("workflow", "instances"),
        key=instance_id
    )
    return WorkflowInstance.model_validate(data)
```

### Checkpoint Strategy

Saves state at key execution points:

```python
# Before each step
await self._save_instance(instance)

# After successful step completion
instance.updated_at = datetime.utcnow()
await self._save_instance(instance)

# On error
instance.error_info = error_details
await self._save_instance(instance)
```

## Performance Optimization

### Concurrent Execution

Maximizes parallelism while maintaining data integrity:

```python
# Parallel step execution
async def _execute_parallel_safely(self, steps: List[WorkflowStep], instance: WorkflowInstance):
    """Execute steps in parallel with proper error isolation."""
    semaphore = asyncio.Semaphore(5)  # Limit concurrent operations
    
    async def execute_with_semaphore(step):
        async with semaphore:
            return await self._execute_single_step(instance, step)
    
    tasks = [execute_with_semaphore(step) for step in steps]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

### Memory Management

Efficient handling of large result sets:

```python
def _optimize_variables(self, variables: Dict[str, Any]) -> Dict[str, Any]:
    """Optimize variable storage for large datasets."""
    optimized = {}
    for key, value in variables.items():
        if isinstance(value, list) and len(value) > 1000:
            # Store large lists as summaries
            optimized[key] = {
                "type": "large_collection",
                "count": len(value),
                "sample": value[:10],
                "summary": f"Collection of {len(value)} items"
            }
        else:
            optimized[key] = value
    return optimized
```

## Monitoring and Observability

### Execution Logging

Comprehensive logging at all execution levels:

```python
# Workflow level
logger.info("workflow_started", 
    workflow_id=instance.id, 
    workflow_name=instance.name,
    triggered_by=context.get("triggered_by"))

# Step level  
logger.info("workflow_step_start",
    workflow_id=instance.id,
    step_id=step.id,
    step_type=step.type.value,
    step_name=step.name)

# Action level
logger.info("workflow_action_step",
    workflow_id=instance.id,
    agent=step.agent,
    instruction_full=instruction)
```

### Metrics Collection

Tracks performance and reliability metrics:

```python
# Duration tracking
execution_start = time.time()
# ... execute workflow
execution_duration = time.time() - execution_start

logger.info("workflow_completed",
    workflow_id=instance.id,
    duration=execution_duration,
    step_count=len(instance.step_history),
    success_rate=self._calculate_success_rate(instance))
```

### Health Monitoring

Provides health checks and status reporting:

```python
async def get_engine_health(self) -> Dict[str, Any]:
    """Get engine health status."""
    active_workflows = await self._count_active_workflows()
    avg_execution_time = await self._get_avg_execution_time()
    
    return {
        "status": "healthy" if active_workflows < 100 else "degraded",
        "active_workflows": active_workflows,
        "average_execution_time": avg_execution_time,
        "storage_health": await self.store.health_check()
    }
```

## Integration Points

### A2A Protocol

Seamless integration with the agent communication protocol:

```python
class WorkflowA2AHandler:
    async def process_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle A2A workflow execution requests."""
        instruction = params.get("instruction", "")
        context = params.get("context", {})
        
        # Route to appropriate workflow
        workflow_type = self._detect_workflow_type(instruction)
        workflow_def = WORKFLOW_TEMPLATES[workflow_type]
        
        # Execute with orchestrator context
        result = await self.engine.execute_workflow(workflow_def, {
            "instruction": instruction,
            "orchestrator_state_snapshot": context.get("state_snapshot")
        })
        
        return {
            "workflow_id": result.id,
            "status": result.status.value,
            "result": self._format_result(result)
        }
```

### LangGraph Integration

Works within the LangGraph state management framework:

```python
def create_workflow_graph() -> StateGraph:
    """Create the main workflow execution graph."""
    graph = StateGraph(WorkflowState)
    
    graph.add_node("router", route_workflow)
    graph.add_node("executor", execute_workflow)
    graph.add_node("status_checker", check_status)
    
    graph.add_edge(START, "router")
    graph.add_edge("router", "executor")
    graph.add_edge("executor", "status_checker")
    graph.add_edge("status_checker", END)
    
    return graph.compile()
```

## Security Considerations

### Input Validation

Comprehensive validation of workflow inputs:

```python
def _validate_workflow_input(self, workflow_def: WorkflowDefinition, variables: Dict[str, Any]):
    """Validate workflow inputs for security and correctness."""
    # Validate required variables
    for required_var in workflow_def.required_variables:
        if required_var not in variables:
            raise ValidationError(f"Required variable missing: {required_var}")
    
    # Sanitize string inputs
    for key, value in variables.items():
        if isinstance(value, str):
            variables[key] = self._sanitize_input(value)
```

### Execution Limits

Prevents resource exhaustion:

```python
# Maximum execution time
MAX_WORKFLOW_DURATION = 3600  # 1 hour

# Maximum steps per workflow
MAX_STEPS_PER_WORKFLOW = 100

# Maximum parallel branches
MAX_PARALLEL_BRANCHES = 10

# Memory limits for variables
MAX_VARIABLE_SIZE = 10 * 1024 * 1024  # 10MB
```

### Access Control

Ensures proper authorization for workflow execution:

```python
def _check_workflow_permissions(self, workflow_id: str, context: Dict[str, Any]) -> bool:
    """Verify user has permission to execute workflow."""
    user_roles = context.get("user_roles", [])
    workflow_requirements = WORKFLOW_PERMISSIONS.get(workflow_id, [])
    
    return any(role in user_roles for role in workflow_requirements)
```

## Best Practices

### Workflow Design

1. **Idempotency**: Design steps to be safely retryable
2. **Atomicity**: Keep steps focused on single operations
3. **Error Boundaries**: Use critical flags appropriately
4. **Resource Limits**: Respect timeout and size constraints

### Performance

1. **Parallel Execution**: Use parallel steps for independent operations
2. **Variable Optimization**: Minimize large data storage in variables
3. **Checkpoint Strategy**: Save state at appropriate intervals
4. **Resource Cleanup**: Clean up temporary data promptly

### Monitoring

1. **Comprehensive Logging**: Log all significant events
2. **Error Tracking**: Capture detailed error information
3. **Performance Metrics**: Track execution times and success rates
4. **Health Monitoring**: Implement proactive health checks

## Related Documentation

- [Workflow Templates](../guides/workflow-templates.md)
- [A2A Protocol](../protocols/a2a-protocol.md)
- [Multi-Agent Architecture](../architecture/multi-agent-architecture.md)
- [Storage System](../operations/memory-system.md)