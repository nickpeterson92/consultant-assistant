"""PostgreSQL backend for persistent user memory storage."""

import json
from typing import List, Dict, Any, Optional, Set
from contextlib import asynccontextmanager
from uuid import UUID

import asyncpg
from asyncpg.pool import Pool

from src.memory.core.memory_node import MemoryNode, ContextType
from src.memory.core.memory_graph import RelationshipType
from src.utils.logging.framework import SmartLogger
from src.utils.datetime_utils import utc_now, datetime_to_iso_utc

logger = SmartLogger("memory.postgres")


class PostgresMemoryBackend:
    """Async PostgreSQL backend for persistent user memory storage."""
    
    def __init__(self, connection_string: str = None, pool_size: int = 20):
        """Initialize with connection string or environment variables."""
        import os
        
        # Use provided connection string or environment variable
        if connection_string:
            self.connection_string = connection_string
        elif os.getenv('POSTGRESQL_CONNECTION_STRING'):
            self.connection_string = os.getenv('POSTGRESQL_CONNECTION_STRING')
        else:
            # Fall back to building from individual variables
            host = os.getenv('POSTGRES_HOST', 'localhost')
            port = os.getenv('POSTGRES_PORT', '5432')
            database = os.getenv('POSTGRES_DB', 'consultant_assistant')
            user = os.getenv('POSTGRES_USER', 'postgres')
            password = os.getenv('POSTGRES_PASSWORD', '')
            
            self.connection_string = f'postgresql://{user}:{password}@{host}:{port}/{database}'
        self.pool_size = pool_size
        self._pool: Optional[Pool] = None
        
        logger.info("postgres_backend_initialized", pool_size=pool_size)
    
    async def initialize(self):
        """Initialize connection pool and ensure schema exists."""
        self._pool = await asyncpg.create_pool(
            self.connection_string,
            min_size=2,
            max_size=self.pool_size,
            command_timeout=60,
            server_settings={
                'application_name': 'consultant_assistant_memory'
            }
        )
        
        # Ensure schema exists (skip if already exists)
        try:
            async with self._pool.acquire() as conn:
                # Check if schema exists first
                schema_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = 'memory')"
                )
                if not schema_exists:
                    with open('src/memory/storage/postgres_schema.sql', 'r') as f:
                        await conn.execute(f.read())
                    logger.info("postgres_schema_created")
        except Exception as e:
            logger.warning("postgres_schema_check_failed", error=str(e))
        
        logger.info("postgres_pool_created", pool_size=self.pool_size)
    
    async def close(self):
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("postgres_pool_closed")
    
    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool."""
        async with self._pool.acquire() as conn:
            yield conn
    
    async def store_node(self, node: MemoryNode, user_id: str) -> str:
        """Store a memory node with entity deduplication at user scope."""
        async with self.acquire() as conn:
            # Check for existing entity within user scope
            entity_id = node.content.get("entity_id") if isinstance(node.content, dict) else None
            entity_system = node.content.get("entity_system") if isinstance(node.content, dict) else None
            
            if entity_id and entity_system:
                # Check for existing entity for this user
                existing = await conn.fetchrow(
                    """
                    SELECT node_id, content 
                    FROM memory.nodes 
                    WHERE user_id = $1 AND entity_id = $2 AND entity_system = $3
                    """,
                    user_id, entity_id, entity_system
                )
                
                if existing:
                    # Update existing entity
                    existing_content = json.loads(existing['content'])
                    
                    logger.info("updating_user_entity",
                               user_id=user_id,
                               entity_id=entity_id,
                               existing_keys=list(existing_content.get('entity_data', {}).keys()),
                               new_keys=list(node.content.get('entity_data', {}).keys()))
                    
                    # Merge content
                    if isinstance(node.content, dict) and isinstance(existing_content, dict):
                        if 'entity_data' in existing_content and 'entity_data' in node.content:
                            existing_content['entity_data'].update(node.content.get('entity_data', {}))
                        else:
                            existing_content.update(node.content)
                        
                        existing_content['last_updated'] = datetime_to_iso_utc(utc_now())
                        existing_content['update_count'] = existing_content.get('update_count', 0) + 1
                    
                    # Update the node
                    await conn.execute(
                        """
                        UPDATE memory.nodes SET
                            content = $1,
                            tags = $2,
                            last_accessed = NOW(),
                            access_count = access_count + 1
                        WHERE node_id = $3
                        """,
                        json.dumps(existing_content),
                        list(node.tags) if node.tags else [],
                        existing['node_id']
                    )
                    
                    logger.info("user_entity_updated",
                               node_id=str(existing['node_id']),
                               user_id=user_id,
                               entity_id=entity_id)
                    
                    return str(existing['node_id'])
            
            # Insert new node
            node_id = await conn.fetchval(
                """
                INSERT INTO memory.nodes (
                    user_id, content, context_type, summary,
                    base_relevance, tags, metadata,
                    entity_id, entity_type, entity_system
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING node_id
                """,
                user_id,
                json.dumps(node.content),
                node.context_type.value,
                node.summary,
                node.base_relevance,
                list(node.tags) if node.tags else [],
                '{}',  # MemoryNode doesn't have metadata field
                entity_id,
                node.content.get("entity_type") if isinstance(node.content, dict) else None,
                entity_system
            )
            
            logger.info("memory_node_stored",
                       node_id=str(node_id),
                       user_id=user_id,
                       context_type=node.context_type.value)
            
            return str(node_id)
    
    async def get_node(self, node_id: str, user_id: str) -> Optional[MemoryNode]:
        """Get a specific node by ID within user scope."""
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM memory.nodes 
                WHERE node_id = $1 AND user_id = $2
                """,
                UUID(node_id), user_id
            )
            
            if row:
                return self._row_to_memory_node(row)
            return None
    
    async def get_nodes_by_user(self, 
                               user_id: str,
                               context_filter: Optional[Set[ContextType]] = None,
                               limit: Optional[int] = None) -> List[MemoryNode]:
        """Get all nodes for a user with optional filters."""
        async with self.acquire() as conn:
            query = "SELECT * FROM memory.nodes WHERE user_id = $1"
            params = [user_id]
            
            if context_filter:
                context_values = [ct.value for ct in context_filter]
                query += " AND context_type = ANY($2)"
                params.append(context_values)
            
            query += " ORDER BY created_at DESC"
            
            if limit:
                query += f" LIMIT {limit}"
            
            rows = await conn.fetch(query, *params)
            return [self._row_to_memory_node(row) for row in rows]
    
    async def store_relationship(self,
                               user_id: str,
                               from_node_id: str,
                               to_node_id: str,
                               relationship_type: RelationshipType,
                               strength: float = 1.0,
                               metadata: Optional[Dict] = None) -> None:
        """Store a relationship between nodes within user scope."""
        async with self.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO memory.relationships (
                    user_id, from_node_id, to_node_id, 
                    relationship_type, strength, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (user_id, from_node_id, to_node_id, relationship_type) 
                DO UPDATE SET strength = $5, metadata = $6
                """,
                user_id,
                UUID(from_node_id),
                UUID(to_node_id),
                relationship_type.value,
                strength,
                json.dumps(metadata) if metadata else '{}'
            )
    
    async def get_relationships(self, node_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Get all relationships for a node within user scope."""
        async with self.acquire() as conn:
            # Get outgoing relationships
            out_rows = await conn.fetch(
                """
                SELECT to_node_id as node_id, relationship_type as type, 
                       strength, metadata, 'out' as direction
                FROM memory.relationships
                WHERE user_id = $1 AND from_node_id = $2
                """,
                user_id, UUID(node_id)
            )
            
            # Get incoming relationships
            in_rows = await conn.fetch(
                """
                SELECT from_node_id as node_id, relationship_type as type,
                       strength, metadata, 'in' as direction
                FROM memory.relationships
                WHERE user_id = $1 AND to_node_id = $2
                """,
                user_id, UUID(node_id)
            )
            
            relationships = []
            for row in out_rows + in_rows:
                relationships.append({
                    'node_id': str(row['node_id']),
                    'type': row['type'],
                    'strength': row['strength'],
                    'metadata': json.loads(row['metadata']),
                    'direction': row['direction']
                })
            
            return relationships
    
    async def search_nodes(self,
                          user_id: str,
                          query: str,
                          context_filter: Optional[Set[ContextType]] = None,
                          limit: int = 50) -> List[MemoryNode]:
        """Search nodes using PostgreSQL full-text search and JSONB operators."""
        async with self.acquire() as conn:
            # Build search conditions
            conditions = ["user_id = $1"]
            params = [user_id]
            param_count = 1
            
            # Add text search on summary
            if query:
                param_count += 1
                conditions.append(f"(summary ILIKE ${param_count} OR content::text ILIKE ${param_count})")
                params.append(f"%{query}%")
            
            # Add context filter
            if context_filter:
                param_count += 1
                context_values = [ct.value for ct in context_filter]
                conditions.append(f"context_type = ANY(${param_count})")
                params.append(context_values)
            
            where_clause = " AND ".join(conditions)
            
            rows = await conn.fetch(
                f"""
                SELECT * FROM memory.nodes
                WHERE {where_clause}
                ORDER BY 
                    CASE WHEN summary ILIKE $2 THEN 0 ELSE 1 END,
                    created_at DESC
                LIMIT {limit}
                """,
                *params
            )
            
            return [self._row_to_memory_node(row) for row in rows]
    
    async def update_node_access(self, node_id: str, user_id: str) -> None:
        """Update node access timestamp and count."""
        async with self.acquire() as conn:
            await conn.execute(
                """
                UPDATE memory.nodes 
                SET last_accessed = NOW(), access_count = access_count + 1
                WHERE node_id = $1 AND user_id = $2
                """,
                UUID(node_id), user_id
            )
    
    async def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get memory statistics for a user."""
        async with self.acquire() as conn:
            # Get basic stats
            stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) as node_count,
                    COUNT(DISTINCT entity_id) FILTER (WHERE entity_id IS NOT NULL) as entity_count,
                    array_agg(DISTINCT context_type) as context_types,
                    MAX(created_at) as latest_node,
                    MIN(created_at) as earliest_node
                FROM memory.nodes
                WHERE user_id = $1
                """,
                user_id
            )
            
            # Get relationship count
            rel_count = await conn.fetchval(
                "SELECT COUNT(*) FROM memory.relationships WHERE user_id = $1",
                user_id
            )
            
            return {
                'user_id': user_id,
                'node_count': stats['node_count'],
                'entity_count': stats['entity_count'],
                'relationship_count': rel_count,
                'context_types': stats['context_types'] or [],
                'latest_node': stats['latest_node'].isoformat() if stats['latest_node'] else None,
                'earliest_node': stats['earliest_node'].isoformat() if stats['earliest_node'] else None
            }
    
    async def cleanup_old_nodes(self, user_id: str, days: int = 30) -> int:
        """Remove nodes older than specified days for a user."""
        async with self.acquire() as conn:
            deleted = await conn.fetchval(
                """
                DELETE FROM memory.nodes
                WHERE user_id = $1 AND created_at < NOW() - INTERVAL '%s days'
                RETURNING COUNT(*)
                """,
                user_id, days
            )
            
            logger.info("old_nodes_cleaned",
                       user_id=user_id,
                       days=days,
                       deleted_count=deleted)
            
            return deleted
    
    def _row_to_memory_node(self, row) -> MemoryNode:
        """Convert a database row to a MemoryNode object."""
        node = MemoryNode(
            node_id=str(row['node_id']),
            content=json.loads(row['content']),
            context_type=ContextType(row['context_type']),
            summary=row['summary'],
            created_at=row['created_at'],
            last_accessed=row['last_accessed'],
            base_relevance=row['base_relevance'],
            tags=set(row['tags']) if row['tags'] else set()
        )
        # Set access count separately as it's not in constructor
        node.access_count = row['access_count']
        return node


# Global instance management
_postgres_backend: Optional[PostgresMemoryBackend] = None


async def get_postgres_backend() -> PostgresMemoryBackend:
    """Get or create the global PostgreSQL backend instance."""
    global _postgres_backend
    if _postgres_backend is None:
        _postgres_backend = PostgresMemoryBackend()
        await _postgres_backend.initialize()
    return _postgres_backend


async def close_postgres_backend():
    """Close the global PostgreSQL backend."""
    global _postgres_backend
    if _postgres_backend:
        await _postgres_backend.close()
        _postgres_backend = None