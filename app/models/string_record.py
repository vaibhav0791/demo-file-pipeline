"""
Phase 4 — STRING-specific database model.

Extends the shared Record table with a STRING-dedicated table for
tighter constraint enforcement and easier querying of STRING-specific
columns without parsing canonical_json.
"""
from sqlalchemy import (
    String, Float, Integer, DateTime,
    UniqueConstraint, Index, func,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class StringRecord(Base):
    """
    Dedicated table for STRING DB interaction records.
    Provides typed columns for all STRING-owned Master Schema fields
    and stricter unique constraints to prevent data repetition.
    """
    __tablename__ = "string_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # ── Context keys ────────────────────────────────────────────
    disease_id: Mapped[str] = mapped_column(String(128), index=True)
    gene_symbol: Mapped[str] = mapped_column(String(64), index=True)
    target_id: Mapped[str] = mapped_column(String(128), index=True)

    # ── Dedup keys ──────────────────────────────────────────────
    source_record_id: Mapped[str] = mapped_column(String(256), index=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)

    # ── Mapped UniProt accession ────────────────────────────────
    uniprot_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)

    # ── STRING Master Schema columns ────────────────────────────
    string_id: Mapped[str] = mapped_column(String(128), index=True)
    partner_a: Mapped[str] = mapped_column(String(64))
    partner_b: Mapped[str] = mapped_column(String(64))
    combined_score: Mapped[float] = mapped_column(Float, default=0.0)

    interaction_count: Mapped[int] = mapped_column(Integer, default=0)
    average_interaction_score: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Phase 3 computed centrality metrics ──────────────────────
    degree_centrality: Mapped[float] = mapped_column(Float, default=0.0)
    betweenness_centrality: Mapped[float] = mapped_column(Float, default=0.0)
    closeness_centrality: Mapped[float] = mapped_column(Float, default=0.0)
    clustering_coefficient: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Sub-scores (evidence channels) ──────────────────────────
    neighborhood_score: Mapped[float] = mapped_column(Float, default=0.0)
    fusion_score: Mapped[float] = mapped_column(Float, default=0.0)
    cooccurrence_score: Mapped[float] = mapped_column(Float, default=0.0)
    coexpression_score: Mapped[float] = mapped_column(Float, default=0.0)
    experimental_score: Mapped[float] = mapped_column(Float, default=0.0)
    database_score: Mapped[float] = mapped_column(Float, default=0.0)
    textmining_score: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Timestamps ──────────────────────────────────────────────
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        # Primary dedup: same source_record_id + same content = skip
        UniqueConstraint(
            "source_record_id", "content_hash",
            name="uq_string_srcid_hash",
        ),
        # Secondary: no exact duplicate interaction per disease×gene×partner
        UniqueConstraint(
            "disease_id", "gene_symbol", "partner_b", "combined_score",
            name="uq_string_disease_gene_partner_score",
        ),
        # Fast lookup index
        Index(
            "ix_string_disease_gene",
            "disease_id", "gene_symbol",
        ),
    )
