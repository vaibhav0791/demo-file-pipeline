from sqlalchemy import String, DateTime, JSON, UniqueConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Record(Base):
    __tablename__ = "records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    disease_id: Mapped[str] = mapped_column(String(128), index=True)
    target_id: Mapped[str] = mapped_column(String(64), index=True)  # UniProt accession
    source: Mapped[str] = mapped_column(String(32), index=True)     # uniprot/rcsb/geo/string
    source_record_id: Mapped[str] = mapped_column(String(256), index=True)
    canonical_json: Mapped[dict] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)  # sha256 hex
    first_seen_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    gene_symbol: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    __table_args__ = (
        UniqueConstraint("source", "source_record_id", "content_hash", name="uq_record_source_sourceid_hash"),
        Index("ix_records_disease_target_source", "disease_id", "target_id", "source"),
    )