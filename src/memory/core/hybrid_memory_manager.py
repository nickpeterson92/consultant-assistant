"""Hybrid memory manager using PostgreSQL for persistence and SQLite for processing."""

from typing import Dict, Optional
import threading

from .memory_graph import MemoryGraph
from .memory_node import MemoryNode, ContextType
from ..storage.postgres_backend import get_postgres_backend, PostgresMemoryBackend
from src.utils.logging.framework import SmartLogger
from src.utils.datetime_utils import utc_now

logger = SmartLogger("memory.hybrid")


class HybridMemoryManager:
    """
    Manages memory with PostgreSQL for persistent user memories 
    and SQLite for transient processing/workflow state.
    """
    
    def __init__(self):
        # SQLite memory graphs for active processing
        self.thread_memories: Dict[str, MemoryGraph] = {}
        self._lock = threading.Lock()
        
        # PostgreSQL backend initialized on first use
        self._postgres_backend: Optional[PostgresMemoryBackend] = None
        
        logger.info("hybrid_memory_manager_initialized")
    
    async def get_postgres_backend(self) -> PostgresMemoryBackend:
        """Get or initialize PostgreSQL backend."""
        if self._postgres_backend is None:
            self._postgres_backend = await get_postgres_backend()
        return self._postgres_backend
    
    def get_memory(self, memory_key: str) -> MemoryGraph:
        """
        Get or create memory graph for a key (user_id or thread_id).
        For user_ids, this will load from PostgreSQL on first access.
        """
        with self._lock:
            if memory_key not in self.thread_memories:
                self.thread_memories[memory_key] = MemoryGraph(memory_key)
                logger.info("new_memory_graph_created",
                           memory_key=memory_key,
                           total_graphs=len(self.thread_memories))
            
            memory = self.thread_memories[memory_key]
            memory.last_activity = utc_now()
            return memory
    
    async def ensure_user_memories_loaded(self, user_id: str) -> None:
        """Ensure user's persistent memories are loaded from PostgreSQL into SQLite.
        
        This is a no-op if memories are already loaded for this user.
        """
        memory = self.get_memory(user_id)
        
        # Check if we've already loaded memories from PostgreSQL
        # Use a marker to track if we've loaded from PostgreSQL
        postgres_loaded_marker = f"_postgres_loaded_{user_id}"
        if hasattr(memory, postgres_loaded_marker):
            logger.debug("user_memories_already_loaded_from_postgres",
                        user_id=user_id,
                        node_count=len(memory.node_manager.nodes))
            return
        
        # Load memories from PostgreSQL
        await self.load_user_memories(user_id)
        
        # Mark as loaded
        setattr(memory, postgres_loaded_marker, True)
    
    async def load_user_memories(self, user_id: str) -> None:
        """Load user's persistent memories from PostgreSQL into SQLite."""
        postgres = await self.get_postgres_backend()
        memory = self.get_memory(user_id)
        
        # Get all user nodes from PostgreSQL
        nodes = await postgres.get_nodes_by_user(user_id, limit=1000)
        
        logger.info("loading_user_memories_from_postgres",
                   user_id=user_id,
                   node_count=len(nodes))
        
        # Store nodes in memory graph for fast local access
        node_id_map = {}
        for node in nodes:
            # Add node directly to the memory graph's node manager
            memory.node_manager.add_node(node)
            node_id_map[node.node_id] = node.node_id
        
        # Load relationships
        for node in nodes:
            relationships = await postgres.get_relationships(node.node_id, user_id)
            for rel in relationships:
                if rel['direction'] == 'out':
                    from_id = node_id_map.get(node.node_id, node.node_id)
                    to_id = node_id_map.get(rel['node_id'], rel['node_id'])
                    
                    # Add relationship to the graph
                    if from_id in memory.node_manager.nodes and to_id in memory.node_manager.nodes:
                        memory.graph.add_edge(
                            from_id, to_id,
                            type=rel['type'],
                            strength=rel['strength'],
                            metadata=rel.get('metadata', {})
                        )
        
        logger.info("user_memories_loaded",
                   user_id=user_id,
                   nodes_loaded=len(nodes))
    
    async def persist_to_postgres(self, user_id: str, node: MemoryNode) -> str:
        """Persist a memory node to PostgreSQL for long-term storage."""
        postgres = await self.get_postgres_backend()
        
        # Store in PostgreSQL
        pg_node_id = await postgres.store_node(node, user_id)
        
        logger.info("node_persisted_to_postgres",
                   user_id=user_id,
                   node_id=pg_node_id,
                   context_type=node.context_type.value)
        
        return pg_node_id
    
    async def store_persistent_memory(self, user_id: str, content, context_type: ContextType,
                                    **kwargs) -> str:
        """
        Store memory that should persist across sessions.
        Writes to both SQLite (for immediate access) and PostgreSQL (for persistence).
        """
        # Store in SQLite first for immediate access
        memory = self.get_memory(user_id)
        node_id = memory.store(content, context_type, **kwargs)
        
        # Get the node to persist it
        node = memory.node_manager.get_node(node_id)
        if node:
            # Persist to PostgreSQL asynchronously
            try:
                await self.persist_to_postgres(user_id, node)
            except Exception as e:
                logger.error("failed_to_persist_to_postgres",
                           error=str(e),
                           user_id=user_id,
                           node_id=node_id)
        
        return node_id
    
    def store_transient_memory(self, thread_id: str, content, context_type: ContextType,
                             **kwargs) -> str:
        """
        Store memory that's only needed for current processing.
        Only writes to SQLite, not PostgreSQL.
        """
        memory = self.get_memory(thread_id)
        return memory.store(content, context_type, **kwargs)
    
    async def get_user_stats(self, user_id: str) -> Dict:
        """Get statistics from both SQLite (current) and PostgreSQL (historical)."""
        # Get SQLite stats
        sqlite_stats = {}
        if user_id in self.thread_memories:
            memory = self.thread_memories[user_id]
            sqlite_stats = memory.get_statistics()
        
        # Get PostgreSQL stats
        postgres = await self.get_postgres_backend()
        pg_stats = await postgres.get_user_stats(user_id)
        
        return {
            'user_id': user_id,
            'sqlite_stats': sqlite_stats,
            'postgres_stats': pg_stats,
            'combined_node_count': sqlite_stats.get('node_count', 0) + pg_stats.get('node_count', 0)
        }
    
    def cleanup_stale_threads(self, max_idle_hours: int = 24) -> Dict:
        """Clean up SQLite memory graphs that haven't been active."""
        with self._lock:
            current_time = utc_now()
            stale_keys = []
            
            for key, memory in self.thread_memories.items():
                # Don't clean up user memories, only thread memories
                if key.startswith('orchestrator-') or key.startswith('thread-'):
                    idle_hours = (current_time - memory.last_activity).total_seconds() / 3600
                    if idle_hours > max_idle_hours:
                        stale_keys.append(key)
            
            # Remove stale threads
            for key in stale_keys:
                del self.thread_memories[key]
            
            return {
                'stale_threads_removed': len(stale_keys),
                'active_graphs_remaining': len(self.thread_memories)
            }
    
    def is_user_memory_loaded(self, user_id: str) -> bool:
        """Check if user's memories have been loaded from PostgreSQL."""
        return user_id in self.thread_memories
    
    async def ensure_user_memories_loaded(self, user_id: str) -> None:
        """Ensure user memories are loaded from PostgreSQL if not already."""
        if not self.is_user_memory_loaded(user_id):
            await self.load_user_memories(user_id)
    
    async def persist_relationship(self, user_id: str, from_node_id: str, to_node_id: str,
                                 relationship_type: str, strength: float = 1.0) -> None:
        """Persist a relationship to PostgreSQL."""
        try:
            postgres = await self.get_postgres_backend()
            from src.memory.core.memory_graph import RelationshipType
            
            # Validate relationship type
            if isinstance(relationship_type, str):
                # Check if it's a valid relationship type
                valid_types = [
                    RelationshipType.LED_TO,
                    RelationshipType.RELATES_TO,
                    RelationshipType.DEPENDS_ON,
                    RelationshipType.CONTRADICTS,
                    RelationshipType.REFINES,
                    RelationshipType.ANSWERS
                ]
                if relationship_type in valid_types:
                    rel_type = relationship_type
                else:
                    # If not a valid type, use default
                    rel_type = RelationshipType.RELATES_TO
                    logger.warning("invalid_relationship_type",
                                 provided=relationship_type,
                                 using_default=rel_type)
            else:
                rel_type = relationship_type
            
            await postgres.store_relationship(
                user_id, from_node_id, to_node_id,
                rel_type, strength
            )
            
            logger.info("relationship_persisted_to_postgres",
                       user_id=user_id,
                       from_node=from_node_id,
                       to_node=to_node_id,
                       type=relationship_type)
                       
        except Exception as e:
            logger.error("failed_to_persist_relationship",
                       error=str(e),
                       user_id=user_id,
                       from_node=from_node_id,
                       to_node=to_node_id)


# Global hybrid manager instance
_global_hybrid_manager: Optional[HybridMemoryManager] = None


def get_hybrid_memory_manager() -> HybridMemoryManager:
    """Get the global hybrid memory manager instance."""
    global _global_hybrid_manager
    if _global_hybrid_manager is None:
        _global_hybrid_manager = HybridMemoryManager()
    return _global_hybrid_manager


async def ensure_user_memories(user_id: str) -> MemoryGraph:
    """Convenience function to ensure user memories are loaded and return the graph."""
    manager = get_hybrid_memory_manager()
    await manager.ensure_user_memories_loaded(user_id)
    return manager.get_memory(user_id)