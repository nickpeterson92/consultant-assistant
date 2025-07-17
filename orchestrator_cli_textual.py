#!/usr/bin/env python3
"""Textual-based CLI client for the orchestrator - handles all real-time updates properly."""

import sys
import os
import asyncio
import time
import uuid
import json
import aiohttp
from typing import List, Dict, Any, Optional

# Add the project root to Python path for src imports
sys.path.insert(0, os.path.dirname(__file__))

from textual.app import App, ComposeResult
from textual.widgets import (
    Header, Footer, Input, Static, DataTable, 
    LoadingIndicator, ProgressBar, Label, Button
)
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.events import Key
from textual import on

from src.a2a import A2AClient
from src.utils.config import (
    get_conversation_config, ENTERPRISE_ASSISTANT_BANNER
)
from src.utils.logging import get_logger

# Initialize logger
logger = get_logger()


class PlanStatusWidget(Static):
    """Widget for displaying execution plan status with real-time updates."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.plan_tasks: List[Dict[str, Any]] = []
        self.completed_steps: List[str] = []
        self.failed_steps: List[str] = []
        self.skipped_steps: List[str] = []
        self.current_step: str = ""
    
    def update_plan(self, tasks: List[Dict[str, Any]]):
        """Update the plan tasks and refresh display."""
        self.plan_tasks = tasks
        self.refresh_display()
    
    def update_progress(self, **kwargs):
        """Update progress state and refresh display."""
        if 'completed_steps' in kwargs:
            for step in kwargs['completed_steps']:
                if step not in self.completed_steps:
                    self.completed_steps.append(step)
        
        if 'failed_steps' in kwargs:
            for step in kwargs['failed_steps']:
                if step not in self.failed_steps:
                    self.failed_steps.append(step)
        
        if 'skipped_steps' in kwargs:
            for step in kwargs['skipped_steps']:
                if step not in self.skipped_steps:
                    self.skipped_steps.append(step)
        
        if 'current_step' in kwargs:
            self.current_step = kwargs['current_step']
        
        self.refresh_display()
    
    def refresh_display(self):
        """Refresh the plan display with current state."""
        if not self.plan_tasks:
            self.update("")
            return
        
        content = []
        content.append("[bold blue]Plan Status[/bold blue]")
        content.append("")
        content.append("[cyan]Execution Plan[/cyan]")
        
        for i, task in enumerate(self.plan_tasks, 1):
            task_content = task.get('content', 'Unknown task')
            
            # Determine status
            if task_content in self.completed_steps:
                icon = "[green]✓[/green]"
                style = "green"
            elif task_content in [fs.split(' (Error:')[0] for fs in self.failed_steps]:
                icon = "[red]✗[/red]"
                style = "red"
            elif task_content in self.skipped_steps:
                icon = "[yellow]−[/yellow]"
                style = "yellow"
            elif task_content == self.current_step:
                icon = "[blue]→[/blue]"
                style = "blue bold"
            else:
                icon = "[white]□[/white]"
                style = "white"
            
            content.append(f"{icon} {i}. [{style}]{task_content}[/{style}]")
        
        self.update("\n".join(content))


class ConversationWidget(Static):
    """Widget for displaying conversation history."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.messages: List[str] = []
    
    def add_message(self, role: str, content: str):
        """Add a message to the conversation."""
        logger.info("conversation_add_message", 
                   role=role, 
                   content_length=len(content),
                   content_preview=content[:100])
        
        if role == "user":
            self.messages.append(f"[bold cyan]USER:[/bold cyan] {content}")
        else:
            self.messages.append(f"[bold green]ASSISTANT:[/bold green] {content}")
        
        # Keep only last 20 messages to prevent memory issues
        if len(self.messages) > 20:
            self.messages = self.messages[-20:]
        
        # Update display
        display_content = "\n".join(self.messages)
        self.update(display_content)
        
        logger.info("conversation_display_updated", 
                   total_messages=len(self.messages),
                   display_length=len(display_content))


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
        
        # Debug logging
        logger.info("textual_app_initialized", thread_id=self.thread_id)
    
    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+q", "quit", "Quit"),
    ]
    
    def compose(self) -> ComposeResult:
        """Compose the UI layout."""
        yield Header()
        
        # Main banner
        yield Static(
            "[bold cyan]Enterprise Assistant[/bold cyan]\n"
            "[dim]Powered by Multi-Agent Orchestration[/dim]",
            classes="header"
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
        
        # Start background tasks
        self.run_worker(self.initialize_connection(), exclusive=True)
    
    async def initialize_connection(self):
        """Initialize connection to orchestrator."""
        try:
            self.status_widget.set_status("Connecting to orchestrator...", processing=True)
            
            # Simple connection test - try to get agent card
            test_result = await self.a2a_client.get_agent_card(f"{self.orchestrator_url}/a2a")
            
            self.status_widget.set_status("Connected! Ready to process requests")
            
        except Exception as e:
            self.status_widget.set_status(f"Connection failed: {str(e)}")
            logger.error("connection_failed", error=str(e))
            # Still allow the app to run for testing
    
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
        
        # Send to orchestrator using SSE streaming like Rich version
        try:
            # Create task data
            task_data = {
                "task": {
                    "id": str(uuid.uuid4()),
                    "instruction": user_input,
                    "context": {"source": "cli_client"},
                    "thread_id": self.thread_id
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
    
    async def process_with_sse_streaming(self, task_data: Dict[str, Any]):
        """Process task with SSE streaming like Rich version."""
        timeout = aiohttp.ClientTimeout(total=120, connect=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            stream_url = f"{self.orchestrator_url}/a2a/stream"
            logger.info("attempting_sse_connection",
                       component="textual_client",
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
                           component="textual_client",
                           status_code=response.status,
                           content_type=response.headers.get('content-type'))
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error("sse_stream_request_failed",
                                component="textual_client",
                                status_code=response.status,
                                error_text=error_text)
                    self.conversation_widget.add_message("assistant", f"Error: HTTP {response.status}: {error_text}")
                    self.is_processing = False
                    self.status_widget.set_status("Error")
                    return
                
                logger.info("sse_stream_processing_start", component="textual_client")
                
                async for line in response.content:
                    if not line:
                        continue
                    
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
                                       component="textual_client",
                                       event_type=event_type,
                                       data_keys=list(data.keys()) if data else [],
                                       raw_line=line[:100])
                            
                            # Process the event
                            await self.process_sse_event(event_type, data)
                            
                        except json.JSONDecodeError as e:
                            logger.warning("sse_json_decode_error",
                                         component="textual_client",
                                         error=str(e),
                                         raw_line=line[:100])
                        except Exception as e:
                            logger.error("sse_event_processing_error",
                                        component="textual_client",
                                        error=str(e),
                                        raw_line=line[:100])
                
                # Processing complete
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
    
    def action_quit(self) -> None:
        """Handle quit action."""
        if self.sse_task:
            self.sse_task.cancel()
        self.exit()
    
    def on_unmount(self) -> None:
        """Cleanup when app unmounts."""
        try:
            # Cancel any running tasks
            if self.sse_task:
                self.sse_task.cancel()
        except Exception as e:
            logger.error("cleanup_error", error=str(e))


def main():
    """Main entry point."""
    app = OrchestatorApp()
    app.run()


if __name__ == "__main__":
    main()