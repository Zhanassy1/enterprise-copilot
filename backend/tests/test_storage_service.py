import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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


if __name__ == "__main__":
    unittest.main()
