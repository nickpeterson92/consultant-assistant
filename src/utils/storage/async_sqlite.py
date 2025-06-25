"""
Async SQLite Operations for Multi-Agent System
Provides non-blocking database operations with connection pooling
"""

import aiosqlite
import asyncio
import json
import logging
from typing import Dict, Any, Optional, List, Union, Tuple
from pathlib import Path
from contextlib import asynccontextmanager
from dataclasses import dataclass
import weakref
import time

from ..logging import get_logger

logger = get_logger()

@dataclass
class ConnectionConfig:
    """Configuration for SQLite connection"""
    database_path: str
    timeout: float = 30.0
    check_same_thread: bool = False
    enable_wal_mode: bool = True
    enable_foreign_keys: bool = True
    cache_size: int = -2000  # 2MB cache
    synchronous: str = "NORMAL"  # FULL, NORMAL, OFF

class AsyncSQLitePool:
    """Async SQLite connection pool for high-performance database operations"""
    
    def __init__(self, config: ConnectionConfig, pool_size: int = 5):
        self.config = config
        self.pool_size = pool_size
        self._pool: asyncio.Queue = asyncio.Queue(maxsize=pool_size)
        self._created_connections = 0
        self._initialized = False
        self._lock = asyncio.Lock()
        
        # Track active connections for cleanup
        self._active_connections = weakref.WeakSet()
    
    async def initialize(self):
        """Initialize the connection pool"""
        if self._initialized:
            return
        
        async with self._lock:
            if self._initialized:
                return
            
            # Ensure database directory exists
            Path(self.config.database_path).parent.mkdir(parents=True, exist_ok=True)
            
            self._initialized = True
            logger.info("sqlite_pool_initialized",
                component="storage",
                operation="init"
            )
    
    async def _create_connection(self) -> aiosqlite.Connection:
        """Create a new SQLite connection with optimal settings"""
        # aiosqlite.connect returns a coroutine that needs to be awaited
        conn = await aiosqlite.connect(
            self.config.database_path,
            timeout=self.config.timeout,
            check_same_thread=self.config.check_same_thread
        )
        
        # Configure for performance
        await conn.execute(f"PRAGMA cache_size = {self.config.cache_size}")
        await conn.execute(f"PRAGMA synchronous = {self.config.synchronous}")
        
        if self.config.enable_wal_mode:
            await conn.execute("PRAGMA journal_mode = WAL")
        
        if self.config.enable_foreign_keys:
            await conn.execute("PRAGMA foreign_keys = ON")
        
        # Enable query optimization
        await conn.execute("PRAGMA optimize")
        
        await conn.commit()
        
        self._active_connections.add(conn)
        self._created_connections += 1
        
        return conn
    
    @asynccontextmanager
    async def get_connection(self):
        """Get a connection from the pool"""
        if not self._initialized:
            await self.initialize()
        
        # For simplicity, always create a new connection
        # In production, you'd want proper pooling
        conn = await self._create_connection()
        
        try:
            yield conn
        finally:
            await conn.close()
    
    async def close_all(self):
        """Close all connections in the pool"""
        logger.info("Closing SQLite connection pool")
        
        # Close pooled connections
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                await conn.close()
            except asyncio.QueueEmpty:
                break
        
        # Close any remaining active connections
        for conn in list(self._active_connections):
            try:
                await conn.close()
            except Exception as e:
                logger.warning("connection_close_error",
                    component="storage",
                    operation="close",
                    error=str(e),
                    error_type=type(e).__name__
                )
        
        self._initialized = False

