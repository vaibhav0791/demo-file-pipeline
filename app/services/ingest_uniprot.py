from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.record import Record
from app.utils.hash_utils import sha256_hash
from app.connectors.uniprot import fetch_uniprot_by_gene

def _canonicalize_uniprot_result(disease_id: str, gene_symbol: str, result: dict[str, Any]) -> dict[str, Any]:
    primary_accession = result.get("primaryAccession")
    entry_type = result.get("entryType")
    protein_desc = result.get("proteinDescription", {})
    organism = result.get("organism", {})
    genes = result.get("genes", [])

    return {
        "disease_id": disease_id,
        "gene_symbol_input": gene_symbol,
        "target_id": primary_accession,
        "source": "uniprot",
        "source_record_id": primary_accession,
        "entry_type": entry_type,
        "protein_description": protein_desc,
        "organism": organism,
        "genes": genes,
        "raw": result,
    }

def ingest_uniprot_gene(db: Session, disease_id: str, gene_symbol: str, size: int = 20) -> dict[str, int]:
    results = fetch_uniprot_by_gene(gene_symbol=gene_symbol, size=size)

    inserted = 0
    skipped = 0

    for r in results:
        canonical = _canonicalize_uniprot_result(disease_id, gene_symbol, r)
        content_hash = sha256_hash(canonical)

        record = Record(
            disease_id=disease_id,
            gene_symbol=gene_symbol,
            target_id=canonical.get("target_id") or gene_symbol,
            source="uniprot",
            source_record_id=canonical.get("source_record_id") or gene_symbol,
            canonical_json=canonical,
            content_hash=content_hash,
        )

        try:
            db.add(record)
            db.commit()
            inserted += 1
        except IntegrityError:
            db.rollback()
            skipped += 1

    return {"inserted": inserted, "skipped": skipped, "total_fetched": len(results)}