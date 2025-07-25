"""Async memory management using hybrid PostgreSQL/SQLite storage."""

import asyncio
from datetime import datetime
from typing import Dict, Optional, List
import threading

from .memory_graph import MemoryGraph
from .memory_node import MemoryNode, ContextType
from .hybrid_memory_manager import HybridMemoryManager, get_hybrid_memory_manager
from src.utils.logging.framework import SmartLogger

logger = SmartLogger("memory")


class ConversationalMemoryManager:
    """Async wrapper around hybrid memory manager for API compatibility."""
    
    def __init__(self):
        self.hybrid_manager = get_hybrid_memory_manager()
        self._loop = None  # Will be set to current event loop when needed
        
        logger.info("async_memory_manager_initialized",
                   component="memory")
    
    async def get_memory(self, memory_key: str, load_from_postgres: bool = True) -> MemoryGraph:
        """Get or create memory graph for a user or thread.
        
        Args:
            memory_key: User ID or thread ID
            load_from_postgres: Whether to load user memories from PostgreSQL
        """
        # Check if this looks like a user ID (doesn't start with common prefixes)
        is_user_id = not any(memory_key.startswith(prefix) for prefix in ['orchestrator-', 'thread-', 'agent-'])
        
        if is_user_id and load_from_postgres:
            # Ensure user memories are loaded from PostgreSQL
            await self.hybrid_manager.ensure_user_memories_loaded(memory_key)
        
        return self.hybrid_manager.get_memory(memory_key)
    
    async def store_memory(self, memory_key: str, content, context_type: ContextType,
                          persist: bool = True, **kwargs) -> str:
        """Store content in memory with optional PostgreSQL persistence.
        
        Args:
            memory_key: User ID or thread ID
            content: Content to store
            context_type: Type of memory node
            persist: Whether to persist to PostgreSQL (for user memories)
            **kwargs: Additional arguments for memory storage
        """
        # Check if this is a user ID
        is_user_id = not any(memory_key.startswith(prefix) for prefix in ['orchestrator-', 'thread-', 'agent-'])
        
        if is_user_id and persist:
            # Store persistent user memory
            return await self.hybrid_manager.store_persistent_memory(
                memory_key, content, context_type, **kwargs
            )
        else:
            # Store transient thread memory
            return self.hybrid_manager.store_transient_memory(
                memory_key, content, context_type, **kwargs
            )
    
    async def retrieve_memories(self, memory_key: str, query_text: str = "", 
                              **kwargs) -> List[MemoryNode]:
        """Retrieve relevant memories for a user or thread."""
        memory = await self.get_memory(memory_key)
        return memory.retrieve_relevant(query_text, **kwargs)
    
    async def retrieve_with_intelligence(self, memory_key: str, query_text: str = "",
                                       **kwargs) -> List[MemoryNode]:
        """Retrieve using graph algorithms for smarter results."""
        memory = await self.get_memory(memory_key)
        return memory.retrieve_with_graph_intelligence(query_text, **kwargs)
    
    async def get_important_memories(self, memory_key: str, top_n: int = 10) -> List[MemoryNode]:
        """Get the most important memories based on PageRank."""
        memory = await self.get_memory(memory_key)
        return memory.find_important_memories(top_n)
    
    async def get_memory_clusters(self, memory_key: str) -> List[List[MemoryNode]]:
        """Get memory clusters showing related topics."""
        memory = await self.get_memory(memory_key)
        return memory.find_memory_clusters()
    
    async def get_bridge_memories(self, memory_key: str, top_n: int = 10) -> List[MemoryNode]:
        """Get memories that connect different topics."""
        memory = await self.get_memory(memory_key)
        return memory.find_bridge_memories(top_n)
    
    def cleanup_stale_threads(self, max_idle_hours: int = 24) -> Dict:
        """Clean up threads that haven't been active recently."""
        return self.hybrid_manager.cleanup_stale_threads(max_idle_hours)
    
    async def get_user_stats(self, user_id: str) -> Dict:
        """Get statistics for a user's memory from both stores."""
        return await self.hybrid_manager.get_user_stats(user_id)
    
    async def ensure_user_memories_loaded(self, user_id: str) -> None:
        """Ensure user's persistent memories are loaded from PostgreSQL.
        
        This delegates to the hybrid manager's ensure_user_memories_loaded method.
        """
        return await self.hybrid_manager.ensure_user_memories_loaded(user_id)
    
    async def add_relationship(self, memory_key: str, from_node_id: str, to_node_id: str,
                             relationship_type: str, persist: bool = True) -> None:
        """Add a relationship between memory nodes."""
        memory = await self.get_memory(memory_key)
        memory.add_relationship(from_node_id, to_node_id, relationship_type)
        
        # Persist to PostgreSQL if this is a user memory
        is_user_id = not any(memory_key.startswith(prefix) for prefix in ['orchestrator-', 'thread-', 'agent-'])
        if is_user_id and persist:
            await self.hybrid_manager.persist_relationship(
                memory_key, from_node_id, to_node_id,
                relationship_type, strength=1.0
            )
    
    def is_memory_loaded(self, memory_key: str) -> bool:
        """Check if memory is currently loaded."""
        return self.hybrid_manager.is_user_memory_loaded(memory_key)
    
    async def ensure_postgres_backend(self) -> None:
        """Ensure PostgreSQL backend is initialized."""
        await self.hybrid_manager.get_postgres_backend()


# Global singleton instance
_global_memory_manager: Optional[ConversationalMemoryManager] = None


def get_memory_manager() -> ConversationalMemoryManager:
    """Get the global memory manager instance."""
    global _global_memory_manager
    if _global_memory_manager is None:
        _global_memory_manager = ConversationalMemoryManager()
    return _global_memory_manager


async def get_user_memory(memory_key: str, load_from_postgres: bool = True) -> MemoryGraph:
    """Async function to get memory for a specific user or thread.
    
    Args:
        memory_key: User ID (e.g., 'alice') or thread ID (e.g., 'orchestrator-abc123')
        load_from_postgres: Whether to load persistent memories from PostgreSQL
    
    Returns:
        MemoryGraph instance for the given key
    """
    manager = get_memory_manager()
    return await manager.get_memory(memory_key, load_from_postgres)