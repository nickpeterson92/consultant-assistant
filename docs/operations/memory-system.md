# Memory System

SQLite-based memory management for multi-agent orchestrator with conversation state persistence, entity extraction, and automatic summarization.

## Overview

The memory system provides persistent storage for conversation history, extracted entities, and user context across agent interactions. It uses a simplified SQLite adapter with thread-safe operations and automatic background summarization.

## Architecture

### Core Components

- **AsyncStoreAdapter**: Simplified SQLite storage
- **Memory Models**: Pydantic models for structured data storage
- **Background Summarization**: Automatic context compression
- **Thread Persistence**: Full conversation state storage

### Storage Schema

```sql
CREATE TABLE store (
    namespace TEXT,    -- ("memory", user_id)
    key TEXT,          -- Object type or state identifier
    value TEXT,        -- JSON serialized data
    PRIMARY KEY (namespace, key)
);
```

### Memory Namespace Format

```python
# Always use tuple format for namespaces
namespace = ("memory", user_id)  # ✅ Correct
namespace = "memory"             # ❌ Wrong
```

## Memory Models

### SimpleMemory Container

```python
@dataclass
class SimpleMemory:
    """Container for all user memory"""
    accounts: List[SimpleAccount] = field(default_factory=list)
    contacts: List[SimpleContact] = field(default_factory=list)
    opportunities: List[SimpleOpportunity] = field(default_factory=list)
    cases: List[SimpleCase] = field(default_factory=list)
    tasks: List[SimpleTask] = field(default_factory=list)
    leads: List[SimpleLead] = field(default_factory=list)
```

### Entity Models

```python
@dataclass
class SimpleAccount:
    """Simplified account representation"""
    name: str
    id: str
    type: Optional[str] = None
    industry: Optional[str] = None

@dataclass
class SimpleContact:
    """Simplified contact representation"""
    name: str
    id: str
    email: Optional[str] = None
    account_name: Optional[str] = None

@dataclass
class SimpleOpportunity:
    """Simplified opportunity representation"""
    name: str
    id: str
    amount: Optional[str] = None
    stage: Optional[str] = None
    account_name: Optional[str] = None
```

## AsyncStoreAdapter Implementation

### Simplified Design

```python
class AsyncStoreAdapter:
    """Simplified async SQLite storage adapter"""
    
    def __init__(self, db_path: str = "./memory_store.db"):
        self.db_path = db_path
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._init_db()
    
    def _init_db(self):
        """Initialize database with schema"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS store (
                namespace TEXT,
                key TEXT,
                value TEXT,
                PRIMARY KEY (namespace, key)
            )
        """)
        conn.commit()
        conn.close()
    
    async def set(self, namespace: Tuple[str, str], key: str, value: Any):
        """Store value asynchronously"""
        namespace_str = json.dumps(namespace)
        value_str = json.dumps(value, default=str)
        
        def _set():
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT OR REPLACE INTO store (namespace, key, value) VALUES (?, ?, ?)",
                (namespace_str, key, value_str)
            )
            conn.commit()
            conn.close()
        
        await asyncio.get_event_loop().run_in_executor(self.executor, _set)
    
    async def get(self, namespace: Tuple[str, str], key: str) -> Optional[Any]:
        """Retrieve value asynchronously"""
        namespace_str = json.dumps(namespace)
        
        def _get():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                "SELECT value FROM store WHERE namespace = ? AND key = ?",
                (namespace_str, key)
            )
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return json.loads(result[0])
            return None
        
        return await asyncio.get_event_loop().run_in_executor(self.executor, _get)
```

## Memory Operations

### Store Memory

```python
async def store_memory(user_id: str, memory: SimpleMemory):
    """Store user memory"""
    if global_memory_store is None:
        raise RuntimeError("Memory store not initialized")
    
    namespace = ("memory", user_id)
    serialized_memory = memory.to_dict()
    
    await global_memory_store.set(namespace, SIMPLE_MEMORY_KEY, serialized_memory)
```

### Retrieve Memory

