"""
Phase 2 Offline Validation Test
Tests canonicalization logic WITHOUT needing a database or server.
"""
import pprint
from app.services.ingest_string import _canonicalize_interaction, _enrich_batch_metrics

def test_canonicalization():
    print("=" * 60)
    print("TEST: Canonicalization of a mock STRING interaction")
    print("=" * 60)

    # Simulated raw interaction from STRING API
    mock_interaction = {
        "preferredName_A": "TRPV1",
        "preferredName_B": "TRPA1",
        "score": 0.943,
        "nscore": 0.0,
        "fscore": 0.0,
        "pscore": 0.102,
        "ascore": 0.621,
        "escore": 0.854,
        "dscore": 0.9,
        "tscore": 0.873,
    }

    canonical = _canonicalize_interaction(
        disease_id="Pain",
        gene_symbol="TRPV1",
        string_id="9606.ENSP00000174621",
        interaction=mock_interaction,
        variant_index=0,
    )

    print("\nCanonical output:")
    pprint.pprint(canonical)

    # Verify key fields exist
    required_keys = [
        "disease_id", "gene_symbol", "source", "target_id",
        "source_record_id", "STRING_ID", "partner_A", "partner_B",
        "combined_score", "Interaction_Count", "Average_Interaction_Score",
        "Degree_Centrality", "Betweenness_Centrality",
        "Closeness_Centrality", "Clustering_Coefficient",
    ]
    missing = [k for k in required_keys if k not in canonical]
    if missing:
        print(f"\n❌ MISSING KEYS: {missing}")
    else:
        print(f"\n✅ All {len(required_keys)} required Master Schema keys present!")

    print("\n" + "=" * 60)
    print("TEST: Batch metric enrichment")
    print("=" * 60)

    # Create 3 mock canonicals
    mock_batch = [
        _canonicalize_interaction("Pain", "TRPV1", "9606.ENSP00000174621",
                                  {"preferredName_A": "TRPV1", "preferredName_B": f"GENE_{i}",
                                   "score": 0.5 + i * 0.1, "nscore": 0, "fscore": 0,
                                   "pscore": 0, "ascore": 0, "escore": 0, "dscore": 0, "tscore": 0}, i)
        for i in range(3)
    ]

    enriched = _enrich_batch_metrics(mock_batch)

    print(f"\nInteraction_Count: {enriched[0]['Interaction_Count']}  (expected: 3)")
    print(f"Average_Interaction_Score: {enriched[0]['Average_Interaction_Score']}  (expected: ~0.6)")

    if enriched[0]["Interaction_Count"] == 3:
        print("\n✅ Batch enrichment working correctly!")
    else:
        print("\n❌ Batch enrichment issue!")


if __name__ == "__main__":
    test_canonicalization()
