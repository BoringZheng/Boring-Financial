from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class TransactionRead(BaseModel):
    id: int
    platform: str
    occurred_at: datetime
    type: str
    amount: Decimal
    merchant: str | None
    item: str | None
    note: str | None
    auto_provider: str | None
    auto_reason: str | None
    auto_confidence: Decimal | None
    auto_category_id: int | None
    final_category_id: int | None
    needs_review: bool

    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    items: list[TransactionRead]
    total: int


class TransactionCategoryUpdate(BaseModel):
    category_id: int
    mark_reviewed: bool = True


class ReclassifyRequest(BaseModel):
    transaction_ids: list[int]
    provider: str | None = None
