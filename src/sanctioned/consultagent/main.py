# main.py


import os
from typing import Annotated

from typing_extensions import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from langchain_openai import AzureChatOpenAI

from salesforce_tools import CreateLeadTool, GetOpportunityTool, UpdateOpportunityTool, CreateOpportunityTool, GetAccountTool



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

    tools = [
             CreateLeadTool(), 
             GetOpportunityTool(), 
             UpdateOpportunityTool(), 
             CreateOpportunityTool(),
             GetAccountTool()
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
    graph = graph_builder.compile(checkpointer=memory)

    # 8) Start an Interactive Loop:
    def stream_graph_updates(user_input: str):
        for event in graph.stream({"messages": [{"role": "user", "content": user_input}]}, config = {"configurable": {"thread_id": "1"}}):
            for value in event.values():
                print("Assistant:", value["messages"][-1].content)
    
    
    while True:
        try:
            user_input = input("User: ")
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break
    
            stream_graph_updates(user_input)
        except:
            # fallback if input() is not available
            user_input = "What do you know about LangGraph?"
            print("User: " + user_input)
            stream_graph_updates(user_input)
            break

if __name__ == "__main__":
    main()
