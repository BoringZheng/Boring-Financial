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
