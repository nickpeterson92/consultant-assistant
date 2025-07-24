"""Clean and professional graph renderer for memory visualization."""

from typing import Dict, List, Tuple, Optional
from collections import defaultdict


class CleanGraphRenderer:
    """Renders a clean, organized graph visualization."""
    
    # Default width, but can be expanded for horizontal scrolling
    DEFAULT_WIDTH = 100
    MIN_WIDTH = 70
    
    @classmethod
    def render(cls, nodes: Dict, edges: List[Tuple], width: Optional[int] = None) -> List[str]:
        """Render a clean graph visualization.
        
        Args:
            nodes: Dictionary of node data
            edges: List of edge tuples
            width: Optional width for the graph (defaults to DEFAULT_WIDTH)
        """
        if not nodes:
            return ["No data to display"]
        
        # Use provided width or calculate based on content
        if width is None:
            # Calculate optimal width based on content
            width = cls._calculate_optimal_width(nodes, edges)
        
        lines = []
        
        # Group nodes by type
        cls._group_nodes(nodes)
        
        # Create a clean header with enhanced styling
        lines.append("╔" + "═" * width + "╗")
        lines.append("║" + " " * width + "║")
        lines.append("║" + f"{'KNOWLEDGE GRAPH':^{width}}" + "║")
        lines.append("║" + f"{f'{len(nodes)} nodes • {len(edges)} connections':^{width}}" + "║")
        lines.append("║" + " " * width + "║")
        lines.append("╠" + "═" * width + "╣")
        
        # Add legend at the top
        lines.extend(cls._render_legend(width))
        
        # Render relationships summary
        lines.extend(cls._render_relationships(edges, nodes, width))
        
        # Render model context section
        lines.extend(cls._render_model_context(nodes, width))
        
        # Close the box
        lines.append("╚" + "═" * width + "╝")
        
        return lines
    
    @classmethod
    def _calculate_optimal_width(cls, nodes: Dict, edges: List[Tuple]) -> int:
        """Calculate optimal width based on content."""
        # Start with default
        width = cls.DEFAULT_WIDTH
        
        # Check longest entity/action names
        max_name_length = 0
        for node_data in nodes.values():
            name = cls._get_short_name(node_data)
            if name:
                max_name_length = max(max_name_length, len(name))
        
        # Account for three columns: entities, actions, relationships
        # Each column needs space for content + padding
        content_width = (max_name_length + 5) * 3 + 10
        
        # Ensure minimum width and reasonable maximum
        width = max(cls.MIN_WIDTH, min(content_width, 150))
        
        return width
    
    @classmethod
    def _group_nodes(cls, nodes: Dict) -> Dict[str, List]:
        """Group nodes by type."""
        groups = defaultdict(list)
        
        for node_id, node_data in nodes.items():
            ctx_type = node_data.get('context_type', 'unknown')
            groups[ctx_type].append((node_id, node_data))
        
        return dict(groups)
    
    @classmethod
    def _render_main_graph(cls, grouped: Dict, edges: List[Tuple], all_nodes: Dict, width: int) -> List[str]:
        """Render the main graph visualization."""
        lines = []
        
        # Calculate column widths dynamically
        col_width = (width - 10) // 3  # Three columns with some padding
        
        # Create three columns with better visual hierarchy
        lines.append("║" + " " * width + "║")
        
        # Create column headers
        entities_header = "◆ ENTITIES"
        actions_header = "■ ACTIONS"
        relationships_header = "↔ RELATIONSHIPS"
        
        header_line = "║  "
        header_line += entities_header.ljust(col_width)
        header_line += actions_header.ljust(col_width)
        header_line += relationships_header.ljust(col_width - 2)
        header_line = header_line.ljust(width) + "║"
        lines.append(header_line)
        
        # Add separator line
        sep_line = "║  "
        sep_line += "─" * (len(entities_header) + 2) + " " * (col_width - len(entities_header) - 2)
        sep_line += "─" * (len(actions_header) + 2) + " " * (col_width - len(actions_header) - 2)
        sep_line += "─" * (len(relationships_header) + 2)
        sep_line = sep_line.ljust(width) + "║"
        lines.append(sep_line)
        
        lines.append("║" + " " * width + "║")
        
        # Get entities and actions
        entities = grouped.get('domain_entity', [])
        actions = grouped.get('completed_action', []) + grouped.get('search_result', [])
        
        # Create connection map
        cls._build_connection_map(edges, all_nodes)
        
        # Render rows
        max_rows = max(len(entities), len(actions), 20)  # Allow more rows with scrolling
        
        for i in range(min(max_rows, 30)):  # Show more with horizontal scroll
            # Build each column separately to ensure proper formatting
            
            # Entity column
            entity_col = ""
            if i < len(entities):
                entity_text = cls._format_entity(entities[i][1])
                # Safely truncate to fit column with icon
                max_text_len = col_width - 4  # Account for "◆ " prefix and padding
                if len(entity_text) > max_text_len:
                    entity_text = entity_text[:max_text_len-3] + "..."
                entity_col = f"◆ {entity_text}"
            entity_col = entity_col.ljust(col_width)
            
            # Action column  
            action_col = ""
            if i < len(actions):
                action_text = cls._format_action(actions[i][1])
                # Safely truncate to fit column with icon
                max_text_len = col_width - 4  # Account for "■ " prefix and padding
                if len(action_text) > max_text_len:
                    action_text = action_text[:max_text_len-3] + "..."
                action_col = f"■ {action_text}"
            action_col = action_col.ljust(col_width)
            
            # Connection column
            connection_col = ""
            if i < len(entities) and i < len(actions):
                entity_id = entities[i][0]
                action_id = actions[i][0]
                connection = cls._find_connection(entity_id, action_id, edges)
                if connection:
                    arrow = cls._get_arrow(connection)
                    # Center the arrow in the column
                    arrow_padding = (col_width - 2 - len(arrow)) // 2
                    connection_col = " " * arrow_padding + arrow
            connection_col = connection_col.ljust(col_width - 2)
            
            # Assemble the line
            line = "║  " + entity_col + action_col + connection_col
            # Ensure the line is exactly the right width
            if len(line) > width:
                line = line[:width]
            line = line.ljust(width) + "║"
            lines.append(line)
        
        lines.append("║" + " " * width + "║")
        
        return lines
    
    @classmethod
    def _format_entity(cls, node_data: Dict) -> str:
        """Format entity for display."""
        content = node_data.get('content', {})
        
        # Debug: log what we're receiving
        if content and isinstance(content, dict):
            from src.utils.logging.framework import SmartLogger
            logger = SmartLogger("client")
            logger.debug("formatting_entity_for_display",
                        has_entity_name='entity_name' in content,
                        entity_name_value=content.get('entity_name'),
                        has_entity_data='entity_data' in content,
                        entity_data_type=type(content.get('entity_data')).__name__ if 'entity_data' in content else None,
                        entity_id=content.get('entity_id'),
                        content_keys=list(content.keys())[:10])
        
        # Try to get the name from multiple possible locations
        name = None
        if isinstance(content, dict):
            # Direct entity_name field (primary location)
            name = content.get('entity_name')
            
            # If not found, try entity_data variations
            if not name and 'entity_data' in content and isinstance(content['entity_data'], dict):
                entity_data = content['entity_data']
                # Try multiple name fields in entity_data
                for name_field in ['Name', 'name', 'AccountName', 'ContactName', 
                                 'OpportunityName', 'LeadName', 'CaseName', 
                                 'Title', 'title', 'Subject', 'subject']:
                    if name_field in entity_data and entity_data[name_field]:
                        name = str(entity_data[name_field])
                        break
            
            # Also check raw_data if available
            if not name and 'raw_data' in content and isinstance(content['raw_data'], dict):
                raw_data = content['raw_data']
                for name_field in ['Name', 'name', 'title', 'subject']:
                    if name_field in raw_data and raw_data[name_field]:
                        name = str(raw_data[name_field])
                        break
        
        # Get the type
        entity_type = None
        if isinstance(content, dict):
            entity_type = content.get('entity_type', '')
        
        # Format display with better abbreviations
        if name:
            # Clean up the name
            name = str(name).strip()
            if entity_type and entity_type not in ['Entity', 'Unknown']:
                # Use better type abbreviations
                type_abbrev = {
                    'Account': 'Acc',
                    'Contact': 'Con',
                    'Opportunity': 'Opp',
                    'Lead': 'Lead',
                    'Case': 'Case',
                    'Task': 'Task'
                }.get(entity_type, entity_type[:3])
                return f"{type_abbrev}: {name}"
            return name
        
        # If still no name, try the summary field
        summary = node_data.get('summary', '')
        if summary and ':' in summary:
            # Extract name from summary like "Account: GenePoint"
            parts = summary.split(':', 1)
            if len(parts) > 1:
                potential_name = parts[1].strip()
                if potential_name and potential_name != 'None':
                    return summary
        
        # Last resort: show entity ID with smart truncation
        entity_id = content.get('entity_id', '') if isinstance(content, dict) else ''
        if entity_id:
            # For Salesforce IDs, show recognizable parts
            if len(entity_id) > 18:
                return f"ID: {entity_id[:3]}...{entity_id[-4:]}"
            return f"ID: {entity_id}"
            
        return node_data.get('summary', 'Unknown')[:20]
    
    @classmethod
    def _format_action(cls, node_data: Dict) -> str:
        """Format action for display."""
        summary = node_data.get('summary', '')
        
        # Clean up common prefixes for cleaner display
        prefixes_to_remove = [
            'Completed: ',
            'Retrieved ',
            'Searched for ',
            'Updated ',
            'Created ',
            'Found '
        ]
        
        for prefix in prefixes_to_remove:
            if summary.startswith(prefix):
                summary = summary[len(prefix):]
                break
        
        # Capitalize first letter if lowercase
        if summary and summary[0].islower():
            summary = summary[0].upper() + summary[1:]
        
        # Smart truncation
        if len(summary) > 20:
            # Try to break at word boundary
            truncated = summary[:17]
            last_space = truncated.rfind(' ')
            if last_space > 10:
                return truncated[:last_space] + "..."
            return truncated + "..."
        
        return summary
    
    @classmethod
    def _build_connection_map(cls, edges: List[Tuple], nodes: Dict) -> Dict:
        """Build a map of connections."""
        connections = defaultdict(list)
        
        for from_id, to_id, rel_type in edges:
            connections[from_id].append((to_id, rel_type))
            connections[to_id].append((from_id, rel_type))
        
        return connections
    
    @classmethod
    def _find_connection(cls, id1: str, id2: str, edges: List[Tuple]) -> Optional[str]:
        """Find connection type between two nodes."""
        for from_id, to_id, rel_type in edges:
            if (from_id == id1 and to_id == id2) or (from_id == id2 and to_id == id1):
                return rel_type
        return None
    
    @classmethod
    def _get_arrow(cls, rel_type: str) -> str:
        """Get arrow for relationship type."""
        arrows = {
            'led_to': '═══▶',
            'relates_to': '───▶',
            'depends_on': '···▶',
            'answers': '◀─?─▶',
            'refines': '◀═▶',
            'created': '◆──▶',
            'updated': '◆═▶',
            'belongs_to': '◀──◆',
        }
        return arrows.get(rel_type, '───▶')
    
    @classmethod
    def _render_relationships(cls, edges: List[Tuple], nodes: Dict, width: int) -> List[str]:
        """Render relationship details."""
        lines = []
        
        lines.append("╠" + "═" * width + "╣")
        lines.append("║" + " " * width + "║")
        lines.append("║" + "  ⚡ KEY RELATIONSHIPS".ljust(width) + "║")
        lines.append("║" + "  ────────────────────".ljust(width) + "║")
        lines.append("║" + " " * width + "║")
        
        # Show meaningful relationships
        shown = 0
        for from_id, to_id, rel_type in edges[:10]:  # Limit display
            from_node = nodes.get(from_id, {})
            to_node = nodes.get(to_id, {})
            
            from_name = cls._get_short_name(from_node)
            to_name = cls._get_short_name(to_node)
            
            if from_name and to_name:
                arrow = cls._get_arrow(rel_type)
                
                # Calculate safe widths for names
                arrow_len = len(arrow) + 4  # Arrow plus padding
                available_width = width - 6  # Account for "║  " prefix and padding
                name_width = (available_width - arrow_len) // 2
                
                # Safely truncate names to fit
                from_display = from_name
                if len(from_display) > name_width:
                    from_display = from_display[:name_width-3] + "..."
                from_display = from_display.rjust(name_width)
                
                to_display = to_name
                if len(to_display) > name_width:
                    to_display = to_display[:name_width-3] + "..."
                    
                # Build relationship display
                rel_display = f"  {from_display} {arrow:^{arrow_len}} {to_display}"
                
                # Ensure it fits within width
                if len(rel_display) > width - 2:
                    rel_display = rel_display[:width-5] + "..."
                    
                lines.append("║" + rel_display.ljust(width) + "║")
                shown += 1
                
                if shown >= 8:  # Limit relationships shown
                    break
        
        if shown == 0:
            lines.append("║" + "  No relationships to display".ljust(width) + "║")
        
        lines.append("║" + " " * width + "║")
        
        return lines
    
    @classmethod
    def _get_short_name(cls, node_data: Dict) -> str:
        """Get a short displayable name for a node."""
        content = node_data.get('content', {})
        
        # For entities
        if isinstance(content, dict):
            # Try direct entity_name first
            name = content.get('entity_name')
            
            # Then try entity_data variations
            if not name and 'entity_data' in content and isinstance(content['entity_data'], dict):
                entity_data = content['entity_data']
                # Try common name fields
                for field in ['Name', 'name', 'Title', 'title', 'Subject', 'subject']:
                    if field in entity_data and entity_data[field]:
                        name = str(entity_data[field])
                        break
            
            if name:
                return str(name)[:25]  # Allow slightly longer names
            
            # Try entity ID but shorten it
            entity_id = content.get('entity_id')
            if entity_id:
                if len(entity_id) > 10:
                    # For Salesforce IDs, show prefix and last 4 chars
                    return f"{entity_id[:3]}...{entity_id[-4:]}"
                return entity_id
        
        # Try summary field
        summary = node_data.get('summary', '')
        if summary:
            # If summary has format "Type: Name", extract the name
            if ':' in summary:
                parts = summary.split(':', 1)
                if len(parts) > 1 and parts[1].strip():
                    return parts[1].strip()[:25]
            
            # Remove common prefixes
            for prefix in ['Completed: ', 'Retrieved ', 'Updated ', 'Found ', 'Searched for ']:
                if summary.startswith(prefix):
                    summary = summary[len(prefix):]
            
            return summary[:25]
        
        return "Unknown"
    
    @classmethod
    def _render_legend(cls, width: int) -> List[str]:
        """Render a legend explaining symbols and relationships."""
        lines = []
        
        lines.append("║" + " " * width + "║")
        lines.append("║" + "  📖 LEGEND".ljust(width) + "║")
        lines.append("║" + "  ─────────".ljust(width) + "║")
        lines.append("║" + " " * width + "║")
        
        # Entity types
        lines.append("║" + "  Entity Types:".ljust(width) + "║")
        lines.append("║" + "    ◆ Domain Entity (Account, Contact, etc.)".ljust(width) + "║")
        lines.append("║" + "    ■ Action (Retrieved, Updated, etc.)".ljust(width) + "║")
        lines.append("║" + "    ○ Search Result".ljust(width) + "║")
        lines.append("║" + " " * width + "║")
        
        # Relationship types
        lines.append("║" + "  Relationship Arrows:".ljust(width) + "║")
        lines.append("║" + "    ═══▶  Led to (sequential flow)".ljust(width) + "║")
        lines.append("║" + "    ───▶  Relates to".ljust(width) + "║")
        lines.append("║" + "    ···▶  Depends on".ljust(width) + "║")
        lines.append("║" + "    ◀─?─▶ Answers question".ljust(width) + "║")
        lines.append("║" + "    ◀═▶   Refines/Updates".ljust(width) + "║")
        lines.append("║" + " " * width + "║")
        
        return lines
    
    @classmethod
    def _render_model_context(cls, nodes: Dict, width: int) -> List[str]:
        """Render the model context section showing what will be sent to LLM."""
        lines = []
        
        lines.append("╠" + "═" * width + "╣")
        lines.append("║" + " " * width + "║")
        lines.append("║" + "  🧠 MODEL CONTEXT (What LLM Sees)".ljust(width) + "║")
        lines.append("║" + "  ─────────────────────────────────".ljust(width) + "║")
        lines.append("║" + " " * width + "║")
        
        # Filter nodes by relevance (simulating what would be sent to LLM)
        # In reality, this would come from the actual memory retrieval
        relevant_nodes = []
        for node_id, node_data in nodes.items():
            # Check if node has high relevance or was recently accessed
            relevance = node_data.get('relevance', 0.0)
            node_data.get('last_accessed', '')
            
            # Only include nodes that would actually be sent to LLM
            # This should match the server-side logic which uses max_results=5-8
            # and filters by actual relevance scores
            if relevance > 0.5:  # Only nodes with actual relevance
                relevant_nodes.append((node_id, node_data, relevance))
        
        # Sort by relevance
        relevant_nodes.sort(key=lambda x: x[2], reverse=True)
        
        # Limit to match server-side behavior (typically 5-8 items)
        relevant_nodes = relevant_nodes[:8]  # Max that server sends to LLM
        
        if not relevant_nodes:
            lines.append("║" + "  No context selected yet (awaiting query)".ljust(width) + "║")
        else:
            # Show what would be included
            # More accurate description of what's shown
            total_available = len([n for n in nodes.values() if n.get('relevance', 0.0) > 0.5])
            lines.append("║" + f"  Included in context: {len(relevant_nodes)} items (from {total_available} with relevance > 0.5)".ljust(width) + "║")
            lines.append("║" + " " * width + "║")
            
            # Group by type for better display
            entities = []
            actions = []
            others = []
            
            for node_id, node_data, relevance in relevant_nodes[:10]:  # Limit display
                ctx_type = node_data.get('context_type', 'unknown')
                if ctx_type == 'domain_entity':
                    entities.append((node_id, node_data, relevance))
                elif ctx_type in ['completed_action', 'search_result']:
                    actions.append((node_id, node_data, relevance))
                else:
                    others.append((node_id, node_data, relevance))
            
            # Display entities
            if entities:
                lines.append("║" + "  Entities:".ljust(width) + "║")
                for node_id, node_data, relevance in entities[:5]:
                    name = cls._get_short_name(node_data)
                    relevance_bar = "█" * int(relevance * 5) + "░" * (5 - int(relevance * 5))
                    entry = f"    • {name:<30} [{relevance_bar}] {relevance:.1f}"
                    if len(entry) > width - 2:
                        entry = entry[:width-5] + "..."
                    lines.append("║" + entry.ljust(width) + "║")
            
            # Display recent actions
            if actions:
                lines.append("║" + " " * width + "║")
                lines.append("║" + "  Recent Actions:".ljust(width) + "║")
                for node_id, node_data, relevance in actions[:5]:
                    summary = node_data.get('summary', '')
                    # Clean up summary
                    for prefix in ['Completed: ', 'Retrieved ', 'Found ']:
                        if summary.startswith(prefix):
                            summary = summary[len(prefix):]
                    
                    relevance_bar = "█" * int(relevance * 5) + "░" * (5 - int(relevance * 5))
                    entry = f"    • {summary[:30]:<30} [{relevance_bar}] {relevance:.1f}"
                    if len(entry) > width - 2:
                        entry = entry[:width-5] + "..."
                    lines.append("║" + entry.ljust(width) + "║")
        
        lines.append("║" + " " * width + "║")
        lines.append("║" + "  Note: Context updates based on your queries".ljust(width) + "║")
        lines.append("║" + " " * width + "║")
        
        return lines