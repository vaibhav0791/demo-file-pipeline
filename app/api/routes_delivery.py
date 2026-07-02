from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from app.api.deps import get_db
from app.services.delivery_service import get_records_for_delivery, mark_delivered

router = APIRouter(prefix="/delivery", tags=["delivery"])


class MarkDeliveredRequest(BaseModel):
    consumer_id: str
    content_hashes: List[str]
    run_id: int | None = None


@router.get("/export")
def export_records(
    consumer_id: str = Query(...),
    disease_id: str | None = Query(None),
    only_new: bool = Query(True),
    limit: int = Query(200, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    items = get_records_for_delivery(
        db=db,
        consumer_id=consumer_id,
        disease_id=disease_id,
        only_new=only_new,
        limit=limit,
    )
    return {
        "consumer_id": consumer_id,
        "count": len(items),
        "only_new": only_new,
        "items": items,
    }


@router.post("/mark-delivered")
def mark_records_delivered(payload: MarkDeliveredRequest, db: Session = Depends(get_db)):
    result = mark_delivered(
        db=db,
        consumer_id=payload.consumer_id,
        content_hashes=payload.content_hashes,
        run_id=payload.run_id,
    )
    return {"consumer_id": payload.consumer_id, **result}