```python
async def get_memory(user_id: str) -> SimpleMemory:
    """Retrieve user memory with fallback to empty memory"""
    if global_memory_store is None:
        logger.warning("Memory store not initialized, returning empty memory")
        return SimpleMemory()
    
    namespace = ("memory", user_id)
    memory_data = await global_memory_store.get(namespace, SIMPLE_MEMORY_KEY)
    
    if memory_data:
        return SimpleMemory.from_dict(memory_data)
    
    return SimpleMemory()
```

### Memory-First Retrieval

```python
async def get_accounts_memory_first(user_id: str, account_name: str = None) -> List[SimpleAccount]:
    """Get accounts from memory first, then external API if needed"""
    memory = await get_memory(user_id)
    
    if account_name:
        # Filter by name from memory
        filtered = [acc for acc in memory.accounts if account_name.lower() in acc.name.lower()]
        if filtered:
            return filtered
    elif memory.accounts:
        # Return all from memory if available
        return memory.accounts
    
    # Fallback to external API
    logger.info("No accounts in memory, fetching from external API")
    # ... external API call logic
    return []
```

## Thread State Persistence

### State Storage

```python
async def save_thread_state(thread_id: str, state: Dict[str, Any], user_id: str):
    """Save complete thread state"""
    if global_memory_store is None:
        return
    
    # Serialize messages for storage
    if "messages" in state:
        state["messages"] = serialize_messages(state["messages"])
    
    namespace = ("memory", user_id)
    state_key = f"{STATE_KEY_PREFIX}{thread_id}"
    
    await global_memory_store.set(namespace, state_key, state)
```

### State Retrieval

```python
async def load_thread_state(thread_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Load thread state from storage"""
    if global_memory_store is None:
        return None
    
    namespace = ("memory", user_id)
    state_key = f"{STATE_KEY_PREFIX}{thread_id}"
    
    state = await global_memory_store.get(namespace, state_key)
    
    if state and "messages" in state:
        # Deserialize messages
        state["messages"] = deserialize_messages(state["messages"])
    
    return state
```

## Message Serialization

### Critical for State Persistence

```python
def serialize_messages(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
    """Serialize LangChain messages for storage"""
    serialized = []
    
    for message in messages:
        if isinstance(message, HumanMessage):
            serialized.append({
                "type": "human",
                "content": message.content
            })
        elif isinstance(message, AIMessage):
            serialized.append({
                "type": "ai", 
                "content": message.content
            })
        elif isinstance(message, SystemMessage):
            serialized.append({
                "type": "system",
                "content": message.content
            })
    
    return serialized

def deserialize_messages(serialized: List[Dict[str, Any]]) -> List[BaseMessage]:
    """Deserialize messages from storage"""
    messages = []
    
    for msg_data in serialized:
        if msg_data["type"] == "human":
            messages.append(HumanMessage(content=msg_data["content"]))
        elif msg_data["type"] == "ai":
            messages.append(AIMessage(content=msg_data["content"]))
        elif msg_data["type"] == "system":
            messages.append(SystemMessage(content=msg_data["content"]))
    
    return messages
```

## Background Summarization

### Automatic Context Compression

```python
class BackgroundSummarizer:
    """Handles automatic conversation summarization"""
    
    def __init__(self):
        self.summary_triggers = {
            "message_count": 15,      # Trigger after 15 messages
            "agent_calls": 2,         # Trigger after 2 agent calls
            "time_threshold": 180     # Trigger after 3 minutes
        }
    
    async def should_trigger_summary(self, state: Dict[str, Any]) -> bool:
        """Check if summarization should be triggered"""
        message_count = len(state.get("messages", []))
        agent_calls = len(state.get("agent_call_history", []))
        
        # Message count trigger
        if message_count >= self.summary_triggers["message_count"]:
            return True
        
        # Agent calls trigger
        if agent_calls >= self.summary_triggers["agent_calls"]:
            return True
        
        # Time-based trigger would be implemented here
        
        return False
    
    async def summarize_conversation(self, messages: List[BaseMessage]) -> str:
        """Create conversation summary"""
        # Preserve recent messages
        recent_messages = messages[-5:]
        older_messages = messages[:-5]
        
        if not older_messages:
            return ""
        
        # Create summary of older messages
        summary_prompt = "Summarize the key points from this conversation:\n"
        for msg in older_messages:
            summary_prompt += f"{msg.type}: {msg.content}\n"
        
        # Use LLM to create summary
        summary = await self._create_summary(summary_prompt)
        
        return summary
```

