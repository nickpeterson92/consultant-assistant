"""SQLite backend for memory storage."""

import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional, Set, Tuple
from contextlib import contextmanager
import threading

from src.memory.core.memory_node import MemoryNode, ContextType
from src.utils.logging.framework import SmartLogger

logger = SmartLogger("memory.sqlite")

class SQLiteMemoryBackend:
    """Thread-safe SQLite backend for memory storage."""
    
    def __init__(self, db_path: str = "memory_store.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._local = threading.local()
        
        # Initialize database
        from .sqlite_schema import init_database
        init_database(db_path)
        
        logger.info("sqlite_backend_initialized", db_path=db_path)
    
    @contextmanager
    def _get_connection(self):
        """Get a thread-local database connection."""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA foreign_keys = ON")
            self._local.conn.execute("PRAGMA journal_mode = WAL")  # Better concurrency
        
        try:
            yield self._local.conn
        except Exception as e:
            self._local.conn.rollback()
            raise
        else:
            self._local.conn.commit()
    
    def store_node(self, node: MemoryNode, thread_id: str) -> str:
        """Store a memory node, handling entity deduplication."""
        with self._lock:
            with self._get_connection() as conn:
                # Check if this is an entity that already exists
                entity_id = node.content.get("entity_id") if isinstance(node.content, dict) else None
                entity_system = node.content.get("entity_system") if isinstance(node.content, dict) else None
                
                if entity_id and entity_system:
                    # Check for existing entity
                    existing = conn.execute(
                        "SELECT node_id, content FROM memory_nodes WHERE entity_id = ? AND entity_system = ?",
                        (entity_id, entity_system)
                    ).fetchone()
                    
                    if existing:
                        # Update existing entity
                        existing_content = json.loads(existing['content'])
                        
                        logger.info("updating_entity_data",
                                   entity_id=entity_id,
                                   existing_keys=list(existing_content.get('entity_data', {}).keys()),
                                   new_keys=list(node.content.get('entity_data', {}).keys()))
                        
                        # Merge content
                        if isinstance(node.content, dict) and isinstance(existing_content, dict):
                            # Deep merge entity data
                            if 'entity_data' in existing_content and 'entity_data' in node.content:
                                existing_content['entity_data'].update(node.content.get('entity_data', {}))
                            else:
                                existing_content.update(node.content)
                            
                            # Update metadata
                            existing_content['last_updated'] = datetime.now().isoformat()
                            existing_content['update_count'] = existing_content.get('update_count', 0) + 1
                            
                            # Update the node
                            conn.execute("""
                                UPDATE memory_nodes SET
                                    content = ?,
                                    last_accessed = ?,
                                    access_count = access_count + 1,
                                    tags = ?
                                WHERE node_id = ?
                            """, (
                                json.dumps(existing_content),
                                datetime.now().isoformat(),
                                json.dumps(list(node.tags)) if node.tags else "[]",
                                existing['node_id']
                            ))
                            
                            logger.info("entity_updated",
                                       node_id=existing['node_id'],
                                       entity_id=entity_id,
                                       entity_system=entity_system)
                            
                            return existing['node_id']
                
                # Store new node
                entity_type = node.content.get("entity_type") if isinstance(node.content, dict) else None
                
                conn.execute("""
                    INSERT INTO memory_nodes (
                        node_id, thread_id, content, context_type, summary,
                        created_at, last_accessed, access_count, base_relevance,
                        tags, metadata, entity_id, entity_type, entity_system
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    node.node_id,
                    thread_id,
                    json.dumps(node.content),
                    node.context_type.value,
                    node.summary,
                    node.created_at.isoformat(),
                    node.last_accessed.isoformat(),
                    1,  # Initial access count
                    node.base_relevance,
                    json.dumps(list(node.tags)) if node.tags else "[]",
                    json.dumps(getattr(node, 'metadata', {})) if hasattr(node, 'metadata') else "{}",
                    entity_id,
                    entity_type,
                    entity_system
                ))
                
                logger.info("node_stored",
                           node_id=node.node_id,
                           thread_id=thread_id,
                           context_type=node.context_type.value,
                           is_entity=bool(entity_id))
                
                return node.node_id
    
    def get_node(self, node_id: str) -> Optional[MemoryNode]:
        """Retrieve a node by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM memory_nodes WHERE node_id = ?",
                (node_id,)
            ).fetchone()
            
            if row:
                return self._row_to_node(row)
            return None
    
    def get_node_by_entity_id(self, entity_id: str, entity_system: Optional[str] = None) -> Optional[MemoryNode]:
        """Get a node by its entity ID."""
        with self._get_connection() as conn:
            if entity_system:
                row = conn.execute(
                    "SELECT * FROM memory_nodes WHERE entity_id = ? AND entity_system = ?",
                    (entity_id, entity_system)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM memory_nodes WHERE entity_id = ?",
                    (entity_id,)
                ).fetchone()
            
            if row:
                return self._row_to_node(row)
            return None
    
    def get_nodes_by_thread(self, thread_id: str, 
                           context_filter: Optional[Set[ContextType]] = None,
                           max_age_hours: Optional[float] = None) -> List[MemoryNode]:
        """Get all nodes for a thread with optional filters."""
        with self._get_connection() as conn:
            query = "SELECT * FROM memory_nodes WHERE thread_id = ?"
            params = [thread_id]
            
            if context_filter:
                placeholders = ','.join('?' * len(context_filter))
                query += f" AND context_type IN ({placeholders})"
                params.extend([ct.value for ct in context_filter])
            
            if max_age_hours:
                query += " AND datetime(created_at) > datetime('now', ?)"
                params.append(f'-{max_age_hours} hours')
            
            query += " ORDER BY created_at DESC"
            
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_node(row) for row in rows]
    
    def get_all_nodes(self, context_filter: Optional[Set[ContextType]] = None,
                      max_age_hours: Optional[float] = None) -> List[MemoryNode]:
        """Get all nodes across all threads."""
        with self._get_connection() as conn:
            query = "SELECT * FROM memory_nodes WHERE 1=1"
            params = []
            
            if context_filter:
                placeholders = ','.join('?' * len(context_filter))
                query += f" AND context_type IN ({placeholders})"
                params.extend([ct.value for ct in context_filter])
            
            if max_age_hours:
                query += " AND datetime(created_at) > datetime('now', ?)"
                params.append(f'-{max_age_hours} hours')
            
            query += " ORDER BY created_at DESC"
            
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_node(row) for row in rows]
    
    def search_nodes(self, query_text: str, thread_id: Optional[str] = None,
                     limit: int = 20) -> List[Tuple[MemoryNode, float]]:
        """Full-text search across nodes."""
        # Escape special characters for FTS5
        # FTS5 uses double quotes for phrase matching, so we need to escape them
        query_text = query_text.replace('"', '""')
        
        with self._get_connection() as conn:
            if thread_id:
                sql = """
                    SELECT n.*, s.rank
                    FROM memory_nodes n
                    JOIN memory_search s ON n.node_id = s.node_id
                    WHERE s.memory_search MATCH ? AND n.thread_id = ?
                    ORDER BY s.rank
                    LIMIT ?
                """
                rows = conn.execute(sql, (query_text, thread_id, limit)).fetchall()
            else:
                sql = """
                    SELECT n.*, s.rank
                    FROM memory_nodes n
                    JOIN memory_search s ON n.node_id = s.node_id
                    WHERE s.memory_search MATCH ?
                    ORDER BY s.rank
                    LIMIT ?
                """
                rows = conn.execute(sql, (query_text, limit)).fetchall()
            
            results = []
            for row in rows:
                node = self._row_to_node(row)
                # Normalize rank to 0-1
                rank = abs(row['rank']) / 10.0  # FTS5 rank is negative
                results.append((node, min(rank, 1.0)))
            
            return results
    
    def store_relationship(self, from_node_id: str, to_node_id: str, 
                          relationship_type: Any,  # Accept string or enum
                          strength: float = 1.0,
                          metadata: Optional[Dict] = None):
        """Store a relationship between nodes."""
        with self._lock:
            with self._get_connection() as conn:
                try:
                    conn.execute("""
                        INSERT INTO memory_relationships (
                            from_node_id, to_node_id, relationship_type,
                            strength, created_at, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        from_node_id,
                        to_node_id,
                        relationship_type.value if hasattr(relationship_type, 'value') else str(relationship_type),
                        strength,
                        datetime.now().isoformat(),
                        json.dumps(metadata) if metadata else "{}"
                    ))
                    
                    logger.debug("relationship_stored",
                               from_node=from_node_id,
                               to_node=to_node_id,
                               rel_type=relationship_type.value if hasattr(relationship_type, 'value') else str(relationship_type))
                    
                except sqlite3.IntegrityError:
                    # Relationship already exists - update strength
                    conn.execute("""
                        UPDATE memory_relationships 
                        SET strength = MAX(strength, ?)
                        WHERE from_node_id = ? AND to_node_id = ? AND relationship_type = ?
                    """, (strength, from_node_id, to_node_id, 
                          relationship_type.value if hasattr(relationship_type, 'value') else str(relationship_type)))
    
    def get_relationships(self, node_id: str, direction: str = "both") -> List[Dict[str, Any]]:
        """Get relationships for a node."""
        with self._get_connection() as conn:
            relationships = []
            
            if direction in ["out", "both"]:
                rows = conn.execute("""
                    SELECT r.*, n.summary as target_summary
                    FROM memory_relationships r
                    JOIN memory_nodes n ON r.to_node_id = n.node_id
                    WHERE r.from_node_id = ?
                """, (node_id,)).fetchall()
                
                for row in rows:
                    relationships.append({
                        "direction": "out",
                        "node_id": row['to_node_id'],
                        "type": row['relationship_type'],
                        "strength": row['strength'],
                        "target_summary": row['target_summary']
                    })
            
            if direction in ["in", "both"]:
                rows = conn.execute("""
                    SELECT r.*, n.summary as source_summary
                    FROM memory_relationships r
                    JOIN memory_nodes n ON r.from_node_id = n.node_id
                    WHERE r.to_node_id = ?
                """, (node_id,)).fetchall()
                
                for row in rows:
                    relationships.append({
                        "direction": "in",
                        "node_id": row['from_node_id'],
                        "type": row['relationship_type'],
                        "strength": row['strength'],
                        "source_summary": row['source_summary']
                    })
            
            return relationships
    
    def update_node_access(self, node_id: str):
        """Update access time and count for a node."""
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE memory_nodes
                SET last_accessed = ?, access_count = access_count + 1
                WHERE node_id = ?
            """, (datetime.now().isoformat(), node_id))
    
    def delete_old_nodes(self, max_age_hours: float, 
                        preserve_types: Optional[Set[ContextType]] = None) -> int:
        """Delete nodes older than specified age."""
        with self._lock:
            with self._get_connection() as conn:
                query = "DELETE FROM memory_nodes WHERE datetime(created_at) < datetime('now', ?)"
                params = [f'-{max_age_hours} hours']
                
                if preserve_types:
                    placeholders = ','.join('?' * len(preserve_types))
                    query += f" AND context_type NOT IN ({placeholders})"
                    params.extend([ct.value for ct in preserve_types])
                
                cursor = conn.execute(query, params)
                deleted = cursor.rowcount
                
                logger.info("old_nodes_deleted", count=deleted, max_age_hours=max_age_hours)
                return deleted
    
    def _row_to_node(self, row: sqlite3.Row) -> MemoryNode:
        """Convert a database row to a MemoryNode."""
        content = json.loads(row['content'])
        tags = set(json.loads(row['tags'])) if row['tags'] else set()
        metadata = json.loads(row['metadata']) if row['metadata'] else {}
        
        node = MemoryNode(
            content=content,
            context_type=ContextType(row['context_type']),
            summary=row['summary'],
            tags=tags
        )
        
        # Set internal fields
        node.node_id = row['node_id']
        node.created_at = datetime.fromisoformat(row['created_at'])
        node.last_accessed = datetime.fromisoformat(row['last_accessed'])
        # Note: access_count is stored in DB but not on node object
        node.base_relevance = row['base_relevance']
        
        # Set metadata if the node has this attribute
        if hasattr(node, 'metadata') and metadata:
            node.metadata = metadata
        
        return node
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        with self._get_connection() as conn:
            stats = {}
            
            # Node counts by type
            rows = conn.execute("""
                SELECT context_type, COUNT(*) as count
                FROM memory_nodes
                GROUP BY context_type
            """).fetchall()
            
            stats['nodes_by_type'] = {row['context_type']: row['count'] for row in rows}
            
            # Total nodes
            stats['total_nodes'] = conn.execute("SELECT COUNT(*) FROM memory_nodes").fetchone()[0]
            
            # Total relationships
            stats['total_relationships'] = conn.execute("SELECT COUNT(*) FROM memory_relationships").fetchone()[0]
            
            # Entity counts
            rows = conn.execute("""
                SELECT entity_system, entity_type, COUNT(*) as count
                FROM memory_nodes
                WHERE entity_id IS NOT NULL
                GROUP BY entity_system, entity_type
            """).fetchall()
            
            stats['entities'] = [
                {
                    'system': row['entity_system'],
                    'type': row['entity_type'],
                    'count': row['count']
                }
                for row in rows
            ]
            
            return stats