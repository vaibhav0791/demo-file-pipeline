"""
Phase 3 Offline Validation Test
Tests networkx graph construction and centrality computation
using mock STRING interaction data. No DB / API needed.
"""
import pprint
from app.services.network_metrics import build_interaction_graph, compute_centrality_metrics
from app.services.ingest_string import _canonicalize_interaction, _enrich_batch_metrics

def test_phase_3():
    # Simulate interactions like STRING would return for TRPV1
    mock_interactions = [
        {"preferredName_A": "TRPV1", "preferredName_B": "TRPA1",  "score": 0.943, "nscore": 0, "fscore": 0, "pscore": 0, "ascore": 0.6, "escore": 0.85, "dscore": 0.9, "tscore": 0.87},
        {"preferredName_A": "TRPV1", "preferredName_B": "SCN9A",  "score": 0.812, "nscore": 0, "fscore": 0, "pscore": 0, "ascore": 0.5, "escore": 0.7,  "dscore": 0.8, "tscore": 0.6},
        {"preferredName_A": "TRPV1", "preferredName_B": "OPRM1",  "score": 0.756, "nscore": 0, "fscore": 0, "pscore": 0, "ascore": 0.4, "escore": 0.6,  "dscore": 0.7, "tscore": 0.5},
        {"preferredName_A": "TRPA1", "preferredName_B": "SCN9A",  "score": 0.689, "nscore": 0, "fscore": 0, "pscore": 0, "ascore": 0.3, "escore": 0.5,  "dscore": 0.6, "tscore": 0.4},
        {"preferredName_A": "TRPA1", "preferredName_B": "SCN10A", "score": 0.534, "nscore": 0, "fscore": 0, "pscore": 0, "ascore": 0.2, "escore": 0.4,  "dscore": 0.5, "tscore": 0.3},
    ]

    print("=" * 60)
    print("TEST 1: Build interaction graph")
    print("=" * 60)

    graph = build_interaction_graph(mock_interactions)
    print(f"Nodes: {list(graph.nodes())}")
    print(f"Edges: {graph.number_of_edges()}")
    print(f"Node count: {graph.number_of_nodes()}")

    print("\n" + "=" * 60)
    print("TEST 2: Compute centrality metrics for TRPV1")
    print("=" * 60)

    metrics = compute_centrality_metrics(graph, "TRPV1")
    pprint.pprint(metrics)

    # Verify all 4 metrics are real numbers (not None)
    all_filled = all(
        isinstance(metrics[k], float) and metrics[k] >= 0
        for k in ["Degree_Centrality", "Betweenness_Centrality",
                   "Closeness_Centrality", "Clustering_Coefficient"]
    )

    if all_filled:
        print("\n✅ All 4 centrality metrics computed successfully!")
    else:
        print("\n❌ Some metrics are missing or invalid!")

    print("\n" + "=" * 60)
    print("TEST 3: Full pipeline — canonicalize + enrich + centrality")
    print("=" * 60)

    # Canonicalize
    canonicals = [
        _canonicalize_interaction("Pain", "TRPV1", "9606.ENSP00000174621", inter, idx)
        for idx, inter in enumerate(mock_interactions[:3])  # just TRPV1's interactions
    ]
    canonicals = _enrich_batch_metrics(canonicals)

    # Apply centrality
    for c in canonicals:
        c["Degree_Centrality"] = metrics["Degree_Centrality"]
        c["Betweenness_Centrality"] = metrics["Betweenness_Centrality"]
        c["Closeness_Centrality"] = metrics["Closeness_Centrality"]
        c["Clustering_Coefficient"] = metrics["Clustering_Coefficient"]

    # Show first row
    print("\nFirst canonical row (complete):")
    pprint.pprint(canonicals[0])

    # Verify nothing is None anymore
    none_keys = [k for k, v in canonicals[0].items() if v is None]
    if none_keys:
        print(f"\n❌ Still None: {none_keys}")
    else:
        print(f"\n✅ Zero None values! All {len(canonicals[0])} fields are populated!")


if __name__ == "__main__":
    test_phase_3()
