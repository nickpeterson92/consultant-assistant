"""
Simplified Async Store Adapter for Multi-Agent System
Provides async operations for the existing SQLiteStore

This is a minimal implementation that leverages SQLite's built-in
concurrency handling without unnecessary abstractions.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

from .sqlite_store import SQLiteStore
from ..logging.memory_logger import get_memory_logger

logger = logging.getLogger(__name__)
memory_logger = get_memory_logger()


class AsyncStoreAdapter:
    """Simple async adapter for SQLiteStore using thread pool executor."""
    
    def __init__(self, db_path: str = "memory_store.db", max_workers: int = 4):
        self.db_path = db_path
        self.max_workers = max_workers
        
        # Single SQLiteStore instance - SQLite handles concurrency internally
        self._store = SQLiteStore(db_path)
        
        # Thread pool for async operations
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, 
            thread_name_prefix="sqlite_"
        )
        logger.info(f"Initialized AsyncStoreAdapter at {db_path}")
    
    async def get(self, namespace: Tuple[str, ...], key: str) -> Optional[Any]:
        """Get a value from the store asynchronously."""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self._executor, 
            self._store.get, 
            namespace, 
            key
        )
        
        # Log the operation
        user_id = namespace[1] if namespace and len(namespace) > 1 else "unknown"
        memory_logger.log_memory_get(namespace, key, result, 
                                   user_id=user_id,
                                   component="async_store_adapter")
        return result
    
    async def put(self, namespace: Tuple[str, ...], key: str, value: Any) -> None:
        """Put a value into the store asynchronously."""
        # Log before the operation
        user_id = namespace[1] if namespace and len(namespace) > 1 else "unknown"
        memory_logger.log_memory_put(namespace, key, value, 
                                   user_id=user_id,
                                   component="async_store_adapter")
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self._executor,
            self._store.put,
            namespace,
            key,
            value
        )
    
    async def delete(self, namespace: Tuple[str, ...], key: str) -> None:
        """Delete a value from the store asynchronously."""
        # Log before the operation
        user_id = namespace[1] if namespace and len(namespace) > 1 else "unknown"
        memory_logger.log_memory_delete(namespace, key, 
                                      user_id=user_id,
                                      component="async_store_adapter")
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self._executor,
            self._store.delete,
            namespace,
            key
        )
    
    async def list_keys(self, namespace: Tuple[str, ...]) -> List[str]:
        """List all keys in a namespace asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._store.list,
            namespace
        )
    
    async def batch_get(self, requests: List[Tuple[Tuple[str, ...], str]]) -> List[Optional[Any]]:
        """Get multiple values in a batch."""
        # Simple concurrent execution
        tasks = [self.get(namespace, key) for namespace, key in requests]
        return await asyncio.gather(*tasks)
    
    async def batch_put(self, requests: List[Tuple[Tuple[str, ...], str, Any]]) -> None:
        """Put multiple values in a batch."""
        # Simple concurrent execution
        tasks = [self.put(namespace, key, value) for namespace, key, value in requests]
        await asyncio.gather(*tasks)
    
    async def close(self):
        """Close the store and clean up resources."""
        logger.info("Closing AsyncStoreAdapter")
        self._executor.shutdown(wait=True)
        logger.info("AsyncStoreAdapter closed")
    
    # Sync methods for backward compatibility
    def sync_get(self, namespace: Tuple[str, ...], key: str) -> Optional[Any]:
        """Synchronous get for backward compatibility."""
        result = self._store.get(namespace, key)
        
        # Log the operation
        user_id = namespace[1] if namespace and len(namespace) > 1 else "unknown"
        memory_logger.log_memory_get(namespace, key, result, 
                                   user_id=user_id,
                                   component="async_store_adapter_sync")
        return result
    
    def sync_put(self, namespace: Tuple[str, ...], key: str, value: Any) -> None:
        """Synchronous put for backward compatibility."""
        # Log before the operation
        user_id = namespace[1] if namespace and len(namespace) > 1 else "unknown"
        memory_logger.log_memory_put(namespace, key, value, 
                                   user_id=user_id,
                                   component="async_store_adapter_sync")
        
        self._store.put(namespace, key, value)


# Global async store adapter instance
_async_adapter: Optional[AsyncStoreAdapter] = None


def get_async_store_adapter(db_path: str = "memory_store.db", **kwargs) -> AsyncStoreAdapter:
    """
    Get the global async store adapter instance.
    
    Args:
        db_path: Path to SQLite database file
        **kwargs: Ignored for compatibility
        
    Returns:
        AsyncStoreAdapter instance
    """
    global _async_adapter
    if _async_adapter is None:
        _async_adapter = AsyncStoreAdapter(db_path=db_path)
        logger.info(f"Created global async store adapter: {db_path}")
    return _async_adapter


async def close_async_adapter():
    """Close the global async store adapter."""
    global _async_adapter
    if _async_adapter is not None:
        await _async_adapter.close()
        _async_adapter = None
        logger.info("Closed global async store adapter")