"""
LLM Response Caching for Multi-Agent System
Provides intelligent caching of LLM responses to reduce costs and improve performance
"""

import asyncio
import hashlib
import json
import time
import logging
from typing import Any, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import weakref

from .async_store_adapter import get_async_store_adapter
from .config import get_llm_config

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """Cache entry for LLM responses"""
    response: Any
    timestamp: float
    ttl: int  # Time to live in seconds
    cost_estimate: Optional[float] = None
    token_count: Optional[int] = None
    model: Optional[str] = None
    
    def is_expired(self) -> bool:
        """Check if the cache entry has expired"""
        return time.time() > (self.timestamp + self.ttl)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CacheEntry':
        """Create from dictionary"""
        return cls(**data)

class LLMCache:
    """Intelligent caching system for LLM responses"""
    
    def __init__(self, namespace: str = "llm_cache", max_cache_size: int = 1000):
        self.namespace = namespace
        self.max_cache_size = max_cache_size
        self.store = get_async_store_adapter()
        self._cache_namespace = ("llm_cache", namespace)
        
        # In-memory cache for frequently accessed items
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._access_count: Dict[str, int] = {}
        self._last_cleanup = time.time()
        
        # Weak reference to allow garbage collection
        self._cache_refs = weakref.WeakSet()
    
    def _generate_cache_key(self, messages: List[Dict[str, Any]], 
                          model: str, temperature: float, 
                          max_tokens: int, **kwargs) -> str:
        """Generate a consistent cache key for the request"""
        # Create a canonical representation
        cache_data = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "kwargs": sorted(kwargs.items())  # Sort for consistency
        }
        
        # Hash the canonical representation
        cache_str = json.dumps(cache_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(cache_str.encode()).hexdigest()
    
    async def get(self, messages: List[Dict[str, Any]], 
                  model: str, temperature: float = 0.1, 
                  max_tokens: int = 4000, **kwargs) -> Optional[Any]:
        """Get cached response if available and not expired"""
        cache_key = self._generate_cache_key(messages, model, temperature, max_tokens, **kwargs)
        
        # Check memory cache first
        if cache_key in self._memory_cache:
            entry = self._memory_cache[cache_key]
            if not entry.is_expired():
                self._access_count[cache_key] = self._access_count.get(cache_key, 0) + 1
                logger.debug(f"Cache hit (memory): {cache_key[:16]}...")
                return entry.response
            else:
                # Remove expired entry
                del self._memory_cache[cache_key]
                if cache_key in self._access_count:
                    del self._access_count[cache_key]
        
        # Check persistent cache
        try:
            cached_data = await self.store.get(self._cache_namespace, cache_key)
            if cached_data:
                entry = CacheEntry.from_dict(cached_data)
                if not entry.is_expired():
                    # Add to memory cache for future access
                    self._memory_cache[cache_key] = entry
                    self._access_count[cache_key] = self._access_count.get(cache_key, 0) + 1
                    logger.debug(f"Cache hit (persistent): {cache_key[:16]}...")
                    return entry.response
                else:
                    # Remove expired entry from persistent storage
                    await self.store.delete(self._cache_namespace, cache_key)
        except Exception as e:
            logger.warning(f"Error reading from cache: {e}")
        
        logger.debug(f"Cache miss: {cache_key[:16]}...")
        return None
    
    async def put(self, messages: List[Dict[str, Any]], 
                  model: str, response: Any, 
                  temperature: float = 0.1, max_tokens: int = 4000,
                  cost_estimate: Optional[float] = None,
                  token_count: Optional[int] = None,
                  **kwargs) -> None:
        """Cache a response"""
        cache_key = self._generate_cache_key(messages, model, temperature, max_tokens, **kwargs)
        
        # Get TTL from config
        llm_config = get_llm_config()
        ttl = llm_config.cache_ttl
        
        entry = CacheEntry(
            response=response,
            timestamp=time.time(),
            ttl=ttl,
            cost_estimate=cost_estimate,
            token_count=token_count,
            model=model
        )
        
        # Store in memory cache
        self._memory_cache[cache_key] = entry
        self._access_count[cache_key] = 1
        
        # Store in persistent cache
        try:
            await self.store.put(self._cache_namespace, cache_key, entry.to_dict())
            logger.debug(f"Cached response: {cache_key[:16]}... (TTL: {ttl}s)")
        except Exception as e:
            logger.warning(f"Error writing to cache: {e}")
        
        # Cleanup if memory cache is getting too large
        if len(self._memory_cache) > self.max_cache_size:
            await self._cleanup_memory_cache()
    
    async def _cleanup_memory_cache(self):
        """Clean up memory cache by removing least accessed items"""
        if len(self._memory_cache) <= self.max_cache_size:
            return
        
        # Sort by access count (ascending) and remove least accessed
        sorted_items = sorted(self._access_count.items(), key=lambda x: x[1])
        items_to_remove = len(self._memory_cache) - self.max_cache_size + 100  # Remove extra for headroom
        
        for cache_key, _ in sorted_items[:items_to_remove]:
            if cache_key in self._memory_cache:
                del self._memory_cache[cache_key]
            if cache_key in self._access_count:
                del self._access_count[cache_key]
        
        logger.debug(f"Cleaned up memory cache: removed {items_to_remove} items")
    
    async def cleanup_expired(self) -> int:
        """Clean up expired entries from persistent storage"""
        try:
            # Get all keys in the cache namespace
            cache_keys = await self.store.list_keys(self._cache_namespace)
            
            expired_keys = []
            for cache_key in cache_keys:
                try:
                    cached_data = await self.store.get(self._cache_namespace, cache_key)
                    if cached_data:
                        entry = CacheEntry.from_dict(cached_data)
                        if entry.is_expired():
                            expired_keys.append(cache_key)
                except Exception as e:
                    logger.warning(f"Error checking cache entry {cache_key}: {e}")
                    expired_keys.append(cache_key)  # Remove problematic entries
            
            # Remove expired keys
            for cache_key in expired_keys:
                try:
                    await self.store.delete(self._cache_namespace, cache_key)
                except Exception as e:
                    logger.warning(f"Error deleting expired cache entry {cache_key}: {e}")
            
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
            return len(expired_keys)
            
        except Exception as e:
            logger.error(f"Error during cache cleanup: {e}")
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            cache_keys = await self.store.list_keys(self._cache_namespace)
            total_entries = len(cache_keys)
            
            # Check how many are expired
            expired_count = 0
            total_cost_saved = 0.0
            total_tokens_saved = 0
            
            for cache_key in cache_keys:
                try:
                    cached_data = await self.store.get(self._cache_namespace, cache_key)
                    if cached_data:
                        entry = CacheEntry.from_dict(cached_data)
                        if entry.is_expired():
                            expired_count += 1
                        else:
                            if entry.cost_estimate:
                                total_cost_saved += entry.cost_estimate
                            if entry.token_count:
                                total_tokens_saved += entry.token_count
                except Exception:
                    expired_count += 1  # Count problematic entries as expired
            
            return {
                "namespace": self.namespace,
                "total_entries": total_entries,
                "active_entries": total_entries - expired_count,
                "expired_entries": expired_count,
                "memory_cache_size": len(self._memory_cache),
                "total_cost_saved": total_cost_saved,
                "total_tokens_saved": total_tokens_saved,
                "hit_rate": self._calculate_hit_rate()
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}
    
    def _calculate_hit_rate(self) -> float:
        """Calculate cache hit rate from access counts"""
        if not self._access_count:
            return 0.0
        
        total_accesses = sum(self._access_count.values())
        cache_hits = len([count for count in self._access_count.values() if count > 1])
        
        return cache_hits / len(self._access_count) if self._access_count else 0.0
    
    async def clear_cache(self, confirm: bool = False) -> int:
        """Clear all cache entries (use with caution)"""
        if not confirm:
            raise ValueError("Must set confirm=True to clear cache")
        
        try:
            cache_keys = await self.store.list_keys(self._cache_namespace)
            
            for cache_key in cache_keys:
                await self.store.delete(self._cache_namespace, cache_key)
            
            # Clear memory cache
            self._memory_cache.clear()
            self._access_count.clear()
            
            logger.warning(f"Cleared all cache entries: {len(cache_keys)} items")
            return len(cache_keys)
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return 0

# Global cache instances
_caches: Dict[str, LLMCache] = {}

def get_llm_cache(namespace: str = "default") -> LLMCache:
    """Get or create an LLM cache for a specific namespace"""
    if namespace not in _caches:
        _caches[namespace] = LLMCache(namespace)
    return _caches[namespace]

async def cleanup_all_caches() -> Dict[str, int]:
    """Clean up expired entries in all caches"""
    results = {}
    for namespace, cache in _caches.items():
        try:
            expired_count = await cache.cleanup_expired()
            results[namespace] = expired_count
        except Exception as e:
            logger.error(f"Error cleaning up cache {namespace}: {e}")
            results[namespace] = -1
    return results

async def get_all_cache_stats() -> Dict[str, Dict[str, Any]]:
    """Get statistics for all caches"""
    stats = {}
    for namespace, cache in _caches.items():
        try:
            stats[namespace] = await cache.get_stats()
        except Exception as e:
            logger.error(f"Error getting stats for cache {namespace}: {e}")
            stats[namespace] = {"error": str(e)}
    return stats