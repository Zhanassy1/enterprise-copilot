import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from app.services.storage.local import LocalStorageService


class StorageServiceTests(unittest.TestCase):
    def test_save_upload_roundtrip_local_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            svc = LocalStorageService(upload_dir=d)
            data = b"hello world"
            out = svc.save_upload(io.BytesIO(data), "a.txt")
            self.assertTrue(Path(out.storage_key).is_file())
            self.assertEqual(out.size_bytes, len(data))
            with svc.local_path(out.storage_key) as p:
                self.assertEqual(Path(p).read_bytes(), data)

    def test_s3_delete_parses_key(self) -> None:
        with patch("boto3.client") as mock_client:
            inst = MagicMock()
            mock_client.return_value = inst
            from app.services.storage.s3 import S3StorageService

            svc = S3StorageService()
            svc.delete("s3://mybucket/prefix/file.pdf")
            inst.delete_object.assert_called_once_with(Bucket="mybucket", Key="prefix/file.pdf")

    def test_s3_presigned_get(self) -> None:
        with patch("boto3.client") as mock_client:
            inst = MagicMock()
            inst.generate_presigned_url.return_value = "https://example/presigned"
            mock_client.return_value = inst
            from app.services.storage.s3 import S3StorageService

            svc = S3StorageService()
            url = svc.presigned_get_url("s3://b/k/x.pdf")
            self.assertEqual(url, "https://example/presigned")

    def test_s3_save_upload_propagates_upload_failure(self) -> None:
        """upload_file errors must not be masked by a success return (regression: return in finally)."""
        with patch("boto3.client") as mock_client:
            inst = MagicMock()
            inst.upload_file.side_effect = OSError("s3 upload failed")
            mock_client.return_value = inst
            from app.services.storage.s3 import S3StorageService

            svc = S3StorageService()
            with self.assertRaises(OSError) as ctx:
                svc.save_upload(io.BytesIO(b"data"), "a.txt")
            self.assertIn("s3 upload failed", str(ctx.exception))
            inst.upload_file.assert_called_once()

    def test_local_direct_download_response_streams_file(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            svc = LocalStorageService(upload_dir=d)
            data = b"streamed-not-buffered"
            out = svc.save_upload(io.BytesIO(data), "a.txt")

            def download(_request):
                return svc.direct_download_response(out.storage_key, filename="a.txt", content_type="text/plain")

            app = Starlette(routes=[Route("/", download)])
            with TestClient(app) as client:
                r = client.get("/")
            self.assertEqual(r.content, data)
            self.assertEqual(r.headers.get("content-type", "").split(";")[0], "text/plain")

    def test_s3_direct_download_response_streams_get_object(self) -> None:
        class _Body:
            def __init__(self, payload: bytes) -> None:
                self.payload = payload
                self.closed = False

            def iter_chunks(self, chunk_size: int = 1024):
                for i in range(0, len(self.payload), chunk_size):
                    yield self.payload[i : i + chunk_size]

            def close(self) -> None:
                self.closed = True

        with patch("boto3.client") as mock_client:
            inst = MagicMock()
            payload = b"abc" * 400_000
            body = _Body(payload)
            inst.get_object.return_value = {"Body": body, "ContentLength": len(payload)}
            mock_client.return_value = inst
            from app.services.storage.s3 import S3StorageService

            svc = S3StorageService()

            def download(_request):
                return svc.direct_download_response(
                    "s3://mybucket/prefix/file.bin",
                    filename="file.bin",
                    content_type="application/octet-stream",
                )

            app = Starlette(routes=[Route("/", download)])
            with TestClient(app) as client:
                r = client.get("/")
            self.assertEqual(r.content, payload)
            self.assertTrue(body.closed)
            inst.get_object.assert_called_once_with(Bucket="mybucket", Key="prefix/file.bin")
            self.assertEqual(r.headers.get("Content-Length"), str(len(payload)))


if __name__ == "__main__":
    unittest.main()
