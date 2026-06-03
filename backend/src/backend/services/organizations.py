from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.entities import Organization, OrganizationMember, User


def create_organization(db: Session, name: str, user_id: int) -> Organization:
    org = Organization(name=name, created_by_user_id=user_id)
    db.add(org)
    db.flush()
    member = OrganizationMember(organization_id=org.id, user_id=user_id, role="owner")
    db.add(member)
    db.commit()
    db.refresh(org)
    return org


def get_organizations_for_user(db: Session, user_id: int) -> list[dict]:
    rows = db.execute(
        select(Organization, OrganizationMember.role)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user_id)
        .order_by(Organization.created_at.asc())
    ).all()
    return [
        {
            "id": org.id, "name": org.name,
            "created_by_user_id": org.created_by_user_id,
            "plan": org.plan, "subscription_status": org.subscription_status,
            "created_at": org.created_at, "updated_at": org.updated_at,
            "role": role,
        }
        for org, role in rows
    ]


def get_organization_members(db: Session, organization_id: int) -> list[dict]:
    rows = db.execute(
        select(OrganizationMember, User.username)
        .join(User, User.id == OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == organization_id)
        .order_by(OrganizationMember.created_at.asc())
    ).all()
    return [
        {
            "id": m.id, "organization_id": m.organization_id,
            "user_id": m.user_id, "role": m.role,
            "username": username,
            "created_at": m.created_at, "updated_at": m.updated_at,
        }
        for m, username in rows
    ]


def get_member_user_ids(db: Session, organization_id: int) -> list[int]:
    return list(db.scalars(
        select(OrganizationMember.user_id).where(
            OrganizationMember.organization_id == organization_id
        )
    ).all())


def verify_org_membership(db: Session, organization_id: int, user_id: int) -> OrganizationMember:
    member = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
        )
    )
    if member is None:
        raise ValueError("not a member of this organization")
    return member


def verify_org_owner_or_admin(db: Session, organization_id: int, user_id: int) -> OrganizationMember:
    member = verify_org_membership(db, organization_id, user_id)
    if member.role not in ("owner", "admin"):
        raise ValueError("organization owner or admin required")
    return member


def add_member(db: Session, organization_id: int, username: str) -> OrganizationMember:
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise ValueError("user not found")
    existing = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user.id,
        )
    )
    if existing is not None:
        raise ValueError("user is already a member of this organization")
    member = OrganizationMember(organization_id=organization_id, user_id=user.id, role="member")
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def update_member_role(db: Session, organization_id: int, user_id: int, new_role: str) -> OrganizationMember:
    if new_role not in ("admin", "member"):
        raise ValueError("role must be admin or member")
    member = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
        )
    )
    if member is None:
        raise ValueError("member not found")
    if member.role == "owner":
        raise ValueError("cannot change the owner's role")
    member.role = new_role
    db.commit()
    db.refresh(member)
    return member


def remove_member(db: Session, organization_id: int, user_id: int) -> None:
    member = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
        )
    )
    if member is None:
        raise ValueError("member not found")
    if member.role == "owner":
        raise ValueError("cannot remove the owner; transfer ownership first")
    db.delete(member)
    db.commit()
