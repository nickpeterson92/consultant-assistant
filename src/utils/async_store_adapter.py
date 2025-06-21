"""
Async Store Adapter for Multi-Agent System
Provides async operations for the existing SQLiteStore with minimal changes
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import functools

from .store.sqlite_store import SQLiteStore
from .async_sqlite import get_async_store

logger = logging.getLogger(__name__)

class AsyncStoreAdapter:
    """Adapter to make existing SQLiteStore operations async"""
    
    def __init__(self, db_path: str = "memory_store.db", use_async: bool = True):
        self.db_path = db_path
        self.use_async = use_async
        
        if use_async:
            # Use the new async store
            self._async_store = get_async_store(db_path)
            self._sync_store = None
            self._executor = None
        else:
            # Use thread pool for sync store
            self._sync_store = SQLiteStore(db_path)
            self._async_store = None
            self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="sqlite_")
    
    async def get(self, namespace: Tuple[str, ...], key: str) -> Optional[Any]:
        """Get a value from the store asynchronously"""
        if self.use_async:
            return await self._async_store.get(namespace, key)
        else:
            loop = asyncio.get_event_loop()
            func = functools.partial(self._sync_store.get, namespace, key)
            return await loop.run_in_executor(self._executor, func)
    
    async def put(self, namespace: Tuple[str, ...], key: str, value: Any) -> None:
        """Put a value into the store asynchronously"""
        if self.use_async:
            await self._async_store.put(namespace, key, value)
        else:
            loop = asyncio.get_event_loop()
            func = functools.partial(self._sync_store.put, namespace, key, value)
            await loop.run_in_executor(self._executor, func)
    
    async def delete(self, namespace: Tuple[str, ...], key: str) -> None:
        """Delete a value from the store asynchronously"""
        if self.use_async:
            await self._async_store.delete(namespace, key)
        else:
            loop = asyncio.get_event_loop()
            func = functools.partial(self._sync_store.delete, namespace, key)
            await loop.run_in_executor(self._executor, func)
    
    async def list_keys(self, namespace: Tuple[str, ...]) -> List[str]:
        """List all keys in a namespace asynchronously"""
        if self.use_async:
            return await self._async_store.list_keys(namespace)
        else:
            loop = asyncio.get_event_loop()
            func = functools.partial(self._sync_store.list, namespace)
            return await loop.run_in_executor(self._executor, func)
    
    async def batch_get(self, requests: List[Tuple[Tuple[str, ...], str]]) -> List[Optional[Any]]:
        """Get multiple values in a batch"""
        if self.use_async:
            return await self._async_store.batch_get(requests)
        else:
            # For sync store, just do individual gets concurrently
            tasks = []
            for namespace, key in requests:
                task = self.get(namespace, key)
                tasks.append(task)
            return await asyncio.gather(*tasks)
    
    async def batch_put(self, requests: List[Tuple[Tuple[str, ...], str, Any]]) -> None:
        """Put multiple values in a batch"""
        if self.use_async:
            await self._async_store.batch_put(requests)
        else:
            # For sync store, just do individual puts concurrently
            tasks = []
            for namespace, key, value in requests:
                task = self.put(namespace, key, value)
                tasks.append(task)
            await asyncio.gather(*tasks)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get store statistics"""
        if self.use_async:
            return await self._async_store.get_stats()
        else:
            # Basic stats for sync store
            return {
                "store_type": "sync_sqlite",
                "database_path": self.db_path,
                "thread_pool_size": self._executor._max_workers if self._executor else 0
            }
    
    async def close(self):
        """Close the store and clean up resources"""
        if self.use_async and self._async_store:
            await self._async_store.close()
        elif self._executor:
            self._executor.shutdown(wait=True)
    
    def sync_get(self, namespace: Tuple[str, ...], key: str) -> Optional[Any]:
        """Synchronous get for backward compatibility"""
        if self.use_async:
            # For async store, we need to run in a new event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're in an async context, we can't use asyncio.run
                    # This is a fallback that creates a new thread
                    import concurrent.futures
                    import threading
                    
                    def run_async():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            return new_loop.run_until_complete(self._async_store.get(namespace, key))
                        finally:
                            new_loop.close()
                    
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(run_async)
                        return future.result()
                else:
                    return loop.run_until_complete(self._async_store.get(namespace, key))
            except RuntimeError:
                # No event loop, create one
                return asyncio.run(self._async_store.get(namespace, key))
        else:
            return self._sync_store.get(namespace, key)
    
    def sync_put(self, namespace: Tuple[str, ...], key: str, value: Any) -> None:
        """Synchronous put for backward compatibility"""
        if self.use_async:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create a new thread for the async operation
                    import concurrent.futures
                    
                    def run_async():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            return new_loop.run_until_complete(self._async_store.put(namespace, key, value))
                        finally:
                            new_loop.close()
                    
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(run_async)
                        return future.result()
                else:
                    return loop.run_until_complete(self._async_store.put(namespace, key, value))
            except RuntimeError:
                return asyncio.run(self._async_store.put(namespace, key, value))
        else:
            return self._sync_store.put(namespace, key, value)

# Global async store adapter instance
_async_adapter: Optional[AsyncStoreAdapter] = None

def get_async_store_adapter(db_path: str = "memory_store.db", use_async: bool = True) -> AsyncStoreAdapter:
    """Get the global async store adapter instance"""
    global _async_adapter
    if _async_adapter is None:
        _async_adapter = AsyncStoreAdapter(db_path, use_async)
    return _async_adapter

async def close_async_adapter():
    """Close the global async store adapter"""
    global _async_adapter
    if _async_adapter is not None:
        await _async_adapter.close()
        _async_adapter = None