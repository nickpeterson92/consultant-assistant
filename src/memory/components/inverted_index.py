"""Inverted index for efficient text search in memory framework."""

from typing import Set, Dict, Optional
from collections import defaultdict

from .text_processor import TextProcessor
from ..config.memory_config import MEMORY_CONFIG
from src.utils.logging.framework import SmartLogger

logger = SmartLogger("memory.index")


class InvertedIndex:
    """Manages inverted index for efficient text search."""
    
    def __init__(self, text_processor: Optional[TextProcessor] = None):
        self.text_processor = text_processor or TextProcessor()
        self._inverted_index: Dict[str, Set[str]] = defaultdict(set)
        self._node_tokens: Dict[str, Set[str]] = {}
        
    def add_document(self, doc_id: str, text: str):
        """Add a document to the index."""
        # Remove old tokens if document is being updated
        if doc_id in self._node_tokens:
            self.remove_document(doc_id)
        
        # Tokenize new text
        tokens = self.text_processor.tokenize(text)
        
        # Update index
        self._node_tokens[doc_id] = tokens
        for token in tokens:
            self._inverted_index[token].add(doc_id)
    
    def remove_document(self, doc_id: str):
        """Remove a document from the index."""
        if doc_id not in self._node_tokens:
            return
        
        # Remove from inverted index
        tokens = self._node_tokens[doc_id]
        for token in tokens:
            self._inverted_index[token].discard(doc_id)
            if not self._inverted_index[token]:
                del self._inverted_index[token]
        
        # Remove token record
        del self._node_tokens[doc_id]
    
    def search(self, query: str, min_match_ratio: float = None) -> Set[str]:
        """Search for documents matching the query.
        
        Args:
            query: Search query
            min_match_ratio: Minimum ratio of query tokens that must match
            
        Returns:
            Set of document IDs matching the query
        """
        if not query:
            return set()
        
        # Tokenize query
        query_tokens = self.text_processor.tokenize(query)
        if not query_tokens:
            return set()
        
        # Count token occurrences across all nodes
        node_token_counts = {}
        for token in query_tokens:
            if token in self._inverted_index:
                for node_id in self._inverted_index[token]:
                    if node_id not in node_token_counts:
                        node_token_counts[node_id] = 0
                    node_token_counts[node_id] += 1
        
        # Filter nodes based on token match threshold
        matching_nodes = set()
        min_match_threshold = min_match_ratio or MEMORY_CONFIG.MIN_MATCH_RATIO
        min_matches = max(1, int(len(query_tokens) * min_match_threshold))
        
        for node_id, match_count in node_token_counts.items():
            if match_count >= min_matches:
                matching_nodes.add(node_id)
        
        return matching_nodes
    
    def has_token(self, token: str) -> bool:
        """Check if a token exists in the index."""
        return token in self._inverted_index
    
    def get_token_count(self, token: str) -> int:
        """Get the number of documents containing a token."""
        return len(self._inverted_index.get(token, set()))
    
    def get_document_tokens(self, doc_id: str) -> Set[str]:
        """Get all tokens for a document."""
        return self._node_tokens.get(doc_id, set())
    
    def check_nonsense_query(self, query: str) -> bool:
        """Check if query contains any indexed tokens.
        
        Returns:
            True if query appears to be nonsense (no indexed tokens)
        """
        query_tokens = self.text_processor.tokenize(query)
        if not query_tokens:
            return True
        
        # Check if any query token exists in our index
        return not any(self.has_token(token) for token in query_tokens)
    
    def get_statistics(self) -> Dict[str, int]:
        """Get index statistics."""
        return {
            'total_tokens': len(self._inverted_index),
            'total_documents': len(self._node_tokens),
            'avg_tokens_per_doc': sum(len(tokens) for tokens in self._node_tokens.values()) / max(1, len(self._node_tokens))
        }