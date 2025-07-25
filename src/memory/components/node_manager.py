"""Node manager for memory framework - handles storage and indexing."""

from typing import Dict, Set, List, Optional, Tuple
from datetime import datetime
from collections import defaultdict, deque

from ..core.memory_node import MemoryNode, ContextType
from .inverted_index import InvertedIndex
from .text_processor import TextProcessor
from ..config.memory_config import MEMORY_CONFIG
from src.utils.logging.framework import SmartLogger
from src.utils.datetime_utils import utc_now

logger = SmartLogger("memory.nodes")


class NodeManager:
    """Manages node storage, indexing, and retrieval."""
    
    def __init__(self, thread_id: str, config=None):
        self.thread_id = thread_id
        self.config = config or MEMORY_CONFIG
        
        # Core storage
        self.nodes: Dict[str, MemoryNode] = {}
        
        # Indexes
        self.nodes_by_type: Dict[ContextType, Set[str]] = defaultdict(set)
        self.nodes_by_tag: Dict[str, Set[str]] = defaultdict(set)
        self.entity_id_index: Dict[str, str] = {}  # entity_id -> node_id
        
        # Components
        self.text_processor = TextProcessor(self.config)
        self.inverted_index = InvertedIndex(self.text_processor)
        
        # Access tracking
        self.recent_accessed_nodes: deque = deque(maxlen=20)
        
        # Statistics
        self.total_nodes_created = 0
        self.total_nodes_cleaned = 0
    
    def add_node(self, node: MemoryNode) -> str:
        """Add a node to storage and update all indexes."""
        node_id = node.node_id
        
        # Store node
        self.nodes[node_id] = node
        self.total_nodes_created += 1
        
        # Update type index
        self.nodes_by_type[node.context_type].add(node_id)
        
        # Update tag index
        for tag in node.tags:
            self.nodes_by_tag[tag.lower()].add(node_id)
        
        # Update entity ID index
        self._update_entity_index(node_id, node)
        
        # Update inverted index
        self._update_inverted_index(node_id, node)
        
        logger.debug("node_added",
                    thread_id=self.thread_id,
                    node_id=node_id,
                    type=node.context_type.value,
                    tags=list(node.tags))
        
        return node_id
    
    def remove_node(self, node_id: str) -> bool:
        """Remove a node and update all indexes."""
        if node_id not in self.nodes:
            return False
        
        node = self.nodes[node_id]
        
        # Remove from type index
        self.nodes_by_type[node.context_type].discard(node_id)
        
        # Remove from tag index
        for tag in node.tags:
            self.nodes_by_tag[tag.lower()].discard(node_id)
            if not self.nodes_by_tag[tag.lower()]:
                del self.nodes_by_tag[tag.lower()]
        
        # Remove from entity ID index
        if hasattr(node, 'content') and isinstance(node.content, dict):
            entity_id = (node.content.get('entity_id') or 
                        node.content.get('Id') or 
                        node.content.get('id'))
            if entity_id and str(entity_id) in self.entity_id_index:
                if self.entity_id_index[str(entity_id)] == node_id:
                    del self.entity_id_index[str(entity_id)]
        
        # Remove from inverted index
        self.inverted_index.remove_document(node_id)
        
        # Remove from storage
        del self.nodes[node_id]
        
        logger.debug("node_removed",
                    thread_id=self.thread_id,
                    node_id=node_id)
        
        return True
    
    def get_node(self, node_id: str) -> Optional[MemoryNode]:
        """Get a node by ID."""
        return self.nodes.get(node_id)
    
    def get_node_by_entity_id(self, entity_id: str) -> Optional[MemoryNode]:
        """Get a node by entity ID."""
        node_id = self.entity_id_index.get(str(entity_id))
        if node_id:
            return self.nodes.get(node_id)
        return None
    
    def track_access(self, node_id: str):
        """Track node access for context scoring."""
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node.access()
            self.recent_accessed_nodes.append((node_id, utc_now()))
    
    def get_recent_accessed(self) -> List[Tuple[str, datetime]]:
        """Get recently accessed nodes."""
        return list(self.recent_accessed_nodes)
    
    def search_by_text(self, query: str, min_match_ratio: float = None) -> Set[str]:
        """Search nodes by text using inverted index."""
        return self.inverted_index.search(query, min_match_ratio)
    
    def filter_nodes(self, node_ids: Set[str] = None,
                    context_filter: Optional[Set[ContextType]] = None,
                    max_age_hours: Optional[float] = None,
                    required_tags: Optional[Set[str]] = None,
                    excluded_tags: Optional[Set[str]] = None) -> List[str]:
        """Filter nodes based on various criteria."""
        # Start with all nodes or provided subset
        if node_ids is None:
            candidates = set(self.nodes.keys())
        else:
            candidates = node_ids & set(self.nodes.keys())
        
        current_time = utc_now()
        filtered = []
        
        for node_id in candidates:
            node = self.nodes[node_id]
            
            # Filter by context type
            if context_filter and node.context_type not in context_filter:
                continue
            
            # Filter by age
            if max_age_hours:
                age_hours = (current_time - node.created_at).total_seconds() / 3600
                if age_hours > max_age_hours:
                    continue
            
            # Filter by required tags
            if required_tags and not required_tags.issubset(node.tags):
                continue
            
            # Filter by excluded tags
            if excluded_tags and excluded_tags.intersection(node.tags):
                continue
            
            filtered.append(node_id)
        
        return filtered
    
    def cleanup_stale_nodes(self, max_age_hours: float = None) -> int:
        """Remove nodes that are too old or have low relevance."""
        max_age_hours = max_age_hours or self.config.DEFAULT_MAX_AGE_HOURS
        
        stale_node_ids = []
        current_time = utc_now()
        
        for node_id, node in self.nodes.items():
            # Calculate age
            age_hours = (current_time - node.created_at).total_seconds() / 3600
            
            # Check if node should be removed
            should_remove = False
            
            # Remove if too old (unless marked as important)
            if (age_hours > max_age_hours and 
                "important" not in node.tags and 
                "preserve" not in node.tags):
                should_remove = True
            
            # Also remove if relevance is extremely low
            elif node.current_relevance() < 0.01:
                should_remove = True
            
            if should_remove:
                stale_node_ids.append(node_id)
        
        # Remove stale nodes
        for node_id in stale_node_ids:
            self.remove_node(node_id)
        
        cleaned_count = len(stale_node_ids)
        self.total_nodes_cleaned += cleaned_count
        
        if cleaned_count > 0:
            logger.info("nodes_cleaned",
                       thread_id=self.thread_id,
                       count=cleaned_count,
                       remaining=len(self.nodes))
        
        return cleaned_count
    
    def _update_entity_index(self, node_id: str, node: MemoryNode):
        """Update entity ID index for fast lookup."""
        if isinstance(node.content, dict):
            # Try different common ID fields
            entity_id = (node.content.get('entity_id') or 
                        node.content.get('Id') or 
                        node.content.get('id') or
                        node.content.get('key') or
                        node.content.get('number'))
            
            if entity_id:
                self.entity_id_index[str(entity_id)] = node_id
    
    def _update_inverted_index(self, node_id: str, node: MemoryNode):
        """Update inverted index for text search."""
        # Get all text to index
        text = self.text_processor.get_node_text(
            node.content if isinstance(node.content, dict) else {},
            node.summary,
            node.tags
        )
        
        # Add to inverted index
        self.inverted_index.add_document(node_id, text)
    
    def get_node_count(self) -> int:
        """Get the total number of nodes."""
        return len(self.nodes)
    
    def get_statistics(self) -> Dict[str, any]:
        """Get storage statistics."""
        stats = {
            'total_nodes': len(self.nodes),
            'nodes_by_type': {t.value: len(nodes) for t, nodes in self.nodes_by_type.items()},
            'total_tags': len(self.nodes_by_tag),
            'total_entities': len(self.entity_id_index),
            'nodes_created': self.total_nodes_created,
            'nodes_cleaned': self.total_nodes_cleaned,
            'index_stats': self.inverted_index.get_statistics()
        }
        return stats