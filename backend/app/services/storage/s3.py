from __future__ import annotations

import hashlib
import os
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote

from starlette.responses import StreamingResponse

from app.core.config import settings
from app.core.upload_limits import MAX_UPLOAD_BYTES, UploadTooLargeError
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
        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp_path = tmp.name
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_UPLOAD_BYTES:
                        raise UploadTooLargeError()
                    hasher.update(chunk)
                    tmp.write(chunk)

            self._client.upload_file(tmp_path, self._bucket, key)
        except UploadTooLargeError:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)
            raise
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)

        return StoredFile(storage_key=f"s3://{self._bucket}/{key}", size_bytes=total, sha256=hasher.hexdigest())

    def delete(self, storage_key: str) -> None:
        if not storage_key.startswith("s3://"):
            return
        _, _, rest = storage_key.partition("s3://")
        bucket, _, key = rest.partition("/")
        if not bucket or not key:
            return
        self._client.delete_object(Bucket=bucket, Key=key)

    def presigned_get_url(self, storage_key: str, *, expires_seconds: int = 3600) -> str | None:
        if not storage_key.startswith("s3://"):
            return None
        _, _, rest = storage_key.partition("s3://")
        bucket, _, key = rest.partition("/")
        if not bucket or not key:
            return None
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=int(expires_seconds),
        )

    @contextmanager
    def local_path(self, storage_key: str):
        if not storage_key.startswith("s3://"):
            raise RuntimeError("Expected s3:// path for S3 storage backend")
        _, _, rest = storage_key.partition("s3://")
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

    def _attachment_disposition_header(self, filename: str) -> str:
        if all(ord(c) < 128 for c in filename) and '"' not in filename and "\r" not in filename:
            return f'attachment; filename="{filename}"'
        return f"attachment; filename*=UTF-8''{quote(filename, safe='')}"

    def direct_download_response(
        self, storage_key: str, *, filename: str, content_type: str | None
    ) -> StreamingResponse:
        if not storage_key.startswith("s3://"):
            raise RuntimeError("Expected s3:// path for S3 storage backend")
        _, _, rest = storage_key.partition("s3://")
        bucket, _, key = rest.partition("/")
        if not bucket or not key:
            raise RuntimeError("Malformed S3 storage path")

        obj = self._client.get_object(Bucket=bucket, Key=key)
        body = obj["Body"]
        media_type = content_type or "application/octet-stream"
        headers: dict[str, str] = {"Content-Disposition": self._attachment_disposition_header(filename)}
        clen = obj.get("ContentLength")
        if clen is not None:
            headers["Content-Length"] = str(int(clen))

        def iter_body():
            try:
                yield from body.iter_chunks(chunk_size=1024 * 1024)
            finally:
                body.close()

        return StreamingResponse(iter_body(), media_type=media_type, headers=headers)
