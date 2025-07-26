"""Configuration for memory framework."""

from typing import Set, Dict
from dataclasses import dataclass, field


@dataclass
class MemoryConfig:
    """Central configuration for memory framework behavior."""
    
    # Text processing
    MIN_TOKEN_LENGTH: int = 3
    STOP_WORDS: Set[str] = field(default_factory=lambda: {
        'a', 'an', 'the', 'is', 'it', 'in', 'on', 'at', 'to', 'for', 
        'of', 'with', 'as', 'by', 'and', 'or', 'but', 'not'
    })
    
    # Generic terms that should have lower weight
    GENERIC_TERMS: Set[str] = field(default_factory=lambda: {
        # Common/general terms
        'account', 'contact', 'opportunity', 'lead', 'case', 'task', 
        'issue', 'ticket', 'record', 'object', 'data', 'item', 'entry',
        'created', 'updated', 'new', 'old', 'first', 'last',
        # Salesforce terms
        'campaign', 'product', 'pricebook', 'order', 'contract', 'asset',
        'solution', 'document', 'folder', 'report', 'dashboard',
        # Jira terms  
        'project', 'board', 'sprint', 'epic', 'story', 'bug', 'subtask',
        'component', 'version', 'release', 'workflow', 'transition',
        # ServiceNow terms
        'incident', 'problem', 'change', 'request', 'catalog', 'knowledge',
        'service', 'user', 'group', 'assignment', 'approval', 'state',
        # Action terms
        'get', 'find', 'search', 'create', 'update', 'delete', 'list',
        'show', 'display', 'fetch', 'retrieve', 'add', 'modify', 'remove'
    })
    
    # Scoring thresholds
    MIN_RELEVANCE_SCORE: float = 0.1
    DEFAULT_MIN_SCORE: float = 0.3
    SPECIFIC_QUERY_MIN_SCORE: float = 0.5
    MIN_MATCH_RATIO: float = 0.5  # 50% of query tokens must match
    
    # Time-based parameters (in hours)
    VERY_RECENT_THRESHOLD: float = 0.1  # 6 minutes
    RECENT_THRESHOLD: float = 0.5       # 30 minutes
    SOMEWHAT_RECENT_THRESHOLD: float = 2.0  # 2 hours
    
    # Recency boost factors
    VERY_RECENT_BOOST_MAX: float = 2.0
    RECENT_BOOST_MAX: float = 1.0
    SOMEWHAT_RECENT_BOOST_MAX: float = 0.5
    TIME_DECAY_FACTOR: float = 0.01
    POSITIONAL_RECENCY_MULTIPLIER: float = 2.0
    
    # Access tracking
    ACCESS_RECENCY_WINDOW: int = 300  # 5 minutes in seconds
    ACCESS_DECAY_FACTOR: float = 0.1
    SUSPICIOUS_ACCESS_FREQUENCY: int = 10
    
    # Spam detection
    KEYWORD_DENSITY_THRESHOLD: float = 0.3
    SPAM_TAG_PENALTY: float = 0.3
    KEYWORD_DENSITY_PENALTY: float = 0.2
    SUSPICIOUS_ACCESS_PENALTY: float = 0.1
    
    # Query analysis
    QUERY_SPECIFICITY_THRESHOLD: float = 0.5
    NONSENSE_QUERY_MAX_RESULTS: int = 0
    
    # Score weights (default)
    DEFAULT_WEIGHTS: Dict[str, float] = field(default_factory=lambda: {
        'keyword': 0.40,
        'semantic': 0.25,
        'context': 0.15,
        'graph': 0.10,
        'recency': 0.20,
        'base': 0.15
    })
    
    # Entity extraction patterns
    ENTITY_ID_PATTERNS: Dict[str, str] = field(default_factory=lambda: {
        'jira': r'\b[A-Z]+-\d+\b',
        'salesforce': r'\b[a-zA-Z0-9]{15,18}\b',
        'servicenow': r'\b(?:INC|CHG|PRB|TASK|REQ|RITM|KB)\d{7}\b',
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'number': r'\b\d{6,}\b'
    })
    
    # Cache settings
    CACHE_STALENESS_MINUTES: int = 5
    METRICS_CACHE_SIZE: int = 1000
    
    # Cleanup settings
    DEFAULT_MAX_AGE_HOURS: float = 168.0  # 7 days
    MIN_NODES_TO_KEEP: int = 100
    CLEANUP_BATCH_SIZE: int = 100
    
    # Graph algorithms
    PAGERANK_ALPHA: float = 0.85
    CENTRALITY_NORMALIZED: bool = True
    MAX_PATH_LENGTH: int = 3
    
    # Retrieval settings
    DEFAULT_MAX_RESULTS: int = 10
    MAX_CANDIDATES_MULTIPLIER: int = 10  # Check 10x max_results candidates
    
    # Fuzzy matching
    FUZZY_MATCH_THRESHOLD: float = 0.8
    MAX_LENGTH_DIFF_FOR_FUZZY: int = 3
    
    def get_weight_profile(self, query_type: str) -> Dict[str, float]:
        """Get scoring weights for specific query type."""
        profiles = {
            'entity_lookup': {
                'keyword': 0.60,
                'semantic': 0.10,
                'context': 0.10,
                'graph': 0.05,
                'recency': 0.10,
                'base': 0.05
            },
            'semantic_search': {
                'keyword': 0.20,
                'semantic': 0.50,
                'context': 0.10,
                'graph': 0.05,
                'recency': 0.10,
                'base': 0.05
            },
            'recent_context': {
                'keyword': 0.20,
                'semantic': 0.20,
                'context': 0.25,
                'graph': 0.15,
                'recency': 0.40,
                'base': 0.00
            },
            'graph_navigation': {
                'keyword': 0.10,
                'semantic': 0.10,
                'context': 0.20,
                'graph': 0.40,
                'recency': 0.15,
                'base': 0.05
            }
        }
        return profiles.get(query_type, self.DEFAULT_WEIGHTS)


# Global instance
MEMORY_CONFIG = MemoryConfig()