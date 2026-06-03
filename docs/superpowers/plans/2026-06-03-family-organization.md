# Family Organization (家庭组织) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add family organization support — users create/join family groups, aggregate member bills for family Dashboard/Reports/Personality, org admins manage members and trigger retry/reclassify on member transactions.

**Architecture:** Two new tables (Organization, OrganizationMember) with role-based access. Family aggregation extends existing APIs with optional `organization_id` query param — no tenant-level data migration. Existing personal flows remain untouched (方案A).

**Tech Stack:** FastAPI + SQLAlchemy 2.x + Pydantic + Vue 3 + TypeScript + Element Plus + Pinia

---

## File Structure

```
BACKEND — new files:
  backend/src/backend/schemas/organizations.py   — Pydantic schemas
  backend/src/backend/api/routes_organizations.py — org CRUD + family retry/reclassify
  backend/src/backend/services/organizations.py   — business logic

BACKEND — modified files:
  backend/src/backend/models/entities.py          — +Organization, +OrganizationMember
  backend/src/backend/api/router.py               — +1 router registration
  backend/src/backend/api/routes_dashboard.py      — +optional organization_id
  backend/src/backend/api/routes_reports.py        — +optional organization_id
  backend/src/backend/api/routes_personality.py    — +optional organization_id
  backend/src/backend/api/routes_classification.py — +org-scoped retry + reclassify
  backend/src/backend/services/analytics.py        — accept user_ids list instead of single user_id
  backend/src/backend/services/personality.py      — accept user_ids list instead of single user_id
  backend/src/backend/services/reports.py          — accept user_ids list instead of single user_id

FRONTEND — new files:
  frontend/src/pages/OrganizationPage.vue          — family org page

FRONTEND — modified files:
  frontend/src/types/models.ts                     — +Organization, +OrganizationMember types
  frontend/src/api/client.ts                       — +org API functions
  frontend/src/router/index.ts                     — +/organization route
  frontend/src/layouts/AppLayout.vue               — +conditional nav item

TESTS — new files:
  backend/tests/test_organizations.py              — comprehensive org tests
```

---

## Production Deployment Impact

### Zero-Downtime Deployment

| Concern | Impact | Mitigation |
|---|---|---|
| New tables | `organizations` + `organization_members` created by `Base.metadata.create_all()` on startup | Additive only; no existing table altered |
| Existing APIs | All endpoints unchanged when `organization_id` is not passed | Backward compatible; optional params default to `None` |
| Performance | Family queries use `WHERE user_id IN (...)` | `transactions.user_id` already indexed; negligible overhead for <50-member families |
| New dependencies | None | No new PyPI/npm packages |
| Docker Compose | No changes required | Tables auto-created at startup by `create_all()` |

### Existing User Data — Zero Impact

- Personal transactions unchanged. `user_id` remains sole owner
- Existing users continue using personal features exactly as before
- `users.is_admin` untouched — remains system/ops admin, NOT repurposed for org admin
- No backfill, no data migration needed

---

### Task 1: Add Organization & OrganizationMember Models

**Files:**
- Modify: `backend/src/backend/models/entities.py` (append at end)

- [ ] **Step 1: Add the two models**

Append after the `GeneratedReport` class:

```python
class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    plan: Mapped[str | None] = mapped_column(String(64), default="free", nullable=True)
    subscription_status: Mapped[str | None] = mapped_column(String(32), default="active", nullable=True)

    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_user_id])


class OrganizationMember(TimestampMixin, Base):
    __tablename__ = "organization_members"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_org_member"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(16), default="member")

    organization: Mapped["Organization"] = relationship()
    user: Mapped["User"] = relationship()
```

- [ ] **Step 2: Verify models import**

```bash
cd backend && uv run python -c "from backend.models.entities import Organization, OrganizationMember; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/backend/models/entities.py
git commit -m "feat: add Organization and OrganizationMember models"
```

---

### Task 2: Add Organization Pydantic Schemas

**Files:**
- Create: `backend/src/backend/schemas/organizations.py`

- [ ] **Step 1: Write schemas**

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    plan: str | None = None
    subscription_status: str | None = None


class OrganizationRead(BaseModel):
    id: int
    name: str
    created_by_user_id: int
    plan: str | None
    subscription_status: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrganizationWithRole(OrganizationRead):
    role: str


class OrganizationMemberRead(BaseModel):
    id: int
    organization_id: int
    user_id: int
    role: str
    username: str = ""
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AddMemberRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)


class UpdateMemberRoleRequest(BaseModel):
    role: str = Field(pattern="^(admin|member)$")
