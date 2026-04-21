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
from app.services.retrieval.chunk_search_aux import build_chunk_search_aux
from app.services.retrieval.keyword_query import (
    KEYWORD_ILIKE_MAX_LEN,
    any_tsquery_non_empty,
    prepare_keyword_tsquery_texts,
)


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
        search_aux_texts: list[str],
    ) -> list[dict[str, Any]]:
        """Insert rows with ``embedding_vector`` NULL; ``page_numbers`` may contain NULLs."""
        if len(search_aux_texts) != len(texts):
            raise ValueError("search_aux_texts and texts length mismatch")
        inserted_rows = (
            self._db.execute(
                text(
                    """
                    INSERT INTO document_chunks (
                        id, document_id, chunk_index, page_number, paragraph_index, text,
                        chunk_search_aux, embedding_vector
                    )
                    SELECT
                        gen_random_uuid(),
                        CAST(:document_id AS uuid),
                        t.chunk_index,
                        t.page_number,
                        t.paragraph_index,
                        t.text,
                        t.search_aux,
                        NULL
                    FROM unnest(
                        CAST(:chunk_indices AS integer[]),
                        CAST(:page_numbers AS integer[]),
                        CAST(:paragraph_indices AS integer[]),
                        CAST(:texts AS text[]),
                        CAST(:search_aux_texts AS text[])
                    ) AS t(chunk_index, page_number, paragraph_index, text, search_aux)
                    RETURNING id, chunk_index
                    """
                ),
                {
                    "document_id": str(document_id),
                    "chunk_indices": chunk_indices,
                    "page_numbers": page_numbers,
                    "paragraph_indices": paragraph_indices,
                    "texts": texts,
                    "search_aux_texts": search_aux_texts,
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
        chunk_search_aux: str | None = None,
    ) -> None:
        """Single-row insert for eval fixtures; ``vector_literal`` is bracketed floats, not user SQL."""
        aux = chunk_search_aux if chunk_search_aux is not None else build_chunk_search_aux(text)
        self._db.execute(
            text(
                f"""
                INSERT INTO document_chunks (
                  id, document_id, chunk_index, text, chunk_search_aux, embedding_vector,
                  page_number, paragraph_index
                ) VALUES (
                  CAST(:cid AS uuid),
                  CAST(:did AS uuid),
                  :idx,
                  :txt,
                  :aux,
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
                "aux": aux,
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
        q_ru, q_simple, q_aux = prepare_keyword_tsquery_texts(self._db, query_text)
        if not any_tsquery_non_empty(q_ru, q_simple, q_aux):
            return []

        use_substring_bonus = len((query_text or "").strip()) <= KEYWORD_ILIKE_MAX_LEN
        substring_sql = (
            " + 0.05 * CASE WHEN POSITION(LOWER(:q_sub) IN LOWER(c.text)) > 0 "
            "THEN 1.0 ELSE 0.0 END"
            if use_substring_bonus
            else ""
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
          (
            0.62 * LEAST(COALESCE(ts_rank_cd(c.chunk_tsv_ru, CAST(:q_ru AS tsquery)), 0.0), 1.0)
            + 0.28 * LEAST(
                COALESCE(ts_rank_cd(c.chunk_tsv_simple, CAST(:q_simple AS tsquery)), 0.0), 1.0
            )
            + 0.05 * LEAST(
                COALESCE(ts_rank_cd(c.chunk_tsv_aux, CAST(:q_aux AS tsquery)), 0.0), 1.0
            )
            {substring_sql}
          ) AS keyword_score
        FROM document_chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE
          d.workspace_id = :workspace_id
          AND d.deleted_at IS NULL
          AND d.status = 'ready'
          AND (
            (:q_ru <> '' AND c.chunk_tsv_ru @@ CAST(:q_ru AS tsquery))
            OR (:q_simple <> '' AND c.chunk_tsv_simple @@ CAST(:q_simple AS tsquery))
            OR (:q_aux <> '' AND c.chunk_tsv_aux @@ CAST(:q_aux AS tsquery))
          )
        ORDER BY keyword_score DESC, c.chunk_index ASC
        LIMIT :candidate_k
        """
        )

        params: dict[str, Any] = {
            "workspace_id": str(workspace_id),
            "candidate_k": int(candidate_k),
            "q_ru": q_ru,
            "q_simple": q_simple,
            "q_aux": q_aux,
        }
        if use_substring_bonus:
            params["q_sub"] = (query_text or "").strip()

        rows = self._db.execute(sql, params).mappings()
        return [dict(r) for r in rows]
