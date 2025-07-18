"""Web search tool using Tavily API for entity enrichment.

This module implements an advanced web search tool following 2024-2025
best practices for agentic RAG systems:
- Context-aware query enhancement
- Multi-source retrieval with validation
- Adaptive search depth
- Source attribution and transparency
"""

import os
from typing import Any, Dict, Optional, List, Type, Union
from pydantic import BaseModel, Field
from langgraph.prebuilt import InjectedState
from typing import Annotated

from .base import BaseUtilityTool
from src.utils.logging.framework import SmartLogger

# Import Tavily after checking for package
try:
    from langchain_tavily import TavilySearch  # type: ignore[import-untyped]
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False
    TavilySearch = None

logger = SmartLogger("utility")


class WebSearchInput(BaseModel):
    """Input schema for web search operations."""
    query: str = Field(
        description="Search query or entity to research. Can be a company name, person, topic, or question."
    )
    context_enhance: bool = Field(
        default=True,
        description="Whether to enhance the query with conversation context"
    )
    max_results: int = Field(
        default=5,
        description="Maximum number of results to return (1-10)"
    )
    search_depth: str = Field(
        default="basic",
        description="Search depth: 'basic' for quick results or 'advanced' for comprehensive research"
    )
    include_domains: Optional[List[str]] = Field(
        default=None,
        description="List of domains to prioritize in search results"
    )
    exclude_domains: Optional[List[str]] = Field(
        default=None,
        description="List of domains to exclude from search results"
    )
    time_range: Optional[str] = Field(
        default=None,
        description="Time filter for results: 'day', 'week', 'month', or 'year'"
    )


