# main.py


import os
from operator import add
from typing import Annotated
from typing_extensions import TypedDict

import asyncio

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

from sys_msg import chatbot_sys_msg, summary_sys_msg, memory_sys_msg
from helpers import unify_messages_to_dicts, convert_dicts_to_lc_messages
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


def create_azure_openai_chat():
    return AzureChatOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"],
        openai_api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
        temperature=0.0,
    )

node_to_stream = "conversation"

async def main():
    print("\n=== Salesforce Assistant Powered by LangGraph ===\n")


    class OverallState(TypedDict):
        messages: Annotated[list, add_messages]
        summary: Annotated[str, add]
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
        tool_choice="AccountList"
    )

    def chatbot(state: OverallState, config: RunnableConfig, store:BaseStore):
        #print("DEBUG: Calling model")

        # Get the summary and turn count from the state
        summary = state.get("summary", "No summary available")
        turn = state.get("turns", 0)

        # Get the user_id value from the config
        user_id = config["configurable"]["user_id"]

        # Get the memory from the store
        namespace = (memory, user_id)
        key = "records"
        existing_memory = store.get(namespace, key)

        # Extract memory if it exists and prefix the content
        if existing_memory:
            existing_memory_content = existing_memory.value.get("memory")
        else:
            existing_memory_content = "No existing memory found"

        if summary:
            system_message = chatbot_sys_msg(summary, existing_memory_content)
            messages = [SystemMessage(content=system_message)] + state["messages"]
        else:
            messages = state["messages"]

        response = llm_with_tools.invoke(
            convert_dicts_to_lc_messages(
                unify_messages_to_dicts(messages)
            )
        )
        return {"messages": response, "turns": turn + 1}
   
    def summarize_conversation(state: OverallState, config: RunnableConfig, store:BaseStore):
        #print("DEBUG: Summarizing conversation")
        summary = state.get("summary", "No summary available")

        system_message = summary_sys_msg(summary)

        # Append the system message to the conversation history.
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
        # Get the user_id value from the config
        user_id = config["configurable"]["user_id"]

        # Get the memory from the store
        namespace = ("memory", user_id)
        key = "records"
        existing_memory = store.get(namespace, key)
        print(f"DEBUG <<MEMORY>>: {existing_memory}")

        if existing_memory:
            existing_memory_content = existing_memory.value.get("memory")
        else:
            existing_memory_content = "No existing memory found"

        system_message = memory_sys_msg(existing_memory_content)
        
        messages = state["messages"] + [HumanMessage(content=system_message)]
        response = await trustcall_extractor.ainvoke(
            convert_dicts_to_lc_messages(
                unify_messages_to_dicts(messages)
            )
        )
        #print(f"DEBUG: {response}")
        store.put(namespace, key, {"memory": response})
        return {"turns": 0}

    def needs_memory(state: OverallState):
        """Memorize records every 8 or so turns"""
        messages = state["messages"]

        if len(messages) > 6:
            return "memorize_records"
        
        return END
    
    tool_node = ToolNode(tools=tools)
    graph_builder.add_node("tools", tool_node)
    graph_builder.add_node("conversation", chatbot)
    graph_builder.add_node(summarize_conversation)
    graph_builder.add_node(memorize_records)

    graph_builder.set_entry_point("conversation")
    graph_builder.add_conditional_edges("conversation",tools_condition)
    graph_builder.add_conditional_edges("conversation",needs_summary)
    graph_builder.add_conditional_edges("conversation",needs_memory)
    graph_builder.add_edge("tools", "conversation")
    graph_builder.add_edge("conversation", END)
    
    graph = graph_builder.compile(checkpointer=memory, store=memory_store)
    config = {"configurable": {"thread_id": "1", "user_id": "1"}}

    while True:
        try:
            user_input = input("User: ")
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break

            async for event in graph.astream(
                {"messages": [{"role": "user", "content": user_input}]},
                config,
                stream_mode="values",):
                #print(event["messages"])
                event["messages"][-1].pretty_print()
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
