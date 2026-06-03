from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user, get_db_session
from backend.models.entities import Organization as OrganizationModel, User
from backend.schemas.organizations import (
    AddMemberRequest,
    OrganizationCreate,
    OrganizationMemberRead,
    OrganizationRead,
    OrganizationUpdate,
    OrganizationWithRole,
    UpdateMemberRoleRequest,
)
from backend.services.organizations import (
    add_member,
    create_organization,
    get_organization_members,
    get_organizations_for_user,
    remove_member,
    update_member_role,
    verify_org_membership,
    verify_org_owner_or_admin,
)

router = APIRouter()


@router.get("", response_model=list[OrganizationWithRole])
def list_organizations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[OrganizationWithRole]:
    return [OrganizationWithRole(**org) for org in get_organizations_for_user(db, current_user.id)]


@router.post("", response_model=OrganizationWithRole, status_code=status.HTTP_201_CREATED)
def create_org(
    payload: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> OrganizationWithRole:
    org = create_organization(db, payload.name, current_user.id)
    return OrganizationWithRole(
        id=org.id, name=org.name, created_by_user_id=org.created_by_user_id,
        plan=org.plan, subscription_status=org.subscription_status,
        created_at=org.created_at, updated_at=org.updated_at, role="owner",
    )


@router.patch("/{organization_id}", response_model=OrganizationRead)
def update_org(
    organization_id: int,
    payload: OrganizationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> OrganizationRead:
    verify_org_owner_or_admin(db, organization_id, current_user.id)
    org = db.get(OrganizationModel, organization_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    if payload.name is not None:
        org.name = payload.name
    if payload.plan is not None:
        org.plan = payload.plan
    if payload.subscription_status is not None:
        org.subscription_status = payload.subscription_status
    db.commit()
    db.refresh(org)
    return OrganizationRead.model_validate(org)


@router.get("/{organization_id}/members", response_model=list[OrganizationMemberRead])
def list_members(
    organization_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[OrganizationMemberRead]:
    verify_org_membership(db, organization_id, current_user.id)
    return [OrganizationMemberRead(**m) for m in get_organization_members(db, organization_id)]


@router.post("/{organization_id}/members", response_model=OrganizationMemberRead, status_code=status.HTTP_201_CREATED)
def add_org_member(
    organization_id: int,
    payload: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> OrganizationMemberRead:
    verify_org_owner_or_admin(db, organization_id, current_user.id)
    try:
        member = add_member(db, organization_id, payload.username)
        user = db.get(User, member.user_id)
        return OrganizationMemberRead(
            id=member.id, organization_id=member.organization_id,
            user_id=member.user_id, role=member.role,
            username=user.username if user else "",
            created_at=member.created_at, updated_at=member.updated_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/{organization_id}/members/{user_id}", response_model=OrganizationMemberRead)
def update_member(
    organization_id: int,
    user_id: int,
    payload: UpdateMemberRoleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> OrganizationMemberRead:
    verify_org_owner_or_admin(db, organization_id, current_user.id)
    try:
        member = update_member_role(db, organization_id, user_id, payload.role)
        user = db.get(User, member.user_id)
        return OrganizationMemberRead(
            id=member.id, organization_id=member.organization_id,
            user_id=member.user_id, role=member.role,
            username=user.username if user else "",
            created_at=member.created_at, updated_at=member.updated_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{organization_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_org_member(
    organization_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> None:
    verify_org_owner_or_admin(db, organization_id, current_user.id)
    try:
        remove_member(db, organization_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
