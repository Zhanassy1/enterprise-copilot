from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document, DocumentChunk
from app.services.chunking import chunk_text
from app.services.embeddings import embed_texts
from app.services.storage.base import StorageService
from app.services.text_extraction import extract_text_metadata_from_file
from app.services.usage_metering import max_pdf_pages_for_workspace


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
            page_limit = max_pdf_pages_for_workspace(self.db, document.workspace_id)
            if page_limit is not None and int(extracted_doc.page_count or 0) > int(page_limit):
                raise ValueError(f"Document exceeds plan page limit ({page_limit} pages max)")
            chunks = chunk_text(extracted, chunk_size=int(settings.chunk_size), overlap=int(settings.chunk_overlap))
            offsets = _chunk_offsets(extracted, chunks)
            spans = _page_spans(extracted)
            vectors = embed_texts(chunks)

            chunk_indices = list(range(len(chunks)))
            page_numbers = []
            paragraph_indices = []
            for i in chunk_indices:
                start, _ = offsets[i]
                page_numbers.append(_page_by_pos(spans, start))
                paragraph_indices.append(_paragraph_index_by_pos(extracted, start))

            inserted_rows = self.db.execute(
                text(
                    """
                    INSERT INTO document_chunks (
                        id, document_id, chunk_index, page_number, paragraph_index, text, embedding_vector
                    )
                    SELECT
                        gen_random_uuid(),
                        CAST(:document_id AS uuid),
                        t.chunk_index,
                        t.page_number,
                        t.paragraph_index,
                        t.text,
                        NULL
                    FROM unnest(
                        CAST(:chunk_indices AS integer[]),
                        CAST(:page_numbers AS integer[]),
                        CAST(:paragraph_indices AS integer[]),
                        CAST(:texts AS text[])
                    ) AS t(chunk_index, page_number, paragraph_index, text)
                    RETURNING id, chunk_index
                    """
                ),
                {
                    "document_id": str(document.id),
                    "chunk_indices": chunk_indices,
                    "page_numbers": page_numbers,
                    "paragraph_indices": paragraph_indices,
                    "texts": chunks,
                },
            ).mappings().all()

            id_by_chunk_index = {
                int(row["chunk_index"]): str(row["id"]) for row in inserted_rows
            }
            if len(id_by_chunk_index) != len(chunks) or set(id_by_chunk_index) != set(chunk_indices):
                raise ValueError("Inserted chunk IDs mismatch")

            ids_to_update: list[str] = []
            vec_literals: list[str] = []
            for i, vec in enumerate(vectors):
                if i >= len(chunks):
                    break
                ids_to_update.append(id_by_chunk_index[i])
                vec_literals.append("[" + ",".join(f"{float(x):.8f}" for x in vec) + "]")

            if ids_to_update:
                self.db.execute(
                    text(
                        """
                        UPDATE document_chunks c
                        SET embedding_vector = (u.vec)::vector(384)
                        FROM unnest(
                            CAST(:ids AS uuid[]),
                            CAST(:vecs AS text[])
                        ) AS u(id, vec)
                        WHERE c.id = u.id
                        """
                    ),
                    {"ids": ids_to_update, "vecs": vec_literals},
                )

            document.status = "ready"
            document.indexed_at = datetime.now(UTC)
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
