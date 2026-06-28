from __future__ import annotations

import uuid
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db  # re-exported for route dependencies  # noqa: F401
from app.models.user import User
from app.services.auth import get_user
from app.services.email import EmailService, build_email
from app.services.storage import StorageService, build_storage


def _extract_token(request: Request) -> str | None:
    """Prefer the httpOnly cookie; fall back to a Bearer header (curl/tests)."""
    cookie = request.cookies.get(settings.cookie_name)
    if cookie:
        return cookie
    header = request.headers.get("Authorization")
    if header and header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=401,
        detail="Not authenticated.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = _extract_token(request)
    if not token:
        raise credentials_error

    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        user_id = uuid.UUID(str(subject))
    except (jwt.PyJWTError, ValueError) as exc:
        raise credentials_error from exc

    user = get_user(db, user_id)
    if user is None:
        raise credentials_error
    return user



@lru_cache(maxsize=1)
def _storage_singleton() -> StorageService:
    return build_storage()


def get_storage() -> StorageService:
    return _storage_singleton()


@lru_cache(maxsize=1)
def _email_singleton() -> EmailService:
    return build_email()


def get_email() -> EmailService:
    return _email_singleton()
