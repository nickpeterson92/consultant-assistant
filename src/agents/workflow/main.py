"""Workflow Agent - Uses compiled LangGraph workflows"""

import os
import asyncio
import argparse
import json
from typing import Dict, Any, Optional

from dotenv import load_dotenv

from src.a2a import A2AServer, AgentCard
from src.utils.logging import get_logger
from src.utils.config import get_llm_config
from src.utils.llm import create_azure_openai_chat
from langchain_core.messages import HumanMessage, SystemMessage

from .workflow_manager import WorkflowManager

# Initialize logger
logger = get_logger("workflow")

# Load environment variables
load_dotenv()


class WorkflowA2AHandler:
    """Simplified A2A handler using compiled workflows"""
    
    def __init__(self):
        self.workflow_manager = WorkflowManager()
        self.llm = create_azure_openai_chat()
    
    async def process_task(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process A2A task for workflow execution"""
        # Initialize task_id for use in except block
        task_id = "unknown"
        
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
            
            # Check if this is a resume attempt for an interrupted workflow
            is_resume = False
            workflow_name = self.workflow_manager.get_interrupted_workflow(task_id)
            
            if workflow_name:
                # This is a resume attempt
                is_resume = True
                logger.info("resuming_interrupted_workflow",
                           component="workflow",
                           workflow_name=workflow_name,
                           thread_id=task_id)
            
            if not is_resume:
                # Select workflow based on instruction
                workflow_name = self.workflow_manager.select_workflow(instruction)
                
                if not workflow_name:
                    # Use LLM to determine workflow
                    workflow_name = await self._select_workflow_with_llm(instruction)
                
                if not workflow_name:
                    return {
                        "artifacts": [{
                            "id": f"workflow-response-{task_id}",
                            "task_id": task_id,
                            "content": "No matching workflow found for this instruction",
                            "content_type": "text/plain"
                        }],
                        "status": "completed"
                    }
            
            # Prepare context
            workflow_context = {
                **context,
                "orchestrator_state_snapshot": state_snapshot,
                "original_instruction": instruction
            }
            
            # For new_customer_onboarding, let the workflow handle extraction
            # This ensures we use actual Salesforce data, not guessed values
            if workflow_name == "new_customer_onboarding":
                logger.info("workflow_will_extract_details",
                          component="workflow",
                          workflow_name=workflow_name,
                          instruction_preview=instruction[:100])
            
            # Execute workflow
            # At this point, workflow_name is guaranteed to be non-None due to the check above
            assert workflow_name is not None  # Type assertion for type checker
            
            if is_resume:
                # For resume, pass the human input as the instruction
                result = await self.workflow_manager.resume_workflow(
                    workflow_name=workflow_name,
                    human_input=instruction,
                    thread_id=task_id
                )
            else:
                result = await self.workflow_manager.execute_workflow(
                    workflow_name=workflow_name,
                    instruction=instruction,
                    context=workflow_context,
                    thread_id=task_id
                )
            
            # Check if workflow was interrupted for human input
            state = result.get("__interrupt__")
            if state:
                # Workflow needs human input
                interrupt_data = state if isinstance(state, dict) else {}
                logger.info("workflow_interrupted_for_human",
                           component="workflow",
                           task_id=task_id,
                           interrupt_data=interrupt_data)
                
                return {
                    "artifacts": [{
                        "id": f"workflow-interrupt-{task_id}",
                        "task_id": task_id,
                        "content": f"WORKFLOW_HUMAN_INPUT_REQUIRED:{json.dumps(interrupt_data)}",
                        "content_type": "text/plain"
                    }],
                    "status": "interrupted",
                    "metadata": {
                        "workflow_name": workflow_name,
                        "thread_id": task_id,
                        "interrupt_data": interrupt_data
                    }
                }
            
            # Generate report from results
            report = await self._generate_report(workflow_name, result)
            
            logger.info("workflow_a2a_task_complete",
                       component="workflow",
                       task_id=task_id,
                       workflow_name=workflow_name,
                       status=result.get("status"))
            
            return {
                "artifacts": [{
                    "id": f"workflow-response-{task_id}",
                    "task_id": task_id,
                    "content": report,
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
    
    async def _select_workflow_with_llm(self, instruction: str) -> Optional[str]:
        """Use LLM to select appropriate workflow"""
        workflows = self.workflow_manager.list_workflows()
        
        system_msg = f"""You are a workflow routing expert. Based on the user instruction, 
        determine which workflow template to use. Available workflows:
        {json.dumps(workflows, indent=2)}
        
        Respond with ONLY the workflow key or 'none' if no workflow matches."""
        
        response = await self.llm.ainvoke([
            SystemMessage(content=system_msg),
            HumanMessage(content=f"Instruction: {instruction}")
        ])
        
        content = response.content
        workflow_name = content.strip() if isinstance(content, str) else str(content).strip()
        return workflow_name if workflow_name != "none" else None
    
    async def _extract_parameter(self, instruction: str, prompt: str) -> str:
        """Extract a parameter from instruction using LLM"""
        enhanced_prompt = f"{prompt}\n\nIMPORTANT: If you cannot find the requested information, return exactly 'NONE' (without quotes)."
        response = await self.llm.ainvoke([
            SystemMessage(content=enhanced_prompt),
            HumanMessage(content=instruction)
        ])
        content = response.content
        return content.strip() if isinstance(content, str) else str(content).strip()
    
    async def _generate_report(self, workflow_name: str, result: Dict[str, Any]) -> str:
        """Generate a report from workflow results"""
        if result.get("status") == "completed":
            # Check for compiled results
            step_results = result.get("step_results", {})
            if step_results:
                report_prompt = f"""You are a business analyst creating a detailed report from workflow execution results.
                
Workflow: {workflow_name}
Results: {json.dumps(step_results, indent=2)}

Generate a comprehensive report that includes:
1. Executive Summary
2. Key Findings
3. Detailed Analysis of each result
4. Recommended Actions
5. Next Steps

Format the report in a clear, professional manner using markdown. Focus on actionable insights."""
                
                response = await self.llm.ainvoke([HumanMessage(content=report_prompt)])
                # Ensure we return a string
                content = response.content
                return str(content) if content else f"Workflow {workflow_name} completed successfully."
            else:
                return f"Workflow {workflow_name} completed successfully."
        elif result.get("status") == "failed":
            return f"Workflow {workflow_name} failed: {result.get('error', 'Unknown error')}"
        else:
            return f"Workflow {workflow_name} status: {result.get('status')}"
    
    async def get_agent_card(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return agent capabilities card"""
        workflows = self.workflow_manager.list_workflows()
        
        return {
            "name": "workflow-agent",
            "version": "2.0.0",
            "description": "Executes complex multi-step workflows using compiled LangGraph graphs",
            "capabilities": [
                "Execute predefined workflow templates",
                "Native LangGraph human-in-the-loop support",
                "Automatic state persistence and recovery",
                "Parallel and conditional execution",
                "Cross-system orchestration"
            ],
            "endpoints": {
                "process_task": "/a2a",
                "agent_card": "/a2a/agent-card"
            },
            "communication_modes": ["sync", "async"],
            "metadata": {
                "available_workflows": list(workflows.values())
            }
        }


async def run_workflow_server(port: int = 8004):
    """Run the workflow agent A2A server"""
    # Create handler
    handler = WorkflowA2AHandler()
    
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