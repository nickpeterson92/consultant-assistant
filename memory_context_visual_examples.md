# Enhanced Memory Context Examples

This document shows how the enhanced memory features create different contexts for execution, planning, and replanning.

## Key Differences Between Context Types

### 1. **Execution Context** (Task-Specific)
- Focuses on **highly relevant** recent memories
- Includes **detailed content** for high-relevance items
- Shows **important memories** that are frequently referenced
- Provides **caution alerts** based on past corrections
- Adds **similar past task** outcomes

### 2. **Planning Context** (Broad Overview)
- Starts with **conversation summary** using PageRank
- Emphasizes **important memories** (most connected nodes)
- Notes **topic clusters** ("Conversation involves 3 topics")
- Shows **bridge memories** that connect topics
- More abstract, less detail-heavy

### 3. **Replanning Context** (Recent + Critical)
- Focuses on **very recent context** with more details
- Includes **critical connections** between topics
- Shows more **content details** to inform adjustments
- Shorter timeframe (1 hour vs 4 hours for planning)

## Visual Examples

### Example 1: EXECUTION CONTEXT
```
Task: "Update the GenePoint opportunity to Closed Won"

CONVERSATION CONTEXT:
- User requests to close GenePoint opportunity         [Relevance: 0.95]
  Details: "Please update the Q4 opportunity for GenePoint to Closed Won status"
- Found GenePoint Q4 opportunity - $450k               [Relevance: 0.88]  
  Details: {'id': 'OPP-123', 'name': 'GenePoint Q4 Expansion', 'amount': 450000}
- Retrieved GenePoint account - Biotech leader         [Relevance: 0.72]
  Details: {'id': '001ABC', 'revenue': '$5M', 'industry': 'Biotechnology'}

IMPORTANT CONTEXT (frequently referenced):
- GenePoint account entity (referenced 7 times today)
- Q4 expansion opportunity (referenced 3 times)

CONNECTING CONTEXT (links different topics):
- Previous opportunity update for GenePoint succeeded last week

CAUTION:
- User previously corrected: Wrong opportunity ID used for GenePoint
  Correction: "Use the Q4 opportunity, not Q3"

SIMILAR PAST TASKS:
- Updated Edge Communications opportunity (2 hours ago) - successful
- Updated Burlington opportunity (yesterday) - required approval first

GUIDANCE: The user has been working with GenePoint all morning. When they say "the opportunity" they mean the Q4 one.
```

### Example 2: PLANNING CONTEXT
```
User Request: "Create a report on all our biotech accounts"

CONVERSATION SUMMARY:
User Requests:
- Analyzed GenePoint account and opportunities
- Reviewed Edge Communications partnerships  
- Updated multiple opportunity stages

Actions Taken:
- Retrieved 5 biotech accounts worth $15M total
- Found 12 active opportunities
- Updated 3 opportunities to new stages

Conversation covers 3 distinct topics.

RELEVANT CONTEXT:
- GenePoint account - Biotech leader, $5M revenue (IMPORTANT - PageRank: 0.8)
- Burlington Textiles - Biotech division, $3M revenue (IMPORTANT - PageRank: 0.6)
- Edge Communications - Biotech partnerships (PageRank: 0.4)
- Found 5 biotech accounts in western region
- Previous biotech analysis showed 23% growth

NOTE: Conversation involves 3 distinct topic areas.
Key connections between topics:
- GenePoint links biotech analysis to opportunity updates
- Regional analysis connects all biotech accounts
```

### Example 3: REPLANNING CONTEXT
```
Current situation: Executing plan step 3 of 5, need to adjust based on findings

RECENT CONTEXT:
- Just discovered GenePoint has a new subsidiary      [10 minutes ago]
  Details: {'name': 'GenePoint Labs', 'focus': 'R&D', 'location': 'Boston'}
- User asked to include subsidiaries in analysis      [8 minutes ago]
  Details: "Make sure to include any subsidiary data in the report"
- Retrieved 3 GenePoint opportunities successfully    [5 minutes ago]
  Details: {'total': 3, 'value': '$850k', 'stages': ['Negotiation', 'Qualification', 'Prospecting']}
- Error: Subsidiary API requires different auth       [3 minutes ago]
  Details: {'error': 'Auth failed for subsidiary endpoint'}

CRITICAL CONNECTIONS:
- GenePoint Labs connects to main GenePoint analysis (bridge node)

Current plan progress:
✓ Step 1: Get biotech accounts - Complete
✓ Step 2: Retrieve opportunities - Complete  
⚡ Step 3: Analyze account relationships - In Progress (discovered subsidiaries)
- Step 4: Generate visualizations
- Step 5: Create final report
```

## How Features Enhance Each Context

### PageRank Contribution
- **Execution**: Identifies "frequently referenced" entities to avoid ambiguity
- **Planning**: Determines which memories become part of the summary
- **Replanning**: Less emphasized, focus is on recency

### Clustering Contribution
- **Execution**: Not directly shown, but influences which memories are retrieved
- **Planning**: Explicitly noted ("Conversation covers 3 distinct topics")
- **Replanning**: Helps identify when plan needs major vs minor adjustments

### Bridge Detection Contribution
- **Execution**: Shows as "CONNECTING CONTEXT" when topics link
- **Planning**: Listed as "Key connections between topics"
- **Replanning**: Shows as "CRITICAL CONNECTIONS" for decision making

### Memory Analyzer Contribution
- **Execution**: Provides CAUTION alerts and similar past tasks
- **Planning**: Generates the conversation summary
- **Replanning**: Identifies patterns that might require plan changes

## Benefits of Enhanced Context

1. **Reduces Ambiguity**: Important entities are highlighted, preventing confusion
2. **Learns from Mistakes**: Caution alerts prevent repeating errors
3. **Maintains Continuity**: Bridge memories connect disparate topics
4. **Adapts to Patterns**: Recognizes user preferences and habits
5. **Provides Right Detail Level**: More detail for execution, more overview for planning