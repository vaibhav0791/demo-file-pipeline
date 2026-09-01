"""
Phase 5 — Full Integration Test

Uses an in-memory SQLite DB to simulate the ENTIRE pipeline:
  1. Ingest 5 mock genes (30 interactions each)
  2. Verify DB records
  3. Export CSV and verify file contents
  4. Re-run pipeline — verify 0 new inserts (dedup across runs)
  5. Verify CSV column alignment with Master schema
"""
import os
import csv
import tempfile
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
from app.services.pipeline_runner_string import STRING_CSV_COLUMNS


def _create_test_db():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _mock_interactions(gene, count=30):
    return [
        {
            "preferredName_A": gene,
            "preferredName_B": f"PARTNER_{gene}_{i}",
            "score": round(0.4 + (i % 6) * 0.1, 3),
            "nscore": 0, "fscore": 0, "pscore": 0,
            "ascore": 0.3, "escore": 0.5, "dscore": 0.6, "tscore": 0.4,
        }
        for i in range(count)
    ]


def _simulate_full_pipeline(db, disease_id, genes, output_dir):
    """Simulates run_string_pipeline without calling STRING API."""
    from sqlalchemy.exc import IntegrityError

    all_results = []
    for gene in genes:
        interactions = _mock_interactions(gene, 30)
        string_id = f"9606.ENSP_MOCK_{gene}"

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

            exists = (
                db.query(StringRecord.id)
                .filter(StringRecord.content_hash == content_hash)
                .first() is not None
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
            try:
                db.add(record)
                db.commit()
                inserted += 1
            except IntegrityError:
                db.rollback()
                skipped += 1

        all_results.append({"gene": gene, "inserted": inserted, "skipped": skipped})

    # Export CSV
    records = db.query(StringRecord).filter(
        StringRecord.disease_id == disease_id
    ).all()

    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, "test_pipeline_output.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=STRING_CSV_COLUMNS)
        writer.writeheader()
        for rec in records:
            writer.writerow({
                "disease_id": rec.disease_id,
                "gene_symbol": rec.gene_symbol,
                "STRING_ID": rec.string_id,
                "partner_a": rec.partner_a,
                "partner_b": rec.partner_b,
                "combined_score": rec.combined_score,
                "interaction_count": rec.interaction_count,
                "average_interaction_score": rec.average_interaction_score,
                "degree_centrality": rec.degree_centrality,
                "betweenness_centrality": rec.betweenness_centrality,
                "closeness_centrality": rec.closeness_centrality,
                "clustering_coefficient": rec.clustering_coefficient,
                "neighborhood_score": rec.neighborhood_score,
                "fusion_score": rec.fusion_score,
                "cooccurrence_score": rec.cooccurrence_score,
                "coexpression_score": rec.coexpression_score,
                "experimental_score": rec.experimental_score,
                "database_score": rec.database_score,
                "textmining_score": rec.textmining_score,
            })

    return all_results, records, csv_path


def test_full_pipeline():
    test_genes = ["TRPV1", "TRPA1", "SCN9A", "OPRM1", "OPRK1"]
    disease = "Pain"
    output_dir = tempfile.mkdtemp()

    # ── Run 1 ───────────────────────────────────────────────────
    print("=" * 60)
    print("TEST 1: Full pipeline run — 5 genes × 30 interactions")
    print("=" * 60)

    db = _create_test_db()
    results, records, csv_path = _simulate_full_pipeline(db, disease, test_genes, output_dir)

    total_inserted = sum(r["inserted"] for r in results)
    print(f"  Total inserted: {total_inserted}")
    assert total_inserted == 150, f"Expected 150, got {total_inserted}"
    print("  ✅ 150 records inserted (5 genes × 30 each)!")

    # ── Verify DB ───────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("TEST 2: Verify DB record count")
    print("=" * 60)

    db_count = db.query(StringRecord).count()
    print(f"  DB total: {db_count}")
    assert db_count == 150
    print("  ✅ DB has exactly 150 records!")

    # ── Verify per-gene counts ──────────────────────────────────
    print("\n" + "=" * 60)
    print("TEST 3: Verify per-gene row counts (≥25 minimum)")
    print("=" * 60)

    for gene in test_genes:
        count = db.query(StringRecord).filter(StringRecord.gene_symbol == gene).count()
        print(f"  {gene}: {count} rows", end="")
        assert count >= MIN_ROWS_PER_PROTEIN, f"{gene} has {count} < {MIN_ROWS_PER_PROTEIN}"
        print("  ✅")

    # ── Verify CSV ──────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("TEST 4: Verify CSV export")
    print("=" * 60)

    assert os.path.exists(csv_path), "CSV file not created!"
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        headers = reader.fieldnames

    print(f"  CSV rows: {len(rows)}")
    print(f"  CSV columns: {len(headers)}")
    assert len(rows) == 150
    assert headers == STRING_CSV_COLUMNS
    print(f"  ✅ CSV has 150 rows and all {len(STRING_CSV_COLUMNS)} columns match!")

    # ── Verify dedup on re-run ──────────────────────────────────
    print("\n" + "=" * 60)
    print("TEST 5: Re-run pipeline — verify ZERO new inserts")
    print("=" * 60)

    results2, _, _ = _simulate_full_pipeline(db, disease, test_genes, output_dir)
    total_inserted_2 = sum(r["inserted"] for r in results2)
    total_skipped_2 = sum(r["skipped"] for r in results2)
    print(f"  Run 2 → Inserted: {total_inserted_2}, Skipped: {total_skipped_2}")
    assert total_inserted_2 == 0
    print("  ✅ ZERO new inserts — data repetition fully blocked!")

    # ── Final DB integrity ──────────────────────────────────────
    print("\n" + "=" * 60)
    print("FINAL: DB integrity check")
    print("=" * 60)

    final_count = db.query(StringRecord).count()
    print(f"  Total records: {final_count}")
    assert final_count == 150
    print("  ✅ DB integrity: still exactly 150 unique records after 2 runs!")

    # Cleanup
    db.close()
    os.remove(csv_path)
    print(f"\n🎉 ALL PHASE 5 TESTS PASSED!")


if __name__ == "__main__":
    test_full_pipeline()
