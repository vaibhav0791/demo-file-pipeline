"""
Phase 2 + 3 + 4 — STRING DB ingestion service.

Transforms raw STRING API responses into the canonical schema
expected by the Master Target Discovery dataset, computes network
centrality metrics via networkx, then persists each record to the
dedicated StringRecord table with hash dedup and constraint enforcement.
"""
import logging
from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.string_record import StringRecord
from app.utils.hash_utils import sha256_hash
from app.connectors.string_connector import (
    map_identifiers_to_string_ids,
    fetch_interaction_partners,
    fetch_network,
)
from app.connectors.uniprot_id_mapper import map_string_to_uniprot
from app.services.network_metrics import (
    build_interaction_graph,
    compute_centrality_metrics,
)

logger = logging.getLogger(__name__)

# ── Pipeline constraints (⁠from pipeline requirement.txt) ───────────
MIN_ROWS_PER_PROTEIN = 25    # each protein must yield ≥ 25 rows


# ── Canonicalization ────────────────────────────────────────────────

def _canonicalize_interaction(
    disease_id: str,
    gene_symbol: str,
    string_id: str,
    interaction: dict[str, Any],
    variant_index: int,
) -> dict[str, Any]:
    """
    Map a single STRING interaction dict into the Master Dataset
    columns owned by the STRING pipeline.

    Master columns produced:
      STRING_ID, Interaction_Count (set later at batch level),
      Average_Interaction_Score (set later),
      Degree_Centrality, Betweenness_Centrality,
      Closeness_Centrality, Clustering_Coefficient  (Phase 3)
    """
    partner_a = interaction.get("preferredName_A", "")
    partner_b = interaction.get("preferredName_B", "")
    score = interaction.get("score", 0)
    nscore = interaction.get("nscore", 0)
    fscore = interaction.get("fscore", 0)
    pscore = interaction.get("pscore", 0)
    ascore = interaction.get("ascore", 0)
    escore = interaction.get("escore", 0)
    dscore = interaction.get("dscore", 0)
    tscore = interaction.get("tscore", 0)

    # Unique source_record_id per interaction variant
    source_record_id = f"{string_id}__interact__{partner_b}__{variant_index}"

    return {
        "disease_id": disease_id,
        "gene_symbol": gene_symbol,
        "source": "string",
        "target_id": string_id,
        "source_record_id": source_record_id,

        # ── STRING master columns ───────────────────────────────
        "STRING_ID": string_id,
        "partner_A": partner_a,
        "partner_B": partner_b,
        "combined_score": score,
        "neighborhood_score": nscore,
        "fusion_score": fscore,
        "cooccurrence_score": pscore,
        "coexpression_score": ascore,
        "experimental_score": escore,
        "database_score": dscore,
        "textmining_score": tscore,

        # Placeholders — filled by the batch summary / Phase 3
        "Interaction_Count": None,
        "Average_Interaction_Score": None,
        "Degree_Centrality": None,
        "Betweenness_Centrality": None,
        "Closeness_Centrality": None,
        "Clustering_Coefficient": None,
    }


