"""Advanced ASCII art graph renderer for memory visualization.

This creates a proper node-and-edge graph visualization in ASCII.
"""

from typing import Dict, List, Tuple


class AdvancedGraphRenderer:
    """Renders graph data as ASCII art with proper node and edge visualization."""
    
    # Node type symbols and colors (for future color support)
    NODE_SYMBOLS = {
        'domain_entity': '◆',     # Diamond for entities
        'completed_action': '■',   # Square for actions
        'search_result': '○',      # Circle for searches
        'tool_output': '▣',        # Tool outputs
        'user_selection': '★',     # Star for user selections
        'conversation_fact': '▪',  # Small square for facts
        'temporary_state': '◦'     # Small circle for temp
    }
    
    # Relationship arrow styles
    ARROW_STYLES = {
        'led_to': '═══>',
        'relates_to': '───>',
        'depends_on': '···>',
        'answers': '──?>',
        'refines': '──►>',
        'belongs_to': '<───',
        'owned_by': '<═══',
        'created_by': '<···',
        'assigned_to': '<──●'
    }
    
    @classmethod
    def render_graph(cls, nodes: Dict, edges: List[Tuple], width: int = 80, height: int = 30) -> List[str]:
        """Render the graph as ASCII art.
        
        Args:
            nodes: Dict of node_id -> node_data
            edges: List of (from_id, to_id, rel_type) tuples
            width: Canvas width
            height: Canvas height
            
        Returns:
            List of strings representing the graph
        """
        if not nodes:
            return ["No nodes to display"]
        
        # Layout nodes using force-directed placement
        positions = cls._layout_nodes(nodes, edges, width, height)
        
        # Create canvas
        canvas = [[' ' for _ in range(width)] for _ in range(height)]
        
        # Draw edges first (so nodes appear on top)
        cls._draw_edges(canvas, edges, positions, nodes)
        
        # Draw nodes
        cls._draw_nodes(canvas, nodes, positions)
        
        # Convert canvas to strings
        lines = [''.join(row) for row in canvas]
        
        # Add legend
        lines.extend(cls._create_legend())
        
        return lines
    
    @classmethod
    def _layout_nodes(cls, nodes: Dict, edges: List[Tuple], width: int, height: int) -> Dict[str, Tuple[int, int]]:
        """Layout nodes using a simple force-directed algorithm."""
        positions = {}
        
        # Group nodes by type for better layout
        node_groups = {
            'entities': [],
            'actions': [],
            'other': []
        }
        
        for node_id, node_data in nodes.items():
            ctx_type = node_data.get('context_type', '')
            if ctx_type == 'domain_entity':
                node_groups['entities'].append(node_id)
            elif ctx_type in ['completed_action', 'search_result']:
                node_groups['actions'].append(node_id)
            else:
                node_groups['other'].append(node_id)
        
        # Place entities on the left
        y_offset = 2
        for i, node_id in enumerate(node_groups['entities'][:10]):  # Limit to fit
            x = 5
            y = y_offset + i * 3
            if y < height - 2:
                positions[node_id] = (x, y)
        
        # Place actions in the middle
        y_offset = 2
        for i, node_id in enumerate(node_groups['actions'][:10]):
            x = width // 2
            y = y_offset + i * 3
            if y < height - 2:
                positions[node_id] = (x, y)
        
        # Place others on the right
        y_offset = 2
        for i, node_id in enumerate(node_groups['other'][:10]):
            x = width - 20
            y = y_offset + i * 3
            if y < height - 2:
                positions[node_id] = (x, y)
        
        return positions
    
    @classmethod
    def _draw_nodes(cls, canvas: List[List[str]], nodes: Dict, positions: Dict[str, Tuple[int, int]]):
        """Draw nodes on the canvas."""
        for node_id, (x, y) in positions.items():
            if node_id not in nodes:
                continue
                
            node_data = nodes[node_id]
            ctx_type = node_data.get('context_type', 'unknown')
            symbol = cls.NODE_SYMBOLS.get(ctx_type, '●')
            
            # Get node label
            label = cls._get_node_label(node_data)[:15]  # Truncate for space
            
            # Draw node symbol
            if 0 <= y < len(canvas) and 0 <= x < len(canvas[0]):
                canvas[y][x] = symbol
            
            # Draw label
            label_x = x + 2
            if 0 <= y < len(canvas) and label_x + len(label) < len(canvas[0]):
                for i, char in enumerate(label):
                    canvas[y][label_x + i] = char
    
    @classmethod
    def _draw_edges(cls, canvas: List[List[str]], edges: List[Tuple], 
                    positions: Dict[str, Tuple[int, int]], nodes: Dict):
        """Draw edges between nodes."""
        for from_id, to_id, rel_type in edges:
            if from_id not in positions or to_id not in positions:
                continue
            
            from_x, from_y = positions[from_id]
            to_x, to_y = positions[to_id]
            
            # Simple line drawing (could be improved with proper line algorithms)
            if from_y == to_y:
                # Horizontal line
                start_x = min(from_x, to_x) + 1
                end_x = max(from_x, to_x)
                arrow = cls._get_arrow_char(rel_type, 'horizontal')
                for x in range(start_x, end_x):
                    if 0 <= from_y < len(canvas) and 0 <= x < len(canvas[0]):
                        if canvas[from_y][x] == ' ':
                            canvas[from_y][x] = arrow
            else:
                # Vertical or diagonal - use simple characters
                arrow = cls._get_arrow_char(rel_type, 'vertical')
                # Draw a simple indicator
                mid_x = (from_x + to_x) // 2
                mid_y = (from_y + to_y) // 2
                if 0 <= mid_y < len(canvas) and 0 <= mid_x < len(canvas[0]):
                    if canvas[mid_y][mid_x] == ' ':
                        canvas[mid_y][mid_x] = arrow
    
    @classmethod
    def _get_node_label(cls, node_data: Dict) -> str:
        """Extract a label for the node."""
        content = node_data.get('content', {})
        
        if isinstance(content, dict):
            # Try various name fields
            for field in ['entity_name', 'Name', 'name', 'title']:
                if field in content and content[field]:
                    return str(content[field])
            
            # Try entity_data
            entity_data = content.get('entity_data', {})
            if isinstance(entity_data, dict):
                for field in ['Name', 'name', 'title']:
                    if field in entity_data and entity_data[field]:
                        return str(entity_data[field])
            
            # Fall back to entity_id
            if content.get('entity_id'):
                entity_id = content['entity_id']
                # Shorten long IDs
                if len(entity_id) > 15:
                    return entity_id[:12] + '...'
                return entity_id
        
        # Fall back to summary
        summary = node_data.get('summary', '')
        if summary:
            return summary[:15]
        
        return 'Unknown'
    
    @classmethod
    def _get_arrow_char(cls, rel_type: str, direction: str) -> str:
        """Get a simple arrow character for the relationship."""
        if direction == 'horizontal':
            if rel_type == 'led_to':
                return '═'
            elif rel_type in ['depends_on', 'created_by']:
                return '·'
            else:
                return '─'
        else:
            if rel_type == 'led_to':
                return '║'
            elif rel_type in ['depends_on', 'created_by']:
                return '┊'
            else:
                return '│'
    
    @classmethod
    def _create_legend(cls) -> List[str]:
        """Create a legend for the graph."""
        lines = []
        lines.append("")
        lines.append("═══ LEGEND ═══")
        lines.append("Node Types:")
        lines.append("  ◆ Entity   ■ Action   ○ Search   ▣ Tool   ★ User Selection")
        lines.append("Relationships:")
        lines.append("  ═══> led_to   ───> relates_to   ···> depends_on   ──?> answers")
        return lines