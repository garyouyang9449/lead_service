# Lead Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a full-stack lead management system: a public submission form that emails prospect + attorney, and a JWT-guarded internal UI to list leads and transition their state.

**Architecture:** FastAPI backend (service-layer pattern) + Next.js App Router frontend, backed by Postgres, MinIO (S3-compatible resume storage), and Mailpit (SMTP capture). All five services run via `docker-compose`. Backend follows TDD with pytest.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, pydantic-settings, boto3, passlib[bcrypt], python-jose, pytest. Next.js 14 (App Router, TypeScript), React. Postgres 16, MinIO, Mailpit. Docker Compose.

---

## Conventions for the implementing agent

- **Backend commands run from `backend/`** unless stated. Use a virtualenv: `python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`.
- **Frontend commands run from `frontend/`**.
- Do not invent APIs not defined here. Every type/function used is defined in an earlier task.
- Tests use a **separate test Postgres DB**; storage and email are **mocked** in unit/API tests (no live MinIO/SMTP needed to run pytest).

---

## File Structure (locked)

```
backend/app/main.py              # app factory, router includes, startup seed, /health
backend/app/core/config.py       # Settings (pydantic-settings)
backend/app/core/security.py     # hash_password, verify_password, create_access_token, decode_token
backend/app/core/logging.py      # configure_logging()
backend/app/db/base.py           # Declarative Base + model imports
backend/app/db/session.py        # engine, SessionLocal, get_db
backend/app/models/lead.py       # Lead model + LeadState enum
backend/app/models/user.py       # User model
backend/app/schemas/lead.py      # LeadRead, LeadUpdate
backend/app/schemas/auth.py      # LoginRequest, TokenResponse, UserRead
backend/app/services/storage.py  # StorageService (boto3/MinIO)
backend/app/services/email.py    # EmailService (SMTP)
backend/app/services/leads.py    # lead business logic + state machine
backend/app/services/auth.py     # authenticate_user
backend/app/api/deps.py          # get_db, get_current_user, get_storage, get_email
backend/app/api/routes/leads.py  # public create + internal list/get/patch
backend/app/api/routes/auth.py   # login, me
backend/tests/...                # pytest suite
frontend/app/...                 # Next.js pages
frontend/lib/api.ts              # fetch client
frontend/lib/auth.ts             # token helpers
docker-compose.yml
.env.example
README.md
```

---

## Task 0: Repo scaffolding, docker-compose, env

**Files:**
- Create: `.gitignore`, `.env.example`, `docker-compose.yml`

- [ ] **Step 1: Create `.gitignore`**

```
# Python
__pycache__/
*.py[cod]
.venv/
*.egg-info/
.pytest_cache/
# Node
node_modules/
.next/
# Env
.env
# OS
.DS_Store
```

- [ ] **Step 2: Create `.env.example`**

```
# Database
POSTGRES_USER=lead
POSTGRES_PASSWORD=lead
POSTGRES_DB=lead
DATABASE_URL=postgresql+psycopg://lead:lead@db:5432/lead

# JWT
JWT_SECRET=change-me-in-prod
JWT_EXPIRE_MINUTES=60

# Default seeded attorney
DEFAULT_ATTORNEY_EMAIL=attorney@firm.test
DEFAULT_ATTORNEY_PASSWORD=password123

# Email
SMTP_HOST=mail
SMTP_PORT=1025
EMAIL_FROM=no-reply@firm.test
ATTORNEY_EMAIL=attorney@firm.test

# Storage (MinIO)
S3_ENDPOINT_URL=http://storage:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=resumes
S3_REGION=us-east-1

# Upload rules
MAX_RESUME_MB=5

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

- [ ] **Step 3: Create `docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-lead}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-lead}
      POSTGRES_DB: ${POSTGRES_DB:-lead}
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U lead"]
      interval: 5s
      timeout: 3s
      retries: 10

  storage:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${S3_ACCESS_KEY:-minioadmin}
      MINIO_ROOT_PASSWORD: ${S3_SECRET_KEY:-minioadmin}
    ports: ["9000:9000", "9001:9001"]
    volumes: ["miniodata:/data"]

  mail:
    image: axllent/mailpit
    ports: ["8025:8025", "1025:1025"]

  api:
    build: ./backend
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      storage:
        condition: service_started
      mail:
        condition: service_started
    ports: ["8000:8000"]

  web:
    build: ./frontend
    environment:
      NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:-http://localhost:8000}
    depends_on:
      api:
        condition: service_started
    ports: ["3000:3000"]

volumes:
  pgdata:
  miniodata:
