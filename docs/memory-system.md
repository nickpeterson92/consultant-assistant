# Memory System Documentation

## Overview

The memory system provides intelligent, persistent storage of structured information extracted from conversations. It uses TrustCall for reliable extraction, Pydantic for data validation, and SQLite for durable storage. The system automatically identifies and stores CRM entities (accounts, contacts, opportunities) while maintaining relationships and avoiding duplicates.

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                      Memory System Architecture                 │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────┐   │
│  │   TrustCall     │  │     Pydantic     │  │    SQLite     │   │
│  │   Extraction    │─>│    Validation    │─>│   Storage     │   │
│  └─────────────────┘  └──────────────────┘  └───────────────┘   │
│           ▲                                           │         │
│           │                                           ▼         │
│  ┌─────────────────┐                        ┌───────────────┐   │
│  │   LangGraph     │                        │     Async     │   │
│  │  Background     │                        │    Adapter    │   │
│  │     Tasks       │                        │               │   │
│  └─────────────────┘                        └───────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Conversation** → User and agent exchange messages
2. **Extraction** → TrustCall identifies entities in messages
3. **Validation** → Pydantic ensures data integrity
4. **Persistence** → AsyncStoreAdapter saves to SQLite
5. **Retrieval** → Memory loaded for context in future conversations

## Memory Schema

### Core Data Models

```python
@dataclass
class SimpleMemory:
    """Root memory container with all CRM entities"""
    accounts: List[SimpleAccount] = field(default_factory=list)
    contacts: List[SimpleContact] = field(default_factory=list)
    opportunities: List[SimpleOpportunity] = field(default_factory=list)
    cases: List[SimpleCase] = field(default_factory=list)
    tasks: List[SimpleTask] = field(default_factory=list)
    leads: List[SimpleLead] = field(default_factory=list)
```

### Entity Schemas

**SimpleAccount**
```python
@dataclass
class SimpleAccount:
    id: Optional[str] = None      # Salesforce ID
    name: str                     # Company name
```

**SimpleContact**
```python
@dataclass
class SimpleContact:
    id: Optional[str] = None      # Salesforce ID
    name: str                     # Full name
    account_id: Optional[str] = None  # Related account
    account_name: Optional[str] = None
```

**SimpleOpportunity**
```python
@dataclass
class SimpleOpportunity:
    id: Optional[str] = None      # Salesforce ID
    name: str                     # Opportunity name
    stage: Optional[str] = None   # Sales stage
    amount: Optional[float] = None  # Deal value
    close_date: Optional[str] = None
    account_id: Optional[str] = None
    account_name: Optional[str] = None
```

**SimpleCase**
```python
@dataclass
class SimpleCase:
    id: Optional[str] = None      # Salesforce ID
    subject: str                  # Case title
    status: Optional[str] = None  # Open/Closed
    priority: Optional[str] = None
    account_id: Optional[str] = None
    contact_id: Optional[str] = None
```

**SimpleTask**
```python
@dataclass
class SimpleTask:
    id: Optional[str] = None      # Salesforce ID
    subject: str                  # Task description
    status: Optional[str] = None  # Completed/Open
    due_date: Optional[str] = None
    related_to_id: Optional[str] = None
    related_to_type: Optional[str] = None
```

**SimpleLead**
```python
@dataclass
class SimpleLead:
    id: Optional[str] = None      # Salesforce ID
    name: str                     # Lead name
    company: Optional[str] = None
    status: Optional[str] = None  # Qualified/Unqualified
    email: Optional[str] = None
```

## Storage Layer

### SQLite Schema

```sql
CREATE TABLE store (
    namespace TEXT NOT NULL,    -- ("memory", user_id)
    key TEXT NOT NULL,         -- "SimpleMemory"
    value TEXT NOT NULL,       -- JSON serialized memory
    PRIMARY KEY (namespace, key)
);
```

### AsyncStoreAdapter

Thread-safe storage access:

```python
class AsyncStoreAdapter:
    """Bridges async LangGraph with sync BaseStore"""
    
    def __init__(self, store: BaseStore):
        self.store = store
        self.executor = ThreadPoolExecutor(max_workers=1)
    
    async def aget(self, namespace: tuple, key: str) -> Optional[Item]:
        """Async get with thread safety"""
        return await asyncio.get_event_loop().run_in_executor(
            self.executor,
            self.store.get,
            namespace,
            key
        )
    
    async def aput(self, namespace: tuple, key: str, value: Item) -> None:
        """Async put with thread safety"""
        await asyncio.get_event_loop().run_in_executor(
            self.executor,
            self.store.put,
            namespace,
            key,
            value
        )
```

