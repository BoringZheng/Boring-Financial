from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user, get_db_session
from backend.models import User
from backend.schemas.reports import DashboardSummary
from backend.services.analytics import dashboard_summary

router = APIRouter()


def parse_optional_datetime(value: str | None) -> datetime | None:
    if value in {None, ""}:
        return None
    return datetime.fromisoformat(value)


@router.get("/summary", response_model=DashboardSummary)
def summary(
    date_from: str | None = None,
    date_to: str | None = None,
    category_id: int | None = None,
    uploaded_file_ids: list[int] | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> DashboardSummary:
    return DashboardSummary(
        **dashboard_summary(
            db,
            current_user.id,
            date_from=parse_optional_datetime(date_from),
            date_to=parse_optional_datetime(date_to),
            category_id=category_id,
            uploaded_file_ids=uploaded_file_ids,
        )
    )
