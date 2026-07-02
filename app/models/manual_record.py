from sqlalchemy import String, DateTime, JSON, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class ManualRecord(Base):
    __tablename__ = "manual_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    uploaded_by: Mapped[str] = mapped_column(String(128), index=True)
    canonical_json: Mapped[dict] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    uploaded_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_manual_content_hash"),
    )