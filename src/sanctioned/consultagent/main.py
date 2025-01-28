# main.py


import os
import re
import json

from langchain_community.chat_models import AzureChatOpenAI
from langchain.agents import initialize_agent, AgentType
from langchain.memory import ConversationBufferMemory
from langchain.schema import AIMessage
from transformers import pipeline

from salesforce_tools import CreateLeadTool, GetOpportunityTool, UpdateOpportunityTool
from callbacks import MultipleMatchesCallback


# Azure OpenAI Setup
AZURE_OPENAI_API_KEY = os.environ["AZURE_OPENAI_API_KEY"]
AZURE_OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
AZURE_OPENAI_API_VERSION = os.environ["AZURE_OPENAI_API_VERSION"]
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME = os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"]

def create_azure_openai_chat():
    return AzureChatOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        azure_deployment=AZURE_OPENAI_CHAT_DEPLOYMENT_NAME,
        openai_api_version=AZURE_OPENAI_API_VERSION,
        openai_api_key=AZURE_OPENAI_API_KEY,
        temperature=0.0,
    )

# Create Agent with Callback
def create_salesforce_agent(memory):
    llm = create_azure_openai_chat()

    getter_tool = GetOpportunityTool()
    updater_tool = UpdateOpportunityTool(getter_tool=getter_tool)
    create_tool = CreateLeadTool()

    tools = [create_tool, updater_tool, getter_tool]

    system_msg = """
    You are a Salesforce assistant using function calling.
    """

    agent = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.OPENAI_FUNCTIONS,
        verbose=True,
        memory=memory,
        system_message=system_msg
    )

    return agent
    
classifier = pipeline(
    "zero-shot-classification", 
    model="facebook/bart-large-mnli"
)

intents = {
    "select_option": [
        "selecting an option from a previously shown list",
        "picking an option number",
    ],
    "new_request": [
        "updating a record in Salesforce",
        "creating a new record",
        "fetching or retrieving data in Salesforce",
    ]
}
def classify_intent(user_input):
    # Quick check for "pick \d+"
    if re.search(r"pick\s+option\s*\d+", user_input.lower()):
        return "select_option"
    
    # Then do zero-shot
    candidate_labels = list(intents.keys())
    hypothesis_template="User wants to: {}."
    results = classifier(user_input, candidate_labels=candidate_labels, hypothesis_template=hypothesis_template)
    return results["labels"][0]

# Leverage NLP to extract stage and amount
def extract_fields_from_input(user_input):
    """Extract stage and amount using NLP and fallback regex for monetary values."""

    # Define possible stages
    possible_stages = [
        "Proposal/Price Quote",
        "Closed Won",
        "Negotiation",
        "Id. Decision Makers",
        "Closed Lost",
    ]
    monetary_label = "monetary value"

    # Extract the stage
    hypothesis_template="A sales opportunity is being updated to stage: {}."
    stage_results = classifier(user_input, candidate_labels=possible_stages, hypothesis_template=hypothesis_template)
    stage = stage_results["labels"][0] if stage_results["scores"][0] > 0.5 else None
    
    # Extract the amount using regex fallback
    amount_match = re.search(r"[\$\s]?([\d,\.]+k?)", user_input, re.IGNORECASE)
    if amount_match:
        amount_str = amount_match.group(1).lower().replace(",", "")
        try:
            if "k" in amount_str:
                amount = float(amount_str.replace("k", "")) * 1000
            else:
                amount = float(amount_str)
        except ValueError:
            amount = None

    return stage, amount

# Main Logic
if __name__ == "__main__":
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True
    )
    multiple_matches_callback = MultipleMatchesCallback(memory)
    agent = create_salesforce_agent(memory)

    print("\nSalesforce Agent is ready. Type 'exit' or 'quit' to close.\n")

    while True:
        try:
            user_input = input("Your Request: ").strip()
            if user_input.lower() in ("exit", "quit"):
                print("Goodbye!")
                break

            print(f"DEBUG: Starting execution for input: {user_input}")
            
            user_intent = classify_intent(user_input)

            print(f"DEBUG: Classified intent: {user_intent}")
            
            # Handle numeric input (selection)
            memory_data = memory.load_memory_variables({})
            stored_context = None
            for msg in memory_data.get("chat_history", []):
                if isinstance(msg, AIMessage) and msg.content.startswith("{") and msg.content.endswith("}"):
                    try:
                        stored_context = json.loads(msg.content)
                        print("DEBUG: Retrieved context from memory:", stored_context)
                        break
                    except json.JSONDecodeError:
                        print("DEBUG: Failed to parse stored context:", msg.content)

            if user_input.isdigit() and stored_context:
                selection_index = int(user_input) - 1
                stored_matches = stored_context.get("matches")
                stage = stored_context.get("stage")
                amount = stored_context.get("amount")

                if stored_matches and 0 <= selection_index < len(stored_matches):
                    selected_match = stored_matches[selection_index]
                    print(f"DEBUG: User selected match: {selected_match}")

                    if not stage or not amount:
                        print("Error: Missing stage or amount in memory.")
                        continue

                    input_data = {
                        "input": json.dumps({
                            "opportunity_id": selected_match["id"],
                            "stage": stage,
                            "amount": amount
                        })
                    }
                    print("DEBUG: Invoking agent for update")
                    response = agent.run(input_data, callbacks=[multiple_matches_callback])
                    print("\nAGENT RESPONSE:\n", response)

                else:
                    print("Error: Invalid selection. Please choose a valid option.")
                continue

            if not user_input:
                print("Error: No input provided. Please enter a valid request.")
                continue
            
            if "update" in user_input.lower():
                stage, amount = extract_fields_from_input(user_input)
                print(f"DEBUG: Extracted stage: {stage}, amount: {amount}")
                if not stage or not amount:
                    print("Error: Could not extract stage or amount. Please rephrase your request.")
                    continue
            
                input_data = {
                    "input": json.dumps({
                        "request": user_input,
                        "stage": stage,
                        "amount": amount
                    })
                }
                print("DEBUG: Invoking agent for update with input_data:", input_data)
                response = agent.run(input_data, callbacks=[multiple_matches_callback])

            else:
                input_data = {"input": user_input}
                print("DEBUG: Invoking agent for retrieval with input_data:", input_data)
                response = agent.run(input_data, callbacks=[multiple_matches_callback])


            print("\nAGENT RESPONSE:\n", response)

        except Exception as e:
            print("Error:", e)
