from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User


def get_user(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def get_user_by_email(db: Session, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
    return db.execute(stmt).scalar_one_or_none()


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def seed_attorney(db: Session, email: str, password: str) -> User:
    """Idempotently ensure a default attorney account exists.

    Used on startup so the app is usable out of the box. Returns the existing
    user if one already has this email; otherwise creates and returns it.
    """
    existing = get_user_by_email(db, email)
    if existing is not None:
        return existing

    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
