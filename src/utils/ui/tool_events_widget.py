"""Tool Events Widget for displaying real-time tool execution events."""

from typing import Dict, Any, List
from datetime import datetime
from textual.widgets import Static, ScrollableContainer
from textual.containers import Vertical
from textual.reactive import reactive

from src.utils.logging.framework import SmartLogger

logger = SmartLogger("ui.tool_events")


class ToolEventEntry:
    """Represents a single tool event entry."""
    
    def __init__(self, event_type: str, data: Dict[str, Any]):
        self.timestamp = datetime.now()
        self.event_type = event_type
        self.data = data
        self.agent_name = data.get("agent_name", "unknown")
        self.task_id = data.get("task_id", "")
        self.instruction = data.get("instruction", "")
        self.additional_data = data.get("additional_data", {})
        
    def format_for_display(self) -> List[str]:
        """Format the event for display with icon and details."""
        # Determine icon based on event type
        icon_map = {
            "agent_call_started": "🔧",
            "agent_call_completed": "✅",
            "agent_call_failed": "❌",
            "tool_selected": "🎯",
            "direct_response": "💡",
            "web_search_started": "🔍",
            "web_search_completed": "🔍✓",
            "human_input_requested": "💬",
            "human_input_received": "💬✓"
        }
        
        icon = icon_map.get(self.event_type, "📌")
        time_str = self.timestamp.strftime("%H:%M:%S")
        
        # Format header
        header = f"[bold cyan][{time_str}][/bold cyan] {icon} {self._format_event_name()}"
        
        # Format details
        lines = [header]
        
        # Add agent name
        agent_display = self._format_agent_name()
        lines.append(f"  [dim]├─[/dim] Agent: [yellow]{agent_display}[/yellow]")
        
        # Add action/instruction
        if self.instruction:
            # Truncate long instructions
            action = self.instruction[:60] + "..." if len(self.instruction) > 60 else self.instruction
            lines.append(f"  [dim]├─[/dim] Action: {action}")
        
        # Add relevant details based on event type
        detail = self._format_details()
        if detail:
            lines.append(f"  [dim]└─[/dim] {detail}")
            
        return lines
    
    def _format_event_name(self) -> str:
        """Format the event type for display."""
        name_map = {
            "agent_call_started": "Tool Started",
            "agent_call_completed": "Tool Completed",
            "agent_call_failed": "Tool Failed",
            "tool_selected": "Tool Selected",
            "direct_response": "Direct Response",
            "web_search_started": "Web Search Started",
            "web_search_completed": "Web Search Completed",
            "human_input_requested": "Human Input Requested",
            "human_input_received": "Human Input Received"
        }
        return name_map.get(self.event_type, self.event_type.replace("_", " ").title())
    
    def _format_agent_name(self) -> str:
        """Format agent name for display."""
        # Make agent names more readable
        name = self.agent_name
        
        # Handle composite names like "salesforce_salesforce_get"
        if name.count("_") >= 2:
            parts = name.split("_")
            if parts[0] == parts[1]:  # e.g., "salesforce_salesforce_get"
                name = f"{parts[0]} → {parts[2]}"
            elif parts[0] in ["salesforce", "jira", "servicenow"]:
                name = f"{parts[0]} → {'_'.join(parts[1:])}"
        
        return name
    
    def _format_details(self) -> str:
        """Format additional details based on event type."""
        if self.event_type == "agent_call_completed":
            preview = self.additional_data.get("response_preview", "")
            if preview:
                return f"Result: [green]{preview[:50]}...[/green]" if len(preview) > 50 else f"Result: [green]{preview}[/green]"
                
        elif self.event_type == "agent_call_failed":
            error = self.additional_data.get("error", "Unknown error")
            return f"Error: [red]{error[:50]}...[/red]" if len(error) > 50 else f"Error: [red]{error}[/red]"
            
        elif self.event_type == "web_search_started":
            return f"Query: {self.additional_data.get('original_query', '')[:40]}..."
            
        elif self.event_type == "web_search_completed":
            count = self.additional_data.get("result_count", 0)
            return f"Found {count} results"
            
        elif self.event_type == "direct_response":
            resp_type = self.additional_data.get("response_type", "unknown")
            return f"Type: {resp_type}"
            
        elif self.event_type == "human_input_requested":
            return "Waiting for user input..."
            
        elif self.event_type == "human_input_received":
            preview = self.additional_data.get("response_preview", "")
            return f"Response: {preview[:40]}..." if len(preview) > 40 else f"Response: {preview}"
            
        # Generic details for other events
        tool_type = self.additional_data.get("tool_type", "")
        if tool_type:
            return f"Type: {tool_type}"
            
        return ""


class ToolEventsWidget(ScrollableContainer):
    """Widget to display tool execution events in real-time."""
    
    # Reactive attribute for auto-scroll
    auto_scroll = reactive(True)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.events: List[ToolEventEntry] = []
        self.max_events = 100
        self.event_container = Vertical()
        
    def on_mount(self):
        """Called when widget is mounted."""
        # Add header
        header = Static("[bold white]Tool Execution Log[/bold white]", classes="tool-events-header")
        self.mount(header)
        self.mount(self.event_container)
        
    def add_tool_event(self, event_type: str, data: Dict[str, Any]):
        """Add a new tool event to the display."""
        # Create event entry
        event = ToolEventEntry(event_type, data)
        self.events.append(event)
        
        # Trim old events if needed
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
            # Clear and redraw all events
            self.event_container.remove_children()
            for evt in self.events:
                self._add_event_to_display(evt)
        else:
            # Just add the new event
            self._add_event_to_display(event)
        
        # Auto-scroll to bottom if enabled
        if self.auto_scroll:
            self.scroll_to_bottom()
            
        logger.info("tool_event_added",
                   event_type=event_type,
                   agent_name=event.agent_name,
                   total_events=len(self.events))
    
    def _add_event_to_display(self, event: ToolEventEntry):
        """Add a single event to the display."""
        lines = event.format_for_display()
        
        # Create a container for this event
        event_widget = Vertical(classes="tool-event-entry")
        
        for i, line in enumerate(lines):
            if i == 0:
                # Header line
                event_widget.mount(Static(line, classes="tool-event-header"))
            else:
                # Detail lines
                event_widget.mount(Static(line, classes="tool-event-detail"))
        
        # Add separator
        event_widget.mount(Static("", classes="tool-event-separator"))
        
        self.event_container.mount(event_widget)
    
    def handle_sse_event(self, event_type: str, data: Dict[str, Any]):
        """Handle incoming SSE events."""
        # Filter out events we care about
        relevant_events = [
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
        
        if event_type in relevant_events:
            self.add_tool_event(event_type, data)
    
    def clear_events(self):
        """Clear all events from the display."""
        self.events.clear()
        self.event_container.remove_children()
        logger.info("tool_events_cleared")
    
    def on_scroll(self, event):
        """Handle scroll events to manage auto-scroll."""
        # If user scrolls up, disable auto-scroll
        # If they scroll to bottom, re-enable it
        if self.is_at_bottom():
            self.auto_scroll = True
        else:
            self.auto_scroll = False
    
    def is_at_bottom(self) -> bool:
        """Check if scrolled to bottom."""
        # This is a simplified check - you may need to adjust based on actual behavior
        return self.scroll_y >= self.max_scroll_y - 1