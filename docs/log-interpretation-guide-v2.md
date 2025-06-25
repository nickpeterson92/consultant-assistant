# 📊 Enhanced Log Interpretation Guide v2

## 📁 NEW: Multi-File Logging System

As of 2025-06-25, logs are now separated by component for easier debugging:

```bash
logs/
├── orchestrator.log      # Orchestrator operations, LLM calls, user interactions
├── salesforce.log        # Salesforce agent AND tool operations combined
├── a2a_protocol.log      # Network calls, circuit breakers, retries
├── storage.log           # SQLite operations, memory persistence
├── system.log            # Startup/shutdown, config loads, health checks
└── errors.log            # ALL ERROR level messages across components
```

### Quick Commands for Multi-File Logs
```bash
# Watch Salesforce operations (agent + tools together)
tail -f logs/salesforce.log

# Track a request across ALL components  
grep "task_id:abc123" logs/*.log | sort

# Monitor all errors in real-time
tail -f logs/errors.log

# See what's happening right now across system
tail -f logs/*.log | grep -v "health_check"
```

## 🎯 Quick Reference - What to Search For

### 🚨 Error Patterns (Priority Searches)
```bash
# Critical Errors - Search These First!
"level\": \"ERROR\"                    # Any error condition
"error_type\":                       # Specific error classification
"error\":                           # Error details/messages
"AttributeError"                    # Code bugs (missing methods/properties)
"all_retry_attempts_failed"         # Complete failure after retries
"resilient_call_failed"             # Circuit breaker gave up

# Threading/Database Issues
"SQLite objects created in a thread"  # Thread safety violations
"readonly database"                   # Database lock contentions
"connection_close_error"              # Connection cleanup issues

# Network/Agent Issues  
"a2a_network_error"                  # Agent communication failures
"Cannot connect to host"             # Agent offline/unreachable
"health_check_failed"                # Agent not responding
"tool_invocation_error"              # Tool execution failed
```

### 🎯 User Flow Tracking
```bash
# User Journey Markers
"user_input_raw"                     # Exact user input
"orchestrator_state_entry"           # Processing begins
"llm_invocation_start"               # AI thinking starts
"tool_call"                          # Tool being invoked
"a2a_dispatch"                       # Request sent to agent
"llm_generation_complete"            # AI response ready
"user_message_displayed"             # What user sees

# Key Identifiers
"thread_id"                          # Conversation thread
"task_id"                           # Specific agent task
"operation_id"                      # Unique operation ID
```

### 🤖 Agent Communication Flow
```bash
# Health Monitoring
"health_check_start"                 # Checking agent status
"health_check_success"               # Agent is healthy
"health_check_failed"                # Agent has issues
"health_check_all_complete"          # System status summary

# A2A Protocol Events
"a2a_client_initialized"             # Client setup
"circuit_breaker_created"            # Resilience activated
"a2a_call_start"                     # Request initiated
"a2a_request_start"                  # Network call begins
"a2a_response_received"              # Got response
"a2a_call_success"                   # Completed successfully
"a2a_task_complete"                  # Task finished

# Connection Management
"creating_new_session"               # New HTTP session
"connection_pool_initialized"        # Pool setup
"timeout_config"                     # Timeout settings
```

### 💾 Storage Operations
```bash
# Memory Operations
"memory_load_start"                  # Loading user memory
"memory_get"                         # Retrieving data
"memory_put"                         # Storing data
"memory_extraction_"                 # Extracting from conversation
"memory_extraction_start"            # Extraction beginning
"memory_extraction_complete"         # Extraction finished
"memory_extraction_error"            # Extraction failed
"memory_extraction_timeout"          # Extraction took too long
"memory_update"                      # Saving changes
"memory_update_complete"             # Update finished
"deduplication_complete"             # Duplicate records removed

# SQLite Operations
"sqlite_init"                        # Database initialized
"sqlite_get"                         # Reading from DB
"sqlite_put"                         # Writing to DB
"sqlite_pool_initialized"            # Connection pool ready
```

### 🔄 Background Tasks & Triggers
```bash
# Summary Operations
"summary_trigger"                    # Why summarization started
"background_summary"                 # Background task running
"background_summary_save"            # Saving summary to store
"background_summary_error"           # Summary task failed
"summary_response"                   # Summary generation result
"summary_format_error"               # Invalid summary format

# Memory Background Tasks
"memory_trigger"                     # Why memory extraction started
"background_memory"                  # Background memory task
"background_memory_save"             # Saving memory to store
"background_memory_error"            # Memory task failed

# Thread Management
"state_key_prefix"                   # Thread state storage
"thread_list"                        # Active threads
```

### 📊 Performance Metrics
```bash
# Timing Information
"duration_seconds"                   # Operation duration
"elapsed_seconds"                    # Time taken
"token_usage"                        # LLM token consumption
"cost"                              # Dollar cost
"session_cost"                       # Running total cost
```

## 🔍 Real Log Analysis Examples

