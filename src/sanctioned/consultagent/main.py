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

# Instantiate zero shot classifier
classifier = pipeline(
    "zero-shot-classification", 
    model="facebook/bart-large-mnli"
)

# Azure chat creater helper
def create_azure_openai_chat():
    return AzureChatOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        azure_deployment=AZURE_OPENAI_CHAT_DEPLOYMENT_NAME,
        openai_api_version=AZURE_OPENAI_API_VERSION,
        openai_api_key=AZURE_OPENAI_API_KEY,
        temperature=0.0,
    )

# Create Agent with memory for callback
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

# Classify user intent, to-be used for routing requests, needs tuning
def classify_intent(user_input):
    user_intents = [
        "selecting from a numbered list",
        "creating a record",
        "updating a record",
        "retrieving a record"
    ]
    
    # Then do zero-shot
    hypothesis_template="A user is {}."
    results = classifier(user_input, candidate_labels=user_intents, hypothesis_template=hypothesis_template)
    return results["labels"][0]

# Extract stage and amount
MULTIPLIERS = {
    "k": 1_000,
    "thousand": 1_000,
    "million": 1_000_000,
    "billion": 1_000_000_000
}

AMOUNT_REGEX = re.compile(
    r"(?i)"                     # case-insensitive
    r"(?:\$|usd\s*)?"           # optional $ or 'USD'
    r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?"  # capture digits with optional commas or decimals
    r"|\d+(\.\d+)?)"            # or simpler fallback with decimals
    r"(?:\s*(k|thousand|million|billion))?"  # optional multiplier
)

def parse_amount_str(text: str) -> float:
    """
    Searches the text for a numeric monetary expression and returns it as a float.
    If multiple matches, returns the first. If none found, returns None.
    """
    match = AMOUNT_REGEX.search(text)
    if not match:
        return None

    # Groups:
    # - match.group(1) => the numeric portion with commas, decimals
    # - match.group(3) => optional multiplier like 'k', 'thousand'
    numeric_str = match.group(1)  # This is the whole numeric portion
    multiplier_str = match.group(3)  # k, thousand, million, or billion if present

    # Remove commas
    numeric_str = numeric_str.replace(",", "")

    # Convert to float
    try:
        value = float(numeric_str)
    except ValueError:
        return None

    # Apply multiplier if present
    if multiplier_str:
        # Lowercase to match dictionary
        multiplier_str = multiplier_str.lower()
        multiplier = MULTIPLIERS.get(multiplier_str, 1)
        value *= multiplier

    return value

# TODO: Modularize for better scalability
def extract_fields_from_input(user_input):
    """Extract stage and amount using NLP and fallback regex for monetary values."""

    # Define possible stages
    possible_stages = [
        "Proposal/Price Quote",
        "Closed Won",
        "Negotiation",
        "Id. Decision Makers",
        "Closed Lost",
        "Prospecting",
        "Qualification",
        "Needs Analysis",
        "Value Proposition",
        "Perception Analysis"
    ]

    # Extract the stage
    hypothesis_template="The text indicates the sales opportunity stage is {}."
    stage_results = classifier(user_input, candidate_labels=possible_stages, hypothesis_template=hypothesis_template)
    stage = stage_results["labels"][0] if stage_results["scores"][0] > 0.5 else None
    
    # Extract the amount using regex
    amount = parse_amount_str(user_input)

    return stage, amount
    
def extract_number(input_string):
    match = re.search(r'\b\d+\b', input_string)
    return match.group() if match else None
    
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

            # TODO: Leverage user intent once tuned...
            if user_intent == "selecting from a numbered list" and stored_context:
                selection_index = int(extract_number(user_input)) - 1
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

            # TODO: Futher expand user intent to include more intents for better routing
            if user_intent == "updating a record":
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
