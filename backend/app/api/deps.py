from __future__ import annotations

from functools import lru_cache

from app.db.session import get_db  # re-exported for route dependencies  # noqa: F401
from app.services.storage import StorageService, build_storage


@lru_cache(maxsize=1)
def _storage_singleton() -> StorageService:
    return build_storage()


def get_storage() -> StorageService:
    return _storage_singleton()
