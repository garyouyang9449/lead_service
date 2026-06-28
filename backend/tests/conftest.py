import io
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
import app.models  # noqa: F401  (register models on Base.metadata)


@pytest.fixture
def db_session():
    """In-memory SQLite session with all tables created."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class FakeStorage:
    """In-memory stand-in for StorageService."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.ensure_called = 0

    def ensure_bucket(self):
        self.ensure_called += 1

    def upload(self, key, fileobj, content_type):
        data = fileobj.read()
        self.objects[key] = data

    def presigned_url(self, key):
        return f"https://fake-storage.local/{key}?signature=abc"


@pytest.fixture
def fake_storage():
    return FakeStorage()


class FakeEmail:
    def __init__(self):
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to, subject, body):
        self.sent.append((to, subject, body))


@pytest.fixture
def fake_email():
    return FakeEmail()


@pytest.fixture
def client(db_session, fake_storage, fake_email):
    from fastapi.testclient import TestClient

    from app.api.deps import get_current_user, get_db, get_email, get_storage
    from app.main import create_app
    from app.models.user import User

    fake_user = User(id=uuid.uuid4(), email="test-attorney@firm.com",
                     hashed_password="x")

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_storage] = lambda: fake_storage
    app.dependency_overrides[get_email] = lambda: fake_email
    app.dependency_overrides[get_current_user] = lambda: fake_user
    with TestClient(app) as c:
        yield c


@pytest.fixture
def unauthed_client(db_session, fake_storage, fake_email):
    """Client WITHOUT a get_current_user override — exercises real auth guards."""
    from fastapi.testclient import TestClient

    from app.api.deps import get_db, get_email, get_storage
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_storage] = lambda: fake_storage
    app.dependency_overrides[get_email] = lambda: fake_email
    with TestClient(app) as c:
        yield c


@pytest.fixture
def seed_user(db_session):
    """Create an attorney user with a known password; returns (user, password)."""
    from app.core.security import hash_password
    from app.models.user import User

    password = "correct-horse"
    user = User(
        id=uuid.uuid4(),
        email="attorney@firm.com",
        hashed_password=hash_password(password),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user, password

