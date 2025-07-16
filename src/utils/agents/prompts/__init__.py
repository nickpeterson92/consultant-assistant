"""Agent system prompts and messages."""

from .orchestrator_prompts import (
    orchestrator_chatbot_sys_msg,
    orchestrator_summary_sys_msg,
    get_fallback_summary,
    orchestrator_a2a_sys_msg,
    get_planning_system_message
)
from .salesforce_prompts import (
    salesforce_agent_sys_msg,
    TRUSTCALL_INSTRUCTION
)
from .jira_prompts import jira_agent_sys_msg
from .servicenow_prompts import servicenow_agent_sys_msg
# Workflow agent removed - functionality moved to plan-and-execute

__all__ = [
    # Orchestrator prompts
    'orchestrator_chatbot_sys_msg',
    'orchestrator_summary_sys_msg', 
    'get_fallback_summary',
    'orchestrator_a2a_sys_msg',
    'get_planning_system_message',
    
    # Agent prompts
    'salesforce_agent_sys_msg',
    'jira_agent_sys_msg',
    'servicenow_agent_sys_msg',
    # 'workflow_agent_sys_msg', - removed
    
    # Constants
    'TRUSTCALL_INSTRUCTION'
]