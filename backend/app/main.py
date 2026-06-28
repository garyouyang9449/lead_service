import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import leads
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from app.api.deps import get_storage

        provider = app.dependency_overrides.get(get_storage, get_storage)
        try:
            provider().ensure_bucket()
        except Exception:  # pragma: no cover - non-fatal at startup
            logger.exception("Failed to ensure storage bucket on startup")
        yield

    app = FastAPI(title="Lead Service", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(leads.router)

    return app


app = create_app()
