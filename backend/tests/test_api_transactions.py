from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.core.security import create_access_token, get_password_hash
from backend.models import User
from tests.helpers import create_category, create_import_batch_with_file, create_transaction


def test_transactions_are_filtered_paginated_and_user_scoped(
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
        merchant="瑞幸咖啡",
        item="生椰拿铁",
        amount=Decimal("18.00"),
        category_id=category.id,
        needs_review=True,
    )
    create_transaction(
        db_session,
        user.id,
        batch.id,
        uploaded_file.id,
        occurred_at=datetime(2026, 3, 2, 8, 0, 0),
        merchant="地铁",
        item="通勤",
        amount=Decimal("6.00"),
        needs_review=False,
    )

    other_user = User(username="bob", email="bob@example.com", hashed_password=get_password_hash("secret-123"))
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)
    other_batch, other_file = create_import_batch_with_file(db_session, other_user.id, "other.csv")
    create_transaction(db_session, other_user.id, other_batch.id, other_file.id, merchant="不应出现", item="晚餐")

    response = client.get(
        "/api/transactions",
        params={
            "page": 1,
            "page_size": 10,
            "search": "咖啡",
            "needs_review": True,
            "category_id": category.id,
            "uploaded_file_ids": [uploaded_file.id],
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["merchant"] == "瑞幸咖啡"
    assert "不应出现" not in {item["merchant"] for item in payload["items"]}


def test_update_transaction_category_marks_reviewed(
    client: TestClient,
    db_session: Session,
    user: User,
    auth_headers: dict[str, str],
) -> None:
    category = create_category(db_session, "交通")
    batch, uploaded_file = create_import_batch_with_file(db_session, user.id)
    transaction = create_transaction(db_session, user.id, batch.id, uploaded_file.id, merchant="地铁", item="通勤")

    response = client.patch(
        f"/api/transactions/{transaction.id}/category",
        json={"category_id": category.id, "mark_reviewed": True},
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["final_category_id"] == category.id
    assert payload["needs_review"] is False


def test_update_transaction_category_rejects_other_users_transaction(
    client: TestClient,
    db_session: Session,
    auth_headers: dict[str, str],
) -> None:
    other_user = User(username="bob", email="bob@example.com", hashed_password=get_password_hash("secret-123"))
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)
    batch, uploaded_file = create_import_batch_with_file(db_session, other_user.id)
    transaction = create_transaction(db_session, other_user.id, batch.id, uploaded_file.id)

    response = client.patch(
        f"/api/transactions/{transaction.id}/category",
        json={"category_id": 1, "mark_reviewed": True},
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_transactions_require_auth(client: TestClient) -> None:
    response = client.get("/api/transactions")

    assert response.status_code == 401
