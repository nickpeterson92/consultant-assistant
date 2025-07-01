"""Workflow tools for the orchestrator - handles both sync and async workflows"""

from typing import Dict, Any, Optional
from datetime import datetime
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from src.utils.logging import get_logger
from src.orchestrator.agent_registry import AgentRegistry
from src.a2a import A2AClient, A2ATask
from src.agents.workflow.templates import WorkflowTemplates
from src.agents.workflow.models import StepType

logger = get_logger("workflow_tools")


async def call_agent(agent_name: str, instruction: str, context: Optional[Dict[str, Any]] = None, state_snapshot: Optional[Dict[str, Any]] = None) -> Any:
    """Helper function to call an agent via A2A protocol
    
    Args:
        agent_name: Name of the agent to call
        instruction: Instruction for the agent
        context: Additional context for the agent
        state_snapshot: State snapshot from orchestrator to propagate
    """
    logger.info("workflow_tools_calling_agent",
               component="workflow_tools",
               operation="call_agent",
               agent_name=agent_name,
               instruction_preview=instruction[:100] if instruction else "",
               has_context=bool(context),
               has_state_snapshot=bool(state_snapshot))
    
    registry = AgentRegistry()
    agent = registry.get_agent(agent_name)
    
    if not agent:
        logger.error("workflow_tools_agent_not_found",
                    component="workflow_tools",
                    operation="call_agent",
                    agent_name=agent_name,
                    available_agents=[a.name for a in registry.list_agents()])
        raise ValueError(f"Agent '{agent_name}' not found in registry")
    
    logger.info("workflow_tools_agent_found",
               component="workflow_tools",
               operation="call_agent",
               agent_name=agent_name,
               agent_endpoint=agent.endpoint)
    
    # Create A2A task with state snapshot
    task = A2ATask(
        id=f"workflow_{agent_name}_{int(datetime.now().timestamp())}",
        instruction=instruction,
        context=context or {},
        state_snapshot=state_snapshot or {}  # Use provided state or empty dict
    )
    
    logger.info("workflow_tools_a2a_task_created",
               component="workflow_tools",
               operation="call_agent",
               task_id=task.id,
               agent_name=agent_name,
               endpoint=agent.endpoint + "/a2a")
    
    # Execute A2A call
    try:
        async with A2AClient() as client:
            endpoint = agent.endpoint + "/a2a"
            logger.info("workflow_tools_a2a_call_start",
                       component="workflow_tools",
                       operation="call_agent",
                       task_id=task.id,
                       endpoint=endpoint)
            
            result = await client.process_task(endpoint=endpoint, task=task)
            
            logger.info("workflow_tools_a2a_call_complete",
                       component="workflow_tools",
                       operation="call_agent",
                       task_id=task.id,
                       agent_name=agent_name,
                       result_type=type(result).__name__,
                       has_artifacts=bool(result.get("artifacts")),
                       result_preview=str(result)[:200] if result else "")
            
            # Extract response from artifacts
            if result.get("artifacts"):
                artifact = result["artifacts"][0]
                extracted = artifact.get("content", artifact)
                logger.info("workflow_tools_a2a_artifact_extracted",
                           component="workflow_tools",
                           operation="call_agent",
                           task_id=task.id,
                           artifact_content_preview=str(extracted)[:200] if extracted else "")
                return extracted
            
            return result
    except Exception as e:
        logger.error("workflow_tools_a2a_call_failed",
                    component="workflow_tools",
                    operation="call_agent",
                    task_id=task.id,
                    agent_name=agent_name,
                    endpoint=agent.endpoint + "/a2a",
                    error=str(e),
                    error_type=type(e).__name__)
        raise


