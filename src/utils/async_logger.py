"""
Async Buffered Logging for Multi-Agent System
Provides high-performance, non-blocking logging with buffering and batch writes
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from collections import deque
import weakref
import atexit

logger = logging.getLogger(__name__)

@dataclass
class LogEntry:
    """Structured log entry"""
    timestamp: str
    component: str
    operation_type: str
    level: str
    data: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "component": self.component,
            "operation_type": self.operation_type,
            "level": self.level,
            **self.data
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(',', ':'))

class AsyncLogBuffer:
    """Async log buffer with automatic flushing"""
    
    def __init__(self, log_file: Path, buffer_size: int = 1000, 
                 flush_interval: float = 1.0, max_file_size: int = 10 * 1024 * 1024):
        self.log_file = log_file
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.max_file_size = max_file_size
        
        self._buffer: deque = deque()
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False
        self._last_flush = time.time()
        self._current_file_size = 0
        
        # Statistics
        self.entries_written = 0
        self.flushes_performed = 0
        self.bytes_written = 0
        
        # Ensure directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Check current file size
        if self.log_file.exists():
            self._current_file_size = self.log_file.stat().st_size
    
    async def start(self):
        """Start the async logging system"""
        if self._running:
            return
        
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_worker())
        logger.debug(f"Started async log buffer for {self.log_file}")
    
    async def stop(self):
        """Stop the async logging system and flush remaining entries"""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel the flush task
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        # Flush any remaining entries
        await self._flush_buffer()
        logger.debug(f"Stopped async log buffer for {self.log_file}")
    
    async def log(self, entry: LogEntry):
        """Add a log entry to the buffer"""
        if not self._running:
            await self.start()
        
        async with self._lock:
            self._buffer.append(entry)
            
            # Force flush if buffer is full
            if len(self._buffer) >= self.buffer_size:
                await self._flush_buffer_unsafe()
    
    async def _flush_worker(self):
        """Background worker that periodically flushes the buffer"""
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                
                # Check if we need to flush
                async with self._lock:
                    if (self._buffer and 
                        (time.time() - self._last_flush) >= self.flush_interval):
                        await self._flush_buffer_unsafe()
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in flush worker: {e}")
    
    async def _flush_buffer_unsafe(self):
        """Flush buffer without acquiring lock (unsafe - must be called with lock held)"""
        if not self._buffer:
            return
        
        try:
            # Check if we need to rotate the log file
            if self._current_file_size > self.max_file_size:
                await self._rotate_log_file()
            
            # Prepare entries for writing
            entries_to_write = list(self._buffer)
            self._buffer.clear()
            
            # Write entries to file
            content_lines = []
            for entry in entries_to_write:
                try:
                    line = f"{entry.timestamp} - {entry.component} - {entry.level} - {entry.to_json()}\n"
                    content_lines.append(line)
                except Exception as e:
                    logger.warning(f"Error serializing log entry: {e}")
                    # Fallback
                    fallback_line = f"{entry.timestamp} - {entry.component} - ERROR - Failed to serialize log entry: {e}\n"
                    content_lines.append(fallback_line)
            
            # Write all lines at once
            content = "".join(content_lines)
            
            # Use asyncio to write file without blocking
            await self._write_to_file(content)
            
            # Update statistics
            self.entries_written += len(entries_to_write)
            self.bytes_written += len(content.encode())
            self.flushes_performed += 1
            self._current_file_size += len(content.encode())
            self._last_flush = time.time()
            
        except Exception as e:
            logger.error(f"Error flushing log buffer to {self.log_file}: {e}")
            # Re-add entries to buffer to avoid losing them
            entries_to_write.reverse()
            for entry in entries_to_write:
                self._buffer.appendleft(entry)
    
    async def _flush_buffer(self):
        """Public method to flush buffer with lock"""
        async with self._lock:
            await self._flush_buffer_unsafe()
    
    async def _write_to_file(self, content: str):
        """Write content to file asynchronously"""
        loop = asyncio.get_event_loop()
        
        # Use thread pool for file I/O to avoid blocking
        def write_file():
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(content)
                f.flush()
        
        await loop.run_in_executor(None, write_file)
    
    async def _rotate_log_file(self):
        """Rotate log file when it gets too large"""
        try:
            backup_file = self.log_file.with_suffix(f".{int(time.time())}.log")
            
            # Use thread pool for file operations
            loop = asyncio.get_event_loop()
            
            def rotate():
                if self.log_file.exists():
                    self.log_file.rename(backup_file)
                    # Create new file
                    self.log_file.touch()
            
            await loop.run_in_executor(None, rotate)
            
            self._current_file_size = 0
            logger.info(f"Rotated log file: {self.log_file} -> {backup_file}")
            
        except Exception as e:
            logger.error(f"Error rotating log file {self.log_file}: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get buffer statistics"""
        return {
            "log_file": str(self.log_file),
            "buffer_size": len(self._buffer),
            "max_buffer_size": self.buffer_size,
            "entries_written": self.entries_written,
            "flushes_performed": self.flushes_performed,
            "bytes_written": self.bytes_written,
            "current_file_size": self._current_file_size,
            "max_file_size": self.max_file_size,
            "is_running": self._running
        }

