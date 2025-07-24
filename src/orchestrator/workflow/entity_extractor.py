"""Intelligent entity extraction for memory graph integration.

This module provides robust entity extraction that:
1. Uses pattern matching for common ID formats
2. Employs heuristics to identify entity types
3. Handles nested and wrapped data structures
4. Extracts relationships between entities
5. Works across multiple systems (Salesforce, Jira, ServiceNow, etc.)
"""

import re
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum

from src.utils.logging.framework import SmartLogger

logger = SmartLogger("orchestrator")


class EntityType(Enum):
    """Known entity types across systems."""
    # Salesforce
    ACCOUNT = "Account"
    CONTACT = "Contact"
    OPPORTUNITY = "Opportunity"
    LEAD = "Lead"
    CASE = "Case"
    TASK = "Task"
    USER = "User"
    
    # Jira
    ISSUE = "Issue"
    PROJECT = "Project"
    EPIC = "Epic"
    SPRINT = "Sprint"
    BOARD = "Board"
    
    # ServiceNow
    INCIDENT = "Incident"
    CHANGE_REQUEST = "Change"
    PROBLEM = "Problem"
    SERVICE_REQUEST = "Request"
    
    # Generic
    UNKNOWN = "Entity"


@dataclass
class ExtractedEntity:
    """Represents an extracted entity with all its metadata."""
    entity_id: str
    entity_name: Optional[str]
    entity_type: EntityType
    system: str  # salesforce, jira, servicenow, etc.
    raw_data: Dict[str, Any]
    relationships: List[Tuple[str, str]]  # [(related_id, relationship_type)]
    confidence: float  # 0.0 to 1.0


