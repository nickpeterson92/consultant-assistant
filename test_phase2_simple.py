#!/usr/bin/env python3
"""Simple Phase 2 integration verification."""

import sys
import os

# Add the project root to Python path for src imports
sys.path.insert(0, os.path.dirname(__file__))

def test_memory_imports():
    """Test that memory system is properly imported in plan_and_execute."""
    print("📦 Testing memory system imports...")
    
    try:
        from src.orchestrator.plan_and_execute import execute_step, plan_step, replan_step
        print("   ✅ All plan-and-execute functions imported")
        
        # Check if memory imports are present in the source
        import inspect
        
        # Check execute_step source
        execute_source = inspect.getsource(execute_step)
        has_memory_import = "from src.memory import" in execute_source
        has_retrieve = "retrieve_relevant" in execute_source
        has_store = "memory.store" in execute_source
        
        if has_memory_import and has_retrieve and has_store:
            print("   ✅ execute_step has complete memory integration")
        else:
            print(f"   ❌ execute_step missing memory integration: import={has_memory_import}, retrieve={has_retrieve}, store={has_store}")
            return False
        
        # Check plan_step source
        plan_source = inspect.getsource(plan_step)
        has_plan_memory = "retrieve_relevant" in plan_source and "memory_context" in plan_source
        
        if has_plan_memory:
            print("   ✅ plan_step has memory integration")
        else:
            print("   ❌ plan_step missing memory integration")
            return False
        
        # Check replan_step source  
        replan_source = inspect.getsource(replan_step)
        has_replan_memory = "retrieve_relevant" in replan_source
        has_task_completion = "mark_task_completed" in replan_source
        
        if has_replan_memory and has_task_completion:
            print("   ✅ replan_step has memory integration and task completion")
        else:
            print(f"   ❌ replan_step missing features: memory={has_replan_memory}, completion={has_task_completion}")
            return False
        
        return True
        
    except Exception as e:
        print(f"   ❌ Import error: {e}")
        return False


def test_memory_system_functionality():
    """Test that memory system functions work correctly."""
    print(f"\n🧠 Testing memory system functionality...")
    
    try:
        from src.memory import get_thread_memory, ContextType
        
        # Test memory creation and storage
        memory = get_thread_memory("test-functionality")
        
        node_id = memory.store(
            content={"test": "data"},
            context_type=ContextType.DOMAIN_ENTITY,
            tags={"test", "functionality"},
            auto_summarize=True  # Test auto-summary integration
        )
        
        print(f"   ✅ Memory storage working, node ID: {node_id[:8]}...")
        
        # Test retrieval
        results = memory.retrieve_relevant("test data functionality")
        
        if results and len(results) > 0:
            print(f"   ✅ Memory retrieval working, found {len(results)} results")
            
            # Test auto-summary
            summary = results[0].summary
            if summary and summary != "":
                print(f"   ✅ Auto-summary working: '{summary}'")
            else:
                print(f"   ❌ Auto-summary not working")
                return False
        else:
            print(f"   ❌ Memory retrieval not working")
            return False
        
        # Test task completion
        decayed_count = memory.mark_task_completed(task_related_tags={"test"})
        print(f"   ✅ Task completion working, decayed {decayed_count} nodes")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Memory system error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration_points():
    """Test specific integration points in the code."""
    print(f"\n🔗 Testing integration points...")
    
    try:
        # Read the source files
        with open("/Users/nick.peterson/consultant-assistant/src/orchestrator/plan_and_execute.py", "r") as f:
            source = f.read()
        
        # Check for key integration points
        integration_points = [
            ("Memory context in execute_step", "relevant_memories = memory.retrieve_relevant"),
            ("Memory storage in execute_step", "memory_node_id = memory.store"),
            ("Memory context in plan_step", "planning_context = memory.retrieve_relevant"),
            ("Memory context in replan_step", "replan_context = memory.retrieve_relevant"),
            ("Task completion detection", "memory.mark_task_completed"),
            ("Auto-summary usage", "auto_summarize=True"),
            ("Thread ID handling", 'thread_id = state.get("thread_id"'),
            ("Memory imports", "from src.memory import"),
        ]
        
        all_present = True
        for description, pattern in integration_points:
            if pattern in source:
                print(f"   ✅ {description}")
            else:
                print(f"   ❌ Missing: {description}")
                all_present = False
        
        return all_present
        
    except Exception as e:
        print(f"   ❌ Source analysis error: {e}")
        return False


def test_memory_context_format():
    """Test that memory context is properly formatted."""
    print(f"\n📝 Testing memory context formatting...")
    
    try:
        from src.memory import get_thread_memory, ContextType
        
        # Create memory with realistic data
        memory = get_thread_memory("test-format")
        
        # Add some context
        account_node = memory.store(
            content={"id": "001TEST", "name": "Test Account", "industry": "Technology"},
            context_type=ContextType.DOMAIN_ENTITY,
            tags={"account", "technology"},
            auto_summarize=True
        )
        
        search_node = memory.store(
            content=[{"name": "Opp 1", "amount": 50000}, {"name": "Opp 2", "amount": 75000}],
            context_type=ContextType.SEARCH_RESULT,
            tags={"opportunities", "search"},
            auto_summarize=True
        )
        
        # Test retrieval
        context = memory.retrieve_relevant("account opportunities technology")
        
        print(f"   📊 Retrieved {len(context)} context nodes:")
        for node in context:
            print(f"     - {node.context_type.value}: {node.summary}")
            print(f"       Relevance: {node.current_relevance():.2f}, Age: {(node.created_at).isoformat()}")
        
        # Verify context quality
        has_account = any("Account" in node.summary for node in context)
        has_search = any(node.context_type == ContextType.SEARCH_RESULT for node in context)
        
        if has_account and has_search:
            print(f"   ✅ Memory context properly formatted and relevant")
            return True
        else:
            print(f"   ❌ Memory context missing key elements")
            return False
        
    except Exception as e:
        print(f"   ❌ Context formatting error: {e}")
        return False


def run_simple_phase2_tests():
    """Run simple Phase 2 verification tests."""
    print("🧠 PHASE 2 SIMPLE INTEGRATION VERIFICATION")
    print("=" * 50)
    print("Testing integration components without mocking")
    print()
    
    tests = [
        ("Memory System Imports", test_memory_imports),
        ("Memory Functionality", test_memory_system_functionality),
        ("Integration Points", test_integration_points),
        ("Memory Context Format", test_memory_context_format)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"{'='*15} {test_name} {'='*15}")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} FAILED: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    print(f"\n{'='*50}")
    print("📊 PHASE 2 VERIFICATION RESULTS:")
    print()
    
    passed = sum(1 for _, success in results if success)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {status}: {test_name}")
    
    print(f"\n🎯 Overall: {passed}/{len(tests)} verification tests passed")
    
    if passed == len(tests):
        print("🚀 PHASE 2 INTEGRATION VERIFIED!")
        print("✅ Memory system properly integrated into LangGraph")
        print("✅ All integration points present")
        print("✅ Auto-summary working")
        print("✅ Task completion detection implemented") 
        return True
    else:
        print("❌ Phase 2 integration verification failed")
        return False


if __name__ == "__main__":
    success = run_simple_phase2_tests()
    sys.exit(0 if success else 1)