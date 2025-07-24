"""Utilities for consistent thread ID management across the system."""

from typing import Optional


class ThreadIDManager:
    """Manages thread ID generation and parsing across agents and orchestrator."""
    
    # Standard format: agent-task_id
    # Examples: salesforce-abc123, jira-def456, servicenow-ghi789, orchestrator-main123
    
    @staticmethod
    def create_thread_id(agent_name: str, task_id: str) -> str:
        """
        Create a standardized thread ID.
        
        Args:
            agent_name: Name of the agent (e.g., 'salesforce', 'jira', 'servicenow', 'orchestrator')
            task_id: The task ID from A2A protocol
            
        Returns:
            Formatted thread ID like 'salesforce-abc123'
        """
        # Normalize agent name to lowercase
        agent_name = agent_name.lower().replace('_', '').replace('-', '')
        
        # Handle special cases for backward compatibility if needed
        if agent_name == 'sf':
            agent_name = 'salesforce'
        elif agent_name == 'sn':
            agent_name = 'servicenow'
            
        return f"{agent_name}-{task_id}"
    
    @staticmethod
    def parse_thread_id(thread_id: str) -> tuple[str, str]:
        """
        Parse a thread ID into its components.
        
        Args:
            thread_id: The thread ID to parse
            
        Returns:
            Tuple of (agent_name, task_id)
            
        Raises:
            ValueError: If thread ID is not in the expected format
        """
        if '-' not in thread_id:
            raise ValueError(f"Invalid thread ID format: {thread_id}. Expected 'agent-task_id'")
        
        parts = thread_id.split('-', 1)  # Split on first hyphen only
        if len(parts) != 2:
            raise ValueError(f"Invalid thread ID format: {thread_id}. Expected 'agent-task_id'")
            
        return parts[0], parts[1]
    
    @staticmethod
    def get_agent_from_thread(thread_id: str) -> str:
        """Extract the agent name from a thread ID."""
        agent_name, _ = ThreadIDManager.parse_thread_id(thread_id)
        return agent_name
    
    @staticmethod
    def get_task_from_thread(thread_id: str) -> str:
        """Extract the task ID from a thread ID."""
        _, task_id = ThreadIDManager.parse_thread_id(thread_id)
        return task_id
    
    @staticmethod
    def is_valid_thread_id(thread_id: str) -> bool:
        """Check if a thread ID is valid."""
        try:
            ThreadIDManager.parse_thread_id(thread_id)
            return True
        except ValueError:
            return False


# Convenience functions
def create_thread_id(agent_name: str, task_id: str) -> str:
    """Create a standardized thread ID."""
    return ThreadIDManager.create_thread_id(agent_name, task_id)


def parse_thread_id(thread_id: str) -> tuple[str, str]:
    """Parse a thread ID into agent name and task ID."""
    return ThreadIDManager.parse_thread_id(thread_id)