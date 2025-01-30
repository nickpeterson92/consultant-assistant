# main.py


import os
from typing import Annotated

from typing_extensions import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import Command, interrupt

from langchain_core.tools import tool
from langchain_openai import AzureChatOpenAI

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


def main():
    print("\n=== Salesforce Assistant Powered by LangGraph ===\n")

    class State(TypedDict):
        messages: Annotated[list, add_messages]

    memory = MemorySaver()
    graph_builder = StateGraph(State)
    
    @tool
    def human_assistance(query: str) -> str:
        """Request assistance from a human"""
        human_response = interrupt({"query": query})
        return human_response["data"]
    
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


    def chatbot(state: State):
        return {"messages": [llm_with_tools.invoke(state["messages"])]}
    
    
    graph_builder.add_node("chatbot", chatbot)
    
    tool_node = ToolNode(tools=tools)
    graph_builder.add_node("tools", tool_node)
    
    graph_builder.add_conditional_edges(
        "chatbot",
        tools_condition,
    )
    graph_builder.add_edge("tools", "chatbot")
    graph_builder.set_entry_point("chatbot")
    graph_builder.add_edge(START, "chatbot")
    graph_builder.add_edge("chatbot", END)
    graph = graph_builder.compile(checkpointer=memory)
    
    config = {"configurable": {"thread_id": "1"}}
    while True:
        try:
            user_input = input("User: ")
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break
    
            events = graph.stream(
                {"messages": [{"role": "user", "content": user_input}]},
                config,
                stream_mode="values",
            )

            for event in events:
                event["messages"][-1].pretty_print()
        except:
            break

if __name__ == "__main__":
    main()
