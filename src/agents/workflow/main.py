"""Workflow Agent - Executes complex multi-step workflows asynchronously"""

import os
import asyncio
import argparse
import json
from typing import Annotated, Dict, Any, Optional
from typing_extensions import TypedDict

from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from src.a2a import A2AServer, AgentCard
from src.utils.logging import get_logger
from src.utils.storage import get_async_store_adapter
from src.utils.config import get_llm_config
from src.utils.llm import create_azure_openai_chat
from src.utils.agents.prompts.workflow_prompts import workflow_agent_sys_msg

from .engine import WorkflowEngine
from .templates import WorkflowTemplates
from .models import WorkflowStatus

# Initialize logger
logger = get_logger("workflow")

# Load environment variables
load_dotenv()


class WorkflowState(TypedDict):
    """State for workflow agent"""
    messages: Annotated[list, add_messages]
    workflow_name: Optional[str]
    workflow_instance_id: Optional[str]
    original_instruction: str
    execution_status: Optional[str]
    orchestrator_state_snapshot: Optional[Dict[str, Any]]  # State from orchestrator for sub-agent calls
    
    
def create_workflow_graph():
    """Build the workflow agent graph"""
    
    # Initialize storage and engine
    storage = get_async_store_adapter()
    workflow_engine = WorkflowEngine(storage)
    templates = WorkflowTemplates()
    
    async def workflow_router(state: WorkflowState, config: RunnableConfig):
        """Determine which workflow to execute based on instruction"""
        instruction = state.get("original_instruction", "")
        
        # For now, simple keyword matching - can be enhanced with LLM
        workflow_name = None
        
        # Check for workflow keywords
        instruction_lower = instruction.lower()
        
        if "risk" in instruction_lower and ("deal" in instruction_lower or "opportunity" in instruction_lower):
            workflow_name = "deal_risk_assessment"
        elif "incident" in instruction_lower and "resolution" in instruction_lower:
            workflow_name = "incident_to_resolution"
        elif "360" in instruction_lower or "everything about" in instruction_lower:
            workflow_name = "customer_360_report"
        elif "health check" in instruction_lower:
            workflow_name = "weekly_account_health_check"
        elif "onboarding" in instruction_lower:
            workflow_name = "new_customer_onboarding"
        else:
            # Use LLM to determine workflow
            llm = create_azure_openai_chat()
            system_msg = """You are a workflow routing expert. Based on the user instruction, 
            determine which workflow template to use. Available workflows:
            - deal_risk_assessment: For checking at-risk opportunities
            - incident_to_resolution: For managing support incidents
            - customer_360_report: For comprehensive customer information
            - weekly_account_health_check: For account health analysis
            - new_customer_onboarding: For new customer setup
            
            Respond with ONLY the workflow name or 'none' if no workflow matches."""
            
            response = await llm.ainvoke([
                SystemMessage(content=system_msg),
                HumanMessage(content=f"Instruction: {instruction}")
            ])
            
            workflow_name = response.content.strip()
            if workflow_name == "none":
                workflow_name = None
        
        state["workflow_name"] = workflow_name
        return state
    
    async def execute_workflow(state: WorkflowState, config: RunnableConfig):
        """Execute the identified workflow"""
        workflow_name = state.get("workflow_name")
        instruction = state.get("original_instruction", "")
        
        if not workflow_name:
            state["messages"].append(
                SystemMessage(content="No matching workflow found for this instruction")
            )
            state["execution_status"] = "no_workflow_found"
            return state
        
        try:
            # Get workflow template
            workflow_def = getattr(templates, workflow_name)()
            
            # Set the original instruction as a workflow variable
            workflow_def.variables["original_instruction"] = instruction
            
            logger.info("workflow_agent_executing",
                       component="workflow",
                       workflow_name=workflow_name,
                       instruction_preview=instruction[:100])
            
            # Use LLM to extract parameters based on workflow requirements
            param_extraction_prompts = {
                "customer_360_report": """Extract the account/company name from this instruction. 
                                       Return ONLY the account name, nothing else.
                                       If no account name is found, return 'NONE'.""",
                "incident_to_resolution": """Extract the case ID or incident ID from this instruction.
                                           Return ONLY the ID, nothing else.
                                           If no ID is found, return 'NONE'.""",
                "new_customer_onboarding": """Extract the opportunity name or account name from this instruction.
                                            Look for phrases like 'opportunity X', 'oppty X', 'deal X', or account/customer names.
                                            Return ONLY the opportunity or account name, nothing else.
                                            If not found, return 'NONE'."""
            }
            
            initial_vars = {
                "original_instruction": instruction,
                "orchestrator_state_snapshot": state.get("orchestrator_state_snapshot", {})
            }
            
            # Add any context variables passed from the caller
            context = state.get("context", {})
            initial_vars.update(context)
            
            # Extract parameters using LLM if needed
            if workflow_name in param_extraction_prompts:
                llm = create_azure_openai_chat()
                prompt = param_extraction_prompts[workflow_name]
                extraction_response = await llm.ainvoke([
                    SystemMessage(content=prompt),
                    HumanMessage(content=instruction)
                ])
                extracted_value = extraction_response.content.strip()
                
                if extracted_value != "NONE":
                    if workflow_name == "customer_360_report":
                        initial_vars["account_name"] = extracted_value
                    elif workflow_name == "incident_to_resolution":
                        initial_vars["case_id"] = extracted_value
                    elif workflow_name == "new_customer_onboarding":
                        initial_vars["opportunity_name"] = extracted_value
            
            instance = await workflow_engine.execute_workflow(
                definition=workflow_def,
                initial_variables=initial_vars,
                triggered_by="workflow_agent"
            )
            
            state["workflow_instance_id"] = instance.id
            state["execution_status"] = instance.status.value
            
            # Create response message
            if instance.status == WorkflowStatus.COMPLETED:
                # Store compiled results in state
                if instance.variables.get("compiled_results"):
                    state["compiled_results"] = instance.variables["compiled_results"]
                    
                    # Use LLM to generate a detailed report from the compiled results
                    llm = create_azure_openai_chat()
                    
                    report_prompt = f"""You are a business analyst creating a detailed report from workflow execution results.
                    
Workflow: {workflow_name}
Results: {json.dumps(instance.variables.get("compiled_results", {}), indent=2)}

Generate a comprehensive report that includes:
1. Executive Summary
2. Key Findings
3. Detailed Analysis of each result
4. Risk Assessment (if applicable)
5. Recommended Actions
6. Next Steps

Format the report in a clear, professional manner using markdown. Focus on actionable insights."""
                    
                    report_response = await llm.ainvoke([HumanMessage(content=report_prompt)])
                    report = report_response.content
                    
                    state["messages"].append(SystemMessage(content=report))
                    state["workflow_report"] = report
                else:
                    # Fallback if no compiled results
                    msg = f"Successfully executed {workflow_name} workflow.\nCompleted {len(instance.history)} steps."
                    state["messages"].append(SystemMessage(content=msg))
                    
            elif instance.status == WorkflowStatus.FAILED:
                msg = f"Workflow {workflow_name} failed: {instance.error}"
                state["messages"].append(SystemMessage(content=msg))
                
            elif instance.status == WorkflowStatus.WAITING:
                msg = f"Workflow {workflow_name} is waiting for external input/approval. Instance ID: {instance.id}"
                state["messages"].append(SystemMessage(content=msg))
                
            else:
                msg = f"Workflow {workflow_name} status: {instance.status.value}"
                state["messages"].append(SystemMessage(content=msg))
            
        except Exception as e:
            logger.error("workflow_execution_error",
                        component="workflow",
                        workflow_name=workflow_name,
                        error=str(e),
                        error_type=type(e).__name__)
            
            state["messages"].append(
                SystemMessage(content=f"Error executing workflow: {str(e)}")
            )
            state["execution_status"] = "error"
        
        return state
    
    async def check_workflow_status(state: WorkflowState, config: RunnableConfig):
        """Check status of a running workflow"""
        instance_id = state.get("workflow_instance_id")
        
        if not instance_id:
            return state
        
        try:
            instance = await workflow_engine.load_instance(instance_id)
            if instance:
                state["execution_status"] = instance.status.value
                
                msg = f"Workflow {instance.workflow_name} (ID: {instance.id}) status: {instance.status.value}"
                if instance.status == WorkflowStatus.COMPLETED:
                    msg += f"\nCompleted at: {instance.completed_at}"
                elif instance.current_step:
                    msg += f"\nCurrent step: {instance.current_step}"
                    
                state["messages"].append(SystemMessage(content=msg))
                
        except Exception as e:
            logger.error("workflow_status_check_error",
                        component="workflow",
                        instance_id=instance_id,
                        error=str(e))
        
        return state
    
    # Build graph
    graph_builder = StateGraph(WorkflowState)
    
    # Add nodes
    graph_builder.add_node("router", workflow_router)
    graph_builder.add_node("executor", execute_workflow)
    graph_builder.add_node("status_checker", check_workflow_status)
    
    # Add edges
    graph_builder.set_entry_point("router")
    graph_builder.add_edge("router", "executor")
    graph_builder.add_edge("executor", "status_checker")
    graph_builder.add_edge("status_checker", END)
    
    return graph_builder.compile()


