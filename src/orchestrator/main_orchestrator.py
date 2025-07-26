"""Main Orchestrator - ReAct agent that can respond directly or delegate to task agent."""

import os
from typing import Dict, Any, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import BaseTool
from langchain_core.prompts import MessagesPlaceholder

from src.orchestrator.core.agent_registry import AgentRegistry
from src.orchestrator.tools.agent_caller_tools import (
    SalesforceAgentTool, 
    JiraAgentTool, 
    ServiceNowAgentTool, 
    AgentRegistryTool
)
from src.orchestrator.tools.web_search import WebSearchTool
from src.orchestrator.tools.human_input import HumanInputTool
from src.orchestrator.tools.task_agent import TaskAgentTool
from src.utils.cost_tracking_decorator import create_cost_tracking_azure_openai
from src.utils.logging.framework import SmartLogger
from src.utils.prompt_templates import create_react_orchestrator_prompt, ContextInjectorOrchestrator

logger = SmartLogger("orchestrator.main")


async def create_main_orchestrator(state: Dict[str, Any] = None) -> Any:
    """Create the main ReAct orchestrator with all tools including TaskAgentTool."""
    
    if state is None:
        state = {}
    
    # Create agent registry
    agent_registry = AgentRegistry()
    
    # Create tools list
    tools: List[BaseTool] = [
        SalesforceAgentTool(agent_registry),
        JiraAgentTool(agent_registry),
        ServiceNowAgentTool(agent_registry),
        AgentRegistryTool(agent_registry),
        WebSearchTool(),
        HumanInputTool(),
        TaskAgentTool()  # Lazy-loaded for complex multi-step tasks
    ]
    
    # Create LLM with cost tracking
    llm = create_cost_tracking_azure_openai(
        component="main_orchestrator",
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4o-mini"),
        openai_api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01"),
        openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
        temperature=0.1,
        max_tokens=4000,
    )
    
    # Use the new ReAct orchestrator prompt template
    prompt = create_react_orchestrator_prompt()
    
    # Prepare context for the orchestrator prompt
    # Get agent registry stats for the agent_section
    registry_stats = agent_registry.get_registry_stats()
    agent_context = f"""AVAILABLE SPECIALIZED AGENTS:
{', '.join(registry_stats['available_capabilities']) if registry_stats['available_capabilities'] else 'None currently available'}

ORCHESTRATOR TOOLS:
1. salesforce_agent: For Salesforce CRM operations (leads, accounts, opportunities, contacts, cases, tasks, etc.)
2. jira_agent: For project management (projects, bugs, epics, stories, etc.)
3. servicenow_agent: For incident management and IT (change requests, incidents, problems, etc.)
4. agent_registry: To check agent status and capabilities
5. web_search: Search the web for information about entities, companies, people, or topics
6. task_agent: Execute complex multi-step tasks that require planning and coordination
7. human_input: Request human clarification when requests are ambiguous or need additional context"""
    
    # Prepare the context using ContextInjectorOrchestrator
    context_dict = ContextInjectorOrchestrator.prepare_context(
        summary=state.get("summary", None),
        memory=state.get("memory_context", None),
        agent_context=agent_context
    )
    
    # Create the ReAct agent with the properly formatted prompt
    # Since ReAct expects a single system message, we need to format the prompt
    # and extract the system message content
    formatted_messages = prompt.format_messages(
        messages=[],  # Empty messages for template formatting
        **context_dict
    )
    
    # Extract the system message content
    system_message_content = formatted_messages[0].content
    
    # Create a new prompt with the formatted system message
    from langchain_core.prompts import ChatPromptTemplate
    formatted_prompt = ChatPromptTemplate.from_messages([
        ("system", system_message_content),
        MessagesPlaceholder(variable_name="messages")
    ])
    
    # Create ReAct agent
    main_orchestrator = create_react_agent(
        llm, 
        tools, 
        prompt=formatted_prompt,
        debug=True
    )
    
    # Store tools reference for TaskAgentTool access
    main_orchestrator._tools = tools
    
    logger.info("main_orchestrator_created",
               tools=[t.name for t in tools])
    
    return main_orchestrator


async def invoke_main_orchestrator(
    message: str,
    thread_id: str = "default-thread",
    user_id: str = "default_user",
    task_id: str = None,
    messages: List[Any] = None,
    memory_context: str = None
) -> Dict[str, Any]:
    """Invoke the main orchestrator with a message."""
    
    if task_id is None:
        task_id = f"main_{hash(message)}"
    
    if messages is None:
        messages = []
    
    # Create the orchestrator with memory context if available
    state = {}
    if memory_context:
        state["memory_context"] = memory_context
    orchestrator = await create_main_orchestrator(state)
    
    # Prepare input
    orchestrator_input = {
        "messages": messages + [HumanMessage(content=message)],
        "thread_id": thread_id,
        "user_id": user_id,
        "task_id": task_id
    }
    
    # Store state for tools to access
    if hasattr(orchestrator, '_tools'):
        for tool in orchestrator._tools:
            if isinstance(tool, TaskAgentTool):
                tool._parent_state = orchestrator_input
    
    logger.info("main_orchestrator_invoke",
               user_message=message[:100],
               thread_id=thread_id,
               user_id=user_id,
               task_id=task_id)
    
    try:
        # Invoke the orchestrator
        result = await orchestrator.ainvoke(orchestrator_input)
        
        # Extract the response
        messages = result.get("messages", [])
        if messages and hasattr(messages[-1], 'content'):
            response = messages[-1].content
        else:
            response = "I completed the task but couldn't generate a response."
        
        logger.info("main_orchestrator_success",
                   response_length=len(response))
        
        return {
            "response": response,
            "messages": messages,
            "status": "success"
        }
        
    except Exception as e:
        logger.error("main_orchestrator_error",
                    error=str(e),
                    error_type=type(e).__name__)
        
        return {
            "response": f"I encountered an error: {str(e)}",
            "messages": messages,
            "status": "error",
            "error": str(e)
        }