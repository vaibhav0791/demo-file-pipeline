from sqlalchemy import String, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class FetchRun(Base):
    __tablename__ = "fetch_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    requested_by: Mapped[str] = mapped_column(String(128), index=True)
    request_json: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), index=True, default="queued")  # queued/running/completed/failed
    started_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())