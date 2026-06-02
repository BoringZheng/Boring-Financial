from __future__ import annotations

from fastapi.testclient import TestClient


def test_register_login_and_me_flow(client: TestClient) -> None:
    register_response = client.post(
        "/api/auth/register",
        json={"username": "new-user", "password": "secret-123", "email": "new@example.com"},
    )

    assert register_response.status_code == 200
    register_payload = register_response.json()
    assert register_payload["token_type"] == "bearer"
    assert register_payload["user"]["username"] == "new-user"
    assert register_payload["access_token"]
    assert register_payload["refresh_token"]

    duplicate_response = client.post(
        "/api/auth/register",
        json={"username": "new-user", "password": "secret-123", "email": "another@example.com"},
    )
    assert duplicate_response.status_code == 400

    login_response = client.post("/api/auth/login", json={"username": "new-user", "password": "secret-123"})
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me_response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "new-user"


def test_login_rejects_bad_credentials(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"username": "missing", "password": "bad-password"})

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid credentials"


def test_me_requires_access_token(client: TestClient) -> None:
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "missing bearer token"
