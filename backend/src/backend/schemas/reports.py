from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class DashboardSummary(BaseModel):
    expense_total: Decimal
    income_total: Decimal
    net_total: Decimal
    transaction_count: int
    pending_review_count: int
    top_merchants: list[dict]
    category_breakdown: list[dict]
    expense_trend: list[dict]
    recent_jobs: list[dict]


class ReportCreateRequest(BaseModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    title: str | None = None
    uploaded_file_ids: list[int] = Field(default_factory=list)

    @field_validator("date_from", "date_to", mode="before")
    @classmethod
    def empty_string_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value


class ReportRead(BaseModel):
    id: int
    user_id: int
    job_id: int
    title: str
    file_path: str

    model_config = {"from_attributes": True}
