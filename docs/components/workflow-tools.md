# Workflow Tools Integration

This document provides comprehensive documentation for the workflow tools that integrate the workflow agent with the orchestrator system. These tools enable intelligent workflow routing, execution monitoring, and discovery through natural language interfaces.

## Overview

The workflow tools serve as the bridge between the conversational orchestrator and the workflow execution engine. They provide three main capabilities:
1. **Intelligent Workflow Execution**: Smart routing and execution of workflows
2. **Status Monitoring**: Real-time tracking of workflow execution
3. **Template Discovery**: Dynamic discovery of available workflows

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   User Input    │    │  Workflow Tools  │    │ Workflow Agent  │
│                 │────│                  │────│                 │
│ Natural Language│    │ Smart Routing    │    │ Engine + State  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                               │
                               ▼
                       ┌──────────────────┐
                       │ Sub-Agents       │
                       │ (SF/JIRA/SN)     │
                       └──────────────────┘
```

## Tool Implementation

### Base Tool Architecture

All workflow tools inherit from the orchestrator's base tool system:

```python
# File: src/tools/workflow_tools.py
from src.orchestrator.agent_caller_tools import BaseAgentTool

class WorkflowExecutionTool(BaseAgentTool):
    """Smart workflow routing and execution."""
    
    name = "workflow_agent"
    description = """Execute complex multi-step workflows across systems.
    
    Use this tool when the user wants to:
    - Run predefined business processes
    - Execute workflows that span multiple systems
    - Automate complex operational tasks
    
    Examples: "check for at-risk deals", "run customer onboarding", "generate account health report"
    """
```

## 1. WorkflowExecutionTool

### Purpose
The primary tool for executing workflows through intelligent routing and context-aware execution.

### Key Features

#### Smart Workflow Detection
Uses LLM-powered analysis to match user intent to workflows:

```python
def _detect_workflow_type(self, instruction: str) -> Optional[str]:
    """Detect workflow type from natural language instruction."""
    instruction_lower = instruction.lower()
    
    # Keyword-based detection for performance
    workflow_keywords = {
        "deal_risk_assessment": ["risk", "deal", "opportunity", "stale", "at-risk"],
        "incident_to_resolution": ["incident", "escalate", "case", "critical"],
        "customer_360_report": ["customer", "360", "report", "comprehensive"],
        "weekly_account_health_check": ["health", "account", "weekly", "assessment"],
        "new_customer_onboarding": ["onboarding", "new customer", "setup"]
    }
    
    # Score each workflow based on keyword matches
    scores = {}
    for workflow_id, keywords in workflow_keywords.items():
        scores[workflow_id] = sum(1 for keyword in keywords if keyword in instruction_lower)
    
    # Return highest scoring workflow if above threshold
    best_workflow = max(scores.items(), key=lambda x: x[1])
    return best_workflow[0] if best_workflow[1] >= 2 else None
```

#### Hybrid Execution Strategy
Optimizes execution based on workflow complexity:

```python
async def _execute_sync_workflow(self, workflow_def: WorkflowDefinition, instruction: str) -> str:
    """Execute simple workflows synchronously for better UX."""
    
    # Criteria for sync execution:
    # 1. No parallel steps
    # 2. All ACTION steps
    # 3. Less than 5 total steps
    # 4. No human intervention steps
    
    has_async_steps = any(
        step.type in [StepType.PARALLEL, StepType.HUMAN, StepType.WAIT] 
        for step in workflow_def.steps
    )
    
    if has_async_steps or len(workflow_def.steps) > 5:
        # Delegate to workflow agent for complex execution
        return await self._call_workflow_agent(instruction)
    else:
        # Execute simple workflows directly
        return await self._execute_simple_workflow(workflow_def, instruction)
