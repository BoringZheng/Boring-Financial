from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.security import decode_token
from backend.db.session import get_db
from backend.models import User


def get_db_session(db: Session = Depends(get_db)) -> Session:
    return db


def get_current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token") from exc
    user_id = payload.get("sub")
    if payload.get("type") != "access" or user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token type")
    user = db.get(User, int(user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin privileges required")
    return current_user
