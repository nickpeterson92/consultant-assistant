#!/usr/bin/env python3
"""Textual-based CLI client for the orchestrator - handles all real-time updates properly."""

import sys
import os
import asyncio
import time
import uuid
import json
import aiohttp
import threading
from typing import List, Dict, Any, Optional

# Add the project root to Python path for src imports
sys.path.insert(0, os.path.dirname(__file__))

from textual.app import App, ComposeResult
from textual.widgets import (
    Header, Footer, Input, Static, DataTable, 
    LoadingIndicator, ProgressBar, Label, Button, Markdown
)
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen, ModalScreen
from textual.events import Key
from textual import on, work

from src.a2a import A2AClient
from src.utils.config import (
    get_conversation_config, ENTERPRISE_ASSISTANT_BANNER, ENTERPRISE_ASSISTANT_COMPACT_LOGO
)
from src.utils.ui.animations import animated_banner_display, format_compact_logo_for_textual
from src.utils.logging import get_logger

# Initialize logger
logger = get_logger()


class TextualWebSocketController:
    """WebSocket controller for the Textual console system."""
    
    def __init__(self, orchestrator_url, thread_id):
        self.orchestrator_url = orchestrator_url
        self.thread_id = thread_id
        self.ws = None
        self.connected = False
        self.client_id = None
        
    async def connect(self):
        """Connect to orchestrator WebSocket."""
        try:
            # Convert HTTP URL to WebSocket URL
            ws_url = self.orchestrator_url.replace("http://", "ws://").replace("https://", "wss://")
            ws_url = f"{ws_url}/a2a/ws"
            
            session = aiohttp.ClientSession()
            self.ws = await session.ws_connect(ws_url)
            
            # Register with the thread ID
            await self.ws.send_str(json.dumps({
                "type": "register",
                "payload": {"thread_id": self.thread_id}
            }))
            
            # Wait for registration acknowledgment
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get("type") == "registration_ack":
                        self.connected = True
                        self.client_id = data.get("payload", {}).get("client_id")
                        logger.info("websocket_connected",
                                   component="client",
                                   client_id=self.client_id,
                                   thread_id=self.thread_id)
                        break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error("websocket_connection_error",
                               component="client",
                               error=str(self.ws.exception()))
                    break
            
            return self.connected
            
        except Exception as e:
            logger.error("websocket_connect_error",
                        component="client",
                        error=str(e))
            return False
    
    async def send_interrupt(self, reason="user_escape"):
        """Send interrupt command via WebSocket."""
        if not self.connected or not self.ws:
            logger.warning("websocket_not_connected_for_interrupt", component="client")
            return False
        
        try:
            message_id = str(uuid.uuid4())[:8]
            await self.ws.send_str(json.dumps({
                "type": "interrupt",
                "payload": {
                    "thread_id": self.thread_id,
                    "reason": reason
                },
                "id": message_id
            }))
            
            # Wait for acknowledgment
            timeout_task = asyncio.create_task(asyncio.sleep(5.0))
            
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get("type") == "interrupt_ack":
                        timeout_task.cancel()
                        success = data.get("payload", {}).get("success", False)
                        message = data.get("payload", {}).get("message", "")
                        
                        logger.info("websocket_interrupt_ack",
                                   component="client",
                                   success=success,
                                   ack_message=message)
                        return success
                
                if timeout_task.done():
                    logger.warning("websocket_interrupt_timeout", component="client")
                    return False
            
            return False
            
        except Exception as e:
            logger.error("websocket_interrupt_error",
                        component="client",
                        error=str(e))
            return False
    
    async def send_resume(self, user_input):
        """Send resume command with user modifications via WebSocket."""
        if not self.connected or not self.ws:
            logger.warning("websocket_not_connected_for_resume", component="client")
            return False
        
        try:
            message_id = str(uuid.uuid4())[:8]
            await self.ws.send_str(json.dumps({
                "type": "resume",
                "payload": {
                    "thread_id": self.thread_id,
                    "user_input": user_input
                },
                "id": message_id
            }))
            
            # Wait for acknowledgment
            timeout_task = asyncio.create_task(asyncio.sleep(10.0))
            
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get("type") == "resume_ack":
                        timeout_task.cancel()
                        success = data.get("payload", {}).get("success", False)
                        message = data.get("payload", {}).get("message", "")
                        
                        logger.info("websocket_resume_ack",
                                   component="client",
                                   success=success,
                                   ack_message=message)
                        return success
                
                if timeout_task.done():
                    logger.warning("websocket_resume_timeout", component="client")
                    return False
            
            return False
            
        except Exception as e:
            logger.error("websocket_resume_error",
                        component="client",
                        error=str(e))
            return False
    
    async def close(self):
        """Close WebSocket connection."""
        if self.ws:
            await self.ws.close()
            self.connected = False
            logger.info("websocket_disconnected",
                       component="client",
                       client_id=self.client_id)


