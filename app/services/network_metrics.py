"""
Phase 3 — Network metric computations using networkx.

Builds a weighted graph from STRING interaction data and computes
the four centrality / clustering metrics required by the Master
Target Discovery schema.
"""
import networkx as nx
from typing import Any


def build_interaction_graph(
    interactions: list[dict[str, Any]],
) -> nx.Graph:
    """
    Construct a weighted undirected graph from raw STRING interactions.

    Each edge connects preferredName_A ↔ preferredName_B with
    the combined `score` as edge weight.
    """
    G = nx.Graph()

    for inter in interactions:
        node_a = inter.get("preferredName_A", "")
        node_b = inter.get("preferredName_B", "")
        score = inter.get("score", 0)

        if node_a and node_b:
            # If edge already exists, keep the higher score
            if G.has_edge(node_a, node_b):
                existing = G[node_a][node_b]["weight"]
                G[node_a][node_b]["weight"] = max(existing, score)
            else:
                G.add_edge(node_a, node_b, weight=score)

    return G


def compute_centrality_metrics(
    G: nx.Graph,
    target_gene: str,
) -> dict[str, float]:
    """
    Compute the four Master Schema network metrics for a specific
    target gene node within the graph.

    Returns:
        {
            "Degree_Centrality":      float,
            "Betweenness_Centrality": float,
            "Closeness_Centrality":   float,
            "Clustering_Coefficient": float,
        }

    If the target gene is not in the graph, returns all zeros.
    """
    if target_gene not in G:
        return {
            "Degree_Centrality": 0.0,
            "Betweenness_Centrality": 0.0,
            "Closeness_Centrality": 0.0,
            "Clustering_Coefficient": 0.0,
        }

    # Compute graph-wide metrics (needed for per-node lookup)
    degree_cent = nx.degree_centrality(G)
    betweenness_cent = nx.betweenness_centrality(G, weight="weight")
    closeness_cent = nx.closeness_centrality(G, distance="weight")
    clustering_coeff = nx.clustering(G, weight="weight")

    return {
        "Degree_Centrality": round(degree_cent.get(target_gene, 0.0), 4),
        "Betweenness_Centrality": round(betweenness_cent.get(target_gene, 0.0), 4),
        "Closeness_Centrality": round(closeness_cent.get(target_gene, 0.0), 4),
        "Clustering_Coefficient": round(clustering_coeff.get(target_gene, 0.0), 4),
    }