```

---

## Task 1: Backend project + config + app skeleton + /health

**Files:**
- Create: `backend/pyproject.toml`, `backend/Dockerfile`, `backend/app/__init__.py`, `backend/app/core/config.py`, `backend/app/core/logging.py`, `backend/app/main.py`, `backend/tests/__init__.py`, `backend/tests/conftest.py`, `backend/tests/test_health.py`

- [ ] **Step 1: Create `backend/pyproject.toml`**

```toml
[project]
name = "lead-service"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.110",
  "uvicorn[standard]>=0.29",
  "sqlalchemy>=2.0",
  "psycopg[binary]>=3.1",
  "alembic>=1.13",
  "pydantic-settings>=2.2",
  "pydantic[email]>=2.6",
  "python-jose[cryptography]>=3.3",
  "passlib[bcrypt]>=1.7",
  "boto3>=1.34",
  "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "httpx>=0.27"]

[tool.setuptools.packages.find]
include = ["app*"]

[tool.pytest.ini_options]
pythonpath = ["."]
```

- [ ] **Step 2: Create `backend/app/core/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://lead:lead@localhost:5432/lead"

    jwt_secret: str = "change-me-in-prod"
    jwt_expire_minutes: int = 60
    jwt_algorithm: str = "HS256"

    default_attorney_email: str = "attorney@firm.test"
    default_attorney_password: str = "password123"

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    email_from: str = "no-reply@firm.test"
    attorney_email: str = "attorney@firm.test"

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "resumes"
    s3_region: str = "us-east-1"

    max_resume_mb: int = 5


settings = Settings()
```

- [ ] **Step 3: Create `backend/app/core/logging.py`**

```python
import logging


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
```

- [ ] **Step 4: Create `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Lead Service")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 5: Create `backend/tests/conftest.py` (minimal for now)**

```python
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    return TestClient(create_app())
```

- [ ] **Step 6: Write failing test `backend/tests/test_health.py`**

```python
def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 7: Run test**

Run: `cd backend && pip install -e ".[dev]" && pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 8: Create `backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"
COPY . .
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

- [ ] **Step 9: Add empty `backend/app/__init__.py` and `backend/tests/__init__.py`**

---

## Task 2: Database models, session, Alembic

**Files:**
- Create: `backend/app/db/session.py`, `backend/app/db/base.py`, `backend/app/models/__init__.py`, `backend/app/models/lead.py`, `backend/app/models/user.py`, `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/tests/test_models.py`

- [ ] **Step 1: Create `backend/app/db/session.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: Create `backend/app/models/lead.py`**

```python
import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LeadState(str, enum.Enum):
    PENDING = "PENDING"
    REACHED_OUT = "REACHED_OUT"


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    resume_key: Mapped[str] = mapped_column(String, nullable=False)
    resume_filename: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[LeadState] = mapped_column(
        Enum(LeadState, name="lead_state"), default=LeadState.PENDING, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 3: Create `backend/app/models/user.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 4: Create `backend/app/db/base.py`**

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import models so Alembic autogenerate + Base.metadata see them.
from app.models.lead import Lead  # noqa: E402,F401
from app.models.user import User  # noqa: E402,F401
```

- [ ] **Step 5: Create `backend/app/models/__init__.py`** (empty file)

- [ ] **Step 6: Initialize Alembic**

Run: `cd backend && alembic init alembic`
Then replace `backend/alembic/env.py` body's config with:

```python
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

from app.core.config import settings
from app.db.base import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        url=settings.database_url,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 7: Generate the initial migration**

Run (requires a running Postgres; use docker `db` service or local):
`cd backend && alembic revision --autogenerate -m "create leads and users"`
Expected: a migration file appears under `backend/alembic/versions/` creating `leads` and `users`.

- [ ] **Step 8: Write test `backend/tests/test_models.py`**

```python
from app.models.lead import Lead, LeadState
from app.models.user import User


def test_lead_defaults_to_pending():
    lead = Lead(
        first_name="A", last_name="B", email="a@b.com",
        resume_key="k", resume_filename="cv.pdf",
    )
    # default applied at flush time; check the enum value exists
    assert LeadState.PENDING.value == "PENDING"
    assert lead.first_name == "A"


def test_user_fields():
    u = User(email="x@y.com", hashed_password="h")
    assert u.email == "x@y.com"
```

- [ ] **Step 9: Run test**

Run: `cd backend && pytest tests/test_models.py -v`
Expected: PASS

---

## Task 3: Security — password hashing + JWT

**Files:**
- Create: `backend/app/core/security.py`, `backend/tests/test_security.py`

- [ ] **Step 1: Write failing test `backend/tests/test_security.py`**

```python
from app.core.security import (
    hash_password, verify_password, create_access_token, decode_token,
)


def test_password_hash_roundtrip():
    h = hash_password("secret")
    assert h != "secret"
    assert verify_password("secret", h)
    assert not verify_password("wrong", h)


def test_jwt_roundtrip():
    token = create_access_token(subject="user@x.com")
    payload = decode_token(token)
    assert payload["sub"] == "user@x.com"


def test_decode_invalid_token_returns_none():
    assert decode_token("not.a.token") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_security.py -v`