class PlanModificationScreen(ModalScreen):
    """Modal screen for plan modification during interrupts."""
    
    def __init__(self, current_plan):
        super().__init__()
        self.current_plan = current_plan
        self.user_input = ""
    
    def compose(self) -> ComposeResult:
        """Compose the modal screen layout."""
        with Container(classes="modal-container"):
            yield Static("[bold red]Plan Execution Interrupted[/bold red]")
            yield Static("")
            
            # Show current plan
            yield Static("[bold]Current Plan:[/bold]")
            if self.current_plan:
                for i, task in enumerate(self.current_plan, 1):
                    task_content = task.get('content', 'Unknown task')
                    yield Static(f"{i}. {task_content}")
            else:
                yield Static("No plan available")
            
            yield Static("")
            yield Static("[bold]Enter your modification instructions:[/bold]")
            yield Static("(e.g., 'skip to step 3', 'change step 2 to...', or 'cancel')")
            yield Static("")
            
            yield Input(
                placeholder="Enter your modifications or press Enter to continue...",
                id="modification-input"
            )
            
            yield Static("")
            yield Static("[dim]Press Enter to submit, Escape to cancel[/dim]")
    
    def on_mount(self) -> None:
        """Focus the input when the modal opens."""
        self.query_one("#modification-input", Input).focus()
    
    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user input submission."""
        self.user_input = event.value.strip()
        logger.info("plan_modification_input_submitted",
                   component="client",
                   user_input=self.user_input,
                   input_length=len(self.user_input))
        self.dismiss(self.user_input)
        # Prevent event from bubbling up
        event.stop()
    
    def on_key(self, event: Key) -> None:
        """Handle key events."""
        if event.key == "escape":
            logger.info("plan_modification_cancelled_via_escape", component="client")
            self.dismiss("")


# Removed raw terminal monitoring - using Textual's built-in event system instead


class PlanStatusWidget(Static):
    """Widget for displaying execution plan status with real-time updates."""
    
    # Reactive attributes - automatically trigger watch methods when changed
    plan_tasks: reactive[List[Dict[str, Any]]] = reactive([], recompose=True)
    completed_steps: reactive[List[str]] = reactive([])
    failed_steps: reactive[List[str]] = reactive([])
    skipped_steps: reactive[List[str]] = reactive([])
    current_step: reactive[str] = reactive("")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def update_plan(self, tasks: List[Dict[str, Any]]):
        """Update the plan tasks - reactive will auto-trigger display update."""
        self.plan_tasks = tasks
    
    def update_progress(self, **kwargs):
        """Update progress state - reactive will auto-trigger display update."""
        if 'completed_steps' in kwargs:
            new_completed = list(self.completed_steps)
            for step in kwargs['completed_steps']:
                if step not in new_completed:
                    new_completed.append(step)
            self.completed_steps = new_completed
        
        if 'failed_steps' in kwargs:
            new_failed = list(self.failed_steps)
            for step in kwargs['failed_steps']:
                if step not in new_failed:
                    new_failed.append(step)
            self.failed_steps = new_failed
        
        if 'skipped_steps' in kwargs:
            new_skipped = list(self.skipped_steps)
            for step in kwargs['skipped_steps']:
                if step not in new_skipped:
                    new_skipped.append(step)
            self.skipped_steps = new_skipped
        
        if 'current_step' in kwargs:
            self.current_step = kwargs['current_step']
    
    def watch_plan_tasks(self, old_tasks: List[Dict[str, Any]], new_tasks: List[Dict[str, Any]]) -> None:
        """Watch method called automatically when plan_tasks changes."""
        self._refresh_display()
    
    def watch_completed_steps(self, old_steps: List[str], new_steps: List[str]) -> None:
        """Watch method called automatically when completed_steps changes."""
        self._refresh_display()
    
    def watch_failed_steps(self, old_steps: List[str], new_steps: List[str]) -> None:
        """Watch method called automatically when failed_steps changes."""
        self._refresh_display()
    
    def watch_skipped_steps(self, old_steps: List[str], new_steps: List[str]) -> None:
        """Watch method called automatically when skipped_steps changes."""
        self._refresh_display()
    
    def watch_current_step(self, old_step: str, new_step: str) -> None:
        """Watch method called automatically when current_step changes."""
        self._refresh_display()
    
    def _refresh_display(self):
        """Internal method to refresh the plan display with current state."""
        if not self.plan_tasks:
            self.update("")
            return
        
        content = []
        content.append("[bold #7dd3fc]Plan Status[/bold #7dd3fc]")
        content.append("")
        content.append("[#94a3b8]Execution Plan[/#94a3b8]")
        
        for i, task in enumerate(self.plan_tasks, 1):
            task_content = task.get('content', 'Unknown task')
            
            # Determine status with softer, more modern colors
            if task_content in self.completed_steps:
                icon = "[#22c55e]✓[/#22c55e]"
                style = "#22c55e"
            elif task_content in [fs.split(' (Error:')[0] for fs in self.failed_steps]:
                icon = "[#ef4444]✗[/#ef4444]"
                style = "#ef4444"
            elif task_content in self.skipped_steps:
                icon = "[#f59e0b]−[/#f59e0b]"
                style = "#f59e0b"
            elif task_content == self.current_step:
                icon = "[#3b82f6]→[/#3b82f6]"
                style = "#3b82f6 bold"
            else:
                icon = "[#64748b]□[/#64748b]"
                style = "#64748b"
            
            content.append(f"{icon} {i}. [{style}]{task_content}[/{style}]")
        
        self.update("\n".join(content))
    
    def refresh_display(self):
        """Public method for manual refresh (kept for backwards compatibility)."""
        self._refresh_display()


class ConversationWidget(ScrollableContainer):
    """Widget for displaying conversation history with proper markdown rendering."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.message_count = 0
    
    def add_message(self, role: str, content: str):
        """Add a message to the conversation."""
        logger.info("conversation_add_message", 
                   role=role, 
                   content_length=len(content),
                   content_preview=content[:100])
        
        # Create separate widgets for label and content
        if role == "user":
            label_widget = Static("[bold cyan]USER:[/bold cyan]", classes="message-label")
            content_widget = Markdown(content, classes="message-content")
        else:
            label_widget = Static("[bold green]ASSISTANT:[/bold green]", classes="message-label") 
            content_widget = Markdown(content, classes="message-content")
        
        # Mount both widgets
        self.mount(label_widget)
        self.mount(content_widget)
        
        self.message_count += 1
        
        # Keep only last 20 messages to prevent memory issues
        if self.message_count > 20:
            # Remove the oldest child widget
            children = list(self.children)
            if children:
                children[0].remove()
        
        # Auto-scroll to bottom
        self.scroll_end(animate=False)
        
        logger.info("conversation_display_updated", 
                   total_messages=self.message_count,
                   content_length=len(content))


