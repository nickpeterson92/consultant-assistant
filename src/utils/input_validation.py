"""User Input Validation for Orchestrator Boundary.

Provides security validation for human user inputs at the orchestrator boundary.
Follows 2024 best practices: validate external inputs only, trust internal LLM outputs.

Philosophy:
- Only validate human inputs at the orchestrator boundary
- Trust LLM-generated content (they format correctly and safely)
- Focus on XSS/HTML injection prevention, not SQL injection
- Keep it simple - LLMs handle complex formatting
"""

import re
import logging

from .logging import get_logger

logger = get_logger()

class ValidationError(Exception):
    """Custom validation error for user input"""
    pass

class InputSanitizer:
    """Sanitizes user input for security (XSS, HTML injection prevention only)"""
    
    # Dangerous patterns that should be rejected in user input
    DANGEROUS_PATTERNS = [
        re.compile(r'<script.*?>', re.IGNORECASE),
        re.compile(r'javascript:', re.IGNORECASE),
        re.compile(r'data:text/html', re.IGNORECASE),
        re.compile(r'vbscript:', re.IGNORECASE),
        re.compile(r'on\w+\s*=', re.IGNORECASE),
        re.compile(r'expression\s*\(', re.IGNORECASE),
        re.compile(r'@import', re.IGNORECASE),
        re.compile(r'<!--.*?-->', re.DOTALL),
    ]
    
    @staticmethod
    def sanitize_user_input(value: str, max_length: int = 50000) -> str:
        """Sanitize human user input for security.
        
        Only checks for XSS/HTML injection, not SQL injection
        (LLMs generate safe SQL/SOQL queries).
        
        Args:
            value: User input string to sanitize
            max_length: Maximum allowed length
            
        Returns:
            Sanitized string safe for processing
        """
        if not isinstance(value, str):
            raise ValidationError(f"Expected string, got {type(value)}")
        
        # Check length
        if len(value) > max_length:
            raise ValidationError(f"Input too long: {len(value)} > {max_length}")
        
        # Check for dangerous HTML/script patterns only
        for pattern in InputSanitizer.DANGEROUS_PATTERNS:
            if pattern.search(value):
                raise ValidationError("Potentially malicious content detected")
        
        # Basic sanitization
        sanitized = value.strip()
        
        # Remove null bytes
        sanitized = sanitized.replace('\x00', '')
        
        return sanitized


def validate_orchestrator_input(user_input: str) -> str:
    """Validate orchestrator user input - the ONLY validation we need.
    
    This is called at the boundary where human users interact with the system.
    We don't validate:
    - LLM-generated content (they format correctly)
    - Agent-to-agent communication (agents trust each other)
    - API parameters (let the APIs handle their own validation)
    
    Args:
        user_input: Raw input from human user
        
    Returns:
        Validated and sanitized input
        
    Raises:
        ValidationError: If input is malicious or invalid
    """
    try:
        if not isinstance(user_input, str):
            raise ValidationError(f"Expected string, got {type(user_input)}")
        
        # Check for empty input
        if len(user_input.strip()) == 0:
            raise ValidationError("Empty input not allowed")
        
        # Sanitize for security (XSS/HTML only, not SQL)
        validated = InputSanitizer.sanitize_user_input(user_input)
        
        return validated
        
    except Exception as e:
        # Only log actual errors, not expected validation issues
        if "empty input" not in str(e).lower():
            logger.error("input_validation_failed",
                component="utils",
                operation="validate_orchestrator_input",
                error=str(e),
                error_type=type(e).__name__
            )
        raise ValidationError(f"Orchestrator input validation failed: {e}")