class WorkflowExecutionTool(BaseTool):
    """Tool for executing workflows - decides between sync and async execution"""
    
    name: str = "execute_workflow"
    description: str = """Execute a multi-step workflow. Use this when:
    - User asks for complex multi-step operations
    - Tasks need to span multiple systems
    - Operations have dependencies between steps
    Examples: risk assessment, incident resolution, customer 360 report"""
    
    class Input(BaseModel):
        instruction: str = Field(description="The user's original instruction")
        workflow_hint: Optional[str] = Field(
            None, 
            description="Optional hint about which workflow to use"
        )
    
    args_schema: type = Input  # pyright: ignore[reportIncompatibleVariableOverride]
    
    def _run(self, instruction: str, workflow_hint: Optional[str] = None) -> str:
        """Execute workflow synchronously if possible, delegate to agent if async needed"""
        raise NotImplementedError("Use async version")
    
    async def _arun(self, instruction: str, workflow_hint: Optional[str] = None) -> str:
        """Execute workflow - sync for simple, async for complex"""
        try:
            # Detect workflow type from instruction
            workflow_name = self._detect_workflow(instruction, workflow_hint)
            
            if not workflow_name:
                return "No matching workflow found for this request. Please be more specific."
            
            # Get workflow definition
            workflow_def = WorkflowTemplates.get_all_templates().get(workflow_name)
            if not workflow_def:
                return f"Workflow '{workflow_name}' not found"
            
            # Check if workflow has async steps (waits, human approval, etc)
            has_async_steps = self._has_async_steps(workflow_def)
            
            logger.info("workflow_execution_requested",
                       workflow_name=workflow_name,
                       is_async=has_async_steps,
                       instruction_preview=instruction[:100])
            
            if has_async_steps:
                # Delegate to workflow agent for async execution
                result = await call_agent(
                    agent_name="workflow_agent",
                    instruction=instruction,
                    context={"workflow_hint": workflow_name}
                )
                
                # Extract meaningful response from agent result
                if isinstance(result, dict):
                    if result.get("status") == "waiting":
                        return f"Workflow '{workflow_name}' has been started and is waiting for approval/input. Instance ID: {result.get('instance_id')}"
                    elif result.get("status") == "completed":
                        return f"Workflow '{workflow_name}' completed successfully. {result.get('summary', '')}"
                    else:
                        return f"Workflow '{workflow_name}' status: {result.get('status')}. {result.get('summary', '')}"
                else:
                    return str(result)
            else:
                # Execute synchronously using simplified flow
                return await self._execute_sync_workflow(workflow_def, instruction)
                
        except Exception as e:
            logger.error("workflow_execution_error",
                        error=str(e),
                        error_type=type(e).__name__)
            return f"Error executing workflow: {str(e)}"
    
    def _detect_workflow(self, instruction: str, hint: Optional[str] = None) -> Optional[str]:
        """Detect which workflow to use based on instruction"""
        if hint:
            return hint
            
        instruction_lower = instruction.lower()
        
        # Keyword-based detection
        if any(word in instruction_lower for word in ["risk", "at-risk", "deal health", "opportunity health"]):
            return "deal_risk_assessment"
        elif any(word in instruction_lower for word in ["incident", "resolution", "support case"]):
            return "incident_to_resolution"
        elif any(word in instruction_lower for word in ["360", "everything about", "complete view", "all information"]):
            return "customer_360_report"
        elif any(word in instruction_lower for word in ["health check", "account health", "key accounts"]):
            return "weekly_account_health_check"
        elif any(word in instruction_lower for word in ["onboarding", "new customer", "setup"]):
            return "new_customer_onboarding"
        
        return None
    
    def _has_async_steps(self, workflow_def) -> bool:
        """Check if workflow has async steps that require the workflow agent"""
        for step in workflow_def.steps.values():
            if step.type in [StepType.WAIT, StepType.HUMAN]:
                return True
            if step.wait_until or step.wait_for_event:
                return True
        return False
    
    async def _execute_sync_workflow(self, workflow_def, instruction: str) -> str:
        """Execute simple workflow synchronously"""
        results = []
        
        logger.info("executing_sync_workflow",
                   workflow_name=workflow_def.name,
                   steps=len(workflow_def.steps))
        
        # For simple workflows, execute steps in sequence
        # This is a simplified version - the full workflow agent handles complex flows
        for step_id, step in workflow_def.steps.items():
            if step.type == StepType.ACTION and step.agent:
                try:
                    # Pass the original instruction to the agent
                    agent_instruction = instruction
                    if step.instruction:
                        # Use step instruction as guidance but include original
                        agent_instruction = f"{step.instruction}. Context: {instruction}"
                    
                    logger.info("executing_workflow_step",
                               step_id=step_id,
                               agent=step.agent)
                    
                    result = await call_agent(
                        agent_name=step.agent,
                        instruction=agent_instruction,
                        context={"workflow": workflow_def.name, "step": step_id}
                    )
                    
                    results.append(f"{step.name}: Completed")
                    
                except Exception as e:
                    logger.error("workflow_step_error",
                                step_id=step_id,
                                error=str(e))
                    results.append(f"{step.name}: Failed - {str(e)}")
        
        return f"Workflow '{workflow_def.name}' executed:\n" + "\n".join(results)


class WorkflowStatusTool(BaseTool):
    """Tool for checking workflow status"""
    
    name: str = "check_workflow_status"
    description: str = "Check the status of a running workflow by its instance ID"
    
    class Input(BaseModel):
        instance_id: str = Field(description="The workflow instance ID to check")
    
    args_schema: type = Input  # pyright: ignore[reportIncompatibleVariableOverride]
    
    def _run(self, instance_id: str) -> str:
        raise NotImplementedError("Use async version")
    
    async def _arun(self, instance_id: str) -> str:
        """Check workflow status via the workflow agent"""
        try:
            result = await call_agent(
                agent_name="workflow_agent",
                instruction=f"Check status of workflow instance {instance_id}",
                context={"action": "status_check", "instance_id": instance_id}
            )
            
            if isinstance(result, dict):
                status = result.get("status", "unknown")
                summary = result.get("summary", "")
                return f"Workflow {instance_id} status: {status}. {summary}"
            else:
                return str(result)
                
        except Exception as e:
            logger.error("workflow_status_check_error",
                        instance_id=instance_id,
                        error=str(e))
            return f"Error checking workflow status: {str(e)}"


class WorkflowListTool(BaseTool):
    """Tool for listing available workflows"""
    
    name: str = "list_workflows"
    description: str = "List all available workflow templates"
    
    def _run(self) -> str:
        """List available workflows"""
        templates = WorkflowTemplates.get_all_templates()
        
        result = "Available workflows:\n\n"
        for name, workflow in templates.items():
            result += f"**{name}**\n"
            result += f"  Description: {workflow.description}\n"
            result += f"  Trigger: {workflow.trigger.get('type', 'manual')}\n\n"
        
        return result
    
    async def _arun(self) -> str:
        """Async version just calls sync"""
        return self._run()


# Export all workflow tools
WORKFLOW_TOOLS = [
    WorkflowExecutionTool(),
    WorkflowStatusTool(),
    WorkflowListTool()
]