# Build the graph at module level
workflow_graph = None  # Will be created when needed


class WorkflowA2AHandler:
    """Handles A2A protocol requests for the Workflow agent"""
    
    def __init__(self, graph):
        self.graph = graph
        self.templates = WorkflowTemplates()
        
    async def process_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process A2A task for workflow execution"""
        try:
            # Extract task data
            task_data = params.get("task", params)
            task_id = task_data.get("id", task_data.get("task_id", "unknown"))
            instruction = task_data.get("instruction", "")
            context = task_data.get("context", {})
            state_snapshot = task_data.get("state_snapshot", {})
            
            logger.info("workflow_a2a_task_start",
                       component="workflow",
                       task_id=task_id,
                       instruction_preview=instruction[:100])
            
            # Prepare initial state
            initial_state = {
                "messages": [HumanMessage(content=instruction)],
                "original_instruction": instruction,
                "workflow_name": None,
                "workflow_instance_id": None,
                "execution_status": None,
                "orchestrator_state_snapshot": state_snapshot,  # Pass through for sub-agent calls
                "context": context  # Pass context for parameter extraction
            }
            
            # Execute graph
            llm_config = get_llm_config()
            config = {
                "configurable": {
                    "thread_id": f"workflow-{task_id}",
                },
                "recursion_limit": llm_config.recursion_limit
            }
            
            result = await self.graph.ainvoke(initial_state, config)
            
            # Extract results
            workflow_name = result.get("workflow_name", "none")
            instance_id = result.get("workflow_instance_id", "none")
            status = result.get("execution_status", "unknown")
            
            # Debug logging
            logger.info("workflow_graph_result",
                       component="workflow",
                       task_id=task_id,
                       has_workflow_report="workflow_report" in result,
                       has_messages="messages" in result,
                       message_count=len(result.get("messages", [])),
                       status=status)
            
            # Extract the report content directly
            response_content = ""
            if status == "completed":
                # Check if we have a workflow report
                if result.get("workflow_report"):
                    # Get the report that was generated by the LLM
                    response_content = result["workflow_report"]
                elif result.get("messages"):
                    # Look for the report in the messages (it's added as a SystemMessage)
                    for msg in reversed(result.get("messages", [])):
                        if hasattr(msg, 'content') and len(getattr(msg, 'content', '')) > 200:
                            # Found a substantial message, likely the report
                            response_content = msg.content
                            break
                    
                    if not response_content:
                        # Fallback to simple completion message
                        response_content = f"Workflow {workflow_name} completed successfully. Instance ID: {instance_id}"
                else:
                    response_content = f"Workflow {workflow_name} completed. Instance ID: {instance_id}"
            elif status == "failed":
                response_content = f"Workflow {workflow_name} failed: {result.get('execution_status', 'Unknown error')}"
            else:
                response_content = f"Workflow {workflow_name} status: {status}"
            
            logger.info("workflow_a2a_task_complete",
                       component="workflow",
                       task_id=task_id,
                       workflow_name=workflow_name,
                       status=status)
            
            # Return the report directly as content, just like other agents do
            return {
                "artifacts": [{
                    "id": f"workflow-response-{task_id}",
                    "task_id": task_id,
                    "content": response_content,
                    "content_type": "text/plain"
                }],
                "status": "completed"
            }
            
        except Exception as e:
            logger.error("workflow_a2a_task_error",
                        component="workflow",
                        task_id=task_id,
                        error=str(e),
                        error_type=type(e).__name__)
            
            return {
                "artifacts": [{
                    "id": f"workflow-error-{task_id}",
                    "task_id": task_id,
                    "content": {"error": str(e)},
                    "content_type": "application/json"
                }],
                "status": "failed"
            }
    
    async def get_agent_card(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return agent capabilities card"""
        # List available workflows
        template_list = []
        for name, workflow in WorkflowTemplates.get_all_templates().items():
            template_list.append({
                "name": name,
                "description": workflow.description,
                "trigger": workflow.trigger
            })
        
        return {
            "name": "workflow-agent",
            "version": "1.0.0",
            "description": "Executes complex multi-step workflows across systems",
            "capabilities": [
                "Execute predefined workflow templates",
                "Handle asynchronous workflow execution",
                "Manage workflow state and resumption",
                "Coordinate multi-system operations",
                "Support human-in-the-loop workflows"
            ],
            "endpoints": {
                "process_task": "/a2a",
                "agent_card": "/a2a/agent-card"
            },
            "communication_modes": ["sync", "async"],
            "metadata": {
                "available_workflows": template_list
            }
        }


async def run_workflow_server(port: int = 8004):
    """Run the workflow agent A2A server"""
    global workflow_graph
    
    # Create graph if needed
    if workflow_graph is None:
        workflow_graph = create_workflow_graph()
    
    # Create handler
    handler = WorkflowA2AHandler(workflow_graph)
    
    # Create agent card
    agent_card_dict = await handler.get_agent_card({})
    agent_card = AgentCard(**agent_card_dict)
    
    # Create and run server
    server = A2AServer(agent_card, "localhost", port)
    server.register_handler("process_task", handler.process_task)
    server.register_handler("get_agent_card", handler.get_agent_card)
    
    # Start the server
    runner = await server.start()
    
    logger.info("workflow_agent_started",
                component="workflow",
                operation="startup",
                agent="workflow",
                host="localhost",
                port=port,
                endpoint=f"http://localhost:{port}")
    
    try:
        # Keep the server running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("workflow_agent_shutdown",
                    component="workflow",
                    operation="shutdown")
    finally:
        await server.stop(runner)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Workflow Agent Server")
    parser.add_argument("--port", type=int, default=8004,
                       help="Port to run the A2A server on (default: 8004)")
    args = parser.parse_args()
    
    asyncio.run(run_workflow_server(args.port))