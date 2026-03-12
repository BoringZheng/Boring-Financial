from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.dependencies import get_current_user, get_db_session
from backend.models import Category, User
from backend.schemas.categories import CategoryCreate, CategoryRead, CategoryUpdate

router = APIRouter()


@router.get("", response_model=list[CategoryRead])
def list_categories(current_user: User = Depends(get_current_user), db: Session = Depends(get_db_session)) -> list[CategoryRead]:
    categories = db.scalars(
        select(Category).where((Category.user_id == None) | (Category.user_id == current_user.id)).order_by(Category.name.asc())
    ).all()
    return [CategoryRead.model_validate(category) for category in categories]


@router.post("", response_model=CategoryRead)
def create_category(payload: CategoryCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db_session)) -> CategoryRead:
    category = Category(
        user_id=current_user.id,
        parent_id=payload.parent_id,
        name=payload.name,
        description=payload.description,
        is_system=False,
        is_active=True,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return CategoryRead.model_validate(category)


@router.patch("/{category_id}", response_model=CategoryRead)
def update_category(category_id: int, payload: CategoryUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db_session)) -> CategoryRead:
    category = db.get(Category, category_id)
    if category is None or (category.user_id not in {None, current_user.id}):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="category not found")
    if category.is_system and payload.is_active is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="system category cannot be disabled here")
    for field in ["name", "parent_id", "description", "is_active"]:
        value = getattr(payload, field)
        if value is not None:
            setattr(category, field, value)
    db.commit()
    db.refresh(category)
    return CategoryRead.model_validate(category)
