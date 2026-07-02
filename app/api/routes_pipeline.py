from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.ingest_uniprot import ingest_uniprot_gene
from app.services.fetch_runs import create_fetch_run, complete_fetch_run
from app.services.delivery_service import get_records_for_delivery, mark_delivered

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


class PipelineRunRequest(BaseModel):
    disease_id: str
    gene_symbols: list[str] = Field(..., min_length=1, max_length=100)
    requested_by: str = "vaibhav"
    consumer_id: str = "qretix_ranker"
    only_new: bool = True
    per_gene_size: int = 20
    export_limit: int = 500
    include_payload: bool = False


@router.post("/run")
def run_pipeline(payload: PipelineRunRequest, db: Session = Depends(get_db)):
    try:
        genes = [g.strip().upper() for g in payload.gene_symbols if g and g.strip()]
        genes = list(dict.fromkeys(genes))

        run = create_fetch_run(
            db=db,
            requested_by=payload.requested_by,
            request_json=payload.model_dump(),
        )

        ingest_results = []
        total_inserted = 0
        total_skipped = 0
        total_fetched = 0
        failed = 0

        for gene in genes:
            try:
                r = ingest_uniprot_gene(
                    db=db,
                    disease_id=payload.disease_id,
                    gene_symbol=gene,
                    size=payload.per_gene_size,
                )
                ingest_results.append({"gene_symbol": gene, **r, "status": "ok"})
                total_inserted += r.get("inserted", 0)
                total_skipped += r.get("skipped", 0)
                total_fetched += r.get("total_fetched", 0)
            except Exception as e:
                failed += 1
                ingest_results.append({
                    "gene_symbol": gene,
                    "inserted": 0,
                    "skipped": 0,
                    "total_fetched": 0,
                    "status": f"failed: {str(e)}",
                })

        export_items = get_records_for_delivery(
            db=db,
            consumer_id=payload.consumer_id,
            disease_id=payload.disease_id,
            only_new=payload.only_new,
            limit=payload.export_limit,
            gene_symbols=None,  # safe mode
            include_payload=payload.include_payload,
        )

        hashes = [x["content_hash"] for x in export_items if "content_hash" in x]

        delivery_result = mark_delivered(
            db=db,
            consumer_id=payload.consumer_id,
            content_hashes=hashes,
            run_id=run.id,
        )

        run_status = "completed" if failed == 0 else ("failed" if failed == len(genes) else "completed_with_errors")
        complete_fetch_run(db=db, run=run, status=run_status)

        return {
            "run_id": run.id,
            "run_status": run_status,
            "ingest_summary": {
                "total_genes": len(genes),
                "total_inserted": total_inserted,
                "total_skipped": total_skipped,
                "total_fetched": total_fetched,
                "failed_genes": failed,
            },
            "delivery_summary": {
                "consumer_id": payload.consumer_id,
                "exported_count": len(export_items),
                "marked_delivered": delivery_result.get("inserted", 0),
                "mark_skipped": delivery_result.get("skipped", 0),
                "only_new": payload.only_new,
                "include_payload": payload.include_payload,
            },
            "ingest_results": ingest_results,
            "export_preview": export_items[:5],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"pipeline_run_failed: {str(e)}")