class StatusWidget(Static):
    """Widget for displaying current status and loading indicators."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_status = "Ready"
        self.is_processing = False
    
    def set_status(self, status: str, processing: bool = False):
        """Update the status display."""
        self.current_status = status
        self.is_processing = processing
        
        if processing:
            self.update(f"[yellow]⏳[/yellow] {status}")
        else:
            self.update(f"[green]✓[/green] {status}")


class OrchestatorApp(App):
    """Main Textual application for orchestrator CLI."""
    
    CSS_PATH = "textual_styles.tcss"
    
    def __init__(self):
        super().__init__()
        self.orchestrator_url = "http://localhost:8000"
        self.a2a_client = A2AClient(self.orchestrator_url)
        self.thread_id = str(uuid.uuid4())
        self.conversation_widget = None
        self.plan_widget = None
        self.status_widget = None
        self.input_widget = None
        self.sse_task = None
        
        # State management
        self.capabilities = []
        self.agent_stats = {}
        self.current_operation = {}
        self.is_processing = False
        
        # Interrupt handling
        self.ws_controller = None
        self.interrupt_requested = False
        self.processing_done = None
        self.escape_monitor_thread = None
        
        # Animation state
        self.startup_animation_complete = False
        conv_config = get_conversation_config()
        self.show_startup_animation = conv_config.animated_banner_enabled
        
        # Debug logging
        logger.info("textual_app_initialized", thread_id=self.thread_id)
    
    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+q", "quit", "Quit"),
        ("escape", "interrupt", "Interrupt"),
    ]
    
    def compose(self) -> ComposeResult:
        """Compose the UI layout."""
        yield Header()
        
        # Main banner with compact ASCII logo
        compact_logo = format_compact_logo_for_textual(ENTERPRISE_ASSISTANT_COMPACT_LOGO)
        yield Static(
            f"{compact_logo}\n"
            "[dim #94a3b8]Powered by Multi-Agent Orchestration[/dim #94a3b8]",
            classes="header",
            id="main-banner"
        )
        
        # Main container
        with Container(classes="main-container"):
            # Left panel - conversation
            with Vertical(classes="left-panel"):
                self.conversation_widget = ConversationWidget(classes="conversation")
                yield self.conversation_widget
                
                # Status bar
                self.status_widget = StatusWidget(classes="status-bar")
                yield self.status_widget
                
                # Input container - simplified
                yield Input(
                    placeholder="Type your message here...",
                    id="message-input",
                    classes="input-field"
                )
            
            # Right panel - plan status
            with Vertical(classes="right-panel"):
                self.plan_widget = PlanStatusWidget(classes="plan-status")
                yield self.plan_widget
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize the application when mounted."""
        logger.info("textual_app_mounted", thread_id=self.thread_id)
        
        # Focus on input using query system
        self.query_one("#message-input", Input).focus()
        logger.info("input_focused", thread_id=self.thread_id)
        
        # Animation happens before Textual starts, so we're always ready
        
        # Start background tasks using Textual's work decorator
        self.initialize_connection()
        self.initialize_websocket_controller()
    
    
    @work(exclusive=True)
    async def initialize_connection(self):
        """Initialize connection to orchestrator using Textual's work decorator."""
        try:
            self.status_widget.set_status("Connecting to orchestrator...", processing=True)
            
            # Simple connection test - try to get agent card
            test_result = await self.a2a_client.get_agent_card(f"{self.orchestrator_url}/a2a")
            
            self.status_widget.set_status("Connected! Ready to process requests")
            
        except Exception as e:
            self.status_widget.set_status(f"Connection failed: {str(e)}")
            logger.error("connection_failed", error=str(e))
            # Still allow the app to run for testing
    
    @work(exclusive=True)
    async def initialize_websocket_controller(self):
        """Initialize WebSocket controller for interrupts using Textual's work decorator."""
        try:
            self.ws_controller = TextualWebSocketController(self.orchestrator_url, self.thread_id)
            ws_connected = await self.ws_controller.connect()
            
            if ws_connected:
                logger.info("websocket_control_ready", component="client", thread_id=self.thread_id)
            else:
                logger.info("websocket_control_unavailable", component="client", thread_id=self.thread_id)
                
        except Exception as e:
            logger.warning("websocket_connection_failed", 
                          component="client", 
                          thread_id=self.thread_id,
                          error=str(e))
            self.ws_controller = None
    
    async def handle_sse_stream(self):
        """Handle server-sent events stream - removed as we use direct SSE in process_with_sse_streaming."""
        pass
    
    async def process_sse_event(self, event_type: str, data: Dict[str, Any]):
        """Process incoming SSE events."""
        try:
            if event_type == 'plan_created':
                plan = data.get('plan', {})
                tasks = plan.get('tasks', [])
                self.plan_widget.update_plan(tasks)
                self.status_widget.set_status("Plan created", processing=True)
            
            elif event_type == 'task_started':
                task = data.get('task', {})
                task_content = task.get('content', '')
                self.plan_widget.update_progress(current_step=task_content)
                self.status_widget.set_status(f"Executing: {task_content}", processing=True)
            
            elif event_type == 'plan_modified':
                # Handle plan modification events (skipping, etc.)
                modification_type = data.get('modification_type', 'unknown')
                current_task_index = data.get('current_task_index', 0)
                skipped_indices = data.get('skipped_task_indices', [])
                plan_data = data.get('plan')
                
                # Update plan widget with skipped tasks
                if plan_data and self.plan_widget.plan_tasks:
                    skipped_task_contents = []
                    for i in skipped_indices:
                        if i < len(self.plan_widget.plan_tasks):
                            task_content = self.plan_widget.plan_tasks[i].get('content', 'Unknown task')
                            skipped_task_contents.append(task_content)
                    
                    self.plan_widget.update_progress(skipped_steps=skipped_task_contents)
                    self.status_widget.set_status(f"Plan modified: {modification_type}")
                
                logger.info("plan_modified_processed",
                           component="client",
                           modification_type=modification_type,
                           current_task_index=current_task_index,
                           skipped_count=len(skipped_indices))
            
            elif event_type == 'plan_updated':
                # Handle plan updates (e.g., from replanning after interrupts)
                current_task_index = data.get('current_task_index', 0)
                skipped_indices = data.get('skipped_task_indices', [])
                plan_data = data.get('plan')
                
                # Update plan widget with current plan state
                if plan_data:
                    tasks = plan_data.get('tasks', [])
                    if tasks:
                        # Update the plan with new tasks
                        self.plan_widget.update_plan(tasks)
                        
                        # Mark skipped tasks if any
                        if skipped_indices:
                            skipped_task_contents = []
                            for i in skipped_indices:
                                if i < len(tasks):
                                    task_content = tasks[i].get('content', 'Unknown task')
                                    skipped_task_contents.append(task_content)
                            
                            self.plan_widget.update_progress(skipped_steps=skipped_task_contents)
                            self.status_widget.set_status("Plan updated with skipped steps")
                        else:
                            self.status_widget.set_status("Plan updated")
                
                logger.info("plan_updated_processed",
                           component="client",
                           current_task_index=current_task_index,
                           skipped_count=len(skipped_indices),
                           has_plan_data=bool(plan_data))
            
            elif event_type == 'task_completed':
                task = data.get('task', {})
                task_content = task.get('content', data.get('content', ''))
                success = data.get('success', False)
                
                if success:
                    self.plan_widget.update_progress(completed_steps=[task_content])
                    self.status_widget.set_status(f"Completed: {task_content}")
                else:
                    self.plan_widget.update_progress(failed_steps=[task_content])
                    self.status_widget.set_status(f"Failed: {task_content}")
            
            elif event_type == 'task_error':
                content = data.get('content', '')
                error = data.get('error', '')
                failed_step = f"{content} (Error: {error})"
                self.plan_widget.update_progress(failed_steps=[failed_step])
                self.status_widget.set_status(f"Error: {error}")
            
            elif event_type == 'plan_completed':
                self.is_processing = False
                self.status_widget.set_status("Plan completed")
            
            elif event_type == 'response':
                response = data.get('response', '')
                self.conversation_widget.add_message("assistant", response)
                self.is_processing = False
                self.status_widget.set_status("Ready")
            
            elif event_type == 'summary_generated':
                # Handle LLM-generated summary responses
                summary_content = data.get('summary', '')
                if summary_content:
                    logger.info("summary_generated_received", 
                               thread_id=self.thread_id,
                               summary_length=len(summary_content),
                               summary_preview=summary_content[:100])
                    self.conversation_widget.add_message("assistant", summary_content)
                    self.is_processing = False
                    self.status_widget.set_status("Ready")
            
            elif event_type == 'error':
                error = data.get('error', 'Unknown error')
                self.conversation_widget.add_message("assistant", f"Error: {error}")
                self.is_processing = False
                self.status_widget.set_status("Error occurred")
        
        except Exception as e:
            logger.error("sse_event_processing_error", event_type=event_type, error=str(e))
    
    @on(Input.Submitted)
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user input submission."""
        logger.info("input_submitted", 
                   thread_id=self.thread_id,
                   input_value=event.value[:50],
                   is_processing=self.is_processing)
        
        if self.is_processing:
            logger.warning("input_rejected_processing", thread_id=self.thread_id)
            return
        
        user_input = event.value.strip()
        if not user_input:
            logger.warning("input_rejected_empty", thread_id=self.thread_id)
            return
        
        logger.info("processing_user_input", 
                   thread_id=self.thread_id,
                   input_length=len(user_input))
        
        # Clear input using query system
        self.query_one("#message-input", Input).value = ""
        
        # Add to conversation
        self.conversation_widget.add_message("user", user_input)
        logger.info("user_message_added_to_conversation", thread_id=self.thread_id)
        
        # Set processing state
        self.is_processing = True
        self.status_widget.set_status("Processing request...", processing=True)
        
        # Start processing with interrupt support using Textual's work decorator
        self.process_with_interrupt_support(user_input)
    
    @work(exclusive=True)
    async def process_with_interrupt_support(self, user_input: str):
        """Process user input with interrupt support using Textual's work decorator."""
        # Initialize interrupt handling
        self.interrupt_requested = False
        self.processing_done = threading.Event()
        
        # No need for raw terminal monitoring - use Textual's built-in event system
        
        try:
            # Create task data
            task_data = {
                "task": {
                    "id": str(uuid.uuid4()),
                    "instruction": user_input,
                    "context": {
                        "source": "cli_client",
                        "thread_id": self.thread_id
                    }
                }
            }
            
            logger.info("starting_sse_streaming", thread_id=self.thread_id)
            # Use SSE streaming
            await self.process_with_sse_streaming(task_data)
            
        except Exception as e:
            logger.error("input_processing_error", 
                        thread_id=self.thread_id,
                        error=str(e))
            self.conversation_widget.add_message("assistant", f"Error: {str(e)}")
            self.is_processing = False
            self.status_widget.set_status("Error sending message")
        finally:
            # Clean up
            self.processing_done.set()
            # No escape monitor thread to clean up
            
            # Handle interrupt if requested
            if self.interrupt_requested and self.ws_controller:
                # Use Textual's work decorator for async handling
                self.handle_interrupt()
            else:
                # Reset processing state if no interrupt
                if not self.interrupt_requested:
                    self.is_processing = False
                    self.status_widget.set_status("Ready")
    
    async def process_with_sse_streaming(self, task_data: Dict[str, Any]):
        """Process task with SSE streaming like Rich version."""
        timeout = aiohttp.ClientTimeout(total=120, connect=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            stream_url = f"{self.orchestrator_url}/a2a/stream"
            logger.info("attempting_sse_connection",
                       component="client",
                       stream_url=stream_url)
            
            async with session.post(
                stream_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "process_task",
                    "params": task_data,
                    "id": "stream_request"
                },
                headers={'Accept': 'text/event-stream'}
            ) as response:
                logger.info("sse_stream_response_received",
                           component="client",
                           status_code=response.status,
                           content_type=response.headers.get('content-type'))
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error("sse_stream_request_failed",
                                component="client",
                                status_code=response.status,
                                error_text=error_text)
                    self.conversation_widget.add_message("assistant", f"Error: HTTP {response.status}: {error_text}")
                    self.is_processing = False
                    self.status_widget.set_status("Error")
                    return
                
                logger.info("sse_stream_processing_start", component="client")
                
                async for line in response.content:
                    if not line:
                        continue
                    
                    # Check for interrupt during streaming
                    if self.interrupt_requested:
                        logger.info("interrupt_detected_during_stream", component="client")
                        break
                    
                    line = line.decode('utf-8').strip()
                    
                    # Parse SSE format
                    if line.startswith('data: '):
                        try:
                            data_json = line[6:]  # Remove 'data: ' prefix
                            event_data = json.loads(data_json)
                            
                            event_type = event_data.get('event')
                            data = event_data.get('data', {})
                            
                            # Log all received events
                            logger.info("sse_event_received",
                                       component="client",
                                       event_type=event_type,
                                       data_keys=list(data.keys()) if data else [],
                                       raw_line=line[:100])
                            
                            # Process the event
                            await self.process_sse_event(event_type, data)
                            
                        except json.JSONDecodeError as e:
                            logger.warning("sse_json_decode_error",
                                         component="client",
                                         error=str(e),
                                         raw_line=line[:100])
                        except Exception as e:
                            logger.error("sse_event_processing_error",
                                        component="client",
                                        error=str(e),
                                        raw_line=line[:100])
                
                # Processing complete
                if not self.interrupt_requested:
                    self.is_processing = False
                    self.status_widget.set_status("Ready")

    @on(Input.Changed)
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes for debugging."""
        logger.info("input_changed", 
                   value=event.value,
                   value_length=len(event.value),
                   cursor_position=event.input.cursor_position,
                   has_focus=event.input.has_focus,
                   thread_id=self.thread_id)
        
        # Update the status widget to show current input
        self.status_widget.set_status(f"Typing: {event.value}")
    
    @work(exclusive=True)
    async def handle_interrupt(self):
        """Handle interrupt request using Textual's work decorator."""
        try:
            logger.info("handle_interrupt_start", component="client")
            
            # Reset processing state first to prevent UI lock
            self.is_processing = False
            self.status_widget.set_status("⏸ Execution interrupted - gathering modifications...", processing=False)
            
            # Show plan modification screen
            current_plan = self.plan_widget.plan_tasks if self.plan_widget else []
            logger.info("showing_plan_modification_modal", 
                       component="client",
                       plan_task_count=len(current_plan))
            
            modification_input = await self.push_screen_wait(PlanModificationScreen(current_plan))
            
            logger.info("plan_modification_modal_result",
                       component="client", 
                       modification_input=modification_input,
                       has_input=bool(modification_input))
            
            if modification_input:
                # Send interrupt and resume via WebSocket
                try:
                    logger.info("sending_websocket_interrupt", component="client")
                    # Send interrupt first
                    interrupt_success = await self.ws_controller.send_interrupt("user_escape")
                    
                    logger.info("websocket_interrupt_result", 
                               component="client",
                               success=interrupt_success)
                    
                    if interrupt_success:
                        self.status_widget.set_status("⏸ Execution interrupted successfully")
                        
                        logger.info("sending_websocket_resume", 
                                   component="client",
                                   modification_input=modification_input)
                        
                        # Send resume with modifications
                        resume_success = await self.ws_controller.send_resume(modification_input)
                        
                        logger.info("websocket_resume_result",
                                   component="client", 
                                   success=resume_success)
                        
                        if resume_success:
                            self.status_widget.set_status("▶ Resume request sent successfully")
                            self.conversation_widget.add_message("assistant", "💡 Plan modification applied successfully!")
                            
                            # Reset state
                            self.interrupt_requested = False
                            self.plan_widget.refresh_display()
                        else:
                            logger.error("websocket_resume_failed", component="client")
                            self.status_widget.set_status("Error resuming execution via WebSocket.")
                    else:
                        logger.error("websocket_interrupt_failed", component="client")
                        self.status_widget.set_status("Error sending interrupt via WebSocket.")
                        
                except Exception as interrupt_error:
                    logger.error("websocket_interrupt_handling_error", 
                               component="client", 
                               error=str(interrupt_error))
                    self.status_widget.set_status(f"Error handling interrupt: {interrupt_error}")
            else:
                logger.info("plan_modification_cancelled", component="client")
                self.status_widget.set_status("▶ Continuing without modifications...")
                # Clear interrupt flag and continue
                self.interrupt_requested = False
                
        except Exception as e:
            logger.error("interrupt_handling_error", component="client", error=str(e))
            self.status_widget.set_status(f"Error handling interrupt: {str(e)}")
        finally:
            logger.info("handle_interrupt_complete", component="client")
            # Always reset processing state
            self.is_processing = False
            self.interrupt_requested = False
    
    def action_interrupt(self) -> None:
        """Handle interrupt action (ESC key) using Textual's action system."""
        logger.info("escape_key_pressed",
                   component="client",
                   is_processing=self.is_processing,
                   has_plan=bool(self.plan_widget and self.plan_widget.plan_tasks),
                   has_ws_controller=bool(self.ws_controller))
        
        if self.is_processing and self.plan_widget and self.plan_widget.plan_tasks and self.ws_controller:
            self.interrupt_requested = True
            logger.info("interrupt_requested_via_key", component="client")
            # Use Textual's work decorator for async handling
            self.handle_interrupt()
        else:
            # Show status if interrupt not available
            if not self.ws_controller:
                logger.warning("interrupt_unavailable_no_websocket", component="client")
                self.status_widget.set_status("WebSocket not connected - interrupt unavailable")
            elif not self.is_processing:
                logger.warning("interrupt_unavailable_not_processing", component="client")
                self.status_widget.set_status("No active plan to interrupt")
            else:
                logger.warning("interrupt_unavailable_no_plan", component="client")
                self.status_widget.set_status("No plan currently executing")
    
    def action_quit(self) -> None:
        """Handle quit action."""
        if self.sse_task:
            self.sse_task.cancel()
        if self.processing_done:
            self.processing_done.set()
        self.exit()
    
    def on_unmount(self) -> None:
        """Cleanup when app unmounts."""
        try:
            # Cancel any running tasks
            if self.sse_task:
                self.sse_task.cancel()
            if self.processing_done:
                self.processing_done.set()
            # No escape monitor thread to clean up
        except Exception as e:
            logger.error("cleanup_error", error=str(e))


