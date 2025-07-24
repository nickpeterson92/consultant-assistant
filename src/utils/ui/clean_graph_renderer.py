"""Clean and professional graph renderer for memory visualization."""

from typing import Dict, List, Tuple, Optional
from collections import defaultdict


class CleanGraphRenderer:
    """Renders a clean, organized graph visualization."""
    
    # Default width, but can be expanded for horizontal scrolling
    DEFAULT_WIDTH = 100
    MIN_WIDTH = 70
    
    @classmethod
    def render(cls, nodes: Dict, edges: List[Tuple], width: Optional[int] = None, llm_context: Optional[Dict] = None) -> List[str]:
        """Render a clean graph visualization.
        
        Args:
            nodes: Dictionary of node data
            edges: List of edge tuples
            width: Optional width for the graph (defaults to DEFAULT_WIDTH)
            llm_context: Optional LLM context data to display
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
        lines.extend(cls._render_model_context(nodes, width, llm_context))
        
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
            # Skip relationships where either node is missing from UI data
            if from_id not in nodes or to_id not in nodes:
                continue
                
            from_node = nodes[from_id]
            to_node = nodes[to_id]
            
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
        content = node_data.get('content')
        context_type = node_data.get('context_type', '')
        
        # Handle None or empty content  
        if content is None:
            content = {}
        elif not isinstance(content, dict):
            content = {}
        
        # For entities - handle specially
        if context_type == 'domain_entity' and isinstance(content, dict):
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
        
        # For tool outputs - extract agent and tool name
        if context_type == 'tool_output' and isinstance(content, dict):
            # Handle agent response tool outputs
            agent_name = content.get('agent_name', '')
            tool_name = content.get('tool_name', '')
            if agent_name and tool_name:
                # Clean up tool name (remove prefixes)
                clean_tool = tool_name.replace('salesforce_', '').replace('jira_', '').replace('servicenow_', '')
                return f"{agent_name}:{clean_tool}"[:25]
            elif tool_name:
                clean_tool = tool_name.replace('salesforce_', '').replace('jira_', '').replace('servicenow_', '')
                return clean_tool[:25]
            
            # Handle agent call tool outputs (calls TO agents)
            tool = content.get('tool', '')
            if tool:
                # Extract the agent name from tool field
                if 'agent' in tool:
                    return f"call:{tool}"[:25]
                return f"tool:{tool}"[:25]
        
        # For completed actions - extract task name
        if context_type == 'completed_action' and isinstance(content, dict):
            task = content.get('task', '')
            if task:
                # Clean up task description
                task = task.replace('Retrieve the ', '').replace('Search for ', '').replace('Get ', '')
                return task[:25]
        
        # Try summary field as fallback
        summary = node_data.get('summary', '')
        if summary:
            # Handle "Tool call: agent_name" format specifically
            if summary.startswith('Tool call: '):
                tool_name = summary[11:].strip()  # Remove "Tool call: " prefix
                return f"call:{tool_name}"[:25]
            
            # If summary has format "Type: Name", extract the name
            if ':' in summary:
                parts = summary.split(':', 1)
                if len(parts) > 1 and parts[1].strip():
                    name_part = parts[1].strip() 
                    # Don't return empty or very short names
                    if len(name_part) > 1:
                        return name_part[:25]
            
            # For tool summaries like "salesforce executed salesforce_search"
            if 'executed' in summary:
                parts = summary.split('executed')
                if len(parts) > 1:
                    agent_tool = parts[1].strip()
                    # Remove parenthetical info
                    if '(' in agent_tool:
                        agent_tool = agent_tool.split('(')[0].strip()
                    return agent_tool.replace('_', ':')[:25]  # Make it more readable
            
            # Remove common prefixes and clean up
            cleaned_summary = summary
            for prefix in ['Completed: ', 'Retrieved ', 'Updated ', 'Found ', 'Searched for ', 'Step ']:
                if cleaned_summary.startswith(prefix):
                    cleaned_summary = cleaned_summary[len(prefix):]
                    break
            
            # Further cleanup for step descriptions
            if ' - ' in cleaned_summary:
                cleaned_summary = cleaned_summary.split(' - ')[0]
            
            # Don't return empty or very short strings
            if len(cleaned_summary.strip()) > 1:
                return cleaned_summary.strip()[:25]
        
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
    def _render_model_context(cls, nodes: Dict, width: int, llm_context: Optional[Dict] = None) -> List[str]:
        """Render the model context section showing what will be sent to LLM."""
        lines = []
        
        lines.append("╠" + "═" * width + "╣")
        lines.append("║" + " " * width + "║")
        lines.append("║" + "  🧠 MODEL CONTEXT (What LLM Sees)".ljust(width) + "║")
        lines.append("║" + "  ─────────────────────────────────".ljust(width) + "║")
        lines.append("║" + " " * width + "║")
        
        # Check if we have actual LLM context data
        # Note: We show the actual context even if context_text is empty, to distinguish
        # from "no context data available" vs "no relevant memories found"
        if llm_context and "context_text" in llm_context:
            # Show the actual context being sent to LLM
            context_type = llm_context.get("context_type", "unknown")
            metadata = llm_context.get("metadata", {})
            context_text = llm_context.get("context_text", "")
            
            # Add context type with emoji
            type_emoji = {
                "execution": "⚡",
                "planning": "📋",
                "replanning": "🔄"
            }.get(context_type, "📝")
            
            lines.append("║" + f"  {type_emoji} {context_type.title()} Context".ljust(width) + "║")
            
            # Add metadata stats
            if metadata:
                stats_line = "  "
                if "relevant_count" in metadata:
                    stats_line += f"Relevant: {metadata['relevant_count']} • "
                if "important_count" in metadata:
                    stats_line += f"Important: {metadata['important_count']} • "
                if "cluster_count" in metadata:
                    stats_line += f"Clusters: {metadata['cluster_count']} • "
                if "bridge_count" in metadata:
                    stats_line += f"Bridges: {metadata['bridge_count']}"
                lines.append("║" + stats_line.rstrip(" • ").ljust(width) + "║")
            
            lines.append("║" + " " * width + "║")
            
            # Show the actual context content (wrapped)
            if context_text:
                context_lines = context_text.split('\n')
                max_lines = 20  # Limit display
                shown_lines = 0
                
                for line in context_lines:
                    if shown_lines >= max_lines:
                        lines.append("║" + f"  ... ({len(context_lines) - shown_lines} more lines)".ljust(width) + "║")
                        break
                    # Wrap long lines
                    if len(line) > width - 4:
                        wrapped = cls._wrap_text(line, width - 4)
                        for wline in wrapped:
                            lines.append("║" + f"  {wline}".ljust(width) + "║")
                            shown_lines += 1
                            if shown_lines >= max_lines:
                                break
                    else:
                        lines.append("║" + f"  {line}".ljust(width) + "║")
                        shown_lines += 1
            else:
                # Context is empty - no relevant memories found
                lines.append("║" + "  No relevant memories found for this context.".ljust(width) + "║")
                lines.append("║" + "  The system will rely on the current conversation.".ljust(width) + "║")
                    
        else:
            # Fallback to simulated view when no actual context
            relevant_nodes = []
            for node_id, node_data in nodes.items():
                relevance = node_data.get('relevance', 0.0)
                if relevance > 0.5:
                    relevant_nodes.append((node_id, node_data, relevance))
            
            relevant_nodes.sort(key=lambda x: x[2], reverse=True)
            relevant_nodes = relevant_nodes[:8]
            
            if not relevant_nodes:
                lines.append("║" + "  No context selected yet (awaiting query)".ljust(width) + "║")
            else:
                total_available = len([n for n in nodes.values() if n.get('relevance', 0.0) > 0.5])
                lines.append("║" + f"  Simulated view: {len(relevant_nodes)} items (from {total_available} with relevance > 0.5)".ljust(width) + "║")
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
    
    @classmethod
    def _wrap_text(cls, text: str, max_width: int) -> List[str]:
        """Wrap text to fit within max_width."""
        if not text:
            return [""]
        
        words = text.split(' ')
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            word_length = len(word)
            if current_length + word_length + len(current_line) <= max_width:
                current_line.append(word)
                current_length += word_length
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = word_length
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines if lines else [""]