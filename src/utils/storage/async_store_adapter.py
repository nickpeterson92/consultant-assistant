"""
Simplified Async Store Adapter for Multi-Agent System
Provides async operations for the existing SQLiteStore

This is a minimal implementation that leverages SQLite's built-in
concurrency handling without unnecessary abstractions.
"""

import asyncio
import threading
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

from .sqlite_store import SQLiteStore
from ..logging import get_smart_logger, log_execution

# Initialize logger
logger = get_smart_logger("storage")


class AsyncStoreAdapter:
    """Simple async adapter for SQLiteStore using thread pool executor."""
    
    def __init__(self, db_path: str = None, max_workers: int = None):
        from ..config import config
        db_config = config
        
        self.db_path = db_path or db_config.db_path
        self.max_workers = max_workers or db_config.get('database.thread_pool_size', 4)
        
        # Thread-local storage for SQLite connections
        self._thread_local = threading.local()
        
        # Thread pool for async operations
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_workers, 
            thread_name_prefix=db_config.get('database.thread_prefix', 'sqlite_')
        )
        logger.info(f"Initialized AsyncStoreAdapter at {self.db_path}")
    
    def _get_store(self) -> SQLiteStore:
        """Get thread-local SQLiteStore instance."""
        if not hasattr(self._thread_local, 'store'):
            self._thread_local.store = SQLiteStore(self.db_path)
            logger.info("Created thread-local SQLiteStore",
                thread_id=threading.current_thread().ident,
                db_path=self.db_path
            )
        return self._thread_local.store
    
    @log_execution(component="storage", operation="async_get")
    async def get(self, namespace: Tuple[str, ...], key: str) -> Optional[Any]:
        """Get a value from the store asynchronously."""
        user_id = namespace[1] if namespace and len(namespace) > 1 else "unknown"
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self._executor, 
            lambda: self._get_store().get(namespace, key)
        )
        
        logger.info("async_storage_read_success",
            namespace=str(namespace),
            key=key,
            user_id=user_id,
            found=result is not None,
            value_size=len(str(result)) if result else 0
        )
        
        return result
    
    @log_execution(component="storage", operation="async_put")
    async def put(self, namespace: Tuple[str, ...], key: str, value: Any) -> None:
        """Put a value into the store asynchronously."""
        user_id = namespace[1] if namespace and len(namespace) > 1 else "unknown"
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self._executor,
            lambda: self._get_store().put(namespace, key, value)
        )
        
        logger.info("async_storage_write_success",
            namespace=str(namespace),
            key=key,
            user_id=user_id,
            value_size=len(str(value))
        )
    
    @log_execution(component="storage", operation="async_delete")
    async def delete(self, namespace: Tuple[str, ...], key: str) -> None:
        """Delete a value from the store asynchronously."""
        user_id = namespace[1] if namespace and len(namespace) > 1 else "unknown"
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self._executor,
            lambda: self._get_store().delete(namespace, key)
        )
        
        logger.info("async_storage_delete_success",
            namespace=str(namespace),
            key=key,
            user_id=user_id
        )
    
    @log_execution(component="storage", operation="list_keys")
    async def list_keys(self, namespace: Tuple[str, ...]) -> List[str]:
        """List all keys in a namespace asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            lambda: self._get_store().list(namespace)
        )
    
    @log_execution(component="storage", operation="batch_get")
    async def batch_get(self, requests: List[Tuple[Tuple[str, ...], str]]) -> List[Optional[Any]]:
        """Get multiple values in a batch."""
        # Simple concurrent execution
        tasks = [self.get(namespace, key) for namespace, key in requests]
        return await asyncio.gather(*tasks)
    
    @log_execution(component="storage", operation="batch_put")
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
        result = self._get_store().get(namespace, key)
        
        # Log the operation
        user_id = namespace[1] if namespace and len(namespace) > 1 else "unknown"
        logger.info("memory_get", namespace=namespace, key=key, result=result, 
                   user_id=user_id, sync_context="backward_compatibility")
        return result
    
    def sync_put(self, namespace: Tuple[str, ...], key: str, value: Any) -> None:
        """Synchronous put for backward compatibility."""
        # Log before the operation
        user_id = namespace[1] if namespace and len(namespace) > 1 else "unknown"
        logger.info("memory_put", namespace=namespace, key=key, value=value, 
                   user_id=user_id, sync_context="backward_compatibility")
        
        self._get_store().put(namespace, key, value)


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