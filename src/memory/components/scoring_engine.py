"""Scoring engine for memory retrieval relevance calculation."""

from typing import Dict, List, Set, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from ..core.memory_node import MemoryNode
from .text_processor import TextProcessor
from ..config.memory_config import MEMORY_CONFIG
from src.utils.logging.framework import SmartLogger

logger = SmartLogger("memory.scoring")


@dataclass
class QueryContext:
    """Context for scoring operations."""
    query_text: str
    query_tags: Set[str]
    extracted_entities: List[str]
    query_embedding: Optional[any] = None
    query_type: str = 'default'
    current_time: datetime = None
    
    def __post_init__(self):
        if self.current_time is None:
            self.current_time = datetime.now()


@dataclass
class ScoreComponents:
    """Individual components of the final score."""
    tag_score: float = 0.0
    semantic_score: float = 0.0
    context_score: float = 0.0
    graph_score: float = 0.0
    recency_boost: float = 0.0
    base_relevance: float = 0.0
    spam_penalty: float = 0.0
    
    def calculate_final_score(self, weights: Dict[str, float]) -> float:
        """Calculate final weighted score."""
        return max(0, (
            self.tag_score * weights.get('keyword', 0.40) +
            self.semantic_score * weights.get('semantic', 0.25) +
            self.context_score * weights.get('context', 0.15) +
            self.graph_score * weights.get('graph', 0.10) +
            self.recency_boost * weights.get('recency', 0.20) +
            self.base_relevance * weights.get('base', 0.15) -
            self.spam_penalty
        ))


