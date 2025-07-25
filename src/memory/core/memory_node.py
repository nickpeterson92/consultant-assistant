"""Memory Node implementation for conversational context."""

import uuid
from datetime import datetime
from typing import Any, Dict, Set, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from src.utils.datetime_utils import utc_now, ensure_utc


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
    created_at: datetime = field(default_factory=utc_now)
    last_accessed: datetime = field(default_factory=utc_now)
    
    # Relevance and decay
    base_relevance: float = 1.0               # Initial importance score
    decay_rate: float = 0.2                   # INCREASED: How quickly relevance decays (per hour)
    min_relevance: float = 0.05               # Minimum relevance before cleanup
    
    # Semantic metadata
    tags: Set[str] = field(default_factory=set)
    summary: str = ""                         # Human-readable summary
    
    # Relationships (managed by MemoryGraph)
    source_nodes: List[str] = field(default_factory=list)  # What led to this
    derived_nodes: List[str] = field(default_factory=list)  # What this led to
    
    # Semantic embedding (optional, computed on demand)
    _embedding: Optional[Any] = field(default=None, init=False, repr=False)
    
    def current_relevance(self) -> float:
        """Calculate current relevance based on time decay."""
        hours_since_creation = (utc_now() - ensure_utc(self.created_at)).total_seconds() / 3600
        hours_since_access = (utc_now() - ensure_utc(self.last_accessed)).total_seconds() / 3600
        
        # IMPROVED: Context-aware exponential decay with different half-lives
        half_life_hours = {
            ContextType.SEARCH_RESULT: 6,      # Fast decay (6 hour half-life)
            ContextType.TEMPORARY_STATE: 3,    # Very fast decay
            ContextType.DOMAIN_ENTITY: 48,     # Slow decay (2 day half-life)
            ContextType.CONVERSATION_FACT: 24, # Medium decay (1 day half-life)
            ContextType.COMPLETED_ACTION: 12,  # Medium-fast decay
            ContextType.TOOL_OUTPUT: 8,        # Fast decay
            ContextType.USER_SELECTION: 36    # Slower decay for user choices
        }.get(self.context_type, 12)  # Default 12 hour half-life
        
        # Exponential decay formula
        decay_factor = 0.5 ** (hours_since_creation / half_life_hours)
        
        # Recent access boost (decays quickly with 2-hour half-life)
        access_boost = 0
        if hours_since_access < 24:  # Only boost if accessed in last day
            access_boost = 0.3 * (0.5 ** (hours_since_access / 2))
        
        current_relevance = self.base_relevance * decay_factor + access_boost
        return max(self.min_relevance, min(1.0, current_relevance))
    
    def access(self):
        """Mark this node as accessed, boosting its relevance."""
        self.last_accessed = utc_now()
    
    def is_stale(self) -> bool:
        """Check if this node should be cleaned up due to low relevance."""
        return self.current_relevance() <= self.min_relevance
    
    def add_tag(self, tag: str):
        """Add a semantic tag for better searchability."""
        if tag is not None:
            self.tags.add(tag.lower())
    
    def matches_tags(self, query_tags: Set[str]) -> float:
        """Calculate tag match score for semantic similarity."""
        if not query_tags or not self.tags:
            return 0.0
        
        intersection = self.tags.intersection(query_tags)
        union = self.tags.union(query_tags)
        
        # Jaccard similarity
        return len(intersection) / len(union) if union else 0.0
    
    def get_embedding_text(self) -> str:
        """Get the text representation for embedding generation."""
        # Combine summary with key content fields
        text_parts = []
        
        if self.summary:
            text_parts.append(self.summary)
            
        # Add entity-specific information
        if isinstance(self.content, dict):
            if 'entity_name' in self.content:
                text_parts.append(f"Name: {self.content['entity_name']}")
            if 'entity_type' in self.content:
                text_parts.append(f"Type: {self.content['entity_type']}")
            if 'industry' in self.content:
                text_parts.append(f"Industry: {self.content['industry']}")
                
        # Add tags
        if self.tags:
            text_parts.append(f"Tags: {', '.join(sorted(self.tags))}")
            
        return " | ".join(text_parts)
    
    @property
    def embedding(self):
        """Get or compute the embedding for this node."""
        if self._embedding is None:
            # Lazy load embeddings
            try:
                from ..algorithms.semantic_embeddings import get_embeddings
                embeddings = get_embeddings()
                if embeddings.is_available():
                    self._embedding = embeddings.encode_text(self.get_embedding_text())
            except Exception:
                pass
        return self._embedding
    
    def clear_embedding(self):
        """Clear cached embedding (useful if content changes)."""
        self._embedding = None
    
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
        age_hours = (utc_now() - ensure_utc(self.created_at)).total_seconds() / 3600
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
    
    # DON'T use predefined decay rate - let exponential decay in current_relevance() handle it
    # decay_rate = CONTEXT_DECAY_RATES.get(context_type, 0.1)
    
    node = MemoryNode(
        content=content,
        context_type=context_type,
        # decay_rate=decay_rate,  # Use default from class
        base_relevance=base_relevance,
        summary=summary
    )
    
    if tags:
        # Filter out None values from tags and ensure lowercase
        node.tags = {tag.lower() for tag in tags if tag is not None}
    
    return node