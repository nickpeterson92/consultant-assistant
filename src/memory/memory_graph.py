"""Core MemoryGraph implementation using NetworkX."""

import networkx as nx
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Any, Tuple
from collections import defaultdict
import json
import logging

from .memory_node import MemoryNode, ContextType, create_memory_node
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
        
        # Create memory node
        node = create_memory_node(
            content=content,
            context_type=context_type,
            tags=tags or set(),
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
            self.nodes_by_tag[tag].add(node.node_id)
        
        # Create relationships
        if relates_to:
            for related_node_id in relates_to:
                if related_node_id in self.nodes:
                    self.add_relationship(node.node_id, related_node_id, RelationshipType.RELATES_TO)
        
        # Update activity timestamp
        self.last_activity = datetime.now()
        
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
        
        # Extract potential tags from query text
        query_tags = set(query_text.lower().split()) if query_text else set()
        
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
                
            # Boost score based on tag matching
            tag_score = node.matches_tags(query_tags)
            
            # Boost score based on recent access
            hours_since_access = (current_time - node.last_accessed).total_seconds() / 3600
            access_boost = max(0, 0.5 - hours_since_access * 0.1)
            
            # STRONG recency boost for recent nodes (prioritizes immediate context)
            hours_since_creation = (current_time - node.created_at).total_seconds() / 3600
            if hours_since_creation < 0.1:  # Less than 6 minutes old
                recency_boost = 1.0  # Very strong boost for very recent context
            elif hours_since_creation < 0.5:  # Less than 30 minutes old  
                recency_boost = 0.5  # Strong boost for recent context
            elif hours_since_creation < 2:  # Less than 2 hours old
                recency_boost = 0.2  # Moderate boost for somewhat recent
            else:
                recency_boost = 0.0  # No boost for older context
            
            # Detect positional reference queries (these need maximum recency weighting)
            has_positional_reference = any(phrase in query_text.lower() for phrase in [
                "first one", "second one", "third one", "last one", "that one", "this one",
                "first", "second", "third", "next", "previous"
            ])
            
            if has_positional_reference:
                recency_boost *= 2.0  # Double the recency boost for positional references
            
            # Anti-spam measures: penalize nodes with spam-like characteristics
            spam_penalty = 0
            
            # Penalize nodes with excessive common tags
            common_spam_tags = {"spam", "noise", "pollution", "malicious", "hub", "connector"}
            if node.tags.intersection(common_spam_tags):
                spam_penalty += 0.3
            
            # Penalize nodes with suspiciously high keyword density
            content_str = str(node.content).lower()
            query_words = query_text.lower().split()
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
            
            final_score = max(0, base_relevance + tag_score * 0.3 + access_boost + recency_boost - spam_penalty)
            
            candidates.append((node, final_score))
            
            # Mark as accessed
            node.access()
        
        # Sort by relevance and return top results
        candidates.sort(key=lambda x: x[1], reverse=True)
        relevant_nodes = [node for node, score in candidates[:max_results]]
        
        logger.info("memory_retrieval",
                   thread_id=self.thread_id,
                   query_preview=query_text[:50],
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
            self.nodes_by_tag[tag].discard(node_id)
        
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
    
    def __str__(self) -> str:
        return f"MemoryGraph(thread={self.thread_id}, nodes={len(self.nodes)}, edges={self.graph.number_of_edges()})"
    
    def __repr__(self) -> str:
        return self.__str__()