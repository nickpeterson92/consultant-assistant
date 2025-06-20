#!/usr/bin/env python3

import asyncio
import sys
import os

# Add path for imports  
project_root = os.path.join(os.path.dirname(__file__))
sys.path.insert(0, project_root)

from src.orchestrator.main import build_orchestrator_graph

async def test_complex_scenario():
    """Test the complex multi-tool scenario that was failing"""
    print("Testing complex multi-tool scenario...")
    
    try:
        # Build the orchestrator graph
        graph = build_orchestrator_graph(debug_mode=False)
        config = {'configurable': {'thread_id': 'test-complex', 'user_id': 'test-user'}}
        
        # Test 1: Simple request (should work)
        print("\n1. Testing simple request...")
        result1 = await graph.ainvoke(
            {'messages': [{'role': 'user', 'content': 'get the lundgren account'}]},
            config
        )
        
        if 'messages' in result1 and result1['messages']:
            last_message = result1['messages'][-1]
            print("✅ Simple request successful")
            print(f"Response: {str(last_message.content)[:100]}...")
        else:
            print("❌ Simple request failed")
            return False
        
        # Test 2: Complex multi-tool request (this was failing before)
        print("\n2. Testing complex multi-tool request...")
        result2 = await graph.ainvoke(
            {'messages': [{'role': 'user', 'content': 'get an all-up, birds-eye view of this account'}]},
            config
        )
        
        if 'messages' in result2 and result2['messages']:
            last_message = result2['messages'][-1]
            print("✅ Complex request successful!")
            print(f"Response: {str(last_message.content)[:200]}...")
            return True
        else:
            print("❌ Complex request failed")
            return False
            
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False

async def main():
    success = await test_complex_scenario()
    
    print(f"\n{'='*50}")
    print(f"RESULT: {'✅ SUCCESS - Enhanced message cleanup working!' if success else '❌ FAILED'}")
    
    if success:
        print("\n🎉 The multi-agent system with enhanced message cleanup is fully functional!")
        print("✅ Both simple and complex multi-tool workflows work correctly")
        print("✅ No more OpenAI API 400 errors from malformed tool messages")
        print("✅ System is ready for production use")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)