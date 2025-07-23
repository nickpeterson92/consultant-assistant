"""Intelligent summary generation from memory content."""

from typing import Any, Optional
import json

from .memory_node import ContextType


def auto_generate_summary(content: Any, context_type: ContextType, 
                         tags: Optional[set] = None) -> str:
    """Generate intelligent, accurate summary from actual content."""
    
    if content is None:
        return "Empty content"
    
    try:
        return _generate_by_context_type(content, context_type, tags or set())
    except Exception as e:
        # Fallback to safe string representation
        return _safe_content_preview(content)


def _generate_by_context_type(content: Any, context_type: ContextType, tags: set) -> str:
    """Generate summary based on context type."""
    
    if context_type == ContextType.DOMAIN_ENTITY:
        return _generate_entity_summary(content, tags)
    
    elif context_type == ContextType.SEARCH_RESULT:
        return _generate_search_summary(content, tags)
    
    elif context_type == ContextType.USER_SELECTION:
        return _generate_selection_summary(content, tags)
    
    elif context_type == ContextType.COMPLETED_ACTION:
        return _generate_action_summary(content, tags)
    
    elif context_type == ContextType.TOOL_OUTPUT:
        return _generate_tool_summary(content, tags)
    
    elif context_type == ContextType.CONVERSATION_FACT:
        return _generate_fact_summary(content, tags)
    
    elif context_type == ContextType.TEMPORARY_STATE:
        return _generate_temp_summary(content, tags)
    
    else:
        return _safe_content_preview(content)


def _generate_entity_summary(content: Any, tags: set) -> str:
    """Generate summary for business entities (accounts, contacts, opportunities, etc.)"""
    
    if not isinstance(content, dict):
        return _safe_content_preview(content)
    
    # Detect entity type from content structure
    entity_type = _detect_entity_type(content, tags)
    
    # Extract name/identifier
    name = _extract_name(content)
    
    # Build base summary
    summary = f"{name} {entity_type}" if name else f"{entity_type.title()} entity"
    
    # Add specific details based on entity type
    if entity_type == "account":
        summary = _enhance_account_summary(summary, content)
    elif entity_type == "opportunity":
        summary = _enhance_opportunity_summary(summary, content)
    elif entity_type == "contact":
        summary = _enhance_contact_summary(summary, content)
    elif entity_type == "case":
        summary = _enhance_case_summary(summary, content)
    else:
        # Generic enhancement
        summary = _enhance_generic_summary(summary, content)
    
    return summary


def _generate_search_summary(content: Any, tags: set) -> str:
    """Generate summary for search results."""
    
    if isinstance(content, list):
        count = len(content)
        
        if count == 0:
            return "No search results found"
        
        # Try to determine what was searched for
        entity_type = _infer_search_type(content, tags)
        
        if count == 1:
            return f"Found 1 {entity_type}"
        else:
            return f"Found {count} {entity_type}s"
    
    elif isinstance(content, dict):
        if "records" in content:
            # Salesforce-style result
            records = content["records"]
            count = len(records) if isinstance(records, list) else 1
            entity_type = _infer_search_type(records, tags)
            return f"Found {count} {entity_type}{'s' if count != 1 else ''}"
    
    return f"Search results: {_safe_content_preview(content)}"


def _generate_selection_summary(content: Any, tags: set) -> str:
    """Generate summary for user selections."""
    
    if isinstance(content, dict):
        if "selected" in content:
            selected = content["selected"]
            if isinstance(selected, dict) and "name" in selected:
                name = selected["name"]
                entity_type = _detect_entity_type(selected, tags)
                return f"User selected {name} ({entity_type})"
            else:
                return f"User selected: {selected}"
        
        elif "selected_item" in content:
            item = content["selected_item"]
            if isinstance(item, dict) and "name" in item:
                return f"User selected {item['name']}"
    
    return f"User selection: {_safe_content_preview(content)}"


def _generate_action_summary(content: Any, tags: set) -> str:
    """Generate summary for completed actions."""
    
    if isinstance(content, dict):
        # Look for action indicators
        if "task" in content and "response" in content:
            task = content["task"]
            response_preview = str(content["response"])[:50]
            return f"Completed: {task} → {response_preview}{'...' if len(str(content['response'])) > 50 else ''}"
        
        elif "action" in content:
            action = content["action"]
            if "opportunity_id" in content:
                return f"Completed {action} on opportunity {content['opportunity_id']}"
            elif "account_id" in content:
                return f"Completed {action} on account {content['account_id']}"
            else:
                return f"Completed action: {action}"
        
        elif "updated" in content or "created" in content or "deleted" in content:
            # CRUD operation
            operation = "updated" if "updated" in content else "created" if "created" in content else "deleted"
            entity = content.get(operation, "entity")
            return f"Successfully {operation} {entity}"
    
    return f"Completed action: {_safe_content_preview(content)}"


def _generate_tool_summary(content: Any, tags: set) -> str:
    """Generate summary for tool outputs."""
    
    if isinstance(content, dict):
        if "tool_name" in content:
            tool_name = content["tool_name"]
            if "result" in content:
                return f"{tool_name} result: {_safe_content_preview(content['result'])}"
            else:
                return f"{tool_name} execution"
    
    return f"Tool output: {_safe_content_preview(content)}"


