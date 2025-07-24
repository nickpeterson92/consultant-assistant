"""Memory graph visualization widget for Textual UI."""

from typing import Dict, List

from textual.app import ComposeResult
from textual.widgets import Static, Label
from textual.containers import ScrollableContainer
from textual.reactive import reactive

from src.utils.logging.framework import SmartLogger

logger = SmartLogger("client")


class MemoryGraphWidget(Static):
    """Widget to display the conversational memory graph in ASCII art."""
    
    graph_data = reactive({})
    selected_node_id = reactive(None)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.nodes = {}  # node_id -> node_data
        self.edges = []  # List of (from_id, to_id, relationship_type)
        self.node_positions = {}  # node_id -> (row, col)
        self.display_buffer = []
        self.max_width = 80
        self.max_height = 20
        self.llm_context_data = None  # Store the actual LLM context
        
    def compose(self) -> ComposeResult:
        """Compose the widget layout."""
        # Create a scrollable container that allows both horizontal and vertical scrolling
        container = ScrollableContainer(
            Static("Memory Graph (No data yet)", id="graph-display"),
            id="graph-container"
        )
        # Enable horizontal scrolling
        container.styles.overflow_x = "auto"
        container.styles.overflow_y = "auto"
        yield container
        yield Label("Node Details", id="node-details")
    
    def update_graph_data(self, data: Dict):
        """Update the graph with new data from SSE events."""
        try:
            self.nodes = data.get("nodes", {})
            
            # Convert edges from dict format to tuple format
            edges_data = data.get("edges", [])
            self.edges = []
            for edge in edges_data:
                if isinstance(edge, dict):
                    self.edges.append((
                        edge.get("from_id"),
                        edge.get("to_id"),
                        edge.get("type", "relates_to")
                    ))
                elif isinstance(edge, (list, tuple)) and len(edge) >= 3:
                    self.edges.append((edge[0], edge[1], edge[2]))
            
            self.render_graph()
            
            logger.info("memory_graph_updated",
                       node_count=len(self.nodes),
                       edge_count=len(self.edges))
        except Exception as e:
            logger.error("memory_graph_update_error", error=str(e))
    
    def render_graph(self):
        """Render the graph as ASCII art."""
        if not self.nodes:
            self.query_one("#graph-display", Static).update("No memory nodes yet")
            return
        
        # Use clean graph renderer for entire visualization
        lines = self._create_graph_visualization()
        
        # Update display with clean graph
        display_text = "\n".join(lines)
        self.query_one("#graph-display", Static).update(display_text)
    
    def handle_sse_memory_update(self, data: Dict):
        """Handle memory update events from SSE."""
        event_type = data.get("event_type", "")
        
        if event_type == "node_added":
            node_id = data.get("node_id")
            node_data = data.get("node_data", {})
            if node_id:
                self.nodes[node_id] = node_data
                
        elif event_type == "edge_added":
            edge_data = data.get("edge_data", {})
            from_id = edge_data.get("from_id")
            to_id = edge_data.get("to_id")
            rel_type = edge_data.get("type", "relates_to")
            if from_id and to_id:
                self.edges.append((from_id, to_id, rel_type))
                
        elif event_type == "graph_snapshot":
            # Full graph update
            self.update_graph_data(data.get("graph_data", {}))
            
        elif event_type == "node_accessed":
            # Update relevance/access time
            node_id = data.get("node_id")
            if node_id in self.nodes:
                self.nodes[node_id]["last_accessed"] = data.get("timestamp", "")
                self.nodes[node_id]["relevance"] = data.get("relevance", 0.0)
        
        # Re-render after update
        self.render_graph()
    
    def handle_llm_context_update(self, data: Dict):
        """Handle LLM context update events."""
        try:
            # Store the LLM context data
            self.llm_context_data = {
                "context_type": data.get("context_type", "unknown"),
                "context_text": data.get("context_text", ""),
                "metadata": data.get("metadata", {}),
                "full_prompt": data.get("full_prompt", ""),
                "timestamp": data.get("timestamp", "")
            }
            
            # Re-render the graph to update the "What LLM Sees" section
            self.render_graph()
            
            logger.info("llm_context_updated_in_widget",
                       context_type=self.llm_context_data["context_type"],
                       has_context=bool(self.llm_context_data["context_text"]))
        except Exception as e:
            logger.error("llm_context_update_error", error=str(e))
    
    def _create_graph_visualization(self) -> List[str]:
        """Create an ASCII art visualization of the graph with nodes and edges."""
        try:
            from .clean_graph_renderer import CleanGraphRenderer
            
            # Use clean renderer with dynamic width for horizontal scrolling
            # Calculate a width that can accommodate the content
            width = None  # Let the renderer calculate optimal width
            return CleanGraphRenderer.render(self.nodes, self.edges, width, llm_context=self.llm_context_data)
        except ImportError:
            try:
                from .advanced_graph_renderer import AdvancedGraphRenderer
                
                # Use advanced renderer if available
                return AdvancedGraphRenderer.render_graph(
                    self.nodes, 
                    self.edges,
                    width=70,
                    height=25
                )
            except ImportError:
                # Fallback to simple visualization
                return self._create_simple_graph_visualization()
    
    def _get_node_display_name(self, node_data: Dict) -> str:
        """Extract the best display name for a node."""
        # Try multiple sources for the name
        content = node_data.get("content", {})
        
        # For entities
        if isinstance(content, dict):
            # Try entity_name first
            if content.get("entity_name"):
                return content["entity_name"]
            # Then try entity_data.Name
            elif content.get("entity_data", {}).get("Name"):
                return content["entity_data"]["Name"]
            # Then try entity_data.name
            elif content.get("entity_data", {}).get("name"):
                return content["entity_data"]["name"]
            # Fall back to entity_id
            elif content.get("entity_id"):
                return content["entity_id"]
        
        # Fall back to summary
        return node_data.get("summary", "Unknown")[:30]
    
    def _get_arrow_for_relationship(self, rel_type: str) -> str:
        """Get the arrow symbol for a relationship type."""
        arrows = {
            "led_to": "═══>",
            "relates_to": "───>",
            "depends_on": "···>",
            "answers": "─?>",
            "refines": "─►>",
            "belongs_to": "◄──",
            "owned_by": "◄═─"
        }
        return arrows.get(rel_type, "───>")
    
    def _create_simple_graph_visualization(self) -> List[str]:
        """Simple fallback visualization."""
        lines = []
        lines.append("╔═══ SIMPLE GRAPH VIEW ═══╗")
        
        # Show nodes by type
        node_types = {}
        for node_id, node_data in self.nodes.items():
            ctx_type = node_data.get("context_type", "unknown")
            if ctx_type not in node_types:
                node_types[ctx_type] = []
            node_types[ctx_type].append((node_id, node_data))
        
        for ctx_type, nodes in node_types.items():
            lines.append(f"\n{ctx_type.upper()}:")
            for node_id, node_data in nodes[:5]:  # Limit display
                name = self._get_node_display_name(node_data)
                lines.append(f"  • {name}")
        
        lines.append("\nCONNECTIONS:")
        for i, (from_id, to_id, rel_type) in enumerate(self.edges[:10]):
            from_name = self._get_node_display_name(self.nodes.get(from_id, {}))[:20]
            to_name = self._get_node_display_name(self.nodes.get(to_id, {}))[:20]
            arrow = self._get_arrow_for_relationship(rel_type)
            lines.append(f"  {from_name} {arrow} {to_name}")
        
        lines.append("╚" + "═" * 30 + "╝")
        return lines
    
    def on_click(self, event):
        """Handle click events to select nodes."""
        # This is a simplified version - in a real implementation,
        # we'd calculate which node was clicked based on position
        pass


class MemoryStatsWidget(Static):
    """Widget to display memory statistics."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.stats = {}
        
    def update_stats(self, stats: Dict):
        """Update displayed statistics."""
        self.stats = stats
        
        lines = []
        lines.append("═══ Memory Statistics ═══")
        lines.append(f"Total Nodes: {stats.get('total_nodes', 0)}")
        lines.append(f"Total Edges: {stats.get('total_edges', 0)}")
        lines.append(f"Avg Relevance: {stats.get('avg_relevance', 0):.2f}")
        lines.append(f"Active Clusters: {stats.get('cluster_count', 0)}")
        
        # Context type distribution
        ctx_dist = stats.get('context_distribution', {})
        if ctx_dist:
            lines.append("\nContext Types:")
            for ctx_type, count in ctx_dist.items():
                lines.append(f"  • {ctx_type}: {count}")
        
        self.update("\n".join(lines))