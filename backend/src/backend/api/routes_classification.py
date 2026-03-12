from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user, get_db_session
from backend.models import Transaction, User
from backend.schemas.transactions import ReclassifyRequest
from backend.services.classifiers import classify_transaction

router = APIRouter()


@router.post("/reclassify")
def reclassify(
    payload: ReclassifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    transactions = db.scalars(
        select(Transaction).where(Transaction.user_id == current_user.id, Transaction.id.in_(payload.transaction_ids))
    ).all()
    processed = 0
    failed = 0
    failures: list[dict] = []
    for transaction in transactions:
        try:
            classify_transaction(db, transaction, current_user.id, provider_override=payload.provider)
            processed += 1
        except Exception as exc:
            failed += 1
            failures.append({"transaction_id": transaction.id, "error": str(exc)})
    return {"processed": processed, "failed": failed, "failures": failures}
