import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.document_indexing import DocumentIndexingService


class _FakeExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakeDb:
    def __init__(self, inserted_rows):
        self.inserted_rows = inserted_rows
        self.execute_calls = []
        self.flushes = 0

    def add(self, _obj) -> None:
        return None

    def flush(self) -> None:
        self.flushes += 1

    def execute(self, stmt, params=None):
        sql = str(stmt)
        payload = params or {}
        self.execute_calls.append((sql, payload))
        if "INSERT INTO document_chunks" in sql:
            return _FakeExecuteResult(self.inserted_rows)
        return _FakeExecuteResult([])


class DocumentIndexingBulkTests(unittest.TestCase):
    def _doc(self):
        return SimpleNamespace(
            id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            storage_key="k",
            content_type="application/pdf",
            status="queued",
            extracted_text=None,
            page_count=None,
            language=None,
            error_message=None,
            indexed_at=None,
            parser_version=None,
        )

    def _storage(self):
        storage = MagicMock()
        storage.local_path.return_value.__enter__.return_value = "tmp-file"
        storage.local_path.return_value.__exit__.return_value = None
        return storage

    def test_uses_bulk_insert_and_bulk_update_for_chunks(self) -> None:
        chunk_count = 3
        inserted_rows = [{"id": uuid.uuid4(), "chunk_index": i} for i in range(chunk_count)]
        db = _FakeDb(inserted_rows=inserted_rows)
        doc = self._doc()
        extracted = SimpleNamespace(text="alpha\n\nbeta\n\ngamma", page_count=1, language="en")

        with (
            patch("app.services.document_indexing.extract_text_metadata_from_file", return_value=extracted),
            patch("app.services.document_indexing.max_pdf_pages_for_workspace", return_value=None),
            patch("app.services.document_indexing.chunk_text", return_value=["alpha", "beta", "gamma"]),
            patch(
                "app.services.document_indexing.embed_texts",
                return_value=[[0.1] * 384, [0.2] * 384, [0.3] * 384],
            ),
        ):
            svc = DocumentIndexingService(db, self._storage())
            out = svc.run(doc)  # type: ignore[arg-type]

        self.assertEqual(out, 3)
        self.assertEqual(db.flushes, 3)
        chunk_sql_calls = [
            sql
            for sql, _ in db.execute_calls
            if "INSERT INTO document_chunks" in sql or "UPDATE document_chunks c" in sql
        ]
        self.assertEqual(len(chunk_sql_calls), 2)

    def test_updates_only_available_vectors_when_vectors_shorter_than_chunks(self) -> None:
        inserted_rows = [{"id": uuid.uuid4(), "chunk_index": i} for i in range(3)]
        db = _FakeDb(inserted_rows=inserted_rows)
        doc = self._doc()
        extracted = SimpleNamespace(text="a\n\nb\n\nc", page_count=1, language="en")

        with (
            patch("app.services.document_indexing.extract_text_metadata_from_file", return_value=extracted),
            patch("app.services.document_indexing.max_pdf_pages_for_workspace", return_value=None),
            patch("app.services.document_indexing.chunk_text", return_value=["a", "b", "c"]),
            patch("app.services.document_indexing.embed_texts", return_value=[[0.1] * 384]),
        ):
            svc = DocumentIndexingService(db, self._storage())
            out = svc.run(doc)  # type: ignore[arg-type]

        self.assertEqual(out, 3)
        update_calls = [
            payload
            for sql, payload in db.execute_calls
            if "UPDATE document_chunks c" in sql
        ]
        self.assertEqual(len(update_calls), 1)
        self.assertEqual(len(update_calls[0]["ids"]), 1)
        self.assertEqual(len(update_calls[0]["vecs"]), 1)

    def test_marks_document_failed_when_bulk_insert_returning_mismatches(self) -> None:
        db = _FakeDb(inserted_rows=[{"id": uuid.uuid4(), "chunk_index": 0}])
        doc = self._doc()
        extracted = SimpleNamespace(text="a\n\nb", page_count=1, language="en")

        with (
            patch("app.services.document_indexing.extract_text_metadata_from_file", return_value=extracted),
            patch("app.services.document_indexing.max_pdf_pages_for_workspace", return_value=None),
            patch("app.services.document_indexing.chunk_text", return_value=["a", "b"]),
            patch("app.services.document_indexing.embed_texts", return_value=[[0.1] * 384, [0.2] * 384]),
        ):
            svc = DocumentIndexingService(db, self._storage())
            with self.assertRaises(ValueError):
                svc.run(doc)  # type: ignore[arg-type]

        self.assertEqual(doc.status, "failed")
        self.assertIn("mismatch", str(doc.error_message).lower())


if __name__ == "__main__":
    unittest.main()