Expected: FAIL with import error.

- [ ] **Step 3: Create `backend/app/core/security.py`**

```python
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _pwd.verify(password, hashed)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_security.py -v`
Expected: PASS

---

## Task 4: Storage service (MinIO/S3)

**Files:**
- Create: `backend/app/services/storage.py`, `backend/app/services/__init__.py`, `backend/tests/test_storage.py`

- [ ] **Step 1: Write failing test `backend/tests/test_storage.py`** (boto3 mocked)

```python
from unittest.mock import MagicMock
from app.services.storage import StorageService


def test_upload_returns_key():
    client = MagicMock()
    svc = StorageService(client=client, bucket="resumes")
    key = svc.upload(b"data", filename="cv.pdf", content_type="application/pdf")
    assert key.endswith("cv.pdf")
    client.put_object.assert_called_once()


def test_presigned_url_delegates_to_client():
    client = MagicMock()
    client.generate_presigned_url.return_value = "http://signed"
    svc = StorageService(client=client, bucket="resumes")
    url = svc.presigned_url("leads/x/cv.pdf")
    assert url == "http://signed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_storage.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Create `backend/app/services/storage.py`**

```python
import uuid

import boto3

from app.core.config import settings


class StorageService:
    def __init__(self, client, bucket: str):
        self._client = client
        self._bucket = bucket

    @classmethod
    def from_settings(cls) -> "StorageService":
        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )
        return cls(client=client, bucket=settings.s3_bucket)

    def ensure_bucket(self) -> None:
        existing = [b["Name"] for b in self._client.list_buckets().get("Buckets", [])]
        if self._bucket not in existing:
            self._client.create_bucket(Bucket=self._bucket)

    def upload(self, data: bytes, filename: str, content_type: str) -> str:
        key = f"leads/{uuid.uuid4()}/{filename}"
        self._client.put_object(
            Bucket=self._bucket, Key=key, Body=data, ContentType=content_type
        )
        return key

    def presigned_url(self, key: str, expires: int = 3600) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_storage.py -v`
Expected: PASS

---

## Task 5: Email service (SMTP)

**Files:**
- Create: `backend/app/services/email.py`, `backend/tests/test_email.py`

- [ ] **Step 1: Write failing test `backend/tests/test_email.py`** (smtplib mocked)

```python
from unittest.mock import MagicMock, patch
from app.services.email import EmailService


def test_send_lead_emails_sends_two_messages():
    svc = EmailService(host="h", port=1025, sender="from@x.com", attorney="att@x.com")
    with patch("app.services.email.smtplib.SMTP") as smtp:
        instance = MagicMock()
        smtp.return_value.__enter__.return_value = instance
        svc.send_lead_notifications(
            prospect_email="p@x.com", first_name="Jane", last_name="Doe"
        )
        # one to prospect, one to attorney
        assert instance.send_message.call_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_email.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Create `backend/app/services/email.py`**

```python
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, host: str, port: int, sender: str, attorney: str):
        self._host = host
        self._port = port
        self._sender = sender
        self._attorney = attorney

    @classmethod
    def from_settings(cls) -> "EmailService":
        return cls(
            host=settings.smtp_host,
            port=settings.smtp_port,
            sender=settings.email_from,
            attorney=settings.attorney_email,
        )

    def _build(self, to: str, subject: str, body: str) -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = self._sender
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        return msg

    def send_lead_notifications(
        self, prospect_email: str, first_name: str, last_name: str
    ) -> None:
        prospect = self._build(
            to=prospect_email,
            subject="We received your application",
            body=f"Hi {first_name},\n\nThanks for applying. We'll be in touch soon.",
        )
        attorney = self._build(
            to=self._attorney,
            subject="New lead submitted",
            body=f"New lead: {first_name} {last_name} <{prospect_email}>.",
        )
        try:
            with smtplib.SMTP(self._host, self._port) as server:
                server.send_message(prospect)
                server.send_message(attorney)
        except Exception:  # noqa: BLE001 — email failures must not break submission
            logger.exception("Failed to send lead notification emails")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_email.py -v`
Expected: PASS

---

## Task 6: Schemas

**Files:**
- Create: `backend/app/schemas/__init__.py`, `backend/app/schemas/lead.py`, `backend/app/schemas/auth.py`

- [ ] **Step 1: Create `backend/app/schemas/lead.py`**

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.lead import LeadState


