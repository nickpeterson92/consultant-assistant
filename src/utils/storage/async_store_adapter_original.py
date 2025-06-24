"""
Async Store Adapter for Multi-Agent System
Provides async operations for the existing SQLiteStore with minimal changes

Phase 1 Enhanced Features:
- Comprehensive error handling and retry logic  
- Performance monitoring and metrics
- Connection pooling for underlying sync store
- Circuit breaker pattern for resilience
- Resource leak prevention
"""

import asyncio
import logging
import time
import sqlite3
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from contextlib import contextmanager
import threading

from .sqlite_store import SQLiteStore
from .async_sqlite import get_async_store
from ..logging import get_summary_logger
from ..logging.memory_logger import get_memory_logger

logger = logging.getLogger(__name__)
memory_logger = get_memory_logger()

@dataclass
class StoreMetrics:
    """Performance metrics for store operations"""
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    avg_response_time: float = 0.0
    total_response_time: float = 0.0
    operations_per_second: float = 0.0
    last_operation_time: float = 0.0
    connection_pool_size: int = 0
    active_connections: int = 0

class CircuitBreaker:
    """Circuit breaker pattern for database operations"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self._lock = threading.Lock()
    
    def can_execute(self) -> bool:
        with self._lock:
            if self.state == 'CLOSED':
                return True
            elif self.state == 'OPEN':
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = 'HALF_OPEN'
                    return True
                return False
            else:  # HALF_OPEN
                return True
    
    def record_success(self):
        with self._lock:
            self.failure_count = 0
            self.state = 'CLOSED'
    
    def record_failure(self):
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'

class ConnectionPool:
    """Simple connection pool for SQLite connections"""
    
    def __init__(self, db_path: str, max_connections: int = 10):
        self.db_path = db_path
        self.max_connections = max_connections
        self._pool = []
        self._lock = threading.Lock()
        self._created_connections = 0
    
    @contextmanager
    def get_connection(self):
        conn = None
        try:
            with self._lock:
                if self._pool:
                    conn = self._pool.pop()
                elif self._created_connections < self.max_connections:
                    conn = sqlite3.connect(self.db_path, check_same_thread=False)
                    conn.execute("PRAGMA journal_mode=WAL")
                    self._created_connections += 1
                else:
                    # If pool is full, create a temporary connection
                    conn = sqlite3.connect(self.db_path, check_same_thread=False)
            
            yield conn
            
        except Exception as e:
            if conn:
                conn.close()
            raise e
        finally:
            if conn:
                with self._lock:
                    if len(self._pool) < self.max_connections:
                        self._pool.append(conn)
                    else:
                        conn.close()
    
    def close_all(self):
        with self._lock:
            for conn in self._pool:
                conn.close()
            self._pool.clear()
            self._created_connections = 0

class AsyncStoreAdapter:
    """Enhanced Adapter to make existing SQLiteStore operations async with monitoring and resilience"""
    
    def __init__(self, db_path: str = "memory_store.db", use_async: bool = False, 
                 max_workers: int = 4, max_connections: int = 10,
                 enable_circuit_breaker: bool = True):
        self.db_path = db_path
        self.use_async = use_async
        self.max_workers = max_workers
        self.max_connections = max_connections
        
        # Performance monitoring
        self.metrics = StoreMetrics()
        self._metrics_lock = threading.Lock()
        
        # Circuit breaker for resilience
        self.circuit_breaker = CircuitBreaker() if enable_circuit_breaker else None
        
        if use_async:
            # Use the new async store
            try:
                self._async_store = get_async_store(db_path)
                self._sync_store = None
                self._executor = None
                self._connection_pool = None
                logger.info(f"Initialized async SQLite store at {db_path}")
            except Exception as e:
                logger.error(f"Failed to initialize async store: {e}, falling back to sync")
                self.use_async = False
                self._init_sync_store()
        else:
            self._init_sync_store()
    
    def _init_sync_store(self):
        """Initialize sync store with enhanced features"""
        # Create a template store for connection management
        self._sync_store_template = SQLiteStore(self.db_path)
        self._async_store = None
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_workers, 
            thread_name_prefix="sqlite_"
        )
        self._connection_pool = ConnectionPool(self.db_path, self.max_connections)
        logger.info(f"Initialized sync SQLite store with thread pool at {self.db_path}")
    
    def _get_thread_safe_store(self):
        """Get a thread-safe store instance for the current thread"""
        return self._sync_store_template.get_connection(self.db_path)
    
    def _record_operation(self, start_time: float, success: bool):
        """Record operation metrics"""
        with self._metrics_lock:
            duration = time.time() - start_time
            self.metrics.total_operations += 1
            self.metrics.total_response_time += duration
            self.metrics.avg_response_time = self.metrics.total_response_time / self.metrics.total_operations
            self.metrics.last_operation_time = time.time()
            
            if success:
                self.metrics.successful_operations += 1
                if self.circuit_breaker:
                    self.circuit_breaker.record_success()
            else:
                self.metrics.failed_operations += 1
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure()
            
            # Calculate operations per second (last 60 seconds)
            if self.metrics.total_operations > 0:
                time_window = min(60, time.time() - (self.metrics.last_operation_time - duration))
                if time_window > 0:
                    self.metrics.operations_per_second = 1.0 / time_window
    
    async def _execute_with_retry(self, operation, *args, max_retries: int = 3, 
                                  backoff_factor: float = 1.5):
        """Execute operation with retry logic and circuit breaker"""
        if self.circuit_breaker and not self.circuit_breaker.can_execute():
            raise Exception("Circuit breaker is OPEN - database operations temporarily disabled")
        
        last_exception = None
        for attempt in range(max_retries):
            start_time = time.time()
            try:
                result = await operation(*args)
                self._record_operation(start_time, True)
                return result
            except Exception as e:
                last_exception = e
                self._record_operation(start_time, False)
                
                if attempt < max_retries - 1:
                    wait_time = backoff_factor ** attempt
                    logger.warning(f"Database operation failed (attempt {attempt + 1}), retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Database operation failed after {max_retries} attempts: {e}")
        
        raise last_exception
    
    async def get(self, namespace: Tuple[str, ...], key: str) -> Optional[Any]:
        """Get a value from the store asynchronously with retry and monitoring"""
        async def _get_operation():
            if self.use_async:
                result = await self._async_store.get(namespace, key)
            else:
                loop = asyncio.get_event_loop()
                def _thread_safe_get():
                    store = self._get_thread_safe_store()
                    return store.get(namespace, key)
                result = await loop.run_in_executor(self._executor, _thread_safe_get)
            
            # Log the memory operation with user_id from namespace
            user_id = namespace[1] if namespace and len(namespace) > 1 else "unknown"
            memory_logger.log_memory_get(namespace, key, result, 
                                       user_id=user_id,
                                       component="async_store_adapter")
            return result
        
        return await self._execute_with_retry(_get_operation)
    
    async def put(self, namespace: Tuple[str, ...], key: str, value: Any) -> None:
        """Put a value into the store asynchronously with retry and monitoring"""
        # Log before the operation with user_id from namespace
        user_id = namespace[1] if namespace and len(namespace) > 1 else "unknown"
        memory_logger.log_memory_put(namespace, key, value, 
                                   user_id=user_id,
                                   component="async_store_adapter")
        
        async def _put_operation():
            if self.use_async:
                await self._async_store.put(namespace, key, value)
            else:
                loop = asyncio.get_event_loop()
                def _thread_safe_put():
                    store = self._get_thread_safe_store()
                    return store.put(namespace, key, value)
                await loop.run_in_executor(self._executor, _thread_safe_put)
        
        await self._execute_with_retry(_put_operation)
    
    async def delete(self, namespace: Tuple[str, ...], key: str) -> None:
        """Delete a value from the store asynchronously with retry and monitoring"""
        # Log before the operation with user_id from namespace
        user_id = namespace[1] if namespace and len(namespace) > 1 else "unknown"
        memory_logger.log_memory_delete(namespace, key, 
                                      user_id=user_id,
                                      component="async_store_adapter")
        
        async def _delete_operation():
            if self.use_async:
                await self._async_store.delete(namespace, key)
            else:
                loop = asyncio.get_event_loop()
                def _thread_safe_delete():
                    store = self._get_thread_safe_store()
                    return store.delete(namespace, key)
                await loop.run_in_executor(self._executor, _thread_safe_delete)
        
        await self._execute_with_retry(_delete_operation)
    
    async def list_keys(self, namespace: Tuple[str, ...]) -> List[str]:
        """List all keys in a namespace asynchronously with retry and monitoring"""
        async def _list_operation():
            if self.use_async:
                return await self._async_store.list_keys(namespace)
            else:
                loop = asyncio.get_event_loop()
                def _thread_safe_list():
                    store = self._get_thread_safe_store()
                    return store.list(namespace)
                return await loop.run_in_executor(self._executor, _thread_safe_list)
        
        return await self._execute_with_retry(_list_operation)
    
    async def batch_get(self, requests: List[Tuple[Tuple[str, ...], str]]) -> List[Optional[Any]]:
        """Get multiple values in a batch with retry and monitoring"""
        async def _batch_get_operation():
            if self.use_async:
                return await self._async_store.batch_get(requests)
            else:
                # For sync store, do individual gets concurrently with semaphore to limit concurrency
                semaphore = asyncio.Semaphore(self.max_workers)
                
                async def _get_with_semaphore(namespace, key):
                    async with semaphore:
                        return await self.get(namespace, key)
                
                tasks = [_get_with_semaphore(namespace, key) for namespace, key in requests]
                return await asyncio.gather(*tasks)
        
        return await self._execute_with_retry(_batch_get_operation)
    
    async def batch_put(self, requests: List[Tuple[Tuple[str, ...], str, Any]]) -> None:
        """Put multiple values in a batch with retry and monitoring"""
        async def _batch_put_operation():
            if self.use_async:
                await self._async_store.batch_put(requests)
            else:
                # For sync store, do individual puts concurrently with semaphore to limit concurrency
                semaphore = asyncio.Semaphore(self.max_workers)
                
                async def _put_with_semaphore(namespace, key, value):
                    async with semaphore:
                        await self.put(namespace, key, value)
                
                tasks = [_put_with_semaphore(namespace, key, value) for namespace, key, value in requests]
                await asyncio.gather(*tasks)
        
        await self._execute_with_retry(_batch_put_operation)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive store statistics and performance metrics"""
        with self._metrics_lock:
            base_stats = {
                "store_type": "async_sqlite" if self.use_async else "sync_sqlite_threadpool",
                "database_path": self.db_path,
                "total_operations": self.metrics.total_operations,
                "successful_operations": self.metrics.successful_operations,
                "failed_operations": self.metrics.failed_operations,
                "success_rate": (self.metrics.successful_operations / max(self.metrics.total_operations, 1)) * 100,
                "avg_response_time_ms": self.metrics.avg_response_time * 1000,
                "operations_per_second": self.metrics.operations_per_second,
                "last_operation_time": self.metrics.last_operation_time
            }
            
            if self.use_async and self._async_store:
                try:
                    async_stats = await self._async_store.get_stats()
                    base_stats.update(async_stats)
                except Exception as e:
                    logger.warning(f"Failed to get async store stats: {e}")
            else:
                base_stats.update({
                    "thread_pool_size": self.max_workers,
                    "max_connections": self.max_connections,
                    "connection_pool_active": len(self._connection_pool._pool) if self._connection_pool else 0
                })
            
            if self.circuit_breaker:
                base_stats.update({
                    "circuit_breaker_state": self.circuit_breaker.state,
                    "circuit_breaker_failures": self.circuit_breaker.failure_count,
                    "circuit_breaker_last_failure": self.circuit_breaker.last_failure_time
                })
            
            return base_stats
    
    async def close(self):
        """Close the store and clean up all resources properly"""
        logger.info("Closing AsyncStoreAdapter and cleaning up resources")
        
        try:
            if self.use_async and self._async_store:
                await self._async_store.close()
                logger.info("Closed async SQLite store")
            
            if self._executor:
                self._executor.shutdown(wait=True)
                logger.info("Shut down thread pool executor")
            
            if self._connection_pool:
                self._connection_pool.close_all()
                logger.info("Closed connection pool")
            
            # Log final metrics
            final_stats = await self.get_stats()
            logger.info(f"Final store statistics: {final_stats}")
            
        except Exception as e:
            logger.error(f"Error during store cleanup: {e}")
            raise
    
    def reset_metrics(self):
        """Reset performance metrics"""
        with self._metrics_lock:
            self.metrics = StoreMetrics()
            if self.circuit_breaker:
                self.circuit_breaker.failure_count = 0
                self.circuit_breaker.state = 'CLOSED'
            logger.info("Reset store metrics and circuit breaker")
    
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
                        result = future.result()
                else:
                    result = loop.run_until_complete(self._async_store.get(namespace, key))
            except RuntimeError:
                # No event loop, create one
                result = asyncio.run(self._async_store.get(namespace, key))
        else:
            # Use thread-safe store instance
            store = self._get_thread_safe_store()
            result = store.get(namespace, key)
        
        # Log the memory operation with user_id from namespace
        user_id = namespace[1] if namespace and len(namespace) > 1 else "unknown"
        memory_logger.log_memory_get(namespace, key, result, 
                                   user_id=user_id,
                                   component="async_store_adapter_sync")
        return result
    
    def sync_put(self, namespace: Tuple[str, ...], key: str, value: Any) -> None:
        """Synchronous put for backward compatibility"""
        # Log before the operation with user_id from namespace
        user_id = namespace[1] if namespace and len(namespace) > 1 else "unknown"
        memory_logger.log_memory_put(namespace, key, value, 
                                   user_id=user_id,
                                   component="async_store_adapter_sync")
        
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
            # Use thread-safe store instance
            store = self._get_thread_safe_store()
            return store.put(namespace, key, value)

