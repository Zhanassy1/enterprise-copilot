"""
Persistence and retrieval for ``document_chunks`` (pgvector + bulk paths).

All raw SQL for this table lives here; callers use typed methods only.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.models.document import DocumentChunk
from app.services.embeddings import assert_embedding_vector_dim, get_embedding_dim


class DocumentChunkRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def delete_by_document_id(self, document_id: uuid.UUID) -> None:
        self._db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))

    def embedding_stats(self, document_id: uuid.UUID) -> tuple[int, int]:
        row = (
            self._db.execute(
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

    def list_pending_text_pairs(self, document_id: uuid.UUID) -> list[tuple[str, str]]:
        rows = (
            self._db.execute(
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

    def bulk_insert_placeholder_chunks(
        self,
        *,
        document_id: uuid.UUID,
        chunk_indices: list[int],
        page_numbers: list[int | None],
        paragraph_indices: list[int],
        texts: list[str],
    ) -> list[dict[str, Any]]:
        """Insert rows with ``embedding_vector`` NULL; ``page_numbers`` may contain NULLs."""
        inserted_rows = (
            self._db.execute(
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
                    "document_id": str(document_id),
                    "chunk_indices": chunk_indices,
                    "page_numbers": page_numbers,
                    "paragraph_indices": paragraph_indices,
                    "texts": texts,
                },
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in inserted_rows]

    def bulk_update_embeddings(
        self,
        chunk_ids: list[str],
        vectors: list[list[float]],
        *,
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
        self._db.execute(
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

    def list_null_embedding_batch(
        self, *, workspace_id: uuid.UUID, limit: int
    ) -> list[dict[str, Any]]:
        return list(
            self._db.execute(
                text(
                    """
            SELECT c.id AS id, c.text AS text
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.workspace_id = CAST(:workspace_id AS uuid) AND c.embedding_vector IS NULL
            LIMIT :lim
            """
                ),
                {"workspace_id": str(workspace_id), "lim": int(limit)},
            )
            .mappings()
            .all()
        )

    def insert_chunk_with_embedding(
        self,
        *,
        chunk_id: uuid.UUID,
        document_id: uuid.UUID,
        chunk_index: int,
        text: str,
        embedding_dim: int,
        vector_literal: str,
        page_number: int | None,
        paragraph_index: int | None,
    ) -> None:
        """Single-row insert for eval fixtures; ``vector_literal`` is bracketed floats, not user SQL."""
        self._db.execute(
            text(
                f"""
                INSERT INTO document_chunks (
                  id, document_id, chunk_index, text, embedding_vector, page_number, paragraph_index
                ) VALUES (
                  CAST(:cid AS uuid),
                  CAST(:did AS uuid),
                  :idx,
                  :txt,
                  CAST(:qv AS vector({embedding_dim})),
                  :pg,
                  :para
                )
                """
            ),
            {
                "cid": str(chunk_id),
                "did": str(document_id),
                "idx": chunk_index,
                "txt": text,
                "qv": vector_literal,
                "pg": page_number,
                "para": paragraph_index,
            },
        )

    def dense_candidates(
        self,
        *,
        workspace_id: uuid.UUID,
        query_embedding: list[float],
        candidate_k: int,
    ) -> list[dict[str, Any]]:
        dim = get_embedding_dim()
        if len(query_embedding) != dim:
            raise ValueError(
                f"Query embedding dimension mismatch: expected {dim}, got {len(query_embedding)}"
            )
        sql = text(
            f"""
        SELECT
          d.id AS document_id,
          d.filename AS source_filename,
          c.id AS chunk_id,
          c.chunk_index AS chunk_index,
          c.page_number AS page_number,
          c.paragraph_index AS paragraph_index,
          c.text AS text,
          (1 - (c.embedding_vector <=> (:qvec)::vector({dim}))) AS dense_score
        FROM document_chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE
          d.workspace_id = :workspace_id
          AND d.deleted_at IS NULL
          AND d.status = 'ready'
          AND c.embedding_vector IS NOT NULL
        ORDER BY dense_score DESC, c.chunk_index ASC
        LIMIT :candidate_k
        """
        )
        rows = self._db.execute(
            sql,
            {
                "workspace_id": str(workspace_id),
                "candidate_k": int(candidate_k),
                "qvec": "[" + ",".join(f"{float(x):.8f}" for x in query_embedding) + "]",
            },
        ).mappings()
        return [dict(r) for r in rows]

    def keyword_candidates(
        self,
        *,
        workspace_id: uuid.UUID,
        query_text: str,
        candidate_k: int,
    ) -> list[dict[str, Any]]:
        sql = text(
            """
        SELECT
          d.id AS document_id,
          d.filename AS source_filename,
          c.id AS chunk_id,
          c.chunk_index AS chunk_index,
          c.page_number AS page_number,
          c.paragraph_index AS paragraph_index,
          c.text AS text,
          (
            0.65 * LEAST(COALESCE(ts_rank_cd(to_tsvector('russian', c.text), websearch_to_tsquery('russian', :qtext)), 0.0), 1.0)
            + 0.30 * LEAST(COALESCE(ts_rank_cd(to_tsvector('simple', c.text), websearch_to_tsquery('simple', :qtext)), 0.0), 1.0)
            + 0.05 * CASE WHEN c.text ILIKE ('%' || :qtext || '%') THEN 1.0 ELSE 0.0 END
          ) AS keyword_score
        FROM document_chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.workspace_id = :workspace_id AND d.deleted_at IS NULL AND d.status = 'ready'
        ORDER BY keyword_score DESC, c.chunk_index ASC
        LIMIT :candidate_k
        """
        )
        rows = self._db.execute(
            sql,
            {
                "workspace_id": str(workspace_id),
                "candidate_k": int(candidate_k),
                "qtext": query_text,
            },
        ).mappings()
        return [dict(r) for r in rows]
