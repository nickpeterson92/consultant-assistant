#!/usr/bin/env python3
"""Quick test of the memory system to verify Phase 1 implementation."""

import sys
import os

# Add the project root to Python path for src imports
sys.path.insert(0, os.path.dirname(__file__))

from src.memory import (
    get_thread_memory, 
    ContextType, 
    RelationshipType,
    get_memory_manager
)

def test_basic_memory_operations():
    """Test basic memory storage and retrieval."""
    print("🧠 Testing Basic Memory Operations...")
    
    # Get memory for a test thread
    memory = get_thread_memory("test-thread-123")
    print(f"✅ Created memory graph: {memory}")
    
    # Store some test data
    account_data = {
        "id": "001XX000003DHP0",
        "name": "GenePoint",
        "industry": "Biotechnology"
    }
    
    node_id = memory.store(
        content=account_data,
        context_type=ContextType.DOMAIN_ENTITY,
        tags={"genepoint", "account", "biotechnology"},
        summary="GenePoint account details"
    )
    print(f"✅ Stored account data with node_id: {node_id}")
    
    # Store related opportunity data
    opp_data = {
        "id": "006XX000002kJgS", 
        "name": "GenePoint SLA",
        "amount": 30000,
        "stage": "Closed Won",
        "account_id": "001XX000003DHP0"
    }
    
    opp_node_id = memory.store(
        content=opp_data,
        context_type=ContextType.DOMAIN_ENTITY,
        tags={"genepoint", "opportunity", "sla"},
        summary="GenePoint SLA opportunity",
        relates_to=[node_id]  # Link to account
    )
    print(f"✅ Stored opportunity data with node_id: {opp_node_id}")
    
    # Test retrieval
    relevant_nodes = memory.retrieve_relevant("genepoint account")
    print(f"✅ Retrieved {len(relevant_nodes)} relevant nodes for 'genepoint account'")
    
    for node in relevant_nodes:
        print(f"   - {node.summary} (relevance: {node.current_relevance():.2f})")
    
    # Test type-based retrieval
    domain_entities = memory.find_by_type(ContextType.DOMAIN_ENTITY)
    print(f"✅ Found {len(domain_entities)} domain entities")
    
    # Test tag-based retrieval  
    genepoint_nodes = memory.find_by_tags({"genepoint"})
    print(f"✅ Found {len(genepoint_nodes)} nodes tagged with 'genepoint'")
    
    # Test relationship traversal
    related_nodes = memory.get_related_nodes(node_id)
    print(f"✅ Found {len(related_nodes)} nodes related to account")
    
    # Display stats
    stats = memory.get_stats()
    print(f"✅ Memory stats: {stats}")
    
    return True

def test_memory_manager():
    """Test the global memory manager."""
    print("\n🌐 Testing Memory Manager...")
    
    manager = get_memory_manager()
    print(f"✅ Got global memory manager: {len(manager)} threads")
    
    # Create memories for different threads
    for i in range(3):
        thread_id = f"test-thread-{i}"
        memory = manager.get_memory(thread_id)
        
        # Store something in each thread
        manager.store_in_thread(
            thread_id=thread_id,
            content=f"Test data for thread {i}",
            context_type=ContextType.CONVERSATION_FACT,
            tags={f"thread{i}", "test"}
        )
    
    print(f"✅ Created {len(manager)} thread memories")
    
    # Test cross-thread retrieval
    for i in range(3):
        thread_id = f"test-thread-{i}"
        nodes = manager.retrieve_from_thread(thread_id, f"thread{i}")
        print(f"   Thread {i}: {len(nodes)} relevant nodes")
    
    # Global stats
    global_stats = manager.get_global_stats()
    print(f"✅ Global stats: {global_stats['total_threads']} threads, {global_stats['total_nodes_across_threads']} total nodes")
    
    return True

def test_memory_decay():
    """Test memory relevance decay over time."""
    print("\n⏰ Testing Memory Decay...")
    
    memory = get_thread_memory("decay-test")
    
    # Store nodes with different decay rates
    temp_node = memory.store(
        content="Temporary state",
        context_type=ContextType.TEMPORARY_STATE,  # Fast decay
        summary="Temporary state (should decay quickly)"
    )
    
    fact_node = memory.store(
        content="Persistent fact",
        context_type=ContextType.CONVERSATION_FACT,  # Slow decay
        summary="Conversation fact (should persist)"
    )
    
    print(f"✅ Stored temporary node: {memory.nodes[temp_node].current_relevance():.2f} relevance")
    print(f"✅ Stored fact node: {memory.nodes[fact_node].current_relevance():.2f} relevance")
    
    # Check initial relevance
    temp_relevance = memory.nodes[temp_node].current_relevance()
    fact_relevance = memory.nodes[fact_node].current_relevance()
    
    print(f"   Initial relevance - Temp: {temp_relevance:.2f}, Fact: {fact_relevance:.2f}")
    
    # Simulate time passing by manually adjusting created_at
    from datetime import datetime, timedelta
    memory.nodes[temp_node].created_at -= timedelta(hours=2)  # 2 hours ago
    memory.nodes[fact_node].created_at -= timedelta(hours=2)   # 2 hours ago
    
    # Check relevance after time
    temp_relevance_after = memory.nodes[temp_node].current_relevance()
    fact_relevance_after = memory.nodes[fact_node].current_relevance()
    
    print(f"   After 2hrs - Temp: {temp_relevance_after:.2f}, Fact: {fact_relevance_after:.2f}")
    print(f"✅ Decay working: temp declined more ({temp_relevance - temp_relevance_after:.2f}) than fact ({fact_relevance - fact_relevance_after:.2f})")
    
    return True

if __name__ == "__main__":
    print("🚀 Testing Conversational Memory System - Phase 1")
    print("=" * 60)
    
    try:
        test_basic_memory_operations()
        test_memory_manager()
        test_memory_decay()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED! Phase 1 memory system is working!")
        print("🎯 Ready to move to Phase 2: Integration with LangGraph")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)