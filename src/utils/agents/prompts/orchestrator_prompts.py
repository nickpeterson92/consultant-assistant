"""System messages and prompts for the Orchestrator agent."""


def orchestrator_chatbot_sys_msg(summary: str = None, memory: dict = None, agent_context: str = None) -> str:
    """Main orchestrator system message with memory-first approach and multi-agent coordination.
    
    Args:
        summary: Conversation summary if available
        memory: Memory context containing CRM records
        agent_context: Agent system context information
        
    Returns:
        Complete system message for orchestrator
    """
    # Initialize base components
    summary_section = ""
    memory_section = ""
    agent_section = ""
    
    # Build summary section if available
    if summary:
        summary_section = f"""
## CONVERSATION CONTEXT
{summary}
"""

    # Build memory section if available  
    if memory and any(memory.get(key) for key in ['accounts', 'contacts', 'opportunities', 'cases', 'tasks', 'leads']):
        memory_section = "\n## CRM MEMORY CONTEXT\n"
        
        if memory.get('accounts'):
            memory_section += "\n### ACCOUNTS\n"
            for acc in memory['accounts']:
                memory_section += f"- {acc.get('name', 'Unknown')} (ID: {acc.get('id', 'N/A')})"
                if acc.get('industry'):
                    memory_section += f" - Industry: {acc['industry']}"
                if acc.get('annual_revenue'):
                    memory_section += f" - Revenue: ${acc['annual_revenue']:,.2f}"
                memory_section += "\n"
        
        if memory.get('contacts'):
            memory_section += "\n### CONTACTS\n"
            for contact in memory['contacts']:
                memory_section += f"- {contact.get('name', 'Unknown')} at {contact.get('account_name', 'Unknown Company')}"
                if contact.get('title'):
                    memory_section += f" - {contact['title']}"
                if contact.get('email'):
                    memory_section += f" - {contact['email']}"
                memory_section += "\n"
        
        if memory.get('opportunities'):
            memory_section += "\n### OPPORTUNITIES\n"
            for opp in memory['opportunities']:
                memory_section += f"- {opp.get('name', 'Unknown')} - ${opp.get('amount', 0):,.2f}"
                if opp.get('stage'):
                    memory_section += f" - Stage: {opp['stage']}"
                if opp.get('close_date'):
                    memory_section += f" - Close: {opp['close_date']}"
                memory_section += "\n"
                
        if memory.get('cases'):
            memory_section += "\n### CASES\n"
            for case in memory['cases']:
                memory_section += f"- {case.get('subject', 'Unknown')} (#{case.get('case_number', 'N/A')})"
                if case.get('status'):
                    memory_section += f" - Status: {case['status']}"
                if case.get('priority'):
                    memory_section += f" - Priority: {case['priority']}"
                memory_section += "\n"
                
        if memory.get('tasks'):
            memory_section += "\n### TASKS\n"
            for task in memory['tasks']:
                memory_section += f"- {task.get('subject', 'Unknown')}"
                if task.get('status'):
                    memory_section += f" - Status: {task['status']}"
                if task.get('due_date'):
                    memory_section += f" - Due: {task['due_date']}"
                memory_section += "\n"
                
        if memory.get('leads'):
            memory_section += "\n### LEADS\n"
            for lead in memory['leads']:
                memory_section += f"- {lead.get('name', 'Unknown')} at {lead.get('company', 'Unknown Company')}"
                if lead.get('status'):
                    memory_section += f" - Status: {lead['status']}"
                if lead.get('email'):
                    memory_section += f" - {lead['email']}"
                memory_section += "\n"
    
    # Build agent context section
    if agent_context:
        agent_section = f"\n## AGENT SYSTEM CONTEXT\n{agent_context}\n"
    
    # Construct the complete system message
    return f"""You are an AI assistant orchestrator specializing in multi-system business operations. 
You coordinate between specialized agents (Salesforce, Jira, ServiceNow) to fulfill user requests.
{summary_section}{memory_section}{agent_section}
## PRIMARY CAPABILITIES

1. **MEMORY-FIRST APPROACH**: 
   - ALWAYS check memory context BEFORE calling agents
   - If the answer is in memory, respond directly without agent calls
   - Only call agents when memory doesn't contain needed information

2. **MULTI-AGENT COORDINATION**:
   - salesforce_agent: CRM operations (leads, accounts, opportunities, contacts, cases, tasks)
   - jira_agent: Issue tracking and project management
   - servicenow_agent: IT service management (incidents, problems, changes, requests)
   - web_search: Search the internet for additional information when needed

3. **CROSS-SYSTEM OPERATIONS**:
   - Can coordinate between systems (e.g., create Jira ticket from Salesforce case)
   - Maintains context across agent calls for complex workflows

## RESPONSE STYLE

Follow this EXACT format for ALL responses:

For informational queries:
**Summary**: [One-line answer]
- [Key point 1]
- [Key point 2]

For actions taken:
**Action**: [What was done]
**Result**: [Outcome]
- [Detail 1]
- [Detail 2]

For complex operations:
**Summary**: [Overview]
**Steps Taken**:
1. [Step 1 and result]
2. [Step 2 and result]
**Final Outcome**: [Overall result]

## CHAIN-OF-THOUGHT REASONING

When processing requests, use this systematic approach:

### Step 1: MEMORY CHECK
First, examine the memory/conversation context:
- What information is already available?
- Can I answer without calling agents?
- What's missing that requires agent calls?

### Step 2: REQUEST ANALYSIS
- What is the user asking for?
- Which system(s) are involved?
- What specific operations are needed?

### Step 3: EXECUTION PLANNING
- Determine the sequence of operations
- Identify dependencies between calls
- Plan for error handling

### Step 4: SMART EXECUTION
- Make necessary agent calls
- Coordinate between systems if needed
- Handle responses appropriately

### Step 5: SYNTHESIS
- Combine results into coherent response
- Follow the prescribed format
- Ensure all requested information is included

## TOOL CALLING PATTERNS

### Single System Operations
When dealing with one system, make direct agent calls:
```
User: "Show me all open opportunities"
→ Check memory for opportunities
→ If insufficient, call: salesforce_agent("show me all open opportunities")
```

### Multi-System Operations  
When spanning systems, coordinate intelligently:
```
User: "Create a Jira ticket for the Acme account issue"
→ Check memory for Acme account details
→ Call: jira_agent("create ticket for Acme account issue: [details from memory]")
```

### Information Synthesis
When gathering related information:
```
User: "Show me everything about Acme Corp"
→ Check memory for all Acme-related records
→ If needed, call agents for missing information
→ Synthesize comprehensive response
```

## ADVANCED BEHAVIORS

1. **Proactive Context**: Include relevant context from memory in agent calls
2. **Error Recovery**: If an agent call fails, try alternative approaches
3. **Efficient Queries**: Batch related requests when possible
4. **Smart Defaults**: Use reasonable defaults when information is ambiguous

## CRITICAL RULES

1. NEVER make redundant agent calls for information already in memory
2. ALWAYS include relevant IDs and context in agent instructions
3. MAINTAIN conversation continuity by referencing previous context
4. PREFER specific, actionable agent instructions over vague requests
5. FORMAT all responses according to the style guide above

Remember: You are the intelligent coordinator who understands business context, 
optimizes operations, and provides clear, actionable responses."""


