"""SSE (Server-Sent Events) observer for live UI updates."""

import asyncio
import concurrent.futures
from typing import Dict, List, Optional
from datetime import datetime

from .base import (
    PlanExecuteObserver,
    SearchResultsEvent,
    HumanInputRequestedEvent,
    PlanStepEvent,
    PlanCreatedEvent,
    TaskStartedEvent,
    TaskCompletedEvent,
    PlanModifiedEvent,
    PlanUpdatedEvent,
    MemoryNodeAddedEvent,
    MemoryEdgeAddedEvent,
    MemoryGraphSnapshotEvent,
    LLMContextEvent
)


class SSEObserver(PlanExecuteObserver):
    """Observer that converts plan events to SSE messages for live UI updates."""
    
    def __init__(self):
        self.sse_queue: List[Dict] = []  # Queue of SSE messages
        self._observers = []  # SSE clients listening
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="sse-observer")
        self._main_loop = None  # Will store reference to main event loop
    
    def set_main_loop(self, loop=None):
        """Set the main event loop to use for SSE emissions.
        
        Args:
            loop: The asyncio event loop to use. If None, captures current running loop.
        """
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                from src.utils.logging.framework import SmartLogger
                logger = SmartLogger("orchestrator")
                logger.warning("SSE_OBSERVER_no_loop_to_capture")
                return
        self._main_loop = loop
    
    def add_client(self, client_callback):
        """Add an SSE client callback."""
        self._observers.append(client_callback)
    
    def remove_client(self, client_callback):
        """Remove an SSE client callback."""
        if client_callback in self._observers:
            self._observers.remove(client_callback)
    
    def _emit_sse_threadsafe(self, event_type: str, data: Dict):
        """Thread-safe method to emit SSE events."""
        from src.utils.logging.framework import SmartLogger
        logger = SmartLogger("orchestrator")
        
        # Only log if we have debug logging enabled
        if logger.isEnabledFor(10):  # DEBUG level
            logger.debug("SSE_OBSERVER_emit_threadsafe", 
                       event_type=event_type,
                       connected_clients=len(self._observers))
        
        # Format to match main branch: {"event": "type", "data": {...}}
        sse_payload = {
            "event": event_type,
            "data": data
        }
        
        sse_message = {
            "event": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat(),
            "sse_payload": sse_payload  # Store formatted payload for transmission
        }
        
        # Add to queue for new connections (thread-safe for simple operations)
        self.sse_queue.append(sse_message)
        
        # Keep only last 50 messages
        if len(self.sse_queue) > 50:
            self.sse_queue.pop(0)
        
        # Use stored main event loop, or try to get the current running loop
        if self._main_loop is None:
            try:
                self._main_loop = asyncio.get_running_loop()
                logger.info("SSE_OBSERVER_captured_loop")
            except RuntimeError:
                # No running loop - this might happen when called from thread
                logger.warning("SSE_OBSERVER_no_running_loop")
                return
        
        # Schedule the callbacks to run in the main event loop
        # This ensures we write to aiohttp responses in the correct event loop
        asyncio.run_coroutine_threadsafe(
            self._emit_sse_async(sse_message),
            self._main_loop
        )
    
    async def _emit_sse_async(self, sse_message: Dict):
        """Async method to actually send SSE messages to connected clients."""
        from src.utils.logging.framework import SmartLogger
        logger = SmartLogger("orchestrator")
        
        event_type = sse_message.get("event", "unknown")
        # Only log if we have debug logging enabled
        if logger.isEnabledFor(10):  # DEBUG level
            logger.debug("SSE_OBSERVER_sending_to_clients", 
                       event_type=event_type, 
                       connected_clients=len(self._observers))
        
        # Send to all connected clients
        for callback in self._observers[:]:  # Copy to avoid modification during iteration
            try:
                await callback(sse_message)  # Await the async callback
                # Success - no need to log unless debugging
                pass
            except Exception as e:
                logger.error("SSE_OBSERVER_callback_failed", event_type=event_type, error=str(e))
                # Remove dead clients
                try:
                    self._observers.remove(callback)
                except ValueError:
                    pass  # Already removed
    
    def on_search_results(self, event: SearchResultsEvent) -> None:
        """Forward search results via SSE."""
        pass  # Not needed for plan updates
    
    def on_human_input_requested(self, event: HumanInputRequestedEvent) -> Optional[str]:
        """Forward human input requests via SSE."""
        return None  # Not handling input via SSE
    
    def on_plan_step(self, event: PlanStepEvent) -> None:
        """Forward plan step events via SSE."""
        pass  # Using more specific events instead
    
    def on_plan_created(self, event: PlanCreatedEvent) -> None:
        """Emit plan_created SSE event."""
        from src.utils.logging.framework import SmartLogger
        logger = SmartLogger("orchestrator")
        logger.info("SSE_OBSERVER_DEBUG_plan_created", 
                   task_id=event.task_id, 
                   total_steps=event.total_steps,
                   connected_clients=len(self._observers))
        
        # Use thread-safe emission
        self._emit_sse_threadsafe("plan_created", {
            "task_id": event.task_id,
            "plan_steps": event.plan_steps,
            "total_steps": event.total_steps
        })
    
    def on_task_started(self, event: TaskStartedEvent) -> None:
        """Emit task_started SSE event."""
        self._emit_sse_threadsafe("task_started", {
            "task_id": event.task_id,
            "task_description": event.task_description,
            "step_number": event.step_number,
            "total_steps": event.total_steps
        })
    
    def on_task_completed(self, event: TaskCompletedEvent) -> None:
        """Emit task_completed SSE event."""
        self._emit_sse_threadsafe("task_completed", {
            "task_id": event.task_id,
            "task_description": event.task_description,
            "step_number": event.step_number,
            "total_steps": event.total_steps,
            "success": event.success,
            "result": event.result
        })
    
    def on_plan_modified(self, event: PlanModifiedEvent) -> None:
        """Emit plan_modified SSE event."""
        self._emit_sse_threadsafe("plan_modified", {
            "task_id": event.task_id,
            "plan_steps": event.plan_steps,
            "modification_type": event.modification_type,
            "details": event.details
        })
    
    def on_plan_updated(self, event: PlanUpdatedEvent) -> None:
        """Emit plan_updated SSE event."""
        self._emit_sse_threadsafe("plan_updated", {
            "task_id": event.task_id,
            "plan_steps": event.plan_steps,
            "completed_steps": event.completed_steps,
            "failed_steps": event.failed_steps,
            "current_step": event.current_step,
            "total_steps": event.total_steps,
            "completed_count": event.completed_count,
            "failed_count": event.failed_count
        })
    
    def on_memory_node_added(self, event: MemoryNodeAddedEvent) -> None:
        """Emit memory_node_added SSE event."""
        self._emit_sse_threadsafe("memory_node_added", {
            "task_id": event.task_id,
            "thread_id": event.thread_id,
            "node_id": event.node_id,
            "node_data": event.node_data
        })
    
    def on_memory_edge_added(self, event: MemoryEdgeAddedEvent) -> None:
        """Emit memory_edge_added SSE event."""
        self._emit_sse_threadsafe("memory_edge_added", {
            "task_id": event.task_id,
            "thread_id": event.thread_id,
            "edge_data": event.edge_data
        })
    
    def on_memory_graph_snapshot(self, event: MemoryGraphSnapshotEvent) -> None:
        """Emit memory_graph_snapshot SSE event."""
        self._emit_sse_threadsafe("memory_graph_snapshot", {
            "task_id": event.task_id,
            "thread_id": event.thread_id,
            "graph_data": event.graph_data
        })
    
    def on_interrupt(self, event) -> None:
        """Emit interrupt SSE event."""
        self._emit_sse_threadsafe("interrupt", {
            "task_id": event.task_id,
            "interrupt_type": event.interrupt_type,
            "interrupt_reason": event.interrupt_reason,
            "thread_id": event.thread_id,
            "current_plan": event.current_plan,
            "completed_steps": event.completed_steps,
            "total_steps": event.total_steps
        })
    
    def on_interrupt_resume(self, event) -> None:
        """Emit interrupt_resume SSE event."""
        self._emit_sse_threadsafe("interrupt_resume", {
            "task_id": event.task_id,
            "interrupt_type": event.interrupt_type,
            "thread_id": event.thread_id,
            "user_input": event.user_input,
            "was_modified": event.was_modified
        })
    
    def on_llm_context(self, event: LLMContextEvent) -> None:
        """Emit LLM context event showing what will be sent to the model."""
        self._emit_sse_threadsafe("llm_context", {
            "task_id": event.task_id,
            "context_type": event.context_type,
            "context_text": event.context_text,
            "metadata": event.metadata,
            "full_prompt": event.full_prompt,
            "thread_id": event.thread_id,
            "timestamp": event.timestamp or datetime.now().isoformat()
        })
    
    def notify(self, event: Dict) -> None:
        """Generic notify method for direct SSE events.
        
        This is used by direct_call_events to emit tool execution events.
        
        Args:
            event: Dict with 'event' and 'data' keys
        """
        event_type = event.get("event", "unknown")
        event_data = event.get("data", {})
        
        # Emit the event directly using our thread-safe method
        self._emit_sse_threadsafe(event_type, event_data)