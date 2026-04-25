import io
import unittest
import zipfile
from unittest.mock import patch

from fastapi import HTTPException, UploadFile

from app.api.routers.documents import _validate_upload


class _BrokenTellStream:
    def tell(self) -> int:
        raise OSError("tell unsupported")

    def read(self, n: int = -1) -> bytes:
        return b""

    def seek(self, *args: object) -> int:
        return 0


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

    def test_rejects_double_extension_disguise(self) -> None:
        file = UploadFile(filename="contract.pdf.exe", file=None, headers={"content-type": "application/pdf"})
        with self.assertRaises(HTTPException) as err:
            _validate_upload(file)
        self.assertEqual(err.exception.status_code, 400)

    def test_rejects_unsupported_content_type(self) -> None:
        file = UploadFile(filename="report.pdf", file=None, headers={"content-type": "application/octet-stream"})
        with self.assertRaises(HTTPException) as err:
            _validate_upload(file)
        self.assertEqual(err.exception.status_code, 400)

    def test_rejects_pdf_extension_when_magic_bytes_invalid(self) -> None:
        file = UploadFile(
            filename="report.pdf",
            file=io.BytesIO(b"NOTPDF-DATA"),
            headers={"content-type": "application/pdf"},
        )
        with self.assertRaises(HTTPException) as err:
            _validate_upload(file)
        self.assertEqual(err.exception.status_code, 400)

    def test_rejects_when_magic_byte_header_unreadable_fail_closed(self) -> None:
        file = UploadFile(
            filename="report.pdf",
            file=_BrokenTellStream(),  # type: ignore[arg-type]
            headers={"content-type": "application/pdf"},
        )
        with self.assertRaises(HTTPException) as err:
            _validate_upload(file)
        self.assertEqual(err.exception.status_code, 400)
        self.assertEqual(err.exception.detail, "Could not validate uploaded file")

    def _minimal_docx_bytes(self) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(
                "[Content_Types].xml",
                b"<?xml version='1.0' encoding='UTF-8'?><Types/>",
            )
            zf.writestr(
                "word/document.xml",
                b"<?xml version='1.0' encoding='UTF-8'?><w:document/>",
            )
        return buf.getvalue()

    def test_accepts_minimal_valid_docx(self) -> None:
        data = self._minimal_docx_bytes()
        file = UploadFile(
            filename="memo.docx",
            file=io.BytesIO(data),
            headers={"content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        )
        _validate_upload(file)
        if file.file is not None:
            self.assertEqual(file.file.tell(), 0)

    def test_rejects_docx_missing_word_document(self) -> None:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(
                "[Content_Types].xml",
                b"<?xml version='1.0' encoding='UTF-8'?><Types/>",
            )
        data = buf.getvalue()
        file = UploadFile(
            filename="x.docx",
            file=io.BytesIO(data),
            headers={"content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        )
        with self.assertRaises(HTTPException) as err:
            _validate_upload(file)
        self.assertEqual(err.exception.status_code, 400)

    def test_rejects_docx_when_too_many_zip_members(self) -> None:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(
                "[Content_Types].xml",
                b"<?xml version='1.0' encoding='UTF-8'?><Types/>",
            )
            zf.writestr(
                "word/document.xml",
                b"<?xml version='1.0' encoding='UTF-8'?><w:document/>",
            )
            for i in range(4):
                zf.writestr(f"extra/placeholder{i}.xml", b"<?xml?><e/>")
        data = buf.getvalue()
        file = UploadFile(
            filename="x.docx",
            file=io.BytesIO(data),
            headers={"content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        )
        with patch("app.services.document_ingestion.MAX_DOCX_ZIP_MEMBERS", 3):
            with self.assertRaises(HTTPException) as err:
                _validate_upload(file)
        self.assertEqual(err.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
