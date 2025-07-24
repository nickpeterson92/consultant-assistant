"""Simple semantic embedding support for memory retrieval."""

import numpy as np
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Try to import sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logger.warning("sentence-transformers not available - falling back to keyword matching")


class SemanticEmbeddings:
    """Manages semantic embeddings for memory nodes."""
    
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """Initialize with a sentence transformer model.
        
        Model options:
        - 'all-MiniLM-L6-v2': 80MB, fast, good quality (recommended)
        - 'all-mpnet-base-v2': 420MB, slower, best quality
        - 'paraphrase-MiniLM-L3-v2': 60MB, fastest, okay quality
        """
        self.model = None
        self.embeddings_cache: Dict[str, np.ndarray] = {}
        
        if EMBEDDINGS_AVAILABLE:
            try:
                self.model = SentenceTransformer(model_name)
                logger.info(f"Loaded embedding model: {model_name}")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
    
    def is_available(self) -> bool:
        """Check if embeddings are available."""
        return self.model is not None
    
    def encode_text(self, text: str) -> Optional[np.ndarray]:
        """Encode text to embedding vector."""
        if not self.model:
            return None
            
        # Check cache first
        if text in self.embeddings_cache:
            return self.embeddings_cache[text]
        
        try:
            # Generate embedding
            embedding = self.model.encode(text, convert_to_numpy=True)
            
            # Cache it
            self.embeddings_cache[text] = embedding
            
            # Limit cache size
            if len(self.embeddings_cache) > 1000:
                # Remove oldest entries
                keys_to_remove = list(self.embeddings_cache.keys())[:100]
                for key in keys_to_remove:
                    del self.embeddings_cache[key]
            
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to encode text: {e}")
            return None
    
    def calculate_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings."""
        if embedding1 is None or embedding2 is None:
            return 0.0
            
        # Cosine similarity
        dot_product = np.dot(embedding1, embedding2)
        norm_product = np.linalg.norm(embedding1) * np.linalg.norm(embedding2)
        
        if norm_product == 0:
            return 0.0
            
        return float(dot_product / norm_product)
    
    def find_similar(self, query_embedding: np.ndarray, 
                    candidate_embeddings: List[Tuple[str, np.ndarray]], 
                    top_k: int = 10) -> List[Tuple[str, float]]:
        """Find most similar embeddings to query.
        
        Returns:
            List of (node_id, similarity_score) tuples
        """
        if not query_embedding.any() or not candidate_embeddings:
            return []
        
        similarities = []
        
        for node_id, candidate_embedding in candidate_embeddings:
            if candidate_embedding is not None:
                similarity = self.calculate_similarity(query_embedding, candidate_embedding)
                similarities.append((node_id, similarity))
        
        # Sort by similarity (highest first)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]


# Global instance (lazy loaded)
_embeddings_instance = None


def get_embeddings() -> SemanticEmbeddings:
    """Get or create the global embeddings instance."""
    global _embeddings_instance
    if _embeddings_instance is None:
        _embeddings_instance = SemanticEmbeddings()
    return _embeddings_instance