# 📊 Log Interpretation Cheat Sheet

## 🔍 Quick Search Guide (Ctrl+F Patterns)

### 🚨 Finding Errors & Issues
```bash
# Critical errors
"level": "ERROR"
"error_type":
"error":

# Warnings (less critical)
"level": "WARNING"
"warning":

# Specific error types
"SQLite objects created in a thread"  # Threading issues
"readonly database"                    # Database lock issues
"Cannot connect to host"              # Network/agent down
"AttributeError"                      # Code bugs
"TimeoutError"                        # Performance issues
```

### 🎯 User Interactions
```bash
# User inputs
"user_input_raw"              # What user typed
"user_request"                # Processed user message
"user_quit"                   # User exited

# AI responses
"user_message_displayed"      # What the AI showed to user
"llm_generation_complete"     # AI response generated
```

### 🤖 Agent Communication
```bash
# Agent health
"health_check_"               # Agent status checks
"Online agents:"              # Working agents
"Offline agents:"             # Failed agents

# Agent calls
"a2a_dispatch"                # Request sent to agent
"a2a_task_start"              # Agent processing started
"a2a_task_complete"           # Agent finished
"tool_invocation_"            # Tool usage

# Salesforce specific
"salesforce_agent"            # Salesforce operations
```

### 💾 Memory & Storage
```bash
# Memory operations
"memory_load_"                # Loading memory
"memory_extraction_"          # Extracting new data
"memory_update"               # Saving memory
"records_extracted"           # What was found

# Database operations
"sqlite_get"                  # Reading from DB
"sqlite_put"                  # Writing to DB
"storage"                     # All storage ops
```

### 🔄 System State
```bash
# Session management
"orchestrator_session_start"  # System startup
"agent_SYSTEM_"              # System events
"thread_id"                  # Conversation threads

# Background tasks
"background_summary"          # Summarization
"background_memory"           # Memory extraction
"summary_trigger"             # Why summary happened
"memory_trigger"             # Why memory extracted
```

### 💰 Performance & Cost
```bash
# Token usage
"token_usage"                # LLM token costs
"cost":                      # Dollar amounts
"session_cost"               # Running total

# Timing
"duration_seconds"           # How long things took
"elapsed_seconds"            # Operation time
"timeout"                    # Timeout issues
```

## 📋 Common Log Patterns

### 1️⃣ **Successful User Request Flow**
```json
1. {"message": "user_input_raw", "input": "get the genepoint account"}
2. {"message": "llm_invocation_start"}
3. {"message": "tool_call", "tool_name": "salesforce_agent"}
4. {"message": "a2a_dispatch", "agent": "salesforce-agent"}
5. {"message": "a2a_task_complete", "success": true}
6. {"message": "llm_generation_complete"}
7. {"message": "user_message_displayed", "response": "Here are the details..."}
```

### 2️⃣ **Error Flow**
```json
1. {"level": "ERROR", "message": "a2a_network_error", "error": "Cannot connect"}
2. {"level": "WARNING", "message": "retry_attempt_failed"}
3. {"level": "ERROR", "message": "all_retry_attempts_failed"}
4. {"level": "ERROR", "message": "tool_invocation_error"}
```

### 3️⃣ **Memory Extraction Flow**
```json
1. {"message": "memory_trigger"}
2. {"message": "memory_extraction_start"}
3. {"message": "trustcall_extraction_start"}
4. {"message": "records_extracted", "record_type": "accounts", "count": 1}
5. {"message": "memory_update_complete"}
```

## 🎨 Log Components Explained

### Component Field Values
- `"orchestrator"` - Main conversation handler
- `"salesforce-agent"` - Salesforce operations
- `"a2a"` - Agent-to-agent communication
- `"storage"` - Database operations
- `"config"` - Configuration management

### Operation Types
- `"conversation_processing"` - Handling user messages
- `"health_check"` - Checking agent status
- `"process_task"` - Agent executing work
- `"extract_records"` - Finding CRM data
- `"background_summary"` - Summarizing conversation

## 🛠️ Troubleshooting by Symptom

### "Bot not responding"
Search for:
1. `"level": "ERROR"`
2. `"llm_invocation_start"` (last one)
3. `"timeout"`

### "Wrong/missing data"
Search for:
1. `"memory_extraction"`
2. `"records_extracted"`
3. `"tool_invocation_error"`

### "Agent offline"
Search for:
1. `"health_check_failed"`
2. `"a2a_network_error"`
3. `"Offline agents"`

### "Slow performance"
Search for:
1. `"duration_seconds"`
2. `"elapsed_seconds"`
3. Sort by these values

## 📊 Useful JQ Commands

```bash
# Show only errors
jq 'select(.level == "ERROR")' logs/app.log

# Show user interactions
jq 'select(.message | contains("user_"))' logs/app.log

# Show agent communication
jq 'select(.component == "a2a")' logs/app.log

# Show timing info
jq 'select(.duration_seconds != null) | {time: .timestamp, op: .operation, duration: .duration_seconds}' logs/app.log

# Show cost tracking
jq 'select(.cost != null) | {time: .timestamp, tokens: .tokens, cost: .cost}' logs/app.log

# Pretty print specific message
jq 'select(.message == "user_input_raw")' logs/app.log
```

## 🔄 Log Rotation

Logs rotate at 50MB with 5 backups:
- `app.log` (current)
- `app.log.1` (newest backup)
- `app.log.2-5` (older backups)

## 💡 Pro Tips

1. **Use timestamps** - They're ISO format, sortable
2. **Follow operation_id** - Links related events
3. **Check component** - Identifies which part failed
4. **Look for patterns** - Errors often cascade
5. **Check event_count** - Shows conversation progress

## 🚦 Status Indicators

### Good Signs ✅
- `"success": true`
- `"status_code": 200`
- `"new_status": "online"`
- `"message": "complete"`

### Warning Signs ⚠️
- `"level": "WARNING"`
- `"retry_attempt"`
- `"timeout"`
- `"status": "error"`

### Bad Signs ❌
- `"level": "ERROR"`
- `"all_retry_attempts_failed"`
- `"AttributeError"`
- `"resilient_call_failed"`

## 📈 Common Sequences

### Startup
```
agent_SYSTEM_START
→ config_loaded
→ health_check_all_start
→ orchestrator_session_start
```

### User Message
```
user_input_raw
→ orchestrator_state_entry
→ llm_invocation_start
→ tool_call (optional)
→ llm_generation_complete
→ user_message_displayed
```

### Background Tasks
```
summary_trigger/memory_trigger
→ background task starts
→ extraction/summary processing
→ storage operations
→ complete/error
```

Remember: The logs are chronological, so you can follow the flow from top to bottom!