### Memory Update Triggers

```python
async def check_memory_update_triggers(state: Dict[str, Any]) -> bool:
    """Check if memory should be updated"""
    
    # Tool call trigger
    tool_calls = state.get("tool_calls_count", 0)
    if tool_calls >= 3:
        return True
    
    # Agent call trigger
    agent_calls = len(state.get("agent_call_history", []))
    if agent_calls >= 2:
        return True
    
    # Time-based trigger (3 minutes)
    last_update = state.get("last_memory_update")
    if last_update:
        time_diff = time.time() - last_update
        if time_diff >= 180:  # 3 minutes
            return True
    
    return False
```

## Entity Extraction

### Automatic Entity Recognition

```python
async def extract_entities_from_messages(messages: List[BaseMessage]) -> SimpleMemory:
    """Extract entities from conversation messages"""
    
    # Combine message content
    content = "\n".join([msg.content for msg in messages if hasattr(msg, 'content')])
    
    # Use LLM for entity extraction
    extraction_prompt = f"""
    Extract business entities from this conversation:
    
    {content}
    
    Return JSON with:
    - accounts: [{"name": "", "id": "", "type": ""}]
    - contacts: [{"name": "", "id": "", "email": "", "account_name": ""}]  
    - opportunities: [{"name": "", "id": "", "amount": "", "stage": "", "account_name": ""}]
    """
    
    # Parse LLM response into memory objects
    extracted_data = await self._extract_with_llm(extraction_prompt)
    
    return SimpleMemory.from_dict(extracted_data)
```

### Smart Entity Merging

```python
async def merge_entities(existing_memory: SimpleMemory, new_entities: SimpleMemory) -> SimpleMemory:
    """Merge new entities with existing memory"""
    
    # Merge accounts (by ID, then by name)
    existing_account_ids = {acc.id for acc in existing_memory.accounts if acc.id}
    existing_account_names = {acc.name.lower() for acc in existing_memory.accounts}
    
    for new_account in new_entities.accounts:
        if new_account.id and new_account.id not in existing_account_ids:
            existing_memory.accounts.append(new_account)
        elif new_account.name.lower() not in existing_account_names:
            existing_memory.accounts.append(new_account)
    
    # Similar logic for contacts, opportunities, etc.
    
    return existing_memory
```

## Performance Optimization

### Memory Caching

```python
class MemoryCache:
    """In-memory cache for frequently accessed data"""
    
    def __init__(self, ttl: int = 300):  # 5 minute TTL
        self.cache = {}
        self.ttl = ttl
        self.timestamps = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get from cache if not expired"""
        if key in self.cache:
            if time.time() - self.timestamps[key] < self.ttl:
                return self.cache[key]
            else:
                # Expired
                del self.cache[key]
                del self.timestamps[key]
        
        return None
    
    def set(self, key: str, value: Any):
        """Store in cache with timestamp"""
        self.cache[key] = value
        self.timestamps[key] = time.time()
```

### Lazy Loading

```python
async def get_memory_lazy(user_id: str) -> SimpleMemory:
    """Get memory with lazy loading"""
    cache_key = f"memory_{user_id}"
    
    # Check cache first
    cached = memory_cache.get(cache_key)
    if cached:
        return cached
    
    # Load from storage
    memory = await get_memory(user_id)
    
    # Cache for future use
    memory_cache.set(cache_key, memory)
    
    return memory
```

## Configuration

### Memory Settings

```json
{
  "memory": {
    "summary_trigger_messages": 15,
    "max_messages_to_preserve": 5,
    "memory_update_trigger_tools": 3,
    "memory_update_trigger_agents": 2,
    "memory_update_trigger_time": 180,
    "cache_ttl": 300
  }
}
```

