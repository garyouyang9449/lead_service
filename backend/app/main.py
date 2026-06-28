import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, leads
from app.core.config import settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from app.api.deps import get_db, get_storage

        provider = app.dependency_overrides.get(get_storage, get_storage)
        try:
            provider().ensure_bucket()
        except Exception:  # pragma: no cover - non-fatal at startup
            logger.exception("Failed to ensure storage bucket on startup")

        # Seed the default attorney so the app is usable out of the box.
        # Skipped when get_db is overridden (tests manage their own users).
        if get_db not in app.dependency_overrides:
            from app.db.session import SessionLocal
            from app.services.auth import seed_attorney

            db = SessionLocal()
            try:
                user = seed_attorney(
                    db,
                    settings.default_attorney_email,
                    settings.default_attorney_password,
                )
                logger.info("Default attorney account ready: %s", user.email)
            except Exception:  # pragma: no cover - non-fatal at startup
                logger.exception("Failed to seed default attorney on startup")
            finally:
                db.close()

        yield

    app = FastAPI(title="Lead Service", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(leads.router)

    return app


app = create_app()
