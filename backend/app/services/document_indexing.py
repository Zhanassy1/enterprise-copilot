from __future__ import annotations

from datetime import datetime, timezone
import re
import uuid

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentChunk
from app.services.chunking import chunk_text
from app.services.embeddings import embed_texts
from app.services.storage.base import StorageService
from app.services.text_extraction import extract_text_metadata_from_file


def _chunk_offsets(full_text: str, chunks: list[str]) -> list[tuple[int, int]]:
    offsets: list[tuple[int, int]] = []
    cursor = 0
    for chunk in chunks:
        idx = full_text.find(chunk, cursor)
        if idx < 0:
            idx = full_text.find(chunk)
        if idx < 0:
            idx = cursor
        end = idx + len(chunk)
        offsets.append((idx, end))
        cursor = max(end - 50, end)
    return offsets


def _paragraph_index_by_pos(full_text: str, pos: int) -> int:
    if pos <= 0:
        return 0
    return len(re.findall(r"\n\s*\n", full_text[:pos]))


def _page_spans(full_text: str) -> list[tuple[int, int, int]]:
    # We insert '\f' between PDF pages in text extraction.
    spans: list[tuple[int, int, int]] = []
    cursor = 0
    page_no = 1
    for part in full_text.split("\f"):
        start = cursor
        end = start + len(part)
        spans.append((start, end, page_no))
        cursor = end + 1
        page_no += 1
    return spans


def _page_by_pos(spans: list[tuple[int, int, int]], pos: int) -> int | None:
    for start, end, page_no in spans:
        if start <= pos <= end:
            return page_no
    return None


class DocumentIndexingService:
    def __init__(self, db: Session, storage: StorageService) -> None:
        self.db = db
        self.storage = storage

    def run(self, document: Document) -> int:
        document.status = "processing"
        document.error_message = None
        self.db.add(document)
        self.db.flush()

        try:
            with self.storage.local_path(document.storage_key) as local_file:
                extracted_doc = extract_text_metadata_from_file(local_file, content_type=document.content_type)
            extracted = extracted_doc.text
            if not extracted:
                raise ValueError("Failed to extract text (empty)")

            self.db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
            self.db.flush()

            document.extracted_text = extracted
            document.page_count = extracted_doc.page_count
            document.language = extracted_doc.language
            chunks = chunk_text(extracted)
            offsets = _chunk_offsets(extracted, chunks)
            spans = _page_spans(extracted)
            vectors = embed_texts(chunks)

            for i, t in enumerate(chunks):
                start, _ = offsets[i]
                row = DocumentChunk(
                    document_id=document.id,
                    chunk_index=i,
                    page_number=_page_by_pos(spans, start),
                    paragraph_index=_paragraph_index_by_pos(extracted, start),
                    text=t,
                    embedding=None,
                )
                self.db.add(row)
                self.db.flush()

                if i < len(vectors):
                    vec = vectors[i]
                    vec_lit = "[" + ",".join(f"{float(x):.8f}" for x in vec) + "]"
                    self.db.execute(
                        text(
                            "UPDATE document_chunks SET embedding_vector = (:v)::vector(384) "
                            "WHERE id = CAST(:id AS uuid)"
                        ),
                        {"v": vec_lit, "id": str(row.id)},
                    )

            document.status = "ready"
            document.indexed_at = datetime.now(timezone.utc)
            document.error_message = None
            document.parser_version = "v1"
            self.db.add(document)
            self.db.flush()
            return len(chunks)
        except Exception as exc:
            document.status = "failed"
            document.error_message = str(exc)
            self.db.add(document)
            self.db.flush()
            raise


def reindex_null_embeddings_for_workspace(db: Session, *, workspace_id: uuid.UUID) -> int:
    """Fill embedding_vector for chunks in workspace where it is NULL (legacy rows)."""
    rows = db.execute(
        text(
            """
            SELECT c.id AS id, c.text AS text
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.workspace_id = CAST(:workspace_id AS uuid) AND c.embedding_vector IS NULL
            """
        ),
        {"workspace_id": str(workspace_id)},
    ).mappings().all()
    if not rows:
        return 0
    texts = [str(r["text"]) for r in rows]
    ids = [str(r["id"]) for r in rows]
    vectors = embed_texts(texts)
    if len(vectors) != len(ids):
        raise ValueError("Embedding count mismatch")
    for cid, vec in zip(ids, vectors, strict=True):
        vec_lit = "[" + ",".join(f"{float(x):.8f}" for x in vec) + "]"
        db.execute(
            text(
                "UPDATE document_chunks SET embedding_vector = (:v)::vector(384) "
                "WHERE id = CAST(:id AS uuid)"
            ),
            {"v": vec_lit, "id": cid},
        )
    db.commit()
    return len(ids)
