# PostgreSQL Memory Migration Guide

## Overview

This guide describes the hybrid memory storage system that uses PostgreSQL for persistent user memories and SQLite for transient processing state.

## Architecture

### Storage Split

**PostgreSQL (Persistent)**
- User memory graphs that persist across sessions
- Entity deduplication at user scope
- Long-term conversation context
- Handles concurrent access from multiple instances

**SQLite (Transient)**
- Thread-local processing state
- Workflow checkpoints
- Temporary execution memory
- Fast local access without network overhead

### Data Flow

```
User Session Start
       ↓
Load from PostgreSQL → SQLite Cache
       ↓
    Processing
       ↓
Write-through to PostgreSQL (for persistent data)
```

## Setup Instructions

### 1. Database Setup

```bash
# Create database
createdb consultant_assistant

# Apply schema
psql consultant_assistant < src/memory/storage/postgres_schema.sql
```

### 2. Environment Variables

```bash
# Required
export POSTGRES_DB=consultant_assistant
export POSTGRES_USER=your_user
export POSTGRES_PASSWORD=your_password

# Optional (defaults shown)
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_POOL_SIZE=20
export POSTGRES_SSL=false
```

### 3. Code Integration

The system automatically uses the hybrid manager when available. Key changes:

```python
# In orchestrator/plan_and_execute.py
from src.memory.core.hybrid_memory_manager import ensure_user_memories

# Load user memories on session start
memory = await ensure_user_memories(user_id)

# Store persistent memory (goes to both SQLite and PostgreSQL)
await manager.store_persistent_memory(user_id, content, context_type)

# Store transient memory (SQLite only)
manager.store_transient_memory(thread_id, content, context_type)
```

## PostgreSQL Best Practices Implemented

1. **Connection Pooling**: Uses asyncpg with configurable pool size
2. **Proper Indexes**: Composite indexes for common query patterns
3. **UUID Primary Keys**: For distributed systems compatibility
4. **JSONB Storage**: For flexible content and metadata
5. **Constraints**: Unique constraints for entity deduplication
6. **Triggers**: Automatic timestamp and count updates
7. **Schema Organization**: Dedicated `memory` schema
8. **Materialized Views**: For user statistics (refresh periodically)

## Memory Scoping

- **User Scope**: All persistent memories filtered by user_id
- **Entity Deduplication**: Unique per (user_id, entity_id, entity_system)
- **Relationships**: Scoped to user to prevent cross-user data leaks

## Performance Considerations

1. **Initial Load**: First session loads user memories from PostgreSQL
2. **Cache Duration**: SQLite cache refreshes every 60 seconds
3. **Write-through**: Persistent memories written to both stores
4. **Connection Pool**: 20 connections by default, adjustable

## Monitoring

Check logs for:
- `loading_user_memories_from_postgres`: Initial load operations
- `node_persisted_to_postgres`: Successful persistence
- `failed_to_persist_to_postgres`: Write failures (SQLite continues working)

## Migration Notes

Since this is a fresh start:
1. No data migration needed from SQLite
2. System continues to work if PostgreSQL is unavailable (SQLite fallback)
3. Can be rolled out gradually by user

# Connect to PostgreSQL
podman exec -it consultant_postgres psql -U postgres -d consultant_assistant

# Delete all memory data (nuclear option)
podman exec -it consultant_postgres psql -U postgres -d consultant_assistant -c "TRUNCATE memory.nodes CASCADE; TRUNCATE memory.user_metadata;"

# Delete specific user's data
podman exec -it consultant_postgres psql -U postgres -d consultant_assistant -c "DELETE FROM memory.nodes WHERE user_id = 'nick';"

# Quick counts
podman exec -it consultant_postgres psql -U postgres -d consultant_assistant -c "SELECT user_id, COUNT(*) FROM memory.nodes GROUP BY user_id;"

# See recent memories
podman exec -it consultant_postgres psql -U postgres -d consultant_assistant -c "SELECT node_id, context_type, summary FROM memory.nodes ORDER BY created_at DESC LIMIT 10;"

# Search for specific content
podman exec -it consultant_postgres psql -U postgres -d consultant_assistant -c "SELECT summary FROM memory.nodes WHERE content::text ILIKE '%genepoint%';"

# Interactive session
podman exec -it consultant_postgres psql -U postgres -d consultant_assistant

The nuclear delete is:
podman exec -it consultant_postgres psql -U postgres -d consultant_assistant -c "TRUNCATE memory.nodes CASCADE;"

# Look for domain entities specifically
podman exec -it consultant_postgres psql -U postgres -d consultant_assistant -c "SELECT node_id, context_type, summary, content->>'entity_name' as name FROM memory.nodes WHERE context_type = 'domain_entity';"

# Check all recent nodes to see what's there
podman exec -it consultant_postgres psql -U postgres -d consultant_assistant -c "SELECT context_type, summary, created_at FROM memory.nodes ORDER BY created_at DESC LIMIT 20;"

# Look for any Salesforce entities
podman exec -it consultant_postgres psql -U postgres -d consultant_assistant -c "SELECT summary, content->>'entity_id' as id, content->>'entity_name' as name FROM memory.nodes WHERE content->>'entity_system' = 'salesforce';"

# See ALL GenePoint related content with more details
podman exec -it consultant_postgres psql -U postgres -d consultant_assistant -c "SELECT context_type, summary, content->>'entity_name' as entity_name, content->>'entity_id' as entity_id FROM memory.nodes WHERE content::text ILIKE
'%genepoint%';"

podman exec -it consultant_postgres psql -U postgres -d consultant_assistant -c "SELECT node_id, context_type, summary, content->>'entity_name' as name FROM memory.nodes WHERE context_type = 'domain_entity';"

podman exec -it consultant_postgres psql -U postgres -d consultant_assistant -c "SELECT context_type, COUNT(*) FROM memory.nodes GROUP BY context_type;"

podman exec -it consultant_postgres psql -U postgres -d consultant_assistant -c "SELECT summary, jsonb_pretty(content) FROM memory.nodes WHERE context_type = 'tool_output' LIMIT 1;"

podman exec -it consultant_postgres psql -U postgres -d consultant_assistant -c "SELECT context_type, summary FROM memory.nodes WHERE summary LIKE '%salesforce%' ORDER BY created_at DESC;"
