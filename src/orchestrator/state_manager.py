"""
Multi-Agent State Management System
Coordinates state between orchestrator and specialized agents
"""

import json
import uuid
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class AgentInteraction:
    """Tracks an interaction with a specialized agent"""
    id: str
    agent_name: str
    task_id: str
    instruction: str
    request_time: str
    response_time: Optional[str] = None
    status: str = "pending"  # pending, completed, failed
    artifacts: List[Dict[str, Any]] = None
    state_updates: Dict[str, Any] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.artifacts is None:
            self.artifacts = []
        if self.state_updates is None:
            self.state_updates = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class GlobalMemory:
    """Global memory that spans across all agents"""
    user_context: Dict[str, Any]
    conversation_summary: str
    agent_interactions: List[AgentInteraction]  
    shared_entities: Dict[str, Any]  # Entities that multiple agents might reference
    session_metadata: Dict[str, Any]
    
    def __post_init__(self):
        if not hasattr(self, 'user_context'):
            self.user_context = {}
        if not hasattr(self, 'agent_interactions'):
            self.agent_interactions = []
        if not hasattr(self, 'shared_entities'):
            self.shared_entities = {}
        if not hasattr(self, 'session_metadata'):
            self.session_metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class MultiAgentStateManager:
    """Manages state coordination across multiple agents"""
    
    def __init__(self):
        self.global_memory = GlobalMemory(
            user_context={},
            conversation_summary="",
            agent_interactions=[],
            shared_entities={},
            session_metadata={}
        )
        self.active_tasks: Dict[str, AgentInteraction] = {}
        self.agent_memories: Dict[str, Dict[str, Any]] = {}  # Per-agent specific memory
    
    def create_agent_interaction(self, agent_name: str, instruction: str) -> AgentInteraction:
        """Create a new agent interaction record"""
        interaction = AgentInteraction(
            id=str(uuid.uuid4()),
            agent_name=agent_name,
            task_id=str(uuid.uuid4()),
            instruction=instruction,
            request_time=datetime.now(timezone.utc).isoformat()
        )
        
        self.active_tasks[interaction.task_id] = interaction
        return interaction
    
    def complete_agent_interaction(self, task_id: str, artifacts: List[Dict[str, Any]] = None, 
                                 state_updates: Dict[str, Any] = None, error_message: Optional[str] = None):
        """Mark an agent interaction as completed and process results"""
        if task_id not in self.active_tasks:
            logger.warning(f"Attempted to complete unknown task: {task_id}")
            return
        
        interaction = self.active_tasks[task_id]
        interaction.response_time = datetime.now(timezone.utc).isoformat()
        interaction.status = "failed" if error_message else "completed"
        interaction.error_message = error_message
        
        if artifacts:
            interaction.artifacts = artifacts
        
        if state_updates:
            interaction.state_updates = state_updates
            self._apply_state_updates(interaction.agent_name, state_updates)
        
        # Move from active to history
        self.global_memory.agent_interactions.append(interaction)
        del self.active_tasks[task_id]
        
        logger.info(f"Completed agent interaction: {task_id} ({interaction.status})")
    
    def _apply_state_updates(self, agent_name: str, state_updates: Dict[str, Any]):
        """Apply state updates from an agent"""
        # Update agent-specific memory
        if agent_name not in self.agent_memories:
            self.agent_memories[agent_name] = {}
        
        agent_memory = self.agent_memories[agent_name]
        
        # Process different types of updates
        if "memory_updates" in state_updates:
            memory_updates = state_updates["memory_updates"]
            if isinstance(memory_updates, dict):
                agent_memory.update(memory_updates)
        
        if "shared_entities" in state_updates:
            # Update global shared entities (like Salesforce records)
            shared_updates = state_updates["shared_entities"]
            if isinstance(shared_updates, dict):
                for entity_type, entities in shared_updates.items():
                    if entity_type not in self.global_memory.shared_entities:
                        self.global_memory.shared_entities[entity_type] = {}
                    
                    if isinstance(entities, dict):
                        self.global_memory.shared_entities[entity_type].update(entities)
                    elif isinstance(entities, list):
                        # Handle list of entities (convert to dict by ID if possible)
                        entity_dict = {}
                        for entity in entities:
                            if isinstance(entity, dict) and "id" in entity:
                                entity_dict[entity["id"]] = entity
                        self.global_memory.shared_entities[entity_type].update(entity_dict)
        
        if "user_context_updates" in state_updates:
            # Update global user context
            context_updates = state_updates["user_context_updates"]
            if isinstance(context_updates, dict):
                self.global_memory.user_context.update(context_updates)
    
    def get_context_for_agent(self, agent_name: str, capabilities: List[str] = None) -> Dict[str, Any]:
        """Get relevant context for a specific agent"""
        context = {
            "conversation_summary": self.global_memory.conversation_summary,
            "user_context": self.global_memory.user_context.copy(),
            "session_metadata": self.global_memory.session_metadata.copy()
        }
        
        # Include agent-specific memory
        if agent_name in self.agent_memories:
            context["agent_memory"] = self.agent_memories[agent_name].copy()
        
        # Include relevant shared entities based on capabilities
        if capabilities:
            relevant_entities = {}
            for entity_type, entities in self.global_memory.shared_entities.items():
                # Check if entity type relates to agent capabilities
                if any(capability.lower() in entity_type.lower() or entity_type.lower() in capability.lower() 
                      for capability in capabilities):
                    relevant_entities[entity_type] = entities
            
            if relevant_entities:
                context["shared_entities"] = relevant_entities
        else:
            # If no capabilities specified, include all shared entities
            context["shared_entities"] = self.global_memory.shared_entities.copy()
        
        # Include recent relevant interactions
        recent_interactions = []
        for interaction in self.global_memory.agent_interactions[-5:]:  # Last 5 interactions
            if interaction.agent_name == agent_name or any(
                cap.lower() in interaction.instruction.lower() for cap in (capabilities or [])
            ):
                recent_interactions.append(interaction.to_dict())
        
        if recent_interactions:
            context["recent_interactions"] = recent_interactions
        
        return context
    
    def update_conversation_summary(self, new_summary: str):
        """Update the global conversation summary"""
        self.global_memory.conversation_summary = new_summary
        logger.debug("Updated global conversation summary")
    
    def update_user_context(self, updates: Dict[str, Any]):
        """Update user context information"""
        self.global_memory.user_context.update(updates)
        logger.debug(f"Updated user context with: {list(updates.keys())}")
    
    def add_shared_entity(self, entity_type: str, entity_id: str, entity_data: Dict[str, Any]):
        """Add or update a shared entity"""
        if entity_type not in self.global_memory.shared_entities:
            self.global_memory.shared_entities[entity_type] = {}
        
        self.global_memory.shared_entities[entity_type][entity_id] = entity_data
        logger.debug(f"Added/updated shared entity: {entity_type}/{entity_id}")
    
    def get_shared_entities(self, entity_type: Optional[str] = None) -> Dict[str, Any]:
        """Get shared entities, optionally filtered by type"""
        if entity_type:
            return self.global_memory.shared_entities.get(entity_type, {})
        return self.global_memory.shared_entities
    
    def get_agent_memory(self, agent_name: str) -> Dict[str, Any]:
        """Get memory specific to an agent"""
        return self.agent_memories.get(agent_name, {})
    
    def get_recent_interactions(self, agent_name: Optional[str] = None, limit: int = 10) -> List[AgentInteraction]:
        """Get recent interactions, optionally filtered by agent"""
        interactions = self.global_memory.agent_interactions
        
        if agent_name:
            interactions = [i for i in interactions if i.agent_name == agent_name]
        
        return interactions[-limit:] if limit else interactions
    
    def get_active_tasks(self) -> Dict[str, AgentInteraction]:
        """Get currently active tasks"""
        return self.active_tasks.copy()
    
    def export_state(self) -> Dict[str, Any]:
        """Export the complete state for persistence"""
        return {
            "global_memory": self.global_memory.to_dict(),
            "active_tasks": {k: v.to_dict() for k, v in self.active_tasks.items()},
            "agent_memories": self.agent_memories.copy(),
            "export_timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def import_state(self, state_data: Dict[str, Any]):
        """Import state from persistence"""
        try:
            if "global_memory" in state_data:
                gm_data = state_data["global_memory"]
                # Reconstruct AgentInteraction objects
                interactions = []
                for interaction_data in gm_data.get("agent_interactions", []):
                    interactions.append(AgentInteraction(**interaction_data))
                
                self.global_memory = GlobalMemory(
                    user_context=gm_data.get("user_context", {}),
                    conversation_summary=gm_data.get("conversation_summary", ""),
                    agent_interactions=interactions,
                    shared_entities=gm_data.get("shared_entities", {}),
                    session_metadata=gm_data.get("session_metadata", {})
                )
            
            if "active_tasks" in state_data:
                self.active_tasks = {
                    k: AgentInteraction(**v) for k, v in state_data["active_tasks"].items()
                }
            
            if "agent_memories" in state_data:
                self.agent_memories = state_data["agent_memories"]
            
            logger.info("Successfully imported multi-agent state")
            
        except Exception as e:
            logger.error(f"Error importing state: {e}")
    
    def get_state_summary(self) -> Dict[str, Any]:
        """Get a summary of the current state"""
        return {
            "conversation_summary_length": len(self.global_memory.conversation_summary),
            "user_context_keys": list(self.global_memory.user_context.keys()),
            "shared_entity_types": list(self.global_memory.shared_entities.keys()),
            "total_interactions": len(self.global_memory.agent_interactions),
            "active_tasks_count": len(self.active_tasks),
            "agents_with_memory": list(self.agent_memories.keys()),
            "session_metadata": self.global_memory.session_metadata
        }