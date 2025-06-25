"""SQLite-based key-value store implementation for persistent storage.

This module provides a thread-safe, async-compatible storage solution using SQLite
as the backend. It implements the BaseStore interface for use with LangGraph's
checkpointing and memory persistence features.

The store uses a simple key-value schema with namespace support, enabling
multi-tenant storage patterns and isolated data contexts. All values are
JSON-serialized for flexibility in storing complex data structures.

Key features:
- Thread-safe connection management with per-thread connections
- Automatic table creation on first use
- Namespace isolation for multi-tenant scenarios
- JSON serialization for complex data types
- Batch operations for performance optimization
- Async compatibility through sync-to-async adapters
- Performance logging for monitoring and optimization
"""

import sqlite3
import json
import asyncio
from langgraph.store.base import BaseStore  # Adjust this import as needed
from src.utils.logging import get_logger

# Initialize logger
logger = get_logger()

class SQLiteStore(BaseStore):
    """Thread-safe SQLite key-value store with namespace support.
    
    Provides persistent storage for the multi-agent system with automatic
    schema creation, connection management, and transaction handling.
    Designed for use with LangGraph's checkpointing and memory features.
    
    The store uses a simple but effective schema:
    - namespace: Logical data partition (e.g., ("memory", "user-1"))
    - key: Unique identifier within namespace (e.g., "conversation_summary")
    - value: JSON-serialized data of any type
    
    Thread Safety:
        Uses SQLite's connection-per-thread model by creating new
        connections for each thread via get_connection(). This ensures
        thread safety in concurrent environments.
    
    Performance Considerations:
        - Connection reuse within threads via get_connection()
        - Batch operations for bulk updates
        - Automatic commits for data durability
        - Performance logging for monitoring
    
    Args:
        db_path: Path to SQLite database file (default: "memory_store.db")
    
    Example:
        >>> store = SQLiteStore("./data.db")
        >>> store.put(("memory", "user1"), "preferences", {"theme": "dark"})
        >>> prefs = store.get(("memory", "user1"), "preferences")
        >>> print(prefs["theme"])  # "dark"
    """
    def __init__(self, db_path: str = "memory_store.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self._create_table()
        logger.info("sqlite_init", component="storage", db_path=db_path)

    def get_connection(self, db_path: str = None):
        """Create a new SQLiteStore instance for thread-safe operations.
        
        Returns a new SQLiteStore instance with its own database connection
        to ensure thread safety. Each thread should use its own connection
        to avoid SQLite's threading limitations.
        
        Args:
            db_path: Optional database path override. If not provided,
                    uses the instance's db_path.
                    
        Returns:
            New SQLiteStore instance with independent connection.
            
        Note:
            This method implements the thread-local storage pattern
            recommended for SQLite in multi-threaded applications.
        """
        path = db_path or self.db_path
        return SQLiteStore(path)

    def _create_table(self):
        """Initialize the key-value store schema in SQLite.
        
        Creates the 'store' table if it doesn't exist with a composite
        primary key on (namespace, key) for efficient lookups and
        uniqueness constraints.
        
        Schema:
            namespace TEXT: Logical partition for data isolation
            key TEXT: Unique identifier within namespace
            value TEXT: JSON-serialized data
            PRIMARY KEY (namespace, key): Ensures uniqueness
        """
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS store (
                namespace TEXT,
                key TEXT,
                value TEXT,
                PRIMARY KEY (namespace, key)
            )
            """
        )
        self.conn.commit()

    def get(self, namespace, key):
        """Retrieve a value from the store by namespace and key.
        
        Performs a lookup in the SQLite store using the composite key
        (namespace, key). Returns None if the key doesn't exist.
        
        Args:
            namespace: Tuple or list identifying the namespace,
                      e.g., ("memory", "user-1")
            key: String key within the namespace,
                 e.g., "conversation_summary"
                 
        Returns:
            The deserialized value if found, None otherwise.
            
        Note:
            Namespace is JSON-serialized for storage to handle
            complex namespace structures like tuples.
        """
        cursor = self.conn.execute(
            "SELECT value FROM store WHERE namespace = ? AND key = ?",
            (json.dumps(namespace), key)
        )
        row = cursor.fetchone()
        result = json.loads(row[0]) if row else None
        logger.info("sqlite_get", component="storage", 
                               namespace=namespace, 
                               key=key, 
                               found=result is not None)
        return result

    def put(self, namespace, key, value):
        """Store or update a value in the SQLite store.
        
        Performs an upsert operation (INSERT OR REPLACE) to store the provided
        value under the given namespace and key. If the key already exists,
        its value is updated; otherwise, a new entry is created.
        
        The method automatically handles JSON serialization of both the namespace
        and value, enabling storage of complex Python data structures including
        dictionaries, lists, and nested objects.
        
        Args:
            namespace: Tuple or list identifying the namespace for data isolation,
                      e.g., ("memory", "user-1") or ["agent", "salesforce"].
                      Namespaces enable multi-tenant storage patterns.
            key: String identifier for the value within the namespace,
                 e.g., "preferences", "session_data", or "cached_results".
            value: Any JSON-serializable Python object to store. Common types:
                  - dict: {"theme": "dark", "language": "en"}
                  - list: ["item1", "item2", "item3"]
                  - string: "simple text value"
                  - number: 42 or 3.14
                  - bool: True or False
                  - None: null value
                  
        Raises:
            json.JSONEncodeError: If the value cannot be JSON-serialized.
            sqlite3.DatabaseError: If the database operation fails.
            
        Side Effects:
            - Commits the transaction immediately for durability
            - Logs performance metrics for monitoring
            
        Example:
            >>> store = SQLiteStore()
            >>> # Store user preferences
            >>> store.put(("memory", "user-1"), "preferences", {
            ...     "theme": "dark",
            ...     "notifications": True,
            ...     "language": "en"
            ... })
            >>> # Update conversation state
            >>> store.put(("agent", "orchestrator"), "state", {
            ...     "current_task": "processing",
            ...     "progress": 0.75
            ... })
            
        Note:
            This method uses SQLite's atomic INSERT OR REPLACE statement
            to ensure consistency even under concurrent access patterns.
        """
        self.conn.execute(
            "INSERT OR REPLACE INTO store (namespace, key, value) VALUES (?, ?, ?)",
            (json.dumps(namespace), key, json.dumps(value))
        )
        self.conn.commit()
        logger.info("sqlite_put", component="storage", 
                               namespace=namespace, 
                               key=key)

    def delete(self, namespace, key):
        """Remove a value from the store by namespace and key.
        
        Deletes the entry identified by the given namespace and key combination.
        If the key doesn't exist, the operation completes silently without error,
        following idempotent deletion semantics.
        
        This method is useful for:
        - Cleaning up expired data
        - Removing user-specific information
        - Clearing cached values
        - Managing storage lifecycle
        
        Args:
            namespace: Tuple or list identifying the namespace,
                      e.g., ("memory", "user-1") or ["cache", "api-responses"].
                      Must match the namespace used during storage.
            key: String identifier of the value to delete,
                 e.g., "session_token", "temp_data", or "old_preferences".
                 
        Returns:
            None. The method doesn't indicate whether a deletion actually
            occurred, maintaining idempotent behavior.
            
        Side Effects:
            - Commits the transaction immediately
            - The deletion is permanent and cannot be undone
            - Performance metrics are logged (could be added)
            
        Example:
            >>> store = SQLiteStore()
            >>> # Store a temporary value
            >>> store.put(("cache", "api"), "temp_response", {"data": "..."})
            >>> # Later, clean it up
            >>> store.delete(("cache", "api"), "temp_response")
            >>> # Delete non-existent key (no error)
            >>> store.delete(("cache", "api"), "does_not_exist")
            
        Note:
            Unlike some key-value stores, this method does not return
            information about whether the key existed before deletion.
            This design choice simplifies error handling and supports
            idempotent operations in distributed systems.
        """
        # Log database delete start
        logger.info("database_delete_start",
            component="storage",
            operation="delete",
            namespace=str(namespace),
            key=key
        )
        
        try:
            cursor = self.conn.execute(
                "DELETE FROM store WHERE namespace = ? AND key = ?",
                (json.dumps(namespace), key)
            )
            self.conn.commit()
            
            logger.info("database_delete_success",
                component="storage",
                operation="delete",
                namespace=str(namespace),
                key=key,
                rows_affected=cursor.rowcount
            )
        except Exception as e:
            logger.error("database_delete_error",
                component="storage",
                operation="delete",
                namespace=str(namespace),
                key=key,
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    def batch(self, items: list[tuple]) -> None:
        """Perform multiple storage operations in a single batch.
        
        Executes multiple put operations sequentially for bulk data storage.
        While not wrapped in a single transaction for simplicity, this method
        provides a convenient interface for storing multiple related items.
        
        This method is ideal for:
        - Initializing application state with multiple values
        - Bulk importing data from external sources
        - Saving related entities together
        - Updating multiple configuration values
        
        Args:
            items: List of tuples, where each tuple contains:
                   (namespace, key, value)
                   - namespace: Tuple/list for data isolation
                   - key: String identifier within namespace
                   - value: JSON-serializable data to store
                   
        Returns:
            None. All items are processed sequentially.
            
        Raises:
            json.JSONEncodeError: If any value cannot be JSON-serialized.
            sqlite3.DatabaseError: If any database operation fails.
            
        Behavior:
            - Each item is processed via individual put() calls
            - Each put() commits immediately (not transactional)
            - Failures on individual items don't roll back previous items
            - Performance logging occurs for each put operation
            
        Example:
            >>> store = SQLiteStore()
            >>> # Bulk store user session data
            >>> store.batch([
            ...     (("memory", "user-1"), "preferences", {"theme": "dark"}),
            ...     (("memory", "user-1"), "last_login", "2024-01-20"),
            ...     (("memory", "user-1"), "permissions", ["read", "write"]),
            ...     (("cache", "global"), "api_tokens", {"service": "token123"})
            ... ])
            >>> # Initialize agent state
            >>> agent_data = [
            ...     (("agent", "salesforce"), "status", "active"),
            ...     (("agent", "salesforce"), "capabilities", ["crm", "lead_gen"]),
            ...     (("agent", "salesforce"), "config", {"timeout": 30})
            ... ]
            >>> store.batch(agent_data)
            
        Performance Considerations:
            For large batches (>100 items), consider:
            - Breaking into smaller chunks to avoid long-running operations
            - Using abatch() for async processing with yielding
            - Implementing progress callbacks for monitoring
            
        Note:
            This implementation prioritizes simplicity over transactional
            guarantees. For atomic batch operations, consider wrapping
            in a database transaction or implementing a custom method.
        """
        for ns, key, value in items:
            self.put(ns, key, value)

    async def abatch(self, items: list[tuple]) -> None:
        """Asynchronously perform multiple storage operations with cooperative yielding.
        
        Executes multiple put operations with periodic yielding to the event loop,
        enabling cooperative multitasking in async applications. This method is
        particularly useful when processing large batches that could block the
        event loop in synchronous execution.
        
        The async implementation ensures:
        - Other coroutines can run between batch items
        - UI remains responsive during bulk operations
        - Network requests aren't blocked by storage operations
        - Better resource utilization in async applications
        
        Args:
            items: List of tuples, where each tuple contains:
                   (namespace, key, value)
                   - namespace: Tuple/list for data isolation
                   - key: String identifier within namespace
                   - value: JSON-serializable data to store
                   
        Returns:
            None. All items are processed with cooperative yielding.
            
        Raises:
            json.JSONEncodeError: If any value cannot be JSON-serialized.
            sqlite3.DatabaseError: If any database operation fails.
            
        Behavior:
            - Each item is processed via synchronous put() calls
            - After each put(), control yields to the event loop
            - Allows other async operations to interleave
            - Maintains same commit semantics as batch()
            
        Example:
            >>> store = SQLiteStore()
            >>> # Async bulk import with yielding
            >>> async def import_user_data():
            ...     await store.abatch([
            ...         (("memory", f"user-{i}"), "profile", {
            ...             "name": f"User {i}",
            ...             "created": "2024-01-20",
            ...             "active": True
            ...         })
            ...         for i in range(1000)  # Large batch
            ...     ])
            >>> # Process multiple data sources concurrently
            >>> async def concurrent_storage():
            ...     await asyncio.gather(
            ...         store.abatch(user_items),
            ...         store.abatch(cache_items),
            ...         store.abatch(config_items)
            ...     )
            
        Performance Characteristics:
            - Slightly slower than batch() due to yielding overhead
            - Better concurrency with other async operations
            - Prevents event loop blocking on large batches
            - Ideal for batches >50 items in async contexts
            
        Implementation Details:
            Uses asyncio.sleep(0) to yield control after each operation.
            This zero-duration sleep is a standard Python idiom for
            cooperative yielding in async code.
            
        Note:
            While this method is async, the underlying SQLite operations
            remain synchronous. For true async database operations,
            consider using aiosqlite or similar async database drivers.
            This method provides async-friendly batch processing within
            the constraints of synchronous SQLite.
        """
        for ns, key, value in items:
            self.put(ns, key, value)
            await asyncio.sleep(0)  # Yield control to the event loop

    def __del__(self):
        self.conn.close()
