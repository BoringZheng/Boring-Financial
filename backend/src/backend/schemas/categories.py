from __future__ import annotations

from pydantic import BaseModel


class CategoryCreate(BaseModel):
    name: str
    parent_id: int | None = None
    description: str | None = None


class CategoryUpdate(BaseModel):
    name: str | None = None
    parent_id: int | None = None
    description: str | None = None
    is_active: bool | None = None


class CategoryRead(BaseModel):
    id: int
    user_id: int | None
    parent_id: int | None
    name: str
    description: str | None
    is_system: bool
    is_active: bool

    model_config = {"from_attributes": True}