class WebSearchTool(BaseUtilityTool):
    """Advanced web search tool for enriching entity information.
    
    Uses Tavily API to perform context-aware web searches with features like:
    - Automatic query enhancement based on conversation context
    - Entity extraction from recent tool results
    - Domain filtering and time-based search
    - Structured output with source attribution
    
    The tool intelligently enhances queries based on recent Salesforce,
    Jira, or ServiceNow results to provide more relevant information.
    """
    
    name: str = "web_search"
    description: str = """Search the web for information about entities, companies, people, or topics.
    
    CAPABILITIES:
    - Research companies, people, products, or any topic
    - Get latest news and updates about entities
    - Find background information and context
    - Retrieve recent developments and announcements
    
    INTELLIGENT FEATURES:
    - Automatically enhances queries with context from recent CRM/ticket data
    - Extracts entities from previous tool results for better search
    - Filters results by domain or time period
    - Provides source attribution for all information
    
    USAGE EXAMPLES:
    - "Find more information about [company] online"
    - "What's the latest news about [entity]"
    - "Search for [person]'s background"
    - After retrieving a record: "Tell me more about this company"
    
    Returns structured results with titles, snippets, URLs, and relevance scores."""
    
    args_schema: Type[BaseModel] = WebSearchInput  # pyright: ignore[reportIncompatibleVariableOverride]
    
    def __init__(self):
        super().__init__()
        
        if not TAVILY_AVAILABLE:
            logger.warning("langchain-tavily package not installed. Install with: pip install langchain-tavily",
                                tool_name="web_search",
                operation="tavily_not_installed"
            )
        
        # Initialize Tavily search client as None (will be created on demand)
        # We don't store api_key as an attribute due to Pydantic restrictions
    
    def _enhance_query_with_context(self, query: str, state: Optional[Dict[str, Any]]) -> str:
        """Enhance the search query with context from conversation state.
        
        Extracts entities and context from recent messages and tool results
        to create a more targeted search query.
        """
        if not state:
            return query
        
        # Extract entities from recent tool results
        entities = self._extract_entities_from_state(state)
        
        # Get recent context
        context = self._extract_context_from_messages(state, count=3)
        
        # Build enhanced query
        enhanced_parts = [query]
        
        # Add entity context if query seems generic
        query_lower = query.lower()
        if entities and len(query_lower.split()) < 5:
            # Check if entities are already in query
            entities_to_add = [e for e in entities[:2] if e.lower() not in query_lower]
            if entities_to_add:
                enhanced_parts.append(f"related to {' and '.join(entities_to_add)}")
        
        # Add temporal context if not present
        if "latest" not in query_lower and "recent" not in query_lower and "news" not in query_lower:
            if any(word in query_lower for word in ["information", "details", "about"]):
                enhanced_parts.append("latest updates")
        
        enhanced_query = " ".join(enhanced_parts)
        
        if enhanced_query != query:
            logger.info("Query enhanced with context",
                                tool_name="web_search",
                operation="query_enhanced",
                original_query=query,
                enhanced_query=enhanced_query,
                entities_found=len(entities)
            )
        
        return enhanced_query
    
    def _format_search_results(self, raw_results: Dict[str, Any]) -> Dict[str, Any]:
        """Format raw Tavily results into structured output."""
        # Tavily returns a dict with 'results' key containing the list
        results_list = raw_results.get("results", [])
        
        formatted_results = {
            "query": raw_results.get("query", ""),
            "results": [],
            "sources": []
        }
        
        for idx, result in enumerate(results_list):
            formatted_result = {
                "title": result.get("title", ""),
                "snippet": result.get("content", ""),
                "url": result.get("url", ""),
                "relevance_score": result.get("score", 0.0),
                "published_date": result.get("published_date"),
                "rank": idx + 1
            }
            
            formatted_results["results"].append(formatted_result)
            formatted_results["sources"].append({
                "title": result.get("title", ""),
                "url": result.get("url", "")
            })
        
        # Add summary if available
        if raw_results.get("answer"):
            formatted_results["summary"] = raw_results["answer"]
        
        return formatted_results
    
    def _build_search_params(self, **kwargs) -> Dict[str, Any]:
        """Build parameters for Tavily search based on input."""
        params = {
            "search_depth": kwargs.get("search_depth", "basic"),
            "max_results": min(kwargs.get("max_results", 5), 10),  # Cap at 10
        }
        
        # Add domain filters if provided
        if kwargs.get("include_domains"):
            params["include_domains"] = kwargs.get("include_domains")
        
        if kwargs.get("exclude_domains"):
            params["exclude_domains"] = kwargs.get("exclude_domains")
        
        # Add time filter
        time_range = kwargs.get("time_range")
        if time_range:
            # Tavily uses different parameter names
            time_map = {
                "day": "d",
                "week": "w",
                "month": "m",
                "year": "y"
            }
            if time_range in time_map:
                params["days"] = time_map[time_range]
        
        return params
    
    def _execute(self, **kwargs) -> Any:
        """Execute the web search operation."""
        query = kwargs.get('query', '')
        context_enhance = kwargs.get('context_enhance', True)
        max_results = kwargs.get('max_results', 5)
        search_depth = kwargs.get('search_depth', "basic")
        include_domains = kwargs.get('include_domains', None)
        exclude_domains = kwargs.get('exclude_domains', None)
        time_range = kwargs.get('time_range', None)
        state = kwargs.get('state', None)
        
        # Check if Tavily is available
        if not TAVILY_AVAILABLE:
            return {
                "error": "Web search unavailable",
                "error_code": "TAVILY_NOT_INSTALLED",
                "guidance": {
                    "reflection": "The Tavily search package is not installed.",
                    "consider": "Do you need web search functionality?",
                    "approach": "Install langchain-tavily package: pip install langchain-tavily"
                }
            }
        
        # Get API key from environment
        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            logger.warning("TAVILY_API_KEY environment variable not set",
                                tool_name="web_search",
                operation="tavily_api_key_missing"
            )
            return {
                "error": "API key missing",
                "error_code": "MISSING_API_KEY",
                "guidance": {
                    "reflection": "TAVILY_API_KEY environment variable is not set.",
                    "consider": "Do you have a Tavily API account?",
                    "approach": "Set TAVILY_API_KEY environment variable with your API key."
                }
            }
        
        # Enhance query if requested
        search_query = query
        if context_enhance and state:
            search_query = self._enhance_query_with_context(query, state)
        
        # Build search parameters
        search_params = self._build_search_params(
            search_depth=search_depth,
            max_results=max_results,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
            time_range=time_range
        )
        
        logger.info("Web search request",
                        tool_name="web_search",
            operation="web_search_request",
            query=search_query,
            original_query=query if query != search_query else None,
            params=search_params
        )
        
        try:
            # Create a new search instance with updated parameters
            if TavilySearch is None:
                return {
                    "error": "TavilySearch not available",
                    "error_code": "TAVILY_NOT_AVAILABLE"
                }
            
            tavily_search = TavilySearch(
                api_key=api_key,
                search_depth=search_params["search_depth"],
                max_results=search_params["max_results"],
                include_domains=search_params.get("include_domains"),
                exclude_domains=search_params.get("exclude_domains")
            )
            
            # Execute search
            raw_results = tavily_search.invoke(search_query)
            
            if not raw_results:
                return {
                    "query": search_query,
                    "results": [],
                    "sources": [],
                    "message": "No results found for the search query."
                }
            
            # Format results
            formatted_results = self._format_search_results(raw_results)
            formatted_results["enhanced_query"] = search_query if query != search_query else None
            
            logger.info("Web search completed successfully",
                                tool_name="web_search",
                operation="web_search_success",
                query=search_query,
                result_count=len(formatted_results["results"]),
                has_summary="summary" in formatted_results
            )
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Web search failed: {str(e)}",
                                tool_name="web_search",
                operation="web_search_error",
                query=search_query,
                error=str(e),
                error_type=type(e).__name__
            )
            raise  # Let base class handle error formatting