# Global async store adapter instance
_async_adapter: Optional[AsyncStoreAdapter] = None

def get_async_store_adapter(db_path: str = "memory_store.db", use_async: bool = False, 
                           max_workers: int = 4, max_connections: int = 10,
                           enable_circuit_breaker: bool = True) -> AsyncStoreAdapter:
    """
    Get the global async store adapter instance with enhanced default configuration.
    
    Args:
        db_path: Path to SQLite database file
        use_async: Whether to use pure async implementation (False = thread pool, True = aiosqlite)
        max_workers: Number of thread pool workers for sync operations
        max_connections: Maximum connections in connection pool  
        enable_circuit_breaker: Whether to enable circuit breaker pattern
        
    Returns:
        Enhanced AsyncStoreAdapter instance
        
    Note: 
        Defaults to thread pool adapter (use_async=False) for maximum reliability.
        This provides excellent performance for 2-5 agents while being battle-tested.
    """
    global _async_adapter
    if _async_adapter is None:
        _async_adapter = AsyncStoreAdapter(
            db_path=db_path,
            use_async=use_async,
            max_workers=max_workers,
            max_connections=max_connections,
            enable_circuit_breaker=enable_circuit_breaker
        )
        logger.info(f"Created global async store adapter: {_async_adapter.db_path}, "
                   f"async={_async_adapter.use_async}, workers={_async_adapter.max_workers}")
    return _async_adapter

async def close_async_adapter():
    """Close the global async store adapter and clean up all resources"""
    global _async_adapter
    if _async_adapter is not None:
        await _async_adapter.close()
        _async_adapter = None
        logger.info("Closed global async store adapter")

async def get_store_stats() -> Dict[str, Any]:
    """Get statistics from the global store adapter"""
    global _async_adapter
    if _async_adapter is not None:
        return await _async_adapter.get_stats()
    return {"error": "No active store adapter"}

def reset_store_metrics():
    """Reset metrics for the global store adapter"""
    global _async_adapter
    if _async_adapter is not None:
        _async_adapter.reset_metrics()