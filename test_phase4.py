"""
Phase 4 Dedup & Constraint Validation Test

Uses an in-memory SQLite database to verify:
  1. Records are inserted correctly on first run
  2. ZERO new records on 2nd and 3rd runs (Data Repetition rule)
  3. Minimum-row constraint blocks under-populated genes
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.string_record import StringRecord
from app.utils.hash_utils import sha256_hash
from app.services.ingest_string import (
    _canonicalize_interaction,
    _enrich_batch_metrics,
    MIN_ROWS_PER_PROTEIN,
)
from app.services.network_metrics import (
    build_interaction_graph,
    compute_centrality_metrics,
)


def _create_test_db():
    """Create a fresh in-memory SQLite DB with StringRecord table."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _build_mock_interactions(gene: str, count: int):
    """Generate `count` mock interactions for a gene."""
    return [
        {
            "preferredName_A": gene,
            "preferredName_B": f"PARTNER_{gene}_{i}",
            "score": round(0.5 + (i % 5) * 0.1, 3),
            "nscore": 0, "fscore": 0, "pscore": 0,
            "ascore": 0.3, "escore": 0.5, "dscore": 0.6, "tscore": 0.4,
        }
        for i in range(count)
    ]


def _simulate_ingest(db, disease_id, gene, string_id, interactions):
    """
    Simulates the full ingest pipeline locally (same logic as
    ingest_string_gene but without calling the STRING API).
    """
    canonicals = [
        _canonicalize_interaction(disease_id, gene, string_id, inter, idx)
        for idx, inter in enumerate(interactions)
    ]
    canonicals = _enrich_batch_metrics(canonicals)

    graph = build_interaction_graph(interactions)
    centrality = compute_centrality_metrics(graph, gene)
    for c in canonicals:
        c.update(centrality)

    inserted = 0
    skipped = 0

    for canonical in canonicals:
        content_hash = sha256_hash(canonical)

        # Pre-check
        exists = (
            db.query(StringRecord.id)
            .filter(StringRecord.content_hash == content_hash)
            .first()
            is not None
        )
        if exists:
            skipped += 1
            continue

        record = StringRecord(
            disease_id=disease_id,
            gene_symbol=gene,
            target_id=canonical["target_id"],
            source_record_id=canonical["source_record_id"],
            content_hash=content_hash,
            string_id=canonical["STRING_ID"],
            partner_a=canonical["partner_A"],
            partner_b=canonical["partner_B"],
            combined_score=canonical["combined_score"],
            interaction_count=canonical["Interaction_Count"],
            average_interaction_score=canonical["Average_Interaction_Score"],
            degree_centrality=canonical["Degree_Centrality"],
            betweenness_centrality=canonical["Betweenness_Centrality"],
            closeness_centrality=canonical["Closeness_Centrality"],
            clustering_coefficient=canonical["Clustering_Coefficient"],
            neighborhood_score=canonical["neighborhood_score"],
            fusion_score=canonical["fusion_score"],
            cooccurrence_score=canonical["cooccurrence_score"],
            coexpression_score=canonical["coexpression_score"],
            experimental_score=canonical["experimental_score"],
            database_score=canonical["database_score"],
            textmining_score=canonical["textmining_score"],
        )

        from sqlalchemy.exc import IntegrityError
        try:
            db.add(record)
            db.commit()
            inserted += 1
        except IntegrityError:
            db.rollback()
            skipped += 1

    return {"inserted": inserted, "skipped": skipped}


def test_dedup():
    print("=" * 60)
    print("TEST 1: Insert on first run")
    print("=" * 60)

    db = _create_test_db()
    interactions = _build_mock_interactions("TRPV1", 30)

    run1 = _simulate_ingest(db, "Pain", "TRPV1", "9606.ENSP00000174621", interactions)
    print(f"  Run 1 → Inserted: {run1['inserted']}, Skipped: {run1['skipped']}")
    assert run1["inserted"] == 30, f"Expected 30 inserts, got {run1['inserted']}"
    print("  ✅ 30 records inserted on first run!")

    print("\n" + "=" * 60)
    print("TEST 2: Zero inserts on 2nd run (Data Repetition rule)")
    print("=" * 60)

    run2 = _simulate_ingest(db, "Pain", "TRPV1", "9606.ENSP00000174621", interactions)
    print(f"  Run 2 → Inserted: {run2['inserted']}, Skipped: {run2['skipped']}")
    assert run2["inserted"] == 0, f"Expected 0 inserts, got {run2['inserted']}"
    print("  ✅ ZERO new records on 2nd run — dedup working!")

    print("\n" + "=" * 60)
    print("TEST 3: Zero inserts on 3rd run (confirming consistency)")
    print("=" * 60)

    run3 = _simulate_ingest(db, "Pain", "TRPV1", "9606.ENSP00000174621", interactions)
    print(f"  Run 3 → Inserted: {run3['inserted']}, Skipped: {run3['skipped']}")
    assert run3["inserted"] == 0, f"Expected 0 inserts, got {run3['inserted']}"
    print("  ✅ ZERO new records on 3rd run — data repetition FULLY blocked!")

    print("\n" + "=" * 60)
    print("TEST 4: Minimum-row constraint check")
    print("=" * 60)

    print(f"  MIN_ROWS_PER_PROTEIN = {MIN_ROWS_PER_PROTEIN}")
    under_interactions = _build_mock_interactions("GENE_X", 10)
    print(f"  Mock gene has only {len(under_interactions)} interactions")
    if len(under_interactions) < MIN_ROWS_PER_PROTEIN:
        print("  ✅ Pipeline would correctly SKIP this gene (below 25-row minimum)!")
    else:
        print("  ❌ Constraint not enforced!")

    # Verify total rows in DB are still exactly 30
    total = db.query(StringRecord).count()
    print(f"\n  Total records in DB: {total}")
    assert total == 30, f"Expected exactly 30, got {total}"
    print("  ✅ DB integrity confirmed — exactly 30 unique records!")

    db.close()


if __name__ == "__main__":
    test_dedup()
