# PostgreSQL Cheatsheet for Consultant Assistant

## Connection
```bash
# Connect to database
psql -h localhost -p 5433 -U postgres -d consultant_assistant

# Or with your connection string
psql postgresql://postgres:password@localhost:5433/consultant_assistant
```

## Investigation Commands

### View Schema and Tables
```sql
-- List all schemas
\dn

-- List all tables in memory schema
\dt memory.*

-- Describe a specific table
\d memory.nodes
\d memory.relationships
\d memory.user_metadata

-- View table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables 
WHERE schemaname = 'memory'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Inspect Data
```sql
-- Count nodes per user
SELECT user_id, COUNT(*) as node_count 
FROM memory.nodes 
GROUP BY user_id;

-- View recent nodes
SELECT node_id, user_id, context_type, summary, created_at 
FROM memory.nodes 
ORDER BY created_at DESC 
LIMIT 10;

-- View nodes for specific user
SELECT node_id, context_type, summary, created_at 
FROM memory.nodes 
WHERE user_id = 'nick'
ORDER BY created_at DESC;

-- Check entity deduplication
SELECT user_id, entity_id, entity_system, COUNT(*) 
FROM memory.nodes 
WHERE entity_id IS NOT NULL 
GROUP BY user_id, entity_id, entity_system 
HAVING COUNT(*) > 1;

-- View relationships
SELECT r.*, 
       n1.summary as from_summary, 
       n2.summary as to_summary
FROM memory.relationships r
JOIN memory.nodes n1 ON r.from_node_id = n1.node_id
JOIN memory.nodes n2 ON r.to_node_id = n2.node_id
WHERE r.user_id = 'nick'
LIMIT 20;

-- Search nodes by content
SELECT node_id, summary, content->>'entity_name' as entity_name
FROM memory.nodes
WHERE content::text ILIKE '%genepoint%';

-- Find domain entities (regardless of user_id)
SELECT user_id, context_type, 
       content->>'entity_id' as entity_id,
       content->>'entity_name' as entity_name,
       content->>'entity_type' as entity_type,
       created_at
FROM memory.nodes
WHERE context_type = 'domain_entity'
ORDER BY created_at DESC;

-- Check what's being stored under agent thread IDs
SELECT user_id, COUNT(*) as node_count, 
       array_agg(DISTINCT context_type) as context_types
FROM memory.nodes
WHERE user_id LIKE '%-agent-%' OR user_id LIKE 'salesforce-%' OR user_id LIKE 'jira-%' OR user_id LIKE 'servicenow-%'
GROUP BY user_id;

-- Find tool outputs by agent
SELECT user_id, 
       content->>'tool_name' as tool_name,
       content->>'agent_name' as agent_name,
       created_at
FROM memory.nodes
WHERE context_type = 'tool_output'
ORDER BY created_at DESC
LIMIT 10;
```

## Reset/Delete Commands

### Delete All Data (Nuclear Option)
```sql
-- Delete all memories for all users
TRUNCATE memory.nodes CASCADE;
TRUNCATE memory.user_metadata;

-- Verify deletion
SELECT COUNT(*) FROM memory.nodes;
SELECT COUNT(*) FROM memory.relationships;
```

### Move Misplaced Agent Data to User
```sql
-- See what agent thread data exists
SELECT DISTINCT user_id FROM memory.nodes WHERE user_id LIKE '%-agent-%' OR user_id LIKE 'salesforce-%';

-- Move all agent thread data to proper user (BE CAREFUL!)
-- This assumes all agent data should belong to user 'nick'
UPDATE memory.nodes 
SET user_id = 'nick' 
WHERE user_id LIKE 'salesforce-%' 
   OR user_id LIKE 'jira-%' 
   OR user_id LIKE 'servicenow-%';

-- Update relationships too
UPDATE memory.relationships 
SET user_id = 'nick' 
WHERE user_id LIKE 'salesforce-%' 
   OR user_id LIKE 'jira-%' 
   OR user_id LIKE 'servicenow-%';
```

### Delete Data for Specific User
```sql
-- Delete all memories for a specific user
DELETE FROM memory.nodes WHERE user_id = 'nick';

-- Delete user metadata
DELETE FROM memory.user_metadata WHERE user_id = 'nick';
```

### Delete Old Data
```sql
-- Delete nodes older than 30 days
DELETE FROM memory.nodes 
WHERE created_at < NOW() - INTERVAL '30 days';

-- Delete specific context types
DELETE FROM memory.nodes 
WHERE user_id = 'nick' 
AND context_type = 'temporary_state';
```

### Selective Deletion
```sql
-- Delete specific entities
DELETE FROM memory.nodes 
WHERE entity_id = '001XX000003DHPa' 
AND entity_system = 'salesforce';

-- Delete orphaned relationships
DELETE FROM memory.relationships r
WHERE NOT EXISTS (
    SELECT 1 FROM memory.nodes n 
    WHERE n.node_id = r.from_node_id
) OR NOT EXISTS (
    SELECT 1 FROM memory.nodes n 
    WHERE n.node_id = r.to_node_id
);
```

## Debugging Queries

### Check for Issues
```sql
-- Find duplicate entities
SELECT user_id, entity_id, entity_system, COUNT(*) as duplicates
FROM memory.nodes
WHERE entity_id IS NOT NULL
GROUP BY user_id, entity_id, entity_system
HAVING COUNT(*) > 1;

