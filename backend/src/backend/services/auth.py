from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.security import get_password_hash, verify_password
from backend.models import User


@dataclass
class AuthResult:
    user: User
    created: bool = False


def create_user(db: Session, username: str, password: str, email: str | None = None) -> User:
    existing = db.scalar(select(User).where(User.username == username))
    if existing:
        raise ValueError("username already exists")
    user = User(username=username, email=email, hashed_password=get_password_hash(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.username == username))
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user