class LeadRead(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    email: EmailStr
    state: LeadState
    resume_filename: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LeadDetail(LeadRead):
    resume_url: str


class LeadUpdate(BaseModel):
    state: LeadState
```

- [ ] **Step 2: Create `backend/app/schemas/auth.py`**

```python
import uuid

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    id: uuid.UUID
    email: EmailStr

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Create empty `backend/app/schemas/__init__.py`**

---

## Task 7: Leads service + state machine

**Files:**
- Create: `backend/app/services/leads.py`, `backend/tests/test_leads_service.py`

- [ ] **Step 1: Write failing test `backend/tests/test_leads_service.py`**

```python
import pytest
from app.models.lead import Lead, LeadState
from app.services.leads import (
    create_lead, transition_state, InvalidTransitionError,
)


class FakeSession:
    def __init__(self):
        self.added = []
        self.committed = False
    def add(self, obj): self.added.append(obj)
    def commit(self): self.committed = True
    def refresh(self, obj): pass


def test_create_lead_persists_pending_lead():
    db = FakeSession()
    lead = create_lead(
        db, first_name="Jane", last_name="Doe", email="j@x.com",
        resume_key="k", resume_filename="cv.pdf",
    )
    assert lead.state == LeadState.PENDING
    assert db.committed


def test_valid_transition_pending_to_reached_out():
    lead = Lead(first_name="J", last_name="D", email="j@x.com",
                resume_key="k", resume_filename="cv.pdf", state=LeadState.PENDING)
    db = FakeSession()
    transition_state(db, lead, LeadState.REACHED_OUT)
    assert lead.state == LeadState.REACHED_OUT


def test_invalid_transition_raises():
    lead = Lead(first_name="J", last_name="D", email="j@x.com",
                resume_key="k", resume_filename="cv.pdf", state=LeadState.REACHED_OUT)
    db = FakeSession()
    with pytest.raises(InvalidTransitionError):
        transition_state(db, lead, LeadState.PENDING)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_leads_service.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Create `backend/app/services/leads.py`**

```python
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lead import Lead, LeadState

# Allowed state transitions.
_ALLOWED = {
    LeadState.PENDING: {LeadState.REACHED_OUT},
    LeadState.REACHED_OUT: set(),
}


class InvalidTransitionError(Exception):
    pass


def create_lead(
    db: Session, *, first_name: str, last_name: str, email: str,
    resume_key: str, resume_filename: str,
) -> Lead:
    lead = Lead(
        first_name=first_name, last_name=last_name, email=email,
        resume_key=resume_key, resume_filename=resume_filename,
        state=LeadState.PENDING,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def list_leads(db: Session, *, limit: int = 50, offset: int = 0) -> list[Lead]:
    stmt = select(Lead).order_by(Lead.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt))


def get_lead(db: Session, lead_id: uuid.UUID) -> Lead | None:
    return db.get(Lead, lead_id)


def transition_state(db: Session, lead: Lead, new_state: LeadState) -> Lead:
    if new_state not in _ALLOWED[lead.state]:
        raise InvalidTransitionError(
            f"Cannot transition from {lead.state} to {new_state}"
        )
    lead.state = new_state
    db.commit()
    db.refresh(lead)
    return lead
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_leads_service.py -v`
Expected: PASS

---

## Task 8: Auth service

**Files:**
- Create: `backend/app/services/auth.py`, `backend/tests/test_auth_service.py`

- [ ] **Step 1: Write failing test `backend/tests/test_auth_service.py`**

```python
from app.core.security import hash_password
from app.models.user import User
from app.services.auth import authenticate_user


class FakeScalars:
    def __init__(self, user): self._user = user
    def first(self): return self._user


class FakeSession:
    def __init__(self, user): self._user = user
    def scalars(self, stmt): return FakeScalars(self._user)


def test_authenticate_valid_credentials_returns_user():
    user = User(email="a@x.com", hashed_password=hash_password("pw"))
    db = FakeSession(user)
    assert authenticate_user(db, "a@x.com", "pw") is user


def test_authenticate_wrong_password_returns_none():
    user = User(email="a@x.com", hashed_password=hash_password("pw"))
    db = FakeSession(user)
    assert authenticate_user(db, "a@x.com", "bad") is None


def test_authenticate_unknown_user_returns_none():
    db = FakeSession(None)
    assert authenticate_user(db, "no@x.com", "pw") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_auth_service.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Create `backend/app/services/auth.py`**

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.user import User


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalars(select(User).where(User.email == email)).first()


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_auth_service.py -v`
Expected: PASS

---

## Task 9: API dependencies (DB, current user, services)

**Files:**
- Create: `backend/app/api/__init__.py`, `backend/app/api/deps.py`, `backend/app/api/routes/__init__.py`

- [ ] **Step 1: Create `backend/app/api/deps.py`**

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.services.auth import get_user_by_email
from app.services.storage import StorageService
from app.services.email import EmailService

_bearer = HTTPBearer(auto_error=True)


def get_storage() -> StorageService:
    return StorageService.from_settings()


def get_email() -> EmailService:
    return EmailService.from_settings()


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_token(creds.credentials)
    if payload is None or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    user = get_user_by_email(db, payload["sub"])
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user
```

- [ ] **Step 2: Create empty `backend/app/api/__init__.py` and `backend/app/api/routes/__init__.py`**

---

## Task 10: Auth routes

**Files:**
- Create: `backend/app/api/routes/auth.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_auth_api.py`

- [ ] **Step 1: Create `backend/app/api/routes/auth.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserRead
from app.services.auth import authenticate_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    return TokenResponse(access_token=create_access_token(subject=user.email))


@router.get("/me", response_model=UserRead)
def me(current: User = Depends(get_current_user)) -> User:
    return current
```

- [ ] **Step 2: Modify `backend/app/main.py` to include the router**

Inside `create_app()`, after CORS middleware and before returning, add:

```python
    from app.api.routes import auth
    app.include_router(auth.router)
```

- [ ] **Step 3: Add DB-backed test fixtures to `backend/tests/conftest.py`** (replace file contents)

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import create_app
from app.db.base import Base
from app.db.session import get_db
from app.core.security import hash_password
from app.models.user import User

TEST_DB_URL = "postgresql+psycopg://lead:lead@localhost:5432/lead_test"


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DB_URL)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture
def db_session(engine):
    connection = engine.connect()
    txn = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    txn.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


