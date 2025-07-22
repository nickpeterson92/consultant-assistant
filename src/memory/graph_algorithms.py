"""Advanced graph algorithms for smarter memory retrieval.

This module implements graph-based algorithms to enhance memory retrieval:
- PageRank for identifying important memories
- Community detection for grouping related memories
- Betweenness centrality for finding bridge concepts
- Semantic similarity clustering
"""

import networkx as nx
from typing import Dict, List, Set, Optional, Tuple, Any
from collections import defaultdict
import numpy as np
from datetime import datetime, timedelta
import logging

from .memory_node import MemoryNode, ContextType
from src.utils.logging.framework import SmartLogger

logger = SmartLogger("memory")


class GraphAlgorithms:
    """Advanced graph algorithms for memory retrieval."""
    
    @staticmethod
    def calculate_pagerank(graph: nx.MultiDiGraph, 
                          personalization: Optional[Dict[str, float]] = None,
                          damping: float = 0.85) -> Dict[str, float]:
        """Calculate PageRank scores for nodes in the memory graph.
        
        PageRank identifies "important" memories based on their relationships.
        Memories that are frequently referenced or lead to many other memories
        get higher scores.
        
        Args:
            graph: The memory graph
            personalization: Optional bias towards specific nodes
            damping: PageRank damping factor (default 0.85)
            
        Returns:
            Dict mapping node_id to PageRank score
        """
        if len(graph) == 0:
            return {}
            
        try:
            # Convert multi-edges to weighted edges for PageRank
            simple_graph = nx.DiGraph()
            for u, v, data in graph.edges(data=True):
                if simple_graph.has_edge(u, v):
                    # Increase weight for multiple relationships
                    simple_graph[u][v]['weight'] += data.get('weight', 1.0)
                else:
                    simple_graph.add_edge(u, v, weight=data.get('weight', 1.0))
            
            # Calculate PageRank
            pagerank_scores = nx.pagerank(
                simple_graph,
                alpha=damping,
                personalization=personalization,
                weight='weight'
            )
            
            logger.debug("pagerank_calculated",
                        node_count=len(pagerank_scores),
                        top_scores=sorted(pagerank_scores.values(), reverse=True)[:5])
            
            return pagerank_scores
            
        except Exception as e:
            logger.error("pagerank_calculation_failed", error=str(e))
            return {node: 1.0/len(graph) for node in graph.nodes()}
    
    @staticmethod
    def detect_communities(graph: nx.MultiDiGraph) -> List[Set[str]]:
        """Detect communities of related memories using Louvain algorithm.
        
        Communities are groups of memories that are more densely connected
        to each other than to the rest of the graph. This helps identify
        related concepts and topics.
        
        Returns:
            List of sets, each containing node IDs in a community
        """
        if len(graph) == 0:
            return []
            
        try:
            # Convert to undirected graph for community detection
            undirected = graph.to_undirected()
            
            # Use Louvain algorithm for community detection
            communities = nx.community.louvain_communities(undirected)
            
            logger.info("communities_detected",
                       community_count=len(communities),
                       sizes=[len(c) for c in communities])
            
            return [set(community) for community in communities]
            
        except Exception as e:
            logger.error("community_detection_failed", error=str(e))
            # Fallback: each node is its own community
            return [{node} for node in graph.nodes()]
    
    @staticmethod
    def calculate_betweenness_centrality(graph: nx.MultiDiGraph,
                                       normalized: bool = True) -> Dict[str, float]:
        """Calculate betweenness centrality for nodes.
        
        Betweenness centrality identifies "bridge" memories that connect
        different parts of the memory graph. These are often important
        context nodes that link different topics.
        
        Args:
            graph: The memory graph
            normalized: Whether to normalize scores
            
        Returns:
            Dict mapping node_id to betweenness centrality score
        """
        if len(graph) == 0:
            return {}
            
        try:
            centrality = nx.betweenness_centrality(
                graph,
                normalized=normalized
            )
            
            logger.debug("betweenness_calculated",
                        node_count=len(centrality),
                        top_scores=sorted(centrality.values(), reverse=True)[:5])
            
            return centrality
            
        except Exception as e:
            logger.error("betweenness_calculation_failed", error=str(e))
            return {node: 0.0 for node in graph.nodes()}
    
    @staticmethod
    def find_activation_spreading(graph: nx.MultiDiGraph,
                                activated_nodes: Set[str],
                                decay_factor: float = 0.5,
                                max_hops: int = 3,
                                activation_threshold: float = 0.1) -> Dict[str, float]:
        """Simulate activation spreading from initially activated nodes.
        
        This models how activation spreads through the memory network,
        similar to how human memory activates related concepts.
        
        Args:
            graph: The memory graph
            activated_nodes: Initially activated node IDs
            decay_factor: How much activation decays per hop
            max_hops: Maximum spreading distance
            activation_threshold: Minimum activation to continue spreading
            
        Returns:
            Dict mapping node_id to activation level
        """
        activation_levels = defaultdict(float)
        
        # Initialize activation
        for node in activated_nodes:
            if node in graph:
                activation_levels[node] = 1.0
        
        # Spread activation
        for hop in range(max_hops):
            new_activations = defaultdict(float)
            
            for node, activation in activation_levels.items():
                if activation < activation_threshold:
                    continue
                    
                # Spread to neighbors
                for neighbor in graph.successors(node):
                    # Calculate spread based on edge weights
                    edge_data = graph.get_edge_data(node, neighbor)
                    total_weight = sum(data.get('weight', 1.0) for data in edge_data.values())
                    
                    spread_activation = activation * decay_factor * (total_weight / len(edge_data))
                    new_activations[neighbor] = max(new_activations[neighbor], spread_activation)
                
                # Also spread backwards (less strongly)
                for neighbor in graph.predecessors(node):
                    edge_data = graph.get_edge_data(neighbor, node)
                    total_weight = sum(data.get('weight', 1.0) for data in edge_data.values())
                    
                    spread_activation = activation * decay_factor * 0.7 * (total_weight / len(edge_data))
                    new_activations[neighbor] = max(new_activations[neighbor], spread_activation)
            
            # Update activation levels
            for node, activation in new_activations.items():
                if node not in activated_nodes:  # Don't override source activation
                    activation_levels[node] = max(activation_levels[node], activation)
        
        logger.debug("activation_spreading_complete",
                    initially_activated=len(activated_nodes),
                    total_activated=len(activation_levels),
                    max_hops=max_hops)
        
        return dict(activation_levels)
    
    @staticmethod
    def find_shortest_paths(graph: nx.MultiDiGraph,
                          source: str,
                          targets: Set[str]) -> Dict[str, List[str]]:
        """Find shortest paths from source to multiple targets.
        
        Useful for understanding how memories are connected and finding
        the chain of reasoning between concepts.
        
        Args:
            graph: The memory graph
            source: Source node ID
            targets: Set of target node IDs
            
        Returns:
            Dict mapping target node_id to shortest path (list of nodes)
        """
        paths = {}
        
        for target in targets:
            if target in graph:
                try:
                    path = nx.shortest_path(graph, source, target)
                    paths[target] = path
                except nx.NetworkXNoPath:
                    # No path exists
                    pass
        
        return paths
    
    @staticmethod
    def calculate_clustering_coefficient(graph: nx.MultiDiGraph) -> Dict[str, float]:
        """Calculate clustering coefficient for nodes.
        
        The clustering coefficient measures how well connected a node's
        neighbors are to each other. High clustering indicates tightly
        connected memory clusters.
        
        Returns:
            Dict mapping node_id to clustering coefficient
        """
        # Convert to undirected for clustering calculation
        undirected = graph.to_undirected()
        
        try:
            clustering = nx.clustering(undirected)
            
            logger.debug("clustering_calculated",
                        average_clustering=nx.average_clustering(undirected),
                        node_count=len(clustering))
            
            return clustering
            
        except Exception as e:
            logger.error("clustering_calculation_failed", error=str(e))
            return {node: 0.0 for node in graph.nodes()}
    
    @staticmethod
    def identify_memory_hubs(graph: nx.MultiDiGraph,
                           min_connections: int = 5) -> List[str]:
        """Identify hub nodes with many connections.
        
        Hubs are memories that connect to many other memories and often
        represent central concepts or important events.
        
        Args:
            graph: The memory graph
            min_connections: Minimum connections to be considered a hub
            
        Returns:
            List of hub node IDs
        """
        hubs = []
        
        for node in graph.nodes():
            in_degree = graph.in_degree(node)
            out_degree = graph.out_degree(node)
            total_connections = in_degree + out_degree
            
            if total_connections >= min_connections:
                hubs.append(node)
        
        logger.info("memory_hubs_identified",
                   hub_count=len(hubs),
                   min_connections=min_connections)
        
        return hubs
    
    @staticmethod
    def temporal_clustering(nodes: Dict[str, MemoryNode],
                          time_window: timedelta = timedelta(minutes=30)) -> List[List[str]]:
        """Group memories by temporal proximity.
        
        Memories created close in time are often related. This identifies
        temporal clusters of memories.
        
        Args:
            nodes: Dict of node_id to MemoryNode
            time_window: Time window for clustering
            
        Returns:
            List of clusters, each cluster is a list of node IDs
        """
        # Sort nodes by creation time
        sorted_nodes = sorted(nodes.items(), key=lambda x: x[1].created_at)
        
        clusters = []
        current_cluster = []
        cluster_start = None
        
        for node_id, node in sorted_nodes:
            if not current_cluster:
                current_cluster = [node_id]
                cluster_start = node.created_at
            elif node.created_at - cluster_start <= time_window:
                current_cluster.append(node_id)
            else:
                if len(current_cluster) > 1:
                    clusters.append(current_cluster)
                current_cluster = [node_id]
                cluster_start = node.created_at
        
        # Don't forget the last cluster
        if len(current_cluster) > 1:
            clusters.append(current_cluster)
        
        logger.info("temporal_clusters_found",
                   cluster_count=len(clusters),
                   time_window_minutes=time_window.total_seconds() / 60)
        
        return clusters