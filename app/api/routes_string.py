from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List

from app.api.deps import get_db
from app.connectors.string_connector import map_identifiers_to_string_ids
from app.services.ingest_string import batch_ingest_string
from app.services.pipeline_runner_string import run_string_pipeline

router = APIRouter(prefix="/string", tags=["string"])


# ── Schemas ─────────────────────────────────────────────────────────

class StringBatchRequest(BaseModel):
    disease_id: str = Field(..., examples=["Pain"])
    gene_symbols: List[str] = Field(
        ...,
        min_length=1,
        max_length=80,
        examples=[["TRPV1", "TRPA1", "SCN9A", "OPRM1", "OPRK1"]],
    )
    requested_by: str = Field(default="himanshu")


class StringPipelineRequest(BaseModel):
    disease_id: str = Field(..., examples=["Pain"])
    gene_symbols: List[str] = Field(
        ...,
        min_length=1,
        max_length=80,
        examples=[["TRPV1", "TRPA1", "SCN9A", "OPRM1", "OPRK1"]],
    )
    requested_by: str = Field(default="himanshu")
    interaction_limit: int = Field(default=50, ge=25, le=200)
    export_csv: bool = Field(default=True)
    output_dir: str = Field(default="output")


# ── Routes ──────────────────────────────────────────────────────────

@router.post("/resolve-ids")
def resolve_string_ids(
    gene_symbols: List[str] = Query(
        ..., description="Gene symbols to map, e.g. TRPV1,TRPA1"
    ),
):
    """Phase 1 — Map gene symbols → STRING IDs (quick test, no DB)."""
    if len(gene_symbols) > 80:
        raise HTTPException(
            status_code=400,
            detail="Max 80 gene symbols per request (pipeline constraint).",
        )
    return map_identifiers_to_string_ids(gene_symbols)


@router.post("/batch-ingest")
def batch_ingest_string_route(
    payload: StringBatchRequest,
    db: Session = Depends(get_db),
):
    """
    Phase 2-4 — Ingest pipeline:
      Resolve → Fetch → Canonicalize → Centrality → Persist (with dedup)
    """
    genes = [g.strip().upper() for g in payload.gene_symbols if g and g.strip()]
    genes = list(dict.fromkeys(genes))

    if not genes:
        raise HTTPException(status_code=400, detail="gene_symbols cannot be empty")
    if len(genes) > 80:
        raise HTTPException(
            status_code=400,
            detail="Max 80 gene symbols per request (pipeline constraint).",
        )

    return batch_ingest_string(
        db=db,
        disease_id=payload.disease_id,
        gene_symbols=genes,
        requested_by=payload.requested_by,
    )


@router.post("/run-pipeline")
def run_pipeline_string(
    payload: StringPipelineRequest,
    db: Session = Depends(get_db),
):
    """
    Phase 5 — Full pipeline:
      Ingest + Persist + CSV Export + Summary Report
    """
    genes = [g.strip().upper() for g in payload.gene_symbols if g and g.strip()]
    genes = list(dict.fromkeys(genes))

    if not genes:
        raise HTTPException(status_code=400, detail="gene_symbols cannot be empty")
    if len(genes) > 80:
        raise HTTPException(
            status_code=400,
            detail="Max 80 gene symbols per request (pipeline constraint).",
        )

    return run_string_pipeline(
        db=db,
        disease_id=payload.disease_id,
        gene_symbols=genes,
        requested_by=payload.requested_by,
        interaction_limit=payload.interaction_limit,
        export_csv=payload.export_csv,
        output_dir=payload.output_dir,
    )

