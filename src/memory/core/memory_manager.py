"""Thread-scoped memory management for conversational AI."""

from datetime import datetime
from typing import Dict, Optional, List
import threading

from .memory_graph import MemoryGraph
from .memory_node import MemoryNode, ContextType
from src.utils.logging.framework import SmartLogger
from src.utils.thread_utils import ThreadIDManager

logger = SmartLogger("memory")


class ConversationalMemoryManager:
    """Manages memory graphs for multiple conversation threads."""
    
    def __init__(self, cleanup_interval_minutes: int = 30):
        self.thread_memories: Dict[str, MemoryGraph] = {}
        self.cleanup_interval_minutes = cleanup_interval_minutes
        self.last_cleanup = datetime.now()
        self._lock = threading.Lock()  # Thread safety for concurrent access
        
        logger.info("memory_manager_initialized",
                   cleanup_interval_minutes=cleanup_interval_minutes,
                   component="memory")
    
    def get_memory(self, thread_id: str) -> MemoryGraph:
        """Get or create memory graph for a thread."""
        # Validate thread ID format
        if not ThreadIDManager.is_valid_thread_id(thread_id):
            raise ValueError(f"Invalid thread ID format: {thread_id}. Expected 'agent-task_id' format.")
            
        with self._lock:
            if thread_id not in self.thread_memories:
                self.thread_memories[thread_id] = MemoryGraph(thread_id)
                logger.info("new_thread_memory_created",
                           thread_id=thread_id,
                           total_threads=len(self.thread_memories),
                           component="memory")
            
            # Update last activity
            memory = self.thread_memories[thread_id]
            memory.last_activity = datetime.now()
            
            return memory
    
    def store_in_thread(self, thread_id: str, content, context_type: ContextType,
                       **kwargs) -> str:
        """Convenience method to store content in a specific thread's memory."""
        memory = self.get_memory(thread_id)
        return memory.store(content, context_type, **kwargs)
    
    def retrieve_from_thread(self, thread_id: str, query_text: str = "", 
                           **kwargs) -> List[MemoryNode]:
        """Convenience method to retrieve from a specific thread's memory."""
        memory = self.get_memory(thread_id)
        return memory.retrieve_relevant(query_text, **kwargs)
    
    def retrieve_with_intelligence(self, thread_id: str, query_text: str = "",
                                 **kwargs) -> List[MemoryNode]:
        """Retrieve using graph algorithms for smarter results."""
        memory = self.get_memory(thread_id)
        return memory.retrieve_with_graph_intelligence(query_text, **kwargs)
    
    def get_important_memories(self, thread_id: str, top_n: int = 10) -> List[MemoryNode]:
        """Get the most important memories from a thread based on PageRank."""
        memory = self.get_memory(thread_id)
        return memory.find_important_memories(top_n)
    
    def get_memory_clusters(self, thread_id: str) -> List[List[MemoryNode]]:
        """Get memory clusters showing related topics in the conversation."""
        memory = self.get_memory(thread_id)
        return memory.find_memory_clusters()
    
    def get_bridge_memories(self, thread_id: str, top_n: int = 10) -> List[MemoryNode]:
        """Get memories that connect different topics in the conversation."""
        memory = self.get_memory(thread_id)
        return memory.find_bridge_memories(top_n)
    
    def cleanup_stale_threads(self, max_idle_hours: int = 24) -> Dict:
        """Clean up threads that haven't been active recently."""
        with self._lock:
            current_time = datetime.now()
            stale_thread_ids = []
            
            for thread_id, memory in self.thread_memories.items():
                idle_hours = (current_time - memory.last_activity).total_seconds() / 3600
                if idle_hours > max_idle_hours:
                    stale_thread_ids.append(thread_id)
            
            # Remove stale threads
            for thread_id in stale_thread_ids:
                del self.thread_memories[thread_id]
            
            cleanup_stats = {
                'stale_threads_removed': len(stale_thread_ids),
                'active_threads_remaining': len(self.thread_memories),
                'cleanup_time': current_time.isoformat()
            }
            
            if len(stale_thread_ids) > 0:
                logger.info("stale_threads_cleanup",
                           **cleanup_stats,
                           component="memory")
            
            return cleanup_stats
    
    def cleanup_stale_nodes(self) -> Dict:
        """Run cleanup on all active memory graphs."""
        cleanup_stats = {
            'threads_processed': 0,
            'total_nodes_cleaned': 0,
            'per_thread_stats': {}
        }
        
        with self._lock:
            for thread_id, memory in self.thread_memories.items():
                nodes_cleaned = memory.cleanup_stale_nodes()
                cleanup_stats['threads_processed'] += 1
                cleanup_stats['total_nodes_cleaned'] += nodes_cleaned
                cleanup_stats['per_thread_stats'][thread_id] = {
                    'nodes_cleaned': nodes_cleaned,
                    'nodes_remaining': memory.node_manager.get_node_count()
                }
        
        self.last_cleanup = datetime.now()
        
        logger.info("global_node_cleanup",
                   **cleanup_stats,
                   component="memory")
        
        return cleanup_stats
    
    def should_run_cleanup(self) -> bool:
        """Check if it's time for periodic cleanup."""
        minutes_since_cleanup = (datetime.now() - self.last_cleanup).total_seconds() / 60
        return minutes_since_cleanup >= self.cleanup_interval_minutes
    
    def periodic_cleanup(self, max_idle_hours: int = 24):
        """Run both thread and node cleanup if needed."""
        if not self.should_run_cleanup():
            return
        
        # Clean up stale threads first
        thread_stats = self.cleanup_stale_threads(max_idle_hours)
        
        # Then clean up stale nodes in remaining threads
        node_stats = self.cleanup_stale_nodes()
        
        logger.info("periodic_cleanup_completed",
                   thread_cleanup=thread_stats,
                   node_cleanup=node_stats,
                   component="memory")
    
    def get_global_stats(self) -> Dict:
        """Get statistics across all memory graphs."""
        with self._lock:
            total_nodes = sum(memory.node_manager.get_node_count() for memory in self.thread_memories.values())
            total_edges = sum(memory.graph.number_of_edges() for memory in self.thread_memories.values())
            
            thread_stats = {}
            for thread_id, memory in self.thread_memories.items():
                thread_stats[thread_id] = memory.get_statistics()
            
            return {
                'total_threads': len(self.thread_memories),
                'total_nodes_across_threads': total_nodes,
                'total_edges_across_threads': total_edges,
                'last_cleanup': self.last_cleanup.isoformat(),
                'thread_details': thread_stats
            }
    
    def thread_exists(self, thread_id: str) -> bool:
        """Check if a thread has an active memory graph."""
        with self._lock:
            return thread_id in self.thread_memories
    
    def remove_thread(self, thread_id: str) -> bool:
        """Manually remove a specific thread's memory."""
        with self._lock:
            if thread_id in self.thread_memories:
                del self.thread_memories[thread_id]
                logger.info("thread_memory_removed",
                           thread_id=thread_id,
                           component="memory")
                return True
            return False
    
    def __len__(self) -> int:
        """Return number of active threads."""
        return len(self.thread_memories)
    
    def __contains__(self, thread_id: str) -> bool:
        """Check if thread exists using 'in' operator."""
        return self.thread_exists(thread_id)


# Global singleton instance
_global_memory_manager: Optional[ConversationalMemoryManager] = None


def get_memory_manager() -> ConversationalMemoryManager:
    """Get the global memory manager instance."""
    global _global_memory_manager
    if _global_memory_manager is None:
        _global_memory_manager = ConversationalMemoryManager()
    return _global_memory_manager


def get_thread_memory(thread_id: str) -> MemoryGraph:
    """Convenience function to get memory for a specific thread."""
    manager = get_memory_manager()
    return manager.get_memory(thread_id)