"""Smart schema knowledge system using semantic embeddings for intelligent lookup.

This module uses embeddings to match user intent with relevant schemas,
providing only the schemas needed for the current task.
"""

import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import numpy as np

from src.memory.algorithms.semantic_embeddings import SemanticEmbeddings
from src.utils.logging.framework import SmartLogger

logger = SmartLogger("schema_knowledge")


@dataclass
class SchemaEntry:
    """A schema entry with embedded search vectors."""
    system: str
    object_type: str
    schema: Dict[str, Any]
    search_phrases: List[str]  # Phrases that should match this schema
    embedding_vectors: Optional[List[np.ndarray]] = None


class SemanticSchemaKnowledge:
    """Smart schema lookup using semantic embeddings."""
    
    def __init__(self):
        self.embeddings = SemanticEmbeddings()
        self.schema_entries: List[SchemaEntry] = []
        self._initialize_schemas()
        
    def _initialize_schemas(self):
        """Initialize schema database with embeddings."""
        
        # Define schemas with search phrases
        schemas = [
            # ===== SERVICENOW SCHEMAS =====
            SchemaEntry(
                system="servicenow",
                object_type="core_company",
                schema={
                    "table": "core_company",
                    "note": "⚠️ Companies use 'core_company' table, NOT 'company' or 'account'!",
                    "required": ["name"],
                    "fields": {
                        "name": "Company name (required)",
                        "stock_symbol": "Stock ticker symbol", 
                        "website": "Company website URL",
                        "phone": "Main phone number",
                        "street": "Street address",
                        "city": "City",
                        "state": "State/Province"
                    }
                },
                search_phrases=[
                    "create company in servicenow",
                    "add customer account to servicenow",
                    "servicenow company record",
                    "new vendor in servicenow",
                    "servicenow customer account",
                    "create a company for the customer"
                ]
            ),
            SchemaEntry(
                system="servicenow",
                object_type="sys_user",
                schema={
                    "table": "sys_user",
                    "required": ["user_name"],
                    "fields": {
                        "user_name": "Username (required, unique)",
                        "first_name": "First name",
                        "last_name": "Last name",
                        "email": "Email address",
                        "title": "Job title",
                        "department": "Department reference",
                        "manager": "Manager's sys_id",
                        "company": "Company sys_id (from core_company)",
                        "active": "true/false"
                    }
                },
                search_phrases=[
                    "create user in servicenow",
                    "add employee to servicenow",
                    "new user account servicenow",
                    "servicenow user fields"
                ]
            ),
            SchemaEntry(
                system="servicenow",
                object_type="change_request",
                schema={
                    "table": "change_request",
                    "required": ["short_description"],
                    "fields": {
                        "short_description": "Brief description (required)",
                        "description": "Detailed description",
                        "type": "Valid: 'Normal', 'Standard', 'Emergency'",
                        "priority": "1 (Critical) to 4 (Low)",
                        "risk": "Valid: 'High', 'Moderate', 'Low', 'None'",
                        "impact": "1 (High) to 3 (Low)",
                        "assignment_group": "Group sys_id",
                        "assigned_to": "User sys_id"
                    }
                },
                search_phrases=[
                    "create change request",
                    "new change in servicenow",
                    "servicenow change management",
                    "submit change request"
                ]
            ),
            SchemaEntry(
                system="servicenow",
                object_type="problem",
                schema={
                    "table": "problem",
                    "required": ["short_description"],
                    "fields": {
                        "short_description": "Brief description (required)",
                        "description": "Root cause analysis",
                        "priority": "1 (Critical) to 5 (Planning)",
                        "known_error": "true/false",
                        "workaround": "Temporary fix description",
                        "cause_notes": "Root cause details"
                    }
                },
                search_phrases=[
                    "create problem record",
                    "log problem in servicenow",
                    "problem management",
                    "root cause analysis"
                ]
            ),
            
            # ===== SALESFORCE SCHEMAS =====
            SchemaEntry(
                system="salesforce",
                object_type="Account",
                schema={
                    "required": ["Name"],
                    "fields": {
                        "Name": "Account name (required)",
                        "Type": "Valid: 'Prospect', 'Customer - Direct', 'Customer - Channel', 'Partner', 'Other'",
                        "Industry": "Industry vertical",
                        "Website": "Company website",
                        "Phone": "Main phone",
                        "BillingStreet": "Billing address street",
                        "BillingCity": "Billing city",
                        "BillingState": "Billing state/province",
                        "BillingPostalCode": "Billing zip/postal code",
                        "BillingCountry": "Billing country",
                        "AnnualRevenue": "Annual revenue (number)",
                        "NumberOfEmployees": "Employee count (number)"
                    }
                },
                search_phrases=[
                    "create account in salesforce",
                    "new customer in salesforce",
                    "add company to salesforce",
                    "salesforce account fields",
                    "create prospect"
                ]
            ),
            SchemaEntry(
                system="salesforce",
                object_type="Contact",
                schema={
                    "required": ["LastName"],
                    "fields": {
                        "FirstName": "First name",
                        "LastName": "Last name (required)",
                        "Email": "Email address",
                        "Phone": "Phone number",
                        "Title": "Job title",
                        "AccountId": "Related Account ID",
                        "Department": "Department name",
                        "MailingStreet": "Mailing street",
                        "MailingCity": "Mailing city",
                        "MailingState": "Mailing state",
                        "MailingPostalCode": "Mailing zip",
                        "MailingCountry": "Mailing country"
                    }
                },
                search_phrases=[
                    "create contact in salesforce",
                    "add person to salesforce",
                    "new contact for account",
                    "salesforce contact fields"
                ]
            ),
            SchemaEntry(
                system="salesforce",
                object_type="Lead",
                schema={
                    "required": ["LastName", "Company"],
                    "fields": {
                        "FirstName": "First name",
                        "LastName": "Last name (required)",
                        "Company": "Company name (required)",
                        "Email": "Email address",
                        "Phone": "Phone number",
                        "Title": "Job title",
                        "Status": "Valid: 'Open - Not Contacted', 'Working - Contacted', 'Closed - Converted', 'Closed - Not Converted'",
                        "Rating": "Valid: 'Hot', 'Warm', 'Cold'",
                        "Industry": "Industry vertical",
                        "LeadSource": "Lead origin"
                    }
                },
                search_phrases=[
                    "create lead in salesforce",
                    "new lead",
                    "add prospect lead",
                    "salesforce lead fields"
                ]
            ),
            SchemaEntry(
                system="salesforce", 
                object_type="Opportunity",
                schema={
                    "fields": {
                        "StageName": "Status (NOT 'Stage'!). Values: 'Prospecting', 'Qualification', 'Needs Analysis', 'Value Proposition', 'Id. Decision Makers', 'Perception Analysis', 'Proposal/Price Quote', 'Negotiation/Review', 'Closed Won', 'Closed Lost'",
                        "Amount": "Deal value (number)",
                        "CloseDate": "Expected close date (YYYY-MM-DD)",
                        "AccountId": "Related Account ID",
                        "Name": "Opportunity name"
                    }
                },
                search_phrases=[
                    "update opportunity stage",
                    "change opportunity status", 
                    "close the deal",
                    "mark opportunity as won",
                    "update sales pipeline",
                    "opportunity fields",
                    "change deal stage"
                ]
            ),
            SchemaEntry(
                system="salesforce",
                object_type="Case", 
                schema={
                    "required": ["Subject"],
                    "fields": {
                        "Subject": "Case title (required)",
                        "Type": "Valid: 'Mechanical', 'Electrical', 'Electronic', 'Structural', 'Other'",
                        "Priority": "Valid: 'High', 'Medium', 'Low'",
                        "Status": "Valid: 'New', 'Working', 'Escalated', 'Closed'",
                        "AccountId": "ID of related Account",
                        "Description": "Case details"
                    }
                },
                search_phrases=[
                    "create support case",
                    "open a ticket in salesforce",
                    "new case for customer",
                    "create case in salesforce",
                    "support ticket fields"
                ]
            ),
            SchemaEntry(
                system="servicenow",
                object_type="incident",
                schema={
                    "table": "incident",
                    "required": ["short_description"],
                    "fields": {
                        "short_description": "Brief description (required)",
                        "description": "Detailed description",
                        "priority": "1 (Critical) to 5 (Planning)", 
                        "urgency": "1 (High), 2 (Medium), 3 (Low)",
                        "impact": "1 (High), 2 (Medium), 3 (Low)",
                        "category": "Incident category",
                        "subcategory": "Incident subcategory"
                    }
                },
                search_phrases=[
                    "create incident in servicenow",
                    "report an issue",
                    "log incident",
                    "servicenow incident fields",
                    "new incident ticket"
                ]
            ),
            SchemaEntry(
                system="salesforce",
                object_type="Task",
                schema={
                    "required": ["Subject"],
                    "fields": {
                        "Subject": "Task subject (required)",
                        "Status": "Valid: 'Not Started', 'In Progress', 'Completed', 'Waiting on someone else', 'Deferred'",
                        "Priority": "Valid: 'High', 'Normal', 'Low'",
                        "ActivityDate": "Due date (YYYY-MM-DD)",
                        "WhoId": "Contact or Lead ID",
                        "WhatId": "Related to (Account/Opportunity/etc ID)",
                        "Description": "Task details"
                    }
                },
                search_phrases=[
                    "create task in salesforce",
                    "new activity",
                    "add follow up task",
                    "salesforce task fields"
                ]
            ),
            
            # ===== JIRA SCHEMAS =====
            SchemaEntry(
                system="jira",
                object_type="issue",
                schema={
                    "note": "⚠️ Assignee requires account ID (not username)! Get with JiraGetResource first.",
                    "required": ["summary", "project", "issuetype"],
                    "fields": {
                        "summary": "Issue title (required)",
                        "description": "Detailed description", 
                        "assignee": {"accountId": "User account ID (NOT username!)"},
                        "priority": {"name": "Valid: 'Highest', 'High', 'Medium', 'Low', 'Lowest'"},
                        "issuetype": {"name": "Type like 'Bug', 'Task', 'Story'"},
                        "project": {"key": "Project key like 'PROJ'"}
                    }
                },
                search_phrases=[
                    "create jira issue",
                    "new jira ticket",
                    "add task to jira",
                    "jira fields",
                    "assign jira issue",
                    "create bug in jira"
                ]
            ),
            SchemaEntry(
                system="jira",
                object_type="project",
                schema={
                    "required": ["key", "name", "projectTypeKey", "leadAccountId"],
                    "fields": {
                        "key": "Project key (required, uppercase, 2-10 chars)",
                        "name": "Project name (required)",
                        "description": "Project description",
                        "projectTypeKey": "Required: 'software' or 'business'",
                        "leadAccountId": "Project lead account ID (required)",
                        "url": "Project URL",
                        "assigneeType": "Valid: 'PROJECT_LEAD' or 'UNASSIGNED'"
                    }
                },
                search_phrases=[
                    "create jira project",
                    "new project in jira",
                    "jira project setup",
                    "project configuration"
                ]
            ),
            SchemaEntry(
                system="jira",
                object_type="sprint",
                schema={
                    "required": ["name", "boardId"],
                    "fields": {
                        "name": "Sprint name (required)",
                        "goal": "Sprint goal description",
                        "startDate": "Start date (ISO format)",
                        "endDate": "End date (ISO format)",
                        "boardId": "Board ID (required)",
                        "state": "Valid: 'active', 'closed', 'future'"
                    }
                },
                search_phrases=[
                    "create sprint",
                    "new sprint in jira",
                    "start sprint",
                    "sprint planning"
                ]
            ),
            SchemaEntry(
                system="jira",
                object_type="epic",
                schema={
                    "note": "Epics are special issue types with additional fields",
                    "required": ["summary", "project"],
                    "fields": {
                        "summary": "Epic name (required)",
                        "description": "Epic description",
                        "customfield_10011": "Epic name field (some instances)",
                        "project": {"key": "Project key (required)"},
                        "issuetype": {"name": "Epic"},
                        "labels": "Array of labels"
                    }
                },
                search_phrases=[
                    "create epic in jira",
                    "new epic",
                    "epic creation",
                    "jira epic fields"
                ]
            )
        ]
        
        # Generate embeddings for search phrases
        if self.embeddings.is_available():
            for entry in schemas:
                vectors = []
                for phrase in entry.search_phrases:
                    vec = self.embeddings.encode_text(phrase)
                    if vec is not None:
                        vectors.append(vec)
                entry.embedding_vectors = vectors
                
        self.schema_entries = schemas
        
        logger.info("schema_knowledge_initialized",
            total_schemas=len(schemas),
            embeddings_available=self.embeddings.is_available()
        )
    
    def find_relevant_schemas(self, query: str, threshold: float = 0.6) -> List[Tuple[SchemaEntry, float]]:
        """Find schemas relevant to the query using semantic search."""
        
        if not self.embeddings.is_available():
            # Fallback to keyword matching
            return self._keyword_fallback(query)
            
        # Encode the query
        query_embedding = self.embeddings.encode_text(query.lower())
        if query_embedding is None:
            return self._keyword_fallback(query)
            
        # Calculate similarities
        results = []
        for entry in self.schema_entries:
            if not entry.embedding_vectors:
                continue
                
            # Find best matching phrase
            max_similarity = 0.0
            for vec in entry.embedding_vectors:
                similarity = self.embeddings.calculate_similarity(query_embedding, vec)
                max_similarity = max(max_similarity, similarity)
                
            if max_similarity >= threshold:
                results.append((entry, max_similarity))
                
        # Sort by similarity
        results.sort(key=lambda x: x[1], reverse=True)
        
        logger.debug("semantic_schema_search",
            query=query[:100],
            found_count=len(results),
            top_match=results[0][0].object_type if results else None
        )
        
        return results
    
    def _keyword_fallback(self, query: str) -> List[Tuple[SchemaEntry, float]]:
        """Simple keyword matching fallback."""
        query_lower = query.lower()
        results = []
        
        for entry in self.schema_entries:
            # Check if system is mentioned
            if entry.system.lower() in query_lower:
                score = 0.8
            else:
                score = 0.3
                
            # Check for object type keywords
            if entry.object_type.lower() in query_lower:
                score += 0.2
                
            # Check search phrases
            for phrase in entry.search_phrases:
                if any(word in query_lower for word in phrase.split()):
                    score += 0.1
                    
            if score > 0.5:
                results.append((entry, min(score, 1.0)))
                
        results.sort(key=lambda x: x[1], reverse=True)
        return results
    
    def get_schema_context(self, query: str, max_schemas: int = 3) -> str:
        """Get formatted schema context for a query."""
        
        relevant = self.find_relevant_schemas(query)
        if not relevant:
            return ""
            
        # Take top matches
        relevant = relevant[:max_schemas]
        
        lines = ["\n## RELEVANT SCHEMA INFORMATION:"]
        
        for entry, score in relevant:
            lines.append(f"\n### {entry.system.upper()} - {entry.object_type}")
            
            schema = entry.schema
            if "note" in schema:
                lines.append(schema['note'])
                
            if "table" in schema:
                lines.append(f"Table: `{schema['table']}`")
                
            if "required" in schema:
                lines.append(f"Required fields: {', '.join(schema['required'])}")
                
            if "fields" in schema:
                lines.append("Fields:")
                for field, desc in schema["fields"].items():
                    lines.append(f"  • {field}: {desc}")
                    
        return "\n".join(lines)


# Global instance
_schema_knowledge = None

def get_schema_knowledge() -> SemanticSchemaKnowledge:
    """Get or create the global schema knowledge instance."""
    global _schema_knowledge
    if _schema_knowledge is None:
        _schema_knowledge = SemanticSchemaKnowledge()
    return _schema_knowledge