```

#### Context Propagation
Maintains conversation state across workflow execution:

```python
def _build_workflow_context(self, state_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Build context for workflow execution including orchestrator state."""
    return {
        "state_snapshot": state_snapshot,
        "user_context": {
            "session_id": state_snapshot.get("session_id"),
            "user_preferences": state_snapshot.get("user_preferences", {}),
            "conversation_history": state_snapshot.get("recent_messages", [])
        },
        "triggered_by": "orchestrator_tool",
        "execution_mode": "conversational"
    }
```

### Usage Examples

```python
# User Input: "check for at-risk deals"
# Tool Processing:
{
    "detected_workflow": "deal_risk_assessment",
    "execution_mode": "async",  # Has parallel steps
    "agent_delegation": True,
    "context_included": True
}

# User Input: "get account info for ACME Corp"  
# Tool Processing:
{
    "detected_workflow": "simple_data_retrieval",
    "execution_mode": "sync",   # Simple single-step workflow
    "agent_delegation": False,
    "direct_execution": True
}
```

### Implementation Details

```python
async def _run(self, instruction: str, **kwargs) -> str:
    """Execute workflow with intelligent routing."""
    
    # 1. Detect workflow type
    workflow_type = self._detect_workflow_type(instruction)
    
    if not workflow_type:
        # Fallback to LLM-based detection
        workflow_type = await self._llm_detect_workflow(instruction)
    
    if not workflow_type:
        return self._format_no_workflow_response(instruction)
    
    # 2. Get workflow definition
    workflow_def = WORKFLOW_TEMPLATES.get(workflow_type)
    if not workflow_def:
        return f"Workflow template '{workflow_type}' not found."
    
    # 3. Choose execution strategy
    if self._should_execute_sync(workflow_def):
        # Simple synchronous execution
        result = await self._execute_sync_workflow(workflow_def, instruction)
    else:
        # Delegate to workflow agent for complex execution
        context = self._build_workflow_context(kwargs.get("state_snapshot", {}))
        result = await self._call_workflow_agent(instruction, context)
    
    return result
```

## 2. WorkflowStatusTool

### Purpose
Monitor and report on workflow execution status, providing real-time updates on running workflows.

### Key Features

#### Instance Status Tracking
```python
class WorkflowStatusTool(BaseAgentTool):
    name = "workflow_status"
    description = """Check the status of a running workflow.
    
    Use this tool to:
    - Monitor workflow execution progress
    - Check if a workflow completed successfully
    - Get detailed status information
    - Troubleshoot workflow issues
    
    Requires workflow_id parameter.
    """
    
    async def _run(self, workflow_id: str, **kwargs) -> str:
        """Get detailed workflow status information."""
        
        try:
            # Query workflow agent for status
            status_request = {
                "operation": "get_status",
                "workflow_id": workflow_id
            }
            
            result = await self._call_agent_with_fallback(
                "workflow-agent", 
                f"Get status for workflow {workflow_id}",
                context=status_request
            )
            
            return self._format_status_response(result)
            
        except Exception as e:
            return f"Error retrieving workflow status: {str(e)}"
```

#### Status Response Formatting
```python
def _format_status_response(self, result: Dict[str, Any]) -> str:
    """Format workflow status for user presentation."""
    
    status = result.get("status", "unknown")
    
    if status == "completed":
        return f"""
        ✅ **Workflow Completed Successfully**
        
        **ID**: {result.get('workflow_id')}
        **Name**: {result.get('workflow_name')}
        **Duration**: {result.get('duration', 'N/A')}
        **Steps Completed**: {result.get('steps_completed', 0)}
        
        **Summary**: {result.get('summary', 'Workflow completed successfully.')}
        """
    
    elif status == "running":
        return f"""
        🔄 **Workflow In Progress**
        
        **ID**: {result.get('workflow_id')}
        **Name**: {result.get('workflow_name')}
        **Current Step**: {result.get('current_step')}
        **Progress**: {result.get('progress_percentage', 0)}%
        **Estimated Time Remaining**: {result.get('estimated_remaining', 'Unknown')}
        """
    
    elif status == "failed":
        return f"""
        ❌ **Workflow Failed**
        
        **ID**: {result.get('workflow_id')}
        **Name**: {result.get('workflow_name')}
        **Failed At**: {result.get('failed_step')}
        **Error**: {result.get('error_message')}
        
        **Troubleshooting**: {result.get('troubleshooting_info', 'Check logs for details.')}
        """
    
    else:
        return f"Workflow {workflow_id} status: {status}"
```

### Usage Examples

```python
# User Input: "Check status of workflow wf_123"
# Tool Response:
"""
🔄 **Workflow In Progress**

**ID**: wf_deal_risk_assessment_1751139212
**Name**: At-Risk Deal Assessment  
**Current Step**: Analyzing opportunities for blockers
**Progress**: 60%
**Estimated Time Remaining**: 2-3 minutes
"""

# User Input: "Did the customer onboarding workflow complete?"
# Tool Response:
"""
✅ **Workflow Completed Successfully**

**ID**: wf_onboarding_acme_1751140000
**Name**: New Customer Onboarding Process
**Duration**: 4 minutes 32 seconds
**Steps Completed**: 8

**Summary**: Successfully set up ACME Corp in all systems. Jira project created, 
ServiceNow account configured, and kickoff meeting scheduled for next Tuesday.
"""
```

## 3. WorkflowListTool

### Purpose
Provide discovery and documentation of available workflow templates.

### Key Features

#### Dynamic Template Discovery
```python
class WorkflowListTool(BaseAgentTool):
    name = "workflow_list"
    description = """List available workflow templates.
    
    Use this tool to:
    - Discover available workflows
    - Show workflow descriptions and triggers
    - Help users understand workflow capabilities
    - Provide workflow documentation
    """
    
    async def _run(self, category: Optional[str] = None, **kwargs) -> str:
        """List available workflows with descriptions."""
        
        try:
            # Get workflow templates from agent
            result = await self._call_agent_with_fallback(
                "workflow-agent",
                "List all available workflow templates",
                context={"operation": "list_templates", "category": category}
            )
            
            return self._format_workflow_list(result)
            
        except Exception as e:
            # Fallback to static template list
            return self._get_static_workflow_list(category)
```

#### Template Information Formatting
```python
def _format_workflow_list(self, workflows: List[Dict[str, Any]]) -> str:
    """Format workflow list for user presentation."""
    
    if not workflows:
        return "No workflows available."
    
    response = "## Available Workflows\n\n"
    
    for workflow in workflows:
        response += f"""
        ### {workflow['name']}
        **Description**: {workflow['description']}
        **Triggers**: {', '.join(workflow['triggers'][:3])}
        **Duration**: {workflow.get('expected_duration', 'Variable')}
        **Systems**: {', '.join(workflow.get('systems_involved', []))}
        
        """
    
    response += "\n💡 **Tip**: Just describe what you want to do, and I'll route you to the right workflow!"
    
    return response
```

#### Category-Based Filtering
```python
def _filter_workflows_by_category(self, workflows: List[Dict], category: str) -> List[Dict]:
    """Filter workflows by business category."""
    
    categories = {
        "sales": ["deal_risk_assessment", "customer_360_report"],
        "service": ["incident_to_resolution", "weekly_account_health_check"],
        "onboarding": ["new_customer_onboarding"],
        "monitoring": ["weekly_account_health_check", "deal_risk_assessment"],
        "reporting": ["customer_360_report", "weekly_account_health_check"]
    }
    
    if category.lower() in categories:
        category_workflows = categories[category.lower()]
        return [w for w in workflows if w['id'] in category_workflows]
    
    return workflows
```

### Usage Examples

```python
# User Input: "What workflows are available?"
# Tool Response:
"""
## Available Workflows

### At-Risk Deal Assessment
**Description**: Comprehensive analysis of deals at risk with multi-system blocker identification
**Triggers**: check for at-risk deals, identify risky opportunities, deal risk assessment
**Duration**: 2-5 minutes
**Systems**: Salesforce, ServiceNow, Jira

### Incident to Resolution Workflow
**Description**: Complete incident lifecycle from Salesforce case to ServiceNow incident
**Triggers**: create incident from case, escalate to incident management
**Duration**: 3-7 minutes
**Systems**: Salesforce, ServiceNow, Jira

### Customer 360 Comprehensive Report
**Description**: Generate comprehensive customer view aggregating data from all systems
**Triggers**: generate customer report, customer 360 view
**Duration**: 2-4 minutes
**Systems**: Salesforce, ServiceNow, Jira

💡 **Tip**: Just describe what you want to do, and I'll route you to the right workflow!
"""

# User Input: "Show me sales workflows"
# Tool Response: (Filtered list showing only sales-related workflows)
```

## Tool Integration Patterns

### Error Handling Strategy

```python
async def _call_agent_with_fallback(self, agent_name: str, instruction: str, context: Dict = None) -> Any:
    """Call agent with comprehensive error handling and fallback."""
    
    try:
        # Primary agent call
        result = await self.call_agent(agent_name, instruction, context)
        return result
        
    except AgentUnavailableError:
        # Agent offline - provide graceful degradation
        return self._handle_agent_offline(agent_name, instruction)
        
    except TimeoutError:
        # Timeout - suggest checking status later
        return self._handle_timeout_error(instruction)
        
    except ValidationError as e:
        # Input validation failed
        return self._handle_validation_error(str(e))
        
    except Exception as e:
        # Unexpected error - log and provide user-friendly message
        logger.error(f"Workflow tool error: {e}", exc_info=True)
        return self._handle_unexpected_error(str(e))
```

### Context Management

```python
def _extract_context_from_state(self, state_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Extract relevant context for workflow execution."""
    
    return {
        # User context
        "user_id": state_snapshot.get("user_id"),
        "session_id": state_snapshot.get("session_id"),
        "user_preferences": state_snapshot.get("user_preferences", {}),
        
        # Conversation context
        "recent_messages": state_snapshot.get("messages", [])[-5:],  # Last 5 messages
        "current_thread": state_snapshot.get("thread_id"),
        
        # System context
        "agent_states": state_snapshot.get("agent_states", {}),
        "active_tools": state_snapshot.get("active_tools", []),
        
        # Workflow context
        "triggered_by": "orchestrator",
        "execution_timestamp": datetime.utcnow().isoformat()
    }
```

### Performance Optimization

```python
class WorkflowToolCache:
    """Cache for workflow tool responses to improve performance."""
    
    def __init__(self, ttl: int = 300):  # 5 minutes TTL
        self.cache = {}
        self.ttl = ttl
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached response if still valid."""
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return data
            else:
                del self.cache[key]
        return None
    
    def set(self, key: str, value: Any):
        """Cache response with timestamp."""
        self.cache[key] = (value, time.time())
    
    def invalidate_pattern(self, pattern: str):
        """Invalidate cache entries matching pattern."""
        keys_to_remove = [k for k in self.cache.keys() if pattern in k]
        for key in keys_to_remove:
            del self.cache[key]

# Usage in tools
tool_cache = WorkflowToolCache()

async def _run(self, **kwargs):
    cache_key = f"workflow_list_{kwargs.get('category', 'all')}"
    
    # Check cache first
    cached_result = tool_cache.get(cache_key)
    if cached_result:
        return cached_result
    
    # Execute and cache result
    result = await self._execute_operation(**kwargs)
    tool_cache.set(cache_key, result)
    
    return result
```

## Security and Validation

### Input Sanitization

```python
def _sanitize_workflow_input(self, params: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize and validate workflow input parameters."""
    
    sanitized = {}
    
    for key, value in params.items():
        # Remove potentially dangerous characters
        if isinstance(value, str):
            # Basic sanitization
            sanitized_value = re.sub(r'[<>"\';]', '', value)
            # Length limits
            sanitized_value = sanitized_value[:1000]
            sanitized[key] = sanitized_value
        elif isinstance(value, (int, float)):
            # Numeric validation
            sanitized[key] = max(0, min(value, 1000000))
        elif isinstance(value, dict):
            # Recursive sanitization for nested objects
            sanitized[key] = self._sanitize_workflow_input(value)
        else:
            sanitized[key] = value
    
    return sanitized
```

### Permission Validation

```python
def _validate_workflow_permissions(self, workflow_id: str, context: Dict[str, Any]) -> bool:
    """Validate user has permission to execute workflow."""
    
    # Get user roles from context
    user_roles = context.get("user_context", {}).get("roles", [])
    
    # Define workflow permission requirements
    workflow_permissions = {
        "deal_risk_assessment": ["sales_manager", "sales_rep", "admin"],
        "incident_to_resolution": ["support_agent", "admin"],
        "customer_360_report": ["account_manager", "sales_rep", "admin"],
        "weekly_account_health_check": ["manager", "admin"],
        "new_customer_onboarding": ["customer_success", "admin"]
    }
    
    required_roles = workflow_permissions.get(workflow_id, ["admin"])
    
    # Check if user has any required role
    return any(role in user_roles for role in required_roles)
```

## Monitoring and Analytics

### Tool Usage Tracking

```python
class WorkflowToolMetrics:
    """Track workflow tool usage and performance metrics."""
    
    def __init__(self):
        self.usage_stats = {
            "executions": {},
            "failures": {},
            "response_times": {},
            "user_patterns": {}
        }
    
    def record_execution(self, tool_name: str, workflow_id: str, duration: float, success: bool):
        """Record tool execution metrics."""
        
        # Track usage counts
        key = f"{tool_name}:{workflow_id}"
        self.usage_stats["executions"][key] = self.usage_stats["executions"].get(key, 0) + 1
        
        # Track failures
        if not success:
            self.usage_stats["failures"][key] = self.usage_stats["failures"].get(key, 0) + 1
        
        # Track response times
        if key not in self.usage_stats["response_times"]:
            self.usage_stats["response_times"][key] = []
        self.usage_stats["response_times"][key].append(duration)
    
    def get_usage_report(self) -> Dict[str, Any]:
        """Generate usage analytics report."""
        
        report = {
            "most_used_workflows": self._get_top_workflows(),
            "average_response_times": self._calculate_avg_response_times(),
            "failure_rates": self._calculate_failure_rates(),
            "usage_trends": self._analyze_usage_trends()
        }
        
        return report
```

### Health Monitoring

```python
async def check_workflow_tools_health() -> Dict[str, Any]:
    """Check health of workflow tool integration."""
    
    health_status = {
        "workflow_agent_connectivity": False,
        "template_availability": False,
        "execution_capability": False,
        "last_check": datetime.utcnow().isoformat()
    }
    
    try:
        # Test agent connectivity
        ping_result = await call_agent("workflow-agent", "ping", timeout=5)
        health_status["workflow_agent_connectivity"] = bool(ping_result)
        
        # Test template listing
        templates = await call_agent("workflow-agent", "list templates", timeout=10)
        health_status["template_availability"] = len(templates) > 0
        
        # Test execution capability (dry run)
        test_result = await call_agent("workflow-agent", "validate system", timeout=15)
        health_status["execution_capability"] = "error" not in test_result.lower()
        
    except Exception as e:
        logger.error(f"Workflow tools health check failed: {e}")
        health_status["error"] = str(e)
    
    return health_status
```

## Best Practices

### Tool Design

1. **Intelligent Routing**: Use multiple detection methods (keyword + LLM) for robust workflow identification
2. **Graceful Degradation**: Provide useful responses even when agents are unavailable
3. **Context Preservation**: Maintain conversation state across workflow execution
4. **User Experience**: Optimize for conversational, natural language interaction

### Performance

1. **Caching Strategy**: Cache static responses (workflow lists) with appropriate TTL
2. **Async Execution**: Use async patterns for long-running workflow operations
3. **Resource Limits**: Implement timeouts and size limits for tool operations
4. **Connection Pooling**: Reuse agent connections for better performance

### Security

1. **Input Validation**: Sanitize all user inputs before processing
2. **Permission Checks**: Validate user permissions for workflow execution
3. **Audit Logging**: Log all tool operations for security and compliance
4. **Error Handling**: Never expose internal system details in error messages

### Monitoring

1. **Comprehensive Metrics**: Track usage, performance, and failure patterns
2. **Health Checks**: Implement proactive health monitoring
3. **User Analytics**: Understand usage patterns for optimization
4. **Error Tracking**: Monitor and alert on tool failures

## Related Documentation

- [Workflow Agent README](../../src/agents/workflow/README.md)
- [Workflow Engine Architecture](workflow-engine.md)
- [Workflow Templates Guide](../guides/workflow-templates.md)
- [A2A Protocol](../protocols/a2a-protocol.md)
- [Multi-Agent Architecture](../architecture/multi-agent-architecture.md)