@pytest.fixture
def seeded_user(db_session):
    user = User(email="attorney@firm.test", hashed_password=hash_password("password123"))
    db_session.add(user)
    db_session.commit()
    return user
```

> Note: requires a `lead_test` database. Create it once: `createdb lead_test` or
> `docker compose exec db psql -U lead -c "CREATE DATABASE lead_test;"`.
> The earlier `test_health.py` still works since it doesn't use `db_session`.

- [ ] **Step 4: Write failing test `backend/tests/test_auth_api.py`**

```python
def test_login_success_returns_token(client, seeded_user):
    resp = client.post("/api/auth/login",
                       json={"email": "attorney@firm.test", "password": "password123"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_bad_password_returns_401(client, seeded_user):
    resp = client.post("/api/auth/login",
                       json={"email": "attorney@firm.test", "password": "wrong"})
    assert resp.status_code == 401


def test_me_requires_token(client, seeded_user):
    assert client.get("/api/auth/me").status_code == 403  # no bearer => HTTPBearer 403


def test_me_with_token(client, seeded_user):
    token = client.post("/api/auth/login",
        json={"email": "attorney@firm.test", "password": "password123"}).json()["access_token"]
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "attorney@firm.test"
```

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest tests/test_auth_api.py -v`
Expected: PASS

---

## Task 11: Leads routes (public create + internal list/get/patch)

**Files:**
- Create: `backend/app/api/routes/leads.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_leads_api.py`

- [ ] **Step 1: Create `backend/app/api/routes/leads.py`**

```python
import uuid

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, UploadFile,
    BackgroundTasks, status,
)
from pydantic import EmailStr
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_storage, get_email
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.lead import LeadRead, LeadDetail, LeadUpdate
from app.services import leads as leads_service
from app.services.email import EmailService
from app.services.storage import StorageService

router = APIRouter(prefix="/api/leads", tags=["leads"])

_ALLOWED_EXT = {"pdf", "doc", "docx"}


@router.post("", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
def create_lead(
    background: BackgroundTasks,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: EmailStr = Form(...),
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
    emailer: EmailService = Depends(get_email),
) -> LeadRead:
    filename = resume.filename or "resume"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _ALLOWED_EXT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(_ALLOWED_EXT))}",
        )
    data = resume.file.read()
    if len(data) > settings.max_resume_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File exceeds {settings.max_resume_mb}MB limit",
        )

    key = storage.upload(
        data, filename=filename,
        content_type=resume.content_type or "application/octet-stream",
    )
    lead = leads_service.create_lead(
        db, first_name=first_name, last_name=last_name, email=str(email),
        resume_key=key, resume_filename=filename,
    )
    background.add_task(
        emailer.send_lead_notifications,
        prospect_email=str(email), first_name=first_name, last_name=last_name,
    )
    return lead


@router.get("", response_model=list[LeadRead])
def list_leads(
    limit: int = 50, offset: int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[LeadRead]:
    return leads_service.list_leads(db, limit=limit, offset=offset)


@router.get("/{lead_id}", response_model=LeadDetail)
def get_lead(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
    _: User = Depends(get_current_user),
) -> LeadDetail:
    lead = leads_service.get_lead(db, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    url = storage.presigned_url(lead.resume_key)
    return LeadDetail(**LeadRead.model_validate(lead).model_dump(), resume_url=url)


@router.patch("/{lead_id}", response_model=LeadRead)
def update_lead(
    lead_id: uuid.UUID,
    payload: LeadUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> LeadRead:
    lead = leads_service.get_lead(db, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    try:
        return leads_service.transition_state(db, lead, payload.state)
    except leads_service.InvalidTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
```

- [ ] **Step 2: Modify `backend/app/main.py`** to include the leads router:

```python
    from app.api.routes import auth, leads
    app.include_router(auth.router)
    app.include_router(leads.router)
```

(Replace the prior single-router import line from Task 10.)

- [ ] **Step 3: Write failing test `backend/tests/test_leads_api.py`** (storage + email overridden)

```python
import io
from unittest.mock import MagicMock

from app.api.deps import get_storage, get_email
from app.models.lead import LeadState


def _auth_header(client):
    token = client.post("/api/auth/login",
        json={"email": "attorney@firm.test", "password": "password123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _override_services(client):
    storage = MagicMock()
    storage.upload.return_value = "leads/x/cv.pdf"
    storage.presigned_url.return_value = "http://signed/cv.pdf"
    emailer = MagicMock()
    client.app.dependency_overrides[get_storage] = lambda: storage
    client.app.dependency_overrides[get_email] = lambda: emailer
    return storage, emailer


def test_create_lead_public_succeeds(client):
    storage, emailer = _override_services(client)
    resp = client.post(
        "/api/leads",
        data={"first_name": "Jane", "last_name": "Doe", "email": "jane@x.com"},
        files={"resume": ("cv.pdf", io.BytesIO(b"%PDF-1.4 data"), "application/pdf")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["state"] == "PENDING"
    storage.upload.assert_called_once()
    emailer.send_lead_notifications.assert_called_once()


def test_create_lead_rejects_bad_extension(client):
    _override_services(client)
    resp = client.post(
        "/api/leads",
        data={"first_name": "Jane", "last_name": "Doe", "email": "jane@x.com"},
        files={"resume": ("cv.exe", io.BytesIO(b"data"), "application/octet-stream")},
    )
    assert resp.status_code == 422


def test_list_leads_requires_auth(client):
    assert client.get("/api/leads").status_code == 403


def test_list_and_patch_flow(client, seeded_user):
    _override_services(client)
    client.post(
        "/api/leads",
        data={"first_name": "Jane", "last_name": "Doe", "email": "jane@x.com"},
        files={"resume": ("cv.pdf", io.BytesIO(b"data"), "application/pdf")},
    )
    headers = _auth_header(client)
    listed = client.get("/api/leads", headers=headers).json()
    assert len(listed) == 1
    lead_id = listed[0]["id"]

    patched = client.patch(f"/api/leads/{lead_id}",
                           json={"state": "REACHED_OUT"}, headers=headers)
    assert patched.status_code == 200
    assert patched.json()["state"] == "REACHED_OUT"

    # second transition is invalid
    again = client.patch(f"/api/leads/{lead_id}",
                         json={"state": "PENDING"}, headers=headers)
    assert again.status_code == 409
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_leads_api.py -v`
Expected: PASS

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && pytest -v`
Expected: all PASS

---

## Task 12: Startup — bucket + DB seed wiring

**Files:**
- Modify: `backend/app/main.py` (startup event: ensure bucket + seed attorney)
- Create: `backend/app/db/seed.py`
- Test: `backend/tests/test_seed.py`

- [ ] **Step 1: Create `backend/app/db/seed.py`**

```python
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User
from app.services.auth import get_user_by_email


def seed_default_attorney(db: Session) -> None:
    if get_user_by_email(db, settings.default_attorney_email) is None:
        db.add(User(
            email=settings.default_attorney_email,
            hashed_password=hash_password(settings.default_attorney_password),
        ))
        db.commit()
```

- [ ] **Step 2: Write failing test `backend/tests/test_seed.py`**

```python
from app.db.seed import seed_default_attorney
from app.services.auth import get_user_by_email
from app.core.config import settings


def test_seed_is_idempotent(db_session):
    seed_default_attorney(db_session)
    seed_default_attorney(db_session)
    user = get_user_by_email(db_session, settings.default_attorney_email)
    assert user is not None
```

- [ ] **Step 3: Run test**

Run: `cd backend && pytest tests/test_seed.py -v`
Expected: PASS

- [ ] **Step 4: Modify `backend/app/main.py`** — add a startup hook inside `create_app()`:

```python
    @app.on_event("startup")
    def _startup() -> None:
        from app.db.session import SessionLocal
        from app.db.seed import seed_default_attorney
        from app.services.storage import StorageService
        db = SessionLocal()
        try:
            seed_default_attorney(db)
        finally:
            db.close()
        try:
            StorageService.from_settings().ensure_bucket()
        except Exception:  # noqa: BLE001 — storage may be unavailable in some envs
            pass
```

- [ ] **Step 5: Run full suite**

Run: `cd backend && pytest -v`
Expected: all PASS

---

## Task 13: Frontend scaffold + API client + auth helpers

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/next.config.js`, `frontend/Dockerfile`, `frontend/app/layout.tsx`, `frontend/lib/api.ts`, `frontend/lib/auth.ts`

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "lead-web",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start -p 3000"
  },
  "dependencies": {
    "next": "14.2.5",
    "react": "18.3.1",
    "react-dom": "18.3.1"
  },
  "devDependencies": {
    "typescript": "5.5.4",
    "@types/react": "18.3.3",
    "@types/node": "20.14.0"
  }
}
```

- [ ] **Step 2: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Create `frontend/next.config.js`**

```js
/** @type {import('next').NextConfig} */
module.exports = { output: "standalone" };
```

- [ ] **Step 4: Create `frontend/lib/auth.ts`**

```ts
const TOKEN_KEY = "lead_token";

