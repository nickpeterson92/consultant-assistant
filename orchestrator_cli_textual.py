#!/usr/bin/env python3
"""Textual-based CLI client for the plan-and-execute orchestrator - exact main branch port."""

import sys
import os
import asyncio
import time
import uuid
import json
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

from src.a2a import A2AClient, A2ATask
from src.utils.config.constants import ENTERPRISE_ASSISTANT_BANNER, ENTERPRISE_ASSISTANT_COMPACT_LOGO
from src.utils.config.unified_config import config as app_config
from src.utils.ui.animations import animated_banner_display, format_compact_logo_for_textual
from src.utils.logging.framework import SmartLogger

# Initialize SmartLogger
logger = SmartLogger("client")


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
    """Widget to display plan status and execution progress - exact main branch style."""
    
    plan_tasks = reactive([])
    current_step = reactive("")
    execution_status = reactive("idle")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.plan_data = []
        self.current_step_index = -1
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
        
    def update_display(self):
        """Refresh the plan display - exact main branch format."""
        if not self.plan_data:
            content = """[bold #7dd3fc]📋 Execution Plan[/bold #7dd3fc]

[dim #8b949e]No plan available[/dim #8b949e]"""
        else:
            content_lines = ["[bold #7dd3fc]📋 Execution Plan[/bold #7dd3fc]", ""]
            
            for i, step in enumerate(self.plan_data):
                if i == self.current_step_index and self.execution_status == "executing":
                    # Currently executing - yellow with arrow
                    content_lines.append(f"[yellow]▶ {i+1}. {step}[/yellow]")
                elif i <= self.current_step_index and self.execution_status == "completed":
                    # Completed steps - green with checkmark
                    content_lines.append(f"[green]✓ {i+1}. {step}[/green]")
                elif i < self.current_step_index:
                    # Previously completed steps - green with checkmark
                    content_lines.append(f"[green]✓ {i+1}. {step}[/green]")
                else:
                    # Pending steps - dim
                    content_lines.append(f"[dim #8b949e]  {i+1}. {step}[/dim #8b949e]")
            
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
            except:
                pass
        
        # Add user message with main branch styling
        user_widget = Static(
            f"[bold #58a6ff]You:[/bold #58a6ff] {message}",
            classes="user-message"
        )
        await self.mount(user_widget)
        self.scroll_end(animate=True)
        
    async def add_assistant_message(self, message: str):
        """Add an assistant message to the conversation."""
        # Add assistant message with main branch styling
        assistant_widget = Static(
            f"[bold #7ee787]Assistant:[/bold #7ee787] {message}",
            classes="assistant-message"
        )
        await self.mount(assistant_widget)
        self.scroll_end(animate=True)
        
    async def add_system_message(self, message: str, message_type: str = "info"):
        """Add a system message to the conversation."""
        if message_type == "error":
            color = "#f85149"
            prefix = "❌ Error:"
        elif message_type == "processing":
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
    
    def __init__(self, orchestrator_url: str = "http://localhost:8000", thread_id: Optional[str] = None):
        super().__init__()
        self.orchestrator_url = orchestrator_url
        self.thread_id = thread_id or f"textual-{uuid.uuid4().hex[:8]}"
        self.a2a_client = A2AClient()
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
        
        logger.info("textual_app_initialized", 
                   orchestrator_url=orchestrator_url,
                   thread_id=self.thread_id)
    
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
            
            # Right panel - plan status
            with Vertical(classes="right-panel"):
                self.plan_widget = PlanStatusWidget(classes="plan-status")
                yield self.plan_widget
        
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
        
        # Send to orchestrator
        await self.send_to_orchestrator(user_input)
    
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
                    "conversation_history": self.conversation_history[-5:] if self.conversation_history else []  # Last 5 exchanges for context
                }
                
                logger.info("sending_new_task_to_orchestrator",
                           task_id=task_id,
                           user_input=user_input[:100])
            
            self.current_task_id = task_id
            
            # Show processing spinner
            spinner_widget = await self.conversation_widget.add_system_message(
                "", "processing"
            )
            
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
    
    def action_quit(self) -> None:
        """Quit the application."""
        logger.info("textual_app_quit", thread_id=self.thread_id)
        self.exit()


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
    app = OrchestatorApp(orchestrator_url=args.url, thread_id=args.thread_id)
    app.run()


if __name__ == "__main__":
    main()