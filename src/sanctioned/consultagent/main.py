# main.py


import os
from typing import Annotated

from typing_extensions import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from langgraph.graph.message import RemoveMessage, add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI

from helpers import unify_messages_to_dicts, convert_dicts_to_lc_messages
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


    class OverallState(TypedDict):
        messages: Annotated[list, add_messages]
        summary: str


    memory = MemorySaver()
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
                UpdateTaskTool()
            ]
    
    attachment_tools = [OCRTool()]

    llm = create_azure_openai_chat()
    llm_with_tools = llm.bind_tools(tools+attachment_tools)

    def call_model(state: OverallState) -> OverallState:
        print("Calling model")
        summary = state.get("summary", "")

        if summary:
            system_message = f"Here is a summary of the conversation: {summary}"
            messages = [SystemMessage(content=system_message)] + state["messages"]
        else:
            messages = state["messages"]

        response = llm_with_tools.invoke(
                convert_dicts_to_lc_messages(
                    unify_messages_to_dicts(messages)))
        return {"messages": response}

    def summarize_conversation(state: OverallState) -> OverallState:
        print("Summarizing conversation")
        summary = state.get("summary", "")

        if summary:
            summary_message = (
                f"This is a summary of the conversation: {summary}\n\n"
                "Extend the summary by taking into account the new messsages above "
                "Prioritize maintaining the order of the records, their relationships "
                "and their key:value pairs. If a user refers to a previous record, check the "
                "summary before retrieving the record from the target system. "
                "If the record is not in the summary, retrieve the record. "
                "Don't just show no records found."
            )
        else:
            summary_message =( "Create a summary of the conversation above. " 
                              "Prioritize maintaining the order of the records, their relationships "
                               "and their key:value pairs:"
            )
        messages = state["messages"] + [HumanMessage(content=summary_message)]
        response = llm_with_tools.invoke(
                convert_dicts_to_lc_messages(
                    unify_messages_to_dicts(messages)))
        
        delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-2]]
        state.update({"summary": response.content, "messages": delete_messages})

    def should_continue(state: OverallState):
        """Return the first node to execute."""

        messages = state["messages"]

        if len(messages)  > 6:
            return "summarize_conversation"
        
        return END
        
    salesforce_tool_node = ToolNode(tools=tools)
    graph_builder.add_node("tools", salesforce_tool_node)

    attachment_tool_node = ToolNode(tools=attachment_tools)
    graph_builder.add_node("attachment_tools", attachment_tool_node)
    
    graph_builder.add_node("conversation", call_model)
    graph_builder.add_node(summarize_conversation)

    graph_builder.add_conditional_edges(
        "conversation",
        tools_condition,
    )
    graph_builder.add_conditional_edges(
        "conversation",
        should_continue,
    )

    graph_builder.add_edge("tools", "conversation")
    graph_builder.add_edge("conversation", END)
    graph_builder.set_entry_point("conversation")
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
            
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
