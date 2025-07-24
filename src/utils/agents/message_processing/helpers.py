"""Message processing helper utilities."""

from typing import List, Dict, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage


def trim_messages_for_context(
    messages: List[BaseMessage],
    max_tokens: int = 80000,  # Conservative default - leave room for system messages and completion
    keep_system: bool = True,
    keep_first_n: int = 2,
    keep_last_n: int = 15,
    use_smart_trimming: bool = True
) -> List[BaseMessage]:
    """Trim messages to fit within token limits while preserving important context.
    
    Uses LangChain's official trim_messages when available for better tool call preservation.
    
    Args:
        messages: List of messages to trim
        max_tokens: Maximum token limit (default 80k for 128k models)
        keep_system: Whether to preserve system messages
        keep_first_n: Number of initial messages to keep
        keep_last_n: Number of recent messages to keep
        use_smart_trimming: Use LangChain's trim_messages if available
        
    Returns:
        Trimmed list of messages
    """
    if not messages:
        return []
    
    # Try to use LangChain's official trim_messages first
    if use_smart_trimming:
        try:
            from langchain_core.messages.utils import trim_messages
            
            # More accurate token estimation
            def token_counter(msgs):
                return estimate_message_tokens(msgs)
            
            trimmed = trim_messages(
                messages,
                strategy="last",
                token_counter=token_counter,
                max_tokens=max_tokens,
                start_on="human",
                end_on=("human", "tool"),
                include_system=keep_system
            )
            
            # Log trimming info
            from src.utils.logging import get_smart_logger
            logger = get_smart_logger("utility")
            logger.info("smart_message_trimming",
                    original_count=len(messages),
                    trimmed_count=len(trimmed),
                    estimated_tokens=estimate_message_tokens(trimmed),
                    max_tokens=max_tokens
            )
            
            return trimmed
        except ImportError:
            pass  # Fall back to manual trimming
    
    # Manual trimming fallback
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
    
    # Add important middle messages (errors, tool results)
    for msg in reversed(middle_messages):  # Add from most recent
        msg_tokens = estimate_message_tokens([msg])
        if current_tokens + msg_tokens <= max_tokens:
            # Prioritize error messages and important tool results
            if (isinstance(msg, AIMessage) and "error" in str(msg.content).lower()) or \
               (hasattr(msg, 'name') and msg.name in ['tool_error', 'tool_result']):
                result.insert(len(system_messages) + len(first_messages), msg)
                current_tokens += msg_tokens
    
    # Add remaining middle messages if still room
    for msg in reversed(middle_messages):
        if msg not in result:
            msg_tokens = estimate_message_tokens([msg])
            if current_tokens + msg_tokens <= max_tokens:
                result.insert(len(system_messages) + len(first_messages), msg)
                current_tokens += msg_tokens
            else:
                break
    
    # Log manual trimming info
    from src.utils.logging import get_smart_logger
    logger = get_smart_logger("utility")
    logger.info("manual_message_trimming",
        original_count=len(messages),
        trimmed_count=len(result),
        estimated_tokens=current_tokens,
        max_tokens=max_tokens
    )
    
    return result


def estimate_message_tokens(messages: List[BaseMessage]) -> int:
    """Estimate token count for messages.
    
    More accurate estimation based on OpenAI's guidelines:
    - ~4 characters per token for English text
    - Account for message structure overhead
    - Tool calls and their results can be verbose
    
    Args:
        messages: List of messages
        
    Returns:
        Estimated token count
    """
    total_chars = 0
    
    for msg in messages:
        # Content tokens
        content_str = str(msg.content)
        total_chars += len(content_str)
        
        # Message structure overhead (role, type, etc.)
        # Each message has ~20-30 tokens of overhead
        total_chars += 100  # ~25 tokens * 4 chars
        
        # System messages have more overhead
        if msg.__class__.__name__ == "SystemMessage":
            total_chars += 100  # Extra overhead
        
        # Tool calls are expensive
        if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls'):
            for tool_call in (msg.tool_calls or []):
                # Tool call structure + arguments
                tool_str = str(tool_call)
                total_chars += len(tool_str) + 200  # Extra for JSON structure
        
        # Tool messages (results) also have overhead
        if hasattr(msg, 'name') and msg.name:
            total_chars += 200  # Tool message structure
            # Large tool results (like search results) are very expensive
            if len(content_str) > 1000:
                total_chars += len(content_str) * 0.2  # Add 20% for JSON escaping
    
    # Conservative estimate: ~3.5 characters per token for structured content
    estimated_tokens = int(total_chars / 3.5)
    
    # Add safety margin (10%)
    return int(estimated_tokens * 1.1)


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