from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user, get_db_session, require_admin
from backend.models import Transaction, User
from backend.schemas.transactions import ReclassifyRequest
from backend.services.classifiers import classify_transaction
from backend.services.retry_queue import get_retry_queue_status, requeue_all_external_api_failures

router = APIRouter()


class RetryAllRequest(BaseModel):
    user_id: int | None = None


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
            classify_transaction(db, transaction, current_user.id, provider_override=payload.provider, force_refresh=True)
            processed += 1
        except Exception as exc:
            failed += 1
            failures.append({"transaction_id": transaction.id, "error": str(exc)})
    return {"processed": processed, "failed": failed, "failures": failures}


@router.post("/retry-all")
def retry_all(
    payload: RetryAllRequest,
    _: User = Depends(require_admin),
) -> dict:
    queued = requeue_all_external_api_failures(user_id=payload.user_id)
    return {"queued": queued}


@router.get("/retry-status")
def retry_status(
    user_id: int | None = None,
    _: User = Depends(require_admin),
) -> dict:
    return get_retry_queue_status(user_id=user_id)