## Extraction Process

### TrustCall Integration

```python
# Create specialized extractor
extractor = create_extractor(
    llm,
    tools=[SimpleMemoryExtractor],
    tool_choice="SimpleMemoryExtractor"
)

# Extract entities from conversation
result = await extractor.ainvoke({
    "messages": [
        SystemMessage(content=TRUSTCALL_INSTRUCTION),
        HumanMessage(content=messages_text)
    ]
})
```

### Extraction Instructions

The system uses carefully crafted prompts:

```python
TRUSTCALL_INSTRUCTION = """
Extract ONLY explicitly mentioned Salesforce CRM entities:

Rules:
1. Only extract if explicitly stated (e.g., "Acme Corp account")
2. Preserve exact Salesforce IDs when mentioned
3. Maintain relationships between entities
4. Never infer or create fictional data
5. Handle duplicates by updating existing records
"""
```

### Incremental Updates

Memory updates preserve existing data:

```python
async def update_memory(state: UpdateMemoryState, config: RunnableConfig):
    # Load existing memory
    existing_memory = await store.aget(
        namespace=("memory", user_id),
        key="SimpleMemory"
    )
    
    # Extract new entities
    extraction_result = await extractor.ainvoke({"messages": messages})
    
    # Merge with deduplication
    updated_memory = merge_memories(
        existing_memory or SimpleMemory(),
        extracted_memory
    )
    
    # Persist updated memory
    await store.aput(
        namespace=("memory", user_id),
        key="SimpleMemory",
        value=updated_memory
    )
```

## Deduplication Strategy

### Entity Matching

The system prevents duplicates using intelligent matching:

```python
def add_or_update_item(items: List[T], new_item: T) -> List[T]:
    """Add new item or update existing based on ID/name match"""
    
    # Try to match by ID first
    if hasattr(new_item, 'id') and new_item.id:
        for i, item in enumerate(items):
            if item.id == new_item.id:
                items[i] = new_item  # Update
                return items
    
    # Fall back to name matching
    if hasattr(new_item, 'name'):
        for i, item in enumerate(items):
            if item.name.lower() == new_item.name.lower():
                # Update if new item has more info
                if should_update(item, new_item):
                    items[i] = new_item
                return items
    
    # No match found - add as new
    items.append(new_item)
    return items
```

### Update Logic

Updates preserve the most complete information:

```python
def should_update(existing: T, new: T) -> bool:
    """Determine if new item has more complete data"""
    # New item has ID but existing doesn't
    if hasattr(new, 'id') and new.id and not existing.id:
        return True
    
    # Count non-None fields
    existing_fields = sum(1 for v in asdict(existing).values() if v)
    new_fields = sum(1 for v in asdict(new).values() if v)
    
    return new_fields > existing_fields
```

## Background Processing

### LangGraph Integration

Memory updates happen asynchronously:

```python
# In the main conversation flow
if should_update_memory:
    return [
        Send("update_memory", {
            "messages": state["messages"][-10:],
            "memory": state.get("memory", SimpleMemory()),
            "user_id": state["user_id"]
        })
    ]
```

### Update Triggers

Memory updates trigger when:
1. Every 5 user messages
2. Significant CRM data mentioned
3. Explicit memory request
4. Before conversation summary

## Memory Usage

### Loading Memory

Memory loads at conversation start:

```python
async def initialize_memory(state: OrchestratorState, config: RunnableConfig):
    if state.get("memory_init_done"):
        return state
    
    store = get_async_store_adapter()
    stored_memory = await store.aget(
        namespace=("memory", state["user_id"]),
        key="SimpleMemory"
    )
    
    return {
        "memory": stored_memory or SimpleMemory(),
        "memory_init_done": True
    }
```

### Context Injection

Memory provides context for responses:

```python
def create_memory_context(memory: SimpleMemory) -> str:
    """Format memory for LLM context"""
    context_parts = []
    
    if memory.accounts:
        context_parts.append(
            f"Known accounts: {', '.join(a.name for a in memory.accounts[:5])}"
        )
    
    if memory.contacts:
        context_parts.append(
            f"Known contacts: {', '.join(c.name for c in memory.contacts[:5])}"
        )
    
    # Include other entities...
    
    return "\n".join(context_parts)
```

## Performance Optimization

### Batch Processing

Minimize extraction calls:

```python
# Process multiple messages at once
messages_batch = state["messages"][-10:]  # Last 10 messages
extraction_result = await extractor.ainvoke({
    "messages": [SystemMessage(TRUSTCALL_INSTRUCTION)] + messages_batch
})
```

### Caching Strategy

In-memory cache for active sessions:

