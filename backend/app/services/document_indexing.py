from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document, DocumentChunk
from app.services.chunking import chunk_text
from app.services.embeddings import assert_embedding_vector_dim, embed_texts, get_embedding_dim
from app.services.pdf_ingestion import extract_pdf_for_indexing
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


def _indexing_fingerprint(parser_version: str) -> dict:
    return {
        "chunk_size": int(settings.chunk_size),
        "chunk_overlap": int(settings.chunk_overlap),
        "parser_version": parser_version,
    }


def _merge_indexing_into_extraction_meta(document: Document, parser_version: str) -> None:
    meta = dict(document.extraction_meta) if isinstance(document.extraction_meta, dict) else {}
    meta["indexing"] = _indexing_fingerprint(parser_version)
    document.extraction_meta = meta


def _indexing_chunk_config_matches(document: Document) -> bool:
    meta = document.extraction_meta if isinstance(document.extraction_meta, dict) else {}
    idx = meta.get("indexing")
    if not isinstance(idx, dict):
        return False
    try:
        return int(idx.get("chunk_size", -1)) == int(settings.chunk_size) and int(
            idx.get("chunk_overlap", -1)
        ) == int(settings.chunk_overlap)
    except (TypeError, ValueError):
        return False


def _document_chunk_stats(db: Session, document_id: uuid.UUID) -> tuple[int, int]:
    row = (
        db.execute(
            text(
                """
            SELECT
              COUNT(*)::int AS total,
              COUNT(*) FILTER (WHERE c.embedding_vector IS NULL)::int AS pending
            FROM document_chunks c
            WHERE c.document_id = CAST(:document_id AS uuid)
            """
            ),
            {"document_id": str(document_id)},
        )
        .mappings()
        .first()
    )
    if not row:
        return 0, 0
    return int(row["total"]), int(row["pending"])


def _chunk_count(db: Session, document_id: uuid.UUID) -> int:
    total, _ = _document_chunk_stats(db, document_id)
    return total


def _parser_version_for_finalize(document: Document) -> str:
    meta = document.extraction_meta if isinstance(document.extraction_meta, dict) else {}
    idx = meta.get("indexing")
    if isinstance(idx, dict) and idx.get("parser_version"):
        return str(idx["parser_version"])
    return document.parser_version or "v1"


def _try_finalize_if_all_embedded(db: Session, document: Document) -> int | None:
    total, pending = _document_chunk_stats(db, document.id)
    if total == 0 or pending > 0:
        return None
    if document.status == "ready":
        return total
    document.status = "ready"
    document.indexed_at = datetime.now(UTC)
    document.error_message = None
    if not document.parser_version:
        document.parser_version = _parser_version_for_finalize(document)
    db.add(document)
    db.flush()
    return total


def _bulk_update_chunk_embeddings(
    db: Session,
    *,
    chunk_ids: list[str],
    vectors: list[list[float]],
    embedding_dim: int,
) -> None:
    if not chunk_ids:
        return
    if len(chunk_ids) != len(vectors):
        raise ValueError("chunk_ids and vectors length mismatch")
    vec_literals: list[str] = []
    for vec in vectors:
        assert_embedding_vector_dim(vec, expected_dim=embedding_dim)
        vec_literals.append("[" + ",".join(f"{float(x):.8f}" for x in vec) + "]")
    db.execute(
        text(
            f"""
            UPDATE document_chunks c
            SET embedding_vector = (u.vec)::vector({embedding_dim})
            FROM unnest(
                CAST(:ids AS uuid[]),
                CAST(:vecs AS text[])
            ) AS u(id, vec)
            WHERE c.id = u.id
            """
        ),
        {"ids": chunk_ids, "vecs": vec_literals},
    )


def _embed_chunk_ids_in_batches(
    db: Session,
    *,
    chunk_ids: list[str],
    texts: list[str],
    embedding_dim: int,
    batch_size: int,
) -> None:
    if len(chunk_ids) != len(texts):
        raise ValueError("chunk_ids and texts length mismatch")
    bs = max(1, int(batch_size))
    for start in range(0, len(chunk_ids), bs):
        batch_ids = chunk_ids[start : start + bs]
        batch_texts = texts[start : start + bs]
        vectors = embed_texts(
            batch_texts,
            encode_batch_size=min(bs, len(batch_texts)),
        )
        if len(vectors) != len(batch_ids):
            raise ValueError("Embedding count mismatch in batch")
        _bulk_update_chunk_embeddings(
            db,
            chunk_ids=batch_ids,
            vectors=vectors,
            embedding_dim=embedding_dim,
        )
        db.commit()


def _pending_chunks_ordered(db: Session, document_id: uuid.UUID) -> list[tuple[str, str]]:
    rows = (
        db.execute(
            text(
                """
            SELECT c.id::text AS id, c.text AS text
            FROM document_chunks c
            WHERE c.document_id = CAST(:document_id AS uuid)
              AND c.embedding_vector IS NULL
            ORDER BY c.chunk_index ASC
            """
            ),
            {"document_id": str(document_id)},
        )
        .mappings()
        .all()
    )
    return [(str(r["id"]), str(r["text"])) for r in rows]


