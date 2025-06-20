# main.py


import os
import json
import asyncio
import argparse

from dotenv import load_dotenv

from typing import Annotated
from typing_extensions import TypedDict

from trustcall import create_extractor

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from langgraph.graph.message import RemoveMessage, add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import AzureChatOpenAI

from store.sqlite_store import SQLiteStore
from store.memory_schemas import AccountList
from utils.state_manager import StateManager
from utils.sys_msg import chatbot_sys_msg, summary_sys_msg, TRUSTCALL_INSTRUCTION
from utils.helpers import clean_orphaned_tool_calls, type_out
from tools.attachment_tools import OCRTool
from tools.salesforce_tools import (
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

# Setup command-line argument parsing
parser = argparse.ArgumentParser(description="Salesforce Assistant Powered by LangGraph")
parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode (disable animation and show events from all nodes)")

# Global state manager instance
state_mgr = StateManager()

def create_azure_openai_chat():
    return AzureChatOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"],
        openai_api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        openai_api_key=os.environ["AZURE_OPENAI_API_KEY"],
        temperature=0.0,
    )

def build_graph(debug_mode: bool = False):
    """
    Build and compile the LangGraph graph.
    """
    load_dotenv()

    # Define the state schema
    class OverallState(TypedDict):
        messages: Annotated[list, add_messages]
        summary: str
        memory: dict
        turns: int 

    memory = MemorySaver()
    memory_store = SQLiteStore()

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

    # Node function: chatbot
    def chatbot(state: OverallState, config: RunnableConfig):
        summary = state.get("summary", "No summary available")
        memory_val = state.get("memory", "No memory available")
        turn = state.get("turns", 0)
        if debug_mode:
            print(f"CHATBOT summary: {summary}")
            print(f"CHATBOT memory: {memory_val}")
            print(f"CHATBOT turns: {turn}")

        if memory_val == "No memory available":
            user_id = config["configurable"]["user_id"]
            namespace = ("memory", user_id)
            key = "AccountList"
            store_conn = memory_store.get_connection("memory_store.db")
            existing_memory = store_conn.get(namespace, key)
            if debug_mode:
                print(f"CHATBOT Existing memory: {existing_memory}")
            existing_memory = {"AccountList": existing_memory} if existing_memory else {"AccountList": AccountList().model_dump()}
        else:
            existing_memory = memory_val

        system_message = chatbot_sys_msg(summary, existing_memory)
        messages = [SystemMessage(content=system_message)] + state["messages"]
        messages = clean_orphaned_tool_calls(messages)
        response = llm_with_tools.invoke(messages)

        state_mgr.update_state({"messages": response, "memory": existing_memory, "turns": turn + 1})
        return {"messages": response, "memory": existing_memory, "turns": turn + 1}

    # Node function: summarize_conversation
    def summarize_conversation(state: OverallState):
        summary = state.get("summary", "No summary available")
        memory_val = state.get("memory", "No memory available")
        if debug_mode:
            print(f"SUMMARY summary: {summary}")
            print(f"SUMMARY memory: {memory_val}")
            
        system_message = summary_sys_msg(summary, memory_val)
        messages = state["messages"] + [HumanMessage(content=system_message)]
        messages = clean_orphaned_tool_calls(messages)
        response = llm_with_tools.invoke(messages)
        delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-2]]
        return {"summary": response.content, "messages": delete_messages}

    # Node function: needs_summary
    def needs_summary(state: OverallState):
        if len(state["messages"]) > 6:
            return "summarize_conversation"
        return END

    # Node function: memorize_records
    async def memorize_records(state: OverallState, config: RunnableConfig):
        user_id = config["configurable"]["user_id"]
        namespace = ("memory", user_id)
        key = "AccountList"
        store_conn = memory_store.get_connection("memory_store.db")
        existing_memory = store_conn.get(namespace, key)
        existing_records = {"AccountList": existing_memory} if existing_memory else {"AccountList": AccountList().model_dump()}
        if debug_mode:
            print(f"Existing memory: {existing_records}")
        messages = {
            "messages": [SystemMessage(content=TRUSTCALL_INSTRUCTION), 
                         HumanMessage(content=state.get("summary", ""))],
            "existing": existing_records,
        }
        if debug_mode:
            print(f"MEMORY Messages: {messages}")

        response = await trustcall_extractor.ainvoke(messages)
        if debug_mode:
            print(f"MEMORY Response: {response}")
        response = response["responses"][0].model_dump()
        store_conn.put(namespace, key, response)
        if debug_mode:
            print(f"Updated memory: {response}")
        return {"memory": response, "turns": 0}

    # Node function: needs_memory
    def needs_memory(state: OverallState):
        if state.get("turns", 0) > 6:
            return "memorize_records"
        return END

    # Build the graph with nodes and edges
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

    # Compile and return the graph
    return graph_builder.compile(checkpointer=memory, store=memory_store)

# Build and export the graph at the module level
graph = build_graph(debug_mode=False)

# Main interactive function (CLI mode)
async def main():
    args = parser.parse_args()
    DEBUG_MODE = args.debug

    # Rebuild the graph with debug mode if requested
    if DEBUG_MODE:
        local_graph = build_graph(debug_mode=True)
    else:
        local_graph = graph  # use the module-level graph

    print("\n=== Salesforce Assistant Powered by LangGraph ===\n")
    config = {"configurable": {"thread_id": "1", "user_id": "1"}}
    node_to_stream = "conversation"

    while True:
        additional_kwargs = None
        try:
            user_input = input("USER: ")
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break

            if DEBUG_MODE:
                # In debug mode, stream all events
                async for event in local_graph.astream(
                    {"messages": [{"role": "user", "content": user_input}]},
                    config,
                    stream_mode="values",
                ):
                    event["messages"][-1].pretty_print()
            else:
                print()
                # In non-debug mode, process only specific streamed events
                async for event in local_graph.astream_events(
                    {"messages": [{"role": "user", "content": user_input}]},
                    config,
                    stream_mode="values",
                    version="v2"
                ):
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
                        await type_out(chunk_content)
                        if isinstance(data, dict) and "chunk" in data:
                            chunk_obj = data["chunk"]
                            if hasattr(chunk_obj, "additional_kwargs"):
                                kwargs_obj = chunk_obj.additional_kwargs
                            elif isinstance(chunk_obj, dict):
                                kwargs_obj = chunk_obj.get("additional_kwargs", {})
                            else:
                                kwargs_obj = None

                            if kwargs_obj and not additional_kwargs:
                                print("\n\n")
                                additional_kwargs = kwargs_obj
            if not DEBUG_MODE:
                print("\n\n")
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