-- Find nodes without relationships
SELECT n.node_id, n.summary
FROM memory.nodes n
LEFT JOIN memory.relationships r1 ON n.node_id = r1.from_node_id
LEFT JOIN memory.relationships r2 ON n.node_id = r2.to_node_id
WHERE r1.id IS NULL AND r2.id IS NULL
AND n.user_id = 'nick';

-- Check timezone issues
SELECT node_id, created_at, created_at AT TIME ZONE 'UTC' as utc_time
FROM memory.nodes
LIMIT 5;
```

### Performance Analysis
```sql
-- Index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'memory'
ORDER BY idx_scan DESC;

-- Slow queries (requires pg_stat_statements extension)
SELECT query, calls, mean_exec_time, total_exec_time
FROM pg_stat_statements
WHERE query LIKE '%memory.%'
ORDER BY mean_exec_time DESC
LIMIT 10;
```

## Maintenance

### Vacuum and Analyze
```sql
-- Update statistics
ANALYZE memory.nodes;
ANALYZE memory.relationships;

-- Clean up dead rows
VACUUM memory.nodes;
VACUUM memory.relationships;

-- Full vacuum (locks table)
VACUUM FULL memory.nodes;
```

### Refresh Materialized Views
```sql
-- Refresh user statistics
REFRESH MATERIALIZED VIEW memory.user_stats;

-- Refresh with concurrency (doesn't lock)
REFRESH MATERIALIZED VIEW CONCURRENTLY memory.user_stats;
```

## Issue: Entities Stored Under Wrong user_id

### Problem
Entities are being created but stored under agent thread IDs (e.g., "salesforce-277f1740-...") instead of the actual user_id ("nick"). This happens because:
1. The orchestrator stores `user_id` in both `state["user_id"]` AND `config["configurable"]["user_id"]`
2. Agent caller tools were only checking `state["user_id"]`, not `state["configurable"]["user_id"]`
3. Without user_id, `memory_writer.py` falls back to using thread_id as the memory key

### Fix Applied
Updated `agent_caller_tools.py` to check both locations:
```python
# Include user_id if available in state (check both direct and configurable)
if state:
    if "user_id" in state:
        extracted_context["user_id"] = state["user_id"]
    elif "configurable" in state and "user_id" in state["configurable"]:
        extracted_context["user_id"] = state["configurable"]["user_id"]
```

### Investigation
```sql
-- Check if entities are being stored under agent thread IDs
SELECT user_id, COUNT(*) as entity_count
FROM memory.nodes
WHERE context_type = 'domain_entity'
GROUP BY user_id;

-- See all GenePoint entities regardless of user_id
SELECT user_id, 
       content->>'entity_id' as entity_id,
       content->>'entity_name' as entity_name
FROM memory.nodes
WHERE content::text ILIKE '%genepoint%'
  AND context_type = 'domain_entity';
```

### Fix: Move Agent Data to Correct User
```sql
-- First, see what needs to be moved
SELECT user_id, COUNT(*) as nodes, 
       array_agg(DISTINCT context_type) as types
FROM memory.nodes
WHERE user_id LIKE 'salesforce-%'
   OR user_id LIKE 'jira-%' 
   OR user_id LIKE 'servicenow-%'
GROUP BY user_id;

-- Move nodes to correct user
BEGIN;
-- Update nodes
UPDATE memory.nodes
SET user_id = 'nick'
WHERE (user_id LIKE 'salesforce-%' 
   OR user_id LIKE 'jira-%' 
   OR user_id LIKE 'servicenow-%')
  AND EXISTS (
    SELECT 1 FROM memory.nodes existing
    WHERE existing.user_id = 'nick'
  );

-- Update relationships
UPDATE memory.relationships
SET user_id = 'nick'
WHERE (user_id LIKE 'salesforce-%' 
   OR user_id LIKE 'jira-%' 
   OR user_id LIKE 'servicenow-%');

COMMIT;
```

## Quick Reset Script
```bash
#!/bin/bash
# reset_memory_db.sh

echo "⚠️  This will delete ALL memory data. Continue? (y/N)"
read -r response

if [[ "$response" == "y" ]]; then
    psql postgresql://postgres:password@localhost:5433/consultant_assistant << EOF
    -- Delete all data
    TRUNCATE memory.nodes CASCADE;
    TRUNCATE memory.user_metadata;
    
    -- Verify
    SELECT 'Nodes remaining: ' || COUNT(*) FROM memory.nodes;
    SELECT 'Relationships remaining: ' || COUNT(*) FROM memory.relationships;
    
    -- Vacuum
    VACUUM ANALYZE memory.nodes;
    VACUUM ANALYZE memory.relationships;
EOF
    echo "✅ Memory database reset complete"
else
    echo "❌ Reset cancelled"
fi
```

## Export/Import

### Export user data
```bash
# Export specific user's memories
pg_dump -h localhost -p 5433 -U postgres -d consultant_assistant \
    --table="memory.nodes" \
    --table="memory.relationships" \
    --where="user_id='nick'" \
    > nick_memories_backup.sql
```

### Import data
```bash
psql -h localhost -p 5433 -U postgres -d consultant_assistant < nick_memories_backup.sql
```

## Monitor Active Connections
```sql
-- View active connections
SELECT pid, usename, application_name, client_addr, state
FROM pg_stat_activity
WHERE datname = 'consultant_assistant';

-- Kill a connection
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE pid = <process_id>;
```