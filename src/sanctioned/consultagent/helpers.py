from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

def unify_messages_to_dicts(messages: list) -> list[dict]:
    """
    Convert each message (which might be a HumanMessage/SystemMessage/ToolMessage or dict)
    into a dict with keys: role, content, possibly name/other fields.

    This ensures they are subscriptable so we can do msg["role"], msg["content"], etc.
    """
    unified = []
    for msg in messages:
        if isinstance(msg, dict):
            # Already a dict, assume it has "role"/"content"
            unified.append(msg)
        elif isinstance(msg, HumanMessage):
            unified.append({
                "role": "user",
                "content": msg.content
            })
        elif isinstance(msg, SystemMessage):
            unified.append({
                "role": "system",
                "content": msg.content
            })
        elif isinstance(msg, ToolMessage):
            unified.append({
                "role": "tool",
                "content": msg.content
            })
        else:
            unified.append({
                "role": "assistant",
                "content": str(msg)
            })
    return unified


def convert_dicts_to_lc_messages(dict_messages: list[dict]) -> list:
    from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
    # or wherever your message classes are

    lc_msgs = []
    for m in dict_messages:
        role = m["role"]
        content = m["content"]
        if role == "user":
            lc_msgs.append(HumanMessage(content=content))
        elif role == "system":
            lc_msgs.append(SystemMessage(content=content))
        elif role == "tool_calls":
            # map to ToolMessage or something else
            lc_msgs.append(ToolMessage(content=content))
        else:
            # fallback
            from langchain_core.messages import AIMessage
            lc_msgs.append(AIMessage(content=content))
    return lc_msgs
