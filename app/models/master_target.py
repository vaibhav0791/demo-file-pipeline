from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, UniqueConstraint, func
)
from app.db.base import Base


class MasterTarget(Base):
    __tablename__ = "master_targets"
    __table_args__ = (
        UniqueConstraint("disease", "uniprot_id", name="uq_master_disease_uniprot"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # General
    disease = Column(String(128), nullable=False, index=True)
    uniprot_id = Column(String(32), nullable=False, index=True)
    gene_symbol = Column(String(64), nullable=False, index=True)
    protein_name = Column(Text, nullable=True)
    organism = Column(String(128), nullable=True)

    # UniProt
    amino_acid_sequence = Column(Text, nullable=True)
    protein_length = Column(Integer, nullable=True)
    molecular_weight = Column(Float, nullable=True)
    go_biological_process = Column(Text, nullable=True)
    go_molecular_function = Column(Text, nullable=True)
    go_cellular_component = Column(Text, nullable=True)
    subcellular_location = Column(Text, nullable=True)

    # GEO
    logfc = Column(Float, nullable=True)
    adj_p_value = Column(Float, nullable=True)
    average_expression = Column(Float, nullable=True)
    tissue = Column(String(128), nullable=True)
    sample_size = Column(Integer, nullable=True)

    # Label
    target_label = Column(Integer, nullable=True)  # 1 target, 0 non-target

    # Quality / audit
    row_status = Column(String(32), nullable=False, default="partial")  # ready|partial
    missing_fields_count = Column(Integer, nullable=False, default=0)
    source_provenance_json = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)