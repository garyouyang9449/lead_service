# Coding-Agent Usage

## Tools
- **OpenCode** running **Claude** as the coding agent, driven by a skills/plan-based workflow ("superpowers"): brainstorm → written design spec → locked task-by-task plan → TDD execution → review.
- Local infra via Docker Compose (Postgres, MinIO, Mailpit) so the agent could write and run real integration code.

## What I delegated vs. wrote myself
I delegated **almost all code authoring** to the agent and kept myself in the **director/reviewer** seat — this is where agents are strongest and where I add the most value.

**Delegated to the agent:**
- The system design and the implementation plan.
- The entire backend (FastAPI service-layer code, SQLAlchemy models, Alembic migration, JWT cookie auth, S3/MinIO storage, SMTP email) — written test-first with pytest.
- The Next.js frontend (public form, login, guarded leads list/detail, API client).
- Docker Compose, Dockerfiles, `.env.example`, and the docs (design doc, README).

**Wrote / owned myself:**
- Requirements, scope, and tech choices (Postgres over SQLite, httpOnly cookie over localStorage, what's out of scope).
- Commit boundaries and messages; accepting/rejecting agent output.
- Review prompts and verification gates.

## One place the agent produced subtly bad code — and the fix
The agent's `LeadCreate` schema typed the public form fields as plain `str`:

```python
class LeadCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
```

The frontend validated non-empty names, so manual testing looked fine. But the **public** `POST /api/leads` endpoint would happily accept blank or whitespace-only `first_name`/`last_name` so a server-side validation gap was needed.

**Prompt examples**

> **Me:** based on this codebase, check past commits, check the spec below and see if all the requirements are implemented: [functional + tech requirements]
>
> **Agent:** Mapped every requirement to its implementation with `file:line` evidence, ran the suite (**72 passed**) and `next build` (success), and flagged gaps: the design doc had been accidentally deleted in commit `82e9a68`; `LeadCreate` accepts blank names; email failures are silently swallowed.