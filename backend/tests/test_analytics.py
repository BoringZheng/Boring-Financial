from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.base_class import Base
from backend.models import Category, ImportBatch, Transaction, UploadedFile, User
from backend.services.analytics import dashboard_summary


def test_dashboard_summary_supports_date_and_category_filters() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)

    db = Session(engine)
    user = User(username="dashboard", email="dashboard@example.com", hashed_password="hashed")
    db.add(user)
    db.commit()
    db.refresh(user)

    batch = ImportBatch(user_id=user.id, status="done", source_count=1, total_count=3, processed_count=3)
    db.add(batch)
    db.commit()
    db.refresh(batch)

    uploaded_file = UploadedFile(
        batch_id=batch.id,
        filename="march-wechat.xlsx",
        stored_path="march-wechat.xlsx",
        platform="WeChat",
        status="done",
    )
    other_uploaded_file = UploadedFile(
        batch_id=batch.id,
        filename="march-alipay.xlsx",
        stored_path="march-alipay.xlsx",
        platform="Alipay",
        status="done",
    )
    db.add_all([uploaded_file, other_uploaded_file])
    db.commit()
    db.refresh(uploaded_file)
    db.refresh(other_uploaded_file)

    food = Category(name="餐饮", is_system=True, is_active=True)
    transport = Category(name="交通", is_system=True, is_active=True)
    db.add_all([food, transport])
    db.commit()
    db.refresh(food)
    db.refresh(transport)

    db.add_all(
        [
            Transaction(
                user_id=user.id,
                batch_id=batch.id,
                uploaded_file_id=uploaded_file.id,
                platform="WeChat",
                occurred_at=datetime(2026, 3, 1, 9, 0, 0),
                type="支出",
                amount=Decimal("25.00"),
                merchant="早餐店",
                item="早餐",
                method="零钱",
                status="支付成功",
                note="",
                merchant_norm="早餐店",
                item_norm="早餐",
                note_norm="",
                dedupe_hash="hash-1",
                auto_category_id=food.id,
                needs_review=False,
            ),
            Transaction(
                user_id=user.id,
                batch_id=batch.id,
                uploaded_file_id=other_uploaded_file.id,
                platform="WeChat",
                occurred_at=datetime(2026, 3, 2, 10, 0, 0),
                type="支出",
                amount=Decimal("18.00"),
                merchant="地铁",
                item="通勤",
                method="银行卡",
                status="支付成功",
                note="",
                merchant_norm="地铁",
                item_norm="通勤",
                note_norm="",
                dedupe_hash="hash-2",
                final_category_id=transport.id,
                needs_review=False,
            ),
            Transaction(
                user_id=user.id,
                batch_id=batch.id,
                uploaded_file_id=other_uploaded_file.id,
                platform="WeChat",
                occurred_at=datetime(2026, 3, 2, 18, 0, 0),
                type="收入",
                amount=Decimal("100.00"),
                merchant="转账",
                item="报销",
                method="银行卡",
                status="到账成功",
                note="",
                merchant_norm="转账",
                item_norm="报销",
                note_norm="",
                dedupe_hash="hash-3",
                needs_review=False,
            ),
        ]
    )
    db.commit()

    filtered = dashboard_summary(
        db,
        user.id,
        date_from=datetime(2026, 3, 2, 0, 0, 0),
        date_to=datetime(2026, 3, 2, 23, 59, 59),
        category_id=transport.id,
        uploaded_file_ids=[other_uploaded_file.id],
    )

    assert filtered["expense_total"] == Decimal("18.00")
    assert filtered["income_total"] == Decimal("0")
    assert filtered["transaction_count"] == 1
    assert filtered["category_breakdown"][0]["category_name"] == "交通"
    assert filtered["top_merchants"][0]["merchant"] == "地铁"
