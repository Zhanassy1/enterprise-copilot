from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from typing import BinaryIO

from starlette.responses import Response


@dataclass
class StoredFile:
    storage_key: str
    size_bytes: int
    sha256: str


class StorageService(ABC):
    @abstractmethod
    def save_upload(self, source: BinaryIO, filename: str) -> StoredFile:
        raise NotImplementedError

    @abstractmethod
    def delete(self, storage_key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    @contextmanager
    def local_path(self, storage_key: str):
        raise NotImplementedError

    @abstractmethod
    def direct_download_response(
        self, storage_key: str, *, filename: str, content_type: str | None
    ) -> Response:
        """Serve bytes when presigned URL is unavailable. Must not buffer the entire object in RAM."""
        ...

    def presigned_get_url(self, storage_key: str, *, expires_seconds: int = 3600) -> str | None:
        """Return a time-limited download URL, or None if not supported (e.g. local dev)."""
        return None
