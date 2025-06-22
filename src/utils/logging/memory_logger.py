"""
Memory and Summary Logging System
Provides detailed tracking of all memory operations and summary generation
"""

import logging
import json
import time
from typing import Any, Dict, Optional, Tuple
from pathlib import Path

# Create logs directory if it doesn't exist
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

class MemoryLogger:
    """Dedicated logger for memory operations"""
    
    def __init__(self, log_file: str = "logs/memory.log"):
        self.logger = logging.getLogger("memory_operations")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False  # Prevent propagation to root logger
        
        # Remove existing handlers to avoid duplicates
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
        
        # Create file handler
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        # Only add console handler in debug mode (no console logging by default)
        # console_handler = logging.StreamHandler()
        # console_handler.setFormatter(formatter)
        # console_handler.setLevel(logging.WARNING)  # Only warnings and errors to console
        # self.logger.addHandler(console_handler)
    
    def log_memory_operation(self, operation: str, namespace: Tuple[str, ...], key: str,
                           value_in: Any = None, value_out: Any = None, 
                           user_id: str = "unknown", component: str = "unknown",
                           success: bool = True, error: str = None):
        """Log a memory storage operation"""
        
        # Skip cache operations to reduce noise
        if namespace and len(namespace) > 0 and namespace[0] == "llm_cache":
            return
        log_data = {
            "timestamp": time.time(),
            "operation": operation,  # GET, PUT, DELETE
            "namespace": namespace,
            "key": key,
            "user_id": user_id,
            "component": component,
            "success": success
        }
        
        if value_in is not None:
            log_data["value_in"] = self._serialize_value(value_in, namespace)
            log_data["value_in_size"] = len(str(value_in)) if value_in else 0
        
        if value_out is not None:
            log_data["value_out"] = self._serialize_value(value_out, namespace)
            log_data["value_out_size"] = len(str(value_out)) if value_out else 0
        
        if error:
            log_data["error"] = str(error)
        
        self.logger.info(json.dumps(log_data))
    
    def log_memory_get(self, namespace: Tuple[str, ...], key: str, result: Any,
                      user_id: str = "unknown", component: str = "unknown"):
        """Log a memory GET operation"""
        self.log_memory_operation("GET", namespace, key, value_out=result,
                                user_id=user_id, component=component)
    
    def log_memory_put(self, namespace: Tuple[str, ...], key: str, value: Any,
                      user_id: str = "unknown", component: str = "unknown"):
        """Log a memory PUT operation"""
        self.log_memory_operation("PUT", namespace, key, value_in=value,
                                user_id=user_id, component=component)
    
    def log_memory_delete(self, namespace: Tuple[str, ...], key: str,
                         user_id: str = "unknown", component: str = "unknown"):
        """Log a memory DELETE operation"""
        self.log_memory_operation("DELETE", namespace, key,
                                user_id=user_id, component=component)
    
    def _serialize_value(self, value: Any, namespace: Tuple[str, ...] = None) -> Dict[str, Any]:
        """Serialize value for logging while preserving type information"""
        if value is None:
            return {"type": "null", "value": None}
        
        value_type = type(value).__name__
        
        # Handle different types appropriately
        if isinstance(value, (str, int, float, bool)):
            return {"type": value_type, "value": value}
        elif isinstance(value, dict):
            # For memory operations, show full content to aid debugging
            if namespace and len(namespace) > 0 and namespace[0] == "memory":
                return {"type": value_type, "value": value}  # Full content for memory
            
            # For other dicts, log structure but truncate large values
            truncated_dict = {}
            for k, v in value.items():
                if isinstance(v, str) and len(v) > 200:
                    truncated_dict[k] = f"{v[:197]}..."
                elif isinstance(v, (list, dict)) and len(str(v)) > 200:
                    truncated_dict[k] = f"<{type(v).__name__} with {len(v) if hasattr(v, '__len__') else '?'} items>"
                else:
                    truncated_dict[k] = v
            return {"type": value_type, "value": truncated_dict}
        elif isinstance(value, list):
            return {"type": value_type, "length": len(value), "preview": value[:3] if len(value) > 3 else value}
        else:
            return {"type": value_type, "string_repr": str(value)[:200]}

