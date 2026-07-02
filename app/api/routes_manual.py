from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Dict, Any

from app.api.deps import get_db
from app.models.manual_record import ManualRecord
from app.utils.hash_utils import sha256_hash

router = APIRouter(prefix="/manual", tags=["manual"])

class ManualUploadRequest(BaseModel):
    uploaded_by: str
    records: List[Dict[str, Any]]

@router.post("/upload")
def upload_manual(payload: ManualUploadRequest, db: Session = Depends(get_db)):
    inserted, skipped = 0, 0

    for r in payload.records:
        h = sha256_hash(r)
        row = ManualRecord(uploaded_by=payload.uploaded_by, canonical_json=r, content_hash=h)
        try:
            db.add(row)
            db.commit()
            inserted += 1
        except IntegrityError:
            db.rollback()
            skipped += 1

    return {"inserted": inserted, "skipped": skipped, "total": len(payload.records)}