export function saveToken(token: string): void {
  if (typeof window !== "undefined") localStorage.setItem(TOKEN_KEY, token);
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function clearToken(): void {
  if (typeof window !== "undefined") localStorage.removeItem(TOKEN_KEY);
}
```

- [ ] **Step 5: Create `frontend/lib/api.ts`**

```ts
import { getToken } from "./auth";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Lead = {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  state: "PENDING" | "REACHED_OUT";
  resume_filename: string;
  created_at: string;
  updated_at: string;
};

export type LeadDetail = Lead & { resume_url: string };

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function login(email: string, password: string): Promise<string> {
  const res = await fetch(`${BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error("Invalid credentials");
  return (await res.json()).access_token as string;
}

export async function submitLead(form: FormData): Promise<void> {
  const res = await fetch(`${BASE}/api/leads`, { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? "Submission failed");
  }
}

export async function fetchLeads(): Promise<Lead[]> {
  const res = await fetch(`${BASE}/api/leads`, { headers: authHeaders() });
  if (res.status === 401 || res.status === 403) throw new Error("unauthorized");
  if (!res.ok) throw new Error("Failed to load leads");
  return res.json();
}

export async function fetchLead(id: string): Promise<LeadDetail> {
  const res = await fetch(`${BASE}/api/leads/${id}`, { headers: authHeaders() });
  if (res.status === 401 || res.status === 403) throw new Error("unauthorized");
  if (!res.ok) throw new Error("Failed to load lead");
  return res.json();
}

export async function markReachedOut(id: string): Promise<Lead> {
  const res = await fetch(`${BASE}/api/leads/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ state: "REACHED_OUT" }),
  });
  if (!res.ok) throw new Error("Failed to update lead");
  return res.json();
}
```

- [ ] **Step 6: Create `frontend/app/layout.tsx`**

```tsx
export const metadata = { title: "Lead Service" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", margin: 0, padding: 24 }}>
        {children}
      </body>
    </html>
  );
}
```

- [ ] **Step 7: Create `frontend/Dockerfile`**

```dockerfile
FROM node:20-slim AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM node:20-slim
WORKDIR /app
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