class AsyncActivityLogger:
    """High-performance async activity logger for the multi-agent system"""
    
    def __init__(self, logs_dir: str = "logs", buffer_size: int = 1000, 
                 flush_interval: float = 1.0):
        self.logs_dir = Path(logs_dir)
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        
        # Create log buffers for different components
        self._buffers: Dict[str, AsyncLogBuffer] = {}
        self._lock = asyncio.Lock()
        
        # Register cleanup on exit
        atexit.register(self._cleanup_sync)
        
        # Weak references for cleanup
        self._refs = weakref.WeakSet()
    
    async def _get_buffer(self, component: str) -> AsyncLogBuffer:
        """Get or create a buffer for a component"""
        if component not in self._buffers:
            async with self._lock:
                if component not in self._buffers:
                    log_file = self.logs_dir / f"{component}.log"
                    buffer = AsyncLogBuffer(
                        log_file, 
                        self.buffer_size, 
                        self.flush_interval
                    )
                    self._buffers[component] = buffer
                    self._refs.add(buffer)
                    await buffer.start()
        
        return self._buffers[component]
    
    async def log_activity(self, component: str, operation_type: str, 
                          level: str = "INFO", **data: Any):
        """Log an activity asynchronously"""
        # Safely serialize data
        safe_data = {}
        for k, v in data.items():
            try:
                if hasattr(v, 'model_dump'):  # Pydantic object
                    safe_data[k] = v.model_dump()
                elif hasattr(v, '__dict__'):
                    safe_data[k] = str(v)
                else:
                    # Test if it's JSON serializable
                    json.dumps(v)
                    safe_data[k] = v
            except (TypeError, ValueError):
                safe_data[k] = str(v)
        
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            component=component,
            operation_type=operation_type,
            level=level,
            data=safe_data
        )
        
        try:
            buffer = await self._get_buffer(component)
            await buffer.log(entry)
        except Exception as e:
            # Fallback to standard logging
            logger.warning(f"Async logging failed for {component}: {e}")
            logger.log(getattr(logging, level, logging.INFO), 
                      f"{operation_type}: {safe_data}")
    
    async def flush_all(self):
        """Flush all buffers"""
        for buffer in self._buffers.values():
            try:
                await buffer._flush_buffer()
            except Exception as e:
                logger.error(f"Error flushing buffer: {e}")
    
    async def close_all(self):
        """Close all buffers and stop logging"""
        for component, buffer in self._buffers.items():
            try:
                await buffer.stop()
            except Exception as e:
                logger.error(f"Error stopping buffer {component}: {e}")
        
        self._buffers.clear()
    
    def _cleanup_sync(self):
        """Synchronous cleanup for atexit"""
        try:
            # Try to run cleanup in existing event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Schedule cleanup
                asyncio.create_task(self.close_all())
            else:
                loop.run_until_complete(self.close_all())
        except RuntimeError:
            # No event loop, create one
            asyncio.run(self.close_all())
        except Exception as e:
            print(f"Error during async logger cleanup: {e}")
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all buffers"""
        return {
            component: buffer.get_stats() 
            for component, buffer in self._buffers.items()
        }

# Global async logger instance
_async_logger: Optional[AsyncActivityLogger] = None

def get_async_logger(logs_dir: str = "logs", buffer_size: int = 1000, 
                    flush_interval: float = 1.0) -> AsyncActivityLogger:
    """Get the global async activity logger"""
    global _async_logger
    if _async_logger is None:
        _async_logger = AsyncActivityLogger(logs_dir, buffer_size, flush_interval)
    return _async_logger

# Convenience functions for different components
async def log_orchestrator_activity_async(operation_type: str, **data: Any):
    """Log orchestrator activity asynchronously"""
    logger_instance = get_async_logger()
    await logger_instance.log_activity("orchestrator", operation_type, **data)

async def log_a2a_activity_async(operation_type: str, **data: Any):
    """Log A2A activity asynchronously"""
    logger_instance = get_async_logger()
    await logger_instance.log_activity("a2a", operation_type, **data)

async def log_performance_activity_async(operation_type: str, **data: Any):
    """Log performance activity asynchronously"""
    logger_instance = get_async_logger()
    await logger_instance.log_activity("performance", operation_type, **data)

async def log_tool_activity_async(tool: str, operation_type: str, **data: Any):
    """Log tool activity asynchronously"""
    logger_instance = get_async_logger()
    await logger_instance.log_activity("tools", operation_type, tool=tool, **data)

async def log_cost_activity_async(operation_type: str, **data: Any):
    """Log cost activity asynchronously"""
    logger_instance = get_async_logger()
    await logger_instance.log_activity("cost_tracking", operation_type, **data)

async def close_async_logger():
    """Close the global async logger"""
    global _async_logger
    if _async_logger is not None:
        await _async_logger.close_all()
        _async_logger = None