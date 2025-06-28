"""Table formatting and display utilities for terminal output."""

from typing import List, Dict, Any, Optional, Union
from .terminal import visible_length, strip_ansi
from .colors import CYAN, BOLD, RESET, DIM


class TableFormatter:
    """Advanced table formatting for terminal display."""
    
    def __init__(self, headers: List[str], 
                 data: List[List[Any]],
                 column_widths: Optional[List[int]] = None,
                 alignment: Optional[List[str]] = None,
                 title: Optional[str] = None):
        """Initialize table formatter.
        
        Args:
            headers: Column headers
            data: Table data rows
            column_widths: Optional fixed column widths
            alignment: Optional column alignments ('left', 'right', 'center')
            title: Optional table title
        """
        self.headers = headers
        self.data = data
        self.title = title
        self.alignment = alignment or ['left'] * len(headers)
        
        # Calculate column widths if not provided
        if column_widths:
            self.column_widths = column_widths
        else:
            self.column_widths = self._calculate_column_widths()
    
    def _calculate_column_widths(self) -> List[int]:
        """Calculate optimal column widths based on content."""
        widths = []
        
        for i, header in enumerate(self.headers):
            max_width = visible_length(str(header))
            
            for row in self.data:
                if i < len(row):
                    cell_width = visible_length(str(row[i]))
                    max_width = max(max_width, cell_width)
            
            widths.append(max_width)
        
        return widths
    
    def _align_text(self, text: str, width: int, alignment: str) -> str:
        """Align text within given width."""
        text_len = visible_length(text)
        padding = width - text_len
        
        if padding <= 0:
            return text
        
        if alignment == 'right':
            return ' ' * padding + text
        elif alignment == 'center':
            left_pad = padding // 2
            right_pad = padding - left_pad
            return ' ' * left_pad + text + ' ' * right_pad
        else:  # left
            return text + ' ' * padding
    
    def format_simple(self) -> str:
        """Format as a simple ASCII table."""
        lines = []
        
        # Title
        if self.title:
            lines.append(f"{BOLD}{self.title}{RESET}")
            lines.append("")
        
        # Headers
        header_cells = []
        for i, header in enumerate(self.headers):
            aligned = self._align_text(header, self.column_widths[i], 'center')
            header_cells.append(f"{BOLD}{aligned}{RESET}")
        lines.append(' | '.join(header_cells))
        
        # Separator
        separators = ['-' * width for width in self.column_widths]
        lines.append('-+-'.join(separators))
        
        # Data rows
        for row in self.data:
            cells = []
            for i in range(len(self.headers)):
                if i < len(row):
                    text = str(row[i])
                else:
                    text = ''
                aligned = self._align_text(text, self.column_widths[i], self.alignment[i])
                cells.append(aligned)
            lines.append(' | '.join(cells))
        
        return '\n'.join(lines)
    
    def format_box(self) -> str:
        """Format as a box-drawing table."""
        lines = []
        
        # Box drawing characters
        tl, tr, bl, br = '┌', '┐', '└', '┘'
        h, v = '─', '│'
        tj, bj, lj, rj, cross = '┬', '┴', '├', '┤', '┼'
        
        # Calculate total width
        total_width = sum(self.column_widths) + len(self.column_widths) * 3 - 1
        
        # Title
        if self.title:
            title_line = f" {self.title} "
            padding = total_width - len(title_line)
            left_pad = padding // 2
            right_pad = padding - left_pad
            lines.append(tl + h * left_pad + title_line + h * right_pad + tr)
        else:
            # Top border
            border_parts = []
            for i, width in enumerate(self.column_widths):
                border_parts.append(h * (width + 2))
            lines.append(tl + tj.join(border_parts) + tr)
        
        # Headers
        header_cells = []
        for i, header in enumerate(self.headers):
            aligned = self._align_text(header, self.column_widths[i], 'center')
            header_cells.append(f" {BOLD}{CYAN}{aligned}{RESET} ")
        lines.append(v + v.join(header_cells) + v)
        
        # Header separator
        sep_parts = []
        for width in self.column_widths:
            sep_parts.append(h * (width + 2))
        lines.append(lj + cross.join(sep_parts) + rj)
        
        # Data rows
        for row_idx, row in enumerate(self.data):
            cells = []
            for i in range(len(self.headers)):
                if i < len(row):
                    text = str(row[i])
                else:
                    text = ''
                aligned = self._align_text(text, self.column_widths[i], self.alignment[i])
                cells.append(f" {aligned} ")
            lines.append(v + v.join(cells) + v)
        
        # Bottom border
        bottom_parts = []
        for width in self.column_widths:
            bottom_parts.append(h * (width + 2))
        lines.append(bl + bj.join(bottom_parts) + br)
        
        return '\n'.join(lines)
    
    def format_minimal(self) -> str:
        """Format as a minimal table with just spacing."""
        lines = []
        
        # Title
        if self.title:
            lines.append(f"{BOLD}{self.title}{RESET}")
            lines.append("")
        
        # Headers
        header_cells = []
        for i, header in enumerate(self.headers):
            aligned = self._align_text(header, self.column_widths[i], self.alignment[i])
            header_cells.append(f"{DIM}{aligned}{RESET}")
        lines.append('  '.join(header_cells))
        
        # Data rows
        for row in self.data:
            cells = []
            for i in range(len(self.headers)):
                if i < len(row):
                    text = str(row[i])
                else:
                    text = ''
                aligned = self._align_text(text, self.column_widths[i], self.alignment[i])
                cells.append(aligned)
            lines.append('  '.join(cells))
        
        return '\n'.join(lines)


def create_simple_table(headers: List[str], rows: List[List[Any]], 
                       title: Optional[str] = None) -> str:
    """Create a simple formatted table.
    
    Args:
        headers: Column headers
        rows: Data rows
        title: Optional table title
        
    Returns:
        Formatted table string
    """
    formatter = TableFormatter(headers, rows, title=title)
    return formatter.format_simple()


def create_box_table(headers: List[str], rows: List[List[Any]], 
                    title: Optional[str] = None,
                    alignment: Optional[List[str]] = None) -> str:
    """Create a box-drawing formatted table.
    
    Args:
        headers: Column headers
        rows: Data rows
        title: Optional table title
        alignment: Optional column alignments
        
    Returns:
        Formatted table string
    """
    formatter = TableFormatter(headers, rows, title=title, alignment=alignment)
    return formatter.format_box()


def format_record_table(records: List[Dict[str, Any]], 
                       fields: Optional[List[str]] = None,
                       max_width: Optional[int] = None) -> str:
    """Format a list of records as a table.
    
    Args:
        records: List of record dictionaries
        fields: Fields to display (uses all if None)
        max_width: Maximum width for each column
        
    Returns:
        Formatted table string
    """
    if not records:
        return "No records to display"
    
    # Determine fields to display
    if fields is None:
        fields = list(records[0].keys())
    
    # Extract data
    headers = fields
    rows = []
    for record in records:
        row = [record.get(field, '') for field in fields]
        rows.append(row)
    
    # Apply max width if specified
    if max_width:
        for i, row in enumerate(rows):
            for j, cell in enumerate(row):
                cell_str = str(cell)
                if len(cell_str) > max_width:
                    rows[i][j] = cell_str[:max_width-3] + '...'
    
    return create_box_table(headers, rows)