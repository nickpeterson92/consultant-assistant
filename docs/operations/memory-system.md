# Memory System Documentation

## Table of Contents
1. [What is Memory in AI Systems?](#what-is-memory-in-ai-systems)
2. [Why Memory Matters](#why-memory-matters)
3. [Human Memory Analogy](#human-memory-analogy)
4. [Overview](#overview)
5. [Step-by-Step Implementation Guide](#step-by-step-implementation-guide)
6. [Common Memory Patterns](#common-memory-patterns)
7. [Memory Optimization Techniques](#memory-optimization-techniques)
8. [Debugging Memory Issues](#debugging-memory-issues)
9. [Testing Memory Systems](#testing-memory-systems)
10. [Real Examples from Our Orchestrator](#real-examples-from-our-orchestrator)
11. [Common Pitfalls and How to Avoid Them](#common-pitfalls-and-how-to-avoid-them)

## What is Memory in AI Systems?

Memory in AI systems is the ability to store, retrieve, and use information from past interactions. Just like humans remember conversations and learn from them, AI systems need memory to:

- **Maintain context** across multiple conversations
- **Remember user preferences** and past decisions
- **Track entities** like people, companies, and projects
- **Learn patterns** from interactions
- **Provide personalized** experiences

Without memory, every conversation with an AI would be like meeting someone with amnesia - they'd have no recollection of previous interactions, making it impossible to build on past knowledge or maintain relationships.

## Why Memory Matters

### 1. **Continuity and Context**
```python
# Without memory:
User: "Update the Acme Corp deal to $50k"
AI: "I don't know which deal you're referring to."

# With memory:
User: "Update the Acme Corp deal to $50k"
AI: "I'll update the opportunity we discussed yesterday for Acme Corp (ID: 006XX000123) from $30k to $50k."
```

### 2. **Efficiency**
- Users don't need to repeat information
- AI can make intelligent assumptions
- Faster task completion

### 3. **Personalization**
- Remember user preferences
- Adapt communication style
- Track user-specific entities

### 4. **Business Intelligence**
- Track patterns over time
- Generate insights from historical data
- Enable reporting and analytics

## Human Memory Analogy

AI memory systems mirror human memory in many ways:

### Short-Term Memory (Working Memory)
- **Human**: Remembering a phone number just long enough to dial it
- **AI**: Current conversation state, temporary variables
- **Implementation**: In-memory state during active session

```python
# Short-term memory example
class ConversationState:
    def __init__(self):
        self.current_topic = None
        self.mentioned_entities = []
        self.user_intent = None
        
    def update_context(self, message):
        # Updates only for current session
        self.current_topic = extract_topic(message)
```

### Long-Term Memory (Persistent Storage)
- **Human**: Remembering your friend's birthday year after year
- **AI**: User preferences, CRM data, learned facts
- **Implementation**: Database storage that persists between sessions

```python
# Long-term memory example
class PersistentMemory:
    def __init__(self, db_path):
        self.db = SQLiteDatabase(db_path)
        
    def remember_entity(self, entity):
        # Stores permanently in database
        self.db.insert("entities", entity)
```

### Episodic Memory (Event-Based)
- **Human**: Remembering specific conversations or events
- **AI**: Conversation history, interaction logs
- **Implementation**: Timestamped event storage

### Semantic Memory (Factual Knowledge)
- **Human**: Knowing that Paris is the capital of France
- **AI**: Structured data about entities and relationships
- **Implementation**: Knowledge graphs and structured schemas

## Overview

The memory system provides intelligent, persistent storage of structured information extracted from conversations. It uses TrustCall for reliable extraction, Pydantic for data validation, and SQLite for durable storage. The system automatically identifies and stores CRM entities (accounts, contacts, opportunities) while maintaining relationships and avoiding duplicates.

## Step-by-Step Implementation Guide

### Step 1: Define Your Memory Schema

First, decide what information you want to remember. Use Pydantic dataclasses for type safety:

```python
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class UserPreference:
    """What the user likes or prefers"""
    preference_type: str  # "communication_style", "timezone", etc.
    value: str
    
@dataclass
class LearnedFact:
    """Facts learned from conversations"""
    subject: str
    fact: str
    confidence: float = 1.0
    
@dataclass
class SimpleMemory:
    """Container for all memory types"""
    preferences: List[UserPreference] = field(default_factory=list)
    facts: List[LearnedFact] = field(default_factory=list)
    # Add your domain-specific memory types here
```

**Junior Engineer Tip**: Start simple! Don't try to remember everything at once. Pick 2-3 important things and expand later.

### Step 2: Set Up Storage

Create a storage layer that persists memory between sessions:

```python
import json
import sqlite3
from typing import Optional, Tuple

class MemoryStore:
    def __init__(self, db_path: str = "memory.db"):
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        """Create the storage table if it doesn't exist"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    user_id TEXT,
                    memory_type TEXT,
                    data TEXT,
                    PRIMARY KEY (user_id, memory_type)
                )
            """)
            
    def save_memory(self, user_id: str, memory: SimpleMemory):
        """Save memory to database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO memory (user_id, memory_type, data) VALUES (?, ?, ?)",
                (user_id, "SimpleMemory", json.dumps(dataclasses.asdict(memory)))
            )
            
    def load_memory(self, user_id: str) -> Optional[SimpleMemory]:
        """Load memory from database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT data FROM memory WHERE user_id = ? AND memory_type = ?",
                (user_id, "SimpleMemory")
            )
            row = cursor.fetchone()
            if row:
                data = json.loads(row[0])
                return SimpleMemory(**data)
            return None
```

**Common Mistake**: Forgetting to handle the case when no memory exists yet. Always return a default empty memory!

### Step 3: Extract Information from Conversations

Use an LLM to intelligently extract information:

```python
from langchain.schema import HumanMessage, SystemMessage

class MemoryExtractor:
    def __init__(self, llm):
        self.llm = llm
        
    async def extract_from_conversation(self, messages: List[str]) -> SimpleMemory:
        """Extract memory-worthy information from messages"""
        
        extraction_prompt = """
        From this conversation, extract:
        1. User preferences (how they like things done)
        2. Important facts mentioned
        
        Be conservative - only extract explicitly stated information.
        
        Conversation:
        {conversation}
        
        Return as JSON with structure:
        {
            "preferences": [{"preference_type": "...", "value": "..."}],
            "facts": [{"subject": "...", "fact": "...", "confidence": 0.9}]
        }
        """
        
        conversation_text = "\n".join(messages)
        
        response = await self.llm.ainvoke([
            SystemMessage(content=extraction_prompt.format(
                conversation=conversation_text
            ))
        ])
        
        # Parse response and create SimpleMemory object
        extracted_data = json.loads(response.content)
        return SimpleMemory(**extracted_data)
```

**Pro Tip**: Always validate extracted data before storing. LLMs can hallucinate!

### Step 4: Integrate Memory into Your Conversation Flow

```python
class ConversationManager:
    def __init__(self, memory_store: MemoryStore, extractor: MemoryExtractor):
        self.memory_store = memory_store
        self.extractor = extractor
        self.message_buffer = []
        
    async def process_message(self, user_id: str, message: str):
        """Process a user message with memory context"""
        
        # 1. Load existing memory
        memory = self.memory_store.load_memory(user_id) or SimpleMemory()
        
        # 2. Add message to buffer
        self.message_buffer.append(message)
        
        # 3. Generate response with memory context
        response = await self._generate_response_with_memory(message, memory)
        
        # 4. Update memory every N messages
        if len(self.message_buffer) >= 5:
            await self._update_memory(user_id)
            
        return response
        
    async def _update_memory(self, user_id: str):
        """Extract and merge new memory"""
        # Extract from recent messages
        new_memory = await self.extractor.extract_from_conversation(
            self.message_buffer
        )
        
        # Load existing memory
        existing_memory = self.memory_store.load_memory(user_id) or SimpleMemory()
        
        # Merge memories (avoid duplicates)
        merged_memory = self._merge_memories(existing_memory, new_memory)
        
        # Save updated memory
        self.memory_store.save_memory(user_id, merged_memory)
        
        # Clear buffer
        self.message_buffer = []
```

### Step 5: Use Memory to Enhance Responses

```python
def create_memory_context(memory: SimpleMemory) -> str:
    """Convert memory into context for the LLM"""
    context_parts = []
    
    if memory.preferences:
        prefs = [f"- {p.preference_type}: {p.value}" for p in memory.preferences]
        context_parts.append(f"User Preferences:\n" + "\n".join(prefs))
        
    if memory.facts:
        facts = [f"- {f.subject}: {f.fact}" for f in memory.facts[:5]]  # Limit to avoid token overflow
        context_parts.append(f"Known Facts:\n" + "\n".join(facts))
        
    return "\n\n".join(context_parts)

# Use in your prompt
memory_context = create_memory_context(memory)
prompt = f"""
You are a helpful assistant. Here's what you remember about this user:

{memory_context}

User: {user_message}
Assistant:"""
```

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
    key TEXT NOT NULL,         -- "SimpleMemory" or "state_{thread_id}"
    value TEXT NOT NULL,       -- JSON serialized memory or state
    PRIMARY KEY (namespace, key)
);
```

### Thread State Persistence

The system now supports full conversation state persistence:

```python
# Save entire state with thread ID
key = f"state_{thread_id}"
state_data = {
    "state": serialized_state,
    "thread_id": thread_id,
    "timestamp": time.time()
}
memory_store.sync_put(namespace, key, state_data)

# Message serialization helper
def _serialize_messages(messages):
    """Convert LangChain messages to JSON-serializable format."""
    serializable_messages = []
    for msg in messages:
        if hasattr(msg, 'dict'):
            serializable_messages.append(msg.dict())
        elif isinstance(msg, dict):
            serializable_messages.append(msg)
        else:
            serializable_messages.append({
                "type": type(msg).__name__,
                "content": str(getattr(msg, 'content', str(msg)))
            })
    return serializable_messages
```

### AsyncStoreAdapter (Simplified)

Simple thread-safe storage access without unnecessary abstractions:

```python
class AsyncStoreAdapter:
    """Simple async adapter for SQLiteStore using thread pool executor."""
    
    def __init__(self, db_path: str = "memory_store.db", max_workers: int = 4):
        self.db_path = db_path
        self.max_workers = max_workers
        
        # Single SQLiteStore instance - SQLite handles concurrency internally
        self._store = SQLiteStore(db_path)
        
        # Thread pool for async operations
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, 
            thread_name_prefix="sqlite_"
        )
    
    async def get(self, namespace: Tuple[str, ...], key: str) -> Optional[Any]:
        """Get a value from the store asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, 
            self._store.get, 
            namespace, 
            key
        )
    
    async def put(self, namespace: Tuple[str, ...], key: str, value: Any) -> None:
        """Put a value into the store asynchronously."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self._executor,
            self._store.put,
            namespace,
            key,
            value
        )
```

**Key simplifications:**
- No circuit breaker (unnecessary for local SQLite)
- No connection pooling (SQLite handles this internally)
- No retry logic (local database operations rarely fail)
- No metrics tracking (adds complexity without clear value)
- **Result: 167 lines vs 536 lines (69% reduction)**

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

## Common Memory Patterns

Understanding common memory patterns helps you implement effective memory systems. Here are the most frequently used patterns in production AI systems:

### 1. Conversation History Pattern

Store and retrieve past conversations for context:

```python
@dataclass
class ConversationTurn:
    timestamp: str
    user_message: str
    assistant_response: str
    
@dataclass
class ConversationHistory:
    turns: List[ConversationTurn] = field(default_factory=list)
    max_turns: int = 100  # Limit to prevent unbounded growth
    
    def add_turn(self, user_msg: str, assistant_msg: str):
        """Add a conversation turn with automatic trimming"""
        turn = ConversationTurn(
            timestamp=datetime.now().isoformat(),
            user_message=user_msg,
            assistant_response=assistant_msg
        )
        self.turns.append(turn)
        
        # Keep only the most recent turns
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]
            
    def get_context(self, num_turns: int = 5) -> str:
        """Get recent conversation context"""
        recent_turns = self.turns[-num_turns:]
        context = []
        for turn in recent_turns:
            context.append(f"User: {turn.user_message}")
            context.append(f"Assistant: {turn.assistant_response}")
        return "\n".join(context)
```

**Use Case**: Customer support bots, personal assistants, tutoring systems

### 2. User Preferences Pattern

Track and apply user-specific preferences:

```python
@dataclass
class UserPreferences:
    communication_style: str = "professional"  # casual, formal, technical
    response_length: str = "balanced"  # brief, balanced, detailed
    timezone: str = "UTC"
    language: str = "en"
    custom_preferences: Dict[str, Any] = field(default_factory=dict)
    
    def apply_to_prompt(self, base_prompt: str) -> str:
        """Modify prompt based on preferences"""
        preference_instructions = []
        
        if self.communication_style == "casual":
            preference_instructions.append("Use a friendly, conversational tone.")
        elif self.communication_style == "technical":
            preference_instructions.append("Use precise technical language.")
            
        if self.response_length == "brief":
            preference_instructions.append("Keep responses concise and to the point.")
        elif self.response_length == "detailed":
            preference_instructions.append("Provide comprehensive, detailed responses.")
            
        if preference_instructions:
            return f"{base_prompt}\n\nUser Preferences:\n" + "\n".join(preference_instructions)
        return base_prompt
```

**Real Example from Our Orchestrator**:
```python
# In the orchestrator, we track user preferences for agents
if "prefers_detailed_explanations" in user_memory.preferences:
    agent_instruction += "\nProvide detailed explanations for all actions."
```

### 3. Learned Facts Pattern

Store facts and knowledge discovered during conversations:

```python
@dataclass
class Fact:
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0
    source: str = "user_stated"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
@dataclass
class KnowledgeBase:
    facts: List[Fact] = field(default_factory=list)
    
    def add_fact(self, subject: str, predicate: str, obj: str, confidence: float = 1.0):
        """Add a fact with deduplication"""
        # Check if fact already exists
        for existing_fact in self.facts:
            if (existing_fact.subject == subject and 
                existing_fact.predicate == predicate and 
                existing_fact.object == obj):
                # Update confidence if higher
                if confidence > existing_fact.confidence:
                    existing_fact.confidence = confidence
                return
                
        # Add new fact
        self.facts.append(Fact(subject, predicate, obj, confidence))
        
    def query_facts(self, subject: str = None, predicate: str = None) -> List[Fact]:
        """Query facts by subject or predicate"""
        results = []
        for fact in self.facts:
            if (subject is None or fact.subject == subject) and \
               (predicate is None or fact.predicate == predicate):
                results.append(fact)
        return results
```

**Example Usage**:
```python
# During conversation
kb = KnowledgeBase()
kb.add_fact("Acme Corp", "has_revenue", "$10M", confidence=0.9)
kb.add_fact("Acme Corp", "located_in", "San Francisco", confidence=1.0)

# Later retrieval
acme_facts = kb.query_facts(subject="Acme Corp")
# Returns all facts about Acme Corp
```

### 4. Entity Relationship Pattern

Track relationships between entities (people, companies, projects):

```python
@dataclass
class Entity:
    id: str
    type: str  # "person", "company", "project"
    name: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    
@dataclass
class Relationship:
    from_id: str
    to_id: str
    relationship_type: str  # "works_for", "owns", "manages"
    attributes: Dict[str, Any] = field(default_factory=dict)
    
class EntityGraph:
    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.relationships: List[Relationship] = []
        
    def add_entity(self, entity: Entity):
        """Add or update an entity"""
        self.entities[entity.id] = entity
        
    def add_relationship(self, from_id: str, to_id: str, rel_type: str):
        """Add a relationship between entities"""
        # Verify both entities exist
        if from_id not in self.entities or to_id not in self.entities:
            raise ValueError("Both entities must exist before creating relationship")
            
        # Check if relationship already exists
        for rel in self.relationships:
            if (rel.from_id == from_id and 
                rel.to_id == to_id and 
                rel.relationship_type == rel_type):
                return  # Already exists
                
        self.relationships.append(
            Relationship(from_id, to_id, rel_type)
        )
        
    def get_related_entities(self, entity_id: str, rel_type: str = None) -> List[Entity]:
        """Get all entities related to a given entity"""
        related_ids = []
        for rel in self.relationships:
            if rel.from_id == entity_id:
                if rel_type is None or rel.relationship_type == rel_type:
                    related_ids.append(rel.to_id)
        
        return [self.entities[id] for id in related_ids if id in self.entities]
```

**Real-World Example from CRM**:
```python
# Track company-contact relationships
graph = EntityGraph()
graph.add_entity(Entity("001", "company", "Acme Corp"))
graph.add_entity(Entity("002", "person", "John Smith"))
graph.add_relationship("002", "001", "works_for")

# Query relationships
acme_employees = graph.get_related_entities("001", "works_for")
```

### 5. Session State Pattern

Maintain state within a conversation session:

```python
@dataclass
class SessionState:
    session_id: str
    user_id: str
    current_task: Optional[str] = None
    context_stack: List[str] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_active: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def push_context(self, context: str):
        """Add a new context to the stack"""
        self.context_stack.append(context)
        self.last_active = datetime.now().isoformat()
        
    def pop_context(self) -> Optional[str]:
        """Remove and return the top context"""
        if self.context_stack:
            self.last_active = datetime.now().isoformat()
            return self.context_stack.pop()
        return None
        
    def set_variable(self, key: str, value: Any):
        """Store a session variable"""
        self.variables[key] = value
        self.last_active = datetime.now().isoformat()
        
    def get_variable(self, key: str, default: Any = None) -> Any:
        """Retrieve a session variable"""
        return self.variables.get(key, default)
```

**Use in Multi-Step Workflows**:
```python
# Start a multi-step task
session = SessionState(session_id="abc123", user_id="user1")
session.current_task = "create_salesforce_opportunity"
session.push_context("gathering_account_info")
session.set_variable("account_name", "Acme Corp")

# Later in the conversation
if session.current_task == "create_salesforce_opportunity":
    account = session.get_variable("account_name")
    # Continue with the task
```

### 6. Temporal Memory Pattern

Track time-sensitive information:

```python
@dataclass
class TemporalMemory:
    """Memory with time-based expiration"""
    value: Any
    created_at: float
    ttl: float  # Time to live in seconds
    
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl
        
class TemporalStore:
    def __init__(self):
        self.memories: Dict[str, TemporalMemory] = {}
        
    def set(self, key: str, value: Any, ttl: float = 3600):
        """Store a value with expiration"""
        self.memories[key] = TemporalMemory(
            value=value,
            created_at=time.time(),
            ttl=ttl
        )
        
    def get(self, key: str) -> Optional[Any]:
        """Get a value if not expired"""
        if key in self.memories:
            memory = self.memories[key]
            if not memory.is_expired():
                return memory.value
            else:
                # Clean up expired memory
                del self.memories[key]
        return None
        
    def cleanup_expired(self):
        """Remove all expired memories"""
        expired_keys = [
            key for key, mem in self.memories.items() 
            if mem.is_expired()
        ]
        for key in expired_keys:
            del self.memories[key]
```

**Real-World Use Cases**:
- Authentication tokens
- Temporary context during multi-turn tasks
- Cache for expensive computations
- Rate limiting information

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

## Memory Optimization Techniques

Optimizing memory systems is crucial for performance, cost-effectiveness, and scalability. Here are proven techniques from production systems:

### 1. Smart Extraction Strategies

**Batch Processing**
Minimize LLM calls by processing multiple messages together:

```python
class BatchExtractor:
    def __init__(self, batch_size: int = 10, min_batch_size: int = 3):
        self.batch_size = batch_size
        self.min_batch_size = min_batch_size
        self.message_buffer = []
        
    async def add_message_and_extract(self, message: str) -> Optional[SimpleMemory]:
        """Add message to buffer and extract when threshold reached"""
        self.message_buffer.append(message)
        
        # Extract if we have enough messages OR it's been too long
        if len(self.message_buffer) >= self.min_batch_size:
            return await self._extract_batch()
        return None
        
    async def _extract_batch(self) -> SimpleMemory:
        """Extract from all buffered messages at once"""
        if not self.message_buffer:
            return SimpleMemory()
            
        # Process entire batch in one LLM call
        extraction_result = await extractor.ainvoke({
            "messages": self.message_buffer[-self.batch_size:]  # Limit size
        })
        
        # Clear processed messages
        self.message_buffer = []
        return extraction_result
```

**Selective Extraction**
Only extract when likely to find valuable information:

```python
def should_extract(message: str) -> bool:
    """Determine if message likely contains memory-worthy info"""
    # Keywords that suggest important information
    memory_triggers = [
        "my name is", "i prefer", "please remember",
        "for future reference", "always", "never",
        "i work at", "my email", "my phone"
    ]
    
    message_lower = message.lower()
    return any(trigger in message_lower for trigger in memory_triggers)

# Use in conversation flow
if should_extract(user_message):
    await update_memory(user_message)
```

### 2. Efficient Storage Patterns

**Compression Techniques**
Reduce storage size without losing information:

```python
import zlib
import base64

class CompressedMemoryStore:
    def save_memory(self, user_id: str, memory: SimpleMemory):
        """Save memory with compression"""
        # Serialize to JSON
        json_data = json.dumps(asdict(memory), separators=(',', ':'))
        
        # Compress if large
        if len(json_data) > 1000:  # Threshold for compression
            compressed = zlib.compress(json_data.encode())
            data_to_store = {
                "compressed": True,
                "data": base64.b64encode(compressed).decode()
            }
        else:
            data_to_store = {
                "compressed": False,
                "data": json_data
            }
            
        # Store in database
        self._store(user_id, json.dumps(data_to_store))
        
    def load_memory(self, user_id: str) -> SimpleMemory:
        """Load and decompress memory"""
        stored_data = json.loads(self._load(user_id))
        
        if stored_data["compressed"]:
            compressed = base64.b64decode(stored_data["data"])
            json_data = zlib.decompress(compressed).decode()
        else:
            json_data = stored_data["data"]
            
        return SimpleMemory(**json.loads(json_data))
```

**Incremental Updates**
Only store changes instead of full memory:

```python
@dataclass
class MemoryDelta:
    """Represents changes to memory"""
    added_facts: List[Fact] = field(default_factory=list)
    removed_fact_ids: List[str] = field(default_factory=list)
    updated_preferences: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

class IncrementalMemoryStore:
    def __init__(self):
        self.base_memories: Dict[str, SimpleMemory] = {}
        self.deltas: Dict[str, List[MemoryDelta]] = {}
        
    def save_delta(self, user_id: str, delta: MemoryDelta):
        """Save only the changes"""
        if user_id not in self.deltas:
            self.deltas[user_id] = []
        self.deltas[user_id].append(delta)
        
        # Compact deltas periodically
        if len(self.deltas[user_id]) > 10:
            self._compact_deltas(user_id)
            
    def _compact_deltas(self, user_id: str):
        """Merge deltas into base memory"""
        base = self.base_memories.get(user_id, SimpleMemory())
        
        for delta in self.deltas[user_id]:
            # Apply delta to base
            base.facts.extend(delta.added_facts)
            base.facts = [f for f in base.facts if f.id not in delta.removed_fact_ids]
            # ... apply other changes
            
        self.base_memories[user_id] = base
        self.deltas[user_id] = []
```

### 3. Caching Strategies

**Multi-Level Cache**
Implement L1 (in-process) and L2 (shared) caches:

```python
class MultiLevelMemoryCache:
    def __init__(self):
        # L1: In-process cache (fastest)
        self.l1_cache: Dict[str, Tuple[SimpleMemory, float]] = {}
        self.l1_ttl = 300  # 5 minutes
        
        # L2: Redis cache (shared between processes)
        self.redis_client = redis.Redis()
        self.l2_ttl = 3600  # 1 hour
        
    async def get_memory(self, user_id: str) -> Optional[SimpleMemory]:
        """Try caches before hitting database"""
        
        # Check L1 cache
        if user_id in self.l1_cache:
            memory, timestamp = self.l1_cache[user_id]
            if time.time() - timestamp < self.l1_ttl:
                return memory
                
        # Check L2 cache
        l2_data = await self.redis_client.get(f"memory:{user_id}")
        if l2_data:
            memory = SimpleMemory(**json.loads(l2_data))
            # Populate L1
            self.l1_cache[user_id] = (memory, time.time())
            return memory
            
        # Load from database
        memory = await self.load_from_db(user_id)
        if memory:
            # Populate both caches
            await self._populate_caches(user_id, memory)
            
        return memory
```

**Smart Eviction**
Remove least valuable memories when space is limited:

```python
class SmartMemoryEviction:
    def __init__(self, max_memories: int = 1000):
        self.max_memories = max_memories
        self.access_counts: Dict[str, int] = {}
        self.last_access: Dict[str, float] = {}
        
    def score_memory(self, memory_id: str) -> float:
        """Calculate memory importance score"""
        access_count = self.access_counts.get(memory_id, 0)
        time_since_access = time.time() - self.last_access.get(memory_id, 0)
        
        # Higher score = more important
        # Balances frequency and recency
        return access_count / (1 + time_since_access / 86400)  # Decay over days
        
    def evict_if_needed(self, memories: Dict[str, SimpleMemory]):
        """Remove least important memories if over limit"""
        if len(memories) <= self.max_memories:
            return
            
        # Score all memories
        scored = [(id, self.score_memory(id)) for id in memories.keys()]
        scored.sort(key=lambda x: x[1])  # Sort by score
        
        # Remove lowest scoring memories
        to_remove = len(memories) - self.max_memories
        for memory_id, _ in scored[:to_remove]:
            del memories[memory_id]
            self.access_counts.pop(memory_id, None)
            self.last_access.pop(memory_id, None)
```

### 4. Query Optimization

**Indexed Memory Access**
Create indexes for fast lookups:

```python
class IndexedMemory:
    def __init__(self):
        self.memories: Dict[str, SimpleMemory] = {}
        # Indexes for fast lookup
        self.entity_index: Dict[str, Set[str]] = {}  # entity_name -> user_ids
        self.fact_index: Dict[str, Set[str]] = {}    # fact_subject -> user_ids
        
    def add_memory(self, user_id: str, memory: SimpleMemory):
        """Add memory with index updates"""
        self.memories[user_id] = memory
        
        # Update entity index
        for entity in memory.entities:
            if entity.name not in self.entity_index:
                self.entity_index[entity.name] = set()
            self.entity_index[entity.name].add(user_id)
            
        # Update fact index
        for fact in memory.facts:
            if fact.subject not in self.fact_index:
                self.fact_index[fact.subject] = set()
            self.fact_index[fact.subject].add(user_id)
            
    def find_users_who_know_entity(self, entity_name: str) -> List[str]:
        """Fast lookup using index"""
        return list(self.entity_index.get(entity_name, set()))
```

### 5. Memory Lifecycle Management

**Automatic Summarization**
Compress old memories into summaries:

```python
class MemorySummarizer:
    def __init__(self, llm, max_age_days: int = 30):
        self.llm = llm
        self.max_age_days = max_age_days
        
    async def summarize_old_memories(self, memory: SimpleMemory) -> SimpleMemory:
        """Summarize memories older than threshold"""
        cutoff_time = time.time() - (self.max_age_days * 86400)
        
        old_facts = [f for f in memory.facts if f.timestamp < cutoff_time]
        recent_facts = [f for f in memory.facts if f.timestamp >= cutoff_time]
        
        if len(old_facts) > 10:  # Worth summarizing
            # Use LLM to create summary
            summary_prompt = f"""
            Summarize these facts into key points:
            {json.dumps([asdict(f) for f in old_facts])}
            
            Return 3-5 most important facts.
            """
            
            summary = await self.llm.ainvoke(summary_prompt)
            summarized_facts = parse_summary(summary)
            
            # Replace old facts with summary
            memory.facts = summarized_facts + recent_facts
            
        return memory
```

**Memory Decay**
Gradually forget less important information:

```python
class MemoryDecay:
    def __init__(self, decay_rate: float = 0.95):
        self.decay_rate = decay_rate
        
    def apply_decay(self, memory: SimpleMemory) -> SimpleMemory:
        """Apply decay to memory confidence scores"""
        current_time = time.time()
        
        for fact in memory.facts:
            # Calculate days since fact was learned
            days_old = (current_time - fact.timestamp) / 86400
            
            # Apply exponential decay
            fact.confidence *= (self.decay_rate ** days_old)
            
        # Remove facts below confidence threshold
        memory.facts = [f for f in memory.facts if f.confidence > 0.1]
        
        return memory
```

### 6. Cost Optimization

**Token Usage Monitoring**
Track and optimize LLM token usage:

```python
class TokenOptimizer:
    def __init__(self, max_tokens_per_extraction: int = 500):
        self.max_tokens = max_tokens_per_extraction
        self.token_usage = {}
        
    def optimize_prompt(self, messages: List[str]) -> str:
        """Create token-efficient extraction prompt"""
        # Truncate messages if too long
        total_text = "\n".join(messages)
        
        if len(total_text) > self.max_tokens * 4:  # Rough estimate
            # Keep most recent messages
            truncated = total_text[-(self.max_tokens * 3):]
            return f"[Earlier messages truncated]\n{truncated}"
            
        return total_text
        
    def track_usage(self, user_id: str, tokens_used: int):
        """Monitor token usage per user"""
        if user_id not in self.token_usage:
            self.token_usage[user_id] = []
            
        self.token_usage[user_id].append({
            "timestamp": time.time(),
            "tokens": tokens_used
        })
        
        # Alert if usage is high
        recent_usage = sum(
            u["tokens"] for u in self.token_usage[user_id]
            if time.time() - u["timestamp"] < 3600
        )
        
        if recent_usage > 10000:
            logger.warning(f"High token usage for user {user_id}: {recent_usage}")
```

**Real Example from Our Orchestrator**:
```python
# Efficient memory context creation
def create_minimal_context(memory: SimpleMemory, relevance_filter: str) -> str:
    """Create context with only relevant memories"""
    context_parts = []
    
    # Only include relevant accounts
    if "account" in relevance_filter.lower():
        relevant_accounts = [a for a in memory.accounts if relevance_filter in a.name]
        if relevant_accounts:
            context_parts.append(f"Relevant accounts: {', '.join(a.name for a in relevant_accounts[:3])}")
    
    return "\n".join(context_parts) if context_parts else ""
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

## Debugging Memory Issues

Debugging memory systems can be challenging due to their asynchronous nature and multiple components. Here's a comprehensive guide to identifying and fixing common issues:

### 1. Memory Not Persisting

**Symptoms**: Information discussed in conversation isn't remembered in future sessions.

**Common Causes & Solutions**:

```python
# PROBLEM: Forgetting to await async operations
def update_memory_wrong(user_id: str, memory: SimpleMemory):
    store.aput(namespace=("memory", user_id), key="SimpleMemory", value=memory)
    # Missing await! This returns a coroutine that never executes

# SOLUTION: Always await async operations
async def update_memory_correct(user_id: str, memory: SimpleMemory):
    await store.aput(namespace=("memory", user_id), key="SimpleMemory", value=memory)
```

**Debugging Steps**:
```python
# Add logging to trace memory operations
import logging

class DebugMemoryStore:
    def __init__(self, store):
        self.store = store
        self.logger = logging.getLogger("memory.debug")
        
    async def aput(self, namespace: tuple, key: str, value: Any):
        self.logger.info(f"Saving memory - namespace: {namespace}, key: {key}")
        self.logger.debug(f"Memory content: {value}")
        
        try:
            result = await self.store.aput(namespace, key, value)
            self.logger.info("Memory saved successfully")
            return result
        except Exception as e:
            self.logger.error(f"Failed to save memory: {e}")
            raise
            
    async def aget(self, namespace: tuple, key: str):
        self.logger.info(f"Loading memory - namespace: {namespace}, key: {key}")
        
        try:
            result = await self.store.aget(namespace, key)
            if result:
                self.logger.info("Memory loaded successfully")
                self.logger.debug(f"Loaded content: {result}")
            else:
                self.logger.warning("No memory found")
            return result
        except Exception as e:
            self.logger.error(f"Failed to load memory: {e}")
            raise
```

### 2. Duplicate Entries

**Symptoms**: Same information appears multiple times in memory.

**Root Cause Analysis**:
```python
# Tool to detect duplicates
def analyze_duplicates(memory: SimpleMemory):
    """Identify duplicate entries in memory"""
    duplicates = {
        "accounts": [],
        "contacts": [],
        "facts": []
    }
    
    # Check accounts
    seen_names = {}
    for account in memory.accounts:
        key = account.name.lower()
        if key in seen_names:
            duplicates["accounts"].append({
                "original": seen_names[key],
                "duplicate": account
            })
        else:
            seen_names[key] = account
            
    # Similar checks for other entities...
    
    return duplicates

# Fix duplicates
def deduplicate_memory(memory: SimpleMemory) -> SimpleMemory:
    """Remove duplicate entries, keeping most complete version"""
    
    def dedupe_list(items: List[Any], key_func) -> List[Any]:
        seen = {}
        for item in items:
            key = key_func(item)
            if key not in seen or is_more_complete(item, seen[key]):
                seen[key] = item
        return list(seen.values())
    
    memory.accounts = dedupe_list(memory.accounts, lambda x: x.name.lower())
    memory.contacts = dedupe_list(memory.contacts, lambda x: (x.name.lower(), x.account_name))
    
    return memory
```

### 3. Memory Extraction Failures

**Symptoms**: LLM fails to extract information from conversations.

**Debugging Approach**:
```python
class ExtractionDebugger:
    def __init__(self, extractor):
        self.extractor = extractor
        self.failed_extractions = []
        
    async def debug_extraction(self, messages: List[str]):
        """Run extraction with detailed debugging"""
        
        # Log input
        print("=== EXTRACTION DEBUG ===")
        print(f"Input messages ({len(messages)} total):")
        for i, msg in enumerate(messages[-5:]):  # Last 5 messages
            print(f"  [{i}]: {msg[:100]}...")
            
        # Run extraction with error handling
        try:
            result = await self.extractor.ainvoke({"messages": messages})
            print(f"Extraction successful: {result}")
            return result
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing failed: {e}")
            print(f"Raw LLM output: {e.doc}")
            self.failed_extractions.append({
                "error": "json_decode",
                "messages": messages,
                "raw_output": e.doc
            })
            
        except Exception as e:
            print(f"Extraction failed: {type(e).__name__}: {e}")
            self.failed_extractions.append({
                "error": str(e),
                "messages": messages
            })
            
        return None
```

### 4. Performance Issues

**Symptoms**: Memory operations are slow, causing timeouts.

**Performance Profiler**:
```python
import time
from contextlib import contextmanager

class MemoryProfiler:
    def __init__(self):
        self.timings = {}
        
    @contextmanager
    def measure(self, operation: str):
        """Measure operation duration"""
        start = time.time()
        try:
            yield
        finally:
            duration = time.time() - start
            if operation not in self.timings:
                self.timings[operation] = []
            self.timings[operation].append(duration)
            
            # Alert on slow operations
            if duration > 1.0:
                print(f"SLOW OPERATION: {operation} took {duration:.2f}s")
                
    def report(self):
        """Generate performance report"""
        print("\n=== Memory Performance Report ===")
        for op, times in self.timings.items():
            avg_time = sum(times) / len(times)
            max_time = max(times)
            print(f"{op}:")
            print(f"  Average: {avg_time:.3f}s")
            print(f"  Max: {max_time:.3f}s")
            print(f"  Count: {len(times)}")

# Usage
profiler = MemoryProfiler()

async def profiled_memory_update(user_id: str, messages: List[str]):
    with profiler.measure("total_update"):
        # Load existing memory
        with profiler.measure("load_memory"):
            memory = await store.aget(("memory", user_id), "SimpleMemory")
            
        # Extract new information
        with profiler.measure("extraction"):
            new_memory = await extractor.extract(messages)
            
        # Merge memories
        with profiler.measure("merge"):
            merged = merge_memories(memory, new_memory)
            
        # Save updated memory
        with profiler.measure("save_memory"):
            await store.aput(("memory", user_id), "SimpleMemory", merged)
            
    profiler.report()
```

### 5. Inconsistent State

**Symptoms**: Memory state doesn't match what was saved or loaded.

**State Verification Tool**:
```python
class MemoryConsistencyChecker:
    def __init__(self, store):
        self.store = store
        
    async def verify_save_load_cycle(self, user_id: str, test_memory: SimpleMemory):
        """Verify that saved memory can be loaded correctly"""
        
        # Save memory
        await self.store.aput(("memory", user_id), "test_memory", test_memory)
        
        # Load it back
        loaded = await self.store.aget(("memory", user_id), "test_memory")
        
        # Compare
        issues = []
        
        if not loaded:
            issues.append("Memory not found after saving")
            return issues
            
        # Deep comparison
        original_dict = asdict(test_memory)
        loaded_dict = asdict(loaded)
        
        def compare_dicts(d1, d2, path=""):
            for key in d1:
                if key not in d2:
                    issues.append(f"Missing key: {path}.{key}")
                elif d1[key] != d2[key]:
                    issues.append(f"Value mismatch at {path}.{key}: {d1[key]} != {d2[key]}")
                    
        compare_dicts(original_dict, loaded_dict)
        
        return issues
```

### 6. Memory Corruption

**Symptoms**: Memory data becomes corrupted or malformed.

**Data Validation and Recovery**:
```python
class MemoryValidator:
    @staticmethod
    def validate_and_repair(memory_data: dict) -> SimpleMemory:
        """Validate and repair corrupted memory data"""
        
        repaired = False
        
        # Ensure all required fields exist
        if "accounts" not in memory_data:
            memory_data["accounts"] = []
            repaired = True
            
        # Validate each account
        valid_accounts = []
        for account in memory_data.get("accounts", []):
            try:
                # Ensure required fields
                if isinstance(account, dict) and "name" in account:
                    valid_accounts.append(SimpleAccount(**account))
                else:
                    logger.warning(f"Skipping invalid account: {account}")
                    repaired = True
            except Exception as e:
                logger.error(f"Failed to parse account: {e}")
                repaired = True
                
        if repaired:
            logger.info("Memory data was repaired")
            
        return SimpleMemory(accounts=valid_accounts, ...)
```

### 7. Debugging Best Practices

**1. Enable Comprehensive Logging**:
```python
import logging

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('memory_debug.log'),
        logging.StreamHandler()
    ]
)

# Create category-specific loggers
extraction_logger = logging.getLogger('memory.extraction')
storage_logger = logging.getLogger('memory.storage')
merge_logger = logging.getLogger('memory.merge')
```

**2. Use Debug Decorators**:
```python
def debug_memory_operation(func):
    """Decorator to debug memory operations"""
    async def wrapper(*args, **kwargs):
        operation = func.__name__
        logger.info(f"Starting {operation}")
        logger.debug(f"Args: {args}, Kwargs: {kwargs}")
        
        try:
            result = await func(*args, **kwargs)
            logger.info(f"Completed {operation} successfully")
            logger.debug(f"Result: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed {operation}: {e}")
            logger.exception("Full traceback:")
            raise
            
    return wrapper

# Apply to memory functions
@debug_memory_operation
async def update_memory(user_id: str, memory: SimpleMemory):
    # Function implementation
    pass
```

**3. Memory Dump Utility**:
```python
async def dump_user_memory(user_id: str, output_file: str):
    """Export user's memory for debugging"""
    
    memory = await store.aget(("memory", user_id), "SimpleMemory")
    
    debug_info = {
        "user_id": user_id,
        "timestamp": datetime.now().isoformat(),
        "memory": asdict(memory) if memory else None,
        "stats": {
            "accounts": len(memory.accounts) if memory else 0,
            "contacts": len(memory.contacts) if memory else 0,
            "facts": len(memory.facts) if memory else 0
        }
    }
    
    with open(output_file, 'w') as f:
        json.dump(debug_info, f, indent=2)
        
    print(f"Memory dumped to {output_file}")
```

## Testing Memory Systems

Testing memory systems requires a comprehensive approach covering unit tests, integration tests, performance tests, and edge cases. Here's a complete testing strategy:

### 1. Unit Tests

**Test Extraction Accuracy**:
```python
import pytest
from unittest.mock import Mock, AsyncMock

class TestMemoryExtraction:
    @pytest.mark.asyncio
    async def test_basic_extraction(self):
        """Test basic entity extraction from conversation"""
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
        
    @pytest.mark.asyncio
    async def test_no_extraction_when_no_entities(self):
        """Test that extraction returns empty when no entities present"""
        messages = [
            HumanMessage("What's the weather like?"),
            AIMessage("It's sunny today!")
        ]
        
        result = await extract_memory(messages)
        
        assert len(result.accounts) == 0
        assert len(result.contacts) == 0
        
    @pytest.mark.asyncio
    async def test_extraction_with_preferences(self):
        """Test preference extraction"""
        messages = [
            HumanMessage("I prefer detailed explanations and always email me, never call")
        ]
        
        result = await extract_memory(messages)
        
        assert len(result.preferences) == 2
        assert any(p.preference_type == "communication_style" for p in result.preferences)
        assert any(p.preference_type == "contact_method" for p in result.preferences)
```

**Test Memory Merging**:
```python
class TestMemoryMerging:
    def test_merge_without_duplicates(self):
        """Test merging memories without creating duplicates"""
        existing = SimpleMemory(
            accounts=[SimpleAccount(id="001", name="Acme Corp")]
        )
        new = SimpleMemory(
            accounts=[SimpleAccount(id="001", name="Acme Corp")]
        )
        
        merged = merge_memories(existing, new)
        
        assert len(merged.accounts) == 1
        assert merged.accounts[0].id == "001"
        
    def test_merge_updates_incomplete_records(self):
        """Test that merge updates records with more complete info"""
        existing = SimpleMemory(
            accounts=[SimpleAccount(name="Acme Corp")]  # No ID
        )
        new = SimpleMemory(
            accounts=[SimpleAccount(id="001", name="Acme Corp")]  # Has ID
        )
        
        merged = merge_memories(existing, new)
        
        assert len(merged.accounts) == 1
        assert merged.accounts[0].id == "001"  # ID was added
        
    def test_merge_preserves_all_unique_entities(self):
        """Test that merge keeps all unique entities"""
        existing = SimpleMemory(
            accounts=[SimpleAccount(id="001", name="Acme Corp")]
        )
        new = SimpleMemory(
            accounts=[SimpleAccount(id="002", name="TechCorp")]
        )
        
        merged = merge_memories(existing, new)
        
        assert len(merged.accounts) == 2
        assert any(a.name == "Acme Corp" for a in merged.accounts)
        assert any(a.name == "TechCorp" for a in merged.accounts)
```

### 2. Integration Tests

**Test Full Memory Lifecycle**:
```python
class TestMemoryLifecycle:
    @pytest.mark.asyncio
    async def test_complete_memory_flow(self):
        """Test complete flow: extract, merge, save, load"""
        # Setup
        store = MemoryStore(":memory:")  # In-memory SQLite for testing
        extractor = MemoryExtractor(mock_llm)
        user_id = "test_user"
        
        # Step 1: Initial conversation
        messages1 = [
            HumanMessage("I work at Acme Corp"),
            AIMessage("Noted that you work at Acme Corp")
        ]
        
        memory1 = await extractor.extract(messages1)
        await store.save_memory(user_id, memory1)
        
        # Step 2: Second conversation
        messages2 = [
            HumanMessage("My manager is John Smith"),
            AIMessage("I'll remember John Smith is your manager")
        ]
        
        # Load existing memory
        existing = await store.load_memory(user_id)
        assert existing is not None
        
        # Extract and merge
        memory2 = await extractor.extract(messages2)
        merged = merge_memories(existing, memory2)
        await store.save_memory(user_id, merged)
        
        # Verify final state
        final_memory = await store.load_memory(user_id)
        assert len(final_memory.accounts) == 1
        assert final_memory.accounts[0].name == "Acme Corp"
        assert len(final_memory.contacts) == 1
        assert final_memory.contacts[0].name == "John Smith"
        
    @pytest.mark.asyncio
    async def test_concurrent_memory_updates(self):
        """Test that concurrent updates don't lose data"""
        store = AsyncMemoryStore()
        user_id = "concurrent_user"
        
        async def update_task(entity_name: str):
            memory = await store.load_memory(user_id) or SimpleMemory()
            memory.accounts.append(SimpleAccount(name=entity_name))
            await store.save_memory(user_id, memory)
            
        # Run concurrent updates
        await asyncio.gather(
            update_task("Company A"),
            update_task("Company B"),
            update_task("Company C")
        )
        
        # Verify all updates were saved
        final = await store.load_memory(user_id)
        assert len(final.accounts) == 3
```

### 3. Performance Tests

**Test Memory Operation Speed**:
```python
class TestMemoryPerformance:
    @pytest.mark.asyncio
    async def test_extraction_performance(self):
        """Ensure extraction completes within time limit"""
        messages = [HumanMessage(f"Message {i}") for i in range(100)]
        
        start_time = time.time()
        result = await extract_memory(messages)
        duration = time.time() - start_time
        
        assert duration < 5.0  # Should complete within 5 seconds
        
    @pytest.mark.asyncio
    async def test_large_memory_handling(self):
        """Test handling of large memory objects"""
        # Create memory with many entities
        large_memory = SimpleMemory(
            accounts=[SimpleAccount(name=f"Company {i}") for i in range(1000)],
            contacts=[SimpleContact(name=f"Person {i}") for i in range(1000)]
        )
        
        # Test save/load performance
        start = time.time()
        await store.save_memory("perf_test", large_memory)
        loaded = await store.load_memory("perf_test")
        duration = time.time() - start
        
        assert duration < 1.0  # Should be fast even with large data
        assert len(loaded.accounts) == 1000
        assert len(loaded.contacts) == 1000
```

### 4. Edge Case Tests

**Test Error Handling**:
```python
class TestMemoryErrorHandling:
    @pytest.mark.asyncio
    async def test_extraction_with_malformed_response(self):
        """Test handling of malformed LLM responses"""
        # Mock LLM that returns invalid JSON
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = Mock(content="Invalid JSON{")
        
        extractor = MemoryExtractor(mock_llm)
        result = await extractor.extract(["test message"])
        
        # Should return empty memory instead of crashing
        assert result == SimpleMemory()
        
    @pytest.mark.asyncio
    async def test_storage_failure_recovery(self):
        """Test recovery from storage failures"""
        # Mock store that fails on first attempt
        mock_store = AsyncMock()
        mock_store.aput.side_effect = [Exception("DB Error"), None]
        
        # Should retry and succeed
        await save_with_retry(mock_store, "user", SimpleMemory())
        assert mock_store.aput.call_count == 2
        
    def test_memory_with_special_characters(self):
        """Test handling of special characters in memory"""
        memory = SimpleMemory(
            accounts=[SimpleAccount(name="O'Reilly & Associates")]
        )
        
        # Should handle quotes and special chars
        serialized = json.dumps(asdict(memory))
        deserialized = SimpleMemory(**json.loads(serialized))
        
        assert deserialized.accounts[0].name == "O'Reilly & Associates"
```

### 5. Mock Testing Utilities

**Create Test Fixtures**:
```python
@pytest.fixture
def mock_memory_store():
    """Create a mock memory store for testing"""
    store = Mock()
    store.memories = {}
    
    async def mock_save(user_id, memory):
        store.memories[user_id] = memory
        
    async def mock_load(user_id):
        return store.memories.get(user_id)
        
    store.save_memory = mock_save
    store.load_memory = mock_load
    
    return store

@pytest.fixture
def sample_memory():
    """Create sample memory for testing"""
    return SimpleMemory(
        accounts=[
            SimpleAccount(id="001", name="Acme Corp"),
            SimpleAccount(id="002", name="TechCorp")
        ],
        contacts=[
            SimpleContact(name="John Smith", account_name="Acme Corp"),
            SimpleContact(name="Jane Doe", account_name="TechCorp")
        ],
        preferences=[
            UserPreference(preference_type="communication", value="email")
        ]
    )
```

### 6. Test Utilities

**Memory Comparison Helper**:
```python
def assert_memories_equal(memory1: SimpleMemory, memory2: SimpleMemory):
    """Helper to compare two memory objects"""
    assert len(memory1.accounts) == len(memory2.accounts)
    assert len(memory1.contacts) == len(memory2.contacts)
    
    # Compare accounts
    for acc1, acc2 in zip(sorted(memory1.accounts, key=lambda x: x.name),
                          sorted(memory2.accounts, key=lambda x: x.name)):
        assert acc1.id == acc2.id
        assert acc1.name == acc2.name
        
    # Compare other entities...

class MemoryTestHelper:
    """Utilities for memory testing"""
    
    @staticmethod
    def create_test_conversation(topics: List[str]) -> List[Message]:
        """Generate test conversation about given topics"""
        messages = []
        for topic in topics:
            messages.append(HumanMessage(f"Tell me about {topic}"))
            messages.append(AIMessage(f"Here's information about {topic}"))
        return messages
        
    @staticmethod
    async def assert_extraction_contains(messages: List[Message], 
                                       expected_entities: Dict[str, List[str]]):
        """Assert that extraction contains expected entities"""
        result = await extract_memory(messages)
        
        if "accounts" in expected_entities:
            account_names = [a.name for a in result.accounts]
            for expected in expected_entities["accounts"]:
                assert expected in account_names
```

## Real Examples from Our Orchestrator

Here are actual implementations from our production multi-agent orchestrator system, demonstrating how memory is used in practice:

### 1. Memory Initialization in LangGraph

**Loading Memory at Conversation Start**:
```python
# From src/orchestrator/main.py
async def initialize_memory(state: OrchestratorState, config: RunnableConfig) -> OrchestratorState:
    """Initialize memory from storage if not already loaded."""
    if state.get("memory_init_done"):
        return state
    
    user_id = state["user_id"]
    store = get_async_store_adapter()
    
    try:
        # Load from namespace ("memory", user_id)
        stored_item = await store.aget(
            namespace=("memory", user_id),
            key="SimpleMemory"
        )
        
        if stored_item and stored_item.value:
            # Deserialize from stored format
            memory_data = stored_item.value
            if isinstance(memory_data, str):
                memory_data = json.loads(memory_data)
            
            memory = SimpleMemory(**memory_data)
            logger.info(f"Loaded memory for user {user_id}: "
                       f"{len(memory.accounts)} accounts, "
                       f"{len(memory.contacts)} contacts")
        else:
            memory = SimpleMemory()
            logger.info(f"No existing memory for user {user_id}")
            
    except Exception as e:
        logger.error(f"Failed to load memory: {e}")
        memory = SimpleMemory()
    
    return {
        "memory": memory,
        "memory_init_done": True
    }
```

### 2. Background Memory Updates

**Asynchronous Memory Extraction**:
```python
# From src/orchestrator/main.py - update_memory node
async def update_memory(state: UpdateMemoryState, config: RunnableConfig) -> UpdateMemoryState:
    """Background task to extract and update memory from recent messages."""
    
    user_id = state["user_id"]
    messages = state.get("messages", [])
    
    if not messages:
        return {"memory_updated": True}
    
    # Create extraction prompt
    messages_text = "\n".join([
        f"{msg.__class__.__name__}: {msg.content}"
        for msg in messages[-10:]  # Last 10 messages
    ])
    
    # Extract using TrustCall
    extractor = create_extractor(
        llm,
        tools=[SimpleMemoryExtractor],
        tool_choice="SimpleMemoryExtractor"
    )
    
    try:
        extraction_messages = [
            SystemMessage(content=TRUSTCALL_INSTRUCTION),
            HumanMessage(content=f"Extract CRM entities from:\n{messages_text}")
        ]
        
        result = await extractor.ainvoke({"messages": extraction_messages})
        
        if result and hasattr(result, 'content'):
            extracted_memory = result.content
            
            # Merge with existing
            store = get_async_store_adapter()
            existing_item = await store.aget(
                namespace=("memory", user_id),
                key="SimpleMemory"
            )
            
            if existing_item:
                existing_memory = SimpleMemory(**existing_item.value)
                merged_memory = merge_memories(existing_memory, extracted_memory)
            else:
                merged_memory = extracted_memory
            
            # Save updated memory
            await store.aput(
                namespace=("memory", user_id),
                key="SimpleMemory",
                value=asdict(merged_memory)
            )
            
            logger.info(f"Updated memory for {user_id}")
            
    except Exception as e:
        logger.error(f"Memory update failed: {e}")
    
    return {"memory_updated": True}
```

### 3. Memory-Aware Tool Selection

**Using Memory Context for Agent Decisions**:
```python
# From src/orchestrator/main.py - llm_node
def create_memory_context(memory: SimpleMemory) -> str:
    """Create context string from memory for LLM."""
    context_parts = []
    
    # Include recent accounts
    if memory.accounts:
        recent_accounts = memory.accounts[:5]
        account_names = [acc.name for acc in recent_accounts]
        context_parts.append(f"Known accounts: {', '.join(account_names)}")
    
    # Include recent contacts
    if memory.contacts:
        recent_contacts = memory.contacts[:5]
        contact_info = [f"{c.name} ({c.account_name})" 
                       for c in recent_contacts if c.account_name]
        if contact_info:
            context_parts.append(f"Known contacts: {', '.join(contact_info)}")
    
    # Include active opportunities
    if memory.opportunities:
        open_opps = [opp for opp in memory.opportunities 
                    if opp.stage not in ["Closed Won", "Closed Lost"]][:3]
        if open_opps:
            opp_info = [f"{o.name} ({o.stage})" for o in open_opps]
            context_parts.append(f"Active opportunities: {', '.join(opp_info)}")
    
    return "\n".join(context_parts) if context_parts else ""

# In the LLM decision node
memory_context = create_memory_context(state.get("memory", SimpleMemory()))
enhanced_messages = [
    SystemMessage(content=f"{system_message}\n\nMemory Context:\n{memory_context}")
] + state["messages"]
```

### 4. Intelligent Memory Merging

**Deduplication and Update Logic**:
```python
# From src/orchestrator/main.py
def merge_memories(existing: SimpleMemory, new: SimpleMemory) -> SimpleMemory:
    """Merge two memory objects, avoiding duplicates."""
    
    def add_or_update_item(items: List[T], new_item: T) -> List[T]:
        """Add new item or update existing based on ID/name match."""
        
        # Match by ID first
        if hasattr(new_item, 'id') and new_item.id:
            for i, item in enumerate(items):
                if hasattr(item, 'id') and item.id == new_item.id:
                    # Update if new item has more information
                    if is_more_complete(new_item, item):
                        items[i] = new_item
                    return items
        
        # Match by name
        if hasattr(new_item, 'name'):
            item_name_lower = new_item.name.lower()
            for i, item in enumerate(items):
                if hasattr(item, 'name') and item.name.lower() == item_name_lower:
                    # Update if new has ID but existing doesn't
                    if (hasattr(new_item, 'id') and new_item.id and 
                        hasattr(item, 'id') and not item.id):
                        items[i] = new_item
                    return items
        
        # No match - add as new
        items.append(new_item)
        return items
    
    # Merge each entity type
    merged = SimpleMemory()
    
    # Copy existing items
    merged.accounts = existing.accounts.copy()
    merged.contacts = existing.contacts.copy()
    merged.opportunities = existing.opportunities.copy()
    
    # Add/update new items
    for account in new.accounts:
        merged.accounts = add_or_update_item(merged.accounts, account)
    
    for contact in new.contacts:
        merged.contacts = add_or_update_item(merged.contacts, contact)
        
    # ... continue for other entities
    
    return merged
```

### 5. Memory-Triggered Updates

**Automatic Memory Updates Based on Activity**:
```python
# From src/orchestrator/main.py - route_after_llm
def route_after_llm(state: OrchestratorState) -> Literal["tools", "final", "update_memory"]:
    """Route based on LLM decision and memory update needs."""
    
    messages = state.get("messages", [])
    last_memory_update = state.get("last_memory_update_index", 0)
    
    # Check if we should update memory
    should_update = False
    
    # Update every 5 user messages
    user_messages_since_update = sum(
        1 for msg in messages[last_memory_update:]
        if isinstance(msg, HumanMessage)
    )
    
    if user_messages_since_update >= 5:
        should_update = True
        
    # Update if significant CRM data mentioned
    recent_messages = messages[-3:]
    crm_keywords = ["account", "contact", "opportunity", "lead", "case"]
    
    for msg in recent_messages:
        if any(keyword in msg.content.lower() for keyword in crm_keywords):
            should_update = True
            break
    
    if should_update and not state.get("memory_update_scheduled"):
        # Schedule background memory update
        return "update_memory"
    
    # Continue with tool execution or final response
    return "tools" if state.get("tool_calls") else "final"
```

### 6. Thread State Persistence

**Saving Complete Conversation State**:
```python
# From src/orchestrator/main.py
async def save_thread_state(thread_id: str, state: dict, store: BaseStore):
    """Save complete thread state for resumption."""
    
    # Serialize messages properly
    serialized_state = state.copy()
    
    if "messages" in serialized_state:
        serialized_state["messages"] = _serialize_messages(state["messages"])
    
    # Include metadata
    state_data = {
        "state": serialized_state,
        "thread_id": thread_id,
        "timestamp": time.time(),
        "checkpoint_version": "1.0"
    }
    
    # Save to store
    await store.aput(
        namespace=("threads", thread_id),
        key=f"state_{thread_id}",
        value=state_data
    )

def _serialize_messages(messages: List[Any]) -> List[dict]:
    """Convert LangChain messages to JSON-serializable format."""
    serializable_messages = []
    
    for msg in messages:
        if hasattr(msg, 'dict'):
            # LangChain message objects
            msg_dict = msg.dict()
        elif isinstance(msg, dict):
            msg_dict = msg
        else:
            # Fallback for unknown message types
            msg_dict = {
                "type": type(msg).__name__,
                "content": str(getattr(msg, 'content', str(msg))),
                "additional_kwargs": getattr(msg, 'additional_kwargs', {})
            }
            
        serializable_messages.append(msg_dict)
        
    return serializable_messages
```

### 7. Memory in Production Error Handling

**Graceful Degradation When Memory Fails**:
```python
# From src/orchestrator/main.py
class MemoryManager:
    def __init__(self, store: BaseStore, logger: Logger):
        self.store = store
        self.logger = logger
        self.memory_cache = {}  # In-memory fallback
        
    async def load_user_memory(self, user_id: str) -> SimpleMemory:
        """Load memory with fallback strategies."""
        
        try:
            # Try primary store
            stored = await self.store.aget(
                namespace=("memory", user_id),
                key="SimpleMemory"
            )
            
            if stored:
                return SimpleMemory(**stored.value)
                
        except ConnectionError:
            self.logger.warning(f"Primary store unavailable for {user_id}")
            
            # Try cache
            if user_id in self.memory_cache:
                self.logger.info("Using cached memory")
                return self.memory_cache[user_id]
                
        except Exception as e:
            self.logger.error(f"Memory load failed: {e}")
            
        # Return empty memory as fallback
        return SimpleMemory()
        
    async def save_user_memory(self, user_id: str, memory: SimpleMemory) -> bool:
        """Save memory with retry and caching."""
        
        # Always update cache
        self.memory_cache[user_id] = memory
        
        # Try to persist
        for attempt in range(3):
            try:
                await self.store.aput(
                    namespace=("memory", user_id),
                    key="SimpleMemory",
                    value=asdict(memory)
                )
                return True
                
            except Exception as e:
                self.logger.warning(f"Save attempt {attempt + 1} failed: {e}")
                
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    
        self.logger.error(f"Failed to persist memory for {user_id}")
        return False
```

### 8. Memory Analytics and Monitoring

**Production Monitoring Implementation**:
```python
# From src/utils/logging/memory_logger.py
class MemoryMetrics:
    def __init__(self):
        self.operations = []
        
    async def track_operation(self, operation: str, user_id: str, 
                            duration: float, success: bool, 
                            memory_size: Optional[int] = None):
        """Track memory operation metrics."""
        
        metric = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "user_id": user_id,
            "duration_ms": duration * 1000,
            "success": success,
            "memory_size_bytes": memory_size
        }
        
        self.operations.append(metric)
        
        # Log for monitoring systems
        logger.info("memory_metric", extra=metric)
        
        # Alert on slow operations
        if duration > 2.0:
            logger.warning(f"Slow memory operation: {operation} took {duration:.2f}s")
            
        # Alert on large memory
        if memory_size and memory_size > 1_000_000:  # 1MB
            logger.warning(f"Large memory for user {user_id}: {memory_size / 1_000_000:.1f}MB")

# Usage in production
metrics = MemoryMetrics()

start = time.time()
memory = await load_memory(user_id)
duration = time.time() - start

await metrics.track_operation(
    "load_memory",
    user_id,
    duration,
    success=memory is not None,
    memory_size=len(json.dumps(asdict(memory))) if memory else 0
)
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

## Common Pitfalls and How to Avoid Them

Understanding common mistakes helps junior engineers build robust memory systems from the start:

### 1. **Over-Extraction: Remembering Everything**

**Pitfall**: Trying to extract and store every piece of information from conversations.

```python
# ❌ BAD: Over-eager extraction
class OverEagerExtractor:
    async def extract(self, message: str):
        # Extracts everything including irrelevant details
        return {
            "weather_mentioned": "sunny" in message,
            "time_of_day": extract_time(message),
            "word_count": len(message.split()),
            "sentiment": analyze_sentiment(message),
            # ... hundreds more fields
        }
```

**Solution**: Be selective and purpose-driven.

```python
# ✅ GOOD: Focused extraction
class FocusedExtractor:
    async def extract(self, message: str):
        # Only extract business-relevant information
        entities = {}
        
        # Clear criteria for extraction
        if has_company_mention(message):
            entities["company"] = extract_company(message)
            
        if has_contact_info(message):
            entities["contact"] = extract_contact(message)
            
        return entities
```

### 2. **Forgetting to Handle Async Operations**

**Pitfall**: Not properly awaiting async operations, causing silent failures.

```python
# ❌ BAD: Missing await
def update_user_memory(user_id: str, new_info: dict):
    memory = load_memory(user_id)  # This returns a coroutine!
    memory.update(new_info)
    save_memory(user_id, memory)   # This also returns a coroutine!
    # Nothing actually happens!
```

**Solution**: Always use async/await properly.

```python
# ✅ GOOD: Proper async handling
async def update_user_memory(user_id: str, new_info: dict):
    memory = await load_memory(user_id)
    memory.update(new_info)
    await save_memory(user_id, memory)
```

### 3. **No Deduplication Strategy**

**Pitfall**: Storing duplicate information, causing memory bloat.

```python
# ❌ BAD: No deduplication
class NaiveMemory:
    def add_account(self, account: Account):
        self.accounts.append(account)  # Duplicates accumulate!
```

**Solution**: Implement proper deduplication logic.

```python
# ✅ GOOD: Smart deduplication
class SmartMemory:
    def add_account(self, account: Account):
        # Check for existing account
        existing_index = self._find_account(account.name)
        
        if existing_index >= 0:
            # Update if new info is more complete
            if self._is_more_complete(account, self.accounts[existing_index]):
                self.accounts[existing_index] = account
        else:
            # Add as new
            self.accounts.append(account)
```

### 4. **Ignoring Memory Size Limits**

**Pitfall**: Allowing unlimited memory growth, causing performance issues.

```python
# ❌ BAD: Unbounded memory growth
class UnboundedMemory:
    def __init__(self):
        self.all_messages = []  # Keeps everything forever!
        
    def add_message(self, message):
        self.all_messages.append(message)
```

**Solution**: Implement size limits and cleanup strategies.

```python
# ✅ GOOD: Bounded memory with cleanup
class BoundedMemory:
    def __init__(self, max_messages: int = 1000):
        self.messages = []
        self.max_messages = max_messages
        
    def add_message(self, message):
        self.messages.append(message)
        
        # Keep only recent messages
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]
            
        # Or implement time-based cleanup
        self._cleanup_old_messages()
```

### 5. **Poor Error Handling**

**Pitfall**: Crashing when memory operations fail.

```python
# ❌ BAD: No error handling
async def get_user_context(user_id: str) -> str:
    memory = await load_memory(user_id)  # What if this fails?
    return memory.create_context()       # Crash!
```

**Solution**: Always handle failures gracefully.

```python
# ✅ GOOD: Robust error handling
async def get_user_context(user_id: str) -> str:
    try:
        memory = await load_memory(user_id)
        if memory:
            return memory.create_context()
    except ConnectionError:
        logger.warning(f"Could not load memory for {user_id}, using empty context")
    except Exception as e:
        logger.error(f"Unexpected error loading memory: {e}")
        
    # Always return something useful
    return "No previous context available."
```

### 6. **Blocking the Main Thread**

**Pitfall**: Performing memory operations synchronously in async contexts.

```python
# ❌ BAD: Blocking I/O in async function
async def process_message(message: str):
    # This blocks the event loop!
    with open("memory.json", "r") as f:
        memory = json.load(f)
    
    # Process message...
```

**Solution**: Use async I/O or thread pools.

```python
# ✅ GOOD: Non-blocking I/O
async def process_message(message: str):
    # Use async file operations
    async with aiofiles.open("memory.json", "r") as f:
        content = await f.read()
        memory = json.loads(content)
    
    # Or use thread pool for sync operations
    loop = asyncio.get_event_loop()
    memory = await loop.run_in_executor(None, load_memory_sync)
```

### 7. **Not Considering Concurrent Access**

**Pitfall**: Race conditions when multiple requests access the same memory.

```python
# ❌ BAD: Race condition
class UnsafeMemory:
    async def increment_counter(self, user_id: str):
        memory = await self.load(user_id)
        memory.counter += 1  # Race condition here!
        await self.save(user_id, memory)
```

**Solution**: Implement proper locking or use atomic operations.

```python
# ✅ GOOD: Thread-safe operations
class SafeMemory:
    def __init__(self):
        self.locks = {}
        
    async def increment_counter(self, user_id: str):
        # Get or create lock for user
        if user_id not in self.locks:
            self.locks[user_id] = asyncio.Lock()
            
        async with self.locks[user_id]:
            memory = await self.load(user_id)
            memory.counter += 1
            await self.save(user_id, memory)
```

### 8. **Inefficient Serialization**

**Pitfall**: Using inefficient serialization formats or methods.

```python
# ❌ BAD: Inefficient serialization
def save_memory(memory: ComplexObject):
    # Pickle can be slow and insecure
    with open("memory.pkl", "wb") as f:
        pickle.dump(memory, f)
```

**Solution**: Use efficient, secure serialization.

```python
# ✅ GOOD: Efficient JSON serialization
def save_memory(memory: SimpleMemory):
    # Convert to dict, remove None values
    data = asdict(memory)
    cleaned_data = {k: v for k, v in data.items() if v is not None}
    
    # Compact JSON
    json_str = json.dumps(cleaned_data, separators=(',', ':'))
    
    # Compress if large
    if len(json_str) > 10000:
        json_str = zlib.compress(json_str.encode())
```

### 9. **Forgetting About Privacy**

**Pitfall**: Storing sensitive information without consideration.

```python
# ❌ BAD: Storing sensitive data in plain text
class InsecureMemory:
    def store_user_info(self, info: dict):
        # Stores SSN, passwords, etc. in plain text!
        self.user_data = info
```

**Solution**: Implement privacy controls.

```python
# ✅ GOOD: Privacy-aware storage
class SecureMemory:
    SENSITIVE_FIELDS = ["ssn", "password", "credit_card"]
    
    def store_user_info(self, info: dict):
        # Filter or hash sensitive data
        safe_info = {}
        for key, value in info.items():
            if key in self.SENSITIVE_FIELDS:
                safe_info[key] = self._hash_sensitive(value)
            else:
                safe_info[key] = value
                
        self.user_data = safe_info
```

### 10. **No Migration Strategy**

**Pitfall**: Changing memory schema without handling existing data.

```python
# ❌ BAD: Breaking schema change
# Version 1
class MemoryV1:
    name: str
    
# Version 2 - breaks existing data!
class MemoryV2:
    first_name: str  # Changed field name
    last_name: str   # New required field
```

**Solution**: Implement versioning and migration.

```python
# ✅ GOOD: Versioned schema with migration
class MemoryMigrator:
    @staticmethod
    def migrate_v1_to_v2(old_memory: dict) -> dict:
        """Migrate from v1 to v2 schema"""
        new_memory = {
            "version": 2,
            "first_name": old_memory.get("name", "").split()[0],
            "last_name": old_memory.get("name", "").split()[-1] if len(old_memory.get("name", "").split()) > 1 else "",
        }
        return new_memory
        
    @staticmethod
    def load_memory(data: dict) -> Memory:
        version = data.get("version", 1)
        
        if version == 1:
            data = MemoryMigrator.migrate_v1_to_v2(data)
            
        return Memory(**data)
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