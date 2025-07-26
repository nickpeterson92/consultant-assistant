#!/usr/bin/env python3
"""Textual-based CLI client for the plan-and-execute orchestrator - exact main branch port."""

import sys
import os
import asyncio
import uuid
import json
import aiohttp
from typing import List, Dict, Any, Optional

# Add the project root to Python path for src imports
sys.path.insert(0, os.path.dirname(__file__))

from textual.app import App, ComposeResult
from textual.widgets import (
    Header, Footer, Input, Static, Markdown
)
from textual.containers import Container, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.events import Key
from textual import on, work

from src.a2a import A2AClient, A2ATask
from src.utils.thread_utils import create_thread_id
from src.utils.config.constants import ENTERPRISE_ASSISTANT_BANNER, ENTERPRISE_ASSISTANT_COMPACT_LOGO
from src.utils.config.unified_config import config as app_config
from src.utils.ui.animations import animated_banner_display, format_compact_logo_for_textual
from src.utils.ui.tool_events_widget import ToolEventsWidget
from src.utils.logging.framework import SmartLogger

# Initialize SmartLogger
logger = SmartLogger("client")


class TextualWebSocketController:
    """WebSocket controller for interrupt handling."""
    
    def __init__(self, orchestrator_url: str, thread_id: str):
        self.orchestrator_url = orchestrator_url.replace("http://", "ws://").replace("https://", "wss://")
        self.thread_id = thread_id
        self.ws = None
        self.connected = False
        self.client_id = str(uuid.uuid4())[:8]
        
    async def connect(self):
        """Connect to WebSocket endpoint."""
        try:
            ws_url = f"{self.orchestrator_url}/ws"
            logger.info("websocket_connecting", url=ws_url, thread_id=self.thread_id)
            
            session = aiohttp.ClientSession()
            self.ws = await session.ws_connect(ws_url)
            self.connected = True
            
            logger.info("websocket_connected", client_id=self.client_id)
            return True
            
        except Exception as e:
            logger.error("websocket_connect_error", error=str(e))
            return False
    
    async def send_interrupt(self, reason="user_escape"):
        """Send interrupt command via WebSocket."""
        logger.info("websocket_interrupt_attempt",
                   connected=self.connected,
                   has_ws=bool(self.ws),
                   thread_id=self.thread_id,
                   reason=reason)
        
        if not self.connected or not self.ws:
            logger.warning("websocket_not_connected_for_interrupt")
            return False
        
        try:
            message_id = str(uuid.uuid4())[:8]
            interrupt_msg = {
                "type": "interrupt",
                "payload": {
                    "thread_id": self.thread_id,
                    "reason": reason
                },
                "id": message_id
            }
            
            await self.ws.send_str(json.dumps(interrupt_msg))
            logger.info("websocket_interrupt_sent_successfully", message_id=message_id)
            
            # Wait for acknowledgment
            async def wait_for_interrupt_ack():
                async for msg in self.ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if data.get("type") == "interrupt_ack":
                            return data.get("payload", {}).get("success", False)
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        return False
                return False
            
            try:
                result = await asyncio.wait_for(wait_for_interrupt_ack(), timeout=5.0)
                return result
            except asyncio.TimeoutError:
                logger.warning("websocket_interrupt_timeout")
                return False
                
        except Exception as e:
            logger.error("websocket_interrupt_error", error=str(e))
            return False
    
    async def send_resume(self, user_input):
        """Send resume command with user modifications."""
        if not self.connected or not self.ws:
            logger.warning("websocket_not_connected_for_resume")
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
            
            logger.info("websocket_resume_sent", message_id=message_id)
            return True
            
        except Exception as e:
            logger.error("websocket_resume_error", error=str(e))
            return False
    
    async def close(self):
        """Close WebSocket connection."""
        if self.ws:
            await self.ws.close()
        self.connected = False
        logger.info("websocket_disconnected", client_id=self.client_id)


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
                    # Handle both string and dict formats
                    if isinstance(task, dict):
                        task_content = task.get('content', 'Unknown task')
                    else:
                        task_content = str(task)
                    yield Static(f"{i}. {task_content}")
            else:
                yield Static("No plan available")
                
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
                   user_input=self.user_input,
                   input_length=len(self.user_input))
        self.dismiss(self.user_input)
        # Prevent event from bubbling up
        event.stop()
    
    def on_key(self, event: Key) -> None:
        """Handle key events."""
        if event.key == "escape":
            logger.info("plan_modification_cancelled_via_escape")
            self.dismiss("")