### Example 1: Successful User Request
```json
// 1. User asks a question
{"timestamp": "2025-06-24T23:10:19.655793Z", "message": "user_input_raw", "input": "get the genepoint account"}

// 2. System processes
{"timestamp": "2025-06-24T23:10:19.660429Z", "message": "orchestrator_state_entry", "thread_id": "orchestrator-39283fe3"}

// 3. Checks memory
{"timestamp": "2025-06-24T23:10:19.660689Z", "message": "sqlite_get", "key": "SimpleMemory", "found": false}

// 4. Invokes AI
{"timestamp": "2025-06-24T23:10:19.660946Z", "message": "llm_invocation_start", "message_count": 2}

// 5. AI decides to use tool
{"timestamp": "2025-06-24T23:10:20.864293Z", "message": "tool_call", "tool_name": "salesforce_agent"}

// 6. Dispatches to agent
{"timestamp": "2025-06-24T23:10:20.868164Z", "message": "a2a_dispatch", "agent": "salesforce-agent", "task_id": "64e52918-619e-4ada-85a9-df20b1963b0c"}

// 7. Agent responds
{"timestamp": "2025-06-24T23:10:25.116460Z", "message": "a2a_task_complete", "success": true}

// 8. Shows to user
{"timestamp": "2025-06-24T23:10:27.198692Z", "message": "user_message_displayed", "response": "Here are the details for the **GenePoint** account..."}
```

### Example 2: Agent Connection Failure
```json
// 1. Health check attempt
{"timestamp": "2025-06-24T23:10:14.146986Z", "message": "health_check_start", "agent_name": "jira-agent", "current_status": "error"}

// 2. Network error
{"timestamp": "2025-06-24T23:10:14.149123Z", "level": "ERROR", "message": "a2a_network_error", "error": "Cannot connect to host localhost:8002"}

// 3. Retry attempt
{"timestamp": "2025-06-24T23:10:14.149170Z", "level": "WARNING", "message": "retry_attempt_failed", "attempt": 1}

// 4. All retries fail
{"timestamp": "2025-06-24T23:10:16.263009Z", "level": "ERROR", "message": "all_retry_attempts_failed", "max_attempts": 3}

// 5. Final failure
{"timestamp": "2025-06-24T23:10:16.263360Z", "level": "WARNING", "message": "health_check_failed", "agent_name": "jira-agent", "new_status": "error"}
```

### Example 3: Background Summary Process
```json
// 1. Summary triggered
{"timestamp": "2025-06-24T23:15:30.123Z", "message": "summary_trigger", "reason": "message_count_threshold", "message_count": 10}

// 2. Background task starts
{"timestamp": "2025-06-24T23:15:30.150Z", "message": "background_summary", "thread_id": "orchestrator-39283fe3"}

// 3. Summary generated
{"timestamp": "2025-06-24T23:15:32.456Z", "message": "summary_response", "messages_preserved": 2, "messages_deleted": 8}

// 4. Saved to storage
{"timestamp": "2025-06-24T23:15:32.789Z", "message": "background_summary_save", "summary_preview": "User requested Salesforce account information..."}
```

### Example 4: Memory Extraction Process
```json
// 1. Memory extraction triggered
{"timestamp": "2025-06-24T23:20:45.123Z", "message": "memory_trigger", "reason": "tool_call_threshold"}

// 2. Extraction starts
{"timestamp": "2025-06-24T23:20:45.456Z", "message": "memory_extraction_start", "message_count": 15}

// 3. Records found
{"timestamp": "2025-06-24T23:20:46.789Z", "message": "records_extracted", "record_type": "accounts", "count": 2}

// 4. Deduplication
{"timestamp": "2025-06-24T23:20:47.012Z", "message": "deduplication_complete", "before_count": 5, "after_count": 3}

// 5. Memory updated
{"timestamp": "2025-06-24T23:20:47.345Z", "message": "memory_update_complete", "total_after": 3}
```

## 📈 Key Performance Indicators

### System Health Check
Search for `"health_check_all_complete"` to find:
```json
{
  "message": "health_check_all_complete",
  "total_agents": 2,
  "online_count": 1,
  "offline_count": 1,
  "success_rate": 50.0
}
```

### Response Times
Search for `"a2a_response_received"` to see:
```json
{
  "message": "a2a_response_received",
  "elapsed_seconds": 4.25,  // Time taken
  "status_code": 200        // Success
}
```

### Token Usage
Search for `"token_usage"` to track costs:
```json
{
  "message": "token_usage",
  "tokens": 3055,
  "cost": 0.0005,
  "session_tokens": 5824,
  "session_cost": 0.0009
}
```

## 🛠️ Troubleshooting Workflows

### Which Log File to Check?
| Issue | Primary Log | Secondary Logs |
|-------|-------------|----------------|
| Bot not responding | `orchestrator.log` | `errors.log` |
| Tool execution errors | `salesforce.log` | `errors.log` |
| Agent offline/timeout | `a2a_protocol.log` | `system.log` |
| Memory not persisting | `storage.log` | `orchestrator.log` |
| Startup issues | `system.log` | `errors.log` |
| Any unknown error | `errors.log` first! | Then component logs |

