from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user, get_db_session
from backend.models import Transaction, User
from backend.schemas.transactions import TransactionCategoryUpdate, TransactionListResponse, TransactionRead

router = APIRouter()


def parse_optional_datetime(value: str | None) -> datetime | None:
    if value in {None, ""}:
        return None
    return datetime.fromisoformat(value)


@router.get("", response_model=TransactionListResponse)
def list_transactions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    platform: str | None = None,
    needs_review: bool | None = None,
    search: str | None = None,
    category_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    uploaded_file_ids: list[int] | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> TransactionListResponse:
    date_from_dt = parse_optional_datetime(date_from)
    date_to_dt = parse_optional_datetime(date_to)
    query = select(Transaction).where(Transaction.user_id == current_user.id)
    count_query = select(func.count()).select_from(Transaction).where(Transaction.user_id == current_user.id)
    if platform:
        query = query.where(Transaction.platform == platform)
        count_query = count_query.where(Transaction.platform == platform)
    if needs_review is not None:
        query = query.where(Transaction.needs_review == needs_review)
        count_query = count_query.where(Transaction.needs_review == needs_review)
    if search:
        pattern = f"%{search}%"
        query = query.where((Transaction.merchant.like(pattern)) | (Transaction.item.like(pattern)) | (Transaction.note.like(pattern)))
        count_query = count_query.where((Transaction.merchant.like(pattern)) | (Transaction.item.like(pattern)) | (Transaction.note.like(pattern)))
    if category_id is not None:
        query = query.where((Transaction.final_category_id == category_id) | (Transaction.auto_category_id == category_id))
        count_query = count_query.where((Transaction.final_category_id == category_id) | (Transaction.auto_category_id == category_id))
    if date_from_dt is not None:
        query = query.where(Transaction.occurred_at >= date_from_dt)
        count_query = count_query.where(Transaction.occurred_at >= date_from_dt)
    if date_to_dt is not None:
        query = query.where(Transaction.occurred_at <= date_to_dt)
        count_query = count_query.where(Transaction.occurred_at <= date_to_dt)
    if uploaded_file_ids:
        query = query.where(Transaction.uploaded_file_id.in_(uploaded_file_ids))
        count_query = count_query.where(Transaction.uploaded_file_id.in_(uploaded_file_ids))
    total = db.scalar(count_query) or 0
    items = db.scalars(
        query.order_by(Transaction.occurred_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return TransactionListResponse(items=[TransactionRead.model_validate(item) for item in items], total=total)


@router.patch("/{transaction_id}/category", response_model=TransactionRead)
def update_transaction_category(
    transaction_id: int,
    payload: TransactionCategoryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> TransactionRead:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None or transaction.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="transaction not found")
    transaction.final_category_id = payload.category_id
    if payload.mark_reviewed:
        transaction.needs_review = False
    db.commit()
    db.refresh(transaction)
    return TransactionRead.model_validate(transaction)