def _enrich_batch_metrics(
    canonicals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Fill Interaction_Count and Average_Interaction_Score across
    the batch of canonicalized rows for a single gene.
    """
    count = len(canonicals)
    avg_score = (
        sum(c["combined_score"] for c in canonicals) / count
        if count > 0 else 0.0
    )

    for c in canonicals:
        c["Interaction_Count"] = count
        c["Average_Interaction_Score"] = round(avg_score, 4)

    return canonicals


# ── Single‑gene ingestion ──────────────────────────────────────────

def _hash_exists(db: Session, content_hash: str) -> bool:
    """Phase 4 — explicit pre-check: does this hash already exist?"""
    return (
        db.query(StringRecord.id)
        .filter(StringRecord.content_hash == content_hash)
        .first()
        is not None
    )


def ingest_string_gene(
    db: Session,
    disease_id: str,
    gene_symbol: str,
    string_id: str,
    interaction_limit: int = 50,
    uniprot_id: str | None = None,
) -> dict[str, Any]:
    """
    Fetch interaction partners for one gene, canonicalize each row,
    enrich batch-level metrics, compute network centrality (Phase 3),
    enforce data-volume constraint (Phase 4), then persist with
    hash dedup.

    Returns a summary dict: inserted / skipped / total_fetched.
    """
    raw_interactions = fetch_interaction_partners(
        string_id,
        limit=interaction_limit,
    )

    # ── Phase 4: enforce minimum data-volume constraint ─────────
    if len(raw_interactions) < MIN_ROWS_PER_PROTEIN:
        logger.warning(
            "Gene %s returned only %d interactions (minimum %d). "
            "Skipping to avoid under-populated data.",
            gene_symbol, len(raw_interactions), MIN_ROWS_PER_PROTEIN,
        )
        return {
            "gene_symbol": gene_symbol,
            "string_id": string_id,
            "inserted": 0,
            "skipped": 0,
            "total_fetched": len(raw_interactions),
            "warning": f"Below minimum {MIN_ROWS_PER_PROTEIN} rows",
        }

    # Canonicalize every interaction into a flat dict
    canonicals = [
        _canonicalize_interaction(
            disease_id=disease_id,
            gene_symbol=gene_symbol,
            string_id=string_id,
            interaction=inter,
            variant_index=idx,
        )
        for idx, inter in enumerate(raw_interactions)
    ]

    # Enrich with batch-level aggregate metrics (Phase 2)
    canonicals = _enrich_batch_metrics(canonicals)

    # ── Phase 3: Compute network centrality metrics ─────────────
    # Collect all partner names to fetch the FULL network (not just
    # hub-spoke edges). This gives partner↔partner edges so that
    # clustering_coefficient is meaningful.
    partner_names = set()
    partner_names.add(gene_symbol)
    for inter in raw_interactions:
        partner_names.add(inter.get("preferredName_A", ""))
        partner_names.add(inter.get("preferredName_B", ""))
    partner_names.discard("")

    # Fetch the full mesh network among all partners
    try:
        network_edges = fetch_network(list(partner_names))
    except Exception as exc:
        logger.warning(
            "fetch_network failed for %s, falling back to hub-spoke: %s",
            gene_symbol, exc,
        )
        network_edges = raw_interactions

    graph = build_interaction_graph(network_edges)
    centrality = compute_centrality_metrics(graph, gene_symbol)

    for c in canonicals:
        c["Degree_Centrality"] = centrality["Degree_Centrality"]
        c["Betweenness_Centrality"] = centrality["Betweenness_Centrality"]
        c["Closeness_Centrality"] = centrality["Closeness_Centrality"]
        c["Clustering_Coefficient"] = centrality["Clustering_Coefficient"]

    # ── Phase 4: Persist with dual dedup (hash pre-check + constraint)
    inserted = 0
    skipped = 0

    for canonical in canonicals:
        content_hash = sha256_hash(canonical)

        # Explicit pre-check — avoids unnecessary DB round-trip
        if _hash_exists(db, content_hash):
            skipped += 1
            continue

        record = StringRecord(
            disease_id=disease_id,
            gene_symbol=gene_symbol,
            target_id=canonical["target_id"],
            source_record_id=canonical["source_record_id"],
            content_hash=content_hash,
            uniprot_id=uniprot_id,
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

    return {
        "gene_symbol": gene_symbol,
        "string_id": string_id,
        "inserted": inserted,
        "skipped": skipped,
        "total_fetched": len(raw_interactions),
    }


# ── Batch orchestrator ─────────────────────────────────────────────

def batch_ingest_string(
    db: Session,
    disease_id: str,
    gene_symbols: list[str],
    requested_by: str = "himanshu",
    interaction_limit: int = 50,
) -> dict[str, Any]:
    """
    End-to-end batch ingestion:
      1. Resolve all genes → STRING IDs (one API call)
      2. Fetch + canonicalize + persist per gene
      3. Return full summary

    Enforces the 80-protein hard cap.
    """
    if len(gene_symbols) > 80:
        raise ValueError("Max 80 gene symbols per batch (pipeline constraint).")

    # Step 1 — resolve identifiers
    resolved = map_identifiers_to_string_ids(gene_symbols)
    symbol_to_sid: dict[str, str] = {}
    for entry in resolved:
        query = entry.get("queryItem", "").upper()
        sid = entry.get("stringId", "")
        if query and sid:
            symbol_to_sid[query] = sid

    # Step 1b — map STRING IDs → UniProt accessions
    all_sids = list(symbol_to_sid.values())
    try:
        sid_to_uniprot = map_string_to_uniprot(all_sids) if all_sids else {}
        logger.info("UniProt mapping: %d/%d IDs mapped", len(sid_to_uniprot), len(all_sids))
    except Exception as exc:
        logger.warning("UniProt ID mapping failed, continuing without: %s", exc)
        sid_to_uniprot = {}

    # Step 2 — ingest per gene
    gene_results: list[dict[str, Any]] = []
    total_inserted = 0
    total_skipped = 0
    total_fetched = 0
    failed = 0

    for gene in gene_symbols:
        gene_upper = gene.strip().upper()
        sid = symbol_to_sid.get(gene_upper)

        if not sid:
            gene_results.append({
                "gene_symbol": gene_upper,
                "string_id": None,
                "inserted": 0,
                "skipped": 0,
                "total_fetched": 0,
                "status": "failed",
                "error": "Could not resolve STRING ID",
            })
            failed += 1
            continue

        try:
            result = ingest_string_gene(
                db=db,
                disease_id=disease_id,
                gene_symbol=gene_upper,
                string_id=sid,
                interaction_limit=interaction_limit,
                uniprot_id=sid_to_uniprot.get(sid),
            )
            result["status"] = "ok"
            gene_results.append(result)
            total_inserted += result["inserted"]
            total_skipped += result["skipped"]
            total_fetched += result["total_fetched"]
        except Exception as exc:
            gene_results.append({
                "gene_symbol": gene_upper,
                "string_id": sid,
                "inserted": 0,
                "skipped": 0,
                "total_fetched": 0,
                "status": "failed",
                "error": str(exc),
            })
            failed += 1

    return {
        "disease_id": disease_id,
        "requested_by": requested_by,
        "total_genes": len(gene_symbols),
        "summary": {
            "total_inserted": total_inserted,
            "total_skipped": total_skipped,
            "total_fetched": total_fetched,
            "failed_genes": failed,
        },
        "results": gene_results,
    }
