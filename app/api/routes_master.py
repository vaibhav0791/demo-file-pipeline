from __future__ import annotations
from typing import List, Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import get_db
from app.models.record import Record
from app.services.ingest_uniprot import ingest_uniprot_gene
from app.services.geo_service import get_geo_metrics_for_gene
from app.services.master_merge import upsert_master_target
from app.services.target_label_service import get_target_label

router = APIRouter(prefix="/master", tags=["master"])


class MasterRunRequest(BaseModel):
    disease_id: str
    gene_symbols: List[str] = Field(..., min_length=1, max_length=200)
    requested_by: str = "vaibhav"
    per_gene_size: int = 20
    include_payload: bool = True


def _as_str(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        return s if s else None
    return str(v)


def _organism_to_str(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, str):
        return v.strip() or None
    if isinstance(v, dict):
        # UniProt style object
        return (
            v.get("scientificName")
            or v.get("commonName")
            or _as_str(v.get("taxonId"))
            or None
        )
    return _as_str(v)


def _extract_go_text(p: Dict[str, Any], key: str) -> str | None:
    """
    Accepts either direct string fields or list/dict forms.
    """
    v = p.get(key)
    if v is None:
        return None
    if isinstance(v, str):
        return v.strip() or None
    if isinstance(v, list):
        out = []
        for x in v:
            if isinstance(x, str) and x.strip():
                out.append(x.strip())
            elif isinstance(x, dict):
                t = x.get("term") or x.get("name") or x.get("value")
                if t:
                    out.append(str(t).strip())
        return "; ".join([x for x in out if x]) or None
    if isinstance(v, dict):
        t = v.get("term") or v.get("name") or v.get("value")
        return str(t).strip() if t else None
    return _as_str(v)


@router.post("/run_uniprot_geo")
def run_master_uniprot_geo(payload: MasterRunRequest, db: Session = Depends(get_db)):
    genes = [g.strip().upper() for g in payload.gene_symbols if g and g.strip()]
    genes = list(dict.fromkeys(genes))

    # 1) Ingest/refresh UniProt records
    for gene in genes:
        try:
            ingest_uniprot_gene(
                db=db,
                disease_id=payload.disease_id,
                gene_symbol=gene,
                size=payload.per_gene_size,
            )
        except Exception:
            db.rollback()
            continue

    # 2) Pull canonical rows directly
    stmt = (
        select(Record)
        .where(Record.disease_id == payload.disease_id)
        .order_by(Record.id.desc())
        .limit(5000)
    )
    rows = db.execute(stmt).scalars().all()

    records = []
    for x in rows:
        p = x.canonical_json or {}
        g = (p.get("gene_symbol_input") or "").upper().strip()
        if g in genes:
            records.append(
                {
                    "target_id": x.target_id,
                    "content_hash": x.content_hash,
                    "payload": p,
                }
            )

    # 3) Build master rows
    ready_rows = 0
    partial_rows = 0
    processed = 0
    errors = 0

    for r in records:
        try:
            p = r.get("payload") or {}
            gene_symbol = (p.get("gene_symbol_input") or "").upper().strip() or None

            # robust field extraction from canonical JSON
            uniprot_id = _as_str(p.get("target_id") or r.get("target_id"))
            protein_name = _as_str(
                p.get("protein_name")
                or p.get("recommended_name")
                or p.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value")
                if isinstance(p.get("proteinDescription"), dict)
                else None
            )
            organism = _organism_to_str(p.get("organism"))
            seq = _as_str(p.get("sequence"))
            length = p.get("length")
            mw = p.get("molecular_weight")

            # if sequence is dict in some payload shapes
            if isinstance(p.get("sequence"), dict):
                seq_obj = p["sequence"]
                seq = _as_str(seq_obj.get("value"))
                if length is None:
                    length = seq_obj.get("length")
                if mw is None:
                    mw = seq_obj.get("molWeight")

            # numeric safety
            try:
                length = int(length) if length is not None else None
            except Exception:
                length = None
            try:
                mw = float(mw) if mw is not None else None
            except Exception:
                mw = None

            uni = {
                "disease": payload.disease_id,
                "uniprot_id": uniprot_id,
                "gene_symbol": gene_symbol,
                "protein_name": protein_name,
                "organism": organism,
                "amino_acid_sequence": seq,
                "protein_length": length,
                "molecular_weight": mw,
                "go_biological_process": _extract_go_text(p, "go_biological_process"),
                "go_molecular_function": _extract_go_text(p, "go_molecular_function"),
                "go_cellular_component": _extract_go_text(p, "go_cellular_component"),
                "subcellular_location": _extract_go_text(p, "subcellular_location"),
            }

            geo = get_geo_metrics_for_gene(payload.disease_id, gene_symbol) or {}
            tlabel = get_target_label(gene_symbol)

            merged = {
                **uni,
                "logfc": geo.get("logfc"),
                "adj_p_value": geo.get("adj_p_value"),
                "average_expression": geo.get("average_expression"),
                "tissue": geo.get("tissue"),
                "sample_size": geo.get("sample_size"),
                "target_label": tlabel,
            }

            row = upsert_master_target(
                db=db,
                payload=merged,
                provenance={
                    "uniprot_source": "records.canonical_json",
                    "geo_source": geo.get("source") if geo else None,
                    "target_label_source": "curated_local_seed",
                },
            )

            processed += 1
            if row.row_status == "ready":
                ready_rows += 1
            else:
                partial_rows += 1

        except Exception:
            db.rollback()
            errors += 1
            continue

    db.commit()

    return {
        "disease_id": payload.disease_id,
        "genes_requested": genes,
        "processed_rows": processed,
        "ready_rows": ready_rows,
        "partial_rows": partial_rows,
        "errors": errors,
        "note": "UniProt normalized to scalar DB fields; GEO remains strict real-only.",
    }