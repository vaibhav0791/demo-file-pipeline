"""
Phase 5 — Full STRING DB pipeline runner.

End-to-end orchestrator that:
  1. Accepts up to 80 gene symbols
  2. Resolves → fetches → canonicalizes → computes metrics → persists
  3. Exports results to CSV matching the Master Target Discovery schema
"""
import os
import csv
import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.string_record import StringRecord
from app.services.ingest_string import batch_ingest_string

logger = logging.getLogger(__name__)

# Column order matching the STRING-owned portion of
# Master_Target_Discovery_Pain.csv
STRING_CSV_COLUMNS = [
    "disease_id",
    "gene_symbol",
    "UniProt_ID",
    "STRING_ID",
    "partner_a",
    "partner_b",
    "combined_score",
    "interaction_count",
    "average_interaction_score",
    "degree_centrality",
    "betweenness_centrality",
    "closeness_centrality",
    "clustering_coefficient",
    "neighborhood_score",
    "fusion_score",
    "cooccurrence_score",
    "coexpression_score",
    "experimental_score",
    "database_score",
    "textmining_score",
]


def run_string_pipeline(
    db: Session,
    disease_id: str,
    gene_symbols: list[str],
    requested_by: str = "himanshu",
    interaction_limit: int = 50,
    export_csv: bool = True,
    output_dir: str = "output",
) -> dict[str, Any]:
    """
    Full Phase 5 pipeline:
      1. Run batch_ingest_string (Phases 1-4 combined)
      2. Query all StringRecords for the run
      3. Export to CSV
      4. Return complete summary
    """
    # ── Step 1: Ingest ──────────────────────────────────────────
    logger.info(
        "Starting STRING pipeline: %d genes for disease '%s'",
        len(gene_symbols), disease_id,
    )

    ingest_result = batch_ingest_string(
        db=db,
        disease_id=disease_id,
        gene_symbols=gene_symbols,
        requested_by=requested_by,
        interaction_limit=interaction_limit,
    )

    # ── Step 2: Query persisted records ─────────────────────────
    records = (
        db.query(StringRecord)
        .filter(StringRecord.disease_id == disease_id)
        .filter(StringRecord.gene_symbol.in_([g.upper() for g in gene_symbols]))
        .order_by(StringRecord.gene_symbol, StringRecord.id)
        .all()
    )

    logger.info("Total STRING records in DB for this run: %d", len(records))

    # ── Step 3: Export CSV ──────────────────────────────────────
    csv_path = None
    if export_csv and records:
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"STRING_{disease_id}_{timestamp}.csv"
        csv_path = os.path.join(output_dir, filename)

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=STRING_CSV_COLUMNS)
            writer.writeheader()

            for rec in records:
                writer.writerow({
                    "disease_id": rec.disease_id,
                    "gene_symbol": rec.gene_symbol,
                    "UniProt_ID": rec.uniprot_id or "",
                    "STRING_ID": rec.string_id.split(".", 1)[-1] if rec.string_id else "",
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

        logger.info("CSV exported to: %s", csv_path)

    # ── Step 4: Build summary ──────────────────────────────────
    gene_breakdown = {}
    for rec in records:
        gene_breakdown.setdefault(rec.gene_symbol, 0)
        gene_breakdown[rec.gene_symbol] += 1

    return {
        "status": "completed",
        "disease_id": disease_id,
        "requested_by": requested_by,
        "ingest_summary": ingest_result["summary"],
        "ingest_results": ingest_result["results"],
        "total_records_in_db": len(records),
        "genes_with_data": len(gene_breakdown),
        "rows_per_gene": gene_breakdown,
        "csv_exported": csv_path,
    }
