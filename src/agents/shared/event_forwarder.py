"""Event forwarding system for cross-process SSE event delivery.

Allows agents to forward their SSE events to the orchestrator for unified display.
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from src.utils.logging.framework import SmartLogger
from src.a2a.client import A2AClient

logger = SmartLogger("event_forwarder")


class EventForwarder:
    """Forwards SSE events from agents to orchestrator via A2A protocol."""
    
    def __init__(self, orchestrator_url: str, agent_name: str):
        """Initialize event forwarder.
        
        Args:
            orchestrator_url: URL of the orchestrator's A2A endpoint
            agent_name: Name of this agent for identification
        """
        self.orchestrator_url = orchestrator_url
        self.agent_name = agent_name
        self.event_queue: List[Dict[str, Any]] = []
        self.batch_size = 10
        self.flush_interval = 0.5  # seconds
        self._running = False
        self._flush_task: Optional[asyncio.Task] = None
        self.a2a_client = A2AClient(base_url=orchestrator_url)
        
    async def start(self):
        """Start the event forwarding background task."""
        if self._running:
            return
            
        self._running = True
        self._flush_task = asyncio.create_task(self._periodic_flush())
        logger.info("event_forwarder_started", 
                   agent_name=self.agent_name,
                   orchestrator_url=self.orchestrator_url)
    
    async def stop(self):
        """Stop the event forwarding and flush remaining events."""
        self._running = False
        
        # Flush any remaining events
        await self.flush()
        
        # Cancel flush task
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
                
        logger.info("event_forwarder_stopped", agent_name=self.agent_name)
    
    async def queue_event(self, event_type: str, event_data: Dict[str, Any]):
        """Queue an event for forwarding to orchestrator.
        
        Args:
            event_type: Type of event (e.g., 'agent_call_started')
            event_data: Event data payload
        """
        event = {
            "event": event_type,
            "data": event_data,
            "timestamp": datetime.now().isoformat()
        }
        
        self.event_queue.append(event)
        
        # Auto-flush if batch size reached
        if len(self.event_queue) >= self.batch_size:
            await self.flush()
    
    async def flush(self):
        """Send all queued events to the orchestrator."""
        if not self.event_queue:
            return
            
        # Get events to send
        events_to_send = self.event_queue[:]
        self.event_queue.clear()
        
        try:
            # Send via A2A protocol
            response = await self.a2a_client.call_method(
                "forward_events",
                {
                    "events": events_to_send,
                    "agent_name": self.agent_name,
                    "batch_id": f"{self.agent_name}-{datetime.now().timestamp()}"
                }
            )
            
            logger.info("events_forwarded",
                       agent_name=self.agent_name,
                       event_count=len(events_to_send),
                       response=response)
                       
        except Exception as e:
            logger.error("event_forwarding_failed",
                        agent_name=self.agent_name,
                        error=str(e),
                        event_count=len(events_to_send))
            # Re-queue events for retry
            self.event_queue = events_to_send + self.event_queue
    
    async def _periodic_flush(self):
        """Background task to periodically flush events."""
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                await self.flush()
            except Exception as e:
                logger.error("periodic_flush_error",
                            agent_name=self.agent_name,
                            error=str(e))


# Global event forwarder instance (to be initialized by each agent)
_event_forwarder: Optional[EventForwarder] = None


def init_event_forwarder(orchestrator_url: str, agent_name: str):
    """Initialize the global event forwarder.
    
    Args:
        orchestrator_url: URL of the orchestrator's A2A endpoint
        agent_name: Name of this agent
    """
    global _event_forwarder
    _event_forwarder = EventForwarder(orchestrator_url, agent_name)
    return _event_forwarder


def get_event_forwarder() -> Optional[EventForwarder]:
    """Get the global event forwarder instance."""
    return _event_forwarder


async def forward_event(event_type: str, event_data: Dict[str, Any]):
    """Forward an event to the orchestrator if forwarder is initialized.
    
    Args:
        event_type: Type of event
        event_data: Event data payload
    """
    if _event_forwarder:
        await _event_forwarder.queue_event(event_type, event_data)