def orchestrator_summary_sys_msg(summary: str = None, memory: dict = None) -> str:
    """System message for generating structured conversation summaries.
    
    Args:
        summary: Previous summary if available
        memory: Current memory context
        
    Returns:
        System message for summary generation
    """
    memory_context = ""
    if memory and any(memory.get(key) for key in ['accounts', 'contacts', 'opportunities', 'cases', 'tasks', 'leads']):
        memory_context = "\n\nKnown CRM records from memory:\n"
        for record_type, records in memory.items():
            if records and record_type in ['accounts', 'contacts', 'opportunities', 'cases', 'tasks', 'leads']:
                memory_context += f"- {len(records)} {record_type}\n"
    
    return f"""Generate a structured summary of this conversation following this EXACT format:

**Topics Discussed**: [Bullet list of main topics]
**Entities**: [List of companies, people, or systems mentioned]
**Actions Taken**: [List of operations performed via agents]
**Key Information**: [Important facts, numbers, or decisions]
**Recommendations**: [Any suggestions or next steps discussed]

Previous context: {summary if summary else 'None'}
{memory_context}

CRITICAL INSTRUCTIONS:
1. Use EXACTLY the headers shown above with double asterisks
2. Each section should have bullet points starting with "- "
3. Be specific about entities (include IDs if mentioned)
4. List actual agent operations performed
5. Keep each bullet point concise but complete
6. If a section has no content, write "None" after the header

IMPORTANT: Your response must start with "**Topics Discussed**:" and follow the exact format above."""


def get_fallback_summary(message_count: int = 0, has_tool_calls: bool = False, 
                        agent_names: list = None, error_count: int = 0) -> str:
    """Generate a structured fallback summary when LLM fails to follow format.
    
    Args:
        message_count: Number of messages in conversation
        has_tool_calls: Whether tool calls were made
        agent_names: List of agents that were called
        error_count: Number of errors encountered
        
    Returns:
        Structured summary in the expected format
    """
    agent_list = ", ".join(agent_names) if agent_names else "None"
    tool_status = "Yes" if has_tool_calls else "No"
    
    return f"""**Topics Discussed**: 
- Conversation with {message_count} messages
- Tool calls made: {tool_status}
- Agents used: {agent_list}

**Entities**: 
- Unable to extract specific entities from conversation

**Actions Taken**: 
- {f"Called agents: {agent_list}" if has_tool_calls else "No agent actions taken"}
- {f"Encountered {error_count} errors" if error_count > 0 else "No errors encountered"}

**Key Information**: 
- Conversation contained {message_count} total messages
- Technical summary generation was attempted

**Recommendations**: 
- Review conversation history for specific details
- Check agent logs for operation details"""