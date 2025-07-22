"""Core MemoryGraph implementation using NetworkX."""

import networkx as nx
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Any, Tuple
from collections import defaultdict
import json
import logging

from .memory_node import MemoryNode, ContextType, create_memory_node
from .graph_algorithms import GraphAlgorithms
from src.utils.logging.framework import SmartLogger

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
    """Graph-based conversational memory for a single thread."""
    
    def __init__(self, thread_id: str):
        self.thread_id = thread_id
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        
        # Core data structures
        self.nodes: Dict[str, MemoryNode] = {}
        self.graph = nx.MultiDiGraph()  # Directed graph with multiple edge types
        
        # Indexing for fast lookups
        self.nodes_by_type: Dict[ContextType, Set[str]] = defaultdict(set)
        self.nodes_by_tag: Dict[str, Set[str]] = defaultdict(set)
        
        # Statistics
        self.total_nodes_created = 0
        self.total_nodes_cleaned = 0
        
        # Cached graph metrics (invalidated on graph changes)
        self._pagerank_cache = None
        self._centrality_cache = None
        self._community_cache = None
        
        # Conversation tracking for better multi-turn support
        self._recent_query_history: List[Tuple[str, datetime]] = []  # (query, timestamp)
        self._recent_accessed_nodes: List[Tuple[str, datetime]] = []  # (node_id, timestamp)
        self._last_metrics_update = None
        
        logger.info("memory_graph_created", 
                   thread_id=thread_id,
                   component="memory")
    
    def store(self, content: Any, context_type: ContextType,
              tags: Optional[Set[str]] = None,
              summary: str = "",
              relates_to: Optional[List[str]] = None,
              base_relevance: float = 1.0,
              auto_summarize: bool = True) -> str:
        """Store content in memory graph with relationships."""
        
        # Auto-generate summary if requested and not provided
        final_summary = summary
        if auto_summarize and not summary.strip():
            from .summary_generator import auto_generate_summary
            final_summary = auto_generate_summary(content, context_type, tags or set())
            
            logger.debug("auto_generated_summary",
                        thread_id=self.thread_id,
                        context_type=context_type.value,
                        generated_summary=final_summary,
                        component="memory")
        
        # Clean tags - remove None values and convert to lowercase
        clean_tags = {tag.lower() for tag in (tags or set()) if tag is not None}
        
        # Create memory node
        node = create_memory_node(
            content=content,
            context_type=context_type,
            tags=clean_tags,
            summary=final_summary,
            base_relevance=base_relevance
        )
        
        # Store in main structures
        self.nodes[node.node_id] = node
        self.graph.add_node(node.node_id)
        self.total_nodes_created += 1
        
        # Update indexes
        self.nodes_by_type[context_type].add(node.node_id)
        for tag in node.tags:
            # Ensure tags are stored in lowercase for consistent retrieval
            self.nodes_by_tag[tag.lower()].add(node.node_id)
        
        # Create relationships
        if relates_to:
            for related_node_id in relates_to:
                if related_node_id in self.nodes:
                    self.add_relationship(node.node_id, related_node_id, RelationshipType.RELATES_TO)
        
        # Update activity timestamp
        self.last_activity = datetime.now()
        
        # Invalidate cached metrics
        self._invalidate_metrics_cache()
        
        logger.info("memory_node_stored",
                   thread_id=self.thread_id,
                   node_id=node.node_id,
                   context_type=context_type.value,
                   tags=list(node.tags),
                   component="memory")
        
        return node.node_id
    
    def add_relationship(self, from_node_id: str, to_node_id: str, 
                        relationship_type: str, weight: float = 1.0):
        """Add a relationship between two nodes."""
        if from_node_id in self.nodes and to_node_id in self.nodes:
            self.graph.add_edge(from_node_id, to_node_id, 
                               type=relationship_type, 
                               weight=weight,
                               created_at=datetime.now())
            
            # Update node relationship lists
            self.nodes[from_node_id].derived_nodes.append(to_node_id)
            self.nodes[to_node_id].source_nodes.append(from_node_id)
            
            # Invalidate cached metrics
            self._invalidate_metrics_cache()
            
            logger.debug("relationship_added",
                        thread_id=self.thread_id,
                        from_node=from_node_id,
                        to_node=to_node_id,
                        type=relationship_type,
                        component="memory")
    
    def retrieve_relevant(self, query_text: str = "", 
                         context_filter: Optional[Set[ContextType]] = None,
                         max_age_hours: Optional[float] = None,
                         min_relevance: float = 0.1,
                         max_results: int = 10,
                         required_tags: Optional[Set[str]] = None,
                         excluded_tags: Optional[Set[str]] = None) -> List[MemoryNode]:
        """Retrieve nodes relevant to current context."""
        
        candidates = []
        current_time = datetime.now()
        
        # Handle None query_text
        if query_text is None:
            query_text = ""
        
        # Extract and clean potential tags from query text
        # Remove special characters but keep important ones
        import re
        cleaned_query = re.sub(r'[^\w\s\-]', ' ', query_text.lower() if query_text else '')
        query_tags = set(word for word in cleaned_query.split() if word and len(word) > 1)
        
        # Extract entities from original query (preserves capitalization)
        extracted_entities = self._extract_query_entities(query_text)
        
        # Try to get query embedding for semantic search
        query_embedding = None
        try:
            from .semantic_embeddings import get_embeddings
            embeddings = get_embeddings()
            if embeddings.is_available() and query_text:
                query_embedding = embeddings.encode_text(query_text)
        except Exception:
            pass
        
        for node_id, node in self.nodes.items():
            # Filter by context type
            if context_filter and node.context_type not in context_filter:
                continue
                
            # Filter by age
            if max_age_hours:
                age_hours = (current_time - node.created_at).total_seconds() / 3600
                if age_hours > max_age_hours:
                    continue
            
            # Filter by required tags (ALL must be present)
            if required_tags and not required_tags.issubset(node.tags):
                continue
                
            # Filter by excluded tags (NONE should be present)
            if excluded_tags and excluded_tags.intersection(node.tags):
                continue
            
            # Calculate relevance score
            base_relevance = node.current_relevance()
            if base_relevance < min_relevance:
                continue
                
            # Smart tag matching with weighted scoring
            tag_score = self._calculate_smart_tag_score(node, query_tags, query_text, extracted_entities)
            
            # Semantic similarity score (if embeddings available)
            semantic_score = 0.0
            if query_embedding is not None and node.embedding is not None:
                from .semantic_embeddings import get_embeddings
                embeddings = get_embeddings()
                semantic_score = embeddings.calculate_similarity(query_embedding, node.embedding)
            
            # Boost score based on recent access
            hours_since_access = (current_time - node.last_accessed).total_seconds() / 3600
            access_boost = max(0, 0.5 - hours_since_access * 0.1)
            
            # STRONG recency boost for recent nodes (prioritizes immediate context)
            hours_since_creation = (current_time - node.created_at).total_seconds() / 3600
            
            # Continuous recency boost - more recent is always better
            if hours_since_creation < 0.1:  # Less than 6 minutes old
                recency_boost = 1.0 + (0.1 - hours_since_creation) * 10  # Extra boost for very recent (up to +2.0)
            elif hours_since_creation < 0.5:  # Less than 30 minutes old  
                recency_boost = 0.5 + (0.5 - hours_since_creation) * 1.0  # Scaled boost (0.5 to 1.0)
            elif hours_since_creation < 2:  # Less than 2 hours old
                recency_boost = 0.2 + (2.0 - hours_since_creation) * 0.2  # Scaled boost (0.2 to 0.5)
            else:
                recency_boost = max(0.0, 0.1 - hours_since_creation * 0.01)  # Gradual decay
            
            # Detect positional reference queries (these need maximum recency weighting)
            has_positional_reference = any(phrase in query_text.lower() for phrase in [
                "first one", "second one", "third one", "last one", "that one", "this one",
                "first", "second", "third", "next", "previous"
            ]) if query_text else False
            
            if has_positional_reference:
                recency_boost *= 2.0  # Double the recency boost for positional references
            
            # Anti-spam measures: penalize nodes with spam-like characteristics
            spam_penalty = 0
            
            # Penalize nodes with excessive common tags
            common_spam_tags = {"spam", "noise", "pollution", "malicious", "hub", "connector"}
            if node.tags.intersection(common_spam_tags):
                spam_penalty += 0.3
            
            # Penalize nodes with suspiciously high keyword density
            content_str = str(node.content).lower() if node.content else ""
            query_words = query_text.lower().split() if query_text else []
            if query_words:
                keyword_density = sum(content_str.count(word) for word in query_words) / len(content_str.split()) if content_str else 0
                if keyword_density > 0.3:  # More than 30% keyword density is suspicious
                    spam_penalty += 0.2
            
            # Penalize nodes that were accessed artificially frequently (possible manipulation)
            hours_since_creation = (current_time - node.created_at).total_seconds() / 3600
            if hours_since_creation > 0:
                access_frequency = (current_time - node.created_at).total_seconds() / 3600  # Simple heuristic
                if access_frequency > 10:  # Very frequent access pattern
                    spam_penalty += 0.1
            
            # Graph distance score (nodes connected to recent activity)
            graph_score = self._calculate_graph_distance_score(node)
            
            # Context boost (recently accessed entities)
            context_score = self._calculate_context_score(node, query_text)
            
            # Determine query type and get adaptive weights
            query_type, weights = self._determine_query_type_and_weights(
                query_text, query_tags, semantic_score > 0)
            
            # Store query type for logging
            self._last_query_type = query_type
            
            # Calculate final score using adaptive weights
            if weights.get('semantic', 0) > 0 and semantic_score > 0:
                # Use semantic scoring
                final_score = max(0,
                    semantic_score * weights.get('semantic', 0) +
                    tag_score * weights.get('keyword', 0) +
                    context_score * weights.get('context', 0) +
                    graph_score * weights.get('graph', 0) +
                    recency_boost * weights.get('recency', 0) +
                    base_relevance * weights.get('base', 0) -
                    spam_penalty
                )
            else:
                # Fallback to keyword-only scoring
                final_score = max(0,
                    tag_score * weights.get('keyword', 0.40) +
                    context_score * weights.get('context', 0.15) +
                    graph_score * weights.get('graph', 0.10) +
                    recency_boost * weights.get('recency', 0.20) +
                    base_relevance * weights.get('base', 0.15) -
                    spam_penalty
                )
            
            candidates.append((node, final_score))
            
            # Don't mark as accessed yet - only mark returned results
        
        # Sort by relevance and return top results
        candidates.sort(key=lambda x: x[1], reverse=True)
        relevant_nodes = [node for node, score in candidates[:max_results]]
        
        # Mark only returned results as accessed
        for node in relevant_nodes:
            node.access()
            # Track accessed nodes for conversation context
            self._recent_accessed_nodes.append((node.node_id, current_time))
        
        # Track query for conversation history
        self._recent_query_history.append((query_text, current_time))
        
        # Clean up old history (keep last 10 queries and 20 accessed nodes)
        self._recent_query_history = self._recent_query_history[-10:]
        self._recent_accessed_nodes = self._recent_accessed_nodes[-20:]
        
        # Log query type detected (if we have results)
        if relevant_nodes and candidates:
            first_query_type = getattr(self, '_last_query_type', 'unknown')
            logger.info("memory_retrieval",
                       thread_id=self.thread_id,
                       query_preview=query_text[:50],
                       query_type=first_query_type,
                       candidates_found=len(candidates),
                       results_returned=len(relevant_nodes),
                       component="memory")
        
        return relevant_nodes
    
    def find_by_type(self, context_type: ContextType, 
                     max_age_hours: Optional[float] = None,
                     min_relevance: float = 0.1) -> List[MemoryNode]:
        """Find nodes by context type."""
        node_ids = self.nodes_by_type.get(context_type, set())
        results = []
        current_time = datetime.now()
        
        for node_id in node_ids:
            node = self.nodes[node_id]
            
            # Filter by age
            if max_age_hours:
                age_hours = (current_time - node.created_at).total_seconds() / 3600
                if age_hours > max_age_hours:
                    continue
            
            # Filter by relevance
            if node.current_relevance() < min_relevance:
                continue
                
            results.append(node)
            node.access()
        
        # Sort by relevance
        results.sort(key=lambda n: n.current_relevance(), reverse=True)
        return results
    
    def find_by_tags(self, tags: Set[str], 
                     match_threshold: float = 0.3) -> List[MemoryNode]:
        """Find nodes matching given tags."""
        candidate_node_ids = set()
        
        # Collect all nodes that have any of the query tags
        for tag in tags:
            if tag is not None:
                candidate_node_ids.update(self.nodes_by_tag.get(tag.lower(), set()))
        
        results = []
        for node_id in candidate_node_ids:
            node = self.nodes[node_id]
            match_score = node.matches_tags(tags)
            
            if match_score >= match_threshold:
                results.append((node, match_score))
                node.access()
        
        # Sort by match score
        results.sort(key=lambda x: x[1], reverse=True)
        return [node for node, score in results]
    
    def get_related_nodes(self, node_id: str, 
                         relationship_types: Optional[Set[str]] = None,
                         max_hops: int = 2) -> List[MemoryNode]:
        """Get nodes related to given node through graph traversal."""
        if node_id not in self.nodes:
            return []
        
        # Use NetworkX for graph traversal
        related_node_ids = set()
        
        # BFS traversal up to max_hops
        current_level = {node_id}
        visited = {node_id}
        
        for hop in range(max_hops):
            next_level = set()
            
            for current_node_id in current_level:
                # Get outgoing edges
                for neighbor in self.graph.successors(current_node_id):
                    if neighbor not in visited:
                        edge_data = self.graph.get_edge_data(current_node_id, neighbor)
                        
                        # Check relationship type filter
                        if relationship_types:
                            edge_types = {data.get('type') for data in edge_data.values()}
                            if not edge_types.intersection(relationship_types):
                                continue
                        
                        next_level.add(neighbor)
                        related_node_ids.add(neighbor)
                
                # Get incoming edges
                for neighbor in self.graph.predecessors(current_node_id):
                    if neighbor not in visited:
                        edge_data = self.graph.get_edge_data(neighbor, current_node_id)
                        
                        # Check relationship type filter
                        if relationship_types:
                            edge_types = {data.get('type') for data in edge_data.values()}
                            if not edge_types.intersection(relationship_types):
                                continue
                        
                        next_level.add(neighbor)
                        related_node_ids.add(neighbor)
            
            visited.update(next_level)
            current_level = next_level
            
            if not current_level:  # No more nodes to explore
                break
        
        # Return memory nodes, mark as accessed
        related_nodes = []
        for related_id in related_node_ids:
            if related_id in self.nodes:
                node = self.nodes[related_id]
                node.access()
                related_nodes.append(node)
        
        return related_nodes
    
    def cleanup_stale_nodes(self) -> int:
        """Remove nodes that have decayed below relevance threshold."""
        stale_node_ids = []
        
        for node_id, node in self.nodes.items():
            if node.is_stale():
                stale_node_ids.append(node_id)
        
        # Remove stale nodes
        for node_id in stale_node_ids:
            self._remove_node(node_id)
        
        cleaned_count = len(stale_node_ids)
        self.total_nodes_cleaned += cleaned_count
        
        if cleaned_count > 0:
            logger.info("memory_cleanup",
                       thread_id=self.thread_id,
                       nodes_cleaned=cleaned_count,
                       nodes_remaining=len(self.nodes),
                       component="memory")
        
        return cleaned_count
    
    def _remove_node(self, node_id: str):
        """Internal method to remove a node and its relationships."""
        if node_id not in self.nodes:
            return
        
        node = self.nodes[node_id]
        
        # Remove from indexes
        self.nodes_by_type[node.context_type].discard(node_id)
        for tag in node.tags:
            # Use lowercase to match how tags are stored
            self.nodes_by_tag[tag.lower()].discard(node_id)
        
        # Remove from graph
        self.graph.remove_node(node_id)
        
        # Remove from main storage
        del self.nodes[node_id]
    
    def get_stats(self) -> Dict:
        """Get memory graph statistics."""
        context_counts = {
            context_type.value: len(node_ids) 
            for context_type, node_ids in self.nodes_by_type.items()
            if node_ids
        }
        
        age_hours = (datetime.now() - self.created_at).total_seconds() / 3600
        
        return {
            'thread_id': self.thread_id,
            'total_nodes': len(self.nodes),
            'total_edges': self.graph.number_of_edges(),
            'context_type_counts': context_counts,
            'total_created': self.total_nodes_created,
            'total_cleaned': self.total_nodes_cleaned,
            'age_hours': round(age_hours, 1),
            'last_activity': self.last_activity.isoformat()
        }
    
    def mark_task_completed(self, task_related_tags: Set[str] = None,
                           related_node_ids: List[str] = None):
        """Mark task-specific memory as completed to trigger faster decay."""
        
        nodes_to_decay = []
        
        # Find nodes to decay by tags
        if task_related_tags:
            for tag in task_related_tags:
                if tag is not None:
                    candidate_node_ids = self.nodes_by_tag.get(tag.lower(), set())
                nodes_to_decay.extend(candidate_node_ids)
        
        # Find nodes to decay by direct IDs
        if related_node_ids:
            nodes_to_decay.extend(related_node_ids)
        
        # Also find related nodes through graph traversal
        all_related = set(nodes_to_decay)
        for node_id in list(nodes_to_decay):
            if node_id in self.nodes:
                # Get nodes that led to this one (source nodes)
                related = self.get_related_nodes(node_id, max_hops=1)
                all_related.update(node.node_id for node in related)
        
        # Apply decay to task-specific context types
        task_specific_types = {
            ContextType.USER_SELECTION,
            ContextType.SEARCH_RESULT,  # May need fresh search for new task
            ContextType.TEMPORARY_STATE
        }
        
        nodes_decayed = 0
        for node_id in all_related:
            if node_id in self.nodes:
                node = self.nodes[node_id]
                if node.context_type in task_specific_types:
                    # Aggressive decay for completed task context
                    node.base_relevance = min(node.base_relevance, 0.2)
                    node.decay_rate = max(node.decay_rate, 1.0)  # Fast decay
                    nodes_decayed += 1
        
        logger.info("task_completion_decay",
                   thread_id=self.thread_id,
                   nodes_decayed=nodes_decayed,
                   task_tags=list(task_related_tags) if task_related_tags else [],
                   component="memory")
        
        return nodes_decayed
    
    def _invalidate_metrics_cache(self):
        """Invalidate cached graph metrics."""
        self._pagerank_cache = None
        self._centrality_cache = None
        self._community_cache = None
        self._last_metrics_update = None
    
    def _update_metrics_cache(self):
        """Update cached graph metrics if needed."""
        # Only update if cache is stale (older than 5 minutes) or invalid
        if (self._last_metrics_update is None or 
            datetime.now() - self._last_metrics_update > timedelta(minutes=5)):
            
            # Calculate PageRank
            self._pagerank_cache = GraphAlgorithms.calculate_pagerank(self.graph)
            
            # Calculate centrality
            self._centrality_cache = GraphAlgorithms.calculate_betweenness_centrality(self.graph)
            
            # Detect communities
            self._community_cache = GraphAlgorithms.detect_communities(self.graph)
            
            self._last_metrics_update = datetime.now()
            
            logger.debug("graph_metrics_updated",
                        thread_id=self.thread_id,
                        pagerank_nodes=len(self._pagerank_cache),
                        communities=len(self._community_cache))
    
    def retrieve_with_graph_intelligence(self, query_text: str = "",
                                       context_filter: Optional[Set[ContextType]] = None,
                                       max_results: int = 10,
                                       use_pagerank: bool = True,
                                       use_centrality: bool = True,
                                       use_activation_spreading: bool = True,
                                       initial_nodes: Optional[Set[str]] = None) -> List[MemoryNode]:
        """Retrieve memories using advanced graph algorithms.
        
        This method combines traditional relevance scoring with graph-based
        metrics for more intelligent retrieval.
        
        Args:
            query_text: Query string for relevance matching
            context_filter: Filter by context types
            max_results: Maximum number of results
            use_pagerank: Weight results by PageRank importance
            use_centrality: Weight results by betweenness centrality
            use_activation_spreading: Use spreading activation from initial nodes
            initial_nodes: Starting nodes for activation spreading
            
        Returns:
            List of relevant MemoryNode objects
        """
        # First get traditionally relevant nodes
        base_results = self.retrieve_relevant(
            query_text=query_text,
            context_filter=context_filter,
            max_results=max_results * 3  # Get more candidates for re-ranking
        )
        
        if not base_results:
            return []
        
        # Update metrics cache if needed
        self._update_metrics_cache()
        
        # Build scoring dict
        node_scores = {}
        
        for node in base_results:
            base_score = node.current_relevance()
            
            # Add PageRank score
            if use_pagerank and self._pagerank_cache:
                pagerank_score = self._pagerank_cache.get(node.node_id, 0.0)
                base_score += pagerank_score * 2.0  # Weight PageRank strongly
            
            # Add centrality score
            if use_centrality and self._centrality_cache:
                centrality_score = self._centrality_cache.get(node.node_id, 0.0)
                base_score += centrality_score * 1.5
            
            node_scores[node.node_id] = base_score
        
        # Apply activation spreading if requested
        if use_activation_spreading:
            # Use initial nodes or highest scoring nodes as seeds
            if initial_nodes:
                activated_nodes = initial_nodes
            else:
                # Use top 3 scoring nodes as seeds
                top_nodes = sorted(node_scores.items(), key=lambda x: x[1], reverse=True)[:3]
                activated_nodes = {node_id for node_id, _ in top_nodes}
            
            activation_levels = GraphAlgorithms.find_activation_spreading(
                self.graph,
                activated_nodes,
                decay_factor=0.6,
                max_hops=2
            )
            
            # Boost scores based on activation
            for node_id, activation in activation_levels.items():
                if node_id in node_scores:
                    node_scores[node_id] += activation * 1.5
        
        # Sort by final scores and return top results
        sorted_nodes = sorted(node_scores.items(), key=lambda x: x[1], reverse=True)
        result_ids = [node_id for node_id, _ in sorted_nodes[:max_results]]
        
        # Return nodes in score order
        results = []
        for node_id in result_ids:
            if node_id in self.nodes:
                results.append(self.nodes[node_id])
        
        logger.info("graph_intelligent_retrieval",
                   thread_id=self.thread_id,
                   query=query_text[:50],
                   base_candidates=len(base_results),
                   final_results=len(results),
                   used_pagerank=use_pagerank,
                   used_centrality=use_centrality,
                   used_activation=use_activation_spreading)
        
        return results
    
    def find_memory_clusters(self) -> List[List[MemoryNode]]:
        """Find clusters of related memories using community detection.
        
        Returns:
            List of memory clusters, each cluster is a list of MemoryNodes
        """
        self._update_metrics_cache()
        
        if not self._community_cache:
            return []
        
        clusters = []
        for community in self._community_cache:
            cluster = []
            for node_id in community:
                if node_id in self.nodes:
                    cluster.append(self.nodes[node_id])
            
            if len(cluster) > 1:  # Only include clusters with multiple nodes
                clusters.append(cluster)
        
        # Sort clusters by size (largest first)
        clusters.sort(key=len, reverse=True)
        
        logger.info("memory_clusters_found",
                   thread_id=self.thread_id,
                   cluster_count=len(clusters),
                   cluster_sizes=[len(c) for c in clusters])
        
        return clusters
    
    def find_important_memories(self, top_n: int = 10) -> List[MemoryNode]:
        """Find the most important memories based on PageRank.
        
        Args:
            top_n: Number of top memories to return
            
        Returns:
            List of important MemoryNodes
        """
        self._update_metrics_cache()
        
        if not self._pagerank_cache:
            return []
        
        # Sort by PageRank score
        sorted_nodes = sorted(self._pagerank_cache.items(), 
                            key=lambda x: x[1], 
                            reverse=True)
        
        results = []
        for node_id, score in sorted_nodes[:top_n]:
            if node_id in self.nodes:
                results.append(self.nodes[node_id])
        
        logger.info("important_memories_found",
                   thread_id=self.thread_id,
                   requested=top_n,
                   found=len(results))
        
        return results
    
    def find_bridge_memories(self, top_n: int = 10) -> List[MemoryNode]:
        """Find memories that bridge different topics/clusters.
        
        These are memories with high betweenness centrality that connect
        different parts of the memory graph.
        
        Args:
            top_n: Number of bridge memories to return
            
        Returns:
            List of bridge MemoryNodes
        """
        self._update_metrics_cache()
        
        if not self._centrality_cache:
            return []
        
        # Sort by centrality score
        sorted_nodes = sorted(self._centrality_cache.items(),
                            key=lambda x: x[1],
                            reverse=True)
        
        results = []
        for node_id, score in sorted_nodes[:top_n]:
            if node_id in self.nodes and score > 0:  # Only include nodes with positive centrality
                results.append(self.nodes[node_id])
        
        logger.info("bridge_memories_found",
                   thread_id=self.thread_id,
                   requested=top_n,
                   found=len(results))
        
        return results
    
    def get_memory_timeline(self, start_time: Optional[datetime] = None,
                          end_time: Optional[datetime] = None) -> List[List[MemoryNode]]:
        """Get memories organized by temporal clusters.
        
        Args:
            start_time: Start of time range (None for all)
            end_time: End of time range (None for all)
            
        Returns:
            List of temporal clusters
        """
        # Filter nodes by time range
        filtered_nodes = {}
        for node_id, node in self.nodes.items():
            if start_time and node.created_at < start_time:
                continue
            if end_time and node.created_at > end_time:
                continue
            filtered_nodes[node_id] = node
        
        # Get temporal clusters
        clusters = GraphAlgorithms.temporal_clustering(
            filtered_nodes,
            time_window=timedelta(minutes=30)
        )
        
        # Convert to MemoryNode lists
        result = []
        for cluster_ids in clusters:
            cluster_nodes = []
            for node_id in cluster_ids:
                if node_id in self.nodes:
                    cluster_nodes.append(self.nodes[node_id])
            
            if cluster_nodes:
                result.append(cluster_nodes)
        
        return result
    
    def _determine_query_type_and_weights(self, query_text: str, query_tags: Set[str], 
                                         has_embeddings: bool) -> Tuple[str, Dict[str, float]]:
        """Determine query type and return adaptive weights.
        
        Returns:
            Tuple of (query_type, weight_dict)
        """
        import re
        
        # Analyze query characteristics
        query_lower = query_text.lower() if query_text else ""
        word_count = len(query_text.split())
        
        # Check for entity ID pattern (e.g., 001ABC, 0019b00000)
        has_entity_id = bool(re.search(r'\b[0-9]{3}[A-Za-z0-9]+\b', query_text))
        
        # Check for follow-up indicators
        follow_up_indicators = {'that', 'this', 'same', 'previous', 'last', 'above', 
                               'mentioned', 'it', 'one', 'those', 'these'}
        has_follow_up = any(indicator in query_tags for indicator in follow_up_indicators)
        
        # Check for natural language patterns
        is_natural_language = any(word in query_lower for word in 
                                 ["what's", "what is", "show me", "find me", "tell me", 
                                  "how many", "list all", "get all"])
        
        # Determine query type and weights
        if not has_embeddings:
            # Fallback weights without embeddings
            if has_follow_up:
                return ("follow_up_no_embed", {
                    'keyword': 0.08,
                    'context': 0.80,
                    'graph': 0.05,
                    'recency': 0.05,
                    'base': 0.02
                })
            else:
                return ("normal_no_embed", {
                    'keyword': 0.40,
                    'context': 0.15,
                    'graph': 0.10,
                    'recency': 0.20,
                    'base': 0.15
                })
        
        # With embeddings - adaptive weights based on query type
        if has_entity_id:
            # Direct entity query - keyword matching dominates
            return ("entity_query", {
                'semantic': 0.15,
                'keyword': 0.60,
                'context': 0.10,
                'graph': 0.05,
                'recency': 0.10,
                'base': 0.00
            })
        
        elif has_follow_up:
            # Follow-up reference - semantic + context crucial
            return ("follow_up_query", {
                'semantic': 0.50,
                'keyword': 0.10,
                'context': 0.35,
                'graph': 0.05,
                'recency': 0.00,
                'base': 0.00
            })
        
        elif word_count <= 2 and not is_natural_language:
            # Short query - could be entity or concept
            return ("short_query", {
                'semantic': 0.35,
                'keyword': 0.35,
                'context': 0.15,
                'graph': 0.10,
                'recency': 0.05,
                'base': 0.00
            })
        
        elif is_natural_language or word_count > 5:
            # Natural language query - semantic understanding important
            return ("natural_language", {
                'semantic': 0.45,
                'keyword': 0.20,
                'context': 0.20,
                'graph': 0.10,
                'recency': 0.05,
                'base': 0.00
            })
        
        else:
            # Default balanced approach
            return ("balanced_query", {
                'semantic': 0.35,
                'keyword': 0.25,
                'context': 0.15,
                'graph': 0.10,
                'recency': 0.15,
                'base': 0.00
            })
    
    def _calculate_smart_tag_score(self, node: MemoryNode, query_tags: Set[str], 
                                  query_text: str, extracted_entities: List[str] = None) -> float:
        """Calculate intelligent tag matching score with weighted importance."""
        if not query_tags and not extracted_entities:
            return 0.0
        
        score = 0.0
        content = node.content if isinstance(node.content, dict) else {}
        entity_name = content.get('entity_name', '')
        entity_name_lower = entity_name.lower() if entity_name else ''
        
        # First check extracted entities (higher priority)
        if extracted_entities and entity_name_lower:
            for entity in extracted_entities:
                entity_lower = entity.lower() if entity else ''
                if entity_lower == entity_name_lower:
                    score += 2.0  # Very high weight for exact entity match
                elif entity_lower in entity_name_lower or entity_name_lower in entity_lower:
                    score += 1.5  # High weight for partial match
                elif self._fuzzy_match(entity_lower, entity_name_lower):
                    score += 1.0  # Good weight for fuzzy match
        
        # Then check individual tags
        if not query_tags:
            return score
            
        # Identify generic terms in query
        generic_terms = {'account', 'contact', 'opportunity', 'lead', 'case', 'task', 
                        'issue', 'ticket', 'record', 'object', 'data', 'the', 'a', 'an'}
        query_generic_count = len(query_tags.intersection(generic_terms))
        query_specific_count = len(query_tags) - query_generic_count
        
        # Calculate query specificity (0-1, higher = more specific)
        query_specificity = query_specific_count / len(query_tags) if query_tags else 0
        
        # Check each query tag
        for tag in query_tags:
            if tag is None:
                continue
            tag_lower = tag.lower()
            
            # High weight for exact entity name matches
            entity_name = content.get('entity_name', '')
            entity_name_lower = entity_name.lower() if entity_name else ''
            
            # Check for exact match
            if entity_name_lower and entity_name_lower == tag_lower:
                score += 1.5  # Boost exact matches
            # Check for partial match
            elif entity_name_lower and tag_lower in entity_name_lower:
                score += 1.0
            # Check for fuzzy match (handles typos)
            elif entity_name_lower and self._fuzzy_match(tag_lower, entity_name_lower):
                score += 0.7
            
            # Very low weight for generic type matches
            elif tag_lower == (content.get('entity_type', '').lower() if content.get('entity_type', '') else ''):
                score += 0.1  # Even lower for generic types
            
            # Medium weight for other tag matches
            elif tag_lower in node.tags:
                if tag_lower in generic_terms:
                    score += 0.05  # Minimal weight for generic
                else:
                    score += 0.6  # Good weight for specific terms
        
        # Boost score if query is specific and node matches well
        if query_specificity > 0.5 and score > 0:
            score *= (1 + query_specificity * 0.5)
        
        # Heavy penalty for generic-only queries
        if query_specificity == 0 and len(query_tags) > 0:
            # All tags are generic - massively reduce score
            score *= 0.1
        
        # Normalize by number of query tags
        normalized_score = score / max(1, len(query_tags)) if query_tags else score
        
        # Final adjustment based on whether we found entity matches
        if extracted_entities and normalized_score < 0.5:
            # Had entities but low match - penalize
            normalized_score *= 0.5
            
        return normalized_score
    
    def _calculate_graph_distance_score(self, node: MemoryNode) -> float:
        """Calculate score based on graph distance from recently accessed nodes."""
        # Use tracked recent accessed nodes instead of scanning all nodes
        current_time = datetime.now()
        recent_node_ids = []
        
        # Get nodes accessed in last 5 minutes from our tracked history
        for node_id, access_time in self._recent_accessed_nodes:
            if (current_time - access_time).total_seconds() < 300:  # 5 minutes
                if node_id != node.node_id and node_id in self.nodes:
                    recent_node_ids.append(node_id)
        
        if not recent_node_ids or node.node_id not in self.graph:
            return 0.0
        
        # Calculate minimum distance to any recent node
        min_distance = float('inf')
        for recent_id in recent_node_ids[:5]:  # Check top 5 most recent
            if recent_id in self.graph:
                try:
                    distance = nx.shortest_path_length(
                        self.graph, 
                        source=node.node_id, 
                        target=recent_id,
                        weight=None
                    )
                    min_distance = min(min_distance, distance)
                except nx.NetworkXNoPath:
                    continue
        
        # Convert distance to score (closer = higher score, but more conservative)
        # Also consider the type of connection
        if min_distance == 1:
            # Check if it's a meaningful connection
            # Domain entities connected to actions get lower boost than entity-to-entity
            if node.context_type == ContextType.DOMAIN_ENTITY:
                return 0.3  # Moderate boost for direct connections
            else:
                return 0.2  # Lower boost for non-entities
        elif min_distance == 2:
            return 0.1  # Small boost for one hop away
        elif min_distance == 3:
            return 0.05  # Tiny boost for two hops away
        else:
            return 0.0  # Too far or not connected
    
    def _calculate_context_score(self, node: MemoryNode, query_text: str) -> float:
        """Calculate score based on conversation context and recent entity access."""
        score = 0.0
        
        # Calculate query characteristics
        query_lower = query_text.lower() if query_text else ""
        query_words = query_lower.split()
        
        # Identify generic terms
        generic_terms = {'account', 'contact', 'opportunity', 'lead', 'case', 'task', 
                        'issue', 'ticket', 'record', 'object', 'data', 'get', 'find', 
                        'show', 'the', 'a', 'an', 'all', 'any'}
        
        # Calculate query specificity
        specific_words = [w for w in query_words if w not in generic_terms and len(w) > 2]
        query_specificity = len(specific_words) / max(1, len(query_words))
        
        # Check if this node was explicitly accessed (not just created)
        # Look in our tracked history
        was_accessed = False
        access_recency = float('inf')
        
        for accessed_id, access_time in reversed(self._recent_accessed_nodes):
            if accessed_id == node.node_id:
                was_accessed = True
                access_recency = (datetime.now() - access_time).total_seconds() / 60
                break
        
        # Base context score based on explicit access (not creation)
        if was_accessed:
            if access_recency < 2:
                base_score = 1.0
            elif access_recency < 5:
                base_score = 0.6
            elif access_recency < 15:
                base_score = 0.3
            else:
                base_score = 0.1
        else:
            base_score = 0.0
        
        # Apply specificity modifier - generic queries get reduced context boost
        score = base_score * (0.3 + 0.7 * query_specificity)
        
        # Follow-up query detection
        follow_up_indicators = ['that', 'this', 'same', 'previous', 'last', 'above', 
                               'mentioned', 'again', 'also', 'another']
        
        # Strong follow-up indicators
        strong_follow_up = ['that', 'this', 'same']
        
        if any(indicator in query_lower for indicator in follow_up_indicators):
            if was_accessed and access_recency < 10:
                # Strong indicators get bigger boost
                if any(indicator in query_lower for indicator in strong_follow_up):
                    score += 1.0
                else:
                    score += 0.5
        
        # Penalize if query contains specific names that don't match this node
        content = node.content if isinstance(node.content, dict) else {}
        entity_name_raw = content.get('entity_name', '')
        entity_name = entity_name_raw.lower() if entity_name_raw else ''
        
        # Look for capitalized words that might be entity names
        potential_names = [w for w in query_text.split() if w and len(w) > 2 and w[0].isupper()]
        for name in potential_names:
            if name and name.lower() not in generic_terms and entity_name and name.lower() not in entity_name:
                # Query mentions a specific name that doesn't match this entity
                score *= 0.3
        
        # Special handling for pure follow-up queries
        pure_follow_up = all(word in follow_up_indicators or word in generic_terms 
                           for word in query_words if len(word) > 1)
        
        # Check if this is the most recently accessed node
        is_most_recent = False
        if self._recent_accessed_nodes:
            most_recent_id, _ = self._recent_accessed_nodes[-1]
            is_most_recent = (node.node_id == most_recent_id)
        
        if pure_follow_up:
            if is_most_recent:
                # This is THE most recent node and it's a pure follow-up
                score += 5.0  # Overwhelming boost
            elif was_accessed and access_recency < 2:
                # Recently accessed with pure follow-up query
                score += 2.0  # Strong boost
        
        return score
    
    def _fuzzy_match(self, str1: str, str2: str, threshold: float = 0.8) -> bool:
        """Simple fuzzy matching for typos using character similarity."""
        if not str1 or not str2:
            return False
            
        # Quick check - if lengths are too different, skip
        if abs(len(str1) - len(str2)) > 3:
            return False
            
        # Calculate simple similarity
        # Count matching characters in order
        matches = 0
        j = 0
        for i in range(len(str1)):
            while j < len(str2) and str1[i] != str2[j]:
                j += 1
            if j < len(str2):
                matches += 1
                j += 1
                
        similarity = matches / max(len(str1), len(str2))
        return similarity >= threshold
    
    def _extract_query_entities(self, query_text: str) -> List[str]:
        """Extract potential entity names from query, including compound names."""
        words = query_text.split()
        entities = []
        
        # Look for capitalized words (potential entity names)
        for i, word in enumerate(words):
            if word and (word[0].isupper() or word.isdigit()):
                # Check if next word is also capitalized (compound name)
                if i + 1 < len(words) and (words[i+1][0].isupper() or words[i+1].isdigit()):
                    entities.append(f"{word} {words[i+1]}")
                entities.append(word)
                
        # Also look for patterns like "company 42"
        for i in range(len(words) - 1):
            if words[i] and words[i].lower() in ['company', 'account', 'contact'] and words[i+1].isdigit():
                entities.append(f"{words[i]} {words[i+1]}")
                
        return entities
    
    def __str__(self) -> str:
        return f"MemoryGraph(thread={self.thread_id}, nodes={len(self.nodes)}, edges={self.graph.number_of_edges()})"
    
    def __repr__(self) -> str:
        return self.__str__()