class IntelligentEntityExtractor:
    """Extracts entities from any data structure with high accuracy."""
    
    # ID patterns for different systems
    ID_PATTERNS = {
        'salesforce': {
            'account': re.compile(r'\b001[a-zA-Z0-9]{12,15}\b'),
            'contact': re.compile(r'\b003[a-zA-Z0-9]{12,15}\b'),
            'opportunity': re.compile(r'\b006[a-zA-Z0-9]{12,15}\b'),
            'lead': re.compile(r'\b00Q[a-zA-Z0-9]{12,15}\b'),
            'case': re.compile(r'\b500[a-zA-Z0-9]{12,15}\b'),
            'task': re.compile(r'\b00T[a-zA-Z0-9]{12,15}\b'),
            'user': re.compile(r'\b005[a-zA-Z0-9]{12,15}\b'),
        },
        'jira': {
            'issue': re.compile(r'\b[A-Z]{2,10}-\d{1,10}\b'),
            'project': re.compile(r'\b[A-Z]{2,10}\b'),  # When in project context
        },
        'servicenow': {
            'incident': re.compile(r'\bINC\d{7,10}\b'),
            'change': re.compile(r'\bCHG\d{7,10}\b'),
            'problem': re.compile(r'\bPRB\d{7,10}\b'),
            'request': re.compile(r'\b(REQ|RITM)\d{7,10}\b'),
            'sys_id': re.compile(r'\b[a-f0-9]{32}\b'),
        }
    }
    
    # Common field names that indicate entities (case-insensitive)
    ENTITY_INDICATORS = {
        'id_fields': {'id', 'ids', '_id', 'uuid', 'key', 'sys_id', 'number', 'identifier'},
        'name_fields': {'name', 'title', 'subject', 'summary', 'display_name', 'label', 'short_description'},
        'type_fields': {'type', '_type', 'object_type', 'record_type', 'entity_type', 'attributes'},
        'relationship_fields': {'account_id', 'contact_id', 'parent_id', 'related_to', 'assigned_to', 
                               'owner_id', 'created_by', 'modified_by', 'reporter', 'assignee'}
    }
    
    @classmethod
    def extract_entities(cls, data: Any, context: Optional[Dict[str, Any]] = None) -> List[ExtractedEntity]:
        """Extract all entities from any data structure.
        
        Args:
            data: The data to extract entities from (dict, list, or primitive)
            context: Optional context about the data source
            
        Returns:
            List of extracted entities with metadata
        """
        entities = []
        processed_ids = set()  # Avoid duplicates
        
        # Handle different data types
        if isinstance(data, dict):
            entities.extend(cls._extract_from_dict(data, context, processed_ids))
        elif isinstance(data, list):
            for item in data:
                entities.extend(cls.extract_entities(item, context))
        elif isinstance(data, str):
            # Try to extract IDs from strings
            entities.extend(cls._extract_from_string(data, context, processed_ids))
            
        return entities
    
    @classmethod
    def _extract_from_dict(cls, data: Dict[str, Any], context: Optional[Dict[str, Any]], 
                          processed_ids: Set[str]) -> List[ExtractedEntity]:
        """Extract entities from a dictionary."""
        entities = []
        
        # First, check if this dict itself is an entity
        entity = cls._try_extract_entity(data, context, processed_ids)
        if entity:
            entities.append(entity)
            
        # Then recursively check nested structures
        for key, value in data.items():
            lower_key = key.lower()
            
            # Check for wrapped data patterns
            if lower_key in ('data', 'records', 'results', 'items', 'entities', 'objects'):
                entities.extend(cls.extract_entities(value, context))
            
            # Check for relationship fields
            elif any(rel in lower_key for rel in cls.ENTITY_INDICATORS['relationship_fields']):
                # This might be a related entity ID
                if isinstance(value, str) and cls._looks_like_id(value):
                    rel_entity = cls._create_minimal_entity(value, context)
                    if rel_entity and rel_entity.entity_id not in processed_ids:
                        entities.append(rel_entity)
                        processed_ids.add(rel_entity.entity_id)
            
            # Recurse into nested structures
            elif isinstance(value, (dict, list)):
                entities.extend(cls.extract_entities(value, context))
                
        return entities
    
    @classmethod
    def _try_extract_entity(cls, data: Dict[str, Any], context: Optional[Dict[str, Any]], 
                           processed_ids: Set[str]) -> Optional[ExtractedEntity]:
        """Try to extract an entity from a dictionary."""
        # Find ID field
        entity_id = None
        id_confidence = 0.0
        
        for field in cls.ENTITY_INDICATORS['id_fields']:
            if field in data or field.upper() in data or field.title() in data:
                value = data.get(field) or data.get(field.upper()) or data.get(field.title())
                if value and isinstance(value, str):
                    entity_id = value
                    id_confidence = 0.9 if cls._looks_like_id(value) else 0.5
                    break
        
        # If no ID but has name-like fields, might still be an entity
        entity_name = None
        
        # Try direct field access first - check exact case variations
        # Check common exact field names first
        for exact_field in ['Name', 'name', 'NAME']:
            if exact_field in data and data[exact_field]:
                entity_name = str(data[exact_field])
                break
        
        # If not found, try other name fields
        if not entity_name:
            for field in cls.ENTITY_INDICATORS['name_fields']:
                if field in data or field.upper() in data or field.title() in data:
                    value = data.get(field) or data.get(field.upper()) or data.get(field.title())
                    if value and isinstance(value, str):
                        entity_name = value
                        break
        
        # Debug logging for entity extraction
        if entity_id and entity_id.startswith('001'):  # Account ID
            logger.debug("extracting_salesforce_account",
                        entity_id=entity_id,
                        found_name=bool(entity_name),
                        entity_name=entity_name,
                        data_keys=list(data.keys()),
                        has_Name='Name' in data,
                        Name_value=data.get('Name'))
        
        # Also try common Salesforce patterns
        if not entity_name:
            # Check for AccountName, OpportunityName etc.
            for prefix in ['Account', 'Opportunity', 'Contact', 'Lead', 'Case']:
                name_field = f"{prefix}Name"
                if name_field in data and data[name_field]:
                    entity_name = str(data[name_field])
                    break
        
        # Need at least ID or name
        if not entity_id and not entity_name:
            return None
            
        # Already processed?
        if entity_id and entity_id in processed_ids:
            return None
            
        # Determine entity type
        entity_type, type_confidence = cls._determine_entity_type(data, entity_id, context)
        
        # Special handling for Salesforce objects that might use different name fields
        if not entity_name and entity_type == EntityType.CASE:
            # Cases use Subject instead of Name
            if 'Subject' in data and data['Subject']:
                entity_name = str(data['Subject'])
        elif not entity_name and entity_type == EntityType.TASK:
            # Tasks also use Subject
            if 'Subject' in data and data['Subject']:
                entity_name = str(data['Subject'])
        
        # Determine system
        system = cls._determine_system(entity_id, data, context)
        
        # Extract relationships
        relationships = cls._extract_relationships(data)
        
        # Calculate overall confidence
        confidence = max(id_confidence, type_confidence)
        if entity_id and entity_name:
            confidence = min(1.0, confidence + 0.2)
            
        # If we still don't have a name but have raw data, try deeper extraction
        if not entity_name and isinstance(data, dict):
            # Try nested paths common in API responses
            nested_paths = [
                ['fields', 'Name'],
                ['attributes', 'Name'],
                ['properties', 'name'],
                ['data', 'Name'],
                ['record', 'Name']
            ]
            
            for path in nested_paths:
                current = data
                for key in path:
                    if isinstance(current, dict) and key in current:
                        current = current[key]
                    else:
                        break
                else:
                    # Made it through the whole path
                    if isinstance(current, str) and current:
                        entity_name = current
                        break
        
        # Create entity
        entity = ExtractedEntity(
            entity_id=entity_id or f"unnamed_{hash(str(data))}",
            entity_name=entity_name,
            entity_type=entity_type,
            system=system,
            raw_data=data,
            relationships=relationships,
            confidence=confidence
        )
        
        if entity_id:
            processed_ids.add(entity_id)
            
        logger.debug("extracted_entity",
                    entity_id=entity.entity_id,
                    entity_name=entity.entity_name,
                    entity_type=entity.entity_type.value,
                    system=entity.system,
                    confidence=entity.confidence,
                    relationships_count=len(entity.relationships))
        
        return entity
    
    @classmethod
    def _looks_like_id(cls, value: str) -> bool:
        """Check if a string looks like an ID."""
        if not value or len(value) < 3:
            return False
            
        # Check against known patterns
        for system_patterns in cls.ID_PATTERNS.values():
            for pattern in system_patterns.values():
                if pattern.match(value):
                    return True
                    
        # Generic ID heuristics
        # Has mix of letters/numbers
        has_letter = any(c.isalpha() for c in value)
        has_digit = any(c.isdigit() for c in value)
        
        # Reasonable length for ID
        good_length = 5 <= len(value) <= 50
        
        # Not a common word
        not_common_word = value.lower() not in {'true', 'false', 'null', 'none', 'yes', 'no'}
        
        # Has ID-like characteristics
        has_underscore_or_dash = '_' in value or '-' in value
        
        return good_length and not_common_word and (
            (has_letter and has_digit) or 
            has_underscore_or_dash or
            len(value) == 32  # Common for UUIDs
        )
    
    @classmethod
    def _determine_entity_type(cls, data: Dict[str, Any], entity_id: Optional[str], 
                              context: Optional[Dict[str, Any]]) -> Tuple[EntityType, float]:
        """Determine the type of entity with confidence score."""
        # Check explicit type fields
        for field in cls.ENTITY_INDICATORS['type_fields']:
            if field in data:
                type_value = str(data[field]).lower()
                
                # Map to known types
                type_mapping = {
                    'account': EntityType.ACCOUNT,
                    'contact': EntityType.CONTACT,
                    'opportunity': EntityType.OPPORTUNITY,
                    'lead': EntityType.LEAD,
                    'case': EntityType.CASE,
                    'task': EntityType.TASK,
                    'issue': EntityType.ISSUE,
                    'bug': EntityType.ISSUE,
                    'story': EntityType.ISSUE,
                    'epic': EntityType.EPIC,
                    'project': EntityType.PROJECT,
                    'incident': EntityType.INCIDENT,
                    'change': EntityType.CHANGE_REQUEST,
                    'problem': EntityType.PROBLEM,
                    'request': EntityType.SERVICE_REQUEST,
                }
                
                for key, entity_type in type_mapping.items():
                    if key in type_value:
                        return entity_type, 0.9
        
        # Check ID patterns
        if entity_id:
            # Salesforce patterns
            if entity_id.startswith('001'):
                return EntityType.ACCOUNT, 0.95
            elif entity_id.startswith('003'):
                return EntityType.CONTACT, 0.95
            elif entity_id.startswith('006'):
                return EntityType.OPPORTUNITY, 0.95
            elif entity_id.startswith('00Q'):
                return EntityType.LEAD, 0.95
            elif entity_id.startswith('500'):
                return EntityType.CASE, 0.95
            elif entity_id.startswith('00T'):
                return EntityType.TASK, 0.95
            elif entity_id.startswith('005'):
                return EntityType.USER, 0.95
            
            # Jira patterns
            elif re.match(r'^[A-Z]{2,10}-\d+$', entity_id):
                return EntityType.ISSUE, 0.9
            
            # ServiceNow patterns
            elif entity_id.startswith('INC'):
                return EntityType.INCIDENT, 0.95
            elif entity_id.startswith('CHG'):
                return EntityType.CHANGE_REQUEST, 0.95
            elif entity_id.startswith('PRB'):
                return EntityType.PROBLEM, 0.95
            elif entity_id.startswith(('REQ', 'RITM')):
                return EntityType.SERVICE_REQUEST, 0.95
        
        # Check field names for hints
        field_hints = {
            'account': EntityType.ACCOUNT,
            'contact': EntityType.CONTACT,
            'opportunity': EntityType.OPPORTUNITY,
            'amount': EntityType.OPPORTUNITY,  # Opportunities have amounts
            'stage': EntityType.OPPORTUNITY,   # Opportunities have stages
            'issue': EntityType.ISSUE,
            'incident': EntityType.INCIDENT,
            'assignee': EntityType.ISSUE,      # Common in issue tracking
        }
        
        for hint, entity_type in field_hints.items():
            if any(hint in key.lower() for key in data.keys()):
                return entity_type, 0.6
                
        return EntityType.UNKNOWN, 0.3
    
    @classmethod
    def _determine_system(cls, entity_id: Optional[str], data: Dict[str, Any], 
                         context: Optional[Dict[str, Any]]) -> str:
        """Determine which system this entity belongs to."""
        # Check context first
        if context and 'system' in context:
            return context['system']
            
        # Check ID patterns
        if entity_id:
            # Salesforce
            if re.match(r'^[0-9]{3}[a-zA-Z0-9]{12,15}$', entity_id):
                return 'salesforce'
            # Jira
            elif re.match(r'^[A-Z]{2,10}-\d+$', entity_id):
                return 'jira'
            # ServiceNow
            elif re.match(r'^(INC|CHG|PRB|REQ|RITM)\d{7,10}$', entity_id):
                return 'servicenow'
        
        # Check for system-specific fields
        if any(key in data for key in ['AccountId', 'OpportunityId', 'ContactId']):
            return 'salesforce'
        elif any(key in data for key in ['issueType', 'projectKey', 'sprint']):
            return 'jira'
        elif any(key in data for key in ['incident_state', 'change_type', 'problem_state']):
            return 'servicenow'
            
        return 'unknown'
    
    @classmethod
    def _extract_relationships(cls, data: Dict[str, Any]) -> List[Tuple[str, str]]:
        """Extract relationships to other entities."""
        relationships = []
        
        relationship_mapping = {
            'account_id': 'belongs_to',
            'accountid': 'belongs_to',
            'contact_id': 'related_to',
            'contactid': 'related_to',
            'parent_id': 'child_of',
            'parentid': 'child_of',
            'opportunity_id': 'related_to',
            'opportunityid': 'related_to',
            'owner_id': 'owned_by',
            'ownerid': 'owned_by',
            'created_by': 'created_by',
            'createdbyid': 'created_by',
            'assigned_to': 'assigned_to',
            'assignee': 'assigned_to',
            'reporter': 'reported_by',
        }
        
        for key, value in data.items():
            lower_key = key.lower()
            if lower_key in relationship_mapping and isinstance(value, str) and cls._looks_like_id(value):
                relationships.append((value, relationship_mapping[lower_key]))
                
        return relationships
    
    @classmethod
    def _extract_from_string(cls, text: str, context: Optional[Dict[str, Any]], 
                           processed_ids: Set[str]) -> List[ExtractedEntity]:
        """Extract entity IDs from plain text."""
        entities = []
        
        # Check all ID patterns
        for system, patterns in cls.ID_PATTERNS.items():
            for entity_type, pattern in patterns.items():
                for match in pattern.finditer(text):
                    entity_id = match.group()
                    if entity_id not in processed_ids:
                        entity = cls._create_minimal_entity(entity_id, context, system)
                        if entity:
                            entities.append(entity)
                            processed_ids.add(entity_id)
                            
        return entities
    
    
    @classmethod
    def _create_minimal_entity(cls, entity_id: str, context: Optional[Dict[str, Any]], 
                              system: Optional[str] = None) -> Optional[ExtractedEntity]:
        """Create a minimal entity from just an ID."""
        entity_type, confidence = cls._determine_entity_type({'id': entity_id}, entity_id, context)
        
        if not system:
            system = cls._determine_system(entity_id, {}, context)
            
        return ExtractedEntity(
            entity_id=entity_id,
            entity_name=None,
            entity_type=entity_type,
            system=system,
            raw_data={'id': entity_id},
            relationships=[],
            confidence=confidence * 0.7  # Lower confidence for minimal extraction
        )


def extract_entities_intelligently(data: Any, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Convenience function to extract entities and return as dicts.
    
    Args:
        data: Data to extract from
        context: Optional context about data source
        
    Returns:
        List of entity dictionaries suitable for memory storage
    """
    entities = IntelligentEntityExtractor.extract_entities(data, context)
    
    return [
        {
            'id': entity.entity_id,
            'name': entity.entity_name,
            'type': entity.entity_type.value,
            'system': entity.system,
            'data': entity.raw_data,
            'relationships': entity.relationships,
            'confidence': entity.confidence
        }
        for entity in entities
        if entity.confidence >= 0.5  # Only return reasonably confident extractions
    ]