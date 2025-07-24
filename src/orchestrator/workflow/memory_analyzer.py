"""Memory graph analyzer for intelligent decision making."""

from typing import Dict, List, Any
from datetime import datetime, timedelta

from src.memory import get_thread_memory, ContextType
from src.utils.logging.framework import SmartLogger

logger = SmartLogger("orchestrator")


class MemoryAnalyzer:
    """Analyzes memory graph to provide insights for planning and execution."""
    
    @staticmethod
    def analyze_conversation_patterns(thread_id: str) -> Dict[str, Any]:
        """
        Analyze conversation patterns to understand user behavior and preferences.
        
        Returns:
            Dict containing pattern analysis:
            - topic_switches: Number of topic changes
            - repetitive_requests: Similar requests made multiple times
            - correction_patterns: Times user corrected or refined requests
            - preferred_detail_level: Brief vs detailed responses preferred
        """
        memory = get_thread_memory(thread_id)
        
        analysis = {
            "topic_switches": 0,
            "repetitive_requests": [],
            "correction_patterns": [],
            "preferred_detail_level": "unknown",
            "common_entities": [],
            "workflow_patterns": []
        }
        
        # Get all user requests
        user_nodes = []
        for node in memory.get_all_nodes():
            if node.context_type == ContextType.USER_SELECTION:
                user_nodes.append(node)
        
        if len(user_nodes) < 2:
            return analysis
        
        # Sort by time
        user_nodes.sort(key=lambda n: n.created_at)
        
        # Analyze topic switches using clusters
        clusters = memory.find_memory_clusters()
        if len(clusters) > 1:
            analysis["topic_switches"] = len(clusters) - 1
        
        # Find repetitive requests
        summaries = [n.summary.lower() for n in user_nodes]
        for i, summary in enumerate(summaries):
            similar_count = sum(1 for s in summaries[i+1:] if MemoryAnalyzer._similarity_score(summary, s) > 0.7)
            if similar_count > 0:
                analysis["repetitive_requests"].append({
                    "request": user_nodes[i].summary,
                    "count": similar_count + 1
                })
        
        # Find correction patterns (requests immediately after errors or clarifications)
        all_nodes = memory.get_all_nodes()
        all_nodes.sort(key=lambda n: n.created_at)
        
        for i, node in enumerate(all_nodes[:-1]):
            next_node = all_nodes[i + 1]
            if (node.context_type in {ContextType.TOOL_OUTPUT, ContextType.COMPLETED_ACTION} and
                next_node.context_type == ContextType.USER_SELECTION and
                (next_node.created_at - node.created_at) < timedelta(minutes=2)):
                # User quickly followed up - might be a correction
                analysis["correction_patterns"].append({
                    "original": node.summary,
                    "correction": next_node.summary
                })
        
        # Analyze preferred detail level
        response_lengths = []
        for node in all_nodes:
            if node.context_type == ContextType.TOOL_OUTPUT:
                response_lengths.append(len(str(node.content)))
        
        if response_lengths:
            avg_length = sum(response_lengths) / len(response_lengths)
            analysis["preferred_detail_level"] = "detailed" if avg_length > 500 else "brief"
        
        # Find common entities
        entity_nodes = [n for n in all_nodes if n.context_type == ContextType.DOMAIN_ENTITY]
        if entity_nodes:
            entity_counts = {}
            for node in entity_nodes:
                entity_id = node.content.get("entity_id", "") if isinstance(node.content, dict) else ""
                if entity_id:
                    entity_counts[entity_id] = entity_counts.get(entity_id, 0) + 1
            
            # Top 5 entities
            analysis["common_entities"] = sorted(
                entity_counts.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:5]
        
        return analysis
    
    @staticmethod
    def suggest_next_actions(thread_id: str, current_task: str) -> List[Dict[str, Any]]:
        """
        Suggest next actions based on memory patterns and graph analysis.
        
        Returns:
            List of suggested actions with confidence scores
        """
        memory = get_thread_memory(thread_id)
        suggestions = []
        
        # Get recent context (currently not used but kept for future enhancements)
        # recent_nodes = memory.retrieve_relevant(
        #     query_text=current_task,
        #     max_age_hours=1,
        #     max_results=10
        # )
        
        # Analyze patterns
        patterns = MemoryAnalyzer.analyze_conversation_patterns(thread_id)
        
        # Find important memories (currently not used but kept for future enhancements)
        # important_memories = memory.find_important_memories(top_n=5)
        
        # Bridge memories might indicate connections to explore
        bridge_memories = memory.find_bridge_memories(top_n=3)
        
        # Suggest based on patterns
        if patterns["repetitive_requests"]:
            for req in patterns["repetitive_requests"][:2]:
                suggestions.append({
                    "action": f"Consider creating a saved workflow for: {req['request']}",
                    "reason": f"User has made this request {req['count']} times",
                    "confidence": 0.8
                })
        
        # Suggest based on common entities
        if patterns["common_entities"]:
            top_entity = patterns["common_entities"][0]
            suggestions.append({
                "action": f"Proactively check for updates on {top_entity[0]}",
                "reason": f"This entity has been referenced {top_entity[1]} times",
                "confidence": 0.7
            })
        
        # Suggest based on bridge memories
        for bridge in bridge_memories[:1]:
            suggestions.append({
                "action": f"Connect current task to: {bridge.summary}",
                "reason": "This memory bridges different conversation topics",
                "confidence": 0.6
            })
        
        return suggestions
    
    @staticmethod
    def get_execution_insights(thread_id: str, task: str) -> Dict[str, Any]:
        """
        Get insights to improve task execution based on memory analysis.
        
        Returns:
            Dict with execution insights
        """
        memory = get_thread_memory(thread_id)
        
        insights = {
            "similar_past_tasks": [],
            "relevant_entities": [],
            "potential_pitfalls": [],
            "optimization_hints": []
        }
        
        # Find similar past tasks
        past_tasks = memory.retrieve_relevant(
            query_text=task,
            context_filter={ContextType.COMPLETED_ACTION, ContextType.TOOL_OUTPUT},
            max_age_hours=24,
            max_results=5
        )
        
        for past_task in past_tasks:
            if past_task.current_relevance() > 0.6:
                insights["similar_past_tasks"].append({
                    "task": past_task.summary,
                    "outcome": "successful" if "success" in past_task.summary.lower() else "completed",
                    "time_ago": MemoryAnalyzer._format_time_ago(past_task.created_at)
                })
        
        # Get relevant entities
        entity_nodes = memory.retrieve_relevant(
            query_text=task,
            context_filter={ContextType.DOMAIN_ENTITY},
            max_results=5
        )
        
        for entity in entity_nodes:
            if isinstance(entity.content, dict):
                insights["relevant_entities"].append({
                    "id": entity.content.get("entity_id", ""),
                    "name": entity.content.get("entity_name", ""),
                    "type": entity.content.get("entity_type", "")
                })
        
        # Check for past failures or corrections
        patterns = MemoryAnalyzer.analyze_conversation_patterns(thread_id)
        if patterns["correction_patterns"]:
            for correction in patterns["correction_patterns"][:2]:
                insights["potential_pitfalls"].append({
                    "warning": f"User previously corrected: {correction['original']}",
                    "correction": correction['correction']
                })
        
        # Add optimization hints based on graph metrics
        stats = memory.get_statistics()
        if stats["graph_density"] > 0.3:
            insights["optimization_hints"].append(
                "High memory density - consider being more specific in queries"
            )
        
        if len(patterns["common_entities"]) > 3:
            insights["optimization_hints"].append(
                "Multiple entities in play - ensure proper context when referencing them"
            )
        
        return insights
    
    @staticmethod
    def _similarity_score(text1: str, text2: str) -> float:
        """Simple similarity score between two texts."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    @staticmethod
    def _format_time_ago(timestamp: datetime) -> str:
        """Format timestamp as human-readable time ago."""
        delta = datetime.now() - timestamp
        
        if delta.total_seconds() < 60:
            return "just now"
        elif delta.total_seconds() < 3600:
            minutes = int(delta.total_seconds() / 60)
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        elif delta.total_seconds() < 86400:
            hours = int(delta.total_seconds() / 3600)
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        else:
            days = int(delta.total_seconds() / 86400)
            return f"{days} day{'s' if days > 1 else ''} ago"