"""Enhanced memory context builder using advanced graph features."""

from typing import List, Dict, Any, Set, Tuple

from src.memory import get_user_memory, MemoryNode
from src.utils.logging.framework import SmartLogger

logger = SmartLogger("orchestrator")


class MemoryContextBuilder:
    """Builds intelligent memory context using PageRank, clustering, and bridge detection."""
    
    @staticmethod
    async def build_enhanced_context(
        thread_id: str,
        query_text: str,
        context_type: str = "execution",
        max_age_hours: float = 2.0,
        min_relevance: float = 0.3,
        max_results: int = 10
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build enhanced memory context using advanced graph features.
        
        Searches both user-specific memories AND global domain entities.
        
        Args:
            thread_id: Thread ID for memory
            query_text: Query to search for
            context_type: Type of context (execution, planning, replanning)
            max_age_hours: Maximum age of memories to consider
            min_relevance: Minimum relevance score
            max_results: Maximum number of results
            
        Returns:
            Tuple of (formatted_context, metadata)
        """
        from src.memory import get_memory_manager
        from src.memory.core.memory_node import ContextType
        
        memory = await get_user_memory(thread_id)
        
        # Get basic relevant memories from user's memory
        # Filter to only include domain entities and conversation facts, not action history
        relevant_memories = memory.retrieve_relevant(
            query_text=query_text,
            context_filter={ContextType.DOMAIN_ENTITY, ContextType.CONVERSATION_FACT, ContextType.USER_SELECTION},
            max_age_hours=max_age_hours,
            min_relevance=min_relevance,
            max_results=max_results
        )
        
        # Also search global domain entities
        memory_manager = get_memory_manager()
        # Ensure global entities are loaded from PostgreSQL
        await memory_manager.ensure_user_memories_loaded("global_domain_entities")
        global_memory = await memory_manager.get_memory("global_domain_entities")
        global_entities = global_memory.retrieve_relevant(
            query_text=query_text,
            context_filter={ContextType.DOMAIN_ENTITY},
            max_results=max_results // 2  # Take half from global
        )
        
        logger.info("global_entities_retrieved",
                   query_text=query_text,
                   global_entities_count=len(global_entities),
                   global_entity_summaries=[e.summary for e in global_entities[:3]],
                   context_type=context_type)
        
        # Combine user memories with global entities
        all_relevant = relevant_memories + global_entities
        
        # Get important memories using PageRank
        important_memories = memory.find_important_memories(top_n=5)
        
        # Get memory clusters
        clusters = memory.find_memory_clusters()
        
        # Get bridge memories that connect clusters
        bridge_memories = memory.find_bridge_memories(top_n=3)
        
        # Build context based on type
        if context_type == "planning":
            return MemoryContextBuilder._build_planning_context(
                all_relevant, important_memories, clusters, bridge_memories
            )
        elif context_type == "replanning":
            return MemoryContextBuilder._build_replanning_context(
                all_relevant, important_memories, clusters, bridge_memories
            )
        else:  # execution
            return MemoryContextBuilder._build_execution_context(
                all_relevant, important_memories, clusters, bridge_memories
            )
    
    @staticmethod
    def _build_execution_context(
        relevant_memories: List[MemoryNode],
        important_memories: List[MemoryNode],
        clusters: List[Set[str]],
        bridge_memories: List[MemoryNode]
    ) -> Tuple[str, Dict[str, Any]]:
        """Build context for task execution."""
        from src.memory.core.memory_node import ContextType
        context_parts = []
        metadata = {
            "relevant_count": len(relevant_memories),
            "important_count": len(important_memories),
            "cluster_count": len(clusters),
            "bridge_count": len(bridge_memories)
        }
        
        # Start with most relevant memories
        if relevant_memories:
            context_parts.append("\n\nCONVERSATION CONTEXT:")
            
            # Deduplicate memories (relevant might overlap with important)
            seen_ids = set()
            
            # First add highly relevant memories
            for memory in relevant_memories[:5]:
                if memory.node_id not in seen_ids:
                    seen_ids.add(memory.node_id)
                    relevance = memory.current_relevance()
                    context_parts.append(f"- {memory.summary}")
                    
                    # Include details for high relevance
                    if relevance > 0.7:
                        content_preview = str(memory.content)[:200]
                        context_parts.append(f"  Details: {content_preview}{'...' if len(str(memory.content)) > 200 else ''}")
            
            # Add important memories that aren't already included
            # Filter out completed actions - only include entities and facts
            important_not_seen = [
                m for m in important_memories 
                if m.node_id not in seen_ids 
                and m.context_type in {ContextType.DOMAIN_ENTITY, ContextType.CONVERSATION_FACT, ContextType.USER_SELECTION}
            ]
            if important_not_seen:
                context_parts.append("\nIMPORTANT CONTEXT (frequently referenced):")
                for memory in important_not_seen[:3]:
                    seen_ids.add(memory.node_id)
                    context_parts.append(f"- {memory.summary}")
            
            # Add bridge memories if they connect to current context
            # Filter out completed actions
            bridge_not_seen = [
                m for m in bridge_memories 
                if m.node_id not in seen_ids
                and m.context_type in {ContextType.DOMAIN_ENTITY, ContextType.CONVERSATION_FACT, ContextType.USER_SELECTION}
            ]
            if bridge_not_seen and len(clusters) > 1:
                context_parts.append("\nCONNECTING CONTEXT (links different topics):")
                for memory in bridge_not_seen[:2]:
                    context_parts.append(f"- {memory.summary}")
            
            context_parts.append("\nGUIDANCE: When user requests are ambiguous, connect them to recent conversation context above - they likely reference items they just discussed.")
        
        return "\n".join(context_parts), metadata
    
    @staticmethod
    def _build_planning_context(
        relevant_memories: List[MemoryNode],
        important_memories: List[MemoryNode],
        clusters: List[Set[str]],
        bridge_memories: List[MemoryNode]
    ) -> Tuple[str, Dict[str, Any]]:
        """Build context for planning phase."""
        from src.memory.core.memory_node import ContextType
        context_parts = []
        metadata = {
            "relevant_count": len(relevant_memories),
            "important_count": len(important_memories),
            "cluster_count": len(clusters),
            "bridge_count": len(bridge_memories)
        }
        
        if relevant_memories or important_memories:
            context_parts.append("\n\nRELEVANT CONTEXT:")
            
            # For planning, focus on important memories and patterns
            seen_ids = set()
            
            # Start with important memories (they represent key topics)
            # Filter out completed actions
            filtered_important = [
                m for m in important_memories[:5]
                if m.context_type in {ContextType.DOMAIN_ENTITY, ContextType.CONVERSATION_FACT, ContextType.USER_SELECTION}
            ]
            for memory in filtered_important:
                if memory.node_id not in seen_ids:
                    seen_ids.add(memory.node_id)
                    context_parts.append(f"- {memory.summary}")
            
            # Add relevant memories not already included
            for memory in relevant_memories[:5]:
                if memory.node_id not in seen_ids:
                    seen_ids.add(memory.node_id)
                    context_parts.append(f"- {memory.summary}")
            
            # If we have multiple clusters, mention the different topics
            if len(clusters) > 1:
                context_parts.append(f"\nNOTE: Conversation involves {len(clusters)} distinct topic areas.")
                
                # Use bridge memories to show connections
                if bridge_memories:
                    context_parts.append("Key connections between topics:")
                    filtered_bridges = [
                        m for m in bridge_memories[:2]
                        if m.context_type in {ContextType.DOMAIN_ENTITY, ContextType.CONVERSATION_FACT, ContextType.USER_SELECTION}
                    ]
                    for memory in filtered_bridges:
                        if memory.node_id not in seen_ids:
                            context_parts.append(f"- {memory.summary}")
        
        return "\n".join(context_parts), metadata
    
    @staticmethod
    def _build_replanning_context(
        relevant_memories: List[MemoryNode],
        important_memories: List[MemoryNode],
        clusters: List[Set[str]],
        bridge_memories: List[MemoryNode]
    ) -> Tuple[str, Dict[str, Any]]:
        """Build context for replanning phase."""
        from src.memory.core.memory_node import ContextType
        context_parts = []
        metadata = {
            "relevant_count": len(relevant_memories),
            "important_count": len(important_memories),
            "cluster_count": len(clusters),
            "bridge_count": len(bridge_memories)
        }
        
        if relevant_memories:
            context_parts.append("\n\nRECENT CONTEXT:")
            
            # For replanning, focus on very recent and high-relevance items
            seen_ids = set()
            
            # Recent relevant memories first - FILTER OUT completed actions
            filtered_memories = [
                m for m in relevant_memories
                if m.context_type in {ContextType.DOMAIN_ENTITY, ContextType.CONVERSATION_FACT, ContextType.USER_SELECTION}
            ]
            
            for memory in filtered_memories[:7]:
                if memory.node_id not in seen_ids:
                    seen_ids.add(memory.node_id)
                    context_parts.append(f"- {memory.summary}")
                    
                    # Include more details for replanning decisions
                    if memory.current_relevance() > 0.7:
                        content_preview = str(memory.content)[:150]
                        context_parts.append(f"  Details: {content_preview}{'...' if len(str(memory.content)) > 150 else ''}")
            
            # Add any critical bridge memories - FILTER OUT completed actions
            if bridge_memories and len(clusters) > 1:
                filtered_bridges = [
                    m for m in bridge_memories
                    if m.context_type in {ContextType.DOMAIN_ENTITY, ContextType.CONVERSATION_FACT, ContextType.USER_SELECTION}
                ]
                if filtered_bridges:
                    context_parts.append("\nCRITICAL CONNECTIONS:")
                    for memory in filtered_bridges[:1]:
                        if memory.node_id not in seen_ids:
                            context_parts.append(f"- {memory.summary}")
        
        return "\n".join(context_parts), metadata
    
    @staticmethod
    async def get_conversation_summary(thread_id: str, max_nodes: int = 20) -> str:
        """
        Generate a conversation summary using important memories and clusters.
        
        Args:
            thread_id: Thread ID
            max_nodes: Maximum nodes to consider
            
        Returns:
            Formatted conversation summary
        """
        memory = await get_user_memory(thread_id)
        
        # Get important memories
        important_memories = memory.find_important_memories(top_n=10)
        
        if not important_memories:
            return ""
        
        # Get clusters to understand topic groupings
        clusters = memory.find_memory_clusters()
        
        summary_parts = ["CONVERSATION SUMMARY:"]
        
        # Group memories by context type
        by_type = {}
        for memory in important_memories:
            ctx_type = memory.context_type.value
            if ctx_type not in by_type:
                by_type[ctx_type] = []
            by_type[ctx_type].append(memory)
        
        # Summarize key user requests
        if "user_selection" in by_type:
            summary_parts.append("\nUser Requests:")
            for memory in by_type["user_selection"][:3]:
                summary_parts.append(f"- {memory.summary}")
        
        # Summarize key actions taken
        if "tool_output" in by_type:
            summary_parts.append("\nActions Taken:")
            for memory in by_type["tool_output"][:3]:
                summary_parts.append(f"- {memory.summary}")
        
        # Mention topic diversity if multiple clusters
        if len(clusters) > 1:
            summary_parts.append(f"\nConversation covers {len(clusters)} distinct topics.")
        
        return "\n".join(summary_parts)