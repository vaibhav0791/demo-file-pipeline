from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.ingest_uniprot import ingest_uniprot_gene
from app.models.schemas import UniProtBatchRequest, UniProtBatchResponse, GeneIngestResult
from app.services.fetch_runs import create_fetch_run, complete_fetch_run

router = APIRouter(prefix="/uniprot", tags=["uniprot"])

@router.post("/ingest")
def ingest_uniprot(
    disease_id: str = Query(..., description="Disease identifier/name"),
    gene_symbol: str = Query(..., description="Gene symbol, e.g. TP53"),
    size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return ingest_uniprot_gene(db=db, disease_id=disease_id, gene_symbol=gene_symbol, size=size)

@router.post("/batch-ingest", response_model=UniProtBatchResponse)
def batch_ingest_uniprot(payload: UniProtBatchRequest, db: Session = Depends(get_db)):
    genes = [g.strip().upper() for g in payload.gene_symbols if g and g.strip()]
    genes = list(dict.fromkeys(genes))  # remove duplicates, keep order

    if not genes:
        raise HTTPException(status_code=400, detail="gene_symbols cannot be empty")
    if len(genes) > 100:
        raise HTTPException(status_code=400, detail="Max 100 gene symbols per request")

    run = create_fetch_run(
        db=db,
        requested_by=payload.requested_by,
        request_json=payload.model_dump(),
    )

    results: list[GeneIngestResult] = []
    total_inserted = 0
    total_skipped = 0
    total_fetched = 0
    failed = 0

    for gene in genes:
        try:
            r = ingest_uniprot_gene(db=db, disease_id=payload.disease_id, gene_symbol=gene, size=20)
            results.append(GeneIngestResult(gene_symbol=gene, **r, status="ok"))
            total_inserted += r["inserted"]
            total_skipped += r["skipped"]
            total_fetched += r["total_fetched"]
        except Exception:
            failed += 1
            results.append(
                GeneIngestResult(
                    gene_symbol=gene,
                    inserted=0,
                    skipped=0,
                    total_fetched=0,
                    status="failed",
                )
            )

    run_status = "completed" if failed == 0 else ("failed" if failed == len(genes) else "completed_with_errors")
    complete_fetch_run(db=db, run=run, status=run_status)

    return UniProtBatchResponse(
        run_id=run.id,
        disease_id=payload.disease_id,
        requested_by=payload.requested_by,
        total_genes=len(genes),
        summary={
            "total_inserted": total_inserted,
            "total_skipped": total_skipped,
            "total_fetched": total_fetched,
            "failed_genes": failed,
            "run_status": run_status,
        },
        results=results,
    )