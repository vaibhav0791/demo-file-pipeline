from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.models.fetch_run import FetchRun

def create_fetch_run(db: Session, requested_by: str, request_json: dict) -> FetchRun:
    run = FetchRun(
        requested_by=requested_by,
        request_json=request_json,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run

def complete_fetch_run(db: Session, run: FetchRun, status: str = "completed") -> FetchRun:
    run.status = status
    run.finished_at = datetime.now(timezone.utc)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run