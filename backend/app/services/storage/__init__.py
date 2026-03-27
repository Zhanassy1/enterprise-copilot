from functools import lru_cache

from app.core.config import settings
from app.services.storage.base import StorageService
from app.services.storage.local import LocalStorageService
from app.services.storage.s3 import S3StorageService


@lru_cache(maxsize=1)
def get_storage_service() -> StorageService:
    backend = settings.storage_backend.lower().strip()
    if backend == "s3":
        return S3StorageService()
    return LocalStorageService()
