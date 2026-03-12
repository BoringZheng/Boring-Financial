from __future__ import annotations

from backend.core.celery_app import celery_app
from backend.db.session import SessionLocal
from backend.models import Transaction
from backend.services.classifiers import classify_transaction


@celery_app.task(name="classification.reclassify")
def reclassify_transactions(user_id: int, transaction_ids: list[int], provider: str | None = None) -> dict:
    db = SessionLocal()
    try:
        processed = 0
        for transaction_id in transaction_ids:
            transaction = db.get(Transaction, transaction_id)
            if transaction is None or transaction.user_id != user_id:
                continue
            classify_transaction(db, transaction, user_id, provider_override=provider)
            processed += 1
        return {"processed": processed}
    finally:
        db.close()
