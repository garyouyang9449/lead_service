import uuid

import pytest

from app.core.security import hash_password
from app.models.user import User
from app.services.auth import (
    authenticate_user,
    get_user,
    get_user_by_email,
    seed_attorney,
)


@pytest.fixture
def attorney(db_session):
    user = User(
        id=uuid.uuid4(),
        email="lawyer@firm.com",
        hashed_password=hash_password("correct-horse"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_authenticate_user_success(db_session, attorney):
    result = authenticate_user(db_session, "lawyer@firm.com", "correct-horse")
    assert result is not None
    assert result.id == attorney.id


def test_authenticate_user_wrong_password(db_session, attorney):
    assert authenticate_user(db_session, "lawyer@firm.com", "nope") is None


def test_authenticate_user_unknown_email(db_session, attorney):
    assert authenticate_user(db_session, "ghost@firm.com", "correct-horse") is None


def test_get_user_by_id(db_session, attorney):
    assert get_user(db_session, attorney.id).email == "lawyer@firm.com"


def test_get_user_missing_returns_none(db_session):
    assert get_user(db_session, uuid.uuid4()) is None


def test_get_user_by_email(db_session, attorney):
    assert get_user_by_email(db_session, "lawyer@firm.com").id == attorney.id
    assert get_user_by_email(db_session, "ghost@firm.com") is None


def test_seed_attorney_creates_user(db_session):
    user = seed_attorney(db_session, "seed@firm.com", "password123")
    assert user.id is not None
    assert get_user_by_email(db_session, "seed@firm.com") is not None
    # created user can authenticate with the seeded password
    assert authenticate_user(db_session, "seed@firm.com", "password123") is not None


def test_seed_attorney_is_idempotent(db_session):
    first = seed_attorney(db_session, "seed@firm.com", "password123")
    second = seed_attorney(db_session, "seed@firm.com", "a-different-password")
    assert first.id == second.id
    # password is not changed on a repeat seed
    assert authenticate_user(db_session, "seed@firm.com", "password123") is not None
    assert authenticate_user(db_session, "seed@firm.com", "a-different-password") is None