class ScoringEngine:
    """Handles all scoring operations for memory retrieval."""
    
    def __init__(self, config=None, text_processor=None):
        self.config = config or MEMORY_CONFIG
        self.text_processor = text_processor or TextProcessor(self.config)
        
    def score_node(self, node: MemoryNode, context: QueryContext, 
                   recent_accessed_nodes: List[Tuple[str, datetime]] = None,
                   graph_distance_func=None) -> Tuple[float, ScoreComponents]:
        """Calculate comprehensive score for a node.
        
        Returns:
            Tuple of (final_score, score_components)
        """
        components = ScoreComponents()
        
        # Base relevance
        components.base_relevance = node.current_relevance()
        
        # Tag/keyword score
        components.tag_score = self._calculate_tag_score(node, context)
        
        # Semantic score (if embeddings available)
        if context.query_embedding is not None and node.embedding is not None:
            components.semantic_score = self._calculate_semantic_score(
                context.query_embedding, node.embedding
            )
        
        # Recency boost
        components.recency_boost = self._calculate_recency_boost(node, context)
        
        # Context score (based on recently accessed nodes)
        if recent_accessed_nodes:
            components.context_score = self._calculate_context_score(
                node, context, recent_accessed_nodes
            )
        
        # Graph distance score
        if graph_distance_func:
            components.graph_score = graph_distance_func(node)
        
        # Spam penalty
        components.spam_penalty = self._calculate_spam_penalty(node, context)
        
        # Get appropriate weights for query type
        weights = self.config.get_weight_profile(context.query_type)
        
        # Calculate final score
        final_score = components.calculate_final_score(weights)
        
        return final_score, components
    
    def _calculate_tag_score(self, node: MemoryNode, context: QueryContext) -> float:
        """Calculate tag/keyword matching score."""
        if not context.query_tags and not context.extracted_entities:
            return 0.0
        
        score = 0.0
        penalty = 0.0
        
        # Get node content
        content = node.content if isinstance(node.content, dict) else {}
        entity_name = content.get('entity_name', '')
        entity_name_lower = entity_name.lower() if entity_name else ''
        
        # Get node's full text for matching
        node_text = self.text_processor.get_node_text(
            content, node.summary, node.tags
        ).lower()
        
        # Check extracted entities
        if context.extracted_entities and entity_name_lower:
            entity_matched = False
            for entity in context.extracted_entities:
                entity_lower = entity.lower() if entity else ''
                if entity_lower == entity_name_lower:
                    score += 3.0  # Very high weight for exact entity match
                    entity_matched = True
                elif len(entity_lower) > 3 and entity_lower in entity_name_lower:
                    score += 1.5  # Partial match only for meaningful entities
                    entity_matched = True
            
            # Penalty if entity was expected but not found
            if not entity_matched:
                penalty += 0.5
        
        # Check individual tags
        if context.query_tags:
            total_matches = 0
            meaningful_matches = 0
            
            for tag in context.query_tags:
                if tag is None or len(tag) < 3:
                    continue
                
                tag_lower = tag.lower()
                
                # Check if tag appears in node content
                if tag_lower in node_text:
                    total_matches += 1
                    
                    # Higher weight for non-generic terms
                    if not self.text_processor.is_generic_term(tag_lower):
                        meaningful_matches += 1
                        score += 1.0
                    else:
                        score += 0.2  # Much lower weight for generic terms
            
            # Apply penalty if match ratio is too low
            if len(context.query_tags) > 2:  # For multi-word queries
                match_ratio = total_matches / len(context.query_tags)
                if match_ratio < 0.5:  # Less than 50% match
                    penalty += (1.0 - match_ratio) * 2.0  # Strong penalty
            
            # Bonus for high-quality matches
            if meaningful_matches >= 2:
                score += meaningful_matches * 0.5
        
        return max(0, score - penalty)
    
    def _calculate_semantic_score(self, query_embedding, node_embedding) -> float:
        """Calculate semantic similarity score."""
        try:
            from ..algorithms.semantic_embeddings import get_embeddings
            embeddings = get_embeddings()
            return embeddings.calculate_similarity(query_embedding, node_embedding)
        except Exception:
            return 0.0
    
    def _calculate_recency_boost(self, node: MemoryNode, context: QueryContext) -> float:
        """Calculate recency boost based on node age."""
        hours_since_creation = (context.current_time - node.created_at).total_seconds() / 3600
        
        # Continuous recency boost - more recent is always better
        if hours_since_creation < self.config.VERY_RECENT_THRESHOLD:
            boost = self.config.VERY_RECENT_BOOST_MAX + \
                   (self.config.VERY_RECENT_THRESHOLD - hours_since_creation) * 10
        elif hours_since_creation < self.config.RECENT_THRESHOLD:
            boost = self.config.RECENT_BOOST_MAX + \
                   (self.config.RECENT_THRESHOLD - hours_since_creation) * 1.0
        elif hours_since_creation < self.config.SOMEWHAT_RECENT_THRESHOLD:
            boost = self.config.SOMEWHAT_RECENT_BOOST_MAX + \
                   (self.config.SOMEWHAT_RECENT_THRESHOLD - hours_since_creation) * 0.2
        elif hours_since_creation < 24:  # Less than 1 day
            # Gradual decay from 0.1 to 0.2 over the day
            boost = 0.1 + (24.0 - hours_since_creation) * 0.004
        else:
            # Old content still gets a minimum boost
            boost = max(0.05, 0.1 - (hours_since_creation - 24) * 0.001)
        
        # Detect positional reference queries
        if context.query_text:
            has_positional = any(phrase in context.query_text.lower() for phrase in [
                "first one", "second one", "third one", "last one", "that one", 
                "this one", "first", "second", "third", "next", "previous"
            ])
            if has_positional:
                boost *= self.config.POSITIONAL_RECENCY_MULTIPLIER
        
        return boost
    
    def _calculate_context_score(self, node: MemoryNode, context: QueryContext,
                               recent_accessed_nodes: List[Tuple[str, datetime]]) -> float:
        """Calculate context score based on recently accessed entities."""
        score = 0.0
        
        # Get recent entity IDs
        recent_entity_ids = set()
        for node_id, access_time in recent_accessed_nodes:
            time_diff = (context.current_time - access_time).total_seconds()
            if time_diff < self.config.ACCESS_RECENCY_WINDOW:
                recent_entity_ids.add(node_id)
        
        # Check if this node was recently accessed
        if node.node_id in recent_entity_ids:
            score += 2.0
        
        # Check for entity ID matches
        if isinstance(node.content, dict):
            node_entity_id = (node.content.get('entity_id') or 
                            node.content.get('Id') or 
                            node.content.get('id'))
            
            if node_entity_id and str(node_entity_id) in recent_entity_ids:
                score += 1.5
        
        return score
    
    def _calculate_spam_penalty(self, node: MemoryNode, context: QueryContext) -> float:
        """Calculate spam penalty for nodes with spam-like characteristics."""
        penalty = 0.0
        
        # Penalize nodes with spam tags
        spam_tags = {"spam", "noise", "pollution", "malicious", "hub", "connector"}
        if node.tags.intersection(spam_tags):
            penalty += self.config.SPAM_TAG_PENALTY
        
        # Penalize high keyword density
        if context.query_text:
            content_str = str(node.content).lower() if node.content else ""
            query_words = context.query_text.lower().split()
            
            if query_words and content_str:
                keyword_density = self.text_processor.calculate_keyword_density(
                    content_str, query_words
                )
                if keyword_density > self.config.KEYWORD_DENSITY_THRESHOLD:
                    penalty += self.config.KEYWORD_DENSITY_PENALTY
        
        # Penalize nodes accessed too recently compared to creation
        # (This is a simplified heuristic since we don't track access count)
        hours_since_creation = (context.current_time - node.created_at).total_seconds() / 3600
        hours_since_access = (context.current_time - node.last_accessed).total_seconds() / 3600
        if hours_since_creation > 0.1 and hours_since_access < 0.01:
            # Accessed very recently after creation - might be spam
            penalty += self.config.SUSPICIOUS_ACCESS_PENALTY
        
        return penalty
    
    def determine_query_type_and_weights(self, query_text: str, query_tags: Set[str],
                                       has_semantic: bool) -> Tuple[str, Dict[str, float]]:
        """Determine query type and get appropriate scoring weights."""
        # Check if we have extracted entities
        entities = self.text_processor.extract_entities(query_text)
        has_entities = bool(entities)
        
        # Determine query type
        query_type = self.text_processor.determine_query_type(
            query_text, has_entities, has_semantic
        )
        
        # Get weights for this query type
        weights = self.config.get_weight_profile(query_type)
        
        return query_type, weights