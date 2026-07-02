from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.record import Record
from app.models.manual_record import ManualRecord
from app.models.delivery import Delivery


def _already_delivered_hashes(db: Session, consumer_id: str) -> set[str]:
    rows = db.execute(
        select(Delivery.content_hash).where(Delivery.consumer_id == consumer_id)
    ).all()
    return {r[0] for r in rows}


def get_records_for_delivery(
    db: Session,
    consumer_id: str,
    disease_id: str | None = None,
    only_new: bool = True,
    limit: int = 1000,
    gene_symbols: list[str] | None = None,
    include_payload: bool = False,
):
    delivered = _already_delivered_hashes(db, consumer_id) if only_new else set()

    q = select(Record).order_by(Record.id.desc()).limit(limit * 5)

    if disease_id:
        q = q.where(Record.disease_id == disease_id)

    # apply only if column exists in your model; otherwise leave gene_symbols=None from caller
    if gene_symbols and hasattr(Record, "gene_symbol"):
        q = q.where(Record.gene_symbol.in_(gene_symbols))

    records = db.execute(q).scalars().all()

    out = []
    for r in records:
        if only_new and r.content_hash in delivered:
            continue

        item = {
            "source_type": "automated",
            "source": r.source,
            "disease_id": r.disease_id,
            "target_id": r.target_id,
            "content_hash": r.content_hash,
        }
        if include_payload:
            item["payload"] = r.canonical_json

        out.append(item)
        if len(out) >= limit:
            break

    if not gene_symbols and len(out) < limit:
        m_q = select(ManualRecord).order_by(ManualRecord.id.desc()).limit(limit * 3)
        manual_rows = db.execute(m_q).scalars().all()

        for m in manual_rows:
            if only_new and m.content_hash in delivered:
                continue

            item = {
                "source_type": "manual",
                "source": "manual_upload",
                "disease_id": disease_id,
                "target_id": None,
                "content_hash": m.content_hash,
            }
            if include_payload:
                item["payload"] = m.canonical_json

            out.append(item)
            if len(out) >= limit:
                break

    return out


def mark_delivered(db: Session, consumer_id: str, content_hashes: list[str], run_id: int | None = None):
    inserted = 0
    skipped = 0
    for h in content_hashes:
        row = Delivery(consumer_id=consumer_id, content_hash=h, run_id=run_id)
        try:
            db.add(row)
            db.commit()
            inserted += 1
        except Exception:
            db.rollback()
            skipped += 1
    return {"inserted": inserted, "skipped": skipped}