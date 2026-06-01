from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.api import routes_reports
from backend.core.security import get_password_hash
from backend.models import GeneratedReport, ReportJob, User
from tests.helpers import create_category, create_import_batch_with_file, create_transaction


def test_imports_list_detail_and_delete_are_user_scoped(
    client: TestClient,
    db_session: Session,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    batch, uploaded_file = create_import_batch_with_file(db_session, user.id)
    create_transaction(db_session, user.id, batch.id, uploaded_file.id)

    other_user = User(username="bob", email="bob@example.com", hashed_password=get_password_hash("secret-123"))
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)
    other_batch, _ = create_import_batch_with_file(db_session, other_user.id, "other.csv")

    list_response = client.get("/api/imports", headers=auth_headers)
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [batch.id]

    files_response = client.get("/api/imports/files", headers=auth_headers)
    assert files_response.status_code == 200
    assert files_response.json()[0]["filename"] == "wechat.csv"

    detail_response = client.get(f"/api/imports/{batch.id}", headers=auth_headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["progress_percent"] == 100.0

    forbidden_detail = client.get(f"/api/imports/{other_batch.id}", headers=auth_headers)
    assert forbidden_detail.status_code == 404

    delete_response = client.delete(f"/api/imports/{batch.id}", headers=auth_headers)
    assert delete_response.status_code == 204
    assert client.get(f"/api/imports/{batch.id}", headers=auth_headers).status_code == 404


def test_dashboard_summary_route_returns_aggregates(
    client: TestClient,
    db_session: Session,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    category = create_category(db_session, "餐饮")
    batch, uploaded_file = create_import_batch_with_file(db_session, user.id)
    create_transaction(
        db_session,
        user.id,
        batch.id,
        uploaded_file.id,
        occurred_at=datetime(2026, 3, 1, 9, 0, 0),
        merchant="早餐店",
        item="早餐",
        amount=Decimal("20.00"),
        category_id=category.id,
        needs_review=False,
    )
    create_transaction(
        db_session,
        user.id,
        batch.id,
        uploaded_file.id,
        occurred_at=datetime(2026, 3, 1, 18, 0, 0),
        transaction_type="收入",
        merchant="报销",
        item="餐补",
        amount=Decimal("50.00"),
        needs_review=True,
    )

    response = client.get(
        "/api/dashboard/summary",
        params={"date_from": "2026-03-01T00:00:00", "date_to": "2026-03-01T23:59:59"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["expense_total"] == "20.00"
    assert payload["income_total"] == "50.00"
    assert payload["transaction_count"] == 2
    assert payload["pending_review_count"] == 1


def test_create_report_route_uses_builder_and_returns_report(
    monkeypatch,
    client: TestClient,
    db_session: Session,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    class FakeReportBuilder:
        def build(
            self,
            db: Session,
            user_id: int,
            report_job: ReportJob,
            title: str | None = None,
            uploaded_file_ids: list[int] | None = None,
        ) -> GeneratedReport:
            report = GeneratedReport(
                user_id=user_id,
                job_id=report_job.id,
                title=title or "账单分析报告",
                file_path="/tmp/report.pdf",
            )
            db.add(report)
            db.commit()
            db.refresh(report)
            return report

    monkeypatch.setattr(routes_reports, "report_builder", FakeReportBuilder())

    response = client.post(
        "/api/reports",
        json={"title": "测试报表", "date_from": "", "date_to": "", "uploaded_file_ids": []},
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "测试报表"
    assert payload["user_id"] == user.id


def test_download_report_rejects_other_users_report(
    client: TestClient,
    db_session: Session,
    auth_headers: dict[str, str],
) -> None:
    other_user = User(username="bob", email="bob@example.com", hashed_password=get_password_hash("secret-123"))
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)
    job = ReportJob(user_id=other_user.id, status="done")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    report = GeneratedReport(user_id=other_user.id, job_id=job.id, title="other", file_path="/tmp/other.pdf")
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    response = client.get(f"/api/reports/{report.id}/download", headers=auth_headers)

    assert response.status_code == 404
