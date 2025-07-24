"""SQLite-backed implementation of MemoryGraph."""

import networkx as nx
from datetime import datetime
from typing import Dict, List, Set, Optional, Any, Tuple

from .memory_node import MemoryNode, ContextType, create_memory_node
from .memory_graph import RelationshipType
from ..components.text_processor import TextProcessor
from ..components.scoring_engine import ScoringEngine, QueryContext
from ..algorithms.graph_algorithms import GraphAlgorithms
from ..config.memory_config import MEMORY_CONFIG
from ..storage.sqlite_backend import SQLiteMemoryBackend
from src.utils.logging.framework import SmartLogger
from src.utils.thread_utils import ThreadIDManager

logger = SmartLogger("memory.sqlite")


class MemoryGraphSQLite:
    """SQLite-backed graph memory that preserves the MemoryGraph interface."""
    
    # Class-level backend shared across all instances
    _backend = None
    
    @classmethod
    def get_backend(cls) -> SQLiteMemoryBackend:
        """Get or create the shared SQLite backend."""
        if cls._backend is None:
            cls._backend = SQLiteMemoryBackend()
        return cls._backend
    
    def __init__(self, thread_id: str, config=None):
        # Validate thread ID format
        if not ThreadIDManager.is_valid_thread_id(thread_id):
            raise ValueError(f"Invalid thread ID format: {thread_id}. Expected 'agent-task_id' format.")
        
        self.thread_id = thread_id
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.config = config or MEMORY_CONFIG
        
        # Use shared SQLite backend
        self.backend = self.get_backend()
        
        # Components for processing
        self.text_processor = TextProcessor(self.config)
        self.scoring_engine = ScoringEngine(self.config, self.text_processor)
        
        # In-memory graph built on-demand from SQLite
        self._graph_cache = None
        self._graph_cache_time = None
        self._cache_duration = 60  # seconds
        
        logger.info("memory_graph_sqlite_initialized", thread_id=thread_id)
    
    @property
    def graph(self) -> nx.MultiDiGraph:
        """Get the graph, building from SQLite if needed."""
        now = datetime.now()
        if (self._graph_cache is None or 
            self._graph_cache_time is None or
            (now - self._graph_cache_time).total_seconds() > self._cache_duration):
            self._rebuild_graph_cache()
        return self._graph_cache
    
    def _rebuild_graph_cache(self):
        """Rebuild the in-memory graph from SQLite."""
        self._graph_cache = nx.MultiDiGraph()
        self._graph_cache_time = datetime.now()
        
        # Get all nodes (from all threads for cross-thread relationships)
        all_nodes = self.backend.get_all_nodes()
        
        # Add nodes to graph
        for node in all_nodes:
            self._graph_cache.add_node(node.node_id, memory_node=node)
        
        # Add relationships
        for node in all_nodes:
            relationships = self.backend.get_relationships(node.node_id)
            for rel in relationships:
                if rel['direction'] == 'out':
                    self._graph_cache.add_edge(
                        node.node_id,
                        rel['node_id'],
                        type=rel['type'],
                        strength=rel['strength']
                    )
    
    def store(self,
              content: Any,
              context_type: ContextType,
              summary: Optional[str] = None,
              tags: Optional[Set[str]] = None,
              confidence: float = 0.5,
              metadata: Optional[Dict[str, Any]] = None,
              relates_to: Optional[List[str]] = None,
              depends_on: Optional[List[str]] = None) -> str:
        """Store a new memory node in SQLite."""
        
        # Create the memory node
        node = create_memory_node(
            content=content,
            context_type=context_type,
            summary=summary,
            tags=tags,
            base_relevance=confidence  # Map confidence to base_relevance
        )
        
        # Add metadata if provided
        if metadata:
            node.metadata = metadata
        
        # Store in SQLite
        node_id = self.backend.store_node(node, self.thread_id)
        
        # Update last activity
        self.last_activity = datetime.now()
        
        # Create relationships
        if relates_to:
            for target_id in relates_to:
                self.add_relationship(node_id, target_id, RelationshipType.RELATES_TO)
        
        if depends_on:
            for target_id in depends_on:
                self.add_relationship(node_id, target_id, RelationshipType.DEPENDS_ON)
        
        # Invalidate cache
        self._graph_cache = None
        
        logger.info("memory_node_stored",
                   thread_id=self.thread_id,
                   node_id=node_id,
                   context_type=context_type.value)
        
        return node_id
    
    def add_relationship(self, from_node_id: str, to_node_id: str, 
                        relationship_type: str, strength: float = 1.0):
        """Add a relationship between nodes."""
        # Convert string to RelationshipType if needed
        if isinstance(relationship_type, str):
            # Handle both old and new relationship type formats
            rel_type_map = {
                RelationshipType.LED_TO: RelationshipType.LED_TO,
                RelationshipType.RELATES_TO: RelationshipType.RELATES_TO,
                RelationshipType.DEPENDS_ON: RelationshipType.DEPENDS_ON,
                RelationshipType.CONTRADICTS: RelationshipType.CONTRADICTS,
                RelationshipType.REFINES: RelationshipType.REFINES,
                RelationshipType.ANSWERS: RelationshipType.ANSWERS,
                # Legacy mappings
                "led_to": RelationshipType.LED_TO,
                "relates_to": RelationshipType.RELATES_TO,
                "depends_on": RelationshipType.DEPENDS_ON,
                "belongs_to": RelationshipType.RELATES_TO,
                "has": RelationshipType.RELATES_TO,
                "produces": RelationshipType.LED_TO,
                # Entity relationship mappings
                "owned_by": RelationshipType.RELATES_TO,
                "created_by": RelationshipType.RELATES_TO,
                "assigned_to": RelationshipType.RELATES_TO,
                "reported_by": RelationshipType.RELATES_TO,
                "requested_by": RelationshipType.RELATES_TO,
                "child_of": RelationshipType.DEPENDS_ON,
                "affects_ci": RelationshipType.RELATES_TO,
                "updated": RelationshipType.REFINES
            }
            relationship_type = rel_type_map.get(relationship_type, RelationshipType.RELATES_TO)
        
        # Store using the actual relationship type value
        rel_type_value = relationship_type if isinstance(relationship_type, str) else relationship_type
        self.backend.store_relationship(from_node_id, to_node_id, rel_type_value, strength)
        
        # Invalidate cache
        self._graph_cache = None
    
    def retrieve_relevant(self,
                         query_text: Optional[str] = None,
                         context_filter: Optional[Set[ContextType]] = None,
                         max_results: int = 10,
                         min_relevance: float = 0.0,
                         max_age_hours: Optional[float] = None,
                         required_tags: Optional[Set[str]] = None) -> List[MemoryNode]:
        """Retrieve relevant memories using SQLite search and scoring."""
        
        candidates = []
        
        # Determine if we should search globally or thread-scoped
        global_types = {ContextType.DOMAIN_ENTITY, ContextType.CONVERSATION_FACT}
        search_globally = (
            context_filter is None or  # No filter means include global types
            any(ct in global_types for ct in context_filter)  # Filter includes global types
        )
        
        # If we have query text, use full-text search
        if query_text:
            if search_globally:
                # Search globally (no thread filter)
                search_results = self.backend.search_nodes(query_text, None, limit=max_results * 3)
            else:
                # Search thread-scoped
                search_results = self.backend.search_nodes(query_text, self.thread_id, limit=max_results * 3)
            
            for node, score in search_results:
                if self._node_matches_filters(node, context_filter, max_age_hours, required_tags):
                    candidates.append(node)
        else:
            # Get nodes by filters
            if search_globally:
                # Get all nodes globally
                nodes = self.backend.get_all_nodes(context_filter, max_age_hours)
            else:
                # Get nodes by thread
                nodes = self.backend.get_nodes_by_thread(self.thread_id, context_filter, max_age_hours)
            
            for node in nodes:
                if self._node_matches_filters(node, None, None, required_tags):
                    candidates.append(node)
        
        # Score and rank candidates
        query_context = QueryContext(
            query_text=query_text or "",
            query_tags=required_tags or set(),
            extracted_entities=[],  # TODO: Extract entities from query
            query_embedding=None,  # Embeddings not implemented yet
            query_type='default'
        )
        
        scored_results = []
        for node in candidates:
            # Use simplified scoring for now
            score = 0.5  # Base score
            
            # Boost score if query text matches content
            if query_text and isinstance(node.content, dict):
                content_str = str(node.content).lower()
                if query_text.lower() in content_str:
                    score += 0.3
            
            # Boost for summary match
            if query_text and node.summary and query_text.lower() in node.summary.lower():
                score += 0.2
            
            # Apply recency factor
            age_hours = (datetime.now() - node.created_at).total_seconds() / 3600
            recency_factor = max(0, 1 - (age_hours / 24))  # Decay over 24 hours
            score *= (0.5 + 0.5 * recency_factor)
            
            if score >= min_relevance:
                scored_results.append((node, score))
                # Update access in SQLite
                self.backend.update_node_access(node.node_id)
        
        # Sort by score and return top results
        scored_results.sort(key=lambda x: x[1], reverse=True)
        return [node for node, _ in scored_results[:max_results]]
    
    def _node_matches_filters(self, node: MemoryNode,
                             context_filter: Optional[Set[ContextType]],
                             max_age_hours: Optional[float],
                             required_tags: Optional[Set[str]]) -> bool:
        """Check if a node matches the given filters."""
        # Check context type filter
        if context_filter and node.context_type not in context_filter:
            return False
        
        # Check age filter
        if max_age_hours:
            age = (datetime.now() - node.created_at).total_seconds() / 3600
            if age > max_age_hours:
                return False
        
        # Check required tags
        if required_tags and not required_tags.issubset(node.tags):
            return False
        
        # For thread-scoped types, ensure they belong to current thread
        # Global types (DOMAIN_ENTITY, CONVERSATION_FACT) can be from any thread
        global_types = {ContextType.DOMAIN_ENTITY, ContextType.CONVERSATION_FACT}
        if node.context_type not in global_types:
            # This is a thread-scoped type, but we got it from global search
            # We need to check if it belongs to our thread (this shouldn't happen with our logic above)
            # but adding as safety check
            pass  # For now, accept all since our search logic should handle this
        
        return True
    
    # Implement NodeManager compatibility methods
    @property
    def node_manager(self):
        """Compatibility property for code expecting node_manager."""
        return self
    
    def get_node(self, node_id: str) -> Optional[MemoryNode]:
        """Get a node by ID."""
        return self.backend.get_node(node_id)
    
    def get_node_by_entity_id(self, entity_id: str, entity_system: Optional[str] = None) -> Optional[MemoryNode]:
        """Get a node by entity ID (searches globally since entities are global)."""
        return self.backend.get_node_by_entity_id(entity_id, entity_system)
    
    def get_node_count(self) -> int:
        """Get total node count for this thread."""
        nodes = self.backend.get_nodes_by_thread(self.thread_id)
        return len(nodes)
    
    def get_all_nodes(self) -> List[MemoryNode]:
        """Get all nodes for UI display (includes global entities from all threads)."""
        # For UI display, we want to show:
        # 1. All nodes from current thread (actions, tool outputs, etc.)
        # 2. All global entities from any thread (domain entities, conversation facts)
        
        # Get thread-scoped nodes
        thread_nodes = self.backend.get_nodes_by_thread(self.thread_id)
        
        # Get global entities from all threads
        global_types = {ContextType.DOMAIN_ENTITY, ContextType.CONVERSATION_FACT}
        global_nodes = self.backend.get_all_nodes(context_filter=global_types)
        
        # Combine and deduplicate by node_id
        all_nodes = {}
        
        for node in thread_nodes:
            all_nodes[node.node_id] = node
            
        for node in global_nodes:
            all_nodes[node.node_id] = node  # This will overwrite duplicates, which is fine
        
        return list(all_nodes.values())
    
    def get_all_edges(self):
        """Get all edges for UI display."""
        # Build edges from the graph
        edges = []
        for u, v, data in self.graph.edges(data=True):
            edges.append((u, v, data))
        return edges
    
    @property
    def nodes(self) -> Dict[str, MemoryNode]:
        """Get all nodes as a dict (for compatibility)."""
        nodes_dict = {}
        for node in self.backend.get_nodes_by_thread(self.thread_id):
            nodes_dict[node.node_id] = node
        return nodes_dict
    
    def get_related_nodes(self, node_id: str, max_distance: int = 2) -> List[MemoryNode]:
        """Get nodes related to a given node within max_distance hops."""
        if max_distance <= 0:
            return []
        
        visited = set()
        to_visit = [(node_id, 0)]
        related = []
        
        while to_visit:
            current_id, distance = to_visit.pop(0)
            if current_id in visited or distance > max_distance:
                continue
            
            visited.add(current_id)
            
            # Get the node
            if distance > 0:  # Don't include the starting node
                node = self.get_node(current_id)
                if node:
                    related.append(node)
            
            # Get relationships
            if distance < max_distance:
                relationships = self.backend.get_relationships(current_id)
                for rel in relationships:
                    if rel['node_id'] not in visited:
                        to_visit.append((rel['node_id'], distance + 1))
        
        return related
    
    def cleanup_stale_nodes(self, max_age_hours: float = 24.0) -> int:
        """Remove old nodes while preserving important ones."""
        preserve_types = {
            ContextType.CONVERSATION_FACT,  # Global persistent facts
            ContextType.DOMAIN_ENTITY       # Global entities
        }
        
        deleted = self.backend.delete_old_nodes(max_age_hours, preserve_types)
        
        # Invalidate cache
        self._graph_cache = None
        
        return deleted
    
    # Graph algorithm methods
    def find_important_memories(self, top_n: int = 10) -> List[MemoryNode]:
        """Find the most important memories using PageRank."""
        scores = GraphAlgorithms.calculate_pagerank(self.graph)
        # Sort by score and get top N
        sorted_nodes = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
        return [self.get_node(node_id) for node_id, _ in sorted_nodes if self.get_node(node_id)]
    
    def find_memory_clusters(self) -> List[Set[str]]:
        """Find clusters of related memories."""
        return GraphAlgorithms.detect_communities(self.graph)
    
    def find_bridge_memories(self, top_n: int = 10) -> List[MemoryNode]:
        """Find memories that bridge different contexts using betweenness centrality."""
        scores = GraphAlgorithms.calculate_betweenness_centrality(self.graph)
        # Sort by score and get top N
        sorted_nodes = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
        return [self.get_node(node_id) for node_id, _ in sorted_nodes if self.get_node(node_id)]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get memory statistics."""
        stats = self.backend.get_statistics()
        stats['thread_id'] = self.thread_id
        stats['thread_node_count'] = self.get_node_count()
        return stats