def _generate_fact_summary(content: Any, tags: set) -> str:
    """Generate summary for conversation facts."""
    
    if isinstance(content, str):
        return f"Fact: {content}"
    
    elif isinstance(content, dict):
        if "fact" in content:
            return f"Fact: {content['fact']}"
        elif "context" in content:
            return f"Context: {content['context']}"
    
    return f"Conversation fact: {_safe_content_preview(content)}"


def _generate_temp_summary(content: Any, tags: set) -> str:
    """Generate summary for temporary state."""
    
    if isinstance(content, dict):
        if "state" in content:
            return f"Temp state: {content['state']}"
        elif "status" in content:
            return f"Status: {content['status']}"
    
    return f"Temporary state: {_safe_content_preview(content)}"


# Helper functions for entity type detection and enhancement

def _detect_entity_type(content: dict, tags: set) -> str:
    """Detect what type of business entity this is."""
    
    # Check tags first
    if "account" in tags:
        return "account"
    elif "opportunity" in tags:
        return "opportunity" 
    elif "contact" in tags:
        return "contact"
    elif "case" in tags:
        return "case"
    elif "lead" in tags:
        return "lead"
    elif "task" in tags:
        return "task"
    
    # Check content structure
    if "industry" in content or "website" in content:
        return "account"
    elif "amount" in content and "stage" in content:
        return "opportunity"
    elif "email" in content and "phone" in content:
        return "contact" 
    elif "subject" in content and "status" in content:
        return "case"
    elif "company" in content and "amount" not in content:
        return "lead"
    
    return "entity"


def _extract_name(content: dict) -> Optional[str]:
    """Extract the primary name/identifier from content."""
    
    # Try common name fields
    for field in ["name", "Name", "title", "subject", "Subject"]:
        if field in content and content[field]:
            return str(content[field])
    
    # Try ID fields as fallback
    for field in ["id", "Id", "ID"]:
        if field in content and content[field]:
            return f"ID:{content[field]}"
    
    return None


def _enhance_account_summary(summary: str, content: dict) -> str:
    """Add account-specific details to summary."""
    
    enhancements = []
    
    if "industry" in content:
        enhancements.append(f"({content['industry']})")
    
    if "opportunities" in content and isinstance(content["opportunities"], list):
        opp_count = len(content["opportunities"])
        if opp_count > 0:
            enhancements.append(f"with {opp_count} opportunity{'s' if opp_count != 1 else ''}")
    
    if "revenue" in content:
        revenue = content["revenue"]
        enhancements.append(f"${revenue:,} revenue")
    
    if enhancements:
        summary += " " + " ".join(enhancements)
    
    return summary


def _enhance_opportunity_summary(summary: str, content: dict) -> str:
    """Add opportunity-specific details to summary."""
    
    enhancements = []
    
    if "amount" in content:
        amount = content["amount"]
        enhancements.append(f"${amount:,}")
    
    if "stage" in content:
        stage = content["stage"]
        enhancements.append(f"({stage})")
    
    if "account" in content:
        account = content["account"]
        if isinstance(account, str):
            enhancements.append(f"for {account}")
        elif isinstance(account, dict) and "name" in account:
            enhancements.append(f"for {account['name']}")
    
    if enhancements:
        summary += " " + " ".join(enhancements)
    
    return summary


def _enhance_contact_summary(summary: str, content: dict) -> str:
    """Add contact-specific details to summary."""
    
    enhancements = []
    
    if "title" in content:
        enhancements.append(f"({content['title']})")
    
    if "account" in content:
        account = content["account"]
        if isinstance(account, str):
            enhancements.append(f"at {account}")
        elif isinstance(account, dict) and "name" in account:
            enhancements.append(f"at {account['name']}")
    
    if enhancements:
        summary += " " + " ".join(enhancements)
    
    return summary


def _enhance_case_summary(summary: str, content: dict) -> str:
    """Add case-specific details to summary."""
    
    enhancements = []
    
    if "status" in content:
        enhancements.append(f"({content['status']})")
    
    if "priority" in content:
        enhancements.append(f"{content['priority']} priority")
    
    if enhancements:
        summary += " " + " ".join(enhancements)
    
    return summary


def _enhance_generic_summary(summary: str, content: dict) -> str:
    """Add generic enhancements from common fields."""
    
    enhancements = []
    
    # Look for common descriptive fields
    for field in ["status", "type", "category", "priority"]:
        if field in content and content[field]:
            enhancements.append(f"({content[field]})")
            break  # Only add one
    
    if enhancements:
        summary += " " + " ".join(enhancements)
    
    return summary


def _infer_search_type(content: Any, tags: set) -> str:
    """Infer what type of entities were searched for."""
    
    # Check tags
    entity_tags = {"account", "opportunity", "contact", "case", "lead", "task"}
    found_tags = tags.intersection(entity_tags)
    if found_tags:
        return list(found_tags)[0]
    
    # Check content structure
    if isinstance(content, list) and len(content) > 0:
        first_item = content[0]
        if isinstance(first_item, dict):
            entity_type = _detect_entity_type(first_item, set())
            if entity_type != "entity":
                return entity_type
    
    return "record"


def _safe_content_preview(content: Any, max_length: int = 100) -> str:
    """Create a safe string preview of content."""
    
    try:
        if isinstance(content, (dict, list)):
            content_str = json.dumps(content, separators=(',', ':'))
        else:
            content_str = str(content)
        
        if len(content_str) <= max_length:
            return content_str
        else:
            return content_str[:max_length] + "..."
    
    except Exception:
        return f"<{type(content).__name__} object>"