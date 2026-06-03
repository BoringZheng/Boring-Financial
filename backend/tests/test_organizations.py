from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.security import create_access_token, get_password_hash
from backend.models.entities import Organization, OrganizationMember, User
from backend.services.organizations import create_organization, get_member_user_ids
from tests.helpers import create_import_batch_with_file, create_transaction


def _make_user(db: Session, username: str, is_admin: bool = False) -> User:
    user = User(username=username, email=f"{username}@test.com",
                hashed_password=get_password_hash("test-123"), is_admin=is_admin)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_headers_for(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


class TestOrganizationCreation:
    def test_create_org_makes_owner(self, db_session: Session):
        owner = _make_user(db_session, "creator")
        org = create_organization(db_session, "测试家庭", owner.id)
        assert org.name == "测试家庭"
        member = db_session.scalars(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org.id,
                OrganizationMember.user_id == owner.id,
            )
        ).first()
        assert member is not None
        assert member.role == "owner"

    def test_org_appears_in_user_list(self, db_session: Session, client: TestClient):
        owner = _make_user(db_session, "org_lister")
        create_organization(db_session, "我的家庭", owner.id)
        resp = client.get("/api/organizations", headers=_auth_headers_for(owner))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "我的家庭"
        assert data[0]["role"] == "owner"


