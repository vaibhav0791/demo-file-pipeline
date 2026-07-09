from __future__ import annotations
from typing import Optional, Dict, Any
import json

from sqlalchemy.orm import Session
from app.models.master_target import MasterTarget


MANDATORY_FIELDS = [
    "disease",
    "uniprot_id",
    "gene_symbol",
    "protein_name",
    "organism",
    "amino_acid_sequence",
    "protein_length",
    "molecular_weight",
    "go_biological_process",
    "go_molecular_function",
    "go_cellular_component",
    "subcellular_location",
    "logfc",
    "adj_p_value",
    "average_expression",
    "tissue",
    "sample_size",
    "target_label",
]


def _missing_count(payload: Dict[str, Any]) -> int:
    c = 0
    for f in MANDATORY_FIELDS:
        v = payload.get(f)
        if v is None or (isinstance(v, str) and not v.strip()):
            c += 1
    return c


def _status_from_missing(missing: int) -> str:
    return "ready" if missing == 0 else "partial"


def upsert_master_target(
    db: Session,
    payload: Dict[str, Any],
    provenance: Optional[Dict[str, Any]] = None,
) -> MasterTarget:
    disease = payload["disease"]
    uniprot_id = payload["uniprot_id"]

    obj = (
        db.query(MasterTarget)
        .filter(MasterTarget.disease == disease, MasterTarget.uniprot_id == uniprot_id)
        .one_or_none()
    )

    missing = _missing_count(payload)
    status = _status_from_missing(missing)

    if obj is None:
        obj = MasterTarget(
            disease=disease,
            uniprot_id=uniprot_id,
        )
        db.add(obj)

    # assign fields
    for k, v in payload.items():
        if hasattr(obj, k):
            setattr(obj, k, v)

    obj.missing_fields_count = missing
    obj.row_status = status
    if provenance is not None:
        obj.source_provenance_json = json.dumps(provenance)

    db.flush()
    return obj