class StatusWidget(Static):
    """Widget to display connection and system status."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connected = False
        self.orchestrator_url = ""
        self.thread_id = ""
        self.current_task_id = None
        self.update_display()
        
    def set_connection_info(self, orchestrator_url: str, thread_id: str):
        """Set connection information."""
        self.orchestrator_url = orchestrator_url
        self.thread_id = thread_id
        self.update_display()
        
    def update_status(self, connected: bool = None, task_id: Optional[str] = None):
        """Update the status display."""
        if connected is not None:
            self.connected = connected
        if task_id is not None:
            self.current_task_id = task_id
        self.update_display()
        
    def update_display(self):
        """Update the status display."""
        status_icon = "🟢 Connected" if self.connected else "🔴 Disconnected"
        
        status_parts = [status_icon]
        if self.orchestrator_url:
            status_parts.append(f"URL: {self.orchestrator_url}")
        if self.thread_id:
            status_parts.append(f"Thread: {self.thread_id}")
        if self.current_task_id:
            status_parts.append(f"Task: {self.current_task_id}")
            
        status_text = " | ".join(status_parts)
        self.update(status_text)


class PlanStatusWidget(Static):
    """Widget to display plan status and execution progress with live SSE updates."""
    
    plan_tasks = reactive([])
    current_step = reactive("")
    execution_status = reactive("idle")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.plan_data = []
        self.completed_steps = []
        self.failed_steps = []
        self.current_step_index = -1
        self.current_task_id = None
        self.plan_status = "idle"  # "idle", "in_progress", "completed", "failed"
        self.update_display()
        
    def update_plan(self, plan: List[str]):
        """Update the plan display with new plan steps."""
        self.plan_data = plan
        self.plan_tasks = plan
        self.current_step_index = -1
        self.update_display()
        
    def update_execution_status(self, step: str, status: str = "executing"):
        """Update which step is currently executing."""
        self.current_step = step
        self.execution_status = status
        
        # Find the step index
        if step in self.plan_data:
            self.current_step_index = self.plan_data.index(step)
        
        self.update_display()
        
    def mark_step_complete(self, step_index: int):
        """Mark a specific step as complete."""
        if 0 <= step_index < len(self.plan_data):
            self.current_step_index = step_index
            self.execution_status = "completed"
            self.update_display()
        
    def handle_sse_plan_created(self, data: Dict[str, Any]):
        """Handle plan_created SSE event."""
        if data.get("task_id") != self.current_task_id:
            return  # Not for our current task
            
        plan_steps = data.get("plan_steps", [])
        
        # Preserve completed steps that still exist in the new plan
        if self.plan_data:  # Only preserve if we had a previous plan
            preserved_completed = [step for step in self.completed_steps if step in plan_steps]
            preserved_failed = [step for step in self.failed_steps if step in plan_steps]
        else:
            # First plan creation - start fresh
            preserved_completed = []
            preserved_failed = []
        
        self.plan_data = plan_steps
        self.plan_tasks = plan_steps
        self.completed_steps = preserved_completed
        self.failed_steps = preserved_failed
        self.plan_status = "in_progress"
        self.update_display()
    
    def handle_sse_task_started(self, data: Dict[str, Any]):
        """Handle task_started SSE event."""
        if data.get("task_id") != self.current_task_id:
            return
            
        task_desc = data.get("task_description", "")
        step_number = data.get("step_number", 1)
        
        # Find the step in our plan data
        for i, step in enumerate(self.plan_data):
            if step == task_desc or i == (step_number - 1):
                self.current_step_index = i
                self.current_step = task_desc
                self.execution_status = "executing" 
                break
        
        self.update_display()
    
    def handle_sse_task_completed(self, data: Dict[str, Any]):
        """Handle task_completed SSE event."""
        if data.get("task_id") != self.current_task_id:
            return
            
        task_desc = data.get("task_description", "")
        status = data.get("status", "success")
        
        logger.info("task_completion_tracking",
                   task_desc=task_desc[:50],
                   status=status,
                   completed_before=len(self.completed_steps),
                   failed_before=len(self.failed_steps))
        
        if status == "success":
            if task_desc not in self.completed_steps:
                self.completed_steps.append(task_desc)
                logger.info("task_marked_completed", 
                           task_desc=task_desc[:50],
                           total_completed=len(self.completed_steps))
            # Remove from failed if it was there
            if task_desc in self.failed_steps:
                self.failed_steps.remove(task_desc)
        else:
            if task_desc not in self.failed_steps:
                self.failed_steps.append(task_desc)
            # Remove from completed if it was there  
            if task_desc in self.completed_steps:
                self.completed_steps.remove(task_desc)
        
        self.execution_status = "completed" if status == "success" else "failed"
        self.update_display()
    
    def handle_sse_plan_modified(self, data: Dict[str, Any]):
        """Handle plan_modified SSE event."""
        if data.get("task_id") != self.current_task_id:
            return
            
        new_plan = data.get("new_plan", [])
        self.plan_data = new_plan
        self.plan_tasks = new_plan
        
        # Intelligently preserve completion status when plan structure changes
        # Keep completed/failed steps that still exist in new plan
        preserved_completed = [step for step in self.completed_steps if step in new_plan]
        preserved_failed = [step for step in self.failed_steps if step in new_plan]
        
        # For steps that were completed in old plan but have similar wording in new plan,
        # try to match them (this handles cases where step text is slightly modified)
        for old_completed in self.completed_steps:
            if old_completed not in new_plan:
                # Look for similar step in new plan
                for new_step in new_plan:
                    if new_step not in preserved_completed and len(new_step) > 10:
                        # Simple similarity check - if they share significant common words
                        old_words = set(old_completed.lower().split())
                        new_words = set(new_step.lower().split())
                        common_words = old_words.intersection(new_words)
                        if len(common_words) >= 3:  # At least 3 words in common
                            preserved_completed.append(new_step)
                            break
        
        self.completed_steps = preserved_completed
        self.failed_steps = preserved_failed
        
        self.update_display()
    
    def handle_sse_plan_updated(self, data: Dict[str, Any]):
        """Handle plan_updated SSE event."""
        if data.get("task_id") != self.current_task_id:
            return
            
        # Update plan structure but preserve our completion tracking
        self.plan_data = data.get("plan_steps", self.plan_data)
        
        # Only update completed/failed steps if server provides them, otherwise preserve client tracking
        server_completed = data.get("completed_steps", [])
        server_failed = data.get("failed_steps", [])
        
        # If server provides completion data, use it; otherwise keep client tracking
        if server_completed or server_failed:
            self.completed_steps = server_completed
            self.failed_steps = server_failed
        # If no server completion data, keep our client-side tracking intact
        
        self.current_step = data.get("current_step")
        self.plan_status = data.get("status", "in_progress")
        
        # Find current step index
        if self.current_step and self.current_step in self.plan_data:
            self.current_step_index = self.plan_data.index(self.current_step)
        
        self.update_display()
    
    def set_task_id(self, task_id: str):
        """Set the current task ID to filter SSE events."""
        self.current_task_id = task_id
        
    def reset_plan(self):
        """Reset the plan state."""
        self.plan_data = []
        self.completed_steps = []
        self.failed_steps = []
        self.current_step_index = -1
        self.current_task_id = None
        self.plan_status = "idle"
        self.update_display()

    def update_display(self):
        """Refresh the plan display with enhanced status indicators."""
        if not self.plan_data:
            content = """[bold #7dd3fc]📋 Execution Plan[/bold #7dd3fc]

[dim #8b949e]No plan available[/dim #8b949e]"""
        else:
            # Plan header with status
            status_indicator = {
                "idle": "[dim #8b949e]●[/dim #8b949e] Idle",
                "in_progress": "[yellow]●[/yellow] In Progress", 
                "completed": "[green]●[/green] Completed",
                "failed": "[red]●[/red] Failed"
            }.get(self.plan_status, "[dim]●[/dim] Unknown")
            
            content_lines = [
                f"[bold #7dd3fc]📋 Execution Plan[/bold #7dd3fc] {status_indicator}",
                ""
            ]
            
            for i, step in enumerate(self.plan_data):
                if step in self.failed_steps:
                    # Failed steps - red with X
                    content_lines.append(f"[red]✗ {i+1}. {step}[/red]")
                elif step in self.completed_steps:
                    # Completed steps - green with checkmark
                    content_lines.append(f"[green]✓ {i+1}. {step}[/green]")
                elif step == self.current_step and self.execution_status == "executing":
                    # Currently executing - yellow with arrow
                    content_lines.append(f"[yellow]▶ {i+1}. {step}[/yellow]")
                else:
                    # Pending steps - dim
                    content_lines.append(f"[dim #8b949e]□ {i+1}. {step}[/dim #8b949e]")
            
            content = "\n".join(content_lines)
        
        self.update(content)


class ConversationWidget(ScrollableContainer):
    """Widget to display conversation history - exact main branch style."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.message_count = 0
        
    def compose(self) -> ComposeResult:
        """Initial welcome message."""
        yield Static(
            "[dim #8b949e]Welcome! Ask me anything about your CRM, projects, or IT systems.[/dim #8b949e]",
            id="welcome-message"
        )
        
    async def add_user_message(self, message: str):
        """Add a user message to the conversation."""
        self.message_count += 1
        
        # Remove welcome message if this is the first real message
        if self.message_count == 1:
            try:
                welcome = self.query_one("#welcome-message")
                welcome.remove()
            except Exception:
                pass
        
        # Create separate widgets for label and content (like main branch)
        # Get user_id from the app
        user_id = self.app.user_id if hasattr(self.app, 'user_id') else "default_user"
        label_text = f"[bold cyan]USER ({user_id}):[/bold cyan]"
        label_widget = Static(label_text, classes="message-label")
        content_widget = Markdown(message, classes="message-content")
        
        # Mount both widgets
        await self.mount(label_widget)
        await self.mount(content_widget)
        self.scroll_end(animate=True)
        
    async def add_assistant_message(self, message: str):
        """Add an assistant message to the conversation."""
        # Create separate widgets for label and content (like main branch)
        label_widget = Static("[bold green]ASSISTANT:[/bold green]", classes="message-label")
        content_widget = Markdown(message, classes="message-content")
        
        # Mount both widgets  
        await self.mount(label_widget)
        await self.mount(content_widget)
        self.scroll_end(animate=True)
        
    async def add_system_message(self, message: str, message_type: str = "info"):
        """Add a system message to the conversation."""
        if message_type == "error":
            color = "#f85149"
            prefix = "❌ Error:"
        elif message_type == "processing":
            # Check if a spinner already exists and remove it
            try:
                existing_spinner = self.query_one("#processing-spinner")
                if existing_spinner:
                    existing_spinner.remove()
            except Exception:
                pass  # No existing spinner, that's fine
            
            # Create a subtle inline processing message with ASCII spinner
            processing_widget = Static(
                "[dim #7dd3fc]⠋[/dim #7dd3fc] [dim #8b949e]Processing...[/dim #8b949e]",
                classes="processing-message",
                id="processing-spinner"
            )
            await self.mount(processing_widget)
            self.scroll_end(animate=True)
            
            # Start the spinner animation
            self._animate_processing_spinner(processing_widget)
            return processing_widget  # Return reference so we can remove it later
        else:
            color = "#8b949e"
            prefix = ""

        system_widget = Static(
            f"[{color}]{prefix}[/{color}] [dim]{message}[/dim]"
        )
        await self.mount(system_widget)
        self.scroll_end(animate=True)
        return system_widget
    
    def _animate_processing_spinner(self, widget):
        """Animate a sophisticated ASCII art spinner for processing indication."""
        async def animate():
            # Advanced ASCII spinner with more sophisticated characters
            spinner_frames = [
                "⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"
            ]
            # Fallback for terminals that don't support Braille patterns
            fallback_frames = [
                "◐", "◓", "◑", "◒"
            ]
            # Simple fallback if even those don't work
            simple_frames = [
                "●", "○", "◯", "○"
            ]
            
            current_index = 0
            frames_to_use = spinner_frames  # Start with the most advanced
            
            while widget.parent:  # Continue while widget is still mounted
                try:
                    frame = frames_to_use[current_index % len(frames_to_use)]
                    widget.update(f"[dim #7dd3fc]{frame}[/dim #7dd3fc] [dim #8b949e]Processing...[/dim #8b949e]")
                    current_index += 1
                    await asyncio.sleep(0.1)  # Smooth 10 FPS animation
                except Exception:
                    # If there's an encoding issue, try fallback frames
                    if frames_to_use == spinner_frames:
                        frames_to_use = fallback_frames
                        current_index = 0
                        continue
                    elif frames_to_use == fallback_frames:
                        frames_to_use = simple_frames
                        current_index = 0
                        continue
                    else:
                        break  # Widget was removed or other error
        
        # Start the animation task
        asyncio.create_task(animate())


class OrchestatorApp(App):
    """Main Textual application - exact main branch structure."""
    
    CSS_PATH = "textual_styles.tcss"
    
    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+q", "quit", "Quit"),
        ("escape", "interrupt", "Interrupt"),
    ]
    
    def __init__(self, orchestrator_url: str = "http://localhost:8000", thread_id: Optional[str] = None, user_id: Optional[str] = None):
        super().__init__()
        self.orchestrator_url = orchestrator_url
        # Use standardized thread ID format for orchestrator
        self.thread_id = thread_id or create_thread_id("orchestrator", f"{uuid.uuid4().hex[:8]}")
        self.user_id = user_id or "default_user"  # Default user ID if not provided
        self.a2a_client = A2AClient()
        self._cleanup_done = False
        self.conversation_history = []
        self.current_task_id = None
        
        # GraphInterrupt state management
        self.interrupted_task_id = None
        self.interrupt_context = None
        self.waiting_for_user_response = False
        
        # Initialize widgets as instance variables
        self.conversation_widget = None
        self.status_widget = None
        self.plan_widget = None
        self.tool_events_widget = None
        
        # SSE connection for live plan updates
        self.sse_session = None
        self.sse_task = None
        self.sse_url = f"{orchestrator_url}/a2a/stream"
        
        # WebSocket controller for interrupts
        self.ws_controller = None
        self.is_processing = False
        self.interrupt_requested = False
        self.processing_done = asyncio.Event()
        
        logger.info("textual_app_initialized", 
                   orchestrator_url=orchestrator_url,
                   thread_id=self.thread_id,
                   sse_url=self.sse_url)
    
    def compose(self) -> ComposeResult:
        """Compose the UI layout - exact main branch structure."""
        yield Header()
        
        # Main banner with compact ASCII logo
        compact_logo = format_compact_logo_for_textual(ENTERPRISE_ASSISTANT_COMPACT_LOGO)
        yield Static(
            f"{compact_logo}\n"
            "[dim #94a3b8]Powered by Plan-and-Execute Multi-Agent Orchestration[/dim #94a3b8]",
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
            
            # Right panel - split between plan/tools and memory graph
            with Vertical(classes="right-panel"):
                # Top half - combined plan status and tool events
                with Vertical(classes="plan-tools-panel"):
                    # Plan status (smaller section)
                    self.plan_widget = PlanStatusWidget(classes="plan-status plan-section")
                    yield self.plan_widget
                    
                    # Tool events log (larger section)
                    self.tool_events_widget = ToolEventsWidget(classes="tool-events")
                    yield self.tool_events_widget
                
                # Bottom half - memory graph
                from src.utils.ui.memory_graph_widget import MemoryGraphWidget
                self.memory_graph_widget = MemoryGraphWidget(classes="memory-graph half-height")
                yield self.memory_graph_widget
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize the application when mounted."""
        logger.info("textual_app_mounted", thread_id=self.thread_id)
        
        # Set up status widget
        self.status_widget.set_connection_info(self.orchestrator_url, self.thread_id)
        self.status_widget.update_status(connected=True)  # Assume connected initially
        
        # Focus on input
        self.query_one("#message-input", Input).focus()
        logger.info("input_focused", thread_id=self.thread_id)
        
        # Start SSE connection for live plan updates
        self.start_sse_connection()
    
    @on(Input.Submitted, "#message-input")
    async def handle_input(self, event: Input.Submitted) -> None:
        """Handle user input submission - exact main branch behavior."""
        user_input = event.value.strip()
        if not user_input:
            return
        
        # Clear the input
        event.input.value = ""
        
        # Add user message to conversation
        await self.conversation_widget.add_user_message(user_input)
        
        # Send to orchestrator (runs in background worker)
        self.send_to_orchestrator(user_input)
    
    @work(exclusive=False)
    async def send_to_orchestrator(self, user_input: str) -> None:
        """Send user input to the orchestrator via A2A protocol."""
        spinner_widget = None
        try:
            # Check if this is a response to an interrupted task
            if self.waiting_for_user_response and self.interrupted_task_id:
                # Resume the interrupted task with user's response
                task_id = self.interrupted_task_id
                context = {
                    "thread_id": self.thread_id,
                    "user_id": self.user_id,
                    "resume_from_interrupt": True,
                    "user_response": user_input,
                    "interrupt_context": self.interrupt_context
                }
                
                logger.info("resuming_interrupted_task",
                           task_id=task_id,
                           user_response=user_input[:100],
                           has_interrupt_context=bool(self.interrupt_context))
                
                # Clear interrupt state
                self.waiting_for_user_response = False
                self.interrupted_task_id = None
                self.interrupt_context = None
            else:
                # Generate new task ID for fresh requests
                task_id = f"task-{uuid.uuid4().hex[:8]}"
                context = {
                    "thread_id": self.thread_id,
                    "user_id": self.user_id,
                    "conversation_history": self.conversation_history[-5:] if self.conversation_history else []  # Last 5 exchanges for context
                }
                
                logger.info("sending_new_task_to_orchestrator",
                           task_id=task_id,
                           user_input=user_input[:100])
            
            self.current_task_id = task_id
            
            # Set task ID for plan widget to track events  
            self.set_plan_task_id(task_id)
            
            # Show processing spinner
            spinner_widget = await self.conversation_widget.add_system_message(
                "", "processing"
            )
            
            # Set processing state
            self.is_processing = True
            
            # Initialize WebSocket controller if not already done
            if not self.ws_controller:
                self.ws_controller = TextualWebSocketController(self.orchestrator_url, self.thread_id)
                await self.ws_controller.connect()
            
            # Update status
            self.status_widget.update_status(connected=True, task_id=task_id)
            
            # Create A2A task
            task = A2ATask(
                id=task_id,
                instruction=user_input,
                context=context,
                state_snapshot={}
            )
            
            # Send A2A request to orchestrator
            response = await self.a2a_client.process_task(
                endpoint=self.orchestrator_url + "/a2a",
                task=task
            )
            
            # Remove spinner
            if spinner_widget:
                spinner_widget.remove()
            
            # Handle response
            if response.get("status") == "completed":
                # Extract artifacts and display results
                artifacts = response.get("artifacts", [])
                
                if artifacts:
                    for artifact in artifacts:
                        content = artifact.get("content", "")
                        await self.conversation_widget.add_assistant_message(content)
                else:
                    await self.conversation_widget.add_assistant_message("Task completed successfully.")
                
                # Handle plan data
                metadata = response.get("metadata", {})
                if "plan" in metadata and metadata["plan"]:
                    self.plan_widget.update_plan(metadata["plan"])
                    logger.info("plan_updated", plan_steps=len(metadata["plan"]))
            
            elif response.get("status") == "interrupted":
                # Handle GraphInterrupt properly using status-based detection
                metadata = response.get("metadata", {})
                interrupt_value = metadata.get("interrupt_value", "")
                interrupt_type = metadata.get("interrupt_type", "model")
                
                if interrupt_type == "user_escape":
                    # This is a user-initiated interrupt (escape key)
                    # The interrupt flow has already been handled by handle_interrupt
                    logger.info("user_escape_interrupt_acknowledged",
                               task_id=task_id,
                               interrupt_value=interrupt_value)
                    # Don't set waiting_for_user_response since we're handling it differently
                else:
                    # This is a model-initiated interrupt (HumanInputTool)
                    # Store interrupt state for resume
                    self.interrupted_task_id = task_id
                    self.interrupt_context = metadata
                    self.waiting_for_user_response = True
                    
                    # Display the clarification request naturally
                    # The interrupt_value should now contain the LLM's natural question
                    if isinstance(interrupt_value, str) and interrupt_value.strip():
                        # Clean up any escaped newlines and display the natural question
                        clarification_text = interrupt_value.replace("\\n", "\n").strip()
                        await self.conversation_widget.add_assistant_message(clarification_text)
                    else:
                        # Fallback: show artifact content
                        artifacts = response.get("artifacts", [])
                        if artifacts and artifacts[0].get("content"):
                            content = artifacts[0]["content"].replace("\\n", "\n").strip()
                            await self.conversation_widget.add_assistant_message(content)
                        else:
                            await self.conversation_widget.add_assistant_message(
                                "I need additional information to continue. Please provide your response."
                            )
                    
                    # Update status to show waiting for user
                    await self.conversation_widget.add_system_message(
                        "Waiting for your response to continue...", "info"
                    )
                
                logger.info("graph_interrupt_detected",
                           task_id=task_id,
                           waiting_for_response=True,
                           interrupt_preview=str(interrupt_value)[:200])
            
            elif response.get("status") == "failed":
                error_msg = response.get("error", "Unknown error occurred")
                # Regular error
                await self.conversation_widget.add_system_message(error_msg, "error")
            
            else:
                status = response.get("status", "unknown")
                await self.conversation_widget.add_system_message(f"Status: {status}")
            
            # Clear task from status only if not waiting for user response
            if not self.waiting_for_user_response:
                self.status_widget.update_status(connected=True, task_id=None)
                # Reset processing state
                self.is_processing = False
            
        except Exception as e:
            # Remove spinner on error too
            if spinner_widget:
                spinner_widget.remove()
                
            logger.error("orchestrator_request_error", 
                        error=str(e),
                        task_id=self.current_task_id)
            
            await self.conversation_widget.add_system_message(
                f"Connection error: {str(e)}", "error"
            )
            
            # Update status to show disconnected
            self.status_widget.update_status(connected=False, task_id=None)
            
            # Reset processing state on error
            self.is_processing = False
    
    def start_sse_connection(self):
        """Start SSE connection for live plan updates."""
        if self.sse_task is None or self.sse_task.done():
            self.sse_task = asyncio.create_task(self._sse_connection_loop())
            logger.info("sse_connection_started", sse_url=self.sse_url)
    
    async def _sse_connection_loop(self):
        """Main SSE connection loop with automatic reconnection."""
        while True:
            try:
                await self._connect_sse()
            except Exception as e:
                logger.error("sse_connection_error", error=str(e), sse_url=self.sse_url)
                # Wait before reconnecting
                await asyncio.sleep(5)
    
    async def _connect_sse(self):
        """Connect to SSE stream and handle events."""
        if self.sse_session is None or self.sse_session.closed:
            # Create new session with proper configuration
            connector = aiohttp.TCPConnector(
                limit=10,
                limit_per_host=5,
                enable_cleanup_closed=True,
                force_close=True  # Force connection close on error
            )
            timeout = aiohttp.ClientTimeout(
                total=None,  # No total timeout for SSE
                connect=30,  # 30 second connection timeout
                sock_read=60  # 60 second read timeout (covers heartbeat)
            )
            self.sse_session = aiohttp.ClientSession(
                connector=connector,
                connector_owner=True,
                timeout=timeout
            )
        
        logger.info("sse_connecting", sse_url=self.sse_url)
        
        try:
            async with self.sse_session.get(
                self.sse_url,
                headers={'Accept': 'text/event-stream'}
            ) as response:
                logger.info("sse_connected", status=response.status, headers=dict(response.headers))
                
                if response.status != 200:
                    logger.error("sse_connection_failed", status=response.status)
                    return
                
                # Track current event being parsed
                logger.info("sse_stream_reading_started")
                
                try:
                    async for line_bytes in response.content:
                        line = line_bytes.decode('utf-8').strip()
                        
                        if not line:
                            continue
                        
                        logger.debug("sse_line_received", line=line[:100])
                        
                        # Parse main branch format: "data: {"event": "type", "data": {...}}"
                        if line.startswith("data: "):
                            data_json = line[6:]  # Remove "data: " prefix
                            logger.info("sse_data_received", data_preview=data_json[:100])
                            try:
                                event_payload = json.loads(data_json)
                                event_type = event_payload.get('event')
                                event_data = event_payload.get('data', {})
                                
                                if event_type:
                                    logger.info("sse_event_parsed", event_type=event_type, has_data=bool(event_data))
                                    await self._handle_sse_event(event_type, event_data)
                                else:
                                    logger.warning("sse_event_missing_type", payload=event_payload)
                            except json.JSONDecodeError as e:
                                logger.error("sse_json_decode_error", error=str(e), data=data_json[:100])
                            
                except asyncio.TimeoutError:
                    # Read timeout - this is OK, we have heartbeats
                    logger.debug("sse_read_timeout_normal")
                    # Don't need continue here - timeout means we'll reconnect
                except (aiohttp.ClientError, aiohttp.ClientPayloadError) as e:
                    # Connection error - will reconnect
                    logger.info("sse_connection_lost", error=str(e))
                    raise
                except Exception as stream_e:
                    # Only log unexpected errors
                    if "Not enough data" not in str(stream_e):
                        logger.error("sse_stream_reading_error", error=str(stream_e))
                    raise
        except (aiohttp.ClientError, aiohttp.ClientPayloadError):
            # Expected connection errors - will reconnect
            logger.info("sse_disconnected_will_reconnect")
            raise
        except Exception as e:
            # Unexpected errors
            logger.error("sse_stream_error", error=str(e))
            raise
    
    async def _handle_sse_event(self, event_type: str, data: Dict[str, Any]):
        """Handle incoming SSE events."""
        logger.info("sse_event_received", 
                   event_type=event_type, 
                   task_id=data.get("task_id"),
                   current_task_id=self.current_task_id)
        
        # Route events to plan widget
        if self.plan_widget:
            if event_type == "plan_created":
                self.plan_widget.handle_sse_plan_created(data)
            elif event_type == "task_started":
                self.plan_widget.handle_sse_task_started(data)
            elif event_type == "task_completed":
                self.plan_widget.handle_sse_task_completed(data)
            elif event_type == "plan_modified":
                self.plan_widget.handle_sse_plan_modified(data)
            elif event_type == "plan_updated":
                self.plan_widget.handle_sse_plan_updated(data)
        
        # Handle human input requested events
        if event_type == "human_input_requested":
            # Reset processing state when human input is needed
            self.is_processing = False
            # Remove any existing spinner
            try:
                existing_spinner = self.query_one("#processing-spinner")
                if existing_spinner:
                    existing_spinner.remove()
            except Exception:
                pass
            
        # Route memory events to memory graph widget
        if self.memory_graph_widget:
            if event_type in ["memory_node_added", "memory_edge_added", 
                            "memory_graph_snapshot", "memory_node_accessed"]:
                self.memory_graph_widget.handle_sse_memory_update({
                    "event_type": event_type.replace("memory_", ""),
                    **data
                })
        
        # Route tool events to tool events widget
        tool_event_types = [
            "agent_call_started",
            "agent_call_completed", 
            "agent_call_failed",
            "tool_selected",
            "direct_response",
            "web_search_started",
            "web_search_completed",
            "human_input_requested",
            "human_input_received"
        ]
        
        if event_type in tool_event_types and self.tool_events_widget:
            self.tool_events_widget.handle_sse_event(event_type, data)
        
        # Handle LLM context events
        if event_type == "llm_context":
            logger.info("llm_context_event_received", 
                       context_type=data.get("context_type"),
                       metadata=data.get("metadata"))
            
            # Route to memory graph widget which has the "What LLM Sees" section
            if self.memory_graph_widget:
                self.memory_graph_widget.handle_llm_context_update({
                    "event_type": "llm_context",
                    **data
                })
    
    def set_plan_task_id(self, task_id: str):
        """Set the current task ID for plan tracking."""
        if self.plan_widget:
            self.plan_widget.set_task_id(task_id)
    
    def action_quit(self) -> None:
        """Quit the application."""
        logger.info("textual_app_quit", thread_id=self.thread_id)
        
        # Schedule async cleanup
        asyncio.create_task(self._async_cleanup())
        
        self.exit()
    
    def action_interrupt(self) -> None:
        """Handle interrupt action (ESC key) using Textual's action system."""
        logger.info("escape_key_pressed",
                   is_processing=self.is_processing,
                   has_plan=bool(self.plan_widget and self.plan_widget.plan_tasks),
                   has_ws_controller=bool(self.ws_controller))
        
        if self.is_processing and self.plan_widget and self.plan_widget.plan_tasks:
            self.interrupt_requested = True
            logger.info("interrupt_requested_via_key")
            # Use Textual's work decorator for async handling
            self.handle_interrupt()
        else:
            # Show status if interrupt not available
            if not self.is_processing:
                logger.warning("interrupt_unavailable_not_processing")
                self.status_widget.update("No active plan to interrupt")
            else:
                logger.warning("interrupt_unavailable_no_plan")
                self.status_widget.update("No plan currently executing")
    
    @work(exclusive=True)
    async def handle_interrupt(self):
        """Handle interrupt request using Textual's work decorator."""
        try:
            logger.info("handle_interrupt_start")
            
            # Reset processing state first to prevent UI lock
            self.is_processing = False
            self.status_widget.update("⏸ Execution interrupted - gathering modifications...")
            
            # Show plan modification screen
            current_plan = self.plan_widget.plan_tasks if self.plan_widget else []
            logger.info("showing_plan_modification_modal", 
                       plan_task_count=len(current_plan))
            
            modification_input = await self.push_screen_wait(PlanModificationScreen(current_plan))
            
            logger.info("plan_modification_modal_result",
                       component="client", 
                       modification_input=modification_input,
                       has_input=bool(modification_input))
            
            if modification_input:
                # Send interrupt and resume via WebSocket
                try:
                    logger.info("sending_websocket_interrupt")
                    # Send interrupt first
                    interrupt_success = await self.ws_controller.send_interrupt("user_escape")
                    
                    logger.info("websocket_interrupt_result", 
                               success=interrupt_success)
                    
                    if interrupt_success:
                        self.status_widget.update("⏸ Execution interrupted successfully")
                        
                        logger.info("sending_websocket_resume", 
                                   modification_input=modification_input)
                        
                        # Send resume with modifications
                        resume_success = await self.ws_controller.send_resume(modification_input)
                        
                        logger.info("websocket_resume_result",
                                   component="client", 
                                   success=resume_success)
                        
                        if resume_success:
                            self.status_widget.update("▶ Resume request sent successfully")
                            await self.conversation_widget.add_system_message(
                                "💡 Plan modification applied successfully!"
                            )
                            
                            # The orchestrator should now continue execution
                            # We don't need to make a new request - the graph will resume
                            # when the interrupt flag is cleared
                            logger.info("interrupt_resume_complete",
                                       task_id=self.current_task_id,
                                       thread_id=self.thread_id)
                            
                            # Reset interrupt flag
                            self.interrupt_requested = False
                            
                            # Keep processing state true since execution continues
                            self.is_processing = True
                        else:
                            self.status_widget.update("⚠ Failed to send resume request")
                            await self.conversation_widget.add_system_message(
                                "⚠ Failed to apply plan modifications. Please try again."
                            )
                    else:
                        self.status_widget.update("⚠ Failed to interrupt execution")
                        await self.conversation_widget.add_system_message(
                            "⚠ Failed to interrupt execution. The plan may continue running."
                        )
                        
                except Exception as e:
                    logger.error("websocket_interrupt_error", error=str(e))
                    self.status_widget.update(f"⚠ Error: {str(e)}")
                    await self.conversation_widget.add_system_message(
                        f"⚠ Error during interrupt: {str(e)}"
                    )
            else:
                # User cancelled the modification
                logger.info("interrupt_cancelled_by_user")
                self.status_widget.update("▶ Execution continuing...")
                self.is_processing = True
                
        except Exception as e:
            logger.error("handle_interrupt_error", 
                        error=str(e),
                        traceback=True)
            self.status_widget.update(f"⚠ Interrupt error: {str(e)}")
        finally:
            # Reset interrupt flag
            self.interrupt_requested = False
    
    async def _async_cleanup(self):
        """Async cleanup of resources."""
        if self._cleanup_done:
            return
        
        self._cleanup_done = True
        
        try:
            # Cancel SSE task
            if self.sse_task and not self.sse_task.done():
                self.sse_task.cancel()
                try:
                    await self.sse_task
                except asyncio.CancelledError:
                    pass
            
            # Close SSE session properly
            if self.sse_session and not self.sse_session.closed:
                await self.sse_session.close()
                logger.info("sse_session_closed")
            
            # Close A2A client properly
            if hasattr(self.a2a_client, 'close'):
                await self.a2a_client.close()
                logger.info("a2a_client_closed")
            
            # Close WebSocket controller
            if self.ws_controller:
                await self.ws_controller.close()
                logger.info("websocket_controller_closed")
        except Exception as e:
            logger.error("cleanup_error", error=str(e))


async def run_startup_animation():
    """Run the impressive banner animation before starting Textual interface."""
    try:
        if app_config.get('conversation.animated_banner_enabled', True):
            # Clear screen and run the actual banner animation
            print("\\033[2J\\033[H", end='')  # Clear screen
            await animated_banner_display(ENTERPRISE_ASSISTANT_BANNER)
            
            # Brief pause to appreciate the banner
            await asyncio.sleep(1.5)
            
            # Clear screen before starting Textual
            print("\\033[2J\\033[H", end='')
            
            logger.info("banner_animation_complete")
        else:
            # Just clear screen if animation is disabled
            print("\\033[2J\\033[H", end='')
            
    except Exception as e:
        logger.error("banner_animation_error", error=str(e))
        # Clear screen and continue even if animation fails
        print("\\033[2J\\033[H", end='')


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Textual CLI for Plan-and-Execute Orchestrator")
    parser.add_argument("--url", default="http://localhost:8000", 
                       help="Orchestrator URL (default: http://localhost:8000)")
    parser.add_argument("--thread-id", help="Specific thread ID to use")
    parser.add_argument("--user-id", help="User ID for memory namespace (default: default_user)")
    parser.add_argument("--no-animation", action="store_true", 
                       help="Skip startup animation")
    
    args = parser.parse_args()
    
    # Override animation setting if requested
    if args.no_animation:
        import os
        os.environ["ANIMATED_BANNER_ENABLED"] = "false"
    
    # Run the startup animation first
    try:
        asyncio.run(run_startup_animation())
    except Exception as e:
        logger.error("startup_animation_failed", error=str(e))
    
    # Now start the Textual app
    app = OrchestatorApp(orchestrator_url=args.url, thread_id=args.thread_id, user_id=args.user_id)
    app.run()


if __name__ == "__main__":
    main()