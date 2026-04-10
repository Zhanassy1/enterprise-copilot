from __future__ import annotations

import hashlib
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings
from app.core.upload_limits import MAX_UPLOAD_BYTES, UploadTooLargeError
from app.services.storage.base import StorageService, StoredFile


class LocalStorageService(StorageService):
    def __init__(self, upload_dir: str | None = None) -> None:
        self._upload_dir = Path(upload_dir or settings.upload_dir)
        self._upload_dir.mkdir(parents=True, exist_ok=True)

    def save_upload(self, source: BinaryIO, filename: str) -> StoredFile:
        suffix = Path(filename or "upload.bin").suffix
        safe_name = f"{uuid.uuid4()}{suffix}"
        target = self._upload_dir / safe_name

        hasher = hashlib.sha256()
        total = 0
        try:
            with target.open("wb") as out:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_UPLOAD_BYTES:
                        raise UploadTooLargeError()
                    hasher.update(chunk)
                    out.write(chunk)
        except UploadTooLargeError:
            target.unlink(missing_ok=True)
            raise

        return StoredFile(
            storage_key=str(target).replace("\\", "/"),
            size_bytes=total,
            sha256=hasher.hexdigest(),
        )

    def delete(self, storage_key: str) -> None:
        Path(storage_key).unlink(missing_ok=True)

    @contextmanager
    def local_path(self, storage_key: str):
        yield storage_key
