# Lead Service — Design Document

**Status:** Implemented

## 1. Purpose

A web application that lets prospects **publicly** submit a lead (a job-application-style form) and lets attorneys inside the company review and act on those leads behind authentication.

## 2. Functional Requirements

1. A **public** lead form collects: `first_name`, `last_name`, `email`, and a `resume`/CV file. No auth.
2. On submission, the system sends **two emails**: a confirmation to the prospect and a notification to an attorney.
3. An **internal, authenticated UI** lists all leads with every field the prospect filled in.
4. Each lead has a **state**: starts `PENDING`, transitions to `REACHED_OUT` when an attorney manually marks it after reaching out.

## 3. Non-Functional Requirements

- Production-shaped repo structure; clean separation of concerns.
- Runs locally with a single `docker compose up`; no external accounts/credentials required.
- Automated backend tests (pytest) covering core paths.
- APIs in **FastAPI**; web app in **Next.js** (App Router).

## 4. Architecture

Five services orchestrated by `docker-compose`:

| Service | Tech | Responsibility |
|---|---|---|
| `web` | Next.js (App Router, TypeScript) | Public lead form + internal leads UI |
| `api` | FastAPI (Python 3.12) | Public + internal REST APIs, business logic |
| `db` | Postgres 16 + SQLAlchemy 2.x + Alembic | Persist leads and users |
| `storage` | MinIO (S3-compatible, accessed via boto3) | Store resume files |
| `mail` | Mailpit (SMTP sink + web UI) | Capture and view sent emails |

```
                 ┌─────────────┐
   Prospect ───▶ │             │           ┌──────────┐
                 │   web       │           │   db     │  leads, users
   Attorney ───▶ │  (Next.js)  │           │ (Postgres)│
                 └──────┬──────┘           └────▲─────┘
                        │ HTTP (cookies)        │ SQLAlchemy
                        ▼                       │
                 ┌─────────────┐  boto3   ┌─────┴─────┐
                 │   api       │────────▶ │  storage  │  resume files
                 │ (FastAPI)   │          │  (MinIO)  │
                 └──────┬──────┘          └───────────┘
                        │ SMTP
                        ▼
                 ┌─────────────┐
                 │   mail      │  prospect + attorney emails
                 │  (Mailpit)  │
                 └─────────────┘
```

### Why these choices
- **Postgres over SQLite:** production-realistic, matches the docker-compose deployment shape. (Tests use in-memory SQLite for speed/isolation.)
- **MinIO over local disk / DB BLOB:** the S3 API is production-realistic and swappable for real S3; the DB stores only the object key.
- **Mailpit over a real provider:** realistic SMTP integration with zero external accounts; sent mail is viewable in a browser at `http://localhost:8025`.
- **JWT + DB users over Basic/static token:** a real login flow, self-contained, demonstrates auth properly.
- **httpOnly cookie over localStorage token:** the JWT is set as an `httpOnly` cookie by the API so it is not readable from JavaScript (mitigates token theft via XSS).

### Request flow — lead submission
```
Prospect (web /)
  → POST /api/leads (multipart: first_name, last_name, email, resume)
    → validate fields + file (extension, content-type, size)
    → upload resume to MinIO (key: leads/{uuid}/{filename})
    → insert lead row (state=PENDING)
    → schedule background tasks: send prospect email + attorney email via SMTP → Mailpit
  ← 201 Created (lead JSON)
```