class TestOrganizationMembership:
    def test_non_member_cannot_access_family_dashboard(self, db_session: Session, client: TestClient):
        owner = _make_user(db_session, "owner_x")
        outsider = _make_user(db_session, "outsider_x")
        org = create_organization(db_session, "私有家庭", owner.id)
        resp = client.get(
            f"/api/dashboard/summary?organization_id={org.id}",
            headers=_auth_headers_for(outsider),
        )
        assert resp.status_code == 403

    def test_member_can_view_family_dashboard(self, db_session: Session, client: TestClient):
        owner = _make_user(db_session, "owner_y")
        member = _make_user(db_session, "member_y")
        org = create_organization(db_session, "共享家庭", owner.id)
        from backend.services.organizations import add_member
        add_member(db_session, org.id, "member_y")
        resp = client.get(
            f"/api/dashboard/summary?organization_id={org.id}",
            headers=_auth_headers_for(member),
        )
        assert resp.status_code == 200

    def test_member_cannot_add_members(self, db_session: Session, client: TestClient):
        owner = _make_user(db_session, "owner_z")
        member = _make_user(db_session, "member_z")
        _make_user(db_session, "newbie")
        org = create_organization(db_session, "家庭Z", owner.id)
        from backend.services.organizations import add_member
        add_member(db_session, org.id, "member_z")
        resp = client.post(
            f"/api/organizations/{org.id}/members",
            json={"username": "newbie"},
            headers=_auth_headers_for(member),
        )
        assert resp.status_code == 403

    def test_member_cannot_retry(self, db_session: Session, client: TestClient):
        owner = _make_user(db_session, "owner_r")
        member = _make_user(db_session, "member_r")
        org = create_organization(db_session, "家庭R", owner.id)
        from backend.services.organizations import add_member
        add_member(db_session, org.id, "member_r")
        resp = client.post(
            f"/api/classification/organizations/{org.id}/retry-all",
            json={},
            headers=_auth_headers_for(member),
        )
        assert resp.status_code == 403

    def test_admin_can_manage_members(self, db_session: Session, client: TestClient):
        owner = _make_user(db_session, "owner_a")
        new_user = _make_user(db_session, "joiner")
        org = create_organization(db_session, "家庭A", owner.id)
        # Add member
        resp = client.post(
            f"/api/organizations/{org.id}/members",
            json={"username": "joiner"},
            headers=_auth_headers_for(owner),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["role"] == "member"
        # Promote to admin
        resp = client.patch(
            f"/api/organizations/{org.id}/members/{new_user.id}",
            json={"role": "admin"},
            headers=_auth_headers_for(owner),
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_cannot_remove_last_owner(self, db_session: Session, client: TestClient):
        owner = _make_user(db_session, "solo_owner")
        org = create_organization(db_session, "单人家庭", owner.id)
        resp = client.delete(
            f"/api/organizations/{org.id}/members/{owner.id}",
            headers=_auth_headers_for(owner),
        )
        assert resp.status_code == 400
        assert "owner" in resp.json()["detail"].lower()


class TestFamilyAggregation:
    def test_family_dashboard_aggregates_members(self, db_session: Session, client: TestClient):
        owner = _make_user(db_session, "fam_own")
        member = _make_user(db_session, "fam_mem")
        org = create_organization(db_session, "聚合家庭", owner.id)
        from backend.services.organizations import add_member
        add_member(db_session, org.id, "fam_mem")

        batch1, _ = create_import_batch_with_file(db_session, owner.id, "w1.csv")
        batch2, _ = create_import_batch_with_file(db_session, member.id, "w2.csv")
        create_transaction(db_session, owner.id, batch1.id, occurred_at=datetime(2026, 6, 1, 12, 0),
                           platform="WeChat", transaction_type="支出", amount=Decimal("100.00"))
        create_transaction(db_session, member.id, batch2.id, occurred_at=datetime(2026, 6, 1, 13, 0),
                           platform="Alipay", transaction_type="支出", amount=Decimal("200.00"))

        resp = client.get(
            f"/api/dashboard/summary?organization_id={org.id}",
            headers=_auth_headers_for(owner),
        )
        assert resp.status_code == 200
        assert resp.json()["transaction_count"] == 2

    def test_family_personality_aggregates_members(self, db_session: Session, client: TestClient):
        owner = _make_user(db_session, "prof_own")
        member = _make_user(db_session, "prof_mem")
        org = create_organization(db_session, "画像家庭", owner.id)
        from backend.services.organizations import add_member
        add_member(db_session, org.id, "prof_mem")

        batch1, _ = create_import_batch_with_file(db_session, owner.id, "a.csv")
        batch2, _ = create_import_batch_with_file(db_session, member.id, "b.csv")
        create_transaction(db_session, owner.id, batch1.id, occurred_at=datetime(2026, 6, 1, 12, 0),
                           platform="WeChat", transaction_type="支出", amount=Decimal("50.00"))
        create_transaction(db_session, member.id, batch2.id, occurred_at=datetime(2026, 6, 1, 13, 0),
                           platform="Alipay", transaction_type="支出", amount=Decimal("80.00"))

        resp = client.get(
            f"/api/personality/profile?organization_id={org.id}",
            headers=_auth_headers_for(owner),
        )
        assert resp.status_code == 200
        assert resp.json()["has_data"] is True


class TestPersonalModeUnaffected:
    def test_user_without_org_still_works(self, client: TestClient, auth_headers: dict):
        resp = client.get("/api/dashboard/summary", headers=auth_headers)
        assert resp.status_code == 200

    def test_personal_dashboard_no_org_id(self, client: TestClient, auth_headers: dict):
        resp = client.get("/api/dashboard/summary", headers=auth_headers)
        assert resp.status_code == 200
        assert "expense_total" in resp.json()


class TestAdminSeparation:
    def test_system_admin_not_confused_with_org_admin(self, db_session: Session, client: TestClient):
        sys_admin = _make_user(db_session, "sysadmin", is_admin=True)
        org_owner = _make_user(db_session, "orgowner")
        org = create_organization(db_session, "测试组织", org_owner.id)

        # sys_admin is NOT a member of the org, should get 403 on family dashboard
        resp = client.get(
            f"/api/dashboard/summary?organization_id={org.id}",
            headers=_auth_headers_for(sys_admin),
        )
        assert resp.status_code == 403

        # Personal dashboard still works for sys_admin without org_id
        resp = client.get(
            "/api/dashboard/summary",
            headers=_auth_headers_for(sys_admin),
        )
        assert resp.status_code == 200
        assert "expense_total" in resp.json()
