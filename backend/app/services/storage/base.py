from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from typing import BinaryIO


@dataclass
class StoredFile:
    storage_path: str
    size_bytes: int
    sha256: str


class StorageService(ABC):
    @abstractmethod
    def save_upload(self, source: BinaryIO, filename: str) -> StoredFile:
        raise NotImplementedError

    @abstractmethod
    def delete(self, storage_path: str) -> None:
        raise NotImplementedError

    @abstractmethod
    @contextmanager
    def local_path(self, storage_path: str):
        raise NotImplementedError
