#!/usr/bin/env python3
"""Debug script to test the LLM planning call directly."""

import asyncio
import sys
import os
sys.path.insert(0, '/Users/nick.peterson/consultant-assistant')

from src.orchestrator.plan_execute_graph import PlanExecuteGraph
from src.orchestrator.plan_execute_state import create_initial_state
from langchain_core.messages import HumanMessage as LCHumanMessage

async def test_llm_planning():
    """Test the LLM planning call directly."""
    print("Testing LLM planning call...")
    
    # Create graph
    graph = PlanExecuteGraph()
    
    # Create initial state
    initial_state = create_initial_state("hello")
    initial_state["messages"] = [LCHumanMessage(content="hello")]
    
    # Test the LLM call directly with more detailed debugging
    try:
        # Import what we need directly
        from src.utils.config import (
            AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_CHAT_DEPLOYMENT_NAME,
            AZURE_OPENAI_API_VERSION, AZURE_OPENAI_API_KEY,
            get_llm_config
        )
        from langchain_openai import AzureChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage
        from src.utils.agents.prompts import get_planning_system_message
        
        print("Testing LLM configuration...")
        print(f"Endpoint: {AZURE_OPENAI_ENDPOINT}")
        print(f"Deployment: {AZURE_OPENAI_CHAT_DEPLOYMENT_NAME}")
        print(f"API Version: {AZURE_OPENAI_API_VERSION}")
        print(f"API Key: {'***' + AZURE_OPENAI_API_KEY[-4:] if AZURE_OPENAI_API_KEY else 'None'}")
        
        # Get LLM config
        llm_config = get_llm_config()
        
        # Create LLM instance
        llm = AzureChatOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            deployment_name=AZURE_OPENAI_CHAT_DEPLOYMENT_NAME,
            api_version=AZURE_OPENAI_API_VERSION,
            api_key=AZURE_OPENAI_API_KEY,
            temperature=llm_config.temperature,
            max_tokens=llm_config.max_tokens
        )
        
        print("✅ LLM instance created successfully")
        
        # Get the planning system message
        system_msg = get_planning_system_message()
        
        print("✅ Planning system message loaded")
        
        # Create the prompt
        user_prompt = """
        Create a detailed execution plan for: "hello"
        
        Break this down into specific, actionable tasks. Each task should:
        - Be specific and measurable
        - Include which agent to route to (salesforce, jira, servicenow, or orchestrator)
        - Note any dependencies on previous tasks
        - Be atomic (complete in one step)
        
        Format as a numbered list:
        1. [Task description] (Agent: salesforce)
        2. [Next task] (Agent: jira, depends on: 1)
        ...
        
        Focus on the core business objective and be practical about what can be accomplished.
        """
        
        # Combine system message with user prompt
        messages = [
            SystemMessage(content=system_msg),
            HumanMessage(content=user_prompt)
        ]
        
        print("✅ Messages prepared, calling LLM...")
        
        # Get response from LLM
        response = await llm.ainvoke(messages)
        
        print(f"✅ LLM call successful!")
        print(f"Response content:\n{response.content}")
        
        # Check if this is a proper plan
        if "1." in response.content and "Agent:" in response.content:
            print("✅ This looks like a proper plan!")
        else:
            print("⚠️  This doesn't look like a proper plan format")
        
    except Exception as e:
        print(f"❌ LLM call failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_llm_planning())