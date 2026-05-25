from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.db.base_class import Base
from backend.models import Transaction, User
from backend.services import retry_queue
from backend.services.classifiers import RETRY_FAILED_PROVIDER, RETRY_QUEUE_PROVIDER


def _transaction(user_id: int, dedupe_hash: str, provider: str, retry_count: int = 0) -> Transaction:
    return Transaction(
        user_id=user_id,
        batch_id=1,
        platform="WeChat",
        occurred_at=datetime(2026, 3, 8, 12, 0, 0),
        type="支出",
        amount=Decimal("18.00"),
        merchant="private merchant",
        item="private item",
        method="card",
        status="paid",
        note="private note",
        merchant_norm="private merchant",
        item_norm="private item",
        note_norm="private note",
        dedupe_hash=dedupe_hash,
        auto_provider=provider,
        auto_reason="external api timeout",
        api_retry_count=retry_count,
        api_retry_provider="openai_compatible_api",
        api_retry_last_error="secret provider error",
        needs_review=False,
        created_at=datetime(2026, 3, 8, 12, 0, 0),
        updated_at=datetime(2026, 3, 8, 12, retry_count, 0),
    )


def test_retry_queue_status_is_aggregate_and_user_filterable(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    db = Session(engine)
    user = User(username="admin", email="admin@example.com", hashed_password="hashed", is_admin=True)
    other = User(username="other", email="other@example.com", hashed_password="hashed")
    db.add_all([user, other])
    db.commit()
    db.refresh(user)
    db.refresh(other)
    user_id = user.id
    other_id = other.id
    db.add_all(
        [
            _transaction(user_id, "queued-1", RETRY_QUEUE_PROVIDER, retry_count=0),
            _transaction(user_id, "queued-2", RETRY_QUEUE_PROVIDER, retry_count=2),
            _transaction(user_id, "failed-1", RETRY_FAILED_PROVIDER, retry_count=10),
            _transaction(other_id, "other-queued", RETRY_QUEUE_PROVIDER, retry_count=1),
        ]
    )
    db.commit()
    db.close()

    monkeypatch.setattr(retry_queue, "SessionLocal", lambda: Session(engine))

    status = retry_queue.get_retry_queue_status(user_id=user_id)

    assert status["queued"] == 2
    assert status["failed"] == 1
    assert status["total"] == 3
    assert status["providers"] == [{"provider": "openai_compatible_api", "queued": 2, "failed": 1}]
    assert status["retry_counts"] == [{"retry_count": 0, "queued": 1}, {"retry_count": 2, "queued": 1}]
    assert "private merchant" not in repr(status)
    assert "secret provider error" not in repr(status)
