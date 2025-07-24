#!/usr/bin/env python3
"""
MEGA ULTRA SUPER ROBUST COMPREHENSIVE Test Suite for Contextual Memory Framework
This test suite will absolutely TORTURE the memory system to ensure it ALWAYS retrieves RELEVANT context.
FIXED VERSION - Uses correct API
"""

import asyncio
import time
import random
import string
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
import traceback

# Add project root to path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.memory import get_thread_memory, ContextType
from src.memory import MemoryGraph, RelationshipType
from src.memory import MemoryNode
from src.utils.logging import get_smart_logger
from src.agents.shared.memory_writer import write_tool_result_to_memory
from src.utils.thread_utils import create_thread_id
from src.memory.core.memory_manager import get_memory_manager

logger = get_smart_logger("memory_test_mega")

class MemoryTortureTest:
    """Comprehensive test suite that pushes the memory framework to its limits."""
    
    def __init__(self):
        self.test_results = []
        self.thread_id = f"test-torture_{int(time.time())}"  # Updated to use standardized format
        self.memory = None
        
    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log test results."""
        result = {
            "test": test_name,
            "passed": passed,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
        if details:
            print(f"   Details: {details}")
    
    def generate_random_content(self, size: int = 100) -> Dict[str, Any]:
        """Generate random content to pollute the graph."""
        return {
            "id": ''.join(random.choices(string.ascii_letters + string.digits, k=16)),
            "data": ''.join(random.choices(string.ascii_letters + " \t\n", k=size)),
            "timestamp": time.time(),
            "random_field": random.random()
        }
    
    async def test_1_basic_storage_retrieval(self):
        """Test 1: Basic storage and retrieval accuracy."""
        print("\n🔥 TEST 1: Basic Storage & Retrieval")
        
        # Store specific entities - using tags instead of entity_id
        sf_account = {
            "Id": "001TESTACCOUNT",
            "Name": "Test Corp",
            "Industry": "Technology",
            "Revenue": 1000000,
            "entity_id": "001TESTACCOUNT",  # Store in content
            "entity_type": "Account"
        }
        
        node_id = self.memory.store(
            content=sf_account,
            context_type=ContextType.DOMAIN_ENTITY,
            tags={"account", "001TESTACCOUNT", "salesforce"},
            summary="Test Corp technology account with $1M revenue"
        )
        
        # Retrieve and verify
        results = self.memory.retrieve_relevant("Test Corp account", max_results=5)
        
        found = any(r.content.get("Id") == "001TESTACCOUNT" if isinstance(r.content, dict) else False for r in results)
        self.log_test("Basic storage and retrieval", found, 
                     f"Found {len(results)} results, target found: {found}")
        
        # Test relevance scoring
        if results and isinstance(results[0].content, dict) and results[0].content.get("Id") == "001TESTACCOUNT":
            self.log_test("Relevance scoring", True, "Most relevant result returned first")
        else:
            self.log_test("Relevance scoring", False, "Wrong result returned first")
    
    async def test_2_massive_pollution(self):
        """Test 2: Pollute the graph with tons of junk and ensure we still find relevant stuff."""
        print("\n🔥 TEST 2: Massive Graph Pollution Test")
        
        # Create fresh memory for this test
        self.memory = MemoryGraph("test-thread-pollution")
        
        # First, store some important data
        important_items = [
            {
                "content": {"Id": "CRITICAL001", "Name": "Critical Account", "Value": 5000000, "entity_id": "CRITICAL001"},
                "summary": "Critical account with 5M value needs attention 5000000",
                "tags": {"critical", "CRITICAL001", "account", "5000000", "5M", "value"}
            },
            {
                "content": {"Id": "JIRA-999", "Summary": "Critical bug in production", "entity_id": "JIRA-999"},
                "summary": "Production breaking bug needs immediate fix",
                "tags": {"critical", "JIRA-999", "bug", "production"}
            }
        ]
        
        for item in important_items:
            self.memory.store(
                content=item["content"],
                context_type=ContextType.DOMAIN_ENTITY,
                tags=item["tags"],
                summary=item["summary"]
            )
        
        # Now pollute with 500 POTENTIALLY RELEVANT nodes to make it challenging
        print("   💩 Polluting with 500 potentially relevant nodes...")
        
        # Create confusing similar data
        pollution_patterns = [
            # Similar account names
            {"content": {"Id": "ACC{i:04d}", "Name": "Critical Systems Inc #{i}", "Value": random.randint(100000, 900000)},
             "summary": "Important account with {value}M value needs review"},
            
            # Similar bug descriptions
            {"content": {"Id": "BUG-{i:03d}", "Summary": "Major issue in production system {i}"},
             "summary": "Production issue needs immediate attention"},
            
            # Variations on "critical"
            {"content": {"Id": "CRIT{i:03d}", "Name": "Crucial Account {i}", "Priority": "High"},
             "summary": "Crucial account with high priority status"},
            
            # Similar Jira tickets
            {"content": {"Id": "JIRA-{i:03d}", "Summary": "Critical system bug #{i}"},
             "summary": "System breaking bug requires fix"},
            
            # Accounts with similar values
            {"content": {"Id": "VAL{i:04d}", "Name": "Account #{i}", "Value": 4900000},
             "summary": "Account with 4.9M value needs attention"},
        ]
        
        for i in range(500):
            pattern = random.choice(pollution_patterns)
            polluted_data = {k: v.format(i=i) if isinstance(v, str) else v for k, v in pattern["content"].items()}
            
            # Format summary with appropriate values
            summary = pattern["summary"]
            if "{value}" in summary:
                value = polluted_data.get("Value", 0) / 1000000
                summary = summary.format(value=f"{value:.1f}")
            else:
                summary = summary.format(i=i)
            
            self.memory.store(
                content=polluted_data,
                context_type=ContextType.DOMAIN_ENTITY,
                tags={f"pollution{i}", "similar", "confusing"},
                summary=summary
            )
        
        # Try MANY different queries to find our important items
        print("\n   🔍 Testing multiple query scenarios...")
        
        query_scenarios = [
            # Bug queries
            ("critical production bug", "JIRA-999", "basic bug query"),
            ("JIRA-999", "JIRA-999", "exact ID search"),
            ("Production breaking bug needs immediate fix", "JIRA-999", "exact summary match"),
            ("breaking bug production", "JIRA-999", "keywords out of order"),
            ("jira 999 critical", "JIRA-999", "mixed case and spacing"),
            
            # Account queries  
            ("Critical Account 5M value", "CRITICAL001", "basic account query"),
            ("CRITICAL001", "CRITICAL001", "exact ID search"),
            ("account 5M value needs attention", "CRITICAL001", "partial description"),
            ("5000000 value account", "CRITICAL001", "numeric value search"),
            ("Critical account with 5M value needs attention", "CRITICAL001", "exact summary"),
        ]
        
        results_summary = []
        for query, expected_id, description in query_scenarios:
            results = self.memory.retrieve_relevant(query, max_results=10)
            found = any(
                isinstance(r.content, dict) and (r.content.get("entity_id") == expected_id or r.content.get("Id") == expected_id)
                for r in results
            )
            
            # Check position if found
            position = -1
            if found:
                for i, r in enumerate(results):
                    if isinstance(r.content, dict) and (r.content.get("entity_id") == expected_id or r.content.get("Id") == expected_id):
                        position = i + 1
                        break
            
            results_summary.append({
                "query": query,
                "found": found,
                "position": position,
                "description": description
            })
            
            status = "✅" if found else "❌"
            pos_info = f" (position {position})" if position > 0 else ""
            print(f"      {status} {description}: '{query}'{pos_info}")
            
            # Debug failing queries
            if not found and query == "Critical Account 5M value":
                print(f"         DEBUG: Looking for {expected_id}")
                print(f"         Total results: {len(results)}")
                for i, r in enumerate(results[:3]):
                    if isinstance(r.content, dict):
                        print(f"         {i+1}. ID: {r.content.get('Id', 'Unknown')}, entity_id: {r.content.get('entity_id', 'None')}")
        
        # Calculate success metrics
        total_queries = len(query_scenarios)
        successful = sum(1 for r in results_summary if r["found"])
        top_3_results = sum(1 for r in results_summary if 0 < r["position"] <= 3)
        
        all_found = successful == total_queries
        
        self.log_test("Find critical items in polluted graph", 
                     all_found,
                     f"Found {successful}/{total_queries} items, {top_3_results} in top 3 results, Graph size: {len(self.memory.node_manager.nodes)}")
    
    async def test_3_time_decay_relevance(self):
        """Test 3: Test time decay - old stuff should rank lower."""
        print("\n🔥 TEST 3: Time Decay & Recency Testing")
        
        # Clear memory from previous tests to ensure clean state
        self.memory = MemoryGraph("test-thread")
        
        # Store old data (simulate 10 hours ago)
        old_time = datetime.now() - timedelta(hours=10)
        
        # First store it normally to get it indexed
        old_node_id = self.memory.store(
            content={"Id": "OLD001", "Name": "Old Account", "entity_id": "OLD001"},
            context_type=ContextType.DOMAIN_ENTITY,
            summary="Old account data from 10 hours ago",
            tags={"OLD001", "account", "old", "data"}
        )
        
        # Then update its timestamp by accessing the node directly
        if old_node_id in self.memory.node_manager.nodes:
            self.memory.node_manager.nodes[old_node_id].created_at = old_time
            self.memory.node_manager.nodes[old_node_id].last_accessed = old_time
        
        # Store recent data
        recent_node_id = self.memory.store(
            content={"Id": "NEW001", "Name": "New Account", "entity_id": "NEW001"},
            context_type=ContextType.DOMAIN_ENTITY,
            summary="New account data just created",
            tags={"NEW001", "account", "new", "data"}
        )
        
        # Add some more nodes to ensure we have enough results
        for i in range(5):
            self.memory.store(
                content={"Id": f"FILLER{i}", "Name": f"Filler Account {i}"},
                context_type=ContextType.DOMAIN_ENTITY,
                summary=f"Filler account {i} with some data",
                tags={f"FILLER{i}", "account", "filler", "data"}
            )
        
        # Search for "account data" - request more results to ensure old item is included
        results = self.memory.retrieve_relevant("account data", max_results=20)
        
        # Debug output
        print(f"   Found {len(results)} results for 'account data'")
        for i, r in enumerate(results[:5]):  # Show top 5
            if isinstance(r.content, dict):
                entity_id = r.content.get("entity_id", r.content.get("Id", "Unknown"))
                age_hours = (datetime.now() - r.created_at).total_seconds() / 3600
                print(f"   Position {i}: {entity_id} (age: {age_hours:.1f}h)")
        
        # Find positions (check both entity_id and Id fields)
        old_pos = next((i for i, r in enumerate(results) 
                       if isinstance(r.content, dict) and (r.content.get("entity_id") == "OLD001" or r.content.get("Id") == "OLD001")), -1)
        new_pos = next((i for i, r in enumerate(results) 
                       if isinstance(r.content, dict) and (r.content.get("entity_id") == "NEW001" or r.content.get("Id") == "NEW001")), -1)
        
        print(f"   Old item position: {old_pos}, New item position: {new_pos}")
        
        # The test should verify that both old and new items are found,
        # and that new items rank higher (which is correct behavior)
        both_found = new_pos != -1 and old_pos != -1
        new_ranks_higher = new_pos < old_pos if both_found else True
        
        self.log_test("Time decay affects ranking",
                     both_found and new_ranks_higher,
                     f"New position: {new_pos}, Old position: {old_pos}")
    
    async def test_4_relationship_navigation(self):
        """Test 4: Complex relationship chains and navigation."""
        print("\n🔥 TEST 4: Complex Relationship Navigation")
        
        # Create a complex chain: Account -> Contact -> Case -> Task
        nodes = []
        
        # Account
        account_id = self.memory.store(
            content={"Id": "ACC001", "Name": "Chain Test Corp", "entity_id": "ACC001"},
            context_type=ContextType.DOMAIN_ENTITY,
            tags={"ACC001", "account", "chain"},
            summary="Account at start of relationship chain"
        )
        nodes.append(account_id)
        
        # Contact linked to Account
        contact_id = self.memory.store(
            content={"Id": "CON001", "Name": "John Chain", "AccountId": "ACC001", "entity_id": "CON001"},
            context_type=ContextType.DOMAIN_ENTITY,
            tags={"CON001", "contact", "chain"},
            summary="Contact linked to Chain Test Corp",
            relates_to=[account_id]
        )
        nodes.append(contact_id)
        
        # Case linked to Contact
        case_id = self.memory.store(
            content={"Id": "CASE001", "Subject": "Chain Issue", "ContactId": "CON001", "entity_id": "CASE001"},
            context_type=ContextType.DOMAIN_ENTITY,
            tags={"CASE001", "case", "chain"},
            summary="Support case for John Chain",
            relates_to=[contact_id]
        )
        nodes.append(case_id)
        
        # Task linked to Case
        task_id = self.memory.store(
            content={"Id": "TASK001", "Subject": "Resolve Chain Issue", "WhatId": "CASE001", "entity_id": "TASK001"},
            context_type=ContextType.DOMAIN_ENTITY,
            tags={"TASK001", "task", "chain"},
            summary="Task to resolve chain issue",
            relates_to=[case_id]
        )
        nodes.append(task_id)
        
        # Now search for "Chain Test Corp" and see if we get related items
        # First get the account
        results = self.memory.retrieve_relevant("Chain Test Corp", max_results=1)
        
        # Then get related nodes through graph traversal
        all_related = set()
        if results and hasattr(self.memory, 'get_related_nodes'):
            # Get directly related nodes
            for node in results:
                related = self.memory.get_related_nodes(node.node_id, max_distance=3)
                all_related.update(r.node_id for r in related)
        
        # Combine original results with related
        all_nodes = []
        for node_id in [r.node_id for r in results] + list(all_related):
            node = self.memory.node_manager.get_node(node_id)
            if node:
                all_nodes.append(node)
        
        results = all_nodes
        
        found_ids = {r.content.get("entity_id") if isinstance(r.content, dict) else None for r in results}
        expected_ids = {"ACC001", "CON001", "CASE001", "TASK001"}
        all_found = len(found_ids & expected_ids) == 4
        
        self.log_test("Relationship chain navigation",
                     all_found,
                     f"Found {len(found_ids & expected_ids)} of 4 related entities")
    
    async def test_5_concurrent_access_stress(self):
        """Test 5: Concurrent access and race conditions."""
        print("\n🔥 TEST 5: Concurrent Access Stress Test")
        
        async def concurrent_writer(writer_id: int):
            """Simulate concurrent writes."""
            for i in range(50):
                self.memory.store(
                    content={"writer": writer_id, "seq": i},
                    context_type=ContextType.CONVERSATION_FACT,
                    summary=f"Writer {writer_id} message {i}"
                )
                await asyncio.sleep(0.001)  # Small delay
        
        async def concurrent_reader(reader_id: int):
            """Simulate concurrent reads."""
            results = []
            for i in range(20):
                res = self.memory.retrieve_relevant(f"Writer {reader_id % 5}", max_results=5)
                results.append(len(res))
                await asyncio.sleep(0.005)
            return results
        
        # Start 5 writers and 3 readers concurrently
        start_nodes = len(self.memory.node_manager.nodes)
        
        tasks = []
        for i in range(5):
            tasks.append(concurrent_writer(i))
        for i in range(3):
            tasks.append(concurrent_reader(i))
        
        try:
            await asyncio.gather(*tasks)
            end_nodes = len(self.memory.node_manager.nodes)
            nodes_added = end_nodes - start_nodes
            
            self.log_test("Concurrent access handling",
                         nodes_added == 250,  # 5 writers * 50 messages
                         f"Expected 250 nodes added, got {nodes_added}")
        except Exception as e:
            self.log_test("Concurrent access handling", False, str(e))
    
    async def test_6_semantic_search_accuracy(self):
        """Test 6: Semantic search with synonyms and related concepts."""
        print("\n🔥 TEST 6: Semantic Search Accuracy")
        
        # Create fresh memory for this test
        self.memory = MemoryGraph("test-thread-semantic")
        
        # Store entities with related but different terms
        test_entities = [
            {
                "content": {"Id": "SEM001", "Name": "Global Revenue Corporation", "entity_id": "SEM001"},
                "summary": "Company focused on worldwide sales and income",
                "tags": {"SEM001", "revenue", "global", "sales"}
            },
            {
                "content": {"Id": "SEM002", "Name": "TechStart Inc", "entity_id": "SEM002"},
                "summary": "Startup technology company in Silicon Valley",
                "tags": {"SEM002", "startup", "technology", "silicon-valley"}
            },
            {
                "content": {"Id": "SEM003", "Name": "Customer Success Ltd", "entity_id": "SEM003"},
                "summary": "Firm specializing in client satisfaction and support",
                "tags": {"SEM003", "customer", "support", "client"}
            }
        ]
        
        for entity in test_entities:
            self.memory.store(
                content=entity["content"],
                context_type=ContextType.DOMAIN_ENTITY,
                summary=entity["summary"],
                tags=entity["tags"]
            )
        
        # Test semantic searches
        searches = [
            ("international earnings", "SEM001"),  # Should find "worldwide sales"
            ("tech startup", "SEM002"),  # Should find technology company
            ("customer support", "SEM003"),  # Should find client satisfaction
        ]
        
        all_found = True
        for query, expected_id in searches:
            results = self.memory.retrieve_relevant(query, max_results=3)
            found = any(isinstance(r.content, dict) and r.content.get("entity_id") == expected_id for r in results)
            if not found:
                all_found = False
                print(f"   ❌ Failed to find {expected_id} for query '{query}'")
        
        self.log_test("Semantic search accuracy", all_found,
                     f"Semantic search working correctly")
    
    async def test_7_memory_cleanup_preservation(self):
        """Test 7: Ensure cleanup doesn't remove important recent items."""
        print("\n🔥 TEST 7: Memory Cleanup Preservation")
        
        # Store important recent items
        important_ids = []
        for i in range(5):
            node_id = self.memory.store(
                content={"Id": f"IMPORTANT{i}", "critical": True, "entity_id": f"IMPORTANT{i}"},
                context_type=ContextType.DOMAIN_ENTITY,
                summary=f"Critical entity {i} that must be preserved",
                tags={f"IMPORTANT{i}", "critical", "preserve"}
            )
            important_ids.append(node_id)
        
        # Store old junk (simulate 25 hours old)
        old_time = datetime.now() - timedelta(hours=25)
        old_node_ids = []
        for i in range(20):
            # Store normally first
            node_id = self.memory.store(
                content={"junk": i},
                context_type=ContextType.SEARCH_RESULT,
                summary=f"Old junk {i}"
            )
            old_node_ids.append(node_id)
            # Then update timestamp
            if node_id in self.memory.node_manager.nodes:
                self.memory.node_manager.nodes[node_id].created_at = old_time
                self.memory.node_manager.nodes[node_id].last_accessed = old_time
        
        # Run cleanup
        nodes_before = len(self.memory.node_manager.nodes)
        removed = self.memory.cleanup_stale_nodes(max_age_hours=24)
        nodes_after = len(self.memory.node_manager.nodes)
        
        # Check if important items survived
        important_survived = all(node_id in self.memory.node_manager.nodes for node_id in important_ids)
        
        self.log_test("Memory cleanup preservation",
                     important_survived and removed >= 15,
                     f"Removed {removed} old nodes, important items preserved: {important_survived}")
    
    async def test_8_cross_system_entity_linking(self):
        """Test 8: Test entity linking across different systems (SF, Jira, ServiceNow)."""
        print("\n🔥 TEST 8: Cross-System Entity Linking")
        
        # Create linked entities across systems
        sf_account_id = self.memory.store(
            content={"Id": "001CROSS", "Name": "CrossSystem Corp", "entity_id": "001CROSS", "system": "salesforce"},
            context_type=ContextType.DOMAIN_ENTITY,
            tags={"001CROSS", "account", "salesforce", "crosssystem"},
            summary="Salesforce account for CrossSystem Corp"
        )
        
        jira_project_id = self.memory.store(
            content={"key": "CROSS-1", "name": "CrossSystem Corp Project", "entity_id": "CROSS-1", "system": "jira"},
            context_type=ContextType.DOMAIN_ENTITY,
            tags={"CROSS-1", "project", "jira", "crosssystem"},
            summary="Jira project for CrossSystem Corp",
            relates_to=[sf_account_id]
        )
        
        sn_incident_id = self.memory.store(
            content={"number": "INC0099999", "short_description": "CrossSystem Corp outage", "entity_id": "INC0099999", "system": "servicenow"},
            context_type=ContextType.DOMAIN_ENTITY,
            tags={"INC0099999", "incident", "servicenow", "crosssystem"},
            summary="ServiceNow incident for CrossSystem Corp",
            relates_to=[sf_account_id, jira_project_id]
        )
        
        # Search for CrossSystem and verify we get all related entities
        # The refactored version already uses graph intelligence in retrieve_relevant
        results = self.memory.retrieve_relevant("CrossSystem", max_results=10)
        found_entities = {r.content.get("entity_id") if isinstance(r.content, dict) else None for r in results}
        
        expected = {"001CROSS", "CROSS-1", "INC0099999"}
        all_systems_found = len(found_entities & expected) == 3
        
        self.log_test("Cross-system entity linking",
                     all_systems_found,
                     f"Found entities from {len(found_entities & expected)} of 3 systems")
    
    async def test_9_retrieval_with_context_window(self):
        """Test 9: Test retrieval with different time windows and context limits."""
        print("\n🔥 TEST 9: Context Window Retrieval")
        
        # Create events at different times
        now = datetime.now()
        time_events = [
            (now - timedelta(minutes=5), "5min", "Event 5 minutes ago"),
            (now - timedelta(hours=1), "1hr", "Event 1 hour ago"),
            (now - timedelta(hours=6), "6hr", "Event 6 hours ago"),
            (now - timedelta(hours=12), "12hr", "Event 12 hours ago"),
            (now - timedelta(hours=24), "24hr", "Event 24 hours ago"),
        ]
        
        for event_time, event_id, summary in time_events:
            # First store it normally to get it indexed
            node_id = self.memory.store(
                content={"id": event_id, "time": event_time.isoformat(), "entity_id": event_id},
                context_type=ContextType.CONVERSATION_FACT,
                summary=summary,
                tags={event_id, "event", "timed"}
            )
            # Then update its timestamp
            if node_id in self.memory.node_manager.nodes:
                self.memory.node_manager.nodes[node_id].created_at = event_time
                self.memory.node_manager.nodes[node_id].last_accessed = event_time
        
        # Test different time windows
        windows = [
            (0.5, ["5min"]),  # 30 minutes - only most recent
            (4, ["5min", "1hr"]),    # 4 hours
            (8, ["5min", "1hr", "6hr"]),  # 8 hours
            (20, ["5min", "1hr", "6hr", "12hr"]),  # 20 hours
        ]
        
        all_correct = True
        for max_hours, expected_ids in windows:
            results = self.memory.retrieve_relevant("Event", max_age_hours=max_hours, max_results=10)
            found_ids = {r.content.get("entity_id") if isinstance(r.content, dict) else None for r in results}
            found_ids.discard(None)
            expected_set = set(expected_ids)
            
            # Check if we got the expected results (allowing for some flexibility)
            if not expected_set.issubset(found_ids):
                all_correct = False
                print(f"   ❌ Window {max_hours}h: Expected {expected_set} to be in {found_ids}")
        
        self.log_test("Time window retrieval accuracy", all_correct,
                     "Time windows filter results correctly")
    
    async def test_10_intelligent_algorithms(self):
        """Test 10: Test PageRank, clustering, and bridge detection algorithms."""
        print("\n🔥 TEST 10: Intelligent Graph Algorithms")
        
        # Create a complex graph structure
        # Hub node (should have high PageRank)
        hub_id = self.memory.store(
            content={"Id": "HUB001", "Name": "Central Hub Entity", "entity_id": "HUB001"},
            context_type=ContextType.DOMAIN_ENTITY,
            tags={"HUB001", "hub", "central"},
            summary="Central hub connected to many entities"
        )
        
        # Create spokes connected to hub
        spoke_ids = []
        for i in range(10):
            spoke_id = self.memory.store(
                content={"Id": f"SPOKE{i}", "Name": f"Spoke Entity {i}", "entity_id": f"SPOKE{i}"},
                context_type=ContextType.DOMAIN_ENTITY,
                tags={f"SPOKE{i}", "spoke", "connected"},
                summary=f"Spoke entity {i} connected to hub",
                relates_to=[hub_id]
            )
            spoke_ids.append(spoke_id)
        
        # Create two separate clusters
        cluster1_ids = []
        cluster1_root = self.memory.store(
            content={"Id": "CLUSTER1", "Name": "Cluster 1 Root", "entity_id": "CLUSTER1"},
            context_type=ContextType.DOMAIN_ENTITY,
            tags={"CLUSTER1", "cluster", "root"},
            summary="Root of cluster 1"
        )
        cluster1_ids.append(cluster1_root)
        
        for i in range(5):
            node_id = self.memory.store(
                content={"Id": f"C1NODE{i}", "entity_id": f"C1NODE{i}"},
                context_type=ContextType.DOMAIN_ENTITY,
                tags={f"C1NODE{i}", "cluster1", "node"},
                summary=f"Cluster 1 node {i}",
                relates_to=[cluster1_root] if i == 0 else [cluster1_ids[-1]]
            )
            cluster1_ids.append(node_id)
        
        # Create second cluster
        cluster2_ids = []
        cluster2_root = self.memory.store(
            content={"Id": "CLUSTER2", "Name": "Cluster 2 Root", "entity_id": "CLUSTER2"},
            context_type=ContextType.DOMAIN_ENTITY,
            tags={"CLUSTER2", "cluster", "root"},
            summary="Root of cluster 2"
        )
        cluster2_ids.append(cluster2_root)
        
        for i in range(5):
            node_id = self.memory.store(
                content={"Id": f"C2NODE{i}", "entity_id": f"C2NODE{i}"},
                context_type=ContextType.DOMAIN_ENTITY,
                tags={f"C2NODE{i}", "cluster2", "node"},
                summary=f"Cluster 2 node {i}",
                relates_to=[cluster2_root] if i == 0 else [cluster2_ids[-1]]
            )
            cluster2_ids.append(node_id)
        
        # Bridge between clusters (should be detected as bridge)
        bridge_id = self.memory.store(
            content={"Id": "BRIDGE001", "Name": "Bridge Entity", "entity_id": "BRIDGE001"},
            context_type=ContextType.DOMAIN_ENTITY,
            tags={"BRIDGE001", "bridge", "connector"},
            summary="Bridge connecting two clusters",
            relates_to=[cluster1_ids[2], cluster2_ids[2]]
        )
        
        # Also create reverse connections to make bridge more central
        self.memory.add_relationship(cluster1_ids[2], bridge_id, RelationshipType.RELATES_TO)
        self.memory.add_relationship(cluster2_ids[2], bridge_id, RelationshipType.RELATES_TO)
        
        # Test PageRank
        important_nodes = self.memory.find_important_memories(top_n=3)
        hub_is_important = any(
            isinstance(n.content, dict) and n.content.get("entity_id") == "HUB001" 
            for n in important_nodes
        )
        
        # Test clustering
        clusters = self.memory.find_memory_clusters()
        has_multiple_clusters = len(clusters) >= 2
        
        # Test bridge detection
        bridges = self.memory.find_bridge_memories(top_n=5)
        bridge_found = any(
            isinstance(n.content, dict) and n.content.get("entity_id") == "BRIDGE001" 
            for n in bridges
        )
        
        self.log_test("Graph algorithms (PageRank, clustering, bridges)",
                     hub_is_important and has_multiple_clusters and bridge_found,
                     f"Hub important: {hub_is_important}, Multiple clusters: {has_multiple_clusters}, Bridge found: {bridge_found}")
    
    async def test_11_extreme_scale(self):
        """Test 11: Extreme scale test - 10,000 nodes."""
        print("\n🔥 TEST 11: EXTREME SCALE TEST (10,000 nodes)")
        print("   ⚠️  This will take a moment...")
        
        # Store a few needles in the haystack
        needles = []
        for i in range(5):
            needle_id = f"NEEDLE{i}"
            node_id = self.memory.store(
                content={"Id": needle_id, "special": True, "keyword": "findmeifyoucan", "entity_id": needle_id},
                context_type=ContextType.DOMAIN_ENTITY,
                tags={needle_id, "needle", "special", "findmeifyoucan"},
                summary=f"Special needle {i} with unique keyword findmeifyoucan"
            )
            needles.append(needle_id)
        
        # Create 10,000 nodes
        start_time = time.time()
        batch_size = 1000
        for batch in range(10):
            print(f"   Creating batch {batch + 1}/10...")
            for i in range(batch_size):
                node_num = batch * batch_size + i
                self.memory.store(
                    content={"id": f"SCALE{node_num}", "data": self.generate_random_content(50)},
                    context_type=ContextType.SEARCH_RESULT,
                    summary=f"Scale test node {node_num}"
                )
        
        creation_time = time.time() - start_time
        
        # Now try to find our needles
        search_start = time.time()
        results = self.memory.retrieve_relevant("findmeifyoucan special needle", max_results=10)
        search_time = time.time() - search_start
        
        found_needles = {
            r.content.get("entity_id") 
            for r in results 
            if isinstance(r.content, dict) and r.content.get("entity_id", "").startswith("NEEDLE")
        }
        
        self.log_test("Extreme scale performance",
                     len(found_needles) >= 3 and search_time < 5.0,
                     f"Created 10k nodes in {creation_time:.2f}s, found {len(found_needles)}/5 needles in {search_time:.2f}s")
    
    async def test_12_false_positive_prevention(self):
        """Test 12: HAMMER false positive prevention - ensure NO irrelevant results."""
        print("\n🔥 TEST 12: False Positive Prevention - BRUTAL IRRELEVANCE TEST")
        
        # Store some VERY SPECIFIC items
        target_items = [
            {
                "content": {"Id": "TARGET001", "Name": "Acme Corporation", "Industry": "Manufacturing"},
                "summary": "Acme Corporation manufacturing client in Detroit",
                "tags": {"acme", "manufacturing", "detroit", "TARGET001"}
            },
            {
                "content": {"Id": "TARGET002", "Summary": "Database migration project", "Status": "In Progress"},
                "summary": "Database migration project for MySQL to PostgreSQL",
                "tags": {"database", "migration", "mysql", "postgresql", "TARGET002"}
            },
            {
                "content": {"Id": "TARGET003", "Error": "Connection timeout", "Service": "API Gateway"},
                "summary": "API Gateway connection timeout error at 2:30 PM",
                "tags": {"error", "timeout", "api", "gateway", "TARGET003"}
            }
        ]
        
        for item in target_items:
            self.memory.store(
                content=item["content"],
                context_type=ContextType.DOMAIN_ENTITY,
                tags=item["tags"],
                summary=item["summary"]
            )
        
        # Now add TONS of completely unrelated data
        print("   💣 Adding 1000 pieces of COMPLETELY UNRELATED data...")
        unrelated_topics = [
            # Food/Restaurant data
            {"summary": "Pizza delivery restaurant on Main Street", "tags": {"pizza", "food", "restaurant"}},
            {"summary": "Chinese takeout menu prices updated", "tags": {"chinese", "food", "menu"}},
            {"summary": "Coffee shop wifi password changed", "tags": {"coffee", "wifi", "shop"}},
            
            # Sports data
            {"summary": "Basketball game score Lakers vs Celtics", "tags": {"basketball", "sports", "lakers"}},
            {"summary": "Football season schedule released", "tags": {"football", "schedule", "sports"}},
            {"summary": "Tennis tournament brackets updated", "tags": {"tennis", "tournament", "sports"}},
            
            # Weather data
            {"summary": "Weather forecast sunny 75 degrees", "tags": {"weather", "forecast", "sunny"}},
            {"summary": "Storm warning for coastal areas", "tags": {"storm", "warning", "weather"}},
            {"summary": "Snow expected in mountain regions", "tags": {"snow", "weather", "mountain"}},
            
            # Random technical terms that should NOT match
            {"summary": "Python tutorial for beginners", "tags": {"python", "tutorial", "programming"}},
            {"summary": "JavaScript framework comparison", "tags": {"javascript", "framework", "web"}},
            {"summary": "Linux kernel update available", "tags": {"linux", "kernel", "update"}},
            
            # Similar words but WRONG context
            {"summary": "Manufacturing defect in toys recalled", "tags": {"manufacturing", "toys", "recall"}},
            {"summary": "Detroit Lions win playoff game", "tags": {"detroit", "lions", "football"}},
            {"summary": "Timeout during cooking recipe", "tags": {"timeout", "cooking", "recipe"}},
            {"summary": "Migration patterns of birds studied", "tags": {"migration", "birds", "study"}},
        ]
        
        # Generate 1000 unrelated items
        for i in range(1000):
            template = random.choice(unrelated_topics)
            self.memory.store(
                content={"id": f"UNRELATED{i:04d}", "data": f"Irrelevant data {i}"},
                context_type=ContextType.SEARCH_RESULT,
                tags=template["tags"],
                summary=f"{template['summary']} - instance {i}"
            )
        
        # Now run VERY SPECIFIC queries and ensure NO false positives
        print("\n   🎯 Testing for false positives with specific queries...")
        
        test_queries = [
            {
                "query": "Acme Corporation Detroit manufacturing",
                "expected_id": "TARGET001",
                "max_acceptable_results": 1,  # ONLY the exact match
                "description": "Very specific company query"
            },
            {
                "query": "Database migration MySQL PostgreSQL project",
                "expected_id": "TARGET002",
                "max_acceptable_results": 1,
                "description": "Specific technical project"
            },
            {
                "query": "API Gateway connection timeout error",
                "expected_id": "TARGET003",
                "max_acceptable_results": 1,
                "description": "Specific error query"
            },
            {
                "query": "Manufacturing in Detroit",  # More general
                "expected_id": "TARGET001",
                "max_acceptable_results": 3,  # Allow a few related
                "description": "Partial match query"
            },
            {
                "query": "Completely unrelated nonsense query xyz123",
                "expected_id": None,
                "max_acceptable_results": 0,  # Should return NOTHING
                "description": "Nonsense query should return empty"
            }
        ]
        
        all_tests_passed = True
        for test in test_queries:
            results = self.memory.retrieve_relevant(test["query"], max_results=10)
            
            # Check if we found the expected item (if any)
            found_expected = False
            if test["expected_id"]:
                found_expected = any(
                    isinstance(r.content, dict) and r.content.get("Id") == test["expected_id"]
                    for r in results
                )
            
            # Check for false positives
            false_positives = []
            for r in results:
                if isinstance(r.content, dict):
                    item_id = r.content.get("Id") or r.content.get("id")
                    if item_id and item_id.startswith("UNRELATED"):
                        false_positives.append(item_id)
            
            # Determine if test passed
            passed = (
                (not test["expected_id"] or found_expected) and  # Found expected or none expected
                len(results) <= test["max_acceptable_results"] and  # Not too many results
                len(false_positives) == 0  # NO false positives
            )
            
            if not passed:
                all_tests_passed = False
            
            status = "✅" if passed else "❌"
            print(f"      {status} {test['description']}: '{test['query']}'")
            print(f"         Expected: {test['expected_id']}, Found: {found_expected}, "
                  f"Results: {len(results)}, False positives: {len(false_positives)}")
            
            if false_positives:
                print(f"         ⚠️  FALSE POSITIVES: {false_positives[:5]}...")
        
        # Calculate precision metrics
        print("\n   📊 Precision Analysis:")
        print(f"      Total nodes in graph: {len(self.memory.node_manager.nodes)}")
        print(f"      Target items: 3")
        print(f"      Unrelated items: 1000")
        
        self.log_test("False positive prevention",
                     all_tests_passed,
                     "All queries returned relevant results with NO false positives" if all_tests_passed
                     else "Some queries returned irrelevant results")
    
    async def test_13_entity_type_filtering(self):
        """Test 13: Entity type filtering and mixed queries."""
        print("\n🔥 TEST 13: Entity Type Filtering")
        
        # Create diverse entity types
        entity_types = ["Account", "Contact", "JiraIssue", "ServiceNowIncident", "Task", "Opportunity"]
        for etype in entity_types:
            for i in range(5):
                self.memory.store(
                    content={"Id": f"{etype}_{i}", "type": etype, "entity_type": etype, "entity_id": f"{etype}_{i}"},
                    context_type=ContextType.DOMAIN_ENTITY,
                    tags={f"{etype}_{i}", etype.lower(), "test"},
                    summary=f"Test {etype} number {i}"
                )
        
        # Search and verify we get diverse results
        results = self.memory.retrieve_relevant("Test", max_results=30)
        found_types = {
            r.content.get("entity_type") 
            for r in results 
            if isinstance(r.content, dict) and r.content.get("entity_type")
        }
        
        diversity = len(found_types)
        self.log_test("Entity type diversity in results",
                     diversity >= 4,
                     f"Found {diversity} different entity types in results")
    
    async def test_14_real_conversation_flow(self):
        """Test 14: Real-world conversation flow with context building."""
        print("\n🔥 TEST 14: Real-World Conversation Flow")
        
        # Create fresh memory for this test
        self.memory = MemoryGraph("test-thread-conversation")
        
        # Simulate a real conversation about a customer issue
        conversation_flow = [
            # Initial customer complaint
            {
                "content": {"Id": "MSG001", "type": "user_message", "entity_id": "MSG001"},
                "summary": "Customer reported that their Salesforce integration is failing with timeout errors",
                "tags": {"salesforce", "integration", "timeout", "error", "customer_issue"},
                "context_type": ContextType.USER_SELECTION
            },
            # Support agent investigation
            {
                "content": {"Id": "MSG002", "type": "agent_action", "entity_id": "MSG002"},
                "summary": "Checked logs and found API rate limit exceeded for customer's instance",
                "tags": {"api", "rate_limit", "logs", "investigation"},
                "context_type": ContextType.SEARCH_RESULT,
                "relates_to": ["MSG001"]
            },
            # Found related ticket
            {
                "content": {"Id": "INC001234", "type": "incident", "entity_id": "INC001234", "customer": "Acme Corp"},
                "summary": "Previous incident where Acme Corp had similar API timeout issues last month",
                "tags": {"incident", "acme_corp", "api", "timeout", "history"},
                "context_type": ContextType.DOMAIN_ENTITY,
                "relates_to": ["MSG002"]
            },
            # Solution found
            {
                "content": {"Id": "KB00567", "type": "knowledge_article", "entity_id": "KB00567"},
                "summary": "Knowledge article: How to increase Salesforce API rate limits and implement retry logic",
                "tags": {"knowledge", "solution", "api", "rate_limit", "salesforce"},
                "context_type": ContextType.TOOL_OUTPUT,
                "relates_to": ["MSG002", "INC001234"]
            },
            # Implementation plan
            {
                "content": {"Id": "PLAN001", "type": "action_plan", "entity_id": "PLAN001"},
                "summary": "Plan to implement exponential backoff and request API limit increase for Acme Corp",
                "tags": {"plan", "implementation", "backoff", "acme_corp"},
                "context_type": ContextType.COMPLETED_ACTION,
                "depends_on": ["KB00567"]
            }
        ]
        
        # Store the conversation flow
        node_ids = {}
        for i, msg in enumerate(conversation_flow):
            # Handle relationships
            relates_to_ids = []
            if "relates_to" in msg:
                for ref in msg["relates_to"]:
                    if ref in node_ids:
                        relates_to_ids.append(node_ids[ref])
            
            depends_on_ids = []
            if "depends_on" in msg:
                for ref in msg["depends_on"]:
                    if ref in node_ids:
                        depends_on_ids.append(node_ids[ref])
            
            node_id = self.memory.store(
                content=msg["content"],
                context_type=msg["context_type"],
                summary=msg["summary"],
                tags=msg["tags"],
                relates_to=relates_to_ids if relates_to_ids else None,
                depends_on=depends_on_ids if depends_on_ids else None
            )
            node_ids[msg["content"]["Id"]] = node_id
        
        # Test retrieval scenarios
        test_scenarios = [
            ("Salesforce timeout", ["MSG001", "INC001234", "KB00567"], "Should find original issue and solution"),
            ("Acme Corp API issues", ["INC001234", "PLAN001"], "Should find customer-specific history"),
            ("rate limit solution", ["MSG002", "KB00567"], "Should find investigation and solution"),
            ("previous incident timeout", ["INC001234"], "Should find historical incident"),
            ("implement backoff", ["KB00567", "PLAN001"], "Should find KB article and plan")
        ]
        
        all_passed = True
        for query, expected_ids, description in test_scenarios:
            results = self.memory.retrieve_relevant(query, max_results=5)
            found_ids = {
                r.content.get("entity_id", r.content.get("Id"))
                for r in results
                if isinstance(r.content, dict)
            }
            
            # Check if we found at least one expected ID
            found_expected = any(eid in found_ids for eid in expected_ids)
            if not found_expected:
                all_passed = False
                print(f"   ❌ Query '{query}': Expected one of {expected_ids}, found {found_ids}")
        
        self.log_test("Real conversation flow retrieval", all_passed,
                     "Conversation context retrieved correctly")
    
    async def test_15_technical_troubleshooting(self):
        """Test 15: Technical troubleshooting scenario with step-by-step debugging."""
        print("\n🔥 TEST 15: Technical Troubleshooting Workflow")
        
        # Create fresh memory
        self.memory = MemoryGraph("test-thread-troubleshooting")
        
        # Simulate debugging a production issue
        troubleshooting_steps = [
            {
                "content": {"Id": "ISSUE001", "type": "error_report", "entity_id": "ISSUE001",
                           "error": "NullPointerException in PaymentProcessor.processTransaction()"},
                "summary": "Production error: NPE in payment processing affecting 15% of transactions",
                "tags": {"production", "error", "npe", "payment", "critical"},
                "context_type": ContextType.TOOL_OUTPUT
            },
            {
                "content": {"Id": "DEBUG001", "type": "debug_session", "entity_id": "DEBUG001",
                           "stacktrace": "at PaymentProcessor.java:145"},
                "summary": "Stack trace shows NPE occurs when customer.getBillingAddress() returns null",
                "tags": {"debug", "stacktrace", "billing", "null"},
                "context_type": ContextType.TOOL_OUTPUT,
                "relates_to": ["ISSUE001"]
            },
            {
                "content": {"Id": "CODE001", "type": "code_analysis", "entity_id": "CODE001",
                           "file": "PaymentProcessor.java", "line": 145},
                "summary": "Code assumes billing address is always present but new API can return null",
                "tags": {"code", "analysis", "api", "assumption"},
                "context_type": ContextType.SEARCH_RESULT,
                "relates_to": ["DEBUG001"]
            },
            {
                "content": {"Id": "COMMIT001", "type": "git_commit", "entity_id": "COMMIT001",
                           "hash": "a3f42b1", "author": "john.doe"},
                "summary": "Recent commit changed API to allow null billing addresses for digital goods",
                "tags": {"git", "commit", "api_change", "recent"},
                "context_type": ContextType.DOMAIN_ENTITY,
                "relates_to": ["CODE001"]
            },
            {
                "content": {"Id": "FIX001", "type": "code_fix", "entity_id": "FIX001"},
                "summary": "Added null check for billing address with fallback to account address",
                "tags": {"fix", "null_check", "solution", "code"},
                "context_type": ContextType.COMPLETED_ACTION,
                "depends_on": ["CODE001", "COMMIT001"]
            },
            {
                "content": {"Id": "TEST001", "type": "test_result", "entity_id": "TEST001"},
                "summary": "Unit tests added for null billing address scenario, all passing",
                "tags": {"test", "unit_test", "validation", "passing"},
                "context_type": ContextType.TOOL_OUTPUT,
                "relates_to": ["FIX001"]
            }
        ]
        
        # Store troubleshooting flow
        node_ids = {}
        for step in troubleshooting_steps:
            relates_to_ids = []
            if "relates_to" in step:
                for ref in step["relates_to"]:
                    if ref in node_ids:
                        relates_to_ids.append(node_ids[ref])
            
            depends_on_ids = []
            if "depends_on" in step:
                for ref in step["depends_on"]:
                    if ref in node_ids:
                        depends_on_ids.append(node_ids[ref])
            
            node_id = self.memory.store(
                content=step["content"],
                context_type=step["context_type"],
                summary=step["summary"],
                tags=step["tags"],
                relates_to=relates_to_ids if relates_to_ids else None,
                depends_on=depends_on_ids if depends_on_ids else None
            )
            node_ids[step["content"]["Id"]] = node_id
        
        # Test technical queries
        queries = [
            ("NPE payment processing", ["ISSUE001", "DEBUG001"], "Should find error and debug info"),
            ("billing address null", ["DEBUG001", "CODE001", "FIX001"], "Should find root cause and fix"),
            ("recent API changes", ["COMMIT001"], "Should find the problematic commit"),
            ("PaymentProcessor.java line 145", ["CODE001", "DEBUG001"], "Should find code analysis"),
            ("fix null pointer production", ["FIX001", "TEST001"], "Should find solution and validation")
        ]
        
        all_passed = True
        for query, expected_ids, description in queries:
            results = self.memory.retrieve_relevant(query, max_results=5)
            found_ids = {
                r.content.get("entity_id", r.content.get("Id"))
                for r in results
                if isinstance(r.content, dict)
            }
            
            found_expected = any(eid in found_ids for eid in expected_ids)
            if not found_expected:
                all_passed = False
                print(f"   ❌ {description}: Query '{query}' found {found_ids}")
        
        self.log_test("Technical troubleshooting workflow", all_passed,
                     "Debugging context retrieved correctly")
    
    async def test_16_project_management_flow(self):
        """Test 16: Project management with tasks, dependencies, and status updates."""
        print("\n🔥 TEST 16: Project Management Workflow")
        
        # Create fresh memory
        self.memory = MemoryGraph("test-thread-project")
        
        # Simulate project management scenario
        project_items = [
            # Project setup
            {
                "content": {"Id": "PROJ001", "type": "project", "entity_id": "PROJ001",
                           "name": "Mobile App Redesign", "client": "TechStart Inc"},
                "summary": "Q1 2024 mobile app redesign project for TechStart Inc",
                "tags": {"project", "mobile", "redesign", "techstart", "q1_2024"},
                "context_type": ContextType.DOMAIN_ENTITY
            },
            # Epic
            {
                "content": {"Id": "EPIC001", "type": "epic", "entity_id": "EPIC001",
                           "project": "PROJ001", "name": "User Authentication Overhaul"},
                "summary": "Implement OAuth2 and biometric authentication for mobile app",
                "tags": {"epic", "authentication", "oauth2", "biometric"},
                "context_type": ContextType.COMPLETED_ACTION,
                "relates_to": ["PROJ001"]
            },
            # Tasks
            {
                "content": {"Id": "TASK001", "type": "task", "entity_id": "TASK001",
                           "epic": "EPIC001", "assignee": "sarah.chen", "points": 5},
                "summary": "Design OAuth2 flow diagrams and user journey maps",
                "tags": {"task", "design", "oauth2", "ux", "sarah"},
                "context_type": ContextType.COMPLETED_ACTION,
                "depends_on": ["EPIC001"]
            },
            {
                "content": {"Id": "TASK002", "type": "task", "entity_id": "TASK002",
                           "epic": "EPIC001", "assignee": "mike.johnson", "points": 8},
                "summary": "Implement OAuth2 backend integration with Google and Apple",
                "tags": {"task", "backend", "oauth2", "integration", "mike"},
                "context_type": ContextType.COMPLETED_ACTION,
                "depends_on": ["EPIC001", "TASK001"]
            },
            # Status update
            {
                "content": {"Id": "UPDATE001", "type": "status_update", "entity_id": "UPDATE001",
                           "task": "TASK001", "status": "completed"},
                "summary": "OAuth2 flow designs completed and approved by client",
                "tags": {"update", "completed", "design", "approved"},
                "context_type": ContextType.USER_SELECTION,
                "relates_to": ["TASK001"]
            },
            # Blocker
            {
                "content": {"Id": "BLOCK001", "type": "blocker", "entity_id": "BLOCK001",
                           "task": "TASK002", "severity": "high"},
                "summary": "Apple OAuth requires paid developer account upgrade",
                "tags": {"blocker", "apple", "oauth", "account", "payment"},
                "context_type": ContextType.TOOL_OUTPUT,
                "relates_to": ["TASK002"]
            },
            # Resolution
            {
                "content": {"Id": "RESOLVE001", "type": "resolution", "entity_id": "RESOLVE001",
                           "blocker": "BLOCK001"},
                "summary": "Finance approved developer account upgrade, proceeding with implementation",
                "tags": {"resolution", "approved", "unblocked", "finance"},
                "context_type": ContextType.TOOL_OUTPUT,
                "relates_to": ["BLOCK001"]
            }
        ]
        
        # Store project items
        node_ids = {}
        for item in project_items:
            relates_to_ids = []
            if "relates_to" in item:
                for ref in item["relates_to"]:
                    if ref in node_ids:
                        relates_to_ids.append(node_ids[ref])
            
            depends_on_ids = []
            if "depends_on" in item:
                for ref in item["depends_on"]:
                    if ref in node_ids:
                        depends_on_ids.append(node_ids[ref])
            
            node_id = self.memory.store(
                content=item["content"],
                context_type=item["context_type"],
                summary=item["summary"],
                tags=item["tags"],
                relates_to=relates_to_ids if relates_to_ids else None,
                depends_on=depends_on_ids if depends_on_ids else None
            )
            node_ids[item["content"]["Id"]] = node_id
        
        # Test project queries
        queries = [
            ("TechStart mobile project status", ["PROJ001", "UPDATE001"], "Should find project and status"),
            ("OAuth2 implementation blockers", ["TASK002", "BLOCK001", "RESOLVE001"], "Should find blockers and resolution"),
            ("Sarah Chen tasks", ["TASK001", "UPDATE001"], "Should find Sarah's assignments"),
            ("authentication epic progress", ["EPIC001", "UPDATE001"], "Should find epic and progress"),
            ("Apple developer account", ["BLOCK001", "RESOLVE001"], "Should find blocker and resolution")
        ]
        
        all_passed = True
        for query, expected_ids, description in queries:
            results = self.memory.retrieve_relevant(query, max_results=5)
            found_ids = {
                r.content.get("entity_id", r.content.get("Id"))
                for r in results
                if isinstance(r.content, dict)
            }
            
            found_expected = any(eid in found_ids for eid in expected_ids)
            if not found_expected:
                all_passed = False
                print(f"   ❌ {description}: Query '{query}' found {found_ids}")
        
        self.log_test("Project management workflow", all_passed,
                     "Project context and dependencies retrieved correctly")
    
    async def test_17_customer_support_interaction(self):
        """Test 17: Customer support interaction with history and escalation."""
        print("\n🔥 TEST 17: Customer Support Interaction")
        
        # Create fresh memory
        self.memory = MemoryGraph("test-thread-support")
        
        # Simulate customer support scenario
        support_flow = [
            # Customer info
            {
                "content": {"Id": "CUST001", "type": "customer", "entity_id": "CUST001",
                           "name": "GlobalTech Solutions", "tier": "Enterprise", 
                           "account_value": 250000},
                "summary": "Enterprise customer GlobalTech Solutions, $250k annual contract",
                "tags": {"customer", "enterprise", "globaltech", "vip"},
                "context_type": ContextType.DOMAIN_ENTITY
            },
            # Initial ticket
            {
                "content": {"Id": "TICK001", "type": "support_ticket", "entity_id": "TICK001",
                           "customer": "CUST001", "priority": "high"},
                "summary": "Data sync failing between CRM and marketing automation platform",
                "tags": {"ticket", "sync", "crm", "marketing", "integration"},
                "context_type": ContextType.USER_SELECTION,
                "relates_to": ["CUST001"]
            },
            # Previous similar issue
            {
                "content": {"Id": "HIST001", "type": "historical_ticket", "entity_id": "HIST001",
                           "customer": "CUST001", "resolved_date": "2024-01-15"},
                "summary": "Previous sync issue was caused by API token expiration",
                "tags": {"history", "sync", "api", "token", "resolved"},
                "context_type": ContextType.SEARCH_RESULT,
                "relates_to": ["TICK001"]
            },
            # Investigation
            {
                "content": {"Id": "INVEST001", "type": "investigation", "entity_id": "INVEST001",
                           "findings": "API returning 403 forbidden errors"},
                "summary": "API calls failing with 403 errors, suggesting permission issues",
                "tags": {"investigation", "api", "403", "permission", "error"},
                "context_type": ContextType.TOOL_OUTPUT,
                "relates_to": ["TICK001"]
            },
            # Escalation
            {
                "content": {"Id": "ESC001", "type": "escalation", "entity_id": "ESC001",
                           "to": "engineering", "severity": "critical"},
                "summary": "Escalated to engineering: Enterprise customer blocked, potential permission model change",
                "tags": {"escalation", "engineering", "critical", "vip"},
                "context_type": ContextType.TOOL_OUTPUT,
                "relates_to": ["TICK001", "INVEST001"],
                "depends_on": ["CUST001"]
            },
            # Root cause
            {
                "content": {"Id": "ROOT001", "type": "root_cause", "entity_id": "ROOT001"},
                "summary": "New security policy requires explicit scope grants for enterprise integrations",
                "tags": {"root_cause", "security", "policy", "enterprise", "scope"},
                "context_type": ContextType.SEARCH_RESULT,
                "relates_to": ["ESC001"]
            },
            # Resolution
            {
                "content": {"Id": "RES001", "type": "resolution", "entity_id": "RES001",
                           "ticket": "TICK001"},
                "summary": "Granted required scopes and documented process for enterprise customers",
                "tags": {"resolution", "fixed", "documented", "process"},
                "context_type": ContextType.COMPLETED_ACTION,
                "depends_on": ["ROOT001"]
            }
        ]
        
        # Store support flow
        node_ids = {}
        for item in support_flow:
            relates_to_ids = []
            if "relates_to" in item:
                for ref in item["relates_to"]:
                    if ref in node_ids:
                        relates_to_ids.append(node_ids[ref])
            
            depends_on_ids = []
            if "depends_on" in item:
                for ref in item["depends_on"]:
                    if ref in node_ids:
                        depends_on_ids.append(node_ids[ref])
            
            node_id = self.memory.store(
                content=item["content"],
                context_type=item["context_type"],
                summary=item["summary"],
                tags=item["tags"],
                relates_to=relates_to_ids if relates_to_ids else None,
                depends_on=depends_on_ids if depends_on_ids else None
            )
            node_ids[item["content"]["Id"]] = node_id
        
        # Test support queries
        queries = [
            ("GlobalTech sync issues", ["CUST001", "TICK001", "HIST001"], "Should find customer and issues"),
            ("403 permission errors", ["INVEST001", "ROOT001"], "Should find investigation and cause"),
            ("enterprise customer escalation", ["ESC001", "CUST001"], "Should find escalation context"),
            ("previous token expiration", ["HIST001"], "Should find historical issue"),
            ("security policy scope", ["ROOT001", "RES001"], "Should find root cause and fix")
        ]
        
        all_passed = True
        for query, expected_ids, description in queries:
            results = self.memory.retrieve_relevant(query, max_results=5)
            found_ids = {
                r.content.get("entity_id", r.content.get("Id"))
                for r in results
                if isinstance(r.content, dict)
            }
            
            found_expected = any(eid in found_ids for eid in expected_ids)
            if not found_expected:
                all_passed = False
                print(f"   ❌ {description}: Query '{query}' found {found_ids}")
        
        self.log_test("Customer support interaction", all_passed,
                     "Support history and escalation tracked correctly")
    
    async def test_18_code_review_discussion(self):
        """Test 18: Code review discussion with comments and iterations."""
        print("\n🔥 TEST 18: Code Review Discussion")
        
        # Create fresh memory
        self.memory = MemoryGraph("test-thread-codereview")
        
        # Simulate code review
        review_flow = [
            # PR creation
            {
                "content": {"Id": "PR001", "type": "pull_request", "entity_id": "PR001",
                           "number": 1234, "author": "alice.wong", "branch": "feature/auth-refactor"},
                "summary": "Refactor authentication module to use JWT tokens instead of sessions",
                "tags": {"pr", "authentication", "jwt", "refactor", "alice"},
                "context_type": ContextType.DOMAIN_ENTITY
            },
            # Code changes
            {
                "content": {"Id": "CHANGE001", "type": "code_change", "entity_id": "CHANGE001",
                           "file": "auth/jwt_handler.py", "lines": "+245 -89"},
                "summary": "Added JWT token generation and validation with RS256 algorithm",
                "tags": {"code", "jwt", "rs256", "security", "python"},
                "context_type": ContextType.TOOL_OUTPUT,
                "relates_to": ["PR001"]
            },
            # Review comment
            {
                "content": {"Id": "COMMENT001", "type": "review_comment", "entity_id": "COMMENT001",
                           "reviewer": "bob.smith", "severity": "major"},
                "summary": "Security concern: JWT secret key is hardcoded, should use environment variable",
                "tags": {"review", "security", "hardcoded", "secret", "concern"},
                "context_type": ContextType.TOOL_OUTPUT,
                "relates_to": ["CHANGE001"]
            },
            # Author response
            {
                "content": {"Id": "RESPONSE001", "type": "author_response", "entity_id": "RESPONSE001",
                           "author": "alice.wong"},
                "summary": "Good catch! Will move to environment variables and add key rotation",
                "tags": {"response", "agreed", "environment", "rotation"},
                "context_type": ContextType.USER_SELECTION,
                "relates_to": ["COMMENT001"]
            },
            # Updated code
            {
                "content": {"Id": "UPDATE001", "type": "code_update", "entity_id": "UPDATE001",
                           "commit": "f3a8b29"},
                "summary": "Moved JWT secrets to environment, added key rotation mechanism",
                "tags": {"update", "fixed", "environment", "rotation", "secure"},
                "context_type": ContextType.COMPLETED_ACTION,
                "depends_on": ["COMMENT001", "RESPONSE001"]
            },
            # Test addition
            {
                "content": {"Id": "TEST001", "type": "test_addition", "entity_id": "TEST001",
                           "file": "tests/test_jwt_handler.py"},
                "summary": "Added unit tests for JWT key rotation and environment variable loading",
                "tags": {"test", "unit", "jwt", "coverage", "validation"},
                "context_type": ContextType.TOOL_OUTPUT,
                "relates_to": ["UPDATE001"]
            },
            # Approval
            {
                "content": {"Id": "APPROVAL001", "type": "approval", "entity_id": "APPROVAL001",
                           "reviewer": "bob.smith"},
                "summary": "LGTM! Good security improvements and test coverage",
                "tags": {"approval", "lgtm", "approved", "security"},
                "context_type": ContextType.USER_SELECTION,
                "relates_to": ["UPDATE001", "TEST001"]
            }
        ]
        
        # Store review flow
        node_ids = {}
        for item in review_flow:
            relates_to_ids = []
            if "relates_to" in item:
                for ref in item["relates_to"]:
                    if ref in node_ids:
                        relates_to_ids.append(node_ids[ref])
            
            depends_on_ids = []
            if "depends_on" in item:
                for ref in item["depends_on"]:
                    if ref in node_ids:
                        depends_on_ids.append(node_ids[ref])
            
            node_id = self.memory.store(
                content=item["content"],
                context_type=item["context_type"],
                summary=item["summary"],
                tags=item["tags"],
                relates_to=relates_to_ids if relates_to_ids else None,
                depends_on=depends_on_ids if depends_on_ids else None
            )
            node_ids[item["content"]["Id"]] = node_id
        
        # Test review queries
        queries = [
            ("JWT security concerns", ["COMMENT001", "UPDATE001"], "Should find security issue and fix"),
            ("auth refactor PR", ["PR001", "CHANGE001"], "Should find PR and changes"),
            ("hardcoded secret key", ["COMMENT001", "RESPONSE001"], "Should find issue and response"),
            ("key rotation implementation", ["UPDATE001", "TEST001"], "Should find implementation and tests"),
            ("Bob Smith review", ["COMMENT001", "APPROVAL001"], "Should find Bob's feedback")
        ]
        
        all_passed = True
        for query, expected_ids, description in queries:
            results = self.memory.retrieve_relevant(query, max_results=5)
            found_ids = {
                r.content.get("entity_id", r.content.get("Id"))
                for r in results
                if isinstance(r.content, dict)
            }
            
            found_expected = any(eid in found_ids for eid in expected_ids)
            if not found_expected:
                all_passed = False
                print(f"   ❌ {description}: Query '{query}' found {found_ids}")
        
        self.log_test("Code review discussion", all_passed,
                     "Code review context and iterations tracked correctly")
    
    async def test_19_entity_extraction_from_tools(self):
        """Test 19: Entity extraction from agent tool results."""
        print("\n🔥 TEST 19: Entity Extraction from Tool Results")
        
        # Create fresh memory
        self.memory = MemoryGraph("test-thread-extraction")
        
        # Test Salesforce entity extraction
        sf_thread_id = create_thread_id("salesforce", "test-extraction")
        sf_tool_result = {
            "success": True,
            "data": [{
                "attributes": {"type": "Account"},
                "Id": "001EXT000001",
                "Name": "Entity Extract Corp",
                "Industry": "Technology",
                "AnnualRevenue": 10000000,
                "Website": "www.entityextract.com"
            }],
            "operation": "salesforce_search"
        }
        
        # Write tool result (should extract entity)
        node_id = write_tool_result_to_memory(
            thread_id=sf_thread_id,
            tool_name="salesforce_search",
            tool_args={"filter": "Name LIKE '%Entity%'"},
            tool_result=sf_tool_result,
            task_id="test-extraction",
            agent_name="salesforce"
        )
        
        # Get memory for verification
        memory_manager = get_memory_manager()
        sf_memory = memory_manager.get_memory(sf_thread_id)
        
        # Verify entity was extracted
        entity_nodes = sf_memory.retrieve_relevant(
            context_filter={ContextType.DOMAIN_ENTITY},
            max_results=10
        )
        
        entity_found = any(
            isinstance(n.content, dict) and 
            n.content.get("entity_id") == "001EXT000001" and
            n.content.get("entity_name") == "Entity Extract Corp"
            for n in entity_nodes
        )
        
        self.log_test("Extract Salesforce entity from tool result", entity_found,
                     f"Found {len(entity_nodes)} entities")
    
    async def test_20_entity_deduplication(self):
        """Test 20: Entity deduplication and updates."""
        print("\n🔥 TEST 20: Entity Deduplication and Updates")
        
        thread_id = create_thread_id("salesforce", "test-dedup")
        
        # First occurrence with basic data
        tool_result_1 = {
            "success": True,
            "data": [{
                "Id": "001DEDUP00001",
                "Name": "DedupTest Corp",
                "Industry": "Finance"
            }],
            "operation": "salesforce_search"
        }
        
        write_tool_result_to_memory(
            thread_id=thread_id,
            tool_name="salesforce_search",
            tool_args={},
            tool_result=tool_result_1,
            task_id="test-dedup",
            agent_name="salesforce"
        )
        
        # Second occurrence with additional data
        tool_result_2 = {
            "success": True,
            "data": {
                "Id": "001DEDUP00001",
                "Name": "DedupTest Corp",
                "Industry": "Finance",
                "Website": "www.deduptest.com",
                "AnnualRevenue": 5000000,
                "NumberOfEmployees": 250
            },
            "operation": "salesforce_get"
        }
        
        write_tool_result_to_memory(
            thread_id=thread_id,
            tool_name="salesforce_get",
            tool_args={"id": "001DEDUP00001"},
            tool_result=tool_result_2,
            task_id="test-dedup",
            agent_name="salesforce"
        )
        
        # Check if entity was updated, not duplicated
        memory_manager = get_memory_manager()
        memory = memory_manager.get_memory(thread_id)
        entity_nodes = memory.retrieve_relevant(
            query_text="DedupTest",
            context_filter={ContextType.DOMAIN_ENTITY},
            max_results=10
        )
        
        # Should have exactly one entity
        dedup_nodes = [n for n in entity_nodes if n.content.get("entity_name") == "DedupTest Corp"]
        
        no_duplicates = len(dedup_nodes) == 1
        data_merged = False
        update_tracked = False
        
        if dedup_nodes:
            entity_data = dedup_nodes[0].content.get("entity_data", {})
            # Should have merged data
            data_merged = "Website" in entity_data and "NumberOfEmployees" in entity_data
            update_tracked = dedup_nodes[0].content.get("update_count", 0) > 0
        
        self.log_test("No duplicate entities", no_duplicates,
                     f"Found {len(dedup_nodes)} entities")
        self.log_test("Entity data merged", data_merged)
        self.log_test("Update count tracked", update_tracked)
    
    async def test_21_cross_system_relationships(self):
        """Test 21: Relationship creation across different systems."""
        print("\n🔥 TEST 21: Cross-System Relationship Creation")
        
        # Create an Account in Salesforce
        sf_thread_id = create_thread_id("salesforce", "test-relationships")
        account_result = {
            "success": True,
            "data": {
                "Id": "001REL000001",
                "Name": "RelationshipTest Inc",
                "Type": "Customer"
            },
            "operation": "salesforce_create"
        }
        
        write_tool_result_to_memory(
            thread_id=sf_thread_id,
            tool_name="salesforce_create",
            tool_args={"object": "Account"},
            tool_result=account_result,
            task_id="test-relationships",
            agent_name="salesforce"
        )
        
        # Create a Jira project for the same customer
        jira_thread_id = create_thread_id("jira", "test-relationships")
        jira_result = {
            "success": True,
            "data": {
                "id": "10123",
                "key": "RELTEST",
                "name": "RelationshipTest Inc Project"
            },
            "operation": "jira_create"
        }
        
        write_tool_result_to_memory(
            thread_id=jira_thread_id,
            tool_name="jira_create",
            tool_args={"type": "Project"},
            tool_result=jira_result,
            task_id="test-relationships",
            agent_name="jira"
        )
        
        # Create ServiceNow incident
        sn_thread_id = create_thread_id("servicenow", "test-relationships")
        sn_result = {
            "success": True,
            "data": {
                "number": "INC0098765",
                "short_description": "RelationshipTest Inc - System outage",
                "caller_id": "RelationshipTest Inc"
            },
            "operation": "servicenow_create"
        }
        
        write_tool_result_to_memory(
            thread_id=sn_thread_id,
            tool_name="servicenow_create",
            tool_args={"type": "incident"},
            tool_result=sn_result,
            task_id="test-relationships",
            agent_name="servicenow"
        )
        
        # Verify entities were created in each system
        memory_manager = get_memory_manager()
        
        sf_memory = memory_manager.get_memory(sf_thread_id)
        sf_entities = sf_memory.retrieve_relevant(
            query_text="RelationshipTest",
            context_filter={ContextType.DOMAIN_ENTITY}
        )
        
        jira_memory = memory_manager.get_memory(jira_thread_id)
        jira_entities = jira_memory.retrieve_relevant(
            query_text="RELTEST",
            context_filter={ContextType.DOMAIN_ENTITY}
        )
        
        sn_memory = memory_manager.get_memory(sn_thread_id)
        sn_entities = sn_memory.retrieve_relevant(
            query_text="INC0098765",
            context_filter={ContextType.DOMAIN_ENTITY}
        )
        
        self.log_test("Cross-system entities created",
                     len(sf_entities) > 0 and len(jira_entities) > 0 and len(sn_entities) > 0,
                     f"SF: {len(sf_entities)}, Jira: {len(jira_entities)}, SN: {len(sn_entities)}")
    
    async def test_22_pending_relationship_resolution(self):
        """Test 22: Resolution of relationships when entities arrive out of order."""
        print("\n🔥 TEST 22: Pending Relationship Resolution")
        
        thread_id = create_thread_id("salesforce", "test-pending")
        
        # Create an Opportunity with a reference to an Account that doesn't exist yet
        opp_result = {
            "success": True,
            "data": {
                "Id": "006PEND000001",
                "Name": "Pending Test - Big Deal",
                "AccountId": "001PEND000001",  # This account doesn't exist yet!
                "Amount": 500000,
                "StageName": "Negotiation"
            },
            "operation": "salesforce_create"
        }
        
        write_tool_result_to_memory(
            thread_id=thread_id,
            tool_name="salesforce_create",
            tool_args={"object": "Opportunity"},
            tool_result=opp_result,
            task_id="test-pending",
            agent_name="salesforce"
        )
        
        # Now create the Account
        account_result = {
            "success": True,
            "data": {
                "Id": "001PEND000001",
                "Name": "Pending Test Corp",
                "Type": "Enterprise"
            },
            "operation": "salesforce_create"
        }
        
        write_tool_result_to_memory(
            thread_id=thread_id,
            tool_name="salesforce_create",
            tool_args={"object": "Account"},
            tool_result=account_result,
            task_id="test-pending",
            agent_name="salesforce"
        )
        
        # Check if relationships were resolved
        memory_manager = get_memory_manager()
        memory = memory_manager.get_memory(thread_id)
        
        # Get nodes by entity ID
        opp_node = memory.node_manager.get_node_by_entity_id("006PEND000001")
        account_node = memory.node_manager.get_node_by_entity_id("001PEND000001")
        
        nodes_created = opp_node is not None and account_node is not None
        relationship_exists = False
        
        if nodes_created and opp_node.node_id in memory.graph:
            # Check if opportunity has relationship to account
            for successor in memory.graph.successors(opp_node.node_id):
                if successor == account_node.node_id:
                    relationship_exists = True
                    break
        
        self.log_test("Entities created", nodes_created)
        self.log_test("Pending relationship resolved", relationship_exists,
                     "Opportunity → Account relationship created after Account was added")
    
    async def test_23_entity_lifecycle_and_relevance(self):
        """Test 23: Entity lifecycle including access patterns and relevance."""
        print("\n🔥 TEST 23: Entity Lifecycle and Relevance")
        
        thread_id = create_thread_id("jira", "test-lifecycle")
        
        # Create an entity
        result = {
            "success": True,
            "data": {
                "id": "50001",
                "key": "LIFE-100",
                "fields": {
                    "summary": "Lifecycle test issue",
                    "priority": {"name": "High"}
                }
            },
            "operation": "jira_create"
        }
        
        write_tool_result_to_memory(
            thread_id=thread_id,
            tool_name="jira_create",
            tool_args={},
            tool_result=result,
            task_id="test-lifecycle",
            agent_name="jira"
        )
        
        memory_manager = get_memory_manager()
        memory = memory_manager.get_memory(thread_id)
        
        # Get the entity
        entity_node = memory.node_manager.get_node_by_entity_id("50001")
        
        initial_relevance = None
        accessed_relevance = None
        has_access_tracking = False
        
        if entity_node:
            # Check initial relevance
            initial_relevance = entity_node.current_relevance()
            
            # Access the entity multiple times
            for _ in range(3):
                entity_node.access()
                time.sleep(0.1)
            
            # Check relevance after access
            accessed_relevance = entity_node.current_relevance()
            
            # Check access tracking
            has_access_tracking = hasattr(entity_node, 'access_count') or \
                                 entity_node.content.get('update_count', 0) > 0
        
        self.log_test("Entity has initial relevance",
                     entity_node is not None and initial_relevance is not None and initial_relevance > 0)
        self.log_test("Accessing entity affects relevance",
                     accessed_relevance is not None and initial_relevance is not None and 
                     accessed_relevance >= initial_relevance)
        self.log_test("Entity tracks access patterns", has_access_tracking)
    
    async def test_24_complex_entity_web(self):
        """Test 24: Complex web of related entities across multiple operations."""
        print("\n🔥 TEST 24: Complex Entity Web")
        
        thread_id = create_thread_id("salesforce", "test-web")
        
        # Create a complex scenario:
        # 1. Account with multiple contacts
        # 2. Opportunities linked to contacts and account
        # 3. Cases linked to contacts
        # 4. Tasks linked to opportunities and cases
        
        # Account
        account = {
            "success": True,
            "data": {
                "Id": "001WEB000001",
                "Name": "WebTest Enterprises",
                "Type": "Enterprise",
                "Industry": "Technology"
            }
        }
        write_tool_result_to_memory(thread_id, "salesforce_create", {}, account,
                                   "test-web", "salesforce")
        
        # Contacts
        contacts = []
        for i in range(3):
            contact = {
                "success": True,
                "data": {
                    "Id": f"003WEB00000{i+1}",
                    "Name": f"Contact {i+1}",
                    "AccountId": "001WEB000001",
                    "Title": ["CEO", "CTO", "CFO"][i]
                }
            }
            write_tool_result_to_memory(thread_id, "salesforce_create", {}, contact,
                                       "test-web", "salesforce")
            contacts.append(f"003WEB00000{i+1}")
        
        # Opportunities
        opportunities = []
        for i in range(2):
            opp = {
                "success": True,
                "data": {
                    "Id": f"006WEB00000{i+1}",
                    "Name": f"WebTest Deal {i+1}",
                    "AccountId": "001WEB000001",
                    "ContactId": contacts[i],
                    "Amount": (i + 1) * 100000
                }
            }
            write_tool_result_to_memory(thread_id, "salesforce_create", {}, opp,
                                       "test-web", "salesforce")
            opportunities.append(f"006WEB00000{i+1}")
        
        # Cases
        cases = []
        for i in range(2):
            case = {
                "success": True,
                "data": {
                    "Id": f"500WEB00000{i+1}",
                    "Subject": f"Support Case {i+1}",
                    "AccountId": "001WEB000001",
                    "ContactId": contacts[i+1],
                    "Priority": "High"
                }
            }
            write_tool_result_to_memory(thread_id, "salesforce_create", {}, case,
                                       "test-web", "salesforce")
            cases.append(f"500WEB00000{i+1}")
        
        # Tasks
        for i in range(3):
            task = {
                "success": True,
                "data": {
                    "Id": f"00TWEB00000{i+1}",
                    "Subject": f"Task {i+1}",
                    "WhatId": opportunities[0] if i < 2 else cases[0],
                    "WhoId": contacts[i]
                }
            }
            write_tool_result_to_memory(thread_id, "salesforce_create", {}, task,
                                       "test-web", "salesforce")
        
        # Verify the complex web
        memory_manager = get_memory_manager()
        memory = memory_manager.get_memory(thread_id)
        
        # Get all entities
        entities = memory.retrieve_relevant(
            context_filter={ContextType.DOMAIN_ENTITY},
            max_results=50
        )
        
        # Count entities by type
        entity_types = {}
        for node in entities:
            entity_type = node.content.get("entity_type", "Unknown")
            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
        
        # Check if all entity types were created
        expected_types = ["Account", "Contact", "Opportunity", "Case", "Task"]
        all_types_created = all(t in entity_types for t in expected_types)
        
        # Check if Account is a hub (has many connections)
        account_node = memory.node_manager.get_node_by_entity_id("001WEB000001")
        hub_connections = 0
        if account_node and account_node.node_id in memory.graph:
            out_degree = memory.graph.out_degree(account_node.node_id)
            in_degree = memory.graph.in_degree(account_node.node_id)
            hub_connections = out_degree + in_degree
        
        self.log_test("All entity types created", all_types_created,
                     f"Types found: {list(entity_types.keys())}")
        self.log_test("Complex relationships formed", hub_connections >= 5,
                     f"Account has {hub_connections} connections")
        self.log_test("Entity web size", len(entities) >= 11,
                     f"Created {len(entities)} entities")
    
    async def run_all_tests(self):
        """Run all torture tests."""
        print("\n" + "="*80)
        print("🔥 MEGA ULTRA SUPER ROBUST COMPREHENSIVE MEMORY FRAMEWORK TEST SUITE 🔥")
        print("="*80)
        
        self.memory = get_thread_memory(self.thread_id)
        
        tests = [
            self.test_1_basic_storage_retrieval,
            self.test_2_massive_pollution,
            self.test_3_time_decay_relevance,
            self.test_4_relationship_navigation,
            self.test_5_concurrent_access_stress,
            self.test_6_semantic_search_accuracy,
            self.test_7_memory_cleanup_preservation,
            self.test_8_cross_system_entity_linking,
            self.test_9_retrieval_with_context_window,
            self.test_10_intelligent_algorithms,
            self.test_11_extreme_scale,
            self.test_12_false_positive_prevention,
            self.test_13_entity_type_filtering,
            self.test_14_real_conversation_flow,
            self.test_15_technical_troubleshooting,
            self.test_16_project_management_flow,
            self.test_17_customer_support_interaction,
            self.test_18_code_review_discussion,
            self.test_19_entity_extraction_from_tools,
            self.test_20_entity_deduplication,
            self.test_21_cross_system_relationships,
            self.test_22_pending_relationship_resolution,
            self.test_23_entity_lifecycle_and_relevance,
            self.test_24_complex_entity_web
        ]
        
        for test_func in tests:
            try:
                await test_func()
            except Exception as e:
                self.log_test(test_func.__name__, False, f"Exception: {str(e)}\n{traceback.format_exc()}")
        
        # Summary
        print("\n" + "="*80)
        print("📊 TEST SUITE SUMMARY")
        print("="*80)
        
        passed = sum(1 for r in self.test_results if r["passed"])
        failed = len(self.test_results) - passed
        
        print(f"\n✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"📈 Total: {len(self.test_results)}")
        print(f"🎯 Success Rate: {(passed/len(self.test_results)*100):.1f}%")
        
        print(f"\n📊 Final Graph Stats:")
        print(f"   - Total Nodes: {len(self.memory.node_manager.nodes)}")
        print(f"   - Total Edges: {self.memory.graph.number_of_edges()}")
        
        # Calculate density safely
        n_nodes = len(self.memory.node_manager.nodes)
        if n_nodes > 1:
            max_edges = n_nodes * (n_nodes - 1) / 2
            density = self.memory.graph.number_of_edges() / max_edges
            print(f"   - Graph Density: {density:.4f}")
        else:
            print(f"   - Graph Density: N/A (not enough nodes)")
        
        if failed > 0:
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result["passed"]:
                    print(f"   - {result['test']}: {result['details']}")
        
        # Save detailed results
        with open("memory_test_results.json", "w") as f:
            json.dump(self.test_results, f, indent=2)
        print("\n📄 Detailed results saved to memory_test_results.json")
        
        return passed == len(self.test_results)

if __name__ == "__main__":
    tester = MemoryTortureTest()
    success = asyncio.run(tester.run_all_tests())
    sys.exit(0 if success else 1)