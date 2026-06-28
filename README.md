# Lead Service

A web application for creating, listing, and updating **leads**.

- A **public** form lets prospects submit their `first_name`, `last_name`, `email`, and a `resume`/CV file.
- On submission, the system emails **both** the prospect (confirmation) and an attorney (notification).
- An **authenticated internal UI** lets attorneys review all leads and mark a lead as **REACHED_OUT** (each lead starts as **PENDING**).

Stack: **FastAPI** (API) · **Next.js** App Router (web) · **Postgres** (data) · **MinIO** (resume storage) · **Mailpit** (email).

See [`docs/design.md`](docs/design.md) for the full system design.

---

## Quick start (Docker — recommended)

This is the easiest way to run everything end-to-end. Requires **Docker** + **Docker Compose**.

```bash
# 1. From the repo root, create your env file
cp .env.example .env

# 2. Build and start all services
docker compose up --build
```

Once everything is healthy, open:

| URL | What |
|---|---|
| http://localhost:3000 | **Public lead form** (prospect) |
| http://localhost:3000/login | **Internal UI** (attorney sign-in) |
| http://localhost:8000/docs | API docs (Swagger UI) |
| http://localhost:8025 | **Mailpit** — view sent emails |
| http://localhost:9001 | MinIO console (`minioadmin` / `minioadmin`) |

Database migrations run automatically on API startup (`alembic upgrade head`), and a default attorney account is seeded.

**Default attorney login:**
- Email: `attorney@firm.com`
- Password: `password123`

---

## Try it end-to-end

1. **Submit a lead** — go to http://localhost:3000, fill in the form, attach a `.pdf`/`.doc`/`.docx` (≤ 5 MB), and submit.
2. **Check the emails** — open http://localhost:8025 (Mailpit). You should see **two** emails: one to the prospect and one to the attorney (`attorney@firm.com`).
3. **Sign in to the internal UI** — go to http://localhost:3000/login and sign in with the default attorney credentials.
4. **Review the lead** — the new lead appears in the list with state **PENDING**. Click **View** to see all fields and download the resume.
5. **Advance the state** — click **Mark as Reached Out**. The state changes to **REACHED_OUT** (the action is then disabled).

---

## Running the tests

### Backend (pytest)

The backend tests use an **in-memory SQLite** database with fake storage/email, so **no Docker services are required**.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest
```

### Frontend (vitest)

```bash
cd frontend
npm install
npm test
```

---

## Local development without Docker (optional)

You still need Postgres, MinIO, and an SMTP sink. The simplest path is to run only those infra services in Docker and run the apps on the host:

```bash
# Start just the infrastructure
docker compose up db storage mail
```

Then point the apps at `localhost` (the committed `.env` uses Docker hostnames like `db`, `storage`, `mail`, so override these for host-based runs):

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

export DATABASE_URL="postgresql+psycopg://lead:lead@localhost:5432/lead"
export SMTP_HOST=localhost
export S3_ENDPOINT_URL=http://localhost:9000

alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
# point the web app at the API
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Open http://localhost:3000.

---

## Configuration

All configuration is via environment variables (see [`.env.example`](.env.example)). Key ones:

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | Postgres connection string | `...@db:5432/lead` |
| `JWT_SECRET` | Signs auth tokens — **change in prod** | `change-me-in-prod` |
| `DEFAULT_ATTORNEY_EMAIL` / `DEFAULT_ATTORNEY_PASSWORD` | Seeded login | `attorney@firm.com` / `password123` |
| `ATTORNEY_EMAIL` | Recipient of new-lead notifications | `attorney@firm.com` |
| `SMTP_HOST` / `SMTP_PORT` | Email (Mailpit) | `mail` / `1025` |
| `S3_ENDPOINT_URL` / `S3_BUCKET` | Resume storage (MinIO) | `http://storage:9000` / `resumes` |
| `MAX_RESUME_MB` | Max resume size | `5` |
| `FRONTEND_ORIGIN` | CORS origin (must be explicit, not `*`) | `http://localhost:3000` |
| `NEXT_PUBLIC_API_URL` | API base URL used by the web app | `http://localhost:8000` |

---

## Project layout

```
backend/    FastAPI app (api/core/db/models/schemas/services), Alembic migrations, pytest
frontend/   Next.js App Router app (pages, components, lib), vitest
docs/       design.md — system design
docker-compose.yml   db + storage + mail + api + web
.env.example
```