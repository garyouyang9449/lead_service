from __future__ import annotations

from functools import lru_cache

from app.db.session import get_db  # re-exported for route dependencies  # noqa: F401
from app.services.email import EmailService, build_email
from app.services.storage import StorageService, build_storage


@lru_cache(maxsize=1)
def _storage_singleton() -> StorageService:
    return build_storage()


def get_storage() -> StorageService:
    return _storage_singleton()


@lru_cache(maxsize=1)
def _email_singleton() -> EmailService:
    return build_email()


def get_email() -> EmailService:
    return _email_singleton()
