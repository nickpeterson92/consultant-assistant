"""Centralized activity logging for all multi-agent system components"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def log_activity(component: str, operation_type: str, **data: Any) -> None:
    """Universal activity logger for all system components
    
    Args:
        component: The component name (e.g., 'orchestrator', 'salesforce_agent', 'a2a_protocol')
        operation_type: The type of operation being logged
        **data: Additional data to include in the log entry
    """
    try:
        # Safely serialize data, handling Pydantic objects and other non-serializable types
        safe_data = {}
        for k, v in data.items():
            try:
                if hasattr(v, 'model_dump'):  # Pydantic object
                    safe_data[k] = v.model_dump()
                elif hasattr(v, '__dict__'):  # Other objects with attributes
                    safe_data[k] = str(v)
                else:
                    # Test if it's JSON serializable
                    json.dumps(v)
                    safe_data[k] = v
            except (TypeError, ValueError):
                # If not serializable, convert to string
                safe_data[k] = str(v)
        
        # Create log entry
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "operation_type": operation_type,
            **safe_data
        }
        
        # Determine log file path (project root logs directory)
        log_file = Path(__file__).parent.parent.parent.parent / "logs" / f"{component}.log"
        log_file.parent.mkdir(exist_ok=True)
        
        # Write to log file
        with open(log_file, 'a') as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {component} - INFO - {json.dumps(log_entry)}\n")
            f.flush()
            
    except Exception:
        # Silent fallback - logging should never crash the system
        pass


# Convenience functions for each component
def log_orchestrator_activity(operation_type: str, **data: Any) -> None:
    """Log orchestrator-specific activity"""
    log_activity("orchestrator", operation_type, **data)


def log_salesforce_activity(operation_type: str, **data: Any) -> None:
    """Log Salesforce agent activity"""
    log_activity("salesforce_agent", operation_type, **data)


def log_a2a_activity(operation_type: str, **data: Any) -> None:
    """Log A2A protocol activity"""
    log_activity("a2a_protocol", operation_type, **data)


def log_tool_activity(tool_name: str, operation: str, **data: Any) -> None:
    """Log tool usage activity"""
    log_activity("tools", operation, tool=tool_name, **data)


def log_cost_activity(operation: str, tokens_used: int, model: str = None, **data: Any) -> None:
    """Log cost tracking activity using global configuration"""
    from ..config import get_llm_config
    
    # Get pricing from global config
    llm_config = get_llm_config()
    model_name = model or llm_config.model
    pricing = llm_config.get_pricing(model_name)
    
    # Use average cost for simplicity (could be enhanced to track input/output separately)
    cost_per_1k = pricing.average_per_1k
    estimated_cost = f"${(tokens_used * cost_per_1k / 1000):.4f}"
    
    log_activity("cost_tracking", "LLM_USAGE", 
                operation=operation,
                model=model_name,
                tokens_used=tokens_used,
                estimated_cost=estimated_cost,
                **data)


def log_performance_activity(operation_type: str, **data: Any) -> None:
    """Log performance tracking activity"""
    log_activity("performance", operation_type, **data)


def log_multi_agent_activity(event_type: str, **data: Any) -> None:
    """Log multi-agent system events"""
    log_activity("multi_agent", event_type, event=event_type, **data)