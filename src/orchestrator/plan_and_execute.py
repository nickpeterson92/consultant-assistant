"""Simple plan-and-execute system for the orchestrator."""

import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from src.utils.logging import get_logger
from src.utils.agents.message_processing import estimate_message_tokens
from .state import OrchestratorState, ExecutionPlan, ExecutionTask, TaskStatus, TaskPriority

logger = get_logger()


class PlanAndExecuteManager:
    """Simple plan-and-execute manager that leverages existing infrastructure."""
    
    def __init__(self, llm, config: Optional[Dict[str, Any]] = None):
        self.llm = llm
        self.task_counter = 0
        self.config = config or {
            "max_tasks_per_plan": 8,
            "planning_temperature": 0.1,
            "routing_confidence_threshold": 0.7
        }
    
    def _generate_task_id(self) -> str:
        """Generate a unique task ID."""
        self.task_counter += 1
        return f"task_{self.task_counter}_{uuid.uuid4().hex[:8]}"
    
    def _generate_plan_id(self) -> str:
        """Generate a unique plan ID."""
        return f"plan_{uuid.uuid4().hex[:8]}"
    
    def _serialize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize context to ensure no LangChain objects leak into plan metadata."""
        if not context:
            return {}
        
        serialized_context = {}
        for key, value in context.items():
            if key == "messages" and isinstance(value, list):
                # Import here to avoid circular imports
                from src.utils.agents.message_processing.unified_serialization import serialize_messages_for_json
                serialized_context[key] = serialize_messages_for_json(value)
            else:
                serialized_context[key] = value
        
        return serialized_context
    
    async def create_plan(self, instruction: str, context: Dict[str, Any]) -> ExecutionPlan:
        """Create an execution plan from a user instruction."""
        
        # Get available agents and their capabilities
        available_agents = self._get_available_agents(context)
        
        # Build planning prompt
        planning_prompt = self._build_planning_prompt(instruction, available_agents, context)
        
        # Generate plan using LLM
        plan_data = await self._generate_plan_with_llm(planning_prompt, instruction)
        
        # Create execution plan
        plan_id = self._generate_plan_id()
        current_time = datetime.now().isoformat()
        
        execution_plan: ExecutionPlan = {
            "id": plan_id,
            "original_instruction": instruction,
            "tasks": plan_data["tasks"],
            "current_task_id": None,
            "status": TaskStatus.PENDING.value,
            "created_at": current_time,
            "completed_at": None,
            "metadata": {
                "context": self._serialize_context(context),
                "available_agents": available_agents,
                "planning_tokens": plan_data.get("tokens_used", 0)
            }
        }
        
        logger.info("execution_plan_created",
                   component="orchestrator",
                   plan_id=plan_id,
                   task_count=len(plan_data["tasks"]),
                   instruction_preview=instruction[:100])
        
        return execution_plan
    
    def _get_available_agents(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get available agents and their capabilities."""
        # Extract from context or use defaults
        return [
            {
                "name": "salesforce_agent",
                "description": "Handles Salesforce CRM operations - accounts, contacts, opportunities, leads, cases",
                "capabilities": ["get", "create", "update", "search", "analytics", "collaboration"]
            },
            {
                "name": "jira_agent", 
                "description": "Handles Jira issue tracking - bugs, stories, tasks, epics, sprints",
                "capabilities": ["get", "create", "update", "search", "analytics", "sprint_management"]
            },
            {
                "name": "servicenow_agent",
                "description": "Handles ServiceNow ITSM - incidents, changes, problems, requests",
                "capabilities": ["get", "create", "update", "search", "analytics", "workflow"]
            },
            {
                "name": "web_search",
                "description": "Searches the web for current information and answers",
                "capabilities": ["search", "lookup", "research"]
            }
        ]
    
    def _build_planning_prompt(self, instruction: str, agents: List[Dict[str, Any]], context: Dict[str, Any]) -> str:
        """Build the planning prompt for the LLM."""
        
        agents_info = "\n".join([
            f"- {agent['name']}: {agent['description']}"
            for agent in agents
        ])
        
        # Include relevant context from memory if available
        memory_context = ""
        if context.get("memory"):
            memory_context = f"\n\nRelevant context from memory:\n{json.dumps(context['memory'], indent=2)}"
        
        return f"""You are an expert task planner for a multi-agent system. Your job is to break down complex user requests into specific, actionable tasks that can be executed by specialized agents.

Available agents and their capabilities:
{agents_info}

User instruction: {instruction}
{memory_context}

Create a detailed execution plan by breaking down the instruction into specific tasks. Each task should:
1. Be specific and actionable
2. Specify which agent should handle it
3. Include any dependencies on other tasks
4. Have appropriate priority (low, medium, high, urgent)

Return your response as a JSON object with this structure:
{{
    "reasoning": "Your reasoning about how to break down this instruction",
    "tasks": [
        {{
            "content": "Specific task description",
            "agent": "agent_name",
            "priority": "high|medium|low|urgent",
            "depends_on": ["task_id1", "task_id2"]
        }}
    ]
}}

Guidelines:
- Start with information gathering tasks before action tasks
- Consider cross-system dependencies (e.g., get account info before creating related records)
- Use web search for any current information or research needed
- Be specific about what data to retrieve or actions to take
- Prioritize tasks that others depend on
- Maximum 8 tasks per plan to keep it manageable

IMPORTANT: Return only valid JSON, no additional text."""
    
    async def _generate_plan_with_llm(self, prompt: str, instruction: str) -> Dict[str, Any]:
        """Generate plan using LLM and parse the response."""
        
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=f"Create execution plan for: {instruction}")
        ]
        
        # Log token usage
        total_tokens = estimate_message_tokens(messages)
        logger.info("plan_generation_token_usage",
                   component="orchestrator",
                   operation="create_plan",
                   message_count=len(messages),
                   estimated_tokens=total_tokens,
                   token_limit=128000)
        
        response = await self.llm.ainvoke(messages)
        content = response.content
        
        try:
            # Parse JSON response
            plan_data = json.loads(content)
            
            # Convert to ExecutionTask objects with generated IDs
            tasks = []
            task_id_mapping = {}  # Map original indices to generated IDs
            
            for i, task_data in enumerate(plan_data["tasks"]):
                task_id = self._generate_task_id()
                task_id_mapping[i] = task_id
                
                # Parse priority
                priority_str = task_data.get("priority", "medium").lower()
                if priority_str == "urgent":
                    priority = TaskPriority.URGENT
                elif priority_str == "high":
                    priority = TaskPriority.HIGH
                elif priority_str == "low":
                    priority = TaskPriority.LOW
                else:
                    priority = TaskPriority.MEDIUM
                
                # Handle dependencies - convert indices to actual task IDs
                depends_on = []
                if "depends_on" in task_data:
                    for dep in task_data["depends_on"]:
                        if isinstance(dep, int) and dep < len(task_id_mapping):
                            depends_on.append(task_id_mapping[dep])
                        elif isinstance(dep, str) and dep in task_id_mapping:
                            depends_on.append(task_id_mapping[dep])
                
                task: ExecutionTask = {
                    "id": task_id,
                    "content": task_data["content"],
                    "status": TaskStatus.PENDING.value,
                    "priority": priority.value,
                    "agent": task_data.get("agent"),
                    "depends_on": depends_on,
                    "created_at": datetime.now().isoformat(),
                    "started_at": None,
                    "completed_at": None,
                    "result": None,
                    "error": None
                }
                tasks.append(task)
            
            return {
                "tasks": tasks,
                "tokens_used": total_tokens,
                "reasoning": plan_data.get("reasoning", "")
            }
            
        except json.JSONDecodeError as e:
            logger.error("plan_generation_json_error",
                        component="orchestrator",
                        error=str(e),
                        content_preview=content[:500])
            
            # Fallback: create a single task
            fallback_task: ExecutionTask = {
                "id": self._generate_task_id(),
                "content": f"Handle the following request: {instruction}",
                "status": TaskStatus.PENDING.value,
                "priority": TaskPriority.MEDIUM.value,
                "agent": None,  # Let the executor decide
                "depends_on": [],
                "created_at": datetime.now().isoformat(),
                "started_at": None,
                "completed_at": None,
                "result": None,
                "error": None
            }
            
            return {
                "tasks": [fallback_task],
                "tokens_used": total_tokens,
                "reasoning": "Fallback plan due to JSON parsing error"
            }
    
    async def replan(self, current_plan: ExecutionPlan, modification_request: str, 
                    context: Dict[str, Any]) -> ExecutionPlan:
        """Modify an existing plan based on user request."""
        
        # Get current plan status
        completed_tasks = [t for t in current_plan["tasks"] if t["status"] == TaskStatus.COMPLETED.value]
        pending_tasks = [t for t in current_plan["tasks"] if t["status"] == TaskStatus.PENDING.value]
        
        # Build replanning prompt
        replanning_prompt = self._build_replanning_prompt(
            current_plan, modification_request, completed_tasks, pending_tasks, context
        )
        
        # Generate updated plan
        updated_plan_data = await self._generate_replan_with_llm(
            replanning_prompt, modification_request, current_plan
        )
        
        # Update the plan
        current_plan["tasks"] = updated_plan_data["tasks"]
        current_plan["metadata"]["replan_count"] = current_plan["metadata"].get("replan_count", 0) + 1
        current_plan["metadata"]["last_replan_at"] = datetime.now().isoformat()
        current_plan["metadata"]["replan_reason"] = modification_request
        
        logger.info("execution_plan_updated",
                   component="orchestrator",
                   plan_id=current_plan["id"],
                   new_task_count=len(updated_plan_data["tasks"]),
                   modification_request=modification_request[:100])
        
        return current_plan
    
    def _build_replanning_prompt(self, current_plan: ExecutionPlan, modification_request: str,
                                completed_tasks: List[ExecutionTask], pending_tasks: List[ExecutionTask],
                                context: Dict[str, Any]) -> str:
        """Build the replanning prompt."""
        
        completed_summary = "\n".join([
            f"- {task['content']} (Status: {task['status']})"
            for task in completed_tasks
        ])
        
        pending_summary = "\n".join([
            f"- {task['content']} (Status: {task['status']}, Priority: {task['priority']})"
            for task in pending_tasks
        ])
        
        return f"""You are updating an existing execution plan based on user feedback.

Original instruction: {current_plan['original_instruction']}
User modification request: {modification_request}

Current plan status:
COMPLETED TASKS:
{completed_summary}

PENDING TASKS:
{pending_summary}

Please update the plan to incorporate the user's request. You can:
1. Add new tasks
2. Modify existing pending tasks
3. Remove pending tasks
4. Change task priorities
5. Update task dependencies

DO NOT modify or remove completed tasks.

Return your response as a JSON object with this structure:
{{
    "reasoning": "Your reasoning about the modifications",
    "tasks": [
        {{
            "content": "Task description",
            "agent": "agent_name",
            "priority": "high|medium|low|urgent",
            "depends_on": ["task_id1", "task_id2"]
        }}
    ]
}}

Include all tasks (both existing and new) in the tasks array. IMPORTANT: Return only valid JSON, no additional text."""
    
    async def _generate_replan_with_llm(self, prompt: str, modification_request: str, current_plan: ExecutionPlan) -> Dict[str, Any]:
        """Generate updated plan using LLM."""
        
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=f"Update the plan based on: {modification_request}")
        ]
        
        # Log token usage
        total_tokens = estimate_message_tokens(messages)
        logger.info("replan_generation_token_usage",
                   component="orchestrator",
                   operation="replan",
                   message_count=len(messages),
                   estimated_tokens=total_tokens,
                   token_limit=128000)
        
        response = await self.llm.ainvoke(messages)
        content = response.content
        
        try:
            # Parse JSON response
            plan_data = json.loads(content)
            
            # Convert to ExecutionTask objects (similar to create_plan)
            tasks = []
            task_id_mapping = {}
            
            for i, task_data in enumerate(plan_data["tasks"]):
                task_id = self._generate_task_id()
                task_id_mapping[i] = task_id
                
                # Parse priority
                priority_str = task_data.get("priority", "medium").lower()
                if priority_str == "urgent":
                    priority = TaskPriority.URGENT
                elif priority_str == "high":
                    priority = TaskPriority.HIGH
                elif priority_str == "low":
                    priority = TaskPriority.LOW
                else:
                    priority = TaskPriority.MEDIUM
                
                # Handle dependencies
                depends_on = []
                if "depends_on" in task_data:
                    for dep in task_data["depends_on"]:
                        if isinstance(dep, int) and dep < len(task_id_mapping):
                            depends_on.append(task_id_mapping[dep])
                        elif isinstance(dep, str) and dep in task_id_mapping:
                            depends_on.append(task_id_mapping[dep])
                
                task: ExecutionTask = {
                    "id": task_id,
                    "content": task_data["content"],
                    "status": TaskStatus.PENDING.value,
                    "priority": priority.value,
                    "agent": task_data.get("agent"),
                    "depends_on": depends_on,
                    "created_at": datetime.now().isoformat(),
                    "started_at": None,
                    "completed_at": None,
                    "result": None,
                    "error": None
                }
                tasks.append(task)
            
            return {
                "tasks": tasks,
                "tokens_used": total_tokens,
                "reasoning": plan_data.get("reasoning", "")
            }
            
        except json.JSONDecodeError as e:
            logger.error("replan_generation_json_error",
                        component="orchestrator",
                        error=str(e),
                        content_preview=content[:500])
            
            # Return existing pending tasks as fallback
            return {
                "tasks": [task for task in current_plan["tasks"] if task["status"] == TaskStatus.PENDING.value],
                "tokens_used": total_tokens,
                "reasoning": "Fallback: kept existing pending tasks due to JSON parsing error"
            }
    
    def get_next_task(self, plan: ExecutionPlan) -> Optional[ExecutionTask]:
        """Get the next task that can be executed (no unmet dependencies)."""
        
        # Get all completed task IDs
        completed_task_ids = {
            task["id"] for task in plan["tasks"] 
            if task["status"] == TaskStatus.COMPLETED.value
        }
        
        # Find pending tasks with no unmet dependencies
        ready_tasks = []
        for task in plan["tasks"]:
            if task["status"] == TaskStatus.PENDING.value:
                # Check if all dependencies are met
                unmet_deps = [dep for dep in task["depends_on"] if dep not in completed_task_ids]
                if not unmet_deps:
                    ready_tasks.append(task)
        
        if not ready_tasks:
            return None
        
        # Sort by priority (urgent > high > medium > low)
        priority_order = {
            TaskPriority.URGENT.value: 4,
            TaskPriority.HIGH.value: 3,
            TaskPriority.MEDIUM.value: 2,
            TaskPriority.LOW.value: 1
        }
        
        ready_tasks.sort(key=lambda t: priority_order.get(t["priority"], 2), reverse=True)
        return ready_tasks[0]
    
    def mark_task_in_progress(self, plan: ExecutionPlan, task_id: str) -> bool:
        """Mark a task as in progress."""
        for task in plan["tasks"]:
            if task["id"] == task_id:
                task["status"] = TaskStatus.IN_PROGRESS.value
                task["started_at"] = datetime.now().isoformat()
                plan["current_task_id"] = task_id
                return True
        return False
    
    def mark_task_completed(self, plan: ExecutionPlan, task_id: str, result: Dict[str, Any]) -> bool:
        """Mark a task as completed with result."""
        for task in plan["tasks"]:
            if task["id"] == task_id:
                task["status"] = TaskStatus.COMPLETED.value
                task["completed_at"] = datetime.now().isoformat()
                task["result"] = result
                if plan["current_task_id"] == task_id:
                    plan["current_task_id"] = None
                return True
        return False
    
    def mark_task_failed(self, plan: ExecutionPlan, task_id: str, error: str) -> bool:
        """Mark a task as failed with error."""
        for task in plan["tasks"]:
            if task["id"] == task_id:
                task["status"] = TaskStatus.FAILED.value
                task["completed_at"] = datetime.now().isoformat()
                task["error"] = error
                if plan["current_task_id"] == task_id:
                    plan["current_task_id"] = None
                return True
        return False
    
    def is_plan_complete(self, plan: ExecutionPlan) -> bool:
        """Check if all tasks in the plan are completed."""
        for task in plan["tasks"]:
            if task["status"] not in [TaskStatus.COMPLETED.value, TaskStatus.CANCELLED.value]:
                return False
        return True
    
    def get_plan_summary(self, plan: ExecutionPlan) -> str:
        """Get a summary of the current plan status."""
        total_tasks = len(plan["tasks"])
        completed_tasks = sum(1 for task in plan["tasks"] if task["status"] == TaskStatus.COMPLETED.value)
        failed_tasks = sum(1 for task in plan["tasks"] if task["status"] == TaskStatus.FAILED.value)
        pending_tasks = sum(1 for task in plan["tasks"] if task["status"] == TaskStatus.PENDING.value)
        in_progress_tasks = sum(1 for task in plan["tasks"] if task["status"] == TaskStatus.IN_PROGRESS.value)
        
        return f"""Plan Status:
- Total Tasks: {total_tasks}
- Completed: {completed_tasks}
- In Progress: {in_progress_tasks}
- Pending: {pending_tasks}
- Failed: {failed_tasks}

Current Task: {plan.get('current_task_id', 'None')}
Plan Status: {plan['status']}
"""

    async def should_create_plan(self, instruction: str, state: OrchestratorState) -> bool:
        """Simple LLM-based routing decision for planning."""
        
        # Skip if already in execution mode
        if state.get("execution_mode") == "executing":
            return False
        
        # Build minimal context
        context_info = self._build_routing_context(state)
        
        routing_prompt = f"""You are an expert at determining if a user request needs multi-step planning.

CONTEXT:
{context_info}

USER REQUEST: {instruction}

PLANNING NEEDED when request involves:
- Multiple sequential actions
- Cross-system coordination  
- Complex workflows with dependencies
- Project-like tasks

NORMAL CONVERSATION for:
- Simple queries or lookups
- Single-step operations
- Basic questions
- Status checks

Respond with only: "PLAN" or "NORMAL"
"""
        
        try:
            messages = [
                SystemMessage(content=routing_prompt),
                HumanMessage(content="Make routing decision")
            ]
            
            response = await self.llm.ainvoke(messages)
            decision = response.content.strip().upper()
            
            logger.info("planning_routing_decision",
                       component="orchestrator",
                       decision=decision,
                       instruction_preview=instruction[:100])
            
            return decision == "PLAN"
            
        except Exception as e:
            logger.error("planning_routing_error",
                        component="orchestrator",
                        error=str(e),
                        defaulting_to=False)
            return False
    
    def _build_routing_context(self, state: OrchestratorState) -> str:
        """Build minimal context for routing decisions."""
        
        context_parts = []
        
        # Recent messages
        recent_messages = state.get("messages", [])[-2:]
        if recent_messages:
            context_parts.append("Recent conversation:")
            for msg in recent_messages:
                if hasattr(msg, 'content') and msg.content:
                    speaker = "User" if isinstance(msg, HumanMessage) else "Assistant"
                    content_preview = str(msg.content)[:100] + "..." if len(str(msg.content)) > 100 else str(msg.content)
                    context_parts.append(f"{speaker}: {content_preview}")
        
        # Memory context
        memory = state.get("memory", {})
        if memory:
            context_parts.append(f"Memory: {str(memory)[:100]}...")
        
        return "\n".join(context_parts) if context_parts else "No additional context"