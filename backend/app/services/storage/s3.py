from __future__ import annotations

import hashlib
import os
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings
from app.services.storage.base import StorageService, StoredFile


class S3StorageService(StorageService):
    def __init__(self) -> None:
        try:
            import boto3  # type: ignore
        except Exception as exc:
            raise RuntimeError("S3 storage requires boto3 package installed") from exc

        self._bucket = settings.s3_bucket
        self._prefix = settings.s3_prefix.strip("/")
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id or None,
            aws_secret_access_key=settings.s3_secret_access_key or None,
        )

    def save_upload(self, source: BinaryIO, filename: str) -> StoredFile:
        suffix = Path(filename or "upload.bin").suffix
        key = f"{self._prefix}/{uuid.uuid4()}{suffix}" if self._prefix else f"{uuid.uuid4()}{suffix}"

        hasher = hashlib.sha256()
        total = 0
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                hasher.update(chunk)
                tmp.write(chunk)

        try:
            self._client.upload_file(tmp_path, self._bucket, key)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        return StoredFile(storage_path=f"s3://{self._bucket}/{key}", size_bytes=total, sha256=hasher.hexdigest())

    def delete(self, storage_path: str) -> None:
        if not storage_path.startswith("s3://"):
            return
        _, _, rest = storage_path.partition("s3://")
        bucket, _, key = rest.partition("/")
        if not bucket or not key:
            return
        self._client.delete_object(Bucket=bucket, Key=key)

    @contextmanager
    def local_path(self, storage_path: str):
        if not storage_path.startswith("s3://"):
            raise RuntimeError("Expected s3:// path for S3 storage backend")
        _, _, rest = storage_path.partition("s3://")
        bucket, _, key = rest.partition("/")
        if not bucket or not key:
            raise RuntimeError("Malformed S3 storage path")

        fd, tmp_path = tempfile.mkstemp(prefix="ecopilot_s3_", suffix=Path(key).suffix)
        os.close(fd)
        try:
            self._client.download_file(bucket, key, tmp_path)
            yield tmp_path
        finally:
            Path(tmp_path).unlink(missing_ok=True)
