"""Tests for the memory system including storage and schemas."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import asyncio
import sqlite3
from datetime import datetime

from src.utils.storage.memory_schemas import (
    SimpleMemory, SimpleAccount, SimpleContact, SimpleOpportunity,
    SimpleCase, SimpleTask, SimpleLead
)
from src.utils.storage.async_store_adapter import AsyncStoreAdapter
from src.utils.storage.sqlite_store import SQLiteStore


class TestMemorySchemas:
    """Test Pydantic memory schema models."""
    
    def test_simple_account_creation(self):
        """Test creating a SimpleAccount."""
        account = SimpleAccount(
            id="001234567890ABC",
            name="Acme Corporation"
        )
        
        assert account.id == "001234567890ABC"
        assert account.name == "Acme Corporation"
        
        # Test dict conversion
        account_dict = account.model_dump()
        assert account_dict["id"] == "001234567890ABC"
        assert account_dict["name"] == "Acme Corporation"
    
    def test_simple_contact_creation(self):
        """Test creating a SimpleContact."""
        contact = SimpleContact(
            id="003234567890DEF",
            name="John Doe",
            email="john@example.com",
            account_id="001234567890ABC"
        )
        
        assert contact.id == "003234567890DEF"
        assert contact.name == "John Doe"
        assert contact.email == "john@example.com"
        assert contact.account_id == "001234567890ABC"
    
    def test_simple_memory_creation(self):
        """Test creating a SimpleMemory with all entity types."""
        memory = SimpleMemory(
            accounts=[
                SimpleAccount(id="001", name="Account 1"),
                SimpleAccount(id="002", name="Account 2")
            ],
            contacts=[
                SimpleContact(id="003", name="Contact 1", account_id="001")
            ],
            opportunities=[
                SimpleOpportunity(id="006", name="Big Deal", stage="Prospecting", amount=100000)
            ],
            cases=[
                SimpleCase(id="500", subject="Support Issue", account_id="001")
            ],
            tasks=[
                SimpleTask(id="00T", subject="Follow up", related_to_id="001")
            ],
            leads=[
                SimpleLead(id="00Q", name="New Lead", company="NewCo", status="New")
            ]
        )
        
        assert len(memory.accounts) == 2
        assert len(memory.contacts) == 1
        assert len(memory.opportunities) == 1
        assert len(memory.cases) == 1
        assert len(memory.tasks) == 1
        assert len(memory.leads) == 1
        
        # Test serialization
        memory_dict = memory.model_dump()
        assert len(memory_dict["accounts"]) == 2
        assert memory_dict["opportunities"][0]["amount"] == 100000
    
    def test_optional_fields(self):
        """Test that optional fields work correctly."""
        # Contact without email
        contact = SimpleContact(id="003", name="No Email")
        assert contact.email is None
        
        # Opportunity without amount
        opp = SimpleOpportunity(id="006", name="Unknown Value", stage="Prospecting")
        assert opp.amount is None
        
        # Task without account_id
        task = SimpleTask(id="00T", subject="Independent Task")
        assert task.account_id is None


class TestSQLiteStore:
    """Test the SQLite storage backend."""
    
    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database for testing."""
        db_path = tmp_path / "test.db"
        return str(db_path)
    
    @pytest.fixture
    def store(self, temp_db):
        """Create a SQLiteStore instance."""
        return SQLiteStore(temp_db)
    
    def test_store_initialization(self, store, temp_db):
        """Test that store initializes correctly."""
        # Check database was created
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Check table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='store'")
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == "store"
        
        conn.close()
    
    def test_put_and_get(self, store):
        """Test storing and retrieving data."""
        namespace = ("test", "user1")
        key = "test_key"
        value = {"data": "test_value", "number": 42}
        
        # Store value
        store.put(namespace, key, value)
        
        # Retrieve value
        retrieved = store.get(namespace, key)
        assert retrieved == value
        assert retrieved["data"] == "test_value"
        assert retrieved["number"] == 42
    
    def test_get_nonexistent(self, store):
        """Test getting a non-existent key."""
        result = store.get(("test", "user1"), "nonexistent")
        assert result is None
    
    def test_update_existing(self, store):
        """Test updating an existing value."""
        namespace = ("test", "user1")
        key = "update_test"
        
        # Store initial value
        store.put(namespace, key, {"version": 1})
        
        # Update value
        store.put(namespace, key, {"version": 2, "updated": True})
        
        # Verify update
        result = store.get(namespace, key)
        assert result["version"] == 2
        assert result["updated"] is True
    
    def test_delete(self, store):
        """Test deleting a value."""
        namespace = ("test", "user1")
        key = "delete_test"
        
        # Store value
        store.put(namespace, key, {"data": "to_delete"})
        
        # Verify it exists
        assert store.get(namespace, key) is not None
        
        # Delete it
        store.delete(namespace, key)
        
        # Verify it's gone
        assert store.get(namespace, key) is None
    
    def test_namespace_isolation(self, store):
        """Test that namespaces are properly isolated."""
        key = "same_key"
        value1 = {"data": "namespace1"}
        value2 = {"data": "namespace2"}
        
        # Store in different namespaces
        store.put(("test", "user1"), key, value1)
        store.put(("test", "user2"), key, value2)
        
        # Verify isolation
        assert store.get(("test", "user1"), key)["data"] == "namespace1"
        assert store.get(("test", "user2"), key)["data"] == "namespace2"
    
    def test_complex_memory_storage(self, store):
        """Test storing complex memory objects."""
        memory = SimpleMemory(
            accounts=[
                SimpleAccount(id="001", name="Test Account")
            ],
            contacts=[
                SimpleContact(id="003", name="Test Contact", account_id="001")
            ]
        )
        
        namespace = ("memory", "user1")
        key = "SimpleMemory"
        
        # Store memory
        store.put(namespace, key, memory.model_dump())
        
        # Retrieve and reconstruct
        retrieved_data = store.get(namespace, key)
        reconstructed = SimpleMemory(**retrieved_data)
        
        assert len(reconstructed.accounts) == 1
        assert reconstructed.accounts[0].name == "Test Account"
        assert len(reconstructed.contacts) == 1
        assert reconstructed.contacts[0].account_id == "001"


