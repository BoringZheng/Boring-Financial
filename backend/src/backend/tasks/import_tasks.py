from __future__ import annotations

from backend.core.celery_app import celery_app
from backend.db.session import SessionLocal
from backend.services.imports import process_import_batch


@celery_app.task(name="import.process_batch")
def process_batch(batch_id: int) -> dict:
    db = SessionLocal()
    try:
        batch = process_import_batch(db, batch_id)
        return {"batch_id": batch.id, "status": batch.status}
    finally:
        db.close()
