"""Message processing helper utilities."""

from typing import List, Dict, Any, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage


def trim_messages_for_context(
    messages: List[BaseMessage],
    max_tokens: int = 100000,
    keep_system: bool = True,
    keep_first_n: int = 1,
    keep_last_n: int = 10
) -> List[BaseMessage]:
    """Trim messages to fit within token limits while preserving important context.
    
    Args:
        messages: List of messages to trim
        max_tokens: Maximum token limit
        keep_system: Whether to preserve system messages
        keep_first_n: Number of initial messages to keep
        keep_last_n: Number of recent messages to keep
        
    Returns:
        Trimmed list of messages
    """
    if not messages:
        return []
    
    # Separate messages into categories
    system_messages = []
    first_messages = []
    last_messages = []
    middle_messages = []
    
    for i, msg in enumerate(messages):
        if keep_system and msg.__class__.__name__ == "SystemMessage":
            system_messages.append(msg)
        elif i < keep_first_n:
            first_messages.append(msg)
        elif i >= len(messages) - keep_last_n:
            last_messages.append(msg)
        else:
            middle_messages.append(msg)
    
    # Combine in priority order
    result = system_messages + first_messages + last_messages
    
    # Add middle messages if there's room
    current_tokens = estimate_message_tokens(result)
    
    for msg in reversed(middle_messages):  # Add from most recent
        msg_tokens = estimate_message_tokens([msg])
        if current_tokens + msg_tokens <= max_tokens:
            result.insert(len(system_messages) + len(first_messages), msg)
            current_tokens += msg_tokens
        else:
            break
    
    return result


def estimate_message_tokens(messages: List[BaseMessage]) -> int:
    """Estimate token count for messages.
    
    Simple estimation: ~4 characters per token.
    
    Args:
        messages: List of messages
        
    Returns:
        Estimated token count
    """
    total_chars = 0
    for msg in messages:
        total_chars += len(str(msg.content))
        # Add extra for metadata
        total_chars += 50  # Role, additional kwargs, etc.
        
        # Add extra for tool calls
        if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls'):
            for tool_call in (msg.tool_calls or []):
                total_chars += len(str(tool_call))
    
    return total_chars // 4


def extract_user_intent(messages: List[BaseMessage]) -> Optional[str]:
    """Extract the primary user intent from conversation.
    
    Args:
        messages: Conversation messages
        
    Returns:
        Extracted intent or None
    """
    # Look for the most recent human message
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            content = msg.content
            return content if isinstance(content, str) else None
    return None


def count_tool_calls(messages: List[BaseMessage]) -> Dict[str, int]:
    """Count tool calls by tool name in the conversation.
    
    Args:
        messages: Conversation messages
        
    Returns:
        Dictionary of tool name to call count
    """
    tool_counts: Dict[str, int] = {}
    
    for msg in messages:
        if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls'):
            for tool_call in (msg.tool_calls or []):
                tool_name = tool_call.get('name', 'unknown')
                tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
    
    return tool_counts


def extract_entities_from_messages(messages: List[BaseMessage]) -> Dict[str, List[str]]:
    """Extract entities mentioned in messages.
    
    Simple extraction based on patterns - in production, use NLP.
    
    Args:
        messages: Conversation messages
        
    Returns:
        Dictionary of entity type to list of entities
    """
    entities: Dict[str, List[str]] = {
        'accounts': [],
        'contacts': [],
        'emails': [],
        'ids': []
    }
    
    import re
    
    for msg in messages:
        content = str(msg.content)
        
        # Extract email addresses
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content)
        entities['emails'].extend(emails)
        
        # Extract Salesforce IDs (18 chars starting with 00)
        sf_ids = re.findall(r'\b00[A-Za-z0-9]{16}\b', content)
        entities['ids'].extend(sf_ids)
        
        # Extract potential account names (capitalized phrases)
        # This is very basic - production would use NER
        potential_accounts = re.findall(r'\b[A-Z][a-z]+ (?:Corp|Inc|LLC|Company|Corporation)\b', content)
        entities['accounts'].extend(potential_accounts)
    
    # Deduplicate
    for key in entities:
        entities[key] = list(set(entities[key]))
    
    return entities


def format_message_for_display(message: BaseMessage, max_length: int = 200) -> str:
    """Format a message for display in logs or UI.
    
    Args:
        message: Message to format
        max_length: Maximum content length to display
        
    Returns:
        Formatted message string
    """
    msg_type = message.__class__.__name__
    content = str(message.content)
    
    if len(content) > max_length:
        content = content[:max_length] + "..."
    
    formatted = f"[{msg_type}] {content}"
    
    # Add tool call info for AI messages
    if isinstance(message, AIMessage) and hasattr(message, 'tool_calls') and message.tool_calls:
        tool_names = [tc.get('name', 'unknown') for tc in message.tool_calls]
        formatted += f" (Tools: {', '.join(tool_names)})"
    
    return formatted


def smart_preserve_messages(messages, keep_count=2):
    """Preserve tool call/response pairs while trimming to keep_count messages.
    
    Args:
        messages: List of LangChain message objects
        keep_count: Target number of messages to preserve (default: 2)
        
    Returns:
        List of preserved messages with tool call pairs intact
    """
    if len(messages) <= keep_count:
        return messages
    
    # Try to use LangGraph's trim_messages for proper tool call preservation
    try:
        from langchain_core.messages.utils import trim_messages
        
        # Simple token estimation: ~400 tokens per message average
        def simple_token_counter(msgs):
            return len(msgs) * 400
        
        # Token budget: keep_count * 800 (to account for tool messages)
        max_tokens = keep_count * 800
        
        return trim_messages(
            messages,
            strategy="last",
            token_counter=simple_token_counter,
            max_tokens=max_tokens,
            start_on="human",
            end_on=("human", "tool"),
            include_system=True
        )
    except ImportError:
        # Fallback: just keep the last keep_count messages
        return messages[-keep_count:]