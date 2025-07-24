"""Memory graph observer integration for the orchestrator."""

from typing import Optional
from datetime import datetime

from src.memory import get_thread_memory, MemoryNode
from src.orchestrator.observers import (
    get_observer_registry, 
    MemoryNodeAddedEvent,
    MemoryEdgeAddedEvent, 
    MemoryGraphSnapshotEvent
)
from src.utils.logging.framework import SmartLogger, log_execution

logger = SmartLogger("orchestrator")


class MemoryObserverIntegration:
    """Integrates memory graph updates with the observer system."""
    
    def __init__(self):
        self.observer_registry = get_observer_registry()
        self._last_snapshot_time = None
        self._snapshot_interval = 5  # Send full snapshot every 5 seconds
        
    @log_execution(component="orchestrator", operation="emit_memory_node_added")
    def emit_node_added(self, thread_id: str, node_id: str, node: MemoryNode, task_id: Optional[str] = None):
        """Emit event when a memory node is added."""
        try:
            # Convert node to serializable format
            node_data = {
                "node_id": node.node_id,
                "summary": node.summary,
                "context_type": node.context_type.value,
                "tags": list(node.tags),
                "created_at": node.created_at.isoformat() if hasattr(node.created_at, 'isoformat') else str(node.created_at),
                "relevance": node.current_relevance(),
                "content_preview": str(node.content)[:100] if node.content else "",
                "content": node.content if isinstance(node.content, dict) else None  # Include full content for entities
            }
            
            event = MemoryNodeAddedEvent(
                step_name="memory_update",
                task_id=task_id,
                timestamp=datetime.now().isoformat(),
                node_id=node_id,
                node_data=node_data,
                thread_id=thread_id
            )
            
            self.observer_registry.notify_memory_node_added(event)
            
            # Check if we should send a full snapshot
            self._check_snapshot_needed(thread_id, task_id)
            
        except Exception as e:
            logger.error("memory_node_emit_error",
                        error=str(e),
                        node_id=node_id,
                        thread_id=thread_id)
    
    @log_execution(component="orchestrator", operation="emit_memory_edge_added")
    def emit_edge_added(self, thread_id: str, from_id: str, to_id: str, 
                       relationship_type: str, task_id: Optional[str] = None):
        """Emit event when a memory edge is added."""
        try:
            edge_data = {
                "from_id": from_id,
                "to_id": to_id,
                "type": relationship_type,
                "created_at": datetime.now().isoformat()
            }
            
            event = MemoryEdgeAddedEvent(
                step_name="memory_update",
                task_id=task_id,
                timestamp=datetime.now().isoformat(),
                edge_data=edge_data,
                thread_id=thread_id
            )
            
            self.observer_registry.notify_memory_edge_added(event)
            
        except Exception as e:
            logger.error("memory_edge_emit_error",
                        error=str(e),
                        from_id=from_id,
                        to_id=to_id,
                        thread_id=thread_id)
    
    @log_execution(component="orchestrator", operation="emit_memory_snapshot")
    def emit_graph_snapshot(self, thread_id: str, task_id: Optional[str] = None):
        """Emit a full snapshot of the memory graph."""
        try:
            memory = get_thread_memory(thread_id)
            
            # Build graph data
            nodes = {}
            edges = []
            
            # Convert nodes
            for node_id, node in memory.nodes.items():
                nodes[node_id] = {
                    "node_id": node.node_id,
                    "summary": node.summary,
                    "context_type": node.context_type.value,
                    "tags": list(node.tags),
                    "created_at": node.created_at.isoformat() if hasattr(node.created_at, 'isoformat') else str(node.created_at),
                    "relevance": node.current_relevance(),
                    "content_preview": str(node.content)[:100] if node.content else "",
                    "content": None  # Removed to reduce snapshot size - UI only needs summaries
                }
            
            # Convert edges
            for u, v, data in memory.graph.edges(data=True):
                edges.append({
                    "from_id": u,
                    "to_id": v,
                    "type": data.get("type", "relates_to")
                })
            
            graph_data = {
                "nodes": nodes,
                "edges": edges,
                "stats": memory.get_stats()
            }
            
            event = MemoryGraphSnapshotEvent(
                step_name="memory_snapshot",
                task_id=task_id,
                timestamp=datetime.now().isoformat(),
                graph_data=graph_data,
                thread_id=thread_id
            )
            
            self.observer_registry.notify_memory_graph_snapshot(event)
            self._last_snapshot_time = datetime.now()
            
            logger.info("memory_snapshot_emitted",
                       thread_id=thread_id,
                       node_count=len(nodes),
                       edge_count=len(edges))
            
        except Exception as e:
            logger.error("memory_snapshot_error",
                        error=str(e),
                        thread_id=thread_id)
    
    def _check_snapshot_needed(self, thread_id: str, task_id: Optional[str] = None):
        """Check if enough time has passed to send a new snapshot."""
        if self._last_snapshot_time is None:
            # First update, send snapshot
            self.emit_graph_snapshot(thread_id, task_id)
        else:
            elapsed = (datetime.now() - self._last_snapshot_time).total_seconds()
            if elapsed >= self._snapshot_interval:
                self.emit_graph_snapshot(thread_id, task_id)


# Global instance
_memory_observer = None


def get_memory_observer() -> MemoryObserverIntegration:
    """Get the global memory observer instance."""
    global _memory_observer
    if _memory_observer is None:
        _memory_observer = MemoryObserverIntegration()
    return _memory_observer


@log_execution(component="orchestrator", operation="notify_memory_update")
def notify_memory_update(thread_id: str, node_id: str, node: MemoryNode, 
                        task_id: Optional[str] = None):
    """Convenience function to notify memory updates."""
    observer = get_memory_observer()
    observer.emit_node_added(thread_id, node_id, node, task_id)


@log_execution(component="orchestrator", operation="notify_memory_edge")
def notify_memory_edge(thread_id: str, from_id: str, to_id: str,
                      relationship_type: str, task_id: Optional[str] = None):
    """Convenience function to notify edge additions."""
    observer = get_memory_observer()
    observer.emit_edge_added(thread_id, from_id, to_id, relationship_type, task_id)