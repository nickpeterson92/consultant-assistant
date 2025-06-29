"""Workflow Router - Intelligent workflow selection"""

import re
from typing import Optional, List, Tuple
from .config import WORKFLOW_ROUTING_RULES


class WorkflowRouter:
    """Routes instructions to appropriate workflows using pattern matching"""
    
    def __init__(self, routing_rules: List[Tuple[str, str]] = None):
        """Initialize router with optional custom routing rules"""
        self.routing_rules = routing_rules or WORKFLOW_ROUTING_RULES
        # Pre-compile regex patterns for performance
        self.compiled_rules = [
            (re.compile(pattern, re.IGNORECASE), workflow)
            for pattern, workflow in self.routing_rules
        ]
    
    def select_workflow(self, instruction: str) -> Optional[str]:
        """Select the appropriate workflow based on instruction"""
        if not instruction:
            return None
            
        # Try each pattern in order
        for pattern, workflow_name in self.compiled_rules:
            if pattern.search(instruction):
                return workflow_name
        
        return None
    
    def add_rule(self, pattern: str, workflow_name: str, priority: int = -1):
        """Add a new routing rule
        
        Args:
            pattern: Regex pattern to match
            workflow_name: Name of workflow to route to
            priority: Position in rules list (-1 for end)
        """
        compiled_pattern = re.compile(pattern, re.IGNORECASE)
        
        if priority >= 0 and priority < len(self.compiled_rules):
            self.compiled_rules.insert(priority, (compiled_pattern, workflow_name))
            self.routing_rules.insert(priority, (pattern, workflow_name))
        else:
            self.compiled_rules.append((compiled_pattern, workflow_name))
            self.routing_rules.append((pattern, workflow_name))
    
    def remove_rule(self, workflow_name: str) -> bool:
        """Remove all rules for a specific workflow"""
        original_count = len(self.compiled_rules)
        
        self.compiled_rules = [
            (pattern, wf_name) 
            for pattern, wf_name in self.compiled_rules 
            if wf_name != workflow_name
        ]
        
        self.routing_rules = [
            (pattern, wf_name) 
            for pattern, wf_name in self.routing_rules 
            if wf_name != workflow_name
        ]
        
        return len(self.compiled_rules) < original_count
    
    def get_confidence(self, instruction: str, workflow_name: str) -> float:
        """Get confidence score for a workflow selection
        
        Returns:
            Confidence score between 0.0 and 1.0
        """
        matches = 0
        total_patterns = 0
        
        for pattern, wf_name in self.compiled_rules:
            if wf_name == workflow_name:
                total_patterns += 1
                if pattern.search(instruction):
                    matches += 1
        
        if total_patterns == 0:
            return 0.0
            
        return matches / total_patterns