"""Examples showing the new logging framework in action.

These examples demonstrate how the advanced logging framework dramatically
reduces code clutter while maintaining extensive logging detail.
"""

from typing import Dict, Any, List
from src.utils.logging import logger, log_execution, log_operation, LoggedTool, LoggedAgent


# ============================================================================
# EXAMPLE 1: Simple Auto-Detection (Most Common Use Case)
# ============================================================================

# OLD WAY - Manual logging everywhere:
# logger = get_logger("salesforce")
# def search_accounts_old(query: str):
#     logger.info("search_accounts_start", operation="search", query=query)
#     try:
#         result = sf.query(query)
#         logger.info("search_accounts_complete", operation="search", 
#                    result_count=len(result), success=True)
#         return result
#     except Exception as e:
#         logger.error("search_accounts_error", operation="search", 
#                     error=str(e), success=False)
#         raise

# NEW WAY - Zero clutter, same detail:
@log_execution()  # Auto-detects component from module path
def search_accounts(query: str):
    """Search Salesforce accounts - logging is automatic!"""
    return sf.query(query)  # Just business logic!


# ============================================================================
# EXAMPLE 2: Scoped Operations with Context
# ============================================================================

def extract_plan_old(request: str):
    """Old way with manual correlation and logging."""
    correlation_id = str(uuid.uuid4())
    logger.info("plan_extraction_start", correlation_id=correlation_id, request=request)
    try:
        # Multiple operations inside, each needs manual logging
        prompt = build_prompt(request)
        logger.info("prompt_built", correlation_id=correlation_id, prompt_length=len(prompt))
        
        result = extractor.invoke(prompt)
        logger.info("extraction_complete", correlation_id=correlation_id, success=True)
        return result
    except Exception as e:
        logger.error("plan_extraction_error", correlation_id=correlation_id, error=str(e))
        raise

def extract_plan_new(request: str):
    """New way - automatic correlation and context."""
    with log_operation("extraction", "plan_extraction", request=request):
        # Everything inside gets automatic correlation ID and context!
        prompt = build_prompt(request)
        logger.info("prompt_built", prompt_length=len(prompt))  # Auto-gets correlation_id!
        
        result = extractor.invoke(prompt)
        return result  # Success/failure logged automatically


# ============================================================================
# EXAMPLE 3: Tool Classes with Automatic Logging
# ============================================================================

# OLD WAY - Manual logging in every tool:
# class SalesforceSearchToolOld(BaseTool):
#     def __init__(self):
#         self.logger = get_logger("salesforce")
#     
#     def _run(self, query: str) -> str:
#         tool_id = str(uuid.uuid4())
#         self.logger.info("tool_start", tool="search", tool_id=tool_id, query=query)
#         try:
#             result = self.search(query)
#             self.logger.info("tool_complete", tool="search", tool_id=tool_id, 
#                            result_count=len(result), success=True)
#             return result
#         except Exception as e:
#             self.logger.error("tool_error", tool="search", tool_id=tool_id,
#                             error=str(e), success=False)
#             raise

# NEW WAY - Automatic logging via base class:
class SalesforceSearchTool(LoggedTool):
    def __init__(self):
        super().__init__("salesforce_search", "salesforce")  # Auto-logs everything!
    
    def _execute(self, query: str) -> str:
        """Just business logic - entry/exit/errors logged automatically!"""
        return self.search(query)
    
    def search(self, query: str) -> List[Dict]:
        # Even internal methods can use simple event emission
        self.emit_event("query_executed", query=query, query_type="SOQL")
        return sf.query(query)


# ============================================================================
# EXAMPLE 4: Agent Classes with Automatic Logging  
# ============================================================================