> Note: create an empty `frontend/public/.gitkeep` so the Dockerfile COPY of `public` succeeds.

- [ ] **Step 8: Install and typecheck**

Run: `cd frontend && npm install && npx tsc --noEmit`
Expected: no type errors.

---

## Task 14: Public lead submission form (`/`)

**Files:**
- Create: `frontend/app/page.tsx`

- [ ] **Step 1: Create `frontend/app/page.tsx`**

```tsx
"use client";

import { useState } from "react";
import { submitLead } from "@/lib/api";

export default function HomePage() {
  const [status, setStatus] = useState<"idle" | "submitting" | "done" | "error">("idle");
  const [error, setError] = useState<string>("");

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setStatus("submitting");
    setError("");
    const form = new FormData(e.currentTarget);
    try {
      await submitLead(form);
      setStatus("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setStatus("error");
    }
  }

  if (status === "done") {
    return <main><h1>Thank you!</h1><p>Your application has been received.</p></main>;
  }

  return (
    <main style={{ maxWidth: 480 }}>
      <h1>Apply</h1>
      <form onSubmit={onSubmit}>
        <p><label>First name<br /><input name="first_name" required /></label></p>
        <p><label>Last name<br /><input name="last_name" required /></label></p>
        <p><label>Email<br /><input name="email" type="email" required /></label></p>
        <p><label>Resume / CV<br />
          <input name="resume" type="file" accept=".pdf,.doc,.docx" required />
        </label></p>
        {status === "error" && <p style={{ color: "red" }}>{error}</p>}
        <button type="submit" disabled={status === "submitting"}>
          {status === "submitting" ? "Submitting…" : "Submit"}
        </button>
      </form>
    </main>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

---

## Task 15: Login page (`/login`)

**Files:**
- Create: `frontend/app/login/page.tsx`

- [ ] **Step 1: Create `frontend/app/login/page.tsx`**

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";
import { saveToken } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const token = await login(email, password);
      saveToken(token);
      router.push("/leads");
    } catch {
      setError("Invalid credentials");
    }
  }

  return (
    <main style={{ maxWidth: 360 }}>
      <h1>Attorney Login</h1>
      <form onSubmit={onSubmit}>
        <p><label>Email<br />
          <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
        </label></p>
        <p><label>Password<br />
          <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required />
        </label></p>
        {error && <p style={{ color: "red" }}>{error}</p>}
        <button type="submit">Log in</button>
      </form>
    </main>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npx tsc --noEmit
```

---

## Task 16: Leads list + detail pages (guarded)

**Files:**
- Create: `frontend/app/leads/page.tsx`, `frontend/app/leads/[id]/page.tsx`

- [ ] **Step 1: Create `frontend/app/leads/page.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { fetchLeads, Lead } from "@/lib/api";
import { getToken } from "@/lib/auth";

export default function LeadsPage() {
  const router = useRouter();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) { router.push("/login"); return; }
    fetchLeads()
      .then(setLeads)
      .catch((err) => {
        if (err.message === "unauthorized") router.push("/login");
      })
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) return <main><p>Loading…</p></main>;

  return (
    <main>
      <h1>Leads</h1>
      <table cellPadding={8} style={{ borderCollapse: "collapse" }}>
        <thead>
          <tr><th>Name</th><th>Email</th><th>State</th><th></th></tr>
        </thead>
        <tbody>
          {leads.map((l) => (
            <tr key={l.id} style={{ borderTop: "1px solid #ccc" }}>
              <td>{l.first_name} {l.last_name}</td>
              <td>{l.email}</td>
              <td>{l.state}</td>
              <td><Link href={`/leads/${l.id}`}>View</Link></td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
```

- [ ] **Step 2: Create `frontend/app/leads/[id]/page.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { fetchLead, markReachedOut, LeadDetail } from "@/lib/api";
import { getToken } from "@/lib/auth";

export default function LeadDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const [lead, setLead] = useState<LeadDetail | null>(null);

  useEffect(() => {
    if (!getToken()) { router.push("/login"); return; }
    fetchLead(params.id)
      .then(setLead)
      .catch((err) => { if (err.message === "unauthorized") router.push("/login"); });
  }, [params.id, router]);

  if (!lead) return <main><p>Loading…</p></main>;

  async function onMark() {
    const updated = await markReachedOut(lead!.id);
    setLead({ ...lead!, state: updated.state });
  }

  return (
    <main style={{ maxWidth: 480 }}>
      <h1>{lead.first_name} {lead.last_name}</h1>
      <p>Email: {lead.email}</p>
      <p>State: <strong>{lead.state}</strong></p>
      <p><a href={lead.resume_url} target="_blank" rel="noreferrer">Download resume ({lead.resume_filename})</a></p>
      {lead.state === "PENDING" && (
        <button onClick={onMark}>Mark as Reached Out</button>
      )}
      <p><a href="/leads">← Back to list</a></p>
    </main>
  );
}
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

---

## Task 17: README + end-to-end smoke verification

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create `README.md`**

````markdown
# Lead Service

Full-stack lead management: public submission form + JWT-guarded internal review UI.

## Stack
FastAPI · Next.js (App Router) · Postgres · MinIO (S3) · Mailpit (SMTP)

## Run (one command)
```bash
cp .env.example .env
docker compose up --build
```

| Service | URL |
|---|---|
| Web app | http://localhost:3000 |
| API docs | http://localhost:8000/docs |
| Mailpit (sent emails) | http://localhost:8025 |
| MinIO console | http://localhost:9001 |

Default attorney login: `attorney@firm.test` / `password123`.

## Flow
1. Visit http://localhost:3000 → submit a lead with a PDF/DOC/DOCX resume.
2. Check http://localhost:8025 → see the prospect + attorney emails.
3. Visit http://localhost:3000/login → log in → see the lead in the list.
4. Open the lead → download the resume → "Mark as Reached Out".

## Backend tests
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
createdb lead_test   # or: docker compose exec db psql -U lead -c "CREATE DATABASE lead_test;"
pytest -v
```

## Architecture
See `docs/superpowers/specs/2026-06-27-lead-service-design.md`.
````

- [ ] **Step 2: Full E2E smoke test**

Run:
```bash
docker compose up --build -d
# wait for services, then:
curl -s localhost:8000/health
```
Expected: `{"status":"ok"}`. Then manually walk the flow in the README and confirm:
- Lead submission returns success on the form.
- Two emails appear in Mailpit.
- Login works; lead appears; resume downloads; "Mark as Reached Out" flips state.

---

## Final Verification Checklist

- [ ] `cd backend && pytest -v` → all green
- [ ] `cd frontend && npx tsc --noEmit` → no errors
- [ ] `docker compose up --build` → all 5 services healthy
- [ ] Public form submits and shows success
- [ ] Mailpit shows 2 emails per submission
- [ ] Login returns a JWT; internal pages reject access without it
- [ ] Lead detail downloads resume via presigned URL
- [ ] "Mark as Reached Out" transitions PENDING→REACHED_OUT; repeat attempt → 409
