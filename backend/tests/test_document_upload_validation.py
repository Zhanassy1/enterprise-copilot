import unittest

from fastapi import HTTPException, UploadFile

from app.api.routers.documents import _validate_upload


class UploadValidationTests(unittest.TestCase):
    def test_accepts_pdf_with_content_type(self) -> None:
        file = UploadFile(filename="contract.pdf", file=None, headers={"content-type": "application/pdf"})
        _validate_upload(file)

    def test_accepts_txt_without_content_type(self) -> None:
        file = UploadFile(filename="notes.txt", file=None)
        _validate_upload(file)

    def test_rejects_unsupported_extension(self) -> None:
        file = UploadFile(filename="archive.zip", file=None, headers={"content-type": "application/zip"})
        with self.assertRaises(HTTPException) as err:
            _validate_upload(file)
        self.assertEqual(err.exception.status_code, 400)

    def test_rejects_unsupported_content_type(self) -> None:
        file = UploadFile(filename="report.pdf", file=None, headers={"content-type": "application/octet-stream"})
        with self.assertRaises(HTTPException) as err:
            _validate_upload(file)
        self.assertEqual(err.exception.status_code, 400)

    def test_rejects_pdf_extension_when_magic_bytes_invalid(self) -> None:
        import io

        file = UploadFile(
            filename="report.pdf",
            file=io.BytesIO(b"NOTPDF-DATA"),
            headers={"content-type": "application/pdf"},
        )
        with self.assertRaises(HTTPException) as err:
            _validate_upload(file)
        self.assertEqual(err.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