### Request flow — internal review
```
Attorney (web /login) → POST /api/auth/login {email, password}
  → on success, API sets httpOnly cookie `access_token` (JWT) and returns the user
  → web derives auth state via GET /api/auth/me (cookie sent with credentials: "include")
Attorney (web /leads)       → GET  /api/leads          → list of leads
Attorney (web /leads/[id])  → GET  /api/leads/{id}     → lead detail + presigned resume URL
Attorney clicks "Mark as Reached Out"
  → PATCH /api/leads/{id} {state: REACHED_OUT}
    → validate transition (PENDING → REACHED_OUT only), else 409
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
| `hashed_password` | text | bcrypt |
| `created_at` | timestamptz | default now |

A default attorney is seeded on startup from `DEFAULT_ATTORNEY_EMAIL` / `DEFAULT_ATTORNEY_PASSWORD` (idempotent).

## 6. API Surface

### Public
- `POST /api/leads` — multipart form (`first_name`, `last_name`, `email`, `resume`). Returns `201` with lead JSON.

### Auth
- `POST /api/auth/login` — JSON `{email, password}`. On success sets an `httpOnly` `access_token` cookie and returns the user `{id, email}`. Invalid → `401`.
- `POST /api/auth/logout` — clears the auth cookie.
- `GET /api/auth/me` — returns the current user from the cookie (or `Authorization: Bearer` fallback). Invalid/expired → `401`.

### Internal (authentication required)
- `GET /api/leads` — list leads (paginated: `limit`, `offset`).
- `GET /api/leads/{id}` — lead detail + `resume_url` (presigned download). Missing → `404`.
- `PATCH /api/leads/{id}` — body `{state}`. Valid transition `PENDING → REACHED_OUT` only, else `409`.

### Ops
- `GET /health` — liveness/readiness.

## 7. Authentication

- **Mechanism:** JWT (HS256), signed with `JWT_SECRET`, expiry `JWT_EXPIRE_MINUTES`.
- **Transport/storage:** the API sets the JWT in an `httpOnly`, `SameSite`-scoped cookie (`COOKIE_NAME`, `COOKIE_SECURE`, `COOKIE_SAMESITE`). The browser cannot read it; the web client sends it automatically via `credentials: "include"`.
- **Bearer fallback:** for curl/tests, `Authorization: Bearer <jwt>` is also accepted.
- **Guard (API):** the FastAPI dependency `get_current_user` extracts the token (cookie first, then Bearer), decodes/validates it, and rejects expired/invalid with `401`.
- **Guard (web):** internal pages use a `useRequireAuth` hook that calls `GET /api/auth/me` and redirects to `/login` when unauthenticated.
- **CORS:** `FRONTEND_ORIGIN` must be an explicit origin (not `*`) because credentialed requests carry the cookie.

## 8. File Upload Rules

- Allowed types: `pdf`, `doc`, `docx` (validated by extension **and** content-type; `application/octet-stream` is tolerated when the extension is valid).
- Max size: 5 MB (configurable via `MAX_RESUME_MB`).
- Violations → `422` with a clear message.

## 9. Email

- An `EmailService` abstraction sends via SMTP (Mailpit host/port from env).
- Two messages on submission:
  - **Prospect:** confirmation that the application was received.
  - **Attorney:** notification with the prospect's details (recipient = `ATTORNEY_EMAIL`).
- Sent in FastAPI **background tasks**. Failures are logged and do **not** roll back the lead or fail the request.

## 10. Frontend Pages (Next.js App Router)

- `/` — public lead form (file upload, client + server validation, success/error states).
- `/login` — attorney login form → sets the auth cookie.
- `/leads` — guarded list of leads.
- `/leads/[id]` — guarded detail: all fields, resume download, "Mark as Reached Out" button.

## 11. Repository Structure

```
backend/
  app/
    main.py                # FastAPI app, router includes, startup seed + bucket, /health
    core/
      config.py            # pydantic-settings
      security.py          # password hashing + JWT encode/decode
      logging.py           # logging setup
    api/
      deps.py              # get_db, get_current_user, get_storage, get_email
      routes/
        leads.py
        auth.py
    models/                # SQLAlchemy: lead.py, user.py
    schemas/               # Pydantic: lead.py, auth.py
    services/
      storage.py           # MinIO/S3 via boto3
      email.py             # SMTP send + templates
      leads.py             # lead business logic + state machine
      auth.py              # authenticate user, seed attorney
    db/
      base.py, session.py, types.py
  alembic/                 # migrations
  tests/                   # pytest (in-memory SQLite + fakes)
  Dockerfile
  pyproject.toml
frontend/
  app/
    layout.tsx
    page.tsx               # public form
    login/page.tsx
    leads/page.tsx
    leads/[id]/page.tsx
  components/              # LeadForm, StateBadge
  lib/
    api.ts                 # fetch client (credentials: include)
    auth.ts                # auth state + route guard
    validation.ts          # client-side form validation
  Dockerfile
  package.json
docs/
  design.md
docker-compose.yml
.env.example
README.md
```

## 12. Testing Strategy

- **Backend (pytest):** in-memory SQLite + fake storage/email (no external services).
  - Lead create: happy path, file-validation errors.
  - State transition: valid `PENDING → REACHED_OUT`; invalid → `409`.
  - Auth: login success/failure; protected route without token → `401`, with token → `200`; cookie + Bearer paths.
  - Storage service, security (JWT), models, email templates, health.
- **Frontend:** form-validation unit tests (`lib/validation.test.ts`).

## 13. Error Handling

- Consistent JSON error envelope: `{ "detail": <message> }`.
- `422` validation, `401` auth, `404` not found, `409` invalid transition.
- Email/storage failures logged with context; email failure is non-fatal.

## 14. Out of Scope (YAGNI)

- Real cloud deployment / IaC / CI.
- Lead editing/deletion, multi-role permissions, password reset.
- Full E2E browser tests.
- Pagination UI beyond simple limit/offset.
