# Lead Service — Design Document

**Date:** 2026-06-27
**Status:** Approved

## 1. Purpose

A web application that lets prospects publicly submit a lead (a job-application-style form) and lets attorneys inside the company review and act on those leads behind authentication.

## 2. Functional Requirements

1. A **public** lead form collects: `first_name`, `last_name`, `email`, and a `resume`/CV file. No auth.
2. On submission, the system sends **two emails**: a confirmation to the prospect and a notification to an attorney.
3. An **internal, authenticated UI** lists all leads with every field the prospect filled in.
4. Each lead has a **state**: starts `PENDING`, transitions to `REACHED_OUT` when an attorney manually marks it after reaching out.

## 3. Non-Functional Requirements

- Production-shaped repo structure; clean separation of concerns.
- Runs locally with a single `docker-compose up`; no external accounts/credentials required.
- Automated backend tests (pytest) covering core paths.
- APIs in **FastAPI**; web app in **Next.js** (App Router).

## 4. Architecture

Five services orchestrated by `docker-compose`:

| Service | Tech | Responsibility |
|---|---|---|
| `api` | FastAPI (Python 3.12) | Public + internal REST APIs, business logic |
| `web` | Next.js (App Router, TypeScript) | Public lead form + internal leads UI |
| `db` | Postgres 16 + SQLAlchemy 2.x + Alembic | Persist leads and users |
| `storage` | MinIO (S3-compatible, accessed via boto3) | Store resume files |
| `mail` | Mailpit (SMTP sink + web UI) | Capture and view sent emails |

### Why these choices
- **Postgres over SQLite:** production-realistic, matches docker-compose deployment shape.
- **MinIO over local disk / DB BLOB:** S3 API is production-realistic and swappable for real S3; DB stores only the object key.
- **Mailpit over a real provider:** realistic SMTP integration with zero external accounts; viewable in a browser.
- **JWT (DB users) over Basic/static token:** real login flow, self-contained, demonstrates auth properly.

### Request flow — lead submission
```
Prospect (web /) 
  → POST /api/leads (multipart)
    → validate fields + file (type, size)
    → upload resume to MinIO (key: leads/{uuid}/{filename})
    → insert lead row (state=PENDING)
    → schedule background task: send prospect email + attorney email via SMTP→Mailpit
  ← 201 Created (lead JSON)
```

### Request flow — internal review
```
Attorney (web /login) → POST /api/auth/login → JWT (returned in body)
  → web stores JWT in localStorage
Attorney (web /leads) → GET /api/leads  (Authorization: Bearer <jwt>)
  → list of leads
Attorney (web /leads/[id]) → GET /api/leads/{id}
  → lead detail + presigned resume download URL
Attorney clicks "Mark as Reached Out"
  → PATCH /api/leads/{id} {state: REACHED_OUT}
    → validate transition (PENDING → REACHED_OUT only) else 409
  ← updated lead
```

## 5. Data Model

### `leads`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `first_name` | text | required |
| `last_name` | text | required |
| `email` | text | required, format-validated |
| `resume_key` | text | S3 object key |
| `resume_filename` | text | original filename (for download) |
| `state` | enum(`PENDING`,`REACHED_OUT`) | default `PENDING` |
| `created_at` | timestamptz | default now |
| `updated_at` | timestamptz | auto-update |

### `users` (attorneys)
| Column | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `email` | text | unique |
| `hashed_password` | text | passlib/bcrypt |
| `created_at` | timestamptz | default now |

Seeded on startup with `DEFAULT_ATTORNEY_EMAIL` / `DEFAULT_ATTORNEY_PASSWORD`.

## 6. API Surface

### Public
- `POST /api/leads` — multipart form (`first_name`, `last_name`, `email`, `resume`). Returns `201` with lead JSON.

### Auth
- `POST /api/auth/login` — JSON `{email, password}` → `200 {access_token, token_type}`. Invalid → `401`.
- `GET /api/auth/me` — Bearer token → current user. Invalid/expired → `401`.