```

- [ ] **Step 2: Verify import**

```bash
cd backend && uv run python -c "from backend.schemas.organizations import OrganizationCreate, OrganizationRead; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/backend/schemas/organizations.py
git commit -m "feat: add organization Pydantic schemas"
```

---

### Task 3: Add Organization Service Layer

**Files:**
- Create: `backend/src/backend/services/organizations.py`

- [ ] **Step 1: Write the service**

```python
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
```

- [ ] **Step 2: Verify import**

```bash
cd backend && uv run python -c "from backend.services.organizations import create_organization, get_member_user_ids; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/backend/services/organizations.py
git commit -m "feat: add organization service layer"
```

---

### Task 4: Add Organization API Routes

**Files:**
- Create: `backend/src/backend/api/routes_organizations.py`
- Modify: `backend/src/backend/api/router.py`

- [ ] **Step 1: Write routes_organizations.py**

```python
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
```

- [ ] **Step 2: Register router in router.py**

In `backend/src/backend/api/router.py`, add after the existing imports:

```python
from backend.api.routes_organizations import router as organizations_router
```

And add after the existing `include_router` lines:

```python
api_router.include_router(organizations_router, prefix="/organizations", tags=["organizations"])
```

- [ ] **Step 3: Verify routes import**

```bash
cd backend && uv run python -c "from backend.api.router import api_router; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/backend/api/routes_organizations.py backend/src/backend/api/router.py
git commit -m "feat: add organization CRUD API routes"
```

---

### Task 5: Refactor analytics.py to Accept User ID List

**Files:**
- Modify: `backend/src/backend/services/analytics.py`

- [ ] **Step 1: Change `dashboard_summary` signature**

Change the function signature from `user_id: int` to `user_ids: list[int]`.

In `dashboard_summary()`, change line 21:
```python
# Old:
query = select(Transaction).where(Transaction.user_id == user_id)
# New:
query = select(Transaction).where(Transaction.user_id.in_(user_ids))
```

Change lines 80-82:
```python
# Old:
jobs = db.scalars(
    select(ImportBatch).where(ImportBatch.user_id == user_id).order_by(ImportBatch.created_at.desc()).limit(5)
).all()
# New:
jobs = db.scalars(
    select(ImportBatch).where(ImportBatch.user_id.in_(user_ids)).order_by(ImportBatch.created_at.desc()).limit(5)
).all()
```

- [ ] **Step 2: Verify tests still pass**

```bash
cd backend && uv run pytest tests/test_analytics.py -v
```

Expect existing tests to fail with a TypeError about `user_id` vs `user_ids`. Update any direct callers of `dashboard_summary()` in tests to pass `user_ids=[user_id]` instead of `user_id=user_id`.

- [ ] **Step 3: Commit**

```bash
git add backend/src/backend/services/analytics.py backend/tests/
git commit -m "refactor: dashboard_summary accepts user_ids list for family aggregation"
```

---

### Task 6: Extend Dashboard API for Family Aggregation

**Files:**
- Modify: `backend/src/backend/api/routes_dashboard.py`

- [ ] **Step 1: Add optional `organization_id` parameter**

Replace the `summary` function in `routes_dashboard.py`:

```python
@router.get("/summary", response_model=DashboardSummary)
def summary(
    date_from: str | None = None,
    date_to: str | None = None,
    category_id: int | None = None,
    uploaded_file_ids: list[int] | None = Query(default=None),
    organization_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> DashboardSummary:
    if organization_id is not None:
        from backend.services.organizations import get_member_user_ids, verify_org_membership
        try:
            verify_org_membership(db, organization_id, current_user.id)
        except ValueError:
            raise HTTPException(status_code=403, detail="not a member of this organization")
        user_ids = get_member_user_ids(db, organization_id)
    else:
        user_ids = [current_user.id]

    return DashboardSummary(
        **dashboard_summary(
            db,
            user_ids,
            date_from=parse_optional_datetime(date_from),
            date_to=parse_optional_datetime(date_to),
            category_id=category_id,
            uploaded_file_ids=uploaded_file_ids,
        )
    )
```

Add `HTTPException` to the imports:
```python
from fastapi import APIRouter, Depends, HTTPException, Query
```

- [ ] **Step 2: Verify tests pass**

```bash
cd backend && uv run pytest tests/test_api_imports_dashboard_reports.py -v -k "dashboard"
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/backend/api/routes_dashboard.py
git commit -m "feat: dashboard API accepts optional organization_id for family aggregation"
```

---

### Task 7: Extend Personality for Family Aggregation

**Files:**
- Modify: `backend/src/backend/services/personality.py`
- Modify: `backend/src/backend/api/routes_personality.py`

- [ ] **Step 1: Refactor personality service functions**

In `compute_personality_profile`, change:
```python
def compute_personality_profile(db: Session, user_ids: list[int]) -> dict:
    transactions = db.scalars(
        select(Transaction).where(Transaction.user_id.in_(user_ids))
    ).all()
    # ... rest of function unchanged
```

In `compute_financial_health`, change:
```python
def compute_financial_health(db: Session, user_ids: list[int]) -> dict:
    transactions = db.scalars(
        select(Transaction).where(Transaction.user_id.in_(user_ids))
    ).all()
    # ... rest of function unchanged
```

- [ ] **Step 2: Update routes_personality.py**

Replace the `get_profile` function:

```python
@router.get("/profile", response_model=PersonalityResponse)
def get_profile(
    organization_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> PersonalityResponse:
    if organization_id is not None:
        from backend.services.organizations import get_member_user_ids, verify_org_membership
        try:
            verify_org_membership(db, organization_id, current_user.id)
        except ValueError:
            raise HTTPException(status_code=403, detail="not a member of this organization")
        user_ids = get_member_user_ids(db, organization_id)
    else:
        user_ids = [current_user.id]

    profile_data = compute_personality_profile(db, user_ids)
    health_data = compute_financial_health(db, user_ids)
    has_data = db.scalar(
        select(Transaction.id).where(Transaction.user_id.in_(user_ids)).limit(1)
    ) is not None

    return PersonalityResponse(
        personality=PersonalityProfile(**profile_data),
        financial_health=health_data,
        has_data=has_data,
    )
```

- [ ] **Step 3: Verify tests pass**

```bash
cd backend && uv run pytest tests/test_personality.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/backend/services/personality.py backend/src/backend/api/routes_personality.py
git commit -m "feat: personality profile accepts user_ids list for family aggregation"
```

---

### Task 8: Extend Reports for Family Aggregation

**Files:**
- Modify: `backend/src/backend/services/reports.py`
- Modify: `backend/src/backend/api/routes_reports.py`

- [ ] **Step 1: Refactor ReportBuilder methods**

In `_build_context`, change signature:
```python
def _build_context(
    self,
    db: Session,
    user_ids: list[int],
    report_job: ReportJob,
    uploaded_file_ids: list[int] | None,
) -> dict:
    query = select(Transaction).where(Transaction.user_id.in_(user_ids))
```

And fix the `selected_files` subquery (line 182-184):
```python
selected_files = (
    db.scalars(
        select(UploadedFile).where(
            UploadedFile.batch_id.in_(
                select(Transaction.batch_id).where(Transaction.user_id.in_(user_ids))
            ),
            UploadedFile.id.in_(uploaded_file_ids),
        )
    ).all()
    if uploaded_file_ids
    else []
)
```

In `build`, change signature:
```python
def build(
    self,
    db: Session,
    user_ids: list[int],
    report_job: ReportJob,
    title: str | None = None,
    uploaded_file_ids: list[int] | None = None,
) -> GeneratedReport:
    context = self._build_context(db, user_ids, report_job, uploaded_file_ids)

    file_name = f"report-{user_ids[0]}-{report_job.id}.pdf"
    # ...
    report = GeneratedReport(user_id=user_ids[0], job_id=report_job.id, title=title or "财务报告", file_path=str(file_path))
```

- [ ] **Step 2: Update routes_reports.py**

Replace the `create_report` function:

```python
@router.post("", response_model=ReportRead)
def create_report(
    payload: ReportCreateRequest,
    organization_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ReportRead:
    if organization_id is not None:
        from backend.services.organizations import get_member_user_ids, verify_org_membership
        try:
            verify_org_membership(db, organization_id, current_user.id)
        except ValueError:
            raise HTTPException(status_code=403, detail="not a member of this organization")
        user_ids = get_member_user_ids(db, organization_id)
    else:
        user_ids = [current_user.id]

    job = ReportJob(user_id=current_user.id, status="processing",
                    date_from=payload.date_from, date_to=payload.date_to)
    db.add(job)
    db.commit()
    db.refresh(job)
    report = report_builder.build(db, user_ids, job, payload.title,
                                  uploaded_file_ids=payload.uploaded_file_ids)
    job.status = "done"
    db.commit()
    return ReportRead.model_validate(report)
```

- [ ] **Step 3: Verify tests pass**

```bash
cd backend && uv run pytest tests/test_reports.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/backend/services/reports.py backend/src/backend/api/routes_reports.py
git commit -m "feat: reports accept user_ids list for family aggregation"
```

---

### Task 9: Add Family Retry and Reclassify Endpoints

**Files:**
- Modify: `backend/src/backend/api/routes_classification.py`

- [ ] **Step 1: Add org-scoped endpoints**

Add `Body` to the existing FastAPI import:
```python
from fastapi import APIRouter, Body, Depends
```

Append after the existing endpoints (before the final line if any):

```python
@router.post("/organizations/{organization_id}/retry-all")
def org_retry_all(
    organization_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    from backend.services.organizations import get_member_user_ids, verify_org_owner_or_admin
    try:
        verify_org_owner_or_admin(db, organization_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    member_ids = get_member_user_ids(db, organization_id)
    queued = 0
    for uid in member_ids:
        queued += requeue_all_external_api_failures(user_id=uid)
    return {"queued": queued}


@router.post("/organizations/{organization_id}/reclassify")
def org_reclassify(
    organization_id: int,
    payload: ReclassifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    from backend.services.organizations import get_member_user_ids, verify_org_owner_or_admin
    try:
        verify_org_owner_or_admin(db, organization_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    member_ids = get_member_user_ids(db, organization_id)

    transactions = db.scalars(
        select(Transaction).where(
            Transaction.user_id.in_(member_ids),
            Transaction.id.in_(payload.transaction_ids),
        )
    ).all()

    processed = 0
    failed = 0
    failures: list[dict] = []
    for transaction in transactions:
        try:
            classify_transaction(db, transaction, transaction.user_id,
                                 provider_override=payload.provider, force_refresh=True)
            processed += 1
        except Exception as exc:
            failed += 1
            failures.append({"transaction_id": transaction.id, "error": str(exc)})
    return {"processed": processed, "failed": failed, "failures": failures}
```

- [ ] **Step 2: Verify import**

```bash
cd backend && uv run python -c "from backend.api.routes_classification import router; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/backend/api/routes_classification.py
git commit -m "feat: add family-scoped retry-all and reclassify endpoints"
```

---

### Task 10: Verify New Tables Auto-Create

- [ ] **Step 1: Confirm `Base.metadata.create_all()` handles new tables**

`backend/src/backend/main.py` line 21 already calls `Base.metadata.create_all(bind=engine)`. Since `Organization` and `OrganizationMember` inherit from `Base`, they will be auto-created on startup. No changes needed to `runtime_schema.py`.

- [ ] **Step 2: Quick verification**

```bash
cd backend && uv run python -c "
from backend.db.base import Base
from backend.models.entities import Organization, OrganizationMember
# Verify both tables are in Base.metadata
print([t for t in Base.metadata.tables.keys() if 'organization' in t])
"
```

Expected: `['organizations', 'organization_members']`

- [ ] **Step 3: No commit needed for this task**

---

### Task 11: Write Backend Tests

**Files:**
- Create: `backend/tests/test_organizations.py`

Note: Existing conftest provides `db_session`, `client`, `user` ("alice"), and `auth_headers` fixtures. Existing helpers provide `create_category`, `create_import_batch_with_file`, `create_transaction`. Tests that need multiple users create them directly with `User(...)` + `db_session.add()`.

- [ ] **Step 1: Write tests**

```python
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.core.security import create_access_token, get_password_hash
from backend.main import app
from backend.models.entities import Organization, OrganizationMember, Transaction, ImportBatch, User
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
        """创建家庭组织的用户自动成为 owner"""
        owner = _make_user(db_session, "creator")
        org = create_organization(db_session, "测试家庭", owner.id)
        assert org.name == "测试家庭"
        member = db_session.scalars(
            __import__("sqlalchemy").select(OrganizationMember).where(
                OrganizationMember.organization_id == org.id,
                OrganizationMember.user_id == owner.id,
            )
        ).first()
        assert member is not None
        assert member.role == "owner"

    def test_org_appears_in_user_list(self, db_session: Session, client: TestClient):
        """GET /api/organizations 返回用户加入的组织"""
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
        """非组织成员不能访问家庭组织聚合数据"""
        owner = _make_user(db_session, "owner_x")
        outsider = _make_user(db_session, "outsider_x")
        org = create_organization(db_session, "私有家庭", owner.id)
        resp = client.get(
            f"/api/dashboard/summary?organization_id={org.id}",
            headers=_auth_headers_for(outsider),
        )
        assert resp.status_code == 403

    def test_member_can_view_family_dashboard(self, db_session: Session, client: TestClient):
        """member 可以查看家庭 Dashboard"""
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
        """member 不能管理成员"""
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
        """member 不能触发家庭 retry"""
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
        """owner/admin 可以添加成员和修改角色"""
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
        """不能移除最后一个 owner"""
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
        """家庭 Dashboard 能聚合多个成员账单"""
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
        """家庭消费画像能聚合多个成员账单"""
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
        """无组织用户仍可使用个人功能"""
        resp = client.get("/api/dashboard/summary", headers=auth_headers)
        assert resp.status_code == 200

    def test_personal_dashboard_no_org_id(self, client: TestClient, auth_headers: dict):
        """不传 organization_id 时保持个人视角"""
        resp = client.get("/api/dashboard/summary", headers=auth_headers)
        assert resp.status_code == 200
        assert "expense_total" in resp.json()


class TestAdminSeparation:
    def test_system_admin_not_confused_with_org_admin(self, db_session: Session, client: TestClient):
        """系统管理员 is_admin 和家庭组织管理员 role 不混淆"""
        sys_admin = _make_user(db_session, "sysadmin", is_admin=True)
        org_owner = _make_user(db_session, "orgowner")
        org = create_organization(db_session, "测试组织", org_owner.id)

        # sys_admin is NOT a member of the org, should get 403 on family endpoints
        resp = client.get(
            f"/api/dashboard/summary?organization_id={org.id}",
            headers=_auth_headers_for(sys_admin),
        )
        assert resp.status_code == 403

        # But sys_admin CAN access global retry-all (existing admin endpoint)
        resp = client.post(
            "/api/classification/retry-all",
            json={},
            headers=_auth_headers_for(sys_admin),
        )
        assert resp.status_code == 200
```

- [ ] **Step 2: Run the new tests**

```bash
cd backend && uv run pytest tests/test_organizations.py -v
```

Expected: All tests pass.

- [ ] **Step 3: Run all existing tests to verify no regression**

```bash
cd backend && uv run pytest -v
```

Expected: All existing tests still pass (may need minor updates if tests call `dashboard_summary` directly with `user_id` instead of `user_ids`).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_organizations.py
git commit -m "test: add organization feature tests covering all scenarios"
```

---

### Task 12: Frontend — Type Definitions

**Files:**
- Modify: `frontend/src/types/models.ts`

- [ ] **Step 1: Add organization types**

Append to the file:

```typescript
export interface Organization {
  id: number
  name: string
  created_by_user_id: number
  plan: string | null
  subscription_status: string | null
  created_at: string
  updated_at: string
  role: 'owner' | 'admin' | 'member'
}

export interface OrganizationMember {
  id: number
  organization_id: number
  user_id: number
  role: 'owner' | 'admin' | 'member'
  username: string
  created_at: string
  updated_at: string
}
```

- [ ] **Step 2: Verify TypeScript compilation**

```bash
cd frontend && npx vue-tsc --noEmit 2>&1 | head -20
```

Expected: No new type errors related to models.ts.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/models.ts
git commit -m "feat: add organization TypeScript types"
```

---

### Task 13: Frontend — API Client Functions

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add organization API functions**

Append after the existing `export default api` line:

```typescript
import type {
  Organization,
  OrganizationMember,
} from '../types/models'

export function fetchOrganizations() {
  return api.get<Organization[]>('/organizations')
}

export function createOrganization(payload: { name: string }) {
  return api.post<Organization>('/organizations', payload)
}

export function updateOrganization(id: number, payload: { name?: string; plan?: string | null; subscription_status?: string | null }) {
  return api.patch<Organization>(`/organizations/${id}`, payload)
}

export function fetchOrganizationMembers(orgId: number) {
  return api.get<OrganizationMember[]>(`/organizations/${orgId}/members`)
}

export function addOrganizationMember(orgId: number, payload: { username: string }) {
  return api.post<OrganizationMember>(`/organizations/${orgId}/members`, payload)
}

export function updateMemberRole(orgId: number, userId: number, payload: { role: 'admin' | 'member' }) {
  return api.patch<OrganizationMember>(`/organizations/${orgId}/members/${userId}`, payload)
}

export function removeOrganizationMember(orgId: number, userId: number) {
  return api.delete(`/organizations/${orgId}/members/${userId}`)
}

export function fetchFamilyDashboard(orgId: number, params?: Record<string, any>) {
  return api.get('/dashboard/summary', { params: { ...params, organization_id: orgId } })
}

export function fetchFamilyPersonality(orgId: number) {
  return api.get('/personality/profile', { params: { organization_id: orgId } })
}

export function orgRetryAll(orgId: number) {
  return api.post<{ queued: number }>(`/classification/organizations/${orgId}/retry-all`, {})
}

export function orgReclassify(orgId: number, transactionIds: number[], provider?: string) {
  return api.post(`/classification/organizations/${orgId}/reclassify`, {
    transaction_ids: transactionIds,
    provider: provider || null,
  })
}
```

- [ ] **Step 2: Verify TypeScript compilation**

```bash
cd frontend && npx vue-tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add organization API client functions"
```

---

### Task 14: Frontend — Router and Navigation

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/layouts/AppLayout.vue`

- [ ] **Step 1: Add organization route**

In `frontend/src/router/index.ts`, add the import:
```typescript
import OrganizationPage from '../pages/OrganizationPage.vue'
```

Add a new child route inside the `AppLayout` children array:
```typescript
{ path: 'organization', component: OrganizationPage },
```

- [ ] **Step 2: Add sidebar nav item**

In `frontend/src/layouts/AppLayout.vue`:

Add to imports:
```typescript
import { OfficeBuilding } from '@element-plus/icons-vue'
```

Add to `menuItems` array:
```typescript
{ path: '/organization', label: 'Family', subLabel: '家庭组织', icon: OfficeBuilding },
```

- [ ] **Step 3: Verify compilation**

```bash
cd frontend && npx vue-tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/router/index.ts frontend/src/layouts/AppLayout.vue
git commit -m "feat: add organization route and sidebar nav item"
```

---

### Task 15: Frontend — Organization Page

**Files:**
- Create: `frontend/src/pages/OrganizationPage.vue`

- [ ] **Step 1: Write the page**

```vue
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  UserFilled,
  Plus,
  Delete,
  RefreshRight,
  DataAnalysis,
  MagicStick,
} from '@element-plus/icons-vue'
import {
  fetchOrganizations,
  createOrganization,
  updateOrganization,
  fetchOrganizationMembers,
  addOrganizationMember,
  updateMemberRole,
  removeOrganizationMember,
  fetchFamilyDashboard,
  fetchFamilyPersonality,
  orgRetryAll,
} from '../api/client'
import type { Organization, OrganizationMember } from '../types/models'

const organizations = ref<Organization[]>([])
const selectedOrgId = ref<number | null>(null)
const members = ref<OrganizationMember[]>([])
const dashboardData = ref<any>(null)
const personalityData = ref<any>(null)
const loading = ref(false)
const showCreateDialog = ref(false)
const newOrgName = ref('')
const showAddMemberDialog = ref(false)
const newMemberUsername = ref('')
const editingPlan = ref(false)

const selectedOrg = computed(() =>
  organizations.value.find((o) => o.id === selectedOrgId.value) ?? null
)

const isOwnerOrAdmin = computed(() => {
  if (!selectedOrg.value) return false
  return selectedOrg.value.role === 'owner' || selectedOrg.value.role === 'admin'
})

onMounted(async () => {
  try {
    const { data } = await fetchOrganizations()
    organizations.value = data
    if (data.length > 0) {
      selectedOrgId.value = data[0].id
    }
  } catch {
    ElMessage.error('加载组织列表失败')
  }
})

watch(selectedOrgId, async (newId) => {
  if (!newId) return
  await loadOrgData()
})

async function loadOrgData() {
  if (!selectedOrgId.value) return
  loading.value = true
  try {
    const [membersRes, dashRes, persRes] = await Promise.all([
      fetchOrganizationMembers(selectedOrgId.value),
      fetchFamilyDashboard(selectedOrgId.value),
      fetchFamilyPersonality(selectedOrgId.value),
    ])
    members.value = membersRes.data
    dashboardData.value = dashRes.data
    personalityData.value = persRes.data
  } catch {
    ElMessage.error('加载家庭数据失败')
  } finally {
    loading.value = false
  }
}

async function handleCreateOrg() {
  if (!newOrgName.value.trim()) return
  try {
    const { data } = await createOrganization({ name: newOrgName.value.trim() })
    organizations.value.push(data)
    selectedOrgId.value = data.id
    showCreateDialog.value = false
    newOrgName.value = ''
    ElMessage.success('家庭组织创建成功')
  } catch {
    ElMessage.error('创建失败')
  }
}

async function handleAddMember() {
  if (!newMemberUsername.value.trim() || !selectedOrgId.value) return
  try {
    const { data } = await addOrganizationMember(selectedOrgId.value, {
      username: newMemberUsername.value.trim(),
    })
    members.value.push(data)
    newMemberUsername.value = ''
    showAddMemberDialog.value = false
    ElMessage.success('成员添加成功')
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '添加失败')
  }
}

async function handleChangeRole(member: OrganizationMember, newRole: 'admin' | 'member') {
  if (!selectedOrgId.value) return
  try {
    await updateMemberRole(selectedOrgId.value, member.user_id, { role: newRole })
    member.role = newRole
    ElMessage.success('角色已更新')
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '更新失败')
  }
}

async function handleRemoveMember(member: OrganizationMember) {
  if (!selectedOrgId.value) return
  try {
    await ElMessageBox.confirm(`确定要移除 ${member.username} 吗？`, '移除成员', {
      type: 'warning',
    })
    await removeOrganizationMember(selectedOrgId.value, member.user_id)
    members.value = members.value.filter((m) => m.user_id !== member.user_id)
    ElMessage.success('成员已移除')
  } catch {
    // user cancelled
  }
}

async function handleRetryAll() {
  if (!selectedOrgId.value) return
  try {
    const { data } = await orgRetryAll(selectedOrgId.value)
    ElMessage.success(`已将 ${data.queued} 笔交易重新放入重试池`)
  } catch {
    ElMessage.error('操作失败')
  }
}

async function handleUpdatePlan() {
  if (!selectedOrgId.value || !selectedOrg.value) return
  try {
    await updateOrganization(selectedOrgId.value, {
      name: selectedOrg.value.name,
      plan: selectedOrg.value.plan,
      subscription_status: selectedOrg.value.subscription_status,
    })
    editingPlan.value = false
    ElMessage.success('已更新')
  } catch {
    ElMessage.error('更新失败')
  }
}

function formatMoney(val: string | number): string {
  return Number(val).toFixed(2)
}
</script>

<template>
  <div class="org-page">
    <!-- Empty state -->
    <div v-if="organizations.length === 0" class="empty-state">
      <el-result icon="info" title="尚未加入任何家庭组织"
        sub-title="创建一个家庭组织来开始管理家庭账单">
        <template #extra>
          <el-button type="primary" @click="showCreateDialog = true">创建家庭组织</el-button>
        </template>
      </el-result>
    </div>

    <template v-else>
      <div class="org-header">
        <el-select v-model="selectedOrgId" placeholder="选择家庭" style="width: 260px" size="large">
          <el-option v-for="org in organizations" :key="org.id" :label="org.name" :value="org.id">
            <span>{{ org.name }}</span>
            <el-tag size="small" style="margin-left: 8px"
              :type="org.role === 'owner' ? '' : 'info'">
              {{ org.role === 'owner' ? '拥有者' : org.role === 'admin' ? '管理员' : '成员' }}
            </el-tag>
          </el-option>
        </el-select>
        <el-button @click="showCreateDialog = true">新建家庭</el-button>
      </div>

      <el-divider />

      <div v-if="selectedOrg" v-loading="loading">
        <!-- Organization Info (owner/admin) -->
        <el-card v-if="isOwnerOrAdmin" class="info-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>组织信息</span>
              <el-button v-if="!editingPlan" size="small" @click="editingPlan = true">编辑</el-button>
              <el-button v-else size="small" type="primary" @click="handleUpdatePlan">保存</el-button>
            </div>
          </template>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="名称">
              <span v-if="!editingPlan">{{ selectedOrg.name }}</span>
              <el-input v-else v-model="selectedOrg.name" size="small" />
            </el-descriptions-item>
            <el-descriptions-item label="方案">
              <span v-if="!editingPlan">{{ selectedOrg.plan || 'free' }}</span>
              <el-input v-else v-model="selectedOrg.plan" size="small" />
            </el-descriptions-item>
            <el-descriptions-item label="订阅状态">
              <el-tag v-if="!editingPlan"
                :type="selectedOrg.subscription_status === 'active' ? 'success' : 'warning'"
                size="small">
                {{ selectedOrg.subscription_status || 'active' }}
              </el-tag>
              <el-input v-else v-model="selectedOrg.subscription_status" size="small" />
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <!-- Dashboard Summary -->
        <el-card v-if="dashboardData" class="info-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span><el-icon><DataAnalysis /></el-icon> 家庭财务概览</span>
            </div>
          </template>
          <el-row :gutter="16">
            <el-col :span="6">
              <el-statistic title="总支出" :value="formatMoney(dashboardData.expense_total)" prefix="¥" />
            </el-col>
            <el-col :span="6">
              <el-statistic title="总收入" :value="formatMoney(dashboardData.income_total)" prefix="¥" />
            </el-col>
            <el-col :span="6">
              <el-statistic title="净流入" :value="formatMoney(dashboardData.net_total)" prefix="¥" />
            </el-col>
            <el-col :span="6">
              <el-statistic title="交易笔数" :value="dashboardData.transaction_count" />
            </el-col>
          </el-row>
        </el-card>

        <!-- Personality -->
        <el-card v-if="personalityData?.personality" class="info-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span><el-icon><MagicStick /></el-icon> 家庭消费人格</span>
            </div>
          </template>
          <div class="personality-display">
            <div class="personality-main">
              <span class="personality-code">{{ personalityData.personality.code }}</span>
              <span class="personality-name">{{ personalityData.personality.name }}</span>
              <span class="personality-tagline">{{ personalityData.personality.tagline }}</span>
            </div>
            <div class="personality-dims">
              <div v-for="dim in personalityData.personality.dimensions" :key="dim.name" class="dim-row">
                <span class="dim-label">{{ dim.label }}</span>
                <el-progress :percentage="dim.value" :stroke-width="8" :show-text="false"
                  style="flex:1; margin: 0 12px" />
                <span class="dim-value">{{ dim.value.toFixed(0) }}</span>
              </div>
            </div>
            <div v-if="personalityData.financial_health" style="margin-top: 16px">
              <el-tag size="large"
                :type="personalityData.financial_health.grade === 'A' || personalityData.financial_health.grade === 'S' ? 'success' : 'warning'">
                财务健康: {{ personalityData.financial_health.grade }}
                ({{ personalityData.financial_health.total_score?.toFixed(0) }})
              </el-tag>
            </div>
          </div>
        </el-card>

        <!-- Members -->
        <el-card class="info-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span><el-icon><UserFilled /></el-icon> 家庭成员 ({{ members.length }})</span>
              <el-button v-if="isOwnerOrAdmin" size="small" type="primary"
                @click="showAddMemberDialog = true">
                <el-icon><Plus /></el-icon> 添加成员
              </el-button>
            </div>
          </template>
          <el-table :data="members" stripe size="small">
            <el-table-column prop="username" label="用户名" />
            <el-table-column prop="role" label="角色" width="150">
              <template #default="{ row }">
                <template v-if="isOwnerOrAdmin && row.role !== 'owner'">
                  <el-select :model-value="row.role" size="small" style="width: 100px"
                    @change="(val: 'admin' | 'member') => handleChangeRole(row, val)">
                    <el-option label="管理员" value="admin" />
                    <el-option label="成员" value="member" />
                  </el-select>
                </template>
                <el-tag v-else size="small" :type="row.role === 'owner' ? '' : 'info'">
                  {{ row.role === 'owner' ? '拥有者' : row.role === 'admin' ? '管理员' : '成员' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column v-if="isOwnerOrAdmin" label="操作" width="100">
              <template #default="{ row }">
                <el-button v-if="row.role !== 'owner'" size="small" type="danger" :icon="Delete"
                  text @click="handleRemoveMember(row)" />
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <!-- Admin Actions -->
        <el-card v-if="isOwnerOrAdmin" class="info-card" shadow="hover">
          <template #header>
            <div class="card-header"><span>管理操作</span></div>
          </template>
          <el-button :icon="RefreshRight" @click="handleRetryAll">
            重试所有失败的分类
          </el-button>
        </el-card>
      </div>
    </template>

    <!-- Create Org Dialog -->
    <el-dialog v-model="showCreateDialog" title="创建家庭组织" width="420px">
      <el-form @submit.prevent="handleCreateOrg">
        <el-form-item label="家庭名称">
          <el-input v-model="newOrgName" placeholder="例如：张家财务" maxlength="128" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreateOrg" :disabled="!newOrgName.trim()">创建</el-button>
      </template>
    </el-dialog>

    <!-- Add Member Dialog -->
    <el-dialog v-model="showAddMemberDialog" title="添加成员" width="420px">
      <el-form @submit.prevent="handleAddMember">
        <el-form-item label="用户名">
          <el-input v-model="newMemberUsername" placeholder="输入已有用户的用户名" maxlength="64" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddMemberDialog = false">取消</el-button>
        <el-button type="primary" @click="handleAddMember" :disabled="!newMemberUsername.trim()">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.org-page { max-width: 960px; margin: 0 auto; }
.empty-state { margin-top: 80px; }
.org-header { display: flex; align-items: center; gap: 16px; }
.info-card { margin-bottom: 16px; }
.card-header { display: flex; align-items: center; justify-content: space-between; }
.card-header .el-icon { margin-right: 6px; vertical-align: middle; }
.personality-display { padding: 8px 0; }
.personality-main { display: flex; align-items: baseline; gap: 12px; margin-bottom: 16px; }
.personality-code { font-size: 24px; font-weight: 700; color: #00A884; font-family: monospace; }
.personality-name { font-size: 18px; font-weight: 600; }
.personality-tagline { color: #8c8c8c; font-size: 14px; }
.dim-row { display: flex; align-items: center; margin-bottom: 8px; }
.dim-label { width: 100px; font-size: 13px; color: #8c8c8c; }
.dim-value { width: 36px; text-align: right; font-size: 13px; font-weight: 600; }
</style>
```

- [ ] **Step 2: Verify TypeScript compilation**

```bash
cd frontend && npx vue-tsc --noEmit
```

Fix any type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/OrganizationPage.vue
git commit -m "feat: add family organization page with dashboard, personality, and member management"
```

---

### Task 16: Final Integration Verification

- [ ] **Step 1: Start backend and smoke-test new endpoints**

```bash
cd backend && uv run uvicorn backend.main:app --port 8000 &
sleep 3

# Health check
curl -s http://127.0.0.1:8000/health

# Register two users
curl -s -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"family_owner","password":"test123"}' | python -m json.tool

# Create org (extract token from above)
TOKEN="<token-from-above>"
curl -s -X POST http://127.0.0.1:8000/api/organizations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"测试家庭"}' | python -m json.tool

# List orgs
curl -s http://127.0.0.1:8000/api/organizations \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

- [ ] **Step 2: Run all backend tests**

```bash
cd backend && uv run pytest -v
```

Expected: All tests pass (existing + new `test_organizations.py`).

- [ ] **Step 3: Run frontend type check**

```bash
cd frontend && npx vue-tsc --noEmit
```

Expected: No type errors.

- [ ] **Step 4: Final commit**

```bash
git status
git add -A
git commit -m "chore: final integration verification for family organization feature"
```

---

## Summary of Changes

| Category | Files Created | Files Modified | Est. Lines |
|---|---|---|---|
| Backend models | 0 | 1 (`entities.py`) | +45 |
| Backend schemas | 1 (`organizations.py`) | 0 | +55 |
| Backend services | 1 (`organizations.py`) | 3 (`analytics.py`, `personality.py`, `reports.py`) | +170 |
| Backend API routes | 1 (`routes_organizations.py`) | 4 (`router.py`, `routes_dashboard.py`, `routes_reports.py`, `routes_personality.py`, `routes_classification.py`) | +250 |
| Backend tests | 1 (`test_organizations.py`) | 0 | +200 |
| Frontend types | 0 | 1 (`models.ts`) | +25 |
| Frontend API | 0 | 1 (`client.ts`) | +55 |
| Frontend pages | 1 (`OrganizationPage.vue`) | 0 | +280 |
| Frontend routing | 0 | 2 (`router/index.ts`, `AppLayout.vue`) | +10 |
| **Total** | **5 new files** | **12 modified files** | **~1090 lines** |
