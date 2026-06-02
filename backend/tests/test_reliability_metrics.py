from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from backend.models import ImportBatch, ReportJob, User
from backend.services.reliability_metrics import reliability_metrics
from tests.helpers import create_category, create_import_batch_with_file, create_transaction


def test_reliability_metrics_return_zeroes_when_empty(db_session: Session) -> None:
    metrics = reliability_metrics(db_session)

    assert metrics["total_import_batches"] == 0
    assert metrics["import_success_rate"] == 0.0
    assert metrics["report_success_rate"] == 0.0
    assert metrics["pending_review_rate"] == 0.0
    assert metrics["classification_coverage_rate"] == 0.0


def test_reliability_metrics_calculate_import_report_and_transaction_rates(db_session: Session, user: User) -> None:
    food = create_category(db_session, "餐饮")
    done_batch, uploaded_file = create_import_batch_with_file(db_session, user.id)
    partial_batch = ImportBatch(user_id=user.id, status="partial_failed", source_count=1, total_count=2, processed_count=1)
    failed_batch = ImportBatch(user_id=user.id, status="failed", source_count=1, total_count=0, processed_count=0)
    db_session.add_all([partial_batch, failed_batch])
    db_session.commit()

    db_session.add_all(
        [
            ReportJob(user_id=user.id, status="done"),
            ReportJob(user_id=user.id, status="failed"),
            ReportJob(user_id=user.id, status="processing"),
        ]
    )
    db_session.commit()

    create_transaction(
        db_session,
        user.id,
        done_batch.id,
        uploaded_file.id,
        merchant="早餐店",
        item="早餐",
        amount=Decimal("10.00"),
        category_id=food.id,
        needs_review=False,
    )
    create_transaction(
        db_session,
        user.id,
        done_batch.id,
        uploaded_file.id,
        merchant="地铁",
        item="通勤",
        amount=Decimal("6.00"),
        needs_review=True,
    )

    metrics = reliability_metrics(db_session, user.id)

    assert metrics["total_import_batches"] == 3
    assert metrics["import_success_count"] == 1
    assert metrics["import_partial_failed_count"] == 1
    assert metrics["import_failed_count"] == 1
    assert metrics["import_success_rate"] == 33.33
    assert metrics["import_partial_failure_rate"] == 33.33
    assert metrics["import_failure_rate"] == 33.33
    assert metrics["total_report_jobs"] == 3
    assert metrics["report_done_count"] == 1
    assert metrics["report_success_rate"] == 33.33
    assert metrics["total_transactions"] == 2
    assert metrics["pending_review_count"] == 1
    assert metrics["pending_review_rate"] == 50.0
    assert metrics["classified_transaction_count"] == 1
    assert metrics["classification_coverage_rate"] == 50.0


def test_reliability_metrics_can_scope_to_one_user(db_session: Session, user: User) -> None:
    other = User(username="other", email="other@example.com", hashed_password="hashed")
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)

    create_import_batch_with_file(db_session, user.id)
    db_session.add(ImportBatch(user_id=other.id, status="failed", source_count=1, total_count=0, processed_count=0))
    db_session.commit()

    metrics = reliability_metrics(db_session, user.id)

    assert metrics["total_import_batches"] == 1
    assert metrics["import_success_rate"] == 100.0
    assert metrics["import_failure_rate"] == 0.0
