#!/usr/bin/env python3
"""Debug script to test the LLM call directly without any fallback."""

import asyncio
import sys
import os
sys.path.insert(0, '/Users/nick.peterson/consultant-assistant')

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Test direct LLM call
async def test_direct_llm():
    """Test the LLM call directly."""
    print("Testing direct LLM call...")
    
    try:
        # Direct LLM setup
        from src.utils.config import get_llm_config
        from langchain_openai import AzureChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage
        from src.utils.agents.prompts import get_planning_system_message
        
        # Get config
        llm_config = get_llm_config()
        
        # Create LLM
        llm = AzureChatOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            azure_deployment=llm_config.azure_deployment,
            api_version=llm_config.api_version,
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            temperature=llm_config.temperature,
            max_tokens=llm_config.max_tokens
        )
        
        # Get planning system message
        system_msg = get_planning_system_message()
        
        # Create user prompt
        user_prompt = """
        Create a detailed execution plan for: "hello"
        
        Break this down into specific, actionable tasks. Each task should:
        - Be specific and measurable
        - Include which agent to route to (salesforce, jira, servicenow, or orchestrator)
        - Note any dependencies on previous tasks
        - Be atomic (complete in one step)
        
        Format as a numbered list:
        1. [Task description] (Agent: agent_name)
        2. [Next task] (Agent: agent_name, depends on: 1)
        ...
        
        Focus on the core business objective and be practical about what can be accomplished.
        """
        
        # Create messages
        messages = [
            SystemMessage(content=system_msg),
            HumanMessage(content=user_prompt)
        ]
        
        print(f"System message length: {len(system_msg)} chars")
        print(f"User prompt length: {len(user_prompt)} chars")
        print("Calling LLM...")
        
        # Make the call
        response = await llm.ainvoke(messages)
        
        print(f"✅ LLM response received!")
        print(f"Response length: {len(response.content)} chars")
        print(f"Response content:\n{response.content}")
        
        # Check if it's a proper plan
        if "1." in response.content and "Agent:" in response.content:
            print("✅ This looks like a proper plan!")
            if "Respond to user greeting" in response.content:
                print("✅ Plan correctly handles 'hello' request!")
        else:
            print("❌ This doesn't look like a proper plan format")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_direct_llm())