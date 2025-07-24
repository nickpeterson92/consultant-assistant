"""SQLite schema for persistent memory storage."""

MEMORY_SCHEMA = """
-- Memory nodes table
CREATE TABLE IF NOT EXISTS memory_nodes (
    node_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    content TEXT NOT NULL,  -- JSON
    context_type TEXT NOT NULL,
    summary TEXT,
    created_at TIMESTAMP NOT NULL,
    last_accessed TIMESTAMP NOT NULL,
    access_count INTEGER DEFAULT 1,
    base_relevance REAL DEFAULT 0.5,
    tags TEXT,  -- JSON array
    metadata TEXT,  -- JSON
    
    -- Entity-specific fields for deduplication
    entity_id TEXT,  -- e.g., Salesforce ID, Jira key
    entity_type TEXT,  -- e.g., Account, Contact, Issue
    entity_system TEXT,  -- e.g., salesforce, jira, servicenow
    
    -- Prevent duplicate entities
    UNIQUE(entity_id, entity_system)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_thread_id ON memory_nodes(thread_id);
CREATE INDEX IF NOT EXISTS idx_context_type ON memory_nodes(context_type);
CREATE INDEX IF NOT EXISTS idx_created_at ON memory_nodes(created_at);
CREATE INDEX IF NOT EXISTS idx_entity_lookup ON memory_nodes(entity_id, entity_type, entity_system);

-- Relationships table
CREATE TABLE IF NOT EXISTS memory_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_node_id TEXT NOT NULL,
    to_node_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    strength REAL DEFAULT 1.0,
    created_at TIMESTAMP NOT NULL,
    metadata TEXT,  -- JSON
    
    FOREIGN KEY (from_node_id) REFERENCES memory_nodes(node_id) ON DELETE CASCADE,
    FOREIGN KEY (to_node_id) REFERENCES memory_nodes(node_id) ON DELETE CASCADE,
    
    -- Prevent duplicate relationships
    UNIQUE(from_node_id, to_node_id, relationship_type)
);

-- Create indexes for relationships
CREATE INDEX IF NOT EXISTS idx_from_node ON memory_relationships(from_node_id);
CREATE INDEX IF NOT EXISTS idx_to_node ON memory_relationships(to_node_id);
CREATE INDEX IF NOT EXISTS idx_rel_type ON memory_relationships(relationship_type);

-- Thread metadata table
CREATE TABLE IF NOT EXISTS memory_threads (
    thread_id TEXT PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    last_activity TIMESTAMP NOT NULL,
    agent_name TEXT,
    task_id TEXT,
    metadata TEXT  -- JSON
);

-- Full-text search support
CREATE VIRTUAL TABLE IF NOT EXISTS memory_search 
USING fts5(
    node_id UNINDEXED,
    content,
    summary,
    tags,
    tokenize='porter'
);

-- Trigger to keep FTS index updated
CREATE TRIGGER IF NOT EXISTS memory_search_insert 
AFTER INSERT ON memory_nodes BEGIN
    INSERT INTO memory_search(node_id, content, summary, tags)
    VALUES (new.node_id, new.content, new.summary, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS memory_search_update
AFTER UPDATE ON memory_nodes BEGIN
    UPDATE memory_search 
    SET content = new.content, summary = new.summary, tags = new.tags
    WHERE node_id = new.node_id;
END;

CREATE TRIGGER IF NOT EXISTS memory_search_delete
AFTER DELETE ON memory_nodes BEGIN
    DELETE FROM memory_search WHERE node_id = old.node_id;
END;
"""

def init_database(db_path: str):
    """Initialize the database with the schema."""
    import sqlite3
    
    conn = sqlite3.connect(db_path)
    conn.executescript(MEMORY_SCHEMA)
    conn.commit()
    conn.close()