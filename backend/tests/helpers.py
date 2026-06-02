from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.models import Category, ImportBatch, Transaction, UploadedFile
from backend.utils.normalizers import build_dedupe_hash


def create_category(db: Session, name: str = "餐饮", user_id: int | None = None) -> Category:
    category = Category(name=name, user_id=user_id, is_system=user_id is None, is_active=True)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def create_import_batch_with_file(db: Session, user_id: int, filename: str = "wechat.csv") -> tuple[ImportBatch, UploadedFile]:
    batch = ImportBatch(user_id=user_id, status="done", source_count=1, total_count=1, processed_count=1)
    db.add(batch)
    db.commit()
    db.refresh(batch)

    uploaded_file = UploadedFile(
        batch_id=batch.id,
        filename=filename,
        stored_path=f"/tmp/{filename}",
        platform="WeChat",
        status="done",
    )
    db.add(uploaded_file)
    db.commit()
    db.refresh(uploaded_file)
    return batch, uploaded_file


def create_transaction(
    db: Session,
    user_id: int,
    batch_id: int,
    uploaded_file_id: int | None = None,
    *,
    occurred_at: datetime = datetime(2026, 3, 1, 10, 0, 0),
    platform: str = "WeChat",
    transaction_type: str = "支出",
    amount: Decimal = Decimal("12.34"),
    merchant: str = "测试商户",
    item: str = "午餐",
    note: str = "",
    category_id: int | None = None,
    needs_review: bool = True,
) -> Transaction:
    transaction = Transaction(
        user_id=user_id,
        batch_id=batch_id,
        uploaded_file_id=uploaded_file_id,
        platform=platform,
        occurred_at=occurred_at,
        type=transaction_type,
        amount=amount,
        merchant=merchant,
        item=item,
        method="零钱",
        status="支付成功",
        note=note,
        merchant_norm=merchant.lower(),
        item_norm=item.lower(),
        note_norm=note.lower(),
        dedupe_hash=build_dedupe_hash(platform, occurred_at, amount, merchant, item),
        auto_category_id=category_id,
        needs_review=needs_review,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction
