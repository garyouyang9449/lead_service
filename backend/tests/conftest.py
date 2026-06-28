import io

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


@pytest.fixture
def client(db_session, fake_storage):
    from fastapi.testclient import TestClient

    from app.api.deps import get_db, get_storage
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_storage] = lambda: fake_storage
    with TestClient(app) as c:
        yield c