class SummaryLogger:
    """Dedicated logger for summary operations"""
    
    def __init__(self, log_file: str = "logs/summary.log"):
        self.logger = logging.getLogger("summary_operations")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False  # Prevent propagation to root logger
        
        # Remove existing handlers to avoid duplicates
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
        
        # Create file handler
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        # Only add console handler in debug mode (no console logging by default)
        # console_handler = logging.StreamHandler()
        # console_handler.setFormatter(formatter)
        # console_handler.setLevel(logging.WARNING)  # Only warnings and errors to console
        # self.logger.addHandler(console_handler)
    
    def log_summary_request(self, messages_count: int, current_summary: str,
                           memory_context: Any, component: str = "unknown",
                           user_id: str = "unknown", turn: int = 0):
        """Log a summary generation request"""
        log_data = {
            "timestamp": time.time(),
            "operation": "SUMMARY_REQUEST",
            "component": component,
            "user_id": user_id,
            "turn": turn,
            "messages_count": messages_count,
            "current_summary_length": len(current_summary) if current_summary else 0,
            "current_summary_preview": (current_summary[:200] + "...") if current_summary and len(current_summary) > 200 else current_summary,
            "memory_context_type": type(memory_context).__name__,
            "memory_context_size": len(str(memory_context)) if memory_context else 0
        }
        
        self.logger.info(json.dumps(log_data))
    
    def log_summary_response(self, new_summary: str, messages_preserved: int,
                           messages_deleted: int, component: str = "unknown",
                           user_id: str = "unknown", turn: int = 0,
                           processing_time: float = 0):
        """Log a summary generation response"""
        log_data = {
            "timestamp": time.time(),
            "operation": "SUMMARY_RESPONSE",
            "component": component,
            "user_id": user_id,
            "turn": turn,
            "new_summary_length": len(new_summary) if new_summary else 0,
            "new_summary_preview": (new_summary[:800] + "...") if new_summary and len(new_summary) > 800 else new_summary,
            "messages_preserved": messages_preserved,
            "messages_deleted": messages_deleted,
            "processing_time_seconds": processing_time
        }
        
        self.logger.info(json.dumps(log_data))
    
    def log_summary_error(self, error: str, component: str = "unknown",
                         user_id: str = "unknown", turn: int = 0):
        """Log a summary generation error"""
        log_data = {
            "timestamp": time.time(),
            "operation": "SUMMARY_ERROR",
            "component": component,
            "user_id": user_id,
            "turn": turn,
            "error": str(error)
        }
        
        self.logger.error(json.dumps(log_data))

# Global logger instances
_memory_logger = None
_summary_logger = None

def get_memory_logger() -> MemoryLogger:
    """Get the global memory logger instance"""
    global _memory_logger
    if _memory_logger is None:
        _memory_logger = MemoryLogger()
    return _memory_logger

def get_summary_logger() -> SummaryLogger:
    """Get the global summary logger instance"""
    global _summary_logger
    if _summary_logger is None:
        _summary_logger = SummaryLogger()
    return _summary_logger

# Convenience functions for easy import
def log_memory_get(namespace: Tuple[str, ...], key: str, result: Any,
                  user_id: str = "unknown", component: str = "unknown"):
    """Convenience function to log memory GET operations"""
    get_memory_logger().log_memory_get(namespace, key, result, user_id, component)

def log_memory_put(namespace: Tuple[str, ...], key: str, value: Any,
                  user_id: str = "unknown", component: str = "unknown"):
    """Convenience function to log memory PUT operations"""
    get_memory_logger().log_memory_put(namespace, key, value, user_id, component)

def log_summary_request(messages_count: int, current_summary: str,
                       memory_context: Any, component: str = "unknown",
                       user_id: str = "unknown", turn: int = 0):
    """Convenience function to log summary requests"""
    get_summary_logger().log_summary_request(messages_count, current_summary, 
                                            memory_context, component, user_id, turn)

def log_summary_response(new_summary: str, messages_preserved: int,
                        messages_deleted: int, component: str = "unknown",
                        user_id: str = "unknown", turn: int = 0,
                        processing_time: float = 0):
    """Convenience function to log summary responses"""
    get_summary_logger().log_summary_response(new_summary, messages_preserved,
                                             messages_deleted, component, user_id, 
                                             turn, processing_time)