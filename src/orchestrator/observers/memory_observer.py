"""Memory graph observer integration for the orchestrator."""

from typing import Optional
from datetime import datetime

from src.memory import get_user_memory, MemoryNode
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
    async def emit_node_added(self, thread_id: str, node_id: str, node: MemoryNode, task_id: Optional[str] = None, user_id: Optional[str] = None):
        """Emit event when a memory node is added."""
        try:
            # Convert node to serializable format
            # Include content for entities, tool outputs, and actions so UI can display proper names
            # TEMPORARY: Include content for ALL node types to debug UI issue
            include_content = True
            
            
            # Debug logging for entity content
            if node.context_type.value == "domain_entity":
                logger.debug("entity_content_debug",
                           node_id=node.node_id,
                           has_content=node.content is not None,
                           content_type=type(node.content).__name__,
                           entity_name=node.content.get('entity_name') if isinstance(node.content, dict) else None,
                           content_keys=list(node.content.keys())[:5] if isinstance(node.content, dict) else None)
            
            node_data = {
                "node_id": node.node_id,
                "summary": node.summary,
                "context_type": node.context_type.value,
                "tags": list(node.tags),
                "created_at": node.created_at.isoformat() if hasattr(node.created_at, 'isoformat') else str(node.created_at),
                "relevance": node.current_relevance(),
                "content_preview": str(node.content)[:100] if node.content else "",
                "content": node.content if include_content else None  # Include content for entities
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
            await self._check_snapshot_needed(thread_id, task_id, user_id)
            
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
    async def emit_graph_snapshot(self, thread_id: str, task_id: Optional[str] = None, user_id: Optional[str] = None):
        """Emit a full snapshot of the memory graph."""
        try:
            # Use user_id for memory lookup (our new namespace), fall back to thread_id for compatibility
            memory_key = user_id if user_id else thread_id
            
            # Get memory asynchronously
            from src.memory import get_memory_manager
            memory_manager = get_memory_manager()
            memory = await memory_manager.get_memory(memory_key)
            
            if not memory:
                logger.warning("memory_graph_not_found", memory_key=memory_key)
                return
            
            # Build graph data
            nodes = {}
            edges = []
            
            # Convert nodes using the new API
            for node in memory.get_all_nodes():
                # Include content for entities, tool outputs, and actions so UI can display proper names
                # TEMPORARY: Include content for ALL node types to debug UI issue
                include_content = True
                
                
                # Debug logging for entity content in snapshot
                if node.context_type.value == "domain_entity":
                    logger.debug("snapshot_entity_content_debug",
                               node_id=node.node_id,
                               has_content=node.content is not None,
                               content_type=type(node.content).__name__,
                               entity_name=node.content.get('entity_name') if isinstance(node.content, dict) else None,
                               content_keys=list(node.content.keys())[:5] if isinstance(node.content, dict) else None)
                
                nodes[node.node_id] = {
                    "node_id": node.node_id,
                    "summary": node.summary,
                    "context_type": node.context_type.value,
                    "tags": list(node.tags),
                    "created_at": node.created_at.isoformat() if hasattr(node.created_at, 'isoformat') else str(node.created_at),
                    "relevance": node.current_relevance(),
                    "content_preview": str(node.content)[:100] if node.content else "",
                    "content": node.content if include_content else None  # Include content for entities
                }
            
            # Convert edges using the new API
            for u, v, data in memory.get_all_edges():
                edges.append({
                    "from_id": u,
                    "to_id": v,
                    "type": data.get("type", "relates_to")
                })
            
            # ALSO include global domain entities if we have a user_id
            global_node_count = 0
            if user_id:
                try:
                    # Ensure global entities are loaded from PostgreSQL
                    await memory_manager.ensure_user_memories_loaded("global_domain_entities")
                    # Get global entities
                    global_memory = await memory_manager.get_memory("global_domain_entities")
                    
                    # Add global entity nodes to the snapshot
                    for node in global_memory.get_all_nodes():
                        if node.context_type.value == "domain_entity":
                            # Check if this entity is already in user's memory to avoid duplicates
                            if node.node_id not in nodes:
                                include_content = True
                                
                                nodes[node.node_id] = {
                                    "node_id": node.node_id,
                                    "summary": node.summary + " (global)",  # Mark as global
                                    "context_type": node.context_type.value,
                                    "tags": list(node.tags) + ["global_entity"],
                                    "created_at": node.created_at.isoformat() if hasattr(node.created_at, 'isoformat') else str(node.created_at),
                                    "relevance": node.current_relevance(),
                                    "content_preview": str(node.content)[:100] if node.content else "",
                                    "content": node.content if include_content else None,
                                    "is_global": True  # Flag for UI
                                }
                                global_node_count += 1
                    
                    # Note: We don't include edges from global memory as they would be between global entities
                    # The UI can show these entities as standalone nodes
                    
                    logger.info("included_global_entities_in_snapshot",
                               user_id=user_id,
                               global_entities_added=global_node_count)
                               
                except Exception as e:
                    logger.warning("failed_to_include_global_entities",
                                 error=str(e),
                                 user_id=user_id)
            
            # Update stats to include global entity count
            stats = memory.get_statistics()
            stats["global_entities_included"] = global_node_count
            
            graph_data = {
                "nodes": nodes,
                "edges": edges,
                "stats": stats
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
    
    async def _check_snapshot_needed(self, thread_id: str, task_id: Optional[str] = None, user_id: Optional[str] = None):
        """Check if enough time has passed to send a new snapshot."""
        if self._last_snapshot_time is None:
            # First update, send snapshot
            await self.emit_graph_snapshot(thread_id, task_id, user_id)
        else:
            elapsed = (datetime.now() - self._last_snapshot_time).total_seconds()
            if elapsed >= self._snapshot_interval:
                await self.emit_graph_snapshot(thread_id, task_id, user_id)


# Global instance
_memory_observer = None


def get_memory_observer() -> MemoryObserverIntegration:
    """Get the global memory observer instance."""
    global _memory_observer
    if _memory_observer is None:
        _memory_observer = MemoryObserverIntegration()
    return _memory_observer


@log_execution(component="orchestrator", operation="notify_memory_update")
async def notify_memory_update(thread_id: str, node_id: str, node: MemoryNode, 
                        task_id: Optional[str] = None, user_id: Optional[str] = None):
    """Convenience function to notify memory updates."""
    observer = get_memory_observer()
    await observer.emit_node_added(thread_id, node_id, node, task_id, user_id)


@log_execution(component="orchestrator", operation="notify_memory_edge")
def notify_memory_edge(thread_id: str, from_id: str, to_id: str,
                      relationship_type: str, task_id: Optional[str] = None):
    """Convenience function to notify edge additions."""
    observer = get_memory_observer()
    observer.emit_edge_added(thread_id, from_id, to_id, relationship_type, task_id)