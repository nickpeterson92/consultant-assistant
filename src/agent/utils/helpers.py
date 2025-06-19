# helpers.property


import sys
import asyncio
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage


def unify_messages_to_dicts(messages: list) -> list[dict]:
    # Map message types to a conversion lambda.
    converters = {
        HumanMessage: lambda m: {"role": "user", "content": m.content},
        SystemMessage: lambda m: {"role": "system", "content": m.content},
        ToolMessage: lambda m: {"role": "tool", "content": m.content},
        AIMessage: lambda m: {"role": "assistant", "content": m.content},
    }
    unified = []
    for msg in messages:
        if isinstance(msg, dict):
            unified.append(msg)
        else:
            # Try each converter based on type.
            for msg_type, converter in converters.items():
                if isinstance(msg, msg_type):
                    unified.append(converter(msg))
                    break
            else:
                # Fallback if no type matches.
                unified.append({"role": "assistant", "content": str(msg)})
    return unified


def convert_dicts_to_lc_messages(dict_messages: list[dict]) -> list:
    # Map roles to message classes; default to AIMessage.
    role_mapping = {
        "user": HumanMessage,
        "system": SystemMessage,
        "tool": AIMessage,  # Defaults tool messages to AIMessage.
    }
    lc_msgs = []
    for m in dict_messages:
        role = m.get("role", "assistant")
        content = m.get("content", "")
        message_class = role_mapping.get(role, AIMessage)
        lc_msgs.append(message_class(content=content))
    return lc_msgs


async def type_out(text, delay=0.02):
    # Animates printing of the given text one character at a time.
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        await asyncio.sleep(delay)

