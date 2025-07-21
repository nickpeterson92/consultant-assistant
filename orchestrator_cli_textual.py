#!/usr/bin/env python3
"""Textual-based CLI client for the plan-and-execute orchestrator."""

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

from src.a2a import A2AClient
from src.utils.config.constants import ENTERPRISE_ASSISTANT_BANNER
from src.utils.config.unified_config import config as app_config
from src.utils.ui.animations import animated_banner_display
from src.utils.logging.framework import SmartLogger

# Initialize SmartLogger
logger = SmartLogger("client")


class PlanStatusWidget(Static):
    """Widget to display plan status and execution progress."""
    
    plan_tasks = reactive([])
    current_step = reactive("")
    execution_status = reactive("idle")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.plan_data = []
        
    def update_plan(self, plan: List[str]):
        """Update the plan display with new plan steps."""
        self.plan_data = plan
        self.plan_tasks = plan
        self.refresh_display()
        
    def update_execution_status(self, step: str, status: str = "executing"):
        """Update which step is currently executing."""
        self.current_step = step
        self.execution_status = status
        self.refresh_display()
        
    def refresh_display(self):
        """Refresh the plan display."""
        if not self.plan_data:
            content = "[dim]No plan available[/dim]"
        else:
            content_lines = ["[bold]📋 Execution Plan:[/bold]", ""]
            
            for i, step in enumerate(self.plan_data, 1):
                if step == self.current_step and self.execution_status == "executing":
                    content_lines.append(f"[yellow]▶ {i}. {step}[/yellow]")
                elif step == self.current_step and self.execution_status == "completed":
                    content_lines.append(f"[green]✓ {i}. {step}[/green]")
                else:
                    content_lines.append(f"[dim]  {i}. {step}[/dim]")
            
            content = "\\n".join(content_lines)
        
        self.update(content)


class ConversationWidget(ScrollableContainer):
    """Widget to display conversation history with proper scrolling."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.conversation_content = Static("Welcome! Ask me anything about your CRM, projects, or IT systems.", id="conversation-content")
        
    def compose(self) -> ComposeResult:
        yield self.conversation_content
        
    async def add_message(self, message: str):
        """Add a message to the conversation display."""
        current_content = self.conversation_content.renderable
        
        if isinstance(current_content, str):
            if current_content.strip() == "Welcome! Ask me anything about your CRM, projects, or IT systems.":
                new_content = message
            else:
                new_content = f"{current_content}\\n\\n{message}"
        else:
            new_content = message
        
        self.conversation_content.update(new_content)
        
        # Scroll to bottom
        self.scroll_end(animate=False)


class StatusWidget(Static):
    """Widget to display connection and system status."""
    
    def __init__(self, orchestrator_url: str, thread_id: str, **kwargs):
        super().__init__(**kwargs)
        self.orchestrator_url = orchestrator_url
        self.thread_id = thread_id
        self.update_status()
        
    def update_status(self, connected: bool = True, task_id: Optional[str] = None):
        """Update the status display."""
        status_icon = "🟢" if connected else "🔴"
        connection_status = "Connected" if connected else "Disconnected"
        
        status_text = f"{status_icon} {connection_status} | URL: {self.orchestrator_url} | Thread: {self.thread_id}"
        
        if task_id:
            status_text += f" | Task: {task_id}"
            
        self.update(status_text)


class OrchestatorApp(App):
    """Main Textual application for the orchestrator client."""
    
    CSS = """
    .header {
        dock: top;
        height: 8;
        padding: 1;
        background: #1e293b;
        color: #94a3b8;
    }
    
    .main-container {
        height: 100%;
        padding: 1;
    }
    
    .plan-status {
        dock: right;
        width: 40%;
        height: 100%;
        border: solid #374151;
        padding: 1;
        margin: 1;
    }
    
    .conversation {
        height: 80%;
        border: solid #374151;
        padding: 1;
        margin-bottom: 1;
    }
    
    .input-container {
        dock: bottom;
        height: 5;
        padding: 1;
    }
    
    .status-bar {
        dock: bottom;
        height: 3;
        background: #1e293b;
        color: #94a3b8;
        padding: 1;
    }
    """
    
    def __init__(self, orchestrator_url: str = "http://localhost:8000", thread_id: Optional[str] = None):
        super().__init__()
        self.orchestrator_url = orchestrator_url
        self.thread_id = thread_id or f"textual-{uuid.uuid4().hex[:8]}"
        self.a2a_client = A2AClient(base_url=orchestrator_url)
        self.conversation_history = []
        self.current_task_id = None
        
        logger.info("textual_app_initialized", 
                   orchestrator_url=orchestrator_url,
                   thread_id=self.thread_id)
    
    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        # Main banner - simple text version for now
        yield Static(
            "[bold cyan]ENTERPRISE ASSISTANT[/bold cyan]\\n"
            "[dim #94a3b8]Powered by Plan-and-Execute Multi-Agent Orchestration[/dim #94a3b8]",
            classes="header",
            id="main-banner"
        )
        
        # Main container
        with Container(classes="main-container"):
            # Plan status widget
            yield PlanStatusWidget(classes="plan-status", id="plan-status")
            
            # Conversation area
            yield ConversationWidget(classes="conversation", id="conversation")
            
            # Input area
            with Container(classes="input-container"):
                yield Input(placeholder="Enter your request...", id="user-input")
        
        # Status bar
        yield StatusWidget(self.orchestrator_url, self.thread_id, classes="status-bar", id="status")
    
    def on_mount(self) -> None:
        """Called when the app is mounted."""
        self.query_one("#user-input", Input).focus()
        logger.info("textual_app_mounted", thread_id=self.thread_id)
    
    @on(Input.Submitted, "#user-input")
    async def handle_input(self, event: Input.Submitted) -> None:
        """Handle user input submission."""
        user_input = event.value.strip()
        if not user_input:
            return
        
        # Clear the input
        event.input.value = ""
        
        # Add user message to conversation
        conversation = self.query_one("#conversation", ConversationWidget)
        await conversation.add_message(f"[bold blue]You:[/bold blue] {user_input}")
        
        # Send to orchestrator
        await self.send_to_orchestrator(user_input)
    
    async def send_to_orchestrator(self, user_input: str) -> None:
        """Send user input to the orchestrator via A2A protocol."""
        try:
            # Generate task ID
            task_id = f"task-{uuid.uuid4().hex[:8]}"
            self.current_task_id = task_id
            
            logger.info("sending_task_to_orchestrator",
                       task_id=task_id,
                       user_input=user_input[:100])
            
            # Show loading state
            conversation = self.query_one("#conversation", ConversationWidget)
            await conversation.add_message(f"[dim yellow]🤔 Processing your request...[/dim yellow]")
            
            # Update status
            status_widget = self.query_one("#status", StatusWidget)
            status_widget.update_status(connected=True, task_id=task_id)
            
            # Send A2A request
            response = await self.a2a_client.process_task(
                task_id=task_id,
                instruction=user_input,
                context={"thread_id": self.thread_id}
            )
            
            if response.get("status") == "completed":
                # Extract artifacts and display results
                artifacts = response.get("artifacts", [])
                
                if artifacts:
                    for artifact in artifacts:
                        content = artifact.get("content", "")
                        await conversation.add_message(f"[bold green]Assistant:[/bold green] {content}")
                else:
                    await conversation.add_message("[bold green]Assistant:[/bold green] Task completed successfully.")
                
                # If there was plan data, show it
                metadata = response.get("metadata", {})
                if "plan" in metadata:
                    plan_widget = self.query_one("#plan-status", PlanStatusWidget)
                    plan_widget.update_plan(metadata["plan"])
            
            elif response.get("status") == "failed":
                error_msg = response.get("error", "Unknown error occurred")
                await conversation.add_message(f"[bold red]Error:[/bold red] {error_msg}")
            
            else:
                await conversation.add_message(f"[yellow]Status:[/yellow] {response.get('status', 'unknown')}")
            
            # Clear task from status
            status_widget.update_status(connected=True, task_id=None)
        
        except Exception as e:
            logger.error("orchestrator_request_error", 
                        error=str(e),
                        task_id=self.current_task_id)
            conversation = self.query_one("#conversation", ConversationWidget)
            await conversation.add_message(f"[bold red]Connection Error:[/bold red] {str(e)}")
            
            # Update status to show disconnected
            status_widget = self.query_one("#status", StatusWidget)
            status_widget.update_status(connected=False)
    
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