### "Bot Not Responding"
1. Check `orchestrator.log`: `"user_input_raw"` - Find last user input
2. Check `orchestrator.log`: `"llm_invocation_start"` - Did AI start processing?
3. Check `errors.log`: Any errors after that timestamp?
4. Check `a2a_protocol.log`: `"timeout"` - Did agent call timeout?

### "Wrong Agent Response"  
1. Check `orchestrator.log`: `"tool_call"` - Which tool was selected?
2. Check `salesforce.log`: Tool execution details
3. Check `a2a_protocol.log`: `"a2a_task_complete"` - What came back?
4. Check `orchestrator.log`: `"user_message_displayed"` - What user saw?

### "Memory Not Working"
1. Check `storage.log`: `"memory_load_start"` - Loading attempt?
2. Check `storage.log`: `"sqlite_get"` with `"found": false` - Missing data?
3. Check `orchestrator.log`: `"memory_extraction"` - Extraction attempts?
4. Check `storage.log`: `"memory_put"` - Save attempts?

## 🎨 Visual Log Flow Patterns

### Startup Sequence
```
agent_SYSTEM_START
├─> config_loaded
├─> sqlite_init
├─> health_check_all_start
│   ├─> health_check_start (salesforce-agent)
│   │   └─> health_check_success ✅
│   └─> health_check_start (jira-agent)
│       └─> health_check_failed ❌
└─> orchestrator_session_start
```

### Request Processing
```
user_input_raw
├─> orchestrator_state_entry
├─> memory_load_start
├─> llm_invocation_start
├─> tool_call
├─> a2a_dispatch
│   ├─> a2a_task_start
│   ├─> a2a_request_start
│   ├─> a2a_response_received
│   └─> a2a_task_complete
├─> llm_generation_complete
└─> user_message_displayed
```

## 💡 Pro Tips

1. **Use Timestamps** - They're sortable, use them to trace flows
2. **Follow IDs** - `task_id`, `operation_id`, `thread_id` link events
3. **Check Components** - `"component": "a2a"` vs `"orchestrator"` tells you where issues are
4. **Watch Status Transitions** - `"previous_status"` → `"new_status"` shows changes
5. **Count Occurrences** - Multiple `"retry_attempt_failed"` = persistent issue

## 🔍 Additional Log Patterns

### Debugging Specific Issues
```bash
# TrustCall/Extraction Issues
"trustcall_extraction_start"         # Structured data extraction begins
"records_extracted"                  # What was found
"memory_extraction_debug"            # Debug info for extraction
"memory_extraction_structured_data_found"  # Found structured data

# Thread State Management
"state_save"                         # Saving thread state
"state_load"                         # Loading thread state
"thread_list"                        # Managing thread list

# Readonly Database Errors (usually non-critical)
"attempt to write a readonly database"  # Thread list update issue
"database_delete_"                   # Database operations

# Summary Processing
"summary_format_error"               # Summary parsing failed
"llm_generation_complete"            # AI response ready (check operation field)
```

## 🔧 Advanced Filtering

### Using grep/ripgrep with Multi-File Logs
```bash
# Find all errors across all components
rg '"level": "ERROR"' logs/*.log | tail -50
# OR just check the errors.log file directly!
tail -50 logs/errors.log

# Track specific user session across components
rg '"thread_id": "orchestrator-39283fe3"' logs/*.log | sort

# Find slow operations in A2A calls
rg '"elapsed_seconds": [3-9]\.' logs/a2a_protocol.log

# Check tool execution issues  
rg '"tool_error"' logs/salesforce.log

# Agent communication issues (now in dedicated file)
rg '"message": "a2a_network_error|retry_attempt_failed"' logs/a2a_protocol.log

# Memory/storage issues
rg '"sqlite_error"' logs/storage.log
```

### Using jq for JSON Processing
```bash
# Extract error summary from all errors
jq 'select(.level == "ERROR") | {time: .timestamp, error: .error, type: .error_type}' logs/errors.log

# Show request/response pairs in orchestrator
jq 'select(.message == "user_input_raw" or .message == "user_message_displayed")' logs/orchestrator.log

# Performance analysis of A2A calls
jq 'select(.elapsed_seconds != null and .elapsed_seconds > 2)' logs/a2a_protocol.log

# Tool execution summary
jq 'select(.message == "tool_call" or .message == "tool_result" or .message == "tool_error")' logs/salesforce.log

# Combine logs for full trace (example)
cat logs/orchestrator.log logs/a2a_protocol.log logs/salesforce.log | jq -s 'sort_by(.timestamp)' | jq '.[] | select(.task_id == "abc123")'
```

## 🚦 Quick Status Checks

### Green Flags ✅
- `"success": true`
- `"status_code": 200`
- `"found": true`
- `"new_status": "online"`

### Yellow Flags ⚠️
- `"retry_attempt_failed"`
- `"level": "WARNING"`
- `"found": false`
- `"elapsed_seconds": >5`

### Red Flags ❌
- `"level": "ERROR"`
- `"all_retry_attempts_failed"`
- `"resilient_call_failed"`
- `"AttributeError"`

Remember: Logs tell a story - follow the timestamps and IDs to understand the full narrative!