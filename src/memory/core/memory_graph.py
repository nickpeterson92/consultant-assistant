"""Graph-based conversational memory using component-based architecture."""

import networkx as nx
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Any, Tuple

from .memory_node import MemoryNode, ContextType, create_memory_node
from ..components.node_manager import NodeManager
from ..components.text_processor import TextProcessor
from ..components.scoring_engine import ScoringEngine, QueryContext
from ..algorithms.graph_algorithms import GraphAlgorithms
from ..config.memory_config import MEMORY_CONFIG
from src.utils.logging.framework import SmartLogger
from src.utils.thread_utils import ThreadIDManager

logger = SmartLogger("memory")


class RelationshipType:
    """Standard relationship types between memory nodes."""
    LED_TO = "led_to"           # A caused B
    RELATES_TO = "relates_to"   # A is semantically related to B  
    DEPENDS_ON = "depends_on"   # A requires B for context
    CONTRADICTS = "contradicts" # A conflicts with B
    REFINES = "refines"         # A is a more specific version of B
    ANSWERS = "answers"         # A answers question B


class MemoryGraph:
    """Graph-based conversational memory with clean architecture."""
    
    def __init__(self, thread_id: str, config=None):
        # Validate thread ID format
        if not ThreadIDManager.is_valid_thread_id(thread_id):
            raise ValueError(f"Invalid thread ID format: {thread_id}. Expected 'agent-task_id' format.")
            
        self.thread_id = thread_id
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.config = config or MEMORY_CONFIG
        
        # Core components
        self.node_manager = NodeManager(thread_id, self.config)
        self.text_processor = TextProcessor(self.config)
        self.scoring_engine = ScoringEngine(self.config, self.text_processor)
        
        # Graph for relationships
        self.graph = nx.MultiDiGraph()
        
        # Cache for graph metrics
        self._metrics_cache = None
        self._cache_timestamp = None
    
    def store(self, content: Any, 
             context_type: ContextType,
             summary: Optional[str] = None,
             tags: Optional[Set[str]] = None,
             relates_to: Optional[List[str]] = None,
             depends_on: Optional[List[str]] = None,
             confidence: float = 1.0,
             metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store a memory node with automatic entity extraction and indexing."""
        
        # Create memory node
        node = create_memory_node(
            content=content,
            context_type=context_type,
            summary=summary,
            tags=tags,
            base_relevance=confidence
        )
        
        # Add metadata if provided
        if metadata:
            for key, value in metadata.items():
                setattr(node, key, value)
        
        # Add to storage
        node_id = self.node_manager.add_node(node)
        
        # Add to graph
        self.graph.add_node(node_id)
        
        # Add relationships
        if relates_to:
            for related_id in relates_to:
                if related_id in self.node_manager.nodes:
                    self.add_relationship(node_id, related_id, RelationshipType.RELATES_TO)
        
        if depends_on:
            for dependency_id in depends_on:
                if dependency_id in self.node_manager.nodes:
                    self.add_relationship(node_id, dependency_id, RelationshipType.DEPENDS_ON)
        
        # Update activity timestamp
        self.last_activity = datetime.now()
        
        # Invalidate cache
        self._invalidate_cache()
        
        logger.info("memory_node_stored",
                   thread_id=self.thread_id,
                   node_id=node_id,
                   type=context_type.value,
                   tags=list(tags) if tags else [],
                   component="memory")
        
        return node_id
    
    def retrieve_relevant(self, query_text: str = "", 
                         context_filter: Optional[Set[ContextType]] = None,
                         max_age_hours: Optional[float] = None,
                         min_relevance: float = None,
                         max_results: int = 10,
                         required_tags: Optional[Set[str]] = None,
                         excluded_tags: Optional[Set[str]] = None,
                         min_score: Optional[float] = None) -> List[MemoryNode]:
        """Retrieve nodes relevant to current context using clean architecture."""
        
        min_relevance = min_relevance or self.config.MIN_RELEVANCE_SCORE
        
        # Handle None or empty query
        if not query_text:
            query_text = ""
        
        # FAST PATH: Direct entity ID lookup
        if query_text:
            node = self.node_manager.get_node_by_entity_id(query_text)
            if node:
                self.node_manager.track_access(node.node_id)
                logger.info("entity_id_fast_path",
                           thread_id=self.thread_id,
                           entity_id=query_text)
                return [node]
        
        # Extract query information
        query_tags, extracted_entities = self.text_processor.extract_query_tags(query_text)
        
        # Get query embedding if available
        query_embedding = None
        try:
            from ..algorithms.semantic_embeddings import get_embeddings
            embeddings = get_embeddings()
            if embeddings.is_available() and query_text:
                query_embedding = embeddings.encode_text(query_text)
        except Exception:
            pass
        
        # Create query context
        context = QueryContext(
            query_text=query_text,
            query_tags=query_tags,
            extracted_entities=extracted_entities,
            query_embedding=query_embedding
        )
        
        # Determine query type and weights
        context.query_type, weights = self.scoring_engine.determine_query_type_and_weights(
            query_text, query_tags, query_embedding is not None
        )
        
        # Get candidate nodes
        candidates = self._get_candidate_nodes(query_text, context_filter, 
                                              max_age_hours, required_tags, 
                                              excluded_tags)
        
        # Score and rank candidates
        scored_candidates = []
        for node_id in candidates:
            node = self.node_manager.get_node(node_id)
            if not node:
                continue
            
            # Check minimum relevance
            if node.current_relevance() < min_relevance:
                continue
            
            # Calculate comprehensive score
            final_score, components = self.scoring_engine.score_node(
                node, context,
                self.node_manager.get_recent_accessed(),
                lambda n: self._calculate_graph_distance_score(n.node_id)
            )
            
            # Apply minimum score threshold
            min_score_threshold = min_score if min_score is not None else self.config.DEFAULT_MIN_SCORE
            
            # Increase threshold for very specific queries only
            if query_text and len(query_text.split()) > 3:
                min_score_threshold = max(min_score_threshold, self.config.SPECIFIC_QUERY_MIN_SCORE)
            
            
            if final_score >= min_score_threshold:
                scored_candidates.append((node, final_score))
        
        # Sort by score
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        
        # Additional filtering to reduce false positives
        if len(scored_candidates) > 3:
            # Calculate score distribution
            scores = [score for _, score in scored_candidates]
            avg_score = sum(scores) / len(scores)
            top_score = scores[0]
            
            # If there's a big gap between top results and average, filter more aggressively
            if top_score > avg_score * 2 and top_score > 0.5:
                cutoff_candidates = []
                for node, score in scored_candidates:
                    # Keep results that are reasonably close to the top score
                    if score >= top_score * 0.6:
                        cutoff_candidates.append((node, score))
                scored_candidates = cutoff_candidates
        
        # Use the requested max_results
        actual_max_results = max_results
        
        # Get top results and track access
        results = []
        for node, score in scored_candidates[:actual_max_results]:
            self.node_manager.track_access(node.node_id)
            results.append(node)
        
        logger.info("memory_retrieval",
                   thread_id=self.thread_id,
                   query=query_text[:50] if query_text else "empty",
                   query_type=context.query_type,
                   candidates=len(candidates),
                   results=len(results))
        
        return results
    
    def add_relationship(self, from_node_id: str, to_node_id: str, 
                        relationship_type: str, weight: float = 1.0):
        """Add a directed relationship between nodes."""
        if from_node_id in self.node_manager.nodes and to_node_id in self.node_manager.nodes:
            self.graph.add_edge(from_node_id, to_node_id, 
                              type=relationship_type, weight=weight)
            self._invalidate_cache()
    
    def get_related_nodes(self, node_id: str, relationship_types: Optional[Set[str]] = None,
                         max_distance: int = 2) -> List[MemoryNode]:
        """Get nodes related through specific relationship types."""
        if node_id not in self.graph:
            return []
        
        related_ids = set()
        
        # Direct relationships (both directions)
        # Check successors (outgoing edges)
        for successor in self.graph.successors(node_id):
            edges = self.graph.get_edge_data(node_id, successor)
            if edges:
                for edge_data in edges.values():
                    if not relationship_types or edge_data.get('type') in relationship_types:
                        related_ids.add(successor)
        
        # Check predecessors (incoming edges)
        for predecessor in self.graph.predecessors(node_id):
            edges = self.graph.get_edge_data(predecessor, node_id)
            if edges:
                for edge_data in edges.values():
                    if not relationship_types or edge_data.get('type') in relationship_types:
                        related_ids.add(predecessor)
        
        # Extended relationships if max_distance > 1
        if max_distance > 1:
            visited = {node_id}
            current_level = related_ids.copy()
            
            for _ in range(max_distance - 1):
                next_level = set()
                for current_id in current_level:
                    if current_id in visited:
                        continue
                    visited.add(current_id)
                    
                    # Check successors
                    for successor in self.graph.successors(current_id):
                        if successor not in visited:
                            edges = self.graph.get_edge_data(current_id, successor)
                            if edges:
                                for edge_data in edges.values():
                                    if not relationship_types or edge_data.get('type') in relationship_types:
                                        next_level.add(successor)
                    
                    # Check predecessors
                    for predecessor in self.graph.predecessors(current_id):
                        if predecessor not in visited:
                            edges = self.graph.get_edge_data(predecessor, current_id)
                            if edges:
                                for edge_data in edges.values():
                                    if not relationship_types or edge_data.get('type') in relationship_types:
                                        next_level.add(predecessor)
                
                related_ids.update(next_level)
                current_level = next_level
        
        # Convert to nodes
        related_nodes = []
        for node_id in related_ids:
            node = self.node_manager.get_node(node_id)
            if node:
                related_nodes.append(node)
        
        return related_nodes
    
    def cleanup_stale_nodes(self, max_age_hours: float = None) -> int:
        """Remove old or irrelevant nodes."""
        removed = self.node_manager.cleanup_stale_nodes(max_age_hours)
        
        # Also remove from graph
        for node_id in list(self.graph.nodes()):
            if node_id not in self.node_manager.nodes:
                self.graph.remove_node(node_id)
        
        if removed > 0:
            self._invalidate_cache()
        
        return removed
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        stats = self.node_manager.get_statistics()
        stats.update({
            'graph_nodes': self.graph.number_of_nodes(),
            'graph_edges': self.graph.number_of_edges(),
            'graph_density': nx.density(self.graph) if self.graph.number_of_nodes() > 1 else 0,
            'thread_age_hours': (datetime.now() - self.created_at).total_seconds() / 3600
        })
        return stats
    
    def get_all_nodes(self) -> List[MemoryNode]:
        """Get all nodes in the memory graph."""
        nodes = []
        for node_id in self.graph.nodes():
            node = self.node_manager.get_node(node_id)
            if node:
                nodes.append(node)
        return nodes
    
    def get_all_edges(self) -> List[Tuple[str, str, Dict[str, Any]]]:
        """Get all edges in the memory graph as (from_id, to_id, data) tuples."""
        return list(self.graph.edges(data=True))
    
    def _get_candidate_nodes(self, query_text: str, context_filter, 
                           max_age_hours, required_tags, excluded_tags) -> List[str]:
        """Get candidate nodes for scoring."""
        # Start with text search if we have a query
        if query_text:
            # Check for nonsense query
            if self.node_manager.inverted_index.check_nonsense_query(query_text):
                # If we have very few nodes, don't filter as nonsense
                # This helps with semantic search in small graphs
                if len(self.node_manager.nodes) > 100:
                    logger.info("nonsense_query_detected",
                               thread_id=self.thread_id,
                               query=query_text[:50])
                    return []
                # Otherwise, let it fall through to the broadening logic below
            
            # Search using inverted index
            candidate_ids = self.node_manager.search_by_text(query_text)
            
            
            # If too few results, broaden search
            if len(candidate_ids) < 5:
                candidate_ids = set(self.node_manager.nodes.keys())
        else:
            # No query text, start with all nodes
            candidate_ids = set(self.node_manager.nodes.keys())
        
        # Apply filters
        filtered_ids = self.node_manager.filter_nodes(
            candidate_ids, context_filter, max_age_hours, 
            required_tags, excluded_tags
        )
        
        return filtered_ids
    
    def _calculate_graph_distance_score(self, node_id: str) -> float:
        """Calculate score based on graph distance from recently accessed nodes."""
        recent_nodes = self.node_manager.get_recent_accessed()
        if not recent_nodes or node_id not in self.graph:
            return 0.0
        
        current_time = datetime.now()
        total_score = 0.0
        
        for recent_id, access_time in recent_nodes:
            if recent_id == node_id or recent_id not in self.graph:
                continue
            
            # Calculate time weight
            time_weight = max(0, 1.0 - (current_time - access_time).total_seconds() / 300)
            
            try:
                # Calculate shortest path
                path_length = nx.shortest_path_length(self.graph, recent_id, node_id)
                distance_score = 1.0 / (1.0 + path_length)
                total_score += distance_score * time_weight
            except nx.NetworkXNoPath:
                continue
        
        return total_score
    
    def _invalidate_cache(self):
        """Invalidate cached metrics."""
        self._metrics_cache = None
        self._cache_timestamp = None
    
    def _update_metrics_cache(self):
        """Update cached graph metrics if needed."""
        if (self._metrics_cache is None or 
            self._cache_timestamp is None or
            (datetime.now() - self._cache_timestamp) > timedelta(minutes=5)):
            
            self._metrics_cache = {
                'pagerank': GraphAlgorithms.calculate_pagerank(self.graph) if self.graph.number_of_nodes() > 0 else {},
                'centrality': GraphAlgorithms.calculate_betweenness_centrality(self.graph) if self.graph.number_of_nodes() > 0 else {},
                'communities': GraphAlgorithms.detect_communities(self.graph) if self.graph.number_of_nodes() > 1 else []
            }
            self._cache_timestamp = datetime.now()
    
    def find_important_memories(self, top_n: int = 10) -> List[MemoryNode]:
        """Find the most important memories using PageRank algorithm."""
        self._update_metrics_cache()
        
        if not self._metrics_cache or 'pagerank' not in self._metrics_cache:
            return []
        
        # Sort nodes by PageRank score
        pagerank_scores = self._metrics_cache['pagerank']
        sorted_nodes = sorted(pagerank_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Return top N nodes
        important_nodes = []
        for node_id, score in sorted_nodes[:top_n]:
            node = self.node_manager.get_node(node_id)
            if node:
                important_nodes.append(node)
        
        return important_nodes
    
    def find_memory_clusters(self) -> List[Set[str]]:
        """Find memory clusters using community detection."""
        self._update_metrics_cache()
        
        if not self._metrics_cache or 'communities' not in self._metrics_cache:
            return []
        
        return self._metrics_cache['communities']
    
    def find_bridge_memories(self, top_n: int = 5) -> List[MemoryNode]:
        """Find bridge memories that connect different clusters."""
        self._update_metrics_cache()
        
        if not self._metrics_cache or 'centrality' not in self._metrics_cache:
            return []
        
        # Sort nodes by betweenness centrality
        centrality_scores = self._metrics_cache['centrality']
        sorted_nodes = sorted(centrality_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Return top N nodes
        bridge_nodes = []
        for node_id, score in sorted_nodes[:top_n]:
            node = self.node_manager.get_node(node_id)
            if node:
                bridge_nodes.append(node)
        
        return bridge_nodes
    
    def _is_entity_id_query(self, query: str) -> bool:
        """Check if query looks like an entity ID lookup."""
        if not query:
            return False
        
        query = query.strip()
        
        # Common ID patterns
        patterns = [
            r'^[A-Z]{2,}-\d+$',  # JIRA-123, INC-456
            r'^\d{3}[A-Z0-9]+$',  # 001ABC123
            r'^[A-Z]+\d{3,}$',   # INC001234
            r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$',  # UUID
        ]
        
        import re
        return any(re.match(pattern, query) for pattern in patterns)