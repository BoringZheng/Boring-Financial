"""User-level classification settings persistence.

Settings are stored as a JSON blob in the User.preferences column.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user, get_db
from backend.models import User

router = APIRouter()


class UserSettings(BaseModel):
    """Classification and display preferences persisted per user."""

    provider: str = Field(default="composite", description="Classification strategy: composite | openai_compatible_api | local_model | rule")
    low_confidence_threshold: float = Field(default=0.75, ge=0.1, le=1.0)
    openai_model: str = Field(default="gpt-4.1-mini")
    local_model: str = Field(default="Qwen2.5-7B-Instruct")


_DEFAULTS = UserSettings()


@router.get("", response_model=UserSettings)
def get_settings(
    current_user: User = Depends(get_current_user),
):
    """Return current user's classification settings."""
    if current_user.preferences:
        try:
            data = json.loads(current_user.preferences)
            return UserSettings(**data)
        except (json.JSONDecodeError, ValueError):
            pass
    return _DEFAULTS


@router.put("", response_model=UserSettings)
def update_settings(
    payload: UserSettings,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist user classification settings."""
    current_user.preferences = payload.model_dump_json()
    db.commit()
    db.refresh(current_user)
    return payload
