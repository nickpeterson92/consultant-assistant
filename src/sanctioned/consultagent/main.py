# main.py


import os
import json
import asyncio
import argparse

from typing import Annotated
from typing_extensions import TypedDict

from trustcall import create_extractor

from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore
from langgraph.graph import StateGraph, END
from langgraph.graph.message import RemoveMessage, add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import AzureChatOpenAI

from state_manager import StateManager
from sys_msg import chatbot_sys_msg, summary_sys_msg, TRUSTCALL_INSTRUCTION
from helpers import unify_messages_to_dicts, convert_dicts_to_lc_messages, type_out
from memory_schemas import AccountList
from attachment_tools import OCRTool
from salesforce_tools import (
    CreateLeadTool,
    GetLeadTool,
    UpdateLeadTool,
    GetOpportunityTool,
    UpdateOpportunityTool,
    CreateOpportunityTool,
    GetAccountTool,
    CreateAccountTool,
    UpdateAccountTool,
    GetContactTool,
    CreateContactTool,
    UpdateContactTool,
    GetCaseTool,
    CreateCaseTool,
    UpdateCaseTool,
    GetTaskTool,
    CreateTaskTool,
    UpdateTaskTool
)

# Debug mode flag
parser = argparse.ArgumentParser(description="Salesforce Assistant Powered by LangGraph")
parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode (disable animation and show events from all nodes)")
args = parser.parse_args()
DEBUG_MODE = args.debug

def create_azure_openai_chat():
    return AzureChatOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"],
        openai_api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
        temperature=0.0,
    )

node_to_stream = "conversation"
state_mgr = StateManager()

async def main():
    print("\n=== Salesforce Assistant Powered by LangGraph ===\n")

    class OverallState(TypedDict):
        messages: Annotated[list, add_messages]
        summary: str
        turns: int 

    memory = MemorySaver()
    memory_store = InMemoryStore()

    graph_builder = StateGraph(OverallState)
    tools = [
        CreateLeadTool(),
        GetLeadTool(),
        UpdateLeadTool(), 
        GetOpportunityTool(), 
        UpdateOpportunityTool(), 
        CreateOpportunityTool(),
        GetAccountTool(),
        CreateAccountTool(),
        UpdateAccountTool(),
        GetContactTool(),
        CreateContactTool(),
        UpdateContactTool(),
        GetCaseTool(),
        CreateCaseTool(),
        UpdateCaseTool(),
        GetTaskTool(),
        CreateTaskTool(),
        UpdateTaskTool(),
        OCRTool()
    ]

    llm = create_azure_openai_chat()
    llm_with_tools = llm.bind_tools(tools)
    trustcall_extractor = create_extractor(
        llm,
        tools=[AccountList],
        tool_choice="AccountList",
    )

    def chatbot(state: OverallState, config: RunnableConfig, store: BaseStore):
        summary = state.get("summary", "No summary available")
        turn = state.get("turns", 0)

        user_id = config["configurable"]["user_id"]

        namespace = ("memory", user_id)
        key = "AccountList"
        existing_memory = store.get(namespace, key)
        existing_records = {"AccountList": existing_memory.value} if existing_memory else None

        system_message = chatbot_sys_msg(summary, existing_records)
        messages = [SystemMessage(content=system_message)] + state["messages"]

        response = llm_with_tools.invoke(
            convert_dicts_to_lc_messages(
                unify_messages_to_dicts(messages)
            )
        )

        state_mgr.update_state({"messages": response, "turns": turn + 1})
        return {"messages": response, "turns": turn + 1}
   
    def summarize_conversation(state: OverallState):
        summary = state.get("summary", "No summary available")

        system_message = summary_sys_msg(summary)
        messages = state["messages"] + [HumanMessage(content=system_message)]

        response = llm.invoke(
            convert_dicts_to_lc_messages(
                unify_messages_to_dicts(messages)
            )
        )

        delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-2]]
        return {"summary": response.content, "messages": delete_messages}

    def needs_summary(state: OverallState):
        """Summarize conversation if more than 6 messages"""
        messages = state["messages"]
        if len(messages) > 6:
            return "summarize_conversation"
        return END
    
    async def memorize_records(state: OverallState, config: RunnableConfig, store: BaseStore):
        """Memorize field-level details of records"""
        summary = state.get("summary", "No summary available")
        messages = state["messages"]
        user_id = config["configurable"]["user_id"]

        namespace = ("memory", user_id)
        key = "AccountList"
        existing_memory = store.get(namespace, key)
        existing_records = {"AccountList": existing_memory.value} if existing_memory else {"AccountList": AccountList().model_dump()}
        print(f"Existing memory: {existing_records}") if DEBUG_MODE else None

        messages = {
                    "messages": [SystemMessage(content=TRUSTCALL_INSTRUCTION), HumanMessage(content=summary)],
                    "existing": existing_records,
        }
        print(f"MEMORY Messages: {messages}") if DEBUG_MODE else None

        response = await trustcall_extractor.ainvoke(messages)
        print(f"MEMORY Response: {response}") if DEBUG_MODE else None

        response = response["responses"][0].model_dump()
        store.put(namespace, key, response)
        print(f"Updated memory: {response}") if DEBUG_MODE else None

        return {"turns": 0}

    def needs_memory(state: OverallState):
        """Memorize if more than 4 turns"""
        turns = state.get("turns")
        if turns > 6:
            return "memorize_records"
        return END
    
    tool_node = ToolNode(tools=tools)
    graph_builder.add_node("tools", tool_node)
    graph_builder.add_node("conversation", chatbot)
    graph_builder.add_node(summarize_conversation)
    graph_builder.add_node(memorize_records)

    graph_builder.set_entry_point("conversation")
    graph_builder.add_conditional_edges("conversation", tools_condition)
    graph_builder.add_conditional_edges("conversation", needs_summary)
    graph_builder.add_conditional_edges("conversation", needs_memory)
    graph_builder.add_edge("tools", "conversation")
    graph_builder.set_finish_point("conversation")
    
    graph = graph_builder.compile(checkpointer=memory, store=memory_store)
    
    config = {"configurable": {"thread_id": "1", "user_id": "1"}}

    while True:
        try:
            user_input = input("User: ")
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break

            if DEBUG_MODE:
                # Debug mode: Use the original approach and print events from all nodes.
                async for event in graph.astream(
                    {"messages": [{"role": "user", "content": user_input}]},
                    config,
                    stream_mode="values",
                ):
                    # Print the last message in the event
                    event["messages"][-1].pretty_print()
            else:
                # Non-debug mode: Process only the desired events with animated output.
                async for event in graph.astream_events(
                    {"messages": [{"role": "user", "content": user_input}]},
                    config,
                    stream_mode="values",
                    version="v2"
                ):
                    # Process only events from the desired node.
                    if (event.get("event") == "on_chat_model_stream" and 
                        event.get("metadata", {}).get("langgraph_node", "") == node_to_stream):
                        
                        data = event["data"]
                        if isinstance(data, dict) and "chunk" in data:
                            chunk_obj = data["chunk"]
                            if hasattr(chunk_obj, "content"):
                                chunk_content = chunk_obj.content
                            elif isinstance(chunk_obj, dict):
                                chunk_content = chunk_obj.get("content", "")
                            else:
                                chunk_content = str(chunk_obj)
                        else:
                            chunk_content = json.dumps(data) if isinstance(data, dict) else str(data)
                        
                        # Animate the output of this chunk.
                        await type_out(chunk_content, delay=0.02)
            print()

        except Exception as e:
            print(f"An error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())
