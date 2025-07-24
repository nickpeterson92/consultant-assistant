"""Shared utility for agents to write tool results and extract entities directly to memory graph."""

from typing import Any, Dict, Optional, Set
from datetime import datetime
from src.memory.core.memory_node import ContextType
from src.memory.core.memory_manager import get_memory_manager
from src.orchestrator.workflow.entity_extractor import extract_entities_intelligently
from src.utils.logging.framework import SmartLogger

logger = SmartLogger("memory_writer")


def write_tool_result_to_memory(
    thread_id: str,
    tool_name: str,
    tool_args: Dict[str, Any],
    tool_result: Any,
    task_id: str,
    agent_name: str,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Write tool execution results directly to the shared memory graph.
    
    Args:
        thread_id: The conversation thread ID
        tool_name: Name of the tool that was executed
        tool_args: Arguments passed to the tool
        tool_result: The result returned by the tool
        task_id: The A2A task ID
        agent_name: Name of the agent executing the tool
        metadata: Additional metadata to store
        
    Returns:
        The node ID of the stored memory
    """
    try:
        # Get the memory manager
        memory_manager = get_memory_manager()
        memory = memory_manager.get_memory(thread_id)
        
        # Prepare content
        content = {
            "tool_name": tool_name,
            "tool_args": tool_args,
            "tool_result": tool_result,
            "task_id": task_id,
            "agent_name": agent_name,
            "timestamp": str(datetime.now())
        }
        
        # Add metadata if provided
        if metadata:
            content.update(metadata)
        
        # Extract tags from tool name and agent name
        tags = {tool_name, agent_name, "tool_execution"}
        
        # Create summary
        summary = f"{agent_name} executed {tool_name}"
        if "operation" in tool_result:
            summary += f" ({tool_result['operation']})"
        
        # Store tool result in memory
        tool_node_id = memory.store(
            content=content,
            context_type=ContextType.TOOL_OUTPUT,
            summary=summary,
            tags=tags,
            confidence=0.9,  # High confidence for direct tool outputs
            metadata={
                "agent": agent_name,
                "tool": tool_name,
                "task_id": task_id
            }
        )
        
        logger.info(
            "tool_result_stored_in_memory",
            thread_id=thread_id,
            node_id=tool_node_id,
            tool_name=tool_name,
            agent_name=agent_name,
            task_id=task_id
        )
        
        # Extract and store entities if tool result contains data
        if isinstance(tool_result, dict) and tool_result.get('success') and tool_result.get('data'):
            extract_and_store_entities(
                memory=memory,
                tool_result=tool_result,
                tool_name=tool_name,
                agent_name=agent_name,
                task_id=task_id,
                relates_to=tool_node_id
            )
        
        return tool_node_id
        
    except Exception as e:
        logger.error(
            "failed_to_store_tool_result",
            thread_id=thread_id,
            tool_name=tool_name,
            agent_name=agent_name,
            error=str(e)
        )
        # Don't raise - we don't want to break tool execution
        return None


def extract_and_store_entities(
    memory,
    tool_result: Dict[str, Any],
    tool_name: str,
    agent_name: str,
    task_id: str,
    relates_to: Optional[str] = None
) -> None:
    """
    Extract entities from tool results and store them in memory.
    
    Args:
        memory: The memory graph instance
        tool_result: The tool execution result containing data
        tool_name: Name of the tool that produced the data
        agent_name: Name of the agent
        task_id: The task ID
        relates_to: Node ID to relate entities to (e.g., the tool result node)
    """
    try:
        # Prepare extraction context
        extraction_context = {
            'agent': agent_name,
            'system': agent_name.replace('-agent', ''),  # Extract system name
            'tool': tool_name
        }
        
        # Extract entities from the data
        data = tool_result.get('data', {})
        entities = extract_entities_intelligently(data, extraction_context)
        
        logger.info(
            "extracting_entities_from_tool_result",
            agent_name=agent_name,
            tool_name=tool_name,
            entities_found=len(entities),
            entity_types=[e.get('type') for e in entities]
        )
        
        # Store each entity in memory
        for entity_info in entities:
            if not entity_info.get('id') and not entity_info.get('name'):
                continue  # Skip entities without identifiers
                
            # Check if entity already exists in memory
            existing_entity_node = None
            entity_id = entity_info.get('id')
            entity_name = entity_info.get('name')
            
            # Fast path: Direct entity ID lookup
            if entity_id:
                entity_system = entity_info.get('system', agent_name.replace('-agent', ''))
                existing_entity_node = memory.node_manager.get_node_by_entity_id(entity_id, entity_system)
                
                logger.info(
                    "entity_lookup_result",
                    entity_id=entity_id,
                    entity_system=entity_system,
                    found_existing=bool(existing_entity_node)
                )
            
            # If not found by ID, search by name and type
            if not existing_entity_node and entity_name:
                # Search for entities with matching name and type
                search_results = memory.retrieve_relevant(
                    query_text=entity_name,
                    context_filter={ContextType.DOMAIN_ENTITY},
                    max_results=10
                )
                
                for node in search_results:
                    if isinstance(node.content, dict):
                        # Check for exact match on name and type
                        if (node.content.get('entity_name') == entity_name and 
                            node.content.get('entity_type') == entity_info.get('type') and
                            node.content.get('entity_system') == entity_info.get('system')):
                            existing_entity_node = node
                            break
            
            # Prepare entity tags
            entity_tags = {agent_name, tool_name}
            if entity_info.get('name'):
                # Add meaningful words from entity name
                name_words = entity_info['name'].lower().split()
                entity_tags.update(word for word in name_words if len(word) > 2)
            if entity_info.get('type'):
                entity_tags.add(entity_info['type'].lower())
            if entity_info.get('system'):
                entity_tags.add(entity_info['system'])
            
            if existing_entity_node:
                # Entity exists - update it
                logger.info(
                    "updating_existing_entity",
                    entity_id=entity_id,
                    entity_name=entity_name,
                    node_id=existing_entity_node.node_id
                )
                
                # Merge the new data with existing data
                existing_content = existing_entity_node.content
                merged_data = existing_content.get('entity_data', {}).copy()
                merged_data.update(entity_info.get('data', {}))
                
                # Merge relationships (avoiding duplicates)
                existing_relationships = set(
                    tuple(rel) if isinstance(rel, list) else rel 
                    for rel in existing_content.get('entity_relationships', [])
                )
                new_relationships = set(
                    tuple(rel) if isinstance(rel, list) else rel 
                    for rel in entity_info.get('relationships', [])
                )
                merged_relationships = list(existing_relationships.union(new_relationships))
                
                # Update the node content
                updated_content = existing_content.copy()
                updated_content.update({
                    "entity_data": merged_data,
                    "entity_relationships": merged_relationships,
                    "last_accessed": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat(),
                    "update_count": existing_content.get('update_count', 0) + 1,
                    "last_extracted_from_tool": tool_name,
                    "last_extracted_by_agent": agent_name
                })
                
                # For SQLite backend, we need to store the updated node
                # Create a new node with the updated content and let SQLite handle the merge
                entity_node_id = memory.store(
                    content=updated_content,
                    context_type=existing_entity_node.context_type,
                    summary=existing_entity_node.summary or f"{entity_info.get('type')}: {entity_name or entity_id}",
                    tags=existing_entity_node.tags.union(entity_tags),
                    confidence=min(1.0, existing_entity_node.base_relevance + 0.05),  # Boost relevance
                    relates_to=[relates_to] if relates_to else None
                )
                
                # Create relationship to new tool result
                if relates_to:
                    memory.add_relationship(relates_to, entity_node_id, "updated")
                    
            else:
                # New entity - create it
                logger.info(
                    "creating_new_entity",
                    entity_id=entity_id,
                    entity_name=entity_name,
                    entity_type=entity_info.get('type')
                )
                
                entity_node_id = memory.store(
                    content={
                        "entity_id": entity_id,
                        "entity_name": entity_name,
                        "entity_type": entity_info.get('type'),
                        "entity_system": entity_info.get('system'),
                        "entity_data": entity_info.get('data', {}),
                        "entity_relationships": entity_info.get('relationships', []),
                        "extraction_confidence": entity_info.get('confidence', 0.8),
                        "extracted_from_tool": tool_name,
                        "extracted_by_agent": agent_name,
                        "task_id": task_id,
                        "first_seen": datetime.now().isoformat(),
                        "last_accessed": datetime.now().isoformat(),
                        "update_count": 0
                    },
                    context_type=ContextType.DOMAIN_ENTITY,
                    summary=f"{entity_info['type']}: {entity_name or entity_id}",
                    tags=entity_tags,
                    confidence=0.6 + (entity_info.get('confidence', 0.8) * 0.3),
                    relates_to=[relates_to] if relates_to else None
                )
                
                # Create relationship to tool result node
                if relates_to:
                    memory.add_relationship(relates_to, entity_node_id, "produces")
                    
                # Check if any existing entities were waiting for this one
                resolve_pending_relationships(memory, entity_id, entity_node_id)
            
            logger.debug(
                "entity_processed",
                entity_id=entity_id,
                entity_name=entity_name,
                entity_type=entity_info.get('type'),
                node_id=entity_node_id,
                agent_name=agent_name,
                was_update=bool(existing_entity_node)
            )
            
            # Process entity relationships to link to other entities
            process_entity_relationships(
                memory=memory,
                entity_node_id=entity_node_id,
                entity_info=entity_info,
                agent_name=agent_name
            )
            
            # Create inferred parent entities (only if not updating existing entity)
            if not existing_entity_node:
                create_inferred_parent_entities(
                    memory=memory,
                    entity_info=entity_info,
                    entity_node_id=entity_node_id,
                    agent_name=agent_name
                )
            
    except Exception as e:
        logger.error(
            "failed_to_extract_entities_from_tool_result",
            agent_name=agent_name,
            tool_name=tool_name,
            error=str(e)
        )
        # Don't raise - entity extraction failure shouldn't break the flow


def create_inferred_parent_entities(memory, entity_info: Dict[str, Any], entity_node_id: str, agent_name: str) -> None:
    """
    Create inferred placeholder nodes for parent entities that we know must exist.
    
    For example, if we have an Opportunity, we know it must have an Account parent.
    We can create a lightweight placeholder Account node from the Account.Name field.
    """
    try:
        entity_type = entity_info.get('type', '').lower()
        entity_data = entity_info.get('data', {})
        entity_system = entity_info.get('system', '')
        
        # Define parent relationships for known systems
        parent_mappings = {
            'salesforce': {
                'opportunity': [
                    ('AccountId', 'Account', 'Account.Name'),
                    ('OwnerId', 'User', None)
                ],
                'contact': [
                    ('AccountId', 'Account', 'Account.Name'),
                    ('ReportsToId', 'User', None)
                ],
                'case': [
                    ('AccountId', 'Account', 'Account.Name'),
                    ('ContactId', 'Contact', 'Contact.Name')
                ],
                'task': [
                    ('WhatId', 'Related', None),  # Polymorphic
                    ('WhoId', 'Name', None)  # Polymorphic
                ]
            },
            'jira': {
                'issue': [
                    ('project.key', 'Project', 'project.name'),
                    ('assignee.accountId', 'User', 'assignee.displayName'),
                    ('reporter.accountId', 'User', 'reporter.displayName'),
                    ('parent.id', 'Issue', 'parent.fields.summary')  # Parent issue
                ]
            },
            'servicenow': {
                'incident': [
                    ('caller_id', 'User', 'caller_id.name'),
                    ('assigned_to', 'User', 'assigned_to.name'),
                    ('company', 'Company', 'company.name')
                ],
                'change_request': [
                    ('requested_by', 'User', 'requested_by.name'),
                    ('assigned_to', 'User', 'assigned_to.name'),
                    ('company', 'Company', 'company.name')
                ],
                'problem': [
                    ('assigned_to', 'User', 'assigned_to.name'),
                    ('company', 'Company', 'company.name')
                ],
                'sc_task': [
                    ('request_item', 'Request Item', 'request_item.number'),
                    ('assigned_to', 'User', 'assigned_to.name')
                ],
                'sc_req_item': [
                    ('request', 'Request', 'request.number'),
                    ('cat_item', 'Catalog Item', 'cat_item.name')
                ]
            }
        }
        
        # Get parent mappings for this entity type
        system_mappings = parent_mappings.get(entity_system, {})
        entity_mappings = system_mappings.get(entity_type, [])
        
        for parent_id_field, parent_type, parent_name_field in entity_mappings:
            # Handle nested fields (e.g., "project.key", "parent.id")
            parent_id = entity_data
            for part in parent_id_field.split('.'):
                if isinstance(parent_id, dict):
                    parent_id = parent_id.get(part)
                else:
                    parent_id = None
                    break
            
            if not parent_id or parent_id in ['', 'null', None]:
                continue
                
            # Get parent name if available
            parent_name = None
            if parent_name_field:
                # Handle nested name fields (e.g., "parent.fields.summary")
                parent_name = entity_data
                for part in parent_name_field.split('.'):
                    if isinstance(parent_name, dict):
                        parent_name = parent_name.get(part)
                    else:
                        parent_name = None
                        break
            
            # Check if this parent entity already exists
            existing_parent = memory.get_node_by_entity_id(parent_id, entity_system)
            
            if not existing_parent and (parent_name or parent_type):
                # Create inferred parent entity
                logger.info(
                    "creating_inferred_parent_entity",
                    parent_id=parent_id,
                    parent_name=parent_name,
                    parent_type=parent_type,
                    inferred_from=entity_info.get('entity_id')
                )
                
                inferred_parent_id = memory.store(
                    content={
                        "entity_id": parent_id,
                        "entity_name": parent_name,
                        "entity_type": parent_type,
                        "entity_system": entity_system,
                        "is_inferred": True,
                        "inferred_from": entity_info.get('entity_id'),
                        "entity_data": {
                            "Id": parent_id,
                            "Name": parent_name
                        } if parent_name else {"Id": parent_id},
                        "entity_relationships": [],
                        "extraction_confidence": 0.6,  # Lower confidence for inferred
                        "extracted_by_agent": agent_name,
                        "first_seen": datetime.now().isoformat(),
                        "last_accessed": datetime.now().isoformat()
                    },
                    context_type=ContextType.DOMAIN_ENTITY,
                    summary=f"{parent_type}: {parent_name or parent_id} (inferred)",
                    tags={entity_system, parent_type.lower(), "inferred", agent_name},
                    confidence=0.5  # Lower confidence for inferred entities
                )
                
                # Create relationships
                memory.add_relationship(entity_node_id, inferred_parent_id, "belongs_to")
                memory.add_relationship(inferred_parent_id, entity_node_id, "has")
                
    except Exception as e:
        logger.error(
            "failed_to_create_inferred_parent",
            error=str(e),
            entity_type=entity_info.get('type')
        )


def resolve_pending_relationships(memory, entity_id: str, entity_node_id: str) -> None:
    """
    When a new entity is created, check if any existing entities
    have relationships pointing to this entity ID.
    
    This handles cases like:
    1. Opportunity created first with AccountId
    2. Account created later
    3. This function links them together
    """
    try:
        # Search all domain entities for ones that might reference this entity
        all_entities = memory.retrieve_relevant(
            query_text="",
            context_filter={ContextType.DOMAIN_ENTITY},
            max_age_hours=24 * 30,  # Look back 30 days
            max_results=1000  # Get many entities
        )
        
        relationships_created = 0
        
        for node in all_entities:
            if not isinstance(node.content, dict):
                continue
                
            # Check if this node has relationships pointing to our new entity
            node_relationships = node.content.get('entity_relationships', [])
            
            for related_id, rel_type in node_relationships:
                if str(related_id) == str(entity_id):
                    # This entity was waiting for our new entity!
                    # Create the relationship
                    memory.add_relationship(node.node_id, entity_node_id, rel_type)
                    
                    # Create reverse relationship
                    reverse_rel_type = {
                        'belongs_to': 'has',
                        'child_of': 'parent_of',
                        'subtask_of': 'has_subtask',
                        'assigned_to': 'assigned_to_entity',
                        'owned_by': 'owns',
                        'created_by': 'created',
                        'reported_by': 'reported',
                        'belongs_to_epic': 'has_issue',
                        'belongs_to_project': 'has_entity'
                    }.get(rel_type, 'relates_to')
                    
                    memory.add_relationship(entity_node_id, node.node_id, reverse_rel_type)
                    
                    relationships_created += 1
                    
                    logger.info(
                        "pending_relationship_resolved",
                        from_entity=node.content.get('entity_id'),
                        to_entity=entity_id,
                        relationship=rel_type,
                        from_node_id=node.node_id,
                        to_node_id=entity_node_id
                    )
        
        if relationships_created > 0:
            logger.info(
                "pending_relationships_resolved",
                entity_id=entity_id,
                relationships_created=relationships_created
            )
            
    except Exception as e:
        logger.error(
            "failed_to_resolve_pending_relationships",
            entity_id=entity_id,
            error=str(e)
        )


def process_entity_relationships(
    memory,
    entity_node_id: str,
    entity_info: Dict[str, Any],
    agent_name: str
) -> None:
    """
    Process and create relationships between entities.
    
    For example, when we get an Opportunity with AccountId,
    this will link it to the existing Account entity.
    """
    try:
        relationships = entity_info.get('relationships', [])
        entity_data = entity_info.get('data', {})
        
        # Also check for relationship fields in the data
        # Common relationship patterns
        relationship_fields = {
            # Salesforce patterns
            'AccountId': ('Account', 'belongs_to'),
            'ContactId': ('Contact', 'relates_to'),
            'OwnerId': ('User', 'owned_by'),
            'CreatedById': ('User', 'created_by'),
            'ParentId': ('Account', 'child_of'),
            'OpportunityId': ('Opportunity', 'relates_to'),
            'CaseId': ('Case', 'relates_to'),
            
            # Jira patterns
            'assignee': ('User', 'assigned_to'),
            'reporter': ('User', 'reported_by'),
            'parent': ('Issue', 'subtask_of'),
            'epic': ('Epic', 'belongs_to_epic'),
            'project': ('Project', 'belongs_to_project'),
            
            # ServiceNow patterns
            'assigned_to': ('User', 'assigned_to'),
            'caller_id': ('User', 'requested_by'),
            'cmdb_ci': ('ConfigurationItem', 'affects_ci'),
            'parent_incident': ('Incident', 'child_of')
        }
        
        # Extract relationships from data fields
        for field_name, (target_type, rel_type) in relationship_fields.items():
            field_value = None
            
            # Check direct fields
            if field_name in entity_data:
                field_value = entity_data[field_name]
            # Check nested fields (e.g., assignee.accountId)
            elif '.' not in field_name:
                # Check if it's a nested object
                for key, value in entity_data.items():
                    if key.lower() == field_name.lower() and isinstance(value, dict):
                        # Extract ID from nested object
                        field_value = value.get('id') or value.get('accountId') or value.get('value')
                        break
            
            if field_value:
                # Add to relationships list
                relationships.append((str(field_value), rel_type))
        
        # Process all relationships
        for related_id, rel_type in relationships:
            if not related_id or related_id == entity_info.get('id'):
                continue  # Skip self-references
                
            # Look for the related entity in memory
            related_node = memory.node_manager.get_node_by_entity_id(related_id)
            
            if related_node:
                # Entity exists - create the relationship
                memory.add_relationship(entity_node_id, related_node.node_id, rel_type)
                
                # Also create reverse relationship for bidirectional navigation
                reverse_rel_type = {
                    'belongs_to': 'has',
                    'child_of': 'parent_of',
                    'subtask_of': 'has_subtask',
                    'assigned_to': 'assigned_to_entity',
                    'owned_by': 'owns',
                    'created_by': 'created',
                    'reported_by': 'reported',
                    'belongs_to_epic': 'has_issue',
                    'belongs_to_project': 'has_entity'
                }.get(rel_type, 'relates_to')
                
                memory.add_relationship(related_node.node_id, entity_node_id, reverse_rel_type)
                
                logger.info(
                    "entity_relationship_created",
                    from_entity=entity_info.get('id'),
                    to_entity=related_id,
                    relationship=rel_type,
                    from_node_id=entity_node_id,
                    to_node_id=related_node.node_id
                )
            else:
                # Related entity doesn't exist yet - it might be created later
                logger.debug(
                    "entity_relationship_pending",
                    from_entity=entity_info.get('id'),
                    to_entity=related_id,
                    relationship=rel_type,
                    note="Related entity not found yet"
                )
                
    except Exception as e:
        logger.error(
            "failed_to_process_entity_relationships",
            entity_id=entity_info.get('id'),
            error=str(e)
        )