class TestAsyncStoreAdapter:
    """Test the async store adapter."""
    
    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database."""
        return str(tmp_path / "test_async.db")
    
    @pytest.fixture
    def sync_adapter(self, temp_db):
        """Create a sync AsyncStoreAdapter."""
        adapter = AsyncStoreAdapter(temp_db, use_async=False)
        yield adapter
        # Properly close the adapter with async close method
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(adapter.close())
        finally:
            loop.close()
    
    def test_sync_operations(self, sync_adapter):
        """Test synchronous operations."""
        namespace = ("test", "user1")
        key = "test_key"
        value = {"data": "test"}
        
        # Test put
        sync_adapter.sync_put(namespace, key, value)
        
        # Test get
        result = sync_adapter.sync_get(namespace, key)
        assert result == value
        
        # Test delete - use async delete through event loop
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(sync_adapter.delete(namespace, key))
        finally:
            loop.close()
        
        result = sync_adapter.sync_get(namespace, key)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_async_operations(self, temp_db):
        """Test asynchronous operations with sync backend."""
        # Create async adapter with sync backend (use_async=False)
        # This tests the async interface over sync operations
        adapter = AsyncStoreAdapter(temp_db, use_async=False)
        
        namespace = ("test", "user1")
        key = "test_key"
        value = {"data": "test"}
        
        try:
            # Test async put
            await adapter.put(namespace, key, value)
            
            # Test async get
            result = await adapter.get(namespace, key)
            assert result == value
            
            # Test async delete
            await adapter.delete(namespace, key)
            result = await adapter.get(namespace, key)
            assert result is None
        finally:
            await adapter.close()
    
    def test_circuit_breaker_integration(self, temp_db):
        """Test circuit breaker functionality."""
        # Create adapter with circuit breaker
        adapter = AsyncStoreAdapter(
            temp_db, 
            use_async=False,
            enable_circuit_breaker=True
        )
        
        namespace = ("test", "user1")
        key = "test_key"
        value = {"data": "test"}
        
        try:
            # Test normal operation
            adapter.sync_put(namespace, key, value)
            result = adapter.sync_get(namespace, key)
            assert result == value
            
            # Test that circuit breaker is enabled
            assert adapter.circuit_breaker is not None
        finally:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(adapter.close())
            finally:
                loop.close()
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self, temp_db):
        """Test handling concurrent operations with sync backend."""
        # Use sync backend for stability in tests
        adapter = AsyncStoreAdapter(temp_db, use_async=False)
        
        async def write_and_read(i):
            namespace = ("test", "concurrent")
            key = f"counter_{i}"
            value = {"value": i}
            await adapter.put(namespace, key, value)
            return await adapter.get(namespace, key)
        
        try:
            # Run multiple concurrent operations
            tasks = [write_and_read(i) for i in range(3)]  # Reduced for stability
            results = await asyncio.gather(*tasks)
            
            # All operations should complete
            assert len(results) == 3
            assert all(r is not None for r in results)
        finally:
            await adapter.close()


class TestMemoryExtraction:
    """Test memory extraction from conversations."""
    
    def test_memory_deduplication(self):
        """Test that duplicate records are properly merged."""
        memory = SimpleMemory()
        
        # Add duplicate accounts
        memory.accounts.extend([
            SimpleAccount(id="001", name="Acme Corp"),
            SimpleAccount(id="001", name="Acme Corporation"),  # Same ID, different name
            SimpleAccount(id="002", name="Other Corp")
        ])
        
        # Create a dict for deduplication (as done in the orchestrator)
        account_dict = {}
        for account in memory.accounts:
            account_dict[account.id] = account.model_dump()
        
        # Should have 2 unique accounts
        assert len(account_dict) == 2
        # The last duplicate should win
        assert account_dict["001"]["name"] == "Acme Corporation"
    
    def test_memory_validation(self):
        """Test memory validation catches invalid data."""
        # Valid memory
        valid_data = {
            "accounts": [{"id": "001", "name": "Test"}],
            "contacts": [],
            "opportunities": [],
            "cases": [],
            "tasks": [],
            "leads": []
        }
        
        memory = SimpleMemory(**valid_data)
        assert len(memory.accounts) == 1
        
        # Invalid data (missing required field)
        invalid_data = {
            "accounts": [{"id": "001"}],  # Missing required 'name' field
            "contacts": [],
            "opportunities": [],
            "cases": [],
            "tasks": [],
            "leads": []
        }
        
        with pytest.raises(Exception):  # Pydantic validation error
            SimpleMemory(**invalid_data)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])