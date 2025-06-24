"""
Memory Extraction Debug Logger

Provides detailed logging for the memory extraction process to help debug
why SimpleMemory might not be populated with Salesforce data.
"""

import logging
import json
import time
from typing import Any, Dict, List, Optional

class MemoryExtractionLogger:
    """Dedicated logger for memory extraction debugging"""
    
    def __init__(self):
        # Use centralized logging configuration
        from .logging_config import get_logger
        self.logger = get_logger('memory_extraction')
    
    def log_extraction_start(self, message_count: int, user_id: str, thread_id: str = None):
        """Log the start of memory extraction process"""
        log_data = {
            "timestamp": time.time(),
            "operation": "EXTRACTION_START",
            "message_count": message_count,
            "user_id": user_id,
            "thread_id": thread_id
        }
        self.logger.info(log_data["operation"], **log_data)
    
    def log_message_scan(self, msg_type: str, msg_name: str, has_content: bool, 
                        content_preview: str = None, has_structured_data: bool = False):
        """Log scanning of individual messages"""
        log_data = {
            "timestamp": time.time(),
            "operation": "MESSAGE_SCAN",
            "message_type": msg_type,
            "message_name": msg_name,
            "has_content": has_content,
            "content_preview": content_preview[:100] if content_preview else None,
            "has_structured_data": has_structured_data
        }
        self.logger.debug(log_data["operation"], **log_data)
    
    def log_structured_data_found(self, tool_name: str, data_preview: str, 
                                 data_size: int, record_count: int = 0):
        """Log when structured data is found"""
        log_data = {
            "timestamp": time.time(),
            "operation": "STRUCTURED_DATA_FOUND",
            "tool_name": tool_name,
            "data_preview": data_preview[:200] if data_preview else None,
            "data_size": data_size,
            "record_count": record_count
        }
        self.logger.info(log_data["operation"], **log_data)
    
    def log_trustcall_extraction(self, input_size: int, extraction_prompt: str = None,
                                success: bool = True, error: str = None):
        """Log TrustCall extraction attempt"""
        log_data = {
            "timestamp": time.time(),
            "operation": "TRUSTCALL_EXTRACTION",
            "input_size": input_size,
            "extraction_prompt_preview": extraction_prompt[:200] if extraction_prompt else None,
            "success": success,
            "error": error
        }
        self.logger.info(log_data["operation"], **log_data)
    
    def log_records_extracted(self, record_type: str, count: int, 
                            sample_ids: List[str] = None):
        """Log extracted records by type"""
        log_data = {
            "timestamp": time.time(),
            "operation": "RECORDS_EXTRACTED",
            "record_type": record_type,
            "count": count,
            "sample_ids": sample_ids[:5] if sample_ids else []
        }
        self.logger.info(log_data["operation"], **log_data)
    
    def log_deduplication(self, record_type: str, before_count: int, 
                         after_count: int, duplicates_removed: int):
        """Log deduplication results"""
        log_data = {
            "timestamp": time.time(),
            "operation": "DEDUPLICATION",
            "record_type": record_type,
            "before_count": before_count,
            "after_count": after_count,
            "duplicates_removed": duplicates_removed
        }
        self.logger.debug(log_data["operation"], **log_data)
    
    def log_memory_update(self, user_id: str, memory_before: Dict[str, List], 
                         memory_after: Dict[str, List], changes: Dict[str, int]):
        """Log memory update results"""
        log_data = {
            "timestamp": time.time(),
            "operation": "MEMORY_UPDATE",
            "user_id": user_id,
            "before_counts": {k: len(v) for k, v in memory_before.items()},
            "after_counts": {k: len(v) for k, v in memory_after.items()},
            "changes": changes
        }
        self.logger.info(log_data["operation"], **log_data)
    
    def log_extraction_complete(self, user_id: str, duration: float, 
                              total_extracted: int, success: bool = True):
        """Log completion of extraction process"""
        log_data = {
            "timestamp": time.time(),
            "operation": "EXTRACTION_COMPLETE",
            "user_id": user_id,
            "duration_seconds": duration,
            "total_records_extracted": total_extracted,
            "success": success
        }
        self.logger.info(log_data["operation"], **log_data)
    
    def log_error(self, operation: str, error: str, context: Dict[str, Any] = None):
        """Log extraction errors"""
        log_data = {
            "timestamp": time.time(),
            "operation": "EXTRACTION_ERROR",
            "error_operation": operation,
            "error_message": str(error),
            "context": context
        }
        self.logger.error(log_data["operation"], **log_data)

# Global logger instance
_extraction_logger = None

def get_memory_extraction_logger() -> MemoryExtractionLogger:
    """Get the global memory extraction logger instance"""
    global _extraction_logger
    if _extraction_logger is None:
        _extraction_logger = MemoryExtractionLogger()
    return _extraction_logger