class AsyncSQLiteStore:
    """Async version of SQLite store for non-blocking operations"""
    
    def __init__(self, database_path: str = "memory_store.db", pool_size: int = 5):
        config = ConnectionConfig(database_path=database_path)
        self.pool = AsyncSQLitePool(config, pool_size)
        self._schema_initialized = False
    
    async def _initialize_schema(self, conn):
        """Initialize the database schema for a connection"""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS key_value_store (
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (namespace, key)
            )
        """)
        
        # Create indexes for performance
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_namespace 
            ON key_value_store(namespace)
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_updated_at 
            ON key_value_store(updated_at)
        """)
        
        # Update trigger for updated_at
        await conn.execute("""
            CREATE TRIGGER IF NOT EXISTS update_timestamp 
            AFTER UPDATE ON key_value_store
            BEGIN
                UPDATE key_value_store 
                SET updated_at = CURRENT_TIMESTAMP 
                WHERE namespace = NEW.namespace AND key = NEW.key;
            END
        """)
        
        await conn.commit()
        logger.debug("SQLite schema initialized")
    
    async def get(self, namespace: Tuple[str, ...], key: str) -> Optional[Any]:
        """Get a value from the store"""
        namespace_str = json.dumps(namespace)
        
        async with self.pool.get_connection() as conn:
            await self._initialize_schema(conn)
            async with conn.execute(
                "SELECT value FROM key_value_store WHERE namespace = ? AND key = ?",
                (namespace_str, key)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    try:
                        return json.loads(row[0])
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to decode JSON for {namespace}:{key}: {e}")
                        return None
                return None
    
    async def put(self, namespace: Tuple[str, ...], key: str, value: Any) -> None:
        """Put a value into the store"""
# Schema initialization now happens per connection
        
        namespace_str = json.dumps(namespace)
        value_str = json.dumps(value)
        
        async with self.pool.get_connection() as conn:
            await conn.execute(
                """INSERT OR REPLACE INTO key_value_store (namespace, key, value) 
                   VALUES (?, ?, ?)""",
                (namespace_str, key, value_str)
            )
            await conn.commit()
    
    async def delete(self, namespace: Tuple[str, ...], key: str) -> None:
        """Delete a value from the store"""
        namespace_str = json.dumps(namespace)
        
        async with self.pool.get_connection() as conn:
            await self._initialize_schema(conn)
            await conn.execute(
                "DELETE FROM key_value_store WHERE namespace = ? AND key = ?",
                (namespace_str, key)
            )
            await conn.commit()
    
    async def list_keys(self, namespace: Tuple[str, ...]) -> List[str]:
        """List all keys in a namespace"""
        namespace_str = json.dumps(namespace)
        
        async with self.pool.get_connection() as conn:
            await self._initialize_schema(conn)
            async with conn.execute(
                "SELECT key FROM key_value_store WHERE namespace = ?",
                (namespace_str,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
    
    async def list_namespaces(self) -> List[Tuple[str, ...]]:
        """List all namespaces"""
# Schema initialization now happens per connection
        
        async with self.pool.get_connection() as conn:
            async with conn.execute(
                "SELECT DISTINCT namespace FROM key_value_store"
            ) as cursor:
                rows = await cursor.fetchall()
                namespaces = []
                for row in rows:
                    try:
                        namespace = tuple(json.loads(row[0]))
                        namespaces.append(namespace)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid namespace JSON: {row[0]}")
                return namespaces
    
    async def clear_namespace(self, namespace: Tuple[str, ...]) -> None:
        """Clear all keys in a namespace"""
        namespace_str = json.dumps(namespace)
        
        async with self.pool.get_connection() as conn:
            await self._initialize_schema(conn)
            await conn.execute(
                "DELETE FROM key_value_store WHERE namespace = ?",
                (namespace_str,)
            )
            await conn.commit()
    
    async def batch_get(self, requests: List[Tuple[Tuple[str, ...], str]]) -> List[Optional[Any]]:
        """Get multiple values in a single transaction"""
# Schema initialization now happens per connection
        
        if not requests:
            return []
        
        async with self.pool.get_connection() as conn:
            results = []
            for namespace, key in requests:
                namespace_str = json.dumps(namespace)
                async with conn.execute(
                    "SELECT value FROM key_value_store WHERE namespace = ? AND key = ?",
                    (namespace_str, key)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        try:
                            results.append(json.loads(row[0]))
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to decode JSON for {namespace}:{key}: {e}")
                            results.append(None)
                    else:
                        results.append(None)
            
            return results
    
    async def batch_put(self, requests: List[Tuple[Tuple[str, ...], str, Any]]) -> None:
        """Put multiple values in a single transaction"""
# Schema initialization now happens per connection
        
        if not requests:
            return
        
        async with self.pool.get_connection() as conn:
            data = []
            for namespace, key, value in requests:
                namespace_str = json.dumps(namespace)
                value_str = json.dumps(value)
                data.append((namespace_str, key, value_str))
            
            await conn.executemany(
                """INSERT OR REPLACE INTO key_value_store (namespace, key, value) 
                   VALUES (?, ?, ?)""",
                data
            )
            await conn.commit()
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
# Schema initialization now happens per connection
        
        async with self.pool.get_connection() as conn:
            # Get row count
            async with conn.execute(
                "SELECT COUNT(*) FROM key_value_store"
            ) as cursor:
                row_count = (await cursor.fetchone())[0]
            
            # Get namespace count
            async with conn.execute(
                "SELECT COUNT(DISTINCT namespace) FROM key_value_store"
            ) as cursor:
                namespace_count = (await cursor.fetchone())[0]
            
            # Get database size
            async with conn.execute("PRAGMA page_size") as cursor:
                page_size = (await cursor.fetchone())[0]
            
            async with conn.execute("PRAGMA page_count") as cursor:
                page_count = (await cursor.fetchone())[0]
            
            database_size = page_size * page_count
            
            return {
                "row_count": row_count,
                "namespace_count": namespace_count,
                "database_size_bytes": database_size,
                "pool_size": self.pool.pool_size,
                "created_connections": self.pool._created_connections
            }
    
    async def close(self):
        """Close the store and all connections"""
        await self.pool.close_all()

# Global async store instance
_async_store: Optional[AsyncSQLiteStore] = None

def get_async_store(database_path: str = "memory_store.db", pool_size: int = 5) -> AsyncSQLiteStore:
    """Get the global async SQLite store instance"""
    global _async_store
    if _async_store is None:
        _async_store = AsyncSQLiteStore(database_path, pool_size)
    return _async_store

async def close_async_store():
    """Close the global async store"""
    global _async_store
    if _async_store is not None:
        await _async_store.close()
        _async_store = None