"""Memory Node implementation for conversational context."""

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Set, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class ContextType(Enum):
    """Types of memory contexts for different data lifecycles."""
    SEARCH_RESULT = "search_result"           # Results from searches/queries
    USER_SELECTION = "user_selection"         # User choices/selections
    TOOL_OUTPUT = "tool_output"              # Raw tool execution results
    DOMAIN_ENTITY = "domain_entity"          # Business objects (accounts, opportunities)
    COMPLETED_ACTION = "completed_action"     # Finished tasks/operations
    CONVERSATION_FACT = "conversation_fact"   # Persistent conversation knowledge
    TEMPORARY_STATE = "temporary_state"       # Short-lived execution state


@dataclass
class MemoryNode:
    """A single memory node in the conversational context graph."""
    
    # Core data
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: Any = None
    context_type: ContextType = ContextType.TEMPORARY_STATE
    
    # Temporal metadata
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    
    # Relevance and decay
    base_relevance: float = 1.0               # Initial importance score
    decay_rate: float = 0.1                   # How quickly relevance decays (per hour)
    min_relevance: float = 0.05               # Minimum relevance before cleanup
    
    # Semantic metadata
    tags: Set[str] = field(default_factory=set)
    summary: str = ""                         # Human-readable summary
    
    # Relationships (managed by MemoryGraph)
    source_nodes: List[str] = field(default_factory=list)  # What led to this
    derived_nodes: List[str] = field(default_factory=list)  # What this led to
    
    def current_relevance(self) -> float:
        """Calculate current relevance based on time decay."""
        hours_since_creation = (datetime.now() - self.created_at).total_seconds() / 3600
        hours_since_access = (datetime.now() - self.last_accessed).total_seconds() / 3600
        
        # Decay based on creation time and last access
        creation_decay = max(0, self.base_relevance - (hours_since_creation * self.decay_rate))
        access_boost = max(0, 0.2 - (hours_since_access * self.decay_rate * 0.5))  # Recent access boosts relevance
        
        current_relevance = max(self.min_relevance, creation_decay + access_boost)
        return min(1.0, current_relevance)  # Cap at 1.0
    
    def access(self):
        """Mark this node as accessed, boosting its relevance."""
        self.last_accessed = datetime.now()
    
    def is_stale(self) -> bool:
        """Check if this node should be cleaned up due to low relevance."""
        return self.current_relevance() <= self.min_relevance
    
    def add_tag(self, tag: str):
        """Add a semantic tag for better searchability."""
        self.tags.add(tag.lower())
    
    def matches_tags(self, query_tags: Set[str]) -> float:
        """Calculate tag match score for semantic similarity."""
        if not query_tags or not self.tags:
            return 0.0
        
        intersection = self.tags.intersection(query_tags)
        union = self.tags.union(query_tags)
        
        # Jaccard similarity
        return len(intersection) / len(union) if union else 0.0
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary for storage."""
        return {
            'node_id': self.node_id,
            'content': self.content,
            'context_type': self.context_type.value,
            'created_at': self.created_at.isoformat(),
            'last_accessed': self.last_accessed.isoformat(),
            'base_relevance': self.base_relevance,
            'decay_rate': self.decay_rate,
            'min_relevance': self.min_relevance,
            'tags': list(self.tags),
            'summary': self.summary,
            'source_nodes': self.source_nodes,
            'derived_nodes': self.derived_nodes
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MemoryNode':
        """Deserialize from dictionary."""
        node = cls(
            node_id=data['node_id'],
            content=data['content'],
            context_type=ContextType(data['context_type']),
            created_at=datetime.fromisoformat(data['created_at']),
            last_accessed=datetime.fromisoformat(data['last_accessed']),
            base_relevance=data['base_relevance'],
            decay_rate=data['decay_rate'],
            min_relevance=data['min_relevance'],
            tags=set(data['tags']),
            summary=data['summary'],
            source_nodes=data['source_nodes'],
            derived_nodes=data['derived_nodes']
        )
        return node
    
    def __str__(self) -> str:
        relevance = self.current_relevance()
        age_hours = (datetime.now() - self.created_at).total_seconds() / 3600
        return f"MemoryNode({self.context_type.value}, relevance={relevance:.2f}, age={age_hours:.1f}h, tags={self.tags})"
    
    def __repr__(self) -> str:
        return self.__str__()


# Pre-defined decay rates for different context types
CONTEXT_DECAY_RATES = {
    ContextType.TEMPORARY_STATE: 2.0,        # Very fast decay (30min relevance)
    ContextType.USER_SELECTION: 0.5,        # Medium decay (2hr relevance)  
    ContextType.TOOL_OUTPUT: 0.2,           # Slow decay (5hr relevance)
    ContextType.SEARCH_RESULT: 0.3,         # Medium-slow decay (3hr relevance)
    ContextType.DOMAIN_ENTITY: 0.05,        # Very slow decay (20hr relevance)
    ContextType.COMPLETED_ACTION: 1.0,      # Fast decay for completed tasks
    ContextType.CONVERSATION_FACT: 0.01,    # Extremely slow decay (persistent)
}


def create_memory_node(content: Any, context_type: ContextType, 
                      tags: Optional[Set[str]] = None,
                      summary: str = "",
                      base_relevance: float = 1.0) -> MemoryNode:
    """Factory function to create appropriately configured memory nodes."""
    
    # Use predefined decay rate for context type
    decay_rate = CONTEXT_DECAY_RATES.get(context_type, 0.1)
    
    node = MemoryNode(
        content=content,
        context_type=context_type,
        decay_rate=decay_rate,
        base_relevance=base_relevance,
        summary=summary
    )
    
    if tags:
        node.tags = tags
    
    return node