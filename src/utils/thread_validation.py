"""Thread ID validation utilities."""

import re
from typing import Optional, Dict, Tuple
from datetime import datetime
from src.utils.logging import get_smart_logger

logger = get_smart_logger("thread_validation")


class ThreadValidator:
    """Validates and manages thread IDs across the system."""
    
    # Pattern for frontend-generated thread IDs: source-timestamp-random
    FRONTEND_THREAD_PATTERN = re.compile(r'^(web|cli|api|test)-[a-z0-9]{8,}-[a-z0-9]{7}$')
    
    # Pattern for legacy thread IDs (for backwards compatibility)
    LEGACY_THREAD_PATTERN = re.compile(r'^[a-z0-9]{8,}$')
    
    # Valid thread sources
    VALID_SOURCES = {'web', 'cli', 'api', 'test'}
    
    @classmethod
    def is_valid_thread_id(cls, thread_id: str) -> bool:
        """Check if a thread ID is valid.
        
        Args:
            thread_id: Thread ID to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not thread_id:
            return False
            
        # Check frontend pattern
        if cls.FRONTEND_THREAD_PATTERN.match(thread_id):
            return True
            
        # Check legacy pattern for backwards compatibility
        if cls.LEGACY_THREAD_PATTERN.match(thread_id):
            logger.warning("legacy_thread_id_detected", thread_id=thread_id)
            return True
            
        return False
    
    @classmethod
    def extract_thread_info(cls, thread_id: str) -> Optional[Dict[str, str]]:
        """Extract information from a thread ID.
        
        Args:
            thread_id: Thread ID to parse
            
        Returns:
            Dict with source, timestamp, and random parts, or None if invalid
        """
        if not cls.is_valid_thread_id(thread_id):
            return None
            
        # Frontend pattern: web-timestamp-random
        if cls.FRONTEND_THREAD_PATTERN.match(thread_id):
            parts = thread_id.split('-')
            return {
                'source': parts[0],
                'timestamp': parts[1],
                'random': parts[2],
                'format': 'frontend'
            }
            
        # Legacy pattern
        return {
            'source': 'legacy',
            'timestamp': None,
            'random': thread_id,
            'format': 'legacy'
        }
    
    @classmethod
    def validate_thread_context(cls, context: Dict) -> Tuple[bool, Optional[str]]:
        """Validate a complete thread context.
        
        Args:
            context: Context dict with thread_id, user_id, session_id, etc.
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields
        required_fields = ['thread_id', 'user_id']
        for field in required_fields:
            if not context.get(field):
                return False, f"Missing required field: {field}"
        
        # Validate thread ID
        thread_id = context.get('thread_id')
        if not cls.is_valid_thread_id(thread_id):
            return False, f"Invalid thread ID format: {thread_id}"
        
        # Extract and validate source
        thread_info = cls.extract_thread_info(thread_id)
        if thread_info and thread_info['source'] not in cls.VALID_SOURCES and thread_info['source'] != 'legacy':
            return False, f"Invalid thread source: {thread_info['source']}"
        
        # Validate session ID if present
        session_id = context.get('session_id')
        if session_id and not re.match(r'^session-[a-z0-9]{8,}-[a-z0-9]{7}$', session_id):
            logger.warning("invalid_session_id_format", session_id=session_id)
        
        # Validate request ID if present
        request_id = context.get('request_id')
        if request_id and not re.match(r'^req-[a-z0-9]{8,}-[a-z0-9]{7}$', request_id):
            logger.warning("invalid_request_id_format", request_id=request_id)
        
        return True, None
    
    @classmethod
    def ensure_thread_id(cls, thread_id: Optional[str], source: str = 'api') -> str:
        """Ensure a valid thread ID exists, generating one if needed.
        
        Args:
            thread_id: Existing thread ID or None
            source: Source system generating the thread
            
        Returns:
            Valid thread ID
        """
        if thread_id and cls.is_valid_thread_id(thread_id):
            return thread_id
            
        # Generate new thread ID if needed
        logger.warning("generating_fallback_thread_id", 
                      original_thread_id=thread_id,
                      source=source)
        
        import random
        import string
        timestamp = datetime.now().strftime('%s')[-8:]
        random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))
        
        return f"{source}-{timestamp}-{random_part}"