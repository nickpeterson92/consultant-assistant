"""
Comprehensive Input Validation for Multi-Agent System
Provides security and data integrity validation for all agent inputs and API calls
"""

import re
import json
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ValidationError
import logging

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Custom validation error"""
    pass

class InputSanitizer:
    """Sanitizes and validates various types of input"""
    
    # Regex patterns for validation
    SALESFORCE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9]{15}$|^[a-zA-Z0-9]{18}$')
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    PHONE_PATTERN = re.compile(r'^[\+]?[1-9][\d]{0,15}$')
    URL_PATTERN = re.compile(r'^https?://[^\s/$.?#].[^\s]*$', re.IGNORECASE)
    UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
    
    # Dangerous patterns that should be rejected
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
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        re.compile(r"('|(\\')|(;)|(\\;)|(\\x27)|(\\x3D))", re.IGNORECASE),
        re.compile(r"(\\x3D)|(\\x27)|(\\x22)|(\\x0D)|(\\x0A)", re.IGNORECASE),
        re.compile(r"(exec(\s|\+)+(s|x)p\w+)", re.IGNORECASE),
        re.compile(r"(union(.|\n)*?select)", re.IGNORECASE),
        re.compile(r"(drop(.|\n)*?(table|database))", re.IGNORECASE),
        re.compile(r"(insert(.|\n)*?into)", re.IGNORECASE),
        re.compile(r"(update(.|\n)*?set)", re.IGNORECASE),
        re.compile(r"(delete(.|\n)*?from)", re.IGNORECASE),
    ]
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000, allow_html: bool = False, check_sql_injection: bool = True) -> str:
        """Sanitize and validate string input
        
        Args:
            value: String to sanitize
            max_length: Maximum allowed length
            allow_html: Whether to allow HTML content
            check_sql_injection: Whether to check for SQL injection patterns (disabled for natural language)
        """
        if not isinstance(value, str):
            raise ValidationError(f"Expected string, got {type(value)}")
        
        # Check length
        if len(value) > max_length:
            raise ValidationError(f"String too long: {len(value)} > {max_length}")
        
        # Check for dangerous patterns
        if not allow_html:
            for pattern in InputSanitizer.DANGEROUS_PATTERNS:
                if pattern.search(value):
                    raise ValidationError("Potentially malicious content detected")
        
        # Check for SQL injection only if enabled (for actual DB queries, not natural language)
        if check_sql_injection:
            for pattern in InputSanitizer.SQL_INJECTION_PATTERNS:
                if pattern.search(value):
                    raise ValidationError("Potential SQL injection detected")
        
        # Basic sanitization
        sanitized = value.strip()
        
        # Remove null bytes
        sanitized = sanitized.replace('\x00', '')
        
        return sanitized
    
    @staticmethod
    def validate_salesforce_id(sf_id: str) -> str:
        """Validate Salesforce ID format"""
        if not isinstance(sf_id, str):
            raise ValidationError(f"Salesforce ID must be string, got {type(sf_id)}")
        
        sf_id = sf_id.strip()
        if not InputSanitizer.SALESFORCE_ID_PATTERN.match(sf_id):
            raise ValidationError("Invalid Salesforce ID format")
        
        return sf_id
    
    @staticmethod
    def validate_email(email: str) -> str:
        """Validate email format"""
        if not isinstance(email, str):
            raise ValidationError(f"Email must be string, got {type(email)}")
        
        email = email.strip().lower()
        if not InputSanitizer.EMAIL_PATTERN.match(email):
            raise ValidationError("Invalid email format")
        
        if len(email) > 254:  # RFC 5321 limit
            raise ValidationError("Email too long")
        
        return email
    
    @staticmethod
    def validate_phone(phone: str) -> str:
        """Validate phone number format"""
        if not isinstance(phone, str):
            raise ValidationError(f"Phone must be string, got {type(phone)}")
        
        # Remove common formatting characters
        cleaned = re.sub(r'[\s\-\(\)\.]+', '', phone)
        
        if not InputSanitizer.PHONE_PATTERN.match(cleaned):
            raise ValidationError("Invalid phone number format")
        
        return cleaned
    
    @staticmethod
    def validate_url(url: str) -> str:
        """Validate URL format"""
        if not isinstance(url, str):
            raise ValidationError(f"URL must be string, got {type(url)}")
        
        url = url.strip()
        if not InputSanitizer.URL_PATTERN.match(url):
            raise ValidationError("Invalid URL format")
        
        if len(url) > 2048:  # Common browser limit
            raise ValidationError("URL too long")
        
        return url
    
    @staticmethod
    def validate_uuid(uuid_str: str) -> str:
        """Validate UUID format"""
        if not isinstance(uuid_str, str):
            raise ValidationError(f"UUID must be string, got {type(uuid_str)}")
        
        uuid_str = uuid_str.strip().lower()
        if not InputSanitizer.UUID_PATTERN.match(uuid_str):
            raise ValidationError("Invalid UUID format")
        
        return uuid_str
    
    @staticmethod
    def validate_json(json_str: str, max_size: int = 10000) -> Dict[str, Any]:
        """Validate and parse JSON input"""
        if not isinstance(json_str, str):
            raise ValidationError(f"JSON must be string, got {type(json_str)}")
        
        if len(json_str) > max_size:
            raise ValidationError(f"JSON too large: {len(json_str)} > {max_size}")
        
        try:
            parsed = json.loads(json_str)
            return parsed
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON: {e}")
    
    @staticmethod
    def validate_numeric(value: Union[int, float, str], min_val: Optional[float] = None, max_val: Optional[float] = None) -> Union[int, float]:
        """Validate numeric input"""
        if isinstance(value, str):
            try:
                if '.' in value:
                    value = float(value)
                else:
                    value = int(value)
            except ValueError:
                raise ValidationError("Invalid numeric format")
        
        if not isinstance(value, (int, float)):
            raise ValidationError(f"Expected numeric type, got {type(value)}")
        
        if min_val is not None and value < min_val:
            raise ValidationError(f"Value too small: {value} < {min_val}")
        
        if max_val is not None and value > max_val:
            raise ValidationError(f"Value too large: {value} > {max_val}")
        
        return value
    
    @staticmethod
    def validate_list(value: List[Any], max_items: int = 100, item_validator: Optional[callable] = None) -> List[Any]:
        """Validate list input"""
        if not isinstance(value, list):
            raise ValidationError(f"Expected list, got {type(value)}")
        
        if len(value) > max_items:
            raise ValidationError(f"Too many items: {len(value)} > {max_items}")
        
        if item_validator:
            validated_items = []
            for i, item in enumerate(value):
                try:
                    validated_items.append(item_validator(item))
                except ValidationError as e:
                    raise ValidationError(f"Item {i} validation failed: {e}")
            return validated_items
        
        return value

class AgentInputValidator:
    """Validator for agent-specific inputs"""
    
    @staticmethod
    def validate_salesforce_tool_input(tool_name: str, **kwargs) -> Dict[str, Any]:
        """Validate Salesforce tool inputs"""
        sanitizer = InputSanitizer()
        validated = {}
        
        try:
            if tool_name.startswith("get_"):
                # Get tool validation
                if "lead_id" in kwargs and kwargs["lead_id"]:
                    validated["lead_id"] = sanitizer.validate_salesforce_id(kwargs["lead_id"])
                if "account_id" in kwargs and kwargs["account_id"]:
                    validated["account_id"] = sanitizer.validate_salesforce_id(kwargs["account_id"])
                if "contact_id" in kwargs and kwargs["contact_id"]:
                    validated["contact_id"] = sanitizer.validate_salesforce_id(kwargs["contact_id"])
                if "opportunity_id" in kwargs and kwargs["opportunity_id"]:
                    validated["opportunity_id"] = sanitizer.validate_salesforce_id(kwargs["opportunity_id"])
                if "case_id" in kwargs and kwargs["case_id"]:
                    validated["case_id"] = sanitizer.validate_salesforce_id(kwargs["case_id"])
                if "task_id" in kwargs and kwargs["task_id"]:
                    validated["task_id"] = sanitizer.validate_salesforce_id(kwargs["task_id"])
                
                # Search criteria
                if "email" in kwargs and kwargs["email"]:
                    validated["email"] = sanitizer.validate_email(kwargs["email"])
                if "phone" in kwargs and kwargs["phone"]:
                    validated["phone"] = sanitizer.validate_phone(kwargs["phone"])
                if "name" in kwargs and kwargs["name"]:
                    validated["name"] = sanitizer.sanitize_string(kwargs["name"], max_length=255)
                if "company" in kwargs and kwargs["company"]:
                    validated["company"] = sanitizer.sanitize_string(kwargs["company"], max_length=255)
                if "account_name" in kwargs and kwargs["account_name"]:
                    validated["account_name"] = sanitizer.sanitize_string(kwargs["account_name"], max_length=255)
                if "contact_name" in kwargs and kwargs["contact_name"]:
                    validated["contact_name"] = sanitizer.sanitize_string(kwargs["contact_name"], max_length=255)
                if "subject" in kwargs and kwargs["subject"]:
                    validated["subject"] = sanitizer.sanitize_string(kwargs["subject"], max_length=255)
                if "opportunity_name" in kwargs and kwargs["opportunity_name"]:
                    validated["opportunity_name"] = sanitizer.sanitize_string(kwargs["opportunity_name"], max_length=255)
            
            elif tool_name.startswith("create_"):
                # Create tool validation
                if "email" in kwargs:
                    validated["email"] = sanitizer.validate_email(kwargs["email"])
                if "phone" in kwargs:
                    validated["phone"] = sanitizer.validate_phone(kwargs["phone"])
                if "website" in kwargs and kwargs["website"]:
                    validated["website"] = sanitizer.validate_url(kwargs["website"])
                
                # Required string fields
                string_fields = ["name", "company", "account_name", "subject", "opportunity_name"]
                for field in string_fields:
                    if field in kwargs:
                        validated[field] = sanitizer.sanitize_string(kwargs[field], max_length=255)
                
                # Numeric fields
                if "amount" in kwargs:
                    validated["amount"] = sanitizer.validate_numeric(kwargs["amount"], min_val=0, max_val=999999999.99)
                
                # ID fields for relationships
                id_fields = ["account_id", "contact_id", "lead_id"]
                for field in id_fields:
                    if field in kwargs:
                        validated[field] = sanitizer.validate_salesforce_id(kwargs[field])
                
                # Optional description
                if "description" in kwargs and kwargs["description"]:
                    validated["description"] = sanitizer.sanitize_string(kwargs["description"], max_length=4000)
            
            elif tool_name.startswith("update_"):
                # Update tool validation - ID is required
                id_field = tool_name.replace("update_", "").replace("_tool", "") + "_id"
                if id_field in kwargs:
                    validated[id_field] = sanitizer.validate_salesforce_id(kwargs[id_field])
                
                # Optional fields same as create
                if "email" in kwargs and kwargs["email"]:
                    validated["email"] = sanitizer.validate_email(kwargs["email"])
                if "phone" in kwargs and kwargs["phone"]:
                    validated["phone"] = sanitizer.validate_phone(kwargs["phone"])
                if "website" in kwargs and kwargs["website"]:
                    validated["website"] = sanitizer.validate_url(kwargs["website"])
                if "company" in kwargs and kwargs["company"]:
                    validated["company"] = sanitizer.sanitize_string(kwargs["company"], max_length=255)
                if "amount" in kwargs and kwargs["amount"]:
                    validated["amount"] = sanitizer.validate_numeric(kwargs["amount"], min_val=0, max_val=999999999.99)
                if "stage" in kwargs and kwargs["stage"]:
                    validated["stage"] = sanitizer.sanitize_string(kwargs["stage"], max_length=100)
                if "status" in kwargs and kwargs["status"]:
                    validated["status"] = sanitizer.sanitize_string(kwargs["status"], max_length=100)
                if "description" in kwargs and kwargs["description"]:
                    validated["description"] = sanitizer.sanitize_string(kwargs["description"], max_length=4000)
            
            return validated
            
        except Exception as e:
            logger.error(f"Input validation failed for {tool_name}: {e}")
            raise ValidationError(f"Input validation failed: {e}")
    
    @staticmethod
    def validate_a2a_task(task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate A2A task input"""
        sanitizer = InputSanitizer()
        validated = {}
        
        try:
            # Required fields
            if "id" not in task_data:
                raise ValidationError("Task ID is required")
            validated["id"] = sanitizer.validate_uuid(task_data["id"])
            
            if "instruction" not in task_data:
                raise ValidationError("Task instruction is required")
            # A2A instructions are natural language - only apply basic sanitization, not SQL injection checks
            instruction = task_data["instruction"]
            if not isinstance(instruction, str):
                raise ValidationError(f"Instruction must be string, got {type(instruction)}")
            if len(instruction) > 10000:
                raise ValidationError(f"Instruction too long: {len(instruction)} > 10000")
            validated["instruction"] = instruction.strip().replace('\x00', '')
            
            # Optional fields
            if "context" in task_data:
                if not isinstance(task_data["context"], dict):
                    raise ValidationError("Context must be a dictionary")
                validated["context"] = task_data["context"]  # Context validation could be more specific
            
            if "state_snapshot" in task_data:
                if not isinstance(task_data["state_snapshot"], dict):
                    raise ValidationError("State snapshot must be a dictionary")
                validated["state_snapshot"] = task_data["state_snapshot"]
            
            if "status" in task_data:
                valid_statuses = ["pending", "in_progress", "completed", "failed"]
                status = task_data["status"].lower()
                if status not in valid_statuses:
                    raise ValidationError(f"Invalid status: {status}")
                validated["status"] = status
            
            if "created_at" in task_data:
                validated["created_at"] = task_data["created_at"]  # Could add datetime validation
            
            return validated
            
        except Exception as e:
            logger.error(f"A2A task validation failed: {e}")
            raise ValidationError(f"A2A task validation failed: {e}")
    
    @staticmethod
    def validate_orchestrator_input(user_input: str) -> str:
        """Validate orchestrator user input - natural language only, no SQL injection checks"""
        try:
            if not isinstance(user_input, str):
                raise ValidationError(f"Expected string, got {type(user_input)}")
            
            # Check length
            if len(user_input) > 50000:
                raise ValidationError(f"Input too long: {len(user_input)} > 50000")
            
            # Basic sanitization - remove null bytes
            validated = user_input.strip().replace('\x00', '')
            
            # Check for empty input
            if len(validated) == 0:
                raise ValidationError("Empty input not allowed")
            
            # Check for dangerous HTML/script patterns only - NOT SQL patterns
            # since this is natural language input to the orchestrator
            for pattern in InputSanitizer.DANGEROUS_PATTERNS:
                if pattern.search(validated):
                    raise ValidationError("Potentially malicious content detected")
            
            # Natural language can contain quotes, SQL keywords, etc.
            # SQL injection protection happens downstream in the actual tools
            return validated
            
        except Exception as e:
            # Only log actual errors, not expected validation issues like empty input
            if "empty input" not in str(e).lower():
                logger.error(f"Orchestrator input validation failed: {e}")
            raise ValidationError(f"Orchestrator input validation failed: {e}")

def validate_tool_input(tool_name: str, **kwargs) -> Dict[str, Any]:
    """Main entry point for tool input validation"""
    if "salesforce" in tool_name.lower():
        return AgentInputValidator.validate_salesforce_tool_input(tool_name, **kwargs)
    else:
        # Generic validation for other tools
        sanitizer = InputSanitizer()
        validated = {}
        
        for key, value in kwargs.items():
            if isinstance(value, str):
                validated[key] = sanitizer.sanitize_string(value, max_length=1000)
            elif isinstance(value, (int, float)):
                validated[key] = sanitizer.validate_numeric(value)
            elif isinstance(value, list):
                validated[key] = sanitizer.validate_list(value)
            else:
                validated[key] = value  # Pass through other types
        
        return validated