### Database Configuration

```python
@dataclass
class MemoryConfig:
    """Memory system configuration"""
    db_path: str = "./memory_store.db"
    summary_trigger_messages: int = 15
    max_messages_to_preserve: int = 5
    memory_update_trigger_tools: int = 3
    memory_update_trigger_agents: int = 2
    memory_update_trigger_time: int = 180
    cache_ttl: int = 300
    thread_pool_workers: int = 4
```

## Error Handling

### Graceful Degradation

```python
async def safe_memory_operation(operation: Callable, fallback_value: Any = None):
    """Execute memory operation with error handling"""
    try:
        return await operation()
    except Exception as e:
        logger.error(f"Memory operation failed: {e}")
        
        if fallback_value is not None:
            return fallback_value
        
        # Return empty memory as fallback
        return SimpleMemory()
```

### Memory Store Initialization

```python
def ensure_memory_store():
    """Ensure memory store is initialized"""
    global global_memory_store
    
    if global_memory_store is None:
        logger.warning("Memory store not initialized, creating new instance")
        global_memory_store = AsyncStoreAdapter()
    
    return global_memory_store
```

## Monitoring & Debugging

### Memory Metrics

```python
class MemoryMetrics:
    """Track memory system performance"""
    
    def __init__(self):
        self.operations_count = defaultdict(int)
        self.operation_durations = defaultdict(list)
        self.cache_hits = 0
        self.cache_misses = 0
    
    def record_operation(self, operation: str, duration: float):
        """Record operation timing"""
        self.operations_count[operation] += 1
        self.operation_durations[operation].append(duration)
    
    def record_cache_hit(self):
        """Record cache hit"""
        self.cache_hits += 1
    
    def record_cache_miss(self):
        """Record cache miss"""
        self.cache_misses += 1
    
    def get_cache_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total) if total > 0 else 0.0
```

### Debug Logging

```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "component": "memory_system",
  "operation_type": "MEMORY_STORE",
  "user_id": "user123",
  "entity_count": 15,
  "duration_ms": 45
}
```

## Best Practices

### Thread Safety
- Always use AsyncStoreAdapter for database operations
- Use proper namespace formatting: `("memory", user_id)`
- Handle None values for uninitialized memory store

### Performance
- Cache frequently accessed memory objects
- Use memory-first retrieval patterns
- Implement background summarization triggers
- Monitor cache hit rates

### Data Integrity
- Always serialize messages before storage
- Validate memory models before storage
- Handle deserialization errors gracefully
- Implement proper error fallbacks

### Memory Management
- Trigger summarization at appropriate thresholds
- Preserve recent messages during summarization
- Extract and store relevant entities
- Merge new entities intelligently

## Troubleshooting

### Common Issues

1. **Message Serialization Errors**
   ```python
   # ❌ Wrong - will crash on restore
   state_to_save = {"messages": messages}
   
   # ✅ Right - always serialize first
   state_to_save = {"messages": serialize_messages(messages)}
   ```

2. **Namespace Format Errors**
   ```python
   # ❌ Wrong
   namespace = "memory"
   
   # ✅ Right
   namespace = ("memory", user_id)
   ```

3. **Memory Store Not Initialized**
   ```python
   # Always check before use
   if global_memory_store is None:
       raise RuntimeError("Memory store not initialized")
   ```

### Debug Commands

```bash
# Check memory database
sqlite3 memory_store.db "SELECT * FROM store WHERE key LIKE 'state_%'"

# Monitor memory operations
tail -f logs/memory_system.log | grep MEMORY

# Check memory metrics
curl http://localhost:8000/debug/memory-stats
```

## Future Enhancements

1. **Distributed Memory**: Redis-based storage for multi-instance deployments
2. **Advanced Entity Linking**: Smarter entity resolution and deduplication
3. **Semantic Search**: Vector-based memory retrieval
4. **Memory Compression**: More sophisticated summarization algorithms
5. **Memory Analytics**: Usage patterns and optimization insights