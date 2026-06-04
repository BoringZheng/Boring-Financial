from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user, get_db_session, require_admin
from backend.models import Transaction, User
from backend.schemas.transactions import ReclassifyRequest
from backend.services.classifiers import classify_transaction
from backend.services.retry_queue import get_retry_queue_status, requeue_all_external_api_failures, requeue_with_progress

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


# --- Family organization endpoints ---

@router.post("/organizations/{organization_id}/retry-all")
def org_retry_all(
    organization_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    from backend.services.organizations import get_member_user_ids, verify_org_owner_or_admin
    try:
        verify_org_owner_or_admin(db, organization_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    member_ids = get_member_user_ids(db, organization_id)
    queued = 0
    for uid in member_ids:
        queued += requeue_all_external_api_failures(user_id=uid)
    return {"queued": queued}


@router.post("/organizations/{organization_id}/reclassify")
def org_reclassify(
    organization_id: int,
    payload: ReclassifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    from backend.services.organizations import get_member_user_ids, verify_org_owner_or_admin
    try:
        verify_org_owner_or_admin(db, organization_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    member_ids = get_member_user_ids(db, organization_id)

    transactions = db.scalars(
        select(Transaction).where(
            Transaction.user_id.in_(member_ids),
            Transaction.id.in_(payload.transaction_ids),
        )
    ).all()

    processed = 0
    failed = 0
    failures: list[dict] = []
    for transaction in transactions:
        try:
            classify_transaction(db, transaction, transaction.user_id,
                                 provider_override=payload.provider, force_refresh=True)
            processed += 1
        except Exception as exc:
            failed += 1
            failures.append({"transaction_id": transaction.id, "error": str(exc)})
    return {"processed": processed, "failed": failed, "failures": failures}

@router.post("/retry-all-stream")
def retry_all_stream(
    payload: RetryAllRequest,
    _: User = Depends(require_admin),
) -> StreamingResponse:
    def event_generator():
        last = 0
        for current, total in requeue_with_progress(user_id=payload.user_id):
            yield f"data: {{\"current\": {current}, \"total\": {total}}}\n\n"
            last = current
        yield f"data: {{\"done\": true, \"queued\": {last}}}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
