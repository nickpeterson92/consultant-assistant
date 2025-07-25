-- PostgreSQL schema for persistent user memory graphs
-- Uses best practices: UUIDs, proper indexes, constraints, partitioning ready

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For text search
CREATE EXTENSION IF NOT EXISTS "btree_gin"; -- For composite indexes

-- Create schema for better organization
CREATE SCHEMA IF NOT EXISTS memory;

-- Memory nodes table (user-scoped)
CREATE TABLE IF NOT EXISTS memory.nodes (
    node_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    content JSONB NOT NULL,
    context_type TEXT NOT NULL,
    summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_accessed TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    access_count INTEGER DEFAULT 1,
    base_relevance REAL DEFAULT 0.5 CHECK (base_relevance BETWEEN 0 AND 1),
    tags TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    
    -- Entity deduplication fields
    entity_id TEXT,
    entity_type TEXT,
    entity_system TEXT,
    
    -- Ensure entity uniqueness per user
    CONSTRAINT unique_user_entity UNIQUE (user_id, entity_id, entity_system),
    
    -- Add check constraints
    CONSTRAINT valid_context_type CHECK (context_type IN ('search_result', 'user_selection', 'tool_output', 'domain_entity', 'completed_action', 'conversation_fact', 'temporary_state'))
);

-- Create indexes for performance
CREATE INDEX idx_nodes_user_id ON memory.nodes (user_id);
CREATE INDEX idx_nodes_user_context ON memory.nodes (user_id, context_type);
CREATE INDEX idx_nodes_user_created ON memory.nodes (user_id, created_at DESC);
CREATE INDEX idx_nodes_entity_lookup ON memory.nodes (user_id, entity_id, entity_system) WHERE entity_id IS NOT NULL;
CREATE INDEX idx_nodes_tags ON memory.nodes USING GIN (tags);
CREATE INDEX idx_nodes_content ON memory.nodes USING GIN (content);
CREATE INDEX idx_nodes_summary_trgm ON memory.nodes USING GIN (summary gin_trgm_ops);

-- Relationships table
CREATE TABLE IF NOT EXISTS memory.relationships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    from_node_id UUID NOT NULL,
    to_node_id UUID NOT NULL,
    relationship_type TEXT NOT NULL,
    strength REAL DEFAULT 1.0 CHECK (strength BETWEEN 0 AND 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    
    -- Ensure relationships are between nodes of the same user
    FOREIGN KEY (from_node_id) REFERENCES memory.nodes(node_id) ON DELETE CASCADE,
    FOREIGN KEY (to_node_id) REFERENCES memory.nodes(node_id) ON DELETE CASCADE,
    
    -- Prevent duplicate relationships
    CONSTRAINT unique_user_relationship UNIQUE (user_id, from_node_id, to_node_id, relationship_type),
    
    -- Add check constraints
    CONSTRAINT valid_relationship_type CHECK (relationship_type IN ('led_to', 'relates_to', 'depends_on', 'produces', 'belongs_to'))
);

-- Create indexes for relationships
CREATE INDEX idx_relationships_user ON memory.relationships (user_id);
CREATE INDEX idx_relationships_from ON memory.relationships (user_id, from_node_id);
CREATE INDEX idx_relationships_to ON memory.relationships (user_id, to_node_id);
CREATE INDEX idx_relationships_type ON memory.relationships (user_id, relationship_type);

-- User memory metadata table
CREATE TABLE IF NOT EXISTS memory.user_metadata (
    user_id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_activity TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    total_nodes INTEGER DEFAULT 0,
    total_relationships INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}'
);

-- Create function to update last_accessed timestamp
CREATE OR REPLACE FUNCTION memory.update_last_accessed()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_accessed = NOW();
    NEW.access_count = NEW.access_count + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for access updates
CREATE TRIGGER update_node_last_accessed
    BEFORE UPDATE ON memory.nodes
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION memory.update_last_accessed();

-- Create function to maintain user metadata
CREATE OR REPLACE FUNCTION memory.update_user_metadata()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO memory.user_metadata (user_id, total_nodes)
        VALUES (NEW.user_id, 1)
        ON CONFLICT (user_id) DO UPDATE
        SET total_nodes = memory.user_metadata.total_nodes + 1,
            last_activity = NOW();
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE memory.user_metadata
        SET total_nodes = GREATEST(0, total_nodes - 1),
            last_activity = NOW()
        WHERE user_id = OLD.user_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for user metadata
CREATE TRIGGER maintain_user_node_count
    AFTER INSERT OR DELETE ON memory.nodes
    FOR EACH ROW
    EXECUTE FUNCTION memory.update_user_metadata();

-- Create materialized view for user memory statistics (refresh periodically)
CREATE MATERIALIZED VIEW IF NOT EXISTS memory.user_stats AS
SELECT 
    n.user_id,
    COUNT(DISTINCT n.node_id) as node_count,
    COUNT(DISTINCT r.id) as relationship_count,
    COUNT(DISTINCT n.entity_id) FILTER (WHERE n.entity_id IS NOT NULL) as entity_count,
    array_agg(DISTINCT n.context_type) as context_types,
    MAX(n.created_at) as latest_node,
    MIN(n.created_at) as earliest_node
FROM memory.nodes n
LEFT JOIN memory.relationships r ON r.user_id = n.user_id
GROUP BY n.user_id;

CREATE UNIQUE INDEX idx_user_stats_user_id ON memory.user_stats (user_id);

-- Add comments for documentation
COMMENT ON TABLE memory.nodes IS 'Stores memory nodes for each user with full content and metadata';
COMMENT ON TABLE memory.relationships IS 'Stores directed relationships between memory nodes';
COMMENT ON TABLE memory.user_metadata IS 'Tracks user-level memory statistics and metadata';
COMMENT ON COLUMN memory.nodes.context_type IS 'Type of memory node: entity, action, search_result, or plan';
COMMENT ON COLUMN memory.nodes.entity_id IS 'External system ID for deduplication (e.g., Salesforce ID, Jira key)';
COMMENT ON COLUMN memory.relationships.relationship_type IS 'Type of relationship: led_to, relates_to, depends_on, produces, belongs_to';