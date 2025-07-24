"""Text processing utilities for memory framework."""

import re
from typing import Set, List, Dict, Optional, Tuple
from difflib import SequenceMatcher

from ..config.memory_config import MEMORY_CONFIG


class TextProcessor:
    """Handles all text processing operations for the memory framework."""
    
    def __init__(self, config=None):
        self.config = config or MEMORY_CONFIG
        
    def tokenize(self, text: str) -> Set[str]:
        """Tokenize text for inverted index."""
        if not text:
            return set()
        
        # Convert to lowercase and split on non-alphanumeric characters
        tokens = re.findall(r'\b\w+\b', text.lower())
        
        # Filter out very short tokens and common stop words
        tokens = {t for t in tokens 
                 if len(t) >= self.config.MIN_TOKEN_LENGTH 
                 and t not in self.config.STOP_WORDS}
        
        return tokens
    
    def extract_entities(self, text: str) -> List[str]:
        """Extract entity IDs from text using patterns."""
        if not text:
            return []
        
        entities = []
        for entity_type, pattern in self.config.ENTITY_ID_PATTERNS.items():
            matches = re.findall(pattern, text)
            entities.extend(matches)
        
        return entities
    
    def extract_query_tags(self, query_text: str) -> Tuple[Set[str], List[str]]:
        """Extract tags and entities from query text.
        
        Returns:
            Tuple of (query_tags, extracted_entities)
        """
        if not query_text:
            return set(), []
        
        # Extract entities first
        extracted_entities = self.extract_entities(query_text)
        
        # Clean query for tag extraction
        cleaned_query = re.sub(r'[^\w\s\-]', ' ', query_text.lower())
        query_tags = set(word for word in cleaned_query.split() 
                        if word and len(word) > 1)
        
        return query_tags, extracted_entities
    
    def fuzzy_match(self, str1: str, str2: str, threshold: float = None) -> bool:
        """Simple fuzzy matching for typos using character similarity."""
        if not str1 or not str2:
            return False
        
        threshold = threshold or self.config.FUZZY_MATCH_THRESHOLD
        
        # Quick check: if length difference is too big, skip
        if abs(len(str1) - len(str2)) > self.config.MAX_LENGTH_DIFF_FOR_FUZZY:
            return False
        
        # Use SequenceMatcher for similarity ratio
        ratio = SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
        return ratio >= threshold
    
    def calculate_keyword_density(self, text: str, keywords: List[str]) -> float:
        """Calculate keyword density in text."""
        if not text or not keywords:
            return 0.0
        
        text_lower = text.lower()
        text_words = text_lower.split()
        
        if not text_words:
            return 0.0
        
        keyword_count = sum(text_lower.count(word.lower()) for word in keywords)
        return keyword_count / len(text_words)
    
    def is_generic_term(self, term: str) -> bool:
        """Check if a term is generic."""
        return term.lower() in self.config.GENERIC_TERMS
    
    def determine_query_type(self, query_text: str, has_entities: bool, 
                           has_semantic: bool) -> str:
        """Determine the type of query for weight adjustment."""
        if not query_text:
            return 'default'
        
        query_lower = query_text.lower()
        
        # Entity lookup queries
        if has_entities or re.match(r'^[A-Z0-9\-]+$', query_text):
            return 'entity_lookup'
        
        # Recent context queries
        if any(word in query_lower for word in ['recent', 'latest', 'last', 'previous', 'earlier']):
            return 'recent_context'
        
        # Graph navigation queries
        if any(word in query_lower for word in ['related', 'connected', 'linked', 'associated']):
            return 'graph_navigation'
        
        # Semantic queries (if embeddings available)
        if has_semantic and len(query_text.split()) > 3:
            return 'semantic_search'
        
        return 'default'
    
    def get_node_text(self, content: Dict, summary: str, tags: Set[str]) -> str:
        """Extract all searchable text from node data."""
        text_parts = []
        
        # Add summary
        if summary:
            text_parts.append(summary)
        
        # Add content based on type
        if isinstance(content, dict):
            # Extract meaningful fields
            for key, value in content.items():
                if key in ['entity_name', 'description', 'summary', 'title', 
                          'name', 'text', 'Name', 'Short_description']:
                    if value and isinstance(value, str):
                        text_parts.append(value)
        elif isinstance(content, str):
            text_parts.append(content)
        
        # Add tags
        text_parts.extend(tags)
        
        return ' '.join(text_parts)