```python
class MemoryCache:
    def __init__(self, ttl: int = 3600):
        self.cache: Dict[str, CacheEntry] = {}
        self.ttl = ttl
    
    async def get_or_load(self, user_id: str) -> SimpleMemory:
        if user_id in self.cache:
            entry = self.cache[user_id]
            if time.time() - entry.timestamp < self.ttl:
                return entry.memory
        
        # Load from storage
        memory = await load_from_storage(user_id)
        self.cache[user_id] = CacheEntry(memory, time.time())
        return memory
```

### Storage Optimization

Efficient serialization:

```python
def serialize_memory(memory: SimpleMemory) -> str:
    """Optimize JSON serialization"""
    # Remove None values to save space
    data = asdict(memory)
    cleaned_data = remove_none_values(data)
    return json.dumps(cleaned_data, separators=(',', ':'))
```

## Error Handling

### Extraction Failures

Graceful handling of TrustCall errors:

```python
try:
    extraction_result = await extractor.ainvoke({"messages": messages})
except Exception as e:
    logger.error(f"Memory extraction failed: {e}")
    # Continue without updating memory
    return {"memory_error": str(e)}
```

### Storage Failures

Resilient storage operations:

```python
async def safe_memory_update(store, namespace, key, value):
    """Update memory with retry logic"""
    for attempt in range(3):
        try:
            await store.aput(namespace, key, value)
            return True
        except Exception as e:
            if attempt == 2:
                logger.error(f"Failed to save memory after 3 attempts: {e}")
                return False
            await asyncio.sleep(2 ** attempt)
```

### Validation Errors

Pydantic validation with fallbacks:

```python
try:
    validated_memory = SimpleMemory(**raw_data)
except ValidationError as e:
    logger.warning(f"Memory validation failed: {e}")
    # Create minimal valid memory
    validated_memory = SimpleMemory()
```

## Testing Memory

### Unit Tests

Test extraction accuracy:

```python
async def test_memory_extraction():
    messages = [
        HumanMessage("I spoke with John Smith from Acme Corp"),
        AIMessage("I found the Acme Corp account with ID 001234")
    ]
    
    result = await extract_memory(messages)
    
    assert len(result.accounts) == 1
    assert result.accounts[0].name == "Acme Corp"
    assert result.accounts[0].id == "001234"
    assert len(result.contacts) == 1
    assert result.contacts[0].name == "John Smith"
```

### Integration Tests

Test full memory lifecycle:

```python
async def test_memory_persistence():
    # Create conversation
    state = create_test_state(user_id="test_user")
    
    # Process messages with CRM data
    state = await process_with_memory(state, [
        "Get the Acme Corp account",
        "The account ID is 001234"
    ])
    
    # Verify memory updated
    stored = await load_memory("test_user")
    assert any(a.name == "Acme Corp" for a in stored.accounts)
```

## Best Practices

### 1. Extraction Guidelines

- Only extract explicitly mentioned entities
- Preserve exact IDs when available
- Maintain entity relationships
- Never infer missing data
- Handle variations in naming

### 2. Storage Patterns

- Use consistent namespaces
- Implement proper locking
- Handle concurrent updates
- Regular cleanup of old data
- Monitor storage growth

### 3. Performance Tips

- Batch extraction operations
- Cache frequently accessed memory
- Limit memory size per user
- Use background processing
- Monitor extraction costs

### 4. Error Recovery

- Log all failures with context
- Implement retry with backoff
- Graceful degradation
- User notification for issues
- Regular consistency checks

## Monitoring

### Key Metrics

1. **Extraction Performance**
   - Success rate
   - Average latency
   - Token usage
   - Cost per extraction

2. **Storage Metrics**
   - Read/write latency
   - Storage size growth
   - Cache hit rate
   - Concurrent access

3. **Data Quality**
   - Duplicate rate
   - Validation failures
   - Relationship integrity
   - Update frequency

### Logging

Structured logs for debugging:

```json
{
    "timestamp": "2024-01-15T10:30:45Z",
    "operation": "memory_extraction",
    "user_id": "user123",
    "entities_extracted": {
        "accounts": 2,
        "contacts": 3,
        "opportunities": 1
    },
    "duration_ms": 543,
    "status": "success"
}
```

## Future Enhancements

### Near Term

1. **Vector Embeddings**: Semantic search in memory
2. **Memory Summarization**: Compress old memories
3. **Cross-User Insights**: Aggregate analytics
4. **Real-time Sync**: Websocket updates

### Long Term

1. **Graph Database**: Neo4j for relationships
2. **ML-Enhanced Extraction**: Custom models
3. **Federated Memory**: Distributed storage
4. **Privacy Controls**: User data management