class DocumentIndexingService:
    def __init__(self, db: Session, storage: StorageService) -> None:
        self.db = db
        self.storage = storage

    def _mark_ready(self, document: Document, parser_ver: str) -> None:
        document.status = "ready"
        document.indexed_at = datetime.now(UTC)
        document.error_message = None
        document.parser_version = parser_ver
        self.db.add(document)
        self.db.flush()

    def _embed_pending_then_ready(
        self,
        document: Document,
        *,
        embedding_dim: int,
        batch_size: int,
        parser_ver: str,
    ) -> int:
        pairs = _pending_chunks_ordered(self.db, document.id)
        if not pairs:
            total, pending = _document_chunk_stats(self.db, document.id)
            if total > 0 and pending == 0:
                self._mark_ready(document, parser_ver)
                self.db.commit()
            return _chunk_count(self.db, document.id)
        ids = [p[0] for p in pairs]
        texts = [p[1] for p in pairs]
        _embed_chunk_ids_in_batches(
            self.db,
            chunk_ids=ids,
            texts=texts,
            embedding_dim=embedding_dim,
            batch_size=batch_size,
        )
        self.db.refresh(document)
        self._mark_ready(document, parser_ver)
        self.db.commit()
        return _chunk_count(self.db, document.id)

    def run(self, document: Document) -> int:
        embedding_dim = get_embedding_dim()
        batch_size = max(1, int(settings.embedding_batch_size))

        if document.status == "ready":
            return _chunk_count(self.db, document.id)

        fin = _try_finalize_if_all_embedded(self.db, document)
        if fin is not None:
            self.db.commit()
            return fin

        self.db.refresh(document)
        total, pending = _document_chunk_stats(self.db, document.id)
        if (
            total > 0
            and pending > 0
            and document.status in ("processing", "retrying")
            and _indexing_chunk_config_matches(document)
        ):
            parser_ver = _parser_version_for_finalize(document)
            return self._embed_pending_then_ready(
                document,
                embedding_dim=embedding_dim,
                batch_size=batch_size,
                parser_ver=parser_ver,
            )

        document.status = "processing"
        document.error_message = None
        self.db.add(document)
        self.db.flush()

        try:
            with self.storage.local_path(document.storage_key) as local_file:
                ct = (document.content_type or "").lower().strip()
                try:
                    suffix = Path(document.filename or "").suffix.lower()
                except Exception:
                    suffix = ""
                if ct == "application/pdf" or suffix == ".pdf":
                    pdf_out = extract_pdf_for_indexing(
                        local_file, storage_key=document.storage_key
                    )
                    extracted_doc = pdf_out.extracted
                    document.pdf_kind = pdf_out.pdf_kind
                    document.ocr_applied = pdf_out.ocr_applied
                    document.extraction_meta = pdf_out.extraction_meta
                    parser_ver = pdf_out.parser_version
                else:
                    document.pdf_kind = None
                    document.ocr_applied = False
                    document.extraction_meta = None
                    extracted_doc = extract_text_metadata_from_file(
                        local_file, content_type=document.content_type
                    )
                    parser_ver = "v1"
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

            _merge_indexing_into_extraction_meta(document, parser_ver)

            chunks = chunk_text(
                extracted, chunk_size=int(settings.chunk_size), overlap=int(settings.chunk_overlap)
            )
            offsets = _chunk_offsets(extracted, chunks)
            spans = _page_spans(extracted)

            chunk_indices = list(range(len(chunks)))
            page_numbers = []
            paragraph_indices = []
            for i in chunk_indices:
                start, _ = offsets[i]
                page_numbers.append(_page_by_pos(spans, start))
                paragraph_indices.append(_paragraph_index_by_pos(extracted, start))

            inserted_rows = (
                self.db.execute(
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
                )
                .mappings()
                .all()
            )

            id_by_chunk_index = {int(row["chunk_index"]): str(row["id"]) for row in inserted_rows}
            if len(id_by_chunk_index) != len(chunks) or set(id_by_chunk_index) != set(
                chunk_indices
            ):
                raise ValueError("Inserted chunk IDs mismatch")

            self.db.add(document)
            self.db.flush()
            self.db.commit()

            ordered_ids = [id_by_chunk_index[i] for i in range(len(chunks))]
            _embed_chunk_ids_in_batches(
                self.db,
                chunk_ids=ordered_ids,
                texts=chunks,
                embedding_dim=embedding_dim,
                batch_size=batch_size,
            )

            self.db.refresh(document)
            self._mark_ready(document, parser_ver)
            self.db.commit()
            return len(chunks)
        except Exception as exc:
            document.status = "failed"
            document.error_message = str(exc)
            self.db.add(document)
            self.db.flush()
            raise


def reindex_null_embeddings_for_workspace(db: Session, *, workspace_id: uuid.UUID) -> int:
    """Fill embedding_vector for chunks in workspace where it is NULL (legacy rows)."""
    embedding_dim = get_embedding_dim()
    batch_size = max(1, int(settings.embedding_batch_size))
    updated_total = 0
    while True:
        rows = (
            db.execute(
                text(
                    """
            SELECT c.id AS id, c.text AS text
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.workspace_id = CAST(:workspace_id AS uuid) AND c.embedding_vector IS NULL
            LIMIT :lim
            """
                ),
                {"workspace_id": str(workspace_id), "lim": batch_size},
            )
            .mappings()
            .all()
        )
        if not rows:
            break
        texts = [str(r["text"]) for r in rows]
        ids = [str(r["id"]) for r in rows]
        vectors = embed_texts(
            texts,
            encode_batch_size=min(batch_size, len(texts)),
        )
        if len(vectors) != len(ids):
            raise ValueError("Embedding count mismatch")
        _bulk_update_chunk_embeddings(
            db,
            chunk_ids=ids,
            vectors=vectors,
            embedding_dim=embedding_dim,
        )
        db.commit()
        updated_total += len(ids)
    return updated_total
