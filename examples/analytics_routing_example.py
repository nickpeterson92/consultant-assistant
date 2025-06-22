"""
Example: How the Orchestrator Routes Analytics Requests to Salesforce Agent

This demonstrates the multi-agent architecture where:
1. User asks orchestrator for analytics
2. Orchestrator recognizes it's a Salesforce analytics request
3. Orchestrator delegates to Salesforce agent via A2A protocol
4. Salesforce agent uses the new analytics tools
5. Results flow back to user
"""

# Example user requests that would trigger analytics tools:

analytics_requests = [
    # Pipeline Analysis
    "Show me our sales pipeline by stage",
    "What's our opportunity pipeline breakdown?",
    "Give me pipeline metrics grouped by sales rep",
    "Show monthly revenue trends for this year",
    
    # Top Performers
    "Who are our top 10 sales reps by revenue?",
    "Show me the best performing sales people",
    "Which reps have the highest win rates?",
    "List top performers by deal count",
    
    # Global Search
    "Find everything related to Acme Corp",
    "Search for john@example.com across all records",
    "Show me all records mentioning 'solar panel'",
    "Find anything about TechCorp in our CRM",
    
    # Account Insights
    "Give me a 360 view of the GenePoint account",
    "Show me everything about Acme including opportunities and contacts",
    "What's the complete picture for Express Logistics?",
    "Get comprehensive insights on our top account",
    
    # Business Metrics
    "What's our revenue this quarter?",
    "Show me lead conversion rates by source",
    "Give me case volume analysis by priority",
    "What are our key business metrics this month?"
]

# The orchestrator would handle these like:

"""
USER: Show me our sales pipeline by stage

ORCHESTRATOR (internal reasoning):
- This is asking for sales analytics
- Specifically pipeline analysis
- The salesforce_agent has 'pipeline_analysis' capability
- Route to salesforce_agent

ORCHESTRATOR → SALESFORCE AGENT (via A2A):
{
    "instruction": "Show me our sales pipeline by stage",
    "context": {
        "request_type": "analytics",
        "user_intent": "pipeline_analysis"
    }
}

SALESFORCE AGENT (internal reasoning):
- This matches the get_sales_pipeline tool
- Default group_by is "StageName" which is what user wants
- Execute the tool

SALESFORCE AGENT (executes):
GetSalesPipelineTool.run(group_by="StageName")

Which internally builds:
SELECT StageName, 
       COUNT(Id) OpportunityCount,
       SUM(Amount) TotalAmount,
       AVG(Amount) AvgAmount
FROM Opportunity
GROUP BY StageName
HAVING SUM(Amount) > 0
ORDER BY TotalAmount DESC

SALESFORCE AGENT → ORCHESTRATOR (response):
{
    "result": {
        "group_by": "StageName",
        "metrics": [
            {
                "StageName": "Negotiation/Review",
                "OpportunityCount": 45,
                "TotalAmount": 2500000,
                "AvgAmount": 55555.56
            },
            {
                "StageName": "Proposal/Price Quote", 
                "OpportunityCount": 32,
                "TotalAmount": 1800000,
                "AvgAmount": 56250
            },
            ...
        ]
    }
}

ORCHESTRATOR → USER:
Here's your sales pipeline breakdown by stage:

**Negotiation/Review**
- 45 opportunities
- Total value: $2,500,000
- Average deal size: $55,556

**Proposal/Price Quote**
- 32 opportunities  
- Total value: $1,800,000
- Average deal size: $56,250

[Additional stages...]
"""

# Another example with global search:

"""
USER: Find everything related to Acme Corp

ORCHESTRATOR → SALESFORCE AGENT:
{
    "instruction": "Find everything related to Acme Corp"
}

SALESFORCE AGENT (executes):
GlobalSearchTool.run(search_term="Acme Corp")

Which internally builds SOSL:
FIND {Acme Corp} IN ALL FIELDS
RETURNING 
    Account(Id, Name, Industry, Phone, Website LIMIT 20),
    Contact(Id, Name, Email, Phone, Title, Account.Name LIMIT 20),
    Opportunity(Id, Name, Amount, StageName, CloseDate, Account.Name 
               WHERE Amount > 0 ORDER BY Amount DESC LIMIT 20),
    Lead(Id, Name, Company, Email, Phone, Status 
         WHERE Status IN ('New', 'Working', 'Qualified') LIMIT 20)
LIMIT 80

Returns all matching records across objects, which orchestrator presents to user
"""

# The key points:
# 1. Orchestrator doesn't need to know HOW to build queries
# 2. It just recognizes the REQUEST TYPE and routes appropriately
# 3. Salesforce agent has the specialized knowledge (tools)
# 4. Clean separation of concerns in multi-agent architecture