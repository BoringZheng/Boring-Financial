from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.base_class import Base
from backend.models import ImportBatch, Transaction, UploadedFile, User
from backend.services import imports as imports_service
from backend.services.parsers import ParsedTransaction


def test_process_import_batch_updates_progress(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)

    db = Session(engine)
    user = User(username="tester", email="tester@example.com", hashed_password="hashed")
    db.add(user)
    db.commit()
    db.refresh(user)

    batch = ImportBatch(user_id=user.id, status="queued", source_count=1, total_count=0, processed_count=0)
    db.add(batch)
    db.commit()
    db.refresh(batch)

    uploaded = UploadedFile(batch_id=batch.id, filename="statement.csv", stored_path="ignored.csv", status="queued")
    db.add(uploaded)
    db.commit()

    parsed_transactions = [
        ParsedTransaction(
            platform="WeChat",
            occurred_at=datetime(2026, 3, 1, 10, 0, 0),
            type="支出",
            amount=Decimal("12.34"),
            merchant="测试商户A",
            item="午餐",
            method="零钱",
            status="支付成功",
            note="",
        ),
        ParsedTransaction(
            platform="WeChat",
            occurred_at=datetime(2026, 3, 1, 11, 0, 0),
            type="支出",
            amount=Decimal("45.67"),
            merchant="测试商户B",
            item="咖啡",
            method="银行卡",
            status="支付成功",
            note="",
        ),
    ]

    monkeypatch.setattr(imports_service.parser_registry, "parse_file", lambda _: parsed_transactions)
    monkeypatch.setattr(imports_service, "classify_transaction_in_session", lambda *args, **kwargs: None)

    result = imports_service.process_import_batch(db, batch.id)

    assert result.status == "done"
    assert result.total_count == 2
    assert result.processed_count == 2
    assert result.progress_percent == 100.0


def test_process_import_batch_marks_partial_failed_when_classification_fails(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)

    db = Session(engine)
    user = User(username="tester", email="tester@example.com", hashed_password="hashed")
    db.add(user)
    db.commit()
    db.refresh(user)

    batch = ImportBatch(user_id=user.id, status="queued", source_count=1, total_count=0, processed_count=0)
    db.add(batch)
    db.commit()
    db.refresh(batch)

    uploaded = UploadedFile(batch_id=batch.id, filename="statement.csv", stored_path="ignored.csv", status="queued")
    db.add(uploaded)
    db.commit()

    parsed_transactions = [
        ParsedTransaction(
            platform="WeChat",
            occurred_at=datetime(2026, 3, 1, 10, 0, 0),
            type="支出",
            amount=Decimal("12.34"),
            merchant="测试商户A",
            item="午餐",
            method="零钱",
            status="支付成功",
            note="",
        )
    ]

    monkeypatch.setattr(imports_service.parser_registry, "parse_file", lambda _: parsed_transactions)
    monkeypatch.setattr(imports_service, "classify_transaction_in_session", lambda *args, **kwargs: "model unavailable")

    result = imports_service.process_import_batch(db, batch.id)

    db.refresh(uploaded)
    assert result.status == "partial_failed"
    assert result.total_count == 1
    assert result.processed_count == 1
    assert uploaded.status == "partial_failed"
    assert "model unavailable" in (result.error_message or "")


def test_process_import_batch_skips_duplicate_transactions(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)

    db = Session(engine)
    user = User(username="tester", email="tester@example.com", hashed_password="hashed")
    db.add(user)
    db.commit()
    db.refresh(user)

    batch = ImportBatch(user_id=user.id, status="queued", source_count=1, total_count=0, processed_count=0)
    db.add(batch)
    db.commit()
    db.refresh(batch)

    uploaded = UploadedFile(batch_id=batch.id, filename="statement.csv", stored_path="ignored.csv", status="queued")
    db.add(uploaded)
    db.commit()

    parsed = ParsedTransaction(
        platform="WeChat",
        occurred_at=datetime(2026, 3, 1, 10, 0, 0),
        type="支出",
        amount=Decimal("12.34"),
        merchant="测试商户A",
        item="午餐",
        method="零钱",
        status="支付成功",
        note="",
    )

    monkeypatch.setattr(imports_service.parser_registry, "parse_file", lambda _: [parsed, parsed])
    monkeypatch.setattr(imports_service, "classify_transaction_in_session", lambda *args, **kwargs: None)

    result = imports_service.process_import_batch(db, batch.id)

    transactions = db.query(Transaction).all()
    assert result.status == "done"
    assert result.total_count == 2
    assert result.processed_count == 2
    assert len(transactions) == 1