async def run_startup_animation():
    """Run the impressive banner animation before starting Textual interface."""
    try:
        conv_config = get_conversation_config()
        if conv_config.animated_banner_enabled:
            # Clear screen and run the actual banner animation
            print("\033[2J\033[H", end='')  # Clear screen
            await animated_banner_display(ENTERPRISE_ASSISTANT_BANNER)
            
            # Brief pause to appreciate the banner
            await asyncio.sleep(1.5)
            
            # Clear screen before starting Textual
            print("\033[2J\033[H", end='')
            
            logger.info("banner_animation_complete", component="client")
        else:
            # Just clear screen if animation is disabled
            print("\033[2J\033[H", end='')
            
    except Exception as e:
        logger.error("banner_animation_error", error=str(e), component="client")
        # Clear screen and continue even if animation fails
        print("\033[2J\033[H", end='')


def main():
    """Main entry point."""
    import signal
    
    # Run the startup animation first
    try:
        asyncio.run(run_startup_animation())
    except Exception as e:
        logger.error("startup_animation_failed", error=str(e), component="client")
    
    # Now start the Textual app
    app = OrchestatorApp()
    
    # Signal handlers for clean shutdown
    def handle_signal(signum, frame):
        logger.info("signal_received", signal=signum, component="client")
        if app.processing_done:
            app.processing_done.set()
        if app.ws_controller:
            asyncio.create_task(app.ws_controller.close())
        app.exit()
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt_received", component="client")
    finally:
        # Ensure cleanup
        if app.processing_done:
            app.processing_done.set()
        if app.ws_controller:
            asyncio.run(app.ws_controller.close())
        
        # Restore terminal settings
        try:
            import termios
            import sys
            if sys.stdin.isatty():
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, termios.tcgetattr(sys.stdin))
        except:
            pass


if __name__ == "__main__":
    main()