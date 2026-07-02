from sqlalchemy import String, DateTime, func, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Delivery(Base):
    __tablename__ = "deliveries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    consumer_id: Mapped[str] = mapped_column(String(128), index=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("fetch_runs.id"), nullable=True)
    delivered_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("consumer_id", "content_hash", name="uq_delivery_consumer_hash"),
    )