### Internal (JWT Bearer required)
- `GET /api/leads` — list leads (paginated: `limit`, `offset`).
- `GET /api/leads/{id}` — lead detail + `resume_url` (presigned). Missing → `404`.
- `PATCH /api/leads/{id}` — body `{state}`. Valid transition `PENDING→REACHED_OUT` else `409`.

### Ops
- `GET /health` — liveness/readiness.

## 7. Authentication

- **Mechanism:** JWT (HS256), signed with `JWT_SECRET`, expiry `JWT_EXPIRE_MINUTES`.
- **Storage (frontend):** `localStorage`; attached as `Authorization: Bearer <token>` by the API client.
- **Guard:** FastAPI dependency `get_current_user` decodes/validates the token; rejects expired/invalid with `401`.
- **Route guard (web):** internal pages redirect to `/login` when no/invalid token.

## 8. File Upload Rules

- Allowed types: `pdf`, `doc`, `docx` (by extension + content-type check).
- Max size: 5 MB (configurable via `MAX_RESUME_MB`).
- Violations → `422` with a clear message.

## 9. Email

- `EmailService` abstraction sends via SMTP (Mailpit host/port from env).
- Two messages on submission:
  - **Prospect:** confirmation that the application was received.
  - **Attorney:** notification with the prospect's details (recipient = `ATTORNEY_EMAIL`).
- Sent in a FastAPI background task. Failures are logged and do **not** roll back the lead or fail the request.

## 10. Frontend Pages (Next.js App Router)

- `/` — public lead form (file upload, client+server validation, success/error states).
- `/login` — attorney login form → stores JWT.
- `/leads` — guarded list of leads.
- `/leads/[id]` — guarded detail: all fields, resume download, "Mark as Reached Out" button.

## 11. Repository Structure

```
backend/
  app/
    main.py                # FastAPI app, router includes, startup seed, /health
    core/
      config.py            # pydantic-settings
      security.py          # password hashing + JWT encode/decode
      logging.py           # structured logging setup
    api/
      deps.py              # get_db, get_current_user
      routes/
        leads.py
        auth.py
    models/                # SQLAlchemy: lead.py, user.py
    schemas/               # Pydantic: lead.py, auth.py
    services/
      storage.py           # MinIO/S3 via boto3
      email.py             # SMTP send
      leads.py             # lead business logic + state machine
      auth.py              # authenticate user, create token
    db/
      base.py, session.py
  alembic/                 # migrations
  tests/
    conftest.py
    test_leads_api.py
    test_auth_api.py
    test_leads_service.py
    test_storage.py
  Dockerfile
  pyproject.toml
frontend/
  app/
    layout.tsx
    page.tsx               # public form
    login/page.tsx
    leads/page.tsx
    leads/[id]/page.tsx
  components/
  lib/
    api.ts                 # fetch client w/ Bearer
    auth.ts                # token helpers + guard
  Dockerfile
  package.json
docker-compose.yml
.env.example
README.md
```

## 12. Testing Strategy

- **Backend (pytest):**
  - Lead create: happy path (mocks storage + email), file-validation errors.
  - State transition: valid `PENDING→REACHED_OUT`; invalid → `409`.
  - Auth: login success/failure; protected route without token → `401`, with token → `200`.
  - Storage service: upload + presigned URL (against a test bucket or mocked boto3).
- **Frontend:** light — form validation logic only.

## 13. Error Handling

- Consistent JSON error envelope: `{ "detail": <message> }` (FastAPI default, extended where needed).
- `422` validation, `401` auth, `404` not found, `409` invalid transition.
- Email/storage failures logged with context; email failure non-fatal.

## 14. Out of Scope (YAGNI)

- Real cloud deployment / IaC / CI.
- Lead editing/deletion, multi-role permissions, password reset.
- Full E2E browser tests.
- Pagination UI beyond simple limit/offset.
