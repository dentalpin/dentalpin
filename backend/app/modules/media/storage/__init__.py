"""Storage backend factory."""

import tempfile
from functools import lru_cache

from app.config import settings

from .base import StorageBackend
from .local import LocalStorageBackend

__all__ = ["StorageBackend", "get_storage_backend"]

# For testing, use a temp directory
_test_storage_path: str | None = None


def set_test_storage_path(path: str | None) -> None:
    """Set storage path for tests (clears cache)."""
    global _test_storage_path
    _test_storage_path = path
    get_storage_backend.cache_clear()


@lru_cache
def get_storage_backend() -> StorageBackend:
    """Get configured storage backend (singleton).

    Returns:
        StorageBackend instance based on STORAGE_BACKEND setting
    """
    backend = settings.STORAGE_BACKEND

    if backend == "local":
        # Use test path if set, otherwise use configured path
        if settings.TESTING and _test_storage_path is None:
            # Auto-create temp directory for tests
            path = tempfile.mkdtemp(prefix="dentalpin_test_storage_")
            return LocalStorageBackend(path)
        path = _test_storage_path or settings.STORAGE_LOCAL_PATH
        return LocalStorageBackend(path)

    if backend == "s3":
        if not settings.STORAGE_S3_BUCKET:
            raise ValueError("STORAGE_BACKEND=s3 requires STORAGE_S3_BUCKET to be set")
        from .s3 import S3StorageBackend

        return S3StorageBackend(
            bucket=settings.STORAGE_S3_BUCKET,
            region=settings.STORAGE_S3_REGION,
            endpoint_url=settings.STORAGE_S3_ENDPOINT_URL,
            access_key_id=settings.STORAGE_S3_ACCESS_KEY_ID,
            secret_access_key=settings.STORAGE_S3_SECRET_ACCESS_KEY,
        )

    raise ValueError(f"Unknown storage backend: {backend}")