class SalesforceAgent(LoggedAgent):
    def __init__(self):
        super().__init__("salesforce-agent", "salesforce")
    
    def _process(self, instruction: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process Salesforce request - automatic logging!"""
        # Emit structured events easily
        self.emit_event("task_received", instruction_preview=instruction[:100])
        
        # Business logic without clutter
        plan = self.create_plan(instruction)
        result = self.execute_plan(plan)
        
        # Events get auto-correlation and routing
        self.emit_event("task_completed", plan_steps=len(plan.tasks))
        
        return result


# ============================================================================
# EXAMPLE 5: Complex Operations with Nested Context
# ============================================================================

def complex_workflow():
    """Shows how context and correlation flow through nested operations."""
    
    with log_operation("orchestrator", "deal_risk_assessment") as correlation_id:
        logger.info("workflow_started", workflow_type="deal_risk")
        
        # This operation inherits the correlation ID automatically
        with log_operation("salesforce", "find_at_risk_deals", parent_correlation=correlation_id):
            deals = find_at_risk_opportunities()  # Auto-logged with correlation
            logger.info("deals_found", count=len(deals))  # Gets correlation automatically
        
        # This too
        with log_operation("jira", "create_action_items"):
            for deal in deals:
                create_jira_ticket(deal)  # Each gets correlation + context
                logger.info("ticket_created", deal_id=deal.id)  # Auto-correlation!
        
        logger.info("workflow_completed", total_deals=len(deals))


# ============================================================================
# EXAMPLE 6: Before/After Comparison - Trustcall Extraction
# ============================================================================

# BEFORE - Manual logging everywhere:
def extract_plan_manual():
    logger.info("trustcall_plan_extraction_start", component="extraction",
               operation="initial_planning", request_preview=request[:100])
    
    extracted_plans = await plan_extractor.ainvoke({"messages": prompt})
    
    logger.info("trustcall_plan_extraction_complete", component="extraction",
               operation="initial_planning", has_result=bool(extracted_plans))
    
    if not extracted_plans:
        logger.error("trustcall_plan_extraction_failed", component="extraction",
                    operation="initial_planning", error="No plan extracted")
        raise ValueError("No plan extracted")

# AFTER - Clean and simple:
@log_execution("extraction", "plan_extraction")
def extract_plan_clean(prompt):
    """Extract structured plan - logging automatic!"""
    extracted_plans = await plan_extractor.ainvoke({"messages": prompt})
    
    if not extracted_plans:
        logger.error("no_plan_extracted")  # Auto-gets component, operation, correlation
        raise ValueError("No plan extracted")
    
    return extracted_plans


# ============================================================================
# EXAMPLE 7: Event-Driven Logging
# ============================================================================

def demonstrate_events():
    """Shows rich event emission without clutter."""
    
    # Simple events
    logger.info("user_request_received", user_id="123", request_type="search")
    
    # Events with data
    logger.info("search_completed", 
               query="opportunities", 
               result_count=42, 
               duration_ms=250)
    
    # Tool-specific events
    tool = SalesforceSearchTool()
    tool.emit_event("cache_hit", query_hash="abc123", cache_age_seconds=30)


# ============================================================================
# LOGS PRODUCED (All automatic!)
# ============================================================================

"""
The framework automatically produces detailed logs like:

salesforce.log:
{
  "timestamp": "2025-01-17T10:30:45Z",
  "level": "INFO", 
  "message": "function_start_search_accounts",
  "component": "salesforce",
  "operation": "search_accounts",
  "function": "search_accounts", 
  "execution_id": "a1b2c3d4",
  "args": ["opportunity"],
  "correlation_id": "xyz789"
}

{
  "timestamp": "2025-01-17T10:30:45Z",
  "level": "INFO",
  "message": "function_complete_search_accounts", 
  "component": "salesforce",
  "operation": "search_accounts",
  "execution_id": "a1b2c3d4",
  "duration_seconds": 0.245,
  "success": true,
  "result_preview": "{'records': [{'Id': '001...', 'Name': 'ACME'}...]}"
}

extraction.log:
{
  "timestamp": "2025-01-17T10:30:45Z",
  "level": "INFO",
  "message": "operation_start_plan_extraction",
  "component": "extraction", 
  "operation": "plan_extraction",
  "correlation_id": "abc123",
  "request": "find at-risk opportunities"
}
"""