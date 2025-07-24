"""Widget for displaying LLM context in the UI."""

from datetime import datetime
from typing import Dict, Any, Optional

from textual.app import ComposeResult
from textual.containers import Vertical, ScrollableContainer
from textual.widgets import Static, Label, Collapsible
from textual.reactive import reactive

from src.utils.logging.framework import SmartLogger

logger = SmartLogger("ui")


class LLMContextWidget(Vertical):
    """Widget that displays the exact context being sent to the LLM."""
    
    # Reactive properties
    current_context = reactive({})
    
    def compose(self) -> ComposeResult:
        """Compose the widget layout."""
        yield Label("[bold yellow]📝 LLM Context[/bold yellow]", id="llm-context-header")
        yield ScrollableContainer(
            Static("No context yet...", id="llm-context-content"),
            id="llm-context-container"
        )
    
    def handle_llm_context_event(self, event_data: Dict[str, Any]) -> None:
        """Handle incoming LLM context events."""
        try:
            context_type = event_data.get("context_type", "unknown")
            context_text = event_data.get("context_text", "")
            metadata = event_data.get("metadata", {})
            full_prompt = event_data.get("full_prompt", "")
            timestamp = event_data.get("timestamp", datetime.now().isoformat())
            
            # Update current context
            self.current_context = event_data
            
            # Format the display
            display_parts = []
            
            # Header with context type
            type_emoji = {
                "execution": "⚡",
                "planning": "📋",
                "replanning": "🔄"
            }.get(context_type, "📝")
            
            display_parts.append(f"[bold yellow]{type_emoji} {context_type.title()} Context[/bold yellow]")
            display_parts.append(f"[dim]Generated at: {timestamp}[/dim]")
            display_parts.append("")
            
            # Metadata stats
            if metadata:
                display_parts.append("[bold]Context Statistics:[/bold]")
                if "relevant_count" in metadata:
                    display_parts.append(f"  • Relevant memories: {metadata['relevant_count']}")
                if "important_count" in metadata:
                    display_parts.append(f"  • Important memories: {metadata['important_count']}")
                if "cluster_count" in metadata:
                    display_parts.append(f"  • Topic clusters: {metadata['cluster_count']}")
                if "bridge_count" in metadata:
                    display_parts.append(f"  • Bridge memories: {metadata['bridge_count']}")
                display_parts.append("")
            
            # Context text
            if context_text:
                display_parts.append("[bold]Memory Context Being Injected:[/bold]")
                display_parts.append("[dim]" + "-" * 60 + "[/dim]")
                display_parts.append(context_text)
                display_parts.append("[dim]" + "-" * 60 + "[/dim]")
                display_parts.append("")
            
            # Full prompt (collapsible for large prompts)
            if full_prompt:
                display_parts.append("[bold]Full Prompt to LLM:[/bold]")
                display_parts.append("[dim cyan]" + "─" * 60 + "[/dim cyan]")
                
                # Truncate if too long
                if len(full_prompt) > 2000:
                    display_parts.append(full_prompt[:2000])
                    display_parts.append(f"\n[dim]... (truncated, showing first 2000 of {len(full_prompt)} chars)[/dim]")
                else:
                    display_parts.append(full_prompt)
                display_parts.append("[dim cyan]" + "─" * 60 + "[/dim cyan]")
            
            # Update the display
            content = self.query_one("#llm-context-content", Static)
            content.update("\n".join(display_parts))
            
            # Scroll to top to show new content
            container = self.query_one("#llm-context-container", ScrollableContainer)
            container.scroll_home()
            
            logger.info("llm_context_displayed",
                       context_type=context_type,
                       context_length=len(context_text),
                       has_full_prompt=bool(full_prompt))
            
        except Exception as e:
            logger.error("llm_context_display_error", error=str(e))
            self.update_error(f"Error displaying context: {str(e)}")
    
    def update_error(self, error_message: str) -> None:
        """Display an error message."""
        content = self.query_one("#llm-context-content", Static)
        content.update(f"[bold red]Error:[/bold red] {error_message}")
    
    def clear(self) -> None:
        """Clear the context display."""
        self.current_context = {}
        content = self.query_one("#llm-context-content", Static)
        content.update("No context yet...")