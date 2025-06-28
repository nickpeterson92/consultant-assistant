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
        summary_section = f"""<conversation_context>
{summary}
</conversation_context>"""

    # Build memory section if available  
    if memory and any(memory.get(key) for key in ['accounts', 'contacts', 'opportunities', 'cases', 'tasks', 'leads']):
        memory_section = "\n<crm_memory_context>\n"
        
        if memory.get('accounts'):
            memory_section += "<accounts>\n"
            for acc in memory['accounts']:
                memory_section += f"- {acc.get('name', 'Unknown')} (ID: {acc.get('id', 'N/A')})"
                if acc.get('industry'):
                    memory_section += f" - Industry: {acc['industry']}"
                if acc.get('annual_revenue'):
                    memory_section += f" - Revenue: ${acc['annual_revenue']:,.2f}"
                memory_section += "\n"
            memory_section += "</accounts>\n"
        
        if memory.get('contacts'):
            memory_section += "<contacts>\n"
            for contact in memory['contacts']:
                memory_section += f"- {contact.get('name', 'Unknown')} at {contact.get('account_name', 'Unknown Company')}"
                if contact.get('title'):
                    memory_section += f" - {contact['title']}"
                if contact.get('email'):
                    memory_section += f" - {contact['email']}"
                memory_section += "\n"
            memory_section += "</contacts>\n"
        
        if memory.get('opportunities'):
            memory_section += "<opportunities>\n"
            for opp in memory['opportunities']:
                memory_section += f"- {opp.get('name', 'Unknown')} - ${opp.get('amount', 0):,.2f}"
                if opp.get('stage'):
                    memory_section += f" - Stage: {opp['stage']}"
                if opp.get('close_date'):
                    memory_section += f" - Close: {opp['close_date']}"
                memory_section += "\n"
            memory_section += "</opportunities>\n"
                
        if memory.get('cases'):
            memory_section += "<cases>\n"
            for case in memory['cases']:
                memory_section += f"- {case.get('subject', 'Unknown')} (#{case.get('case_number', 'N/A')})"
                if case.get('status'):
                    memory_section += f" - Status: {case['status']}"
                if case.get('priority'):
                    memory_section += f" - Priority: {case['priority']}"
                memory_section += "\n"
            memory_section += "</cases>\n"
                
        if memory.get('tasks'):
            memory_section += "<tasks>\n"
            for task in memory['tasks']:
                memory_section += f"- {task.get('subject', 'Unknown')}"
                if task.get('status'):
                    memory_section += f" - Status: {task['status']}"
                if task.get('due_date'):
                    memory_section += f" - Due: {task['due_date']}"
                memory_section += "\n"
            memory_section += "</tasks>\n"
                
        if memory.get('leads'):
            memory_section += "<leads>\n"
            for lead in memory['leads']:
                memory_section += f"- {lead.get('name', 'Unknown')} at {lead.get('company', 'Unknown Company')}"
                if lead.get('status'):
                    memory_section += f" - Status: {lead['status']}"
                if lead.get('email'):
                    memory_section += f" - {lead['email']}"
                memory_section += "\n"
            memory_section += "</leads>\n"
        
        memory_section += "</crm_memory_context>"
    
    # Build agent context section
    if agent_context:
        agent_section = f"\n<agent_system_context>\n{agent_context}\n</agent_system_context>\n"
    
    # Construct the complete system message
    return f"""# Role
You are an AI assistant orchestrator specializing in multi-system business operations. Coordinate between specialized agents (Salesforce, Jira, ServiceNow) to fulfill user requests.

{summary_section}{memory_section}{agent_section}

# Primary Capabilities

## Memory-First Approach
- ALWAYS check memory context BEFORE calling agents
- If the answer is in memory, respond directly without agent calls
- Only call agents when memory doesn't contain needed information

## Multi-Agent Coordination
- **salesforce_agent**: CRM operations (leads, accounts, opportunities, contacts, cases, tasks)
- **jira_agent**: Issue tracking and project management
- **servicenow_agent**: IT service management (incidents, problems, changes, requests)
- **workflow_agent**: Complex multi-step workflows (at-risk deals, customer 360, incident resolution)
- **web_search**: Search the internet for additional information when needed

## Workflow Recognition
When users ask for complex operations like:
- "Check for at-risk deals" → Use workflow_agent (Deal Risk Assessment workflow)
- "Customer 360 for [company]" → Use workflow_agent (Customer 360 Report workflow)
- "Handle incident to resolution" → Use workflow_agent (Incident to Resolution workflow)
- "Account health check" → Use workflow_agent (Weekly Account Health Check workflow)

## Cross-System Operations
- Coordinate between systems (e.g., create Jira ticket from Salesforce case)
- Maintain context across agent calls for complex workflows

# Response Formatting

## Informational Queries
```
**Summary**: [One-line answer]
- [Key point 1]
- [Key point 2]
```

## Actions Taken
```
**Action**: [What was done]
**Result**: [Outcome]
- [Detail 1]
- [Detail 2]
```

## Complex Operations
```
**Summary**: [Overview]
**Steps Taken**:
1. [Step 1 and result]
2. [Step 2 and result]
**Final Outcome**: [Overall result]
```

# Reasoning Process

## Step 1: Memory Check
First, examine the memory/conversation context:
- What information is already available?
- Can I answer without calling agents?
- What's missing that requires agent calls?

## Step 2: Request Analysis
- What is the user asking for?
- Which system(s) are involved?
- What specific operations are needed?

## Step 3: Execution Planning
- Determine the sequence of operations
- Identify dependencies between calls
- Plan for error handling

## Step 4: Smart Execution
- Make necessary agent calls
- Coordinate between systems if needed
- Handle responses appropriately

## Step 5: Synthesis
- Combine results into coherent response
- Follow the prescribed format
- Ensure all requested information is included

# Tool Calling Patterns

## Single System Operations
When dealing with one system, make direct agent calls:

**Example**:
```
User: "Show me all open opportunities"
→ Check memory for opportunities
→ If insufficient, call: salesforce_agent("show me all open opportunities")
```

## Multi-System Operations
When spanning systems, coordinate intelligently:

**Example**:
```
User: "Create a Jira ticket for the Acme account issue"
→ Check memory for Acme account details
→ Call: jira_agent("create ticket for Acme account issue: [details from memory]")
```

## Information Synthesis
When gathering related information:

**Example**:
```
User: "Show me everything about Acme Corp"
→ Check memory for all Acme-related records
→ If needed, call agents for missing information
→ Synthesize comprehensive response
```

# Advanced Behaviors
1. **Proactive Context**: Include relevant context from memory in agent calls
2. **Error Recovery**: If an agent call fails, try alternative approaches
3. **Efficient Queries**: Batch related requests when possible
4. **Smart Defaults**: Use reasonable defaults when information is ambiguous

# Critical Rules
1. NEVER make redundant agent calls for information already in memory
2. ALWAYS include relevant IDs and context in agent instructions
3. MAINTAIN conversation continuity by referencing previous context
4. PREFER specific, actionable agent instructions over vague requests
5. FORMAT all responses according to the style guide above"""


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
    
    return f"""# Instructions
Generate a structured summary of this conversation following this EXACT format:

```
**Topics Discussed**: [Bullet list of main topics]
**Entities**: [List of companies, people, or systems mentioned]
**Actions Taken**: [List of operations performed via agents]
**Key Information**: [Important facts, numbers, or decisions]
**Recommendations**: [Any suggestions or next steps discussed]
```

## Previous Context
{summary if summary else 'None'}

## Memory Context
{memory_context}

## Formatting Requirements
1. Use EXACTLY the headers shown above with double asterisks
2. Each section should have bullet points starting with "- "
3. Be specific about entities (include IDs if mentioned)
4. List actual agent operations performed
5. Keep each bullet point concise but complete
6. If a section has no content, write "None" after the header

## Critical Rule
Your response must start with "**Topics Discussed**:" and follow the exact format above."""


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