"""
Generic hybrid retrieval: dense pgvector + PostgreSQL full-text, fused via RRF.

No domain heuristics — only candidate generation and rank fusion.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.embeddings import get_embedding_dim


def dense_candidates(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    query_embedding: list[float],
    candidate_k: int,
) -> list[dict]:
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
    rows = db.execute(
        sql,
        {
            "workspace_id": str(workspace_id),
            "candidate_k": int(candidate_k),
            "qvec": "[" + ",".join(f"{float(x):.8f}" for x in query_embedding) + "]",
        },
    ).mappings()
    return [dict(r) for r in rows]


def keyword_candidates(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    query_text: str,
    candidate_k: int,
) -> list[dict]:
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
    rows = db.execute(
        sql,
        {
            "workspace_id": str(workspace_id),
            "candidate_k": int(candidate_k),
            "qtext": query_text,
        },
    ).mappings()
    return [dict(r) for r in rows]


def rrf_fuse(
    dense: list[dict],
    keyword: list[dict],
    *,
    rrf_k: int,
    dense_weight: float,
    keyword_weight: float,
) -> list[dict]:
    fused: dict[str, dict] = {}
    dense_ranks: dict[str, int] = {}
    keyword_ranks: dict[str, int] = {}

    for i, row in enumerate(dense, start=1):
        dense_ranks[str(row["chunk_id"])] = i
    for i, row in enumerate(keyword, start=1):
        keyword_ranks[str(row["chunk_id"])] = i

    for row in dense:
        key = str(row["chunk_id"])
        fused[key] = {
            "document_id": row["document_id"],
            "source_filename": row.get("source_filename"),
            "chunk_id": row["chunk_id"],
            "chunk_index": row["chunk_index"],
            "page_number": row.get("page_number"),
            "paragraph_index": row.get("paragraph_index"),
            "text": row["text"],
            "dense_score": float(row.get("dense_score") or 0.0),
            "keyword_score": 0.0,
        }

    for row in keyword:
        key = str(row["chunk_id"])
        if key not in fused:
            fused[key] = {
                "document_id": row["document_id"],
                "source_filename": row.get("source_filename"),
                "chunk_id": row["chunk_id"],
                "chunk_index": row["chunk_index"],
                "page_number": row.get("page_number"),
                "paragraph_index": row.get("paragraph_index"),
                "text": row["text"],
                "dense_score": 0.0,
                "keyword_score": float(row.get("keyword_score") or 0.0),
            }
        else:
            fused[key]["keyword_score"] = float(row.get("keyword_score") or 0.0)

    for key, row in fused.items():
        score = 0.0
        if key in dense_ranks:
            score += float(dense_weight) / float(rrf_k + dense_ranks[key])
        if key in keyword_ranks:
            score += float(keyword_weight) / float(rrf_k + keyword_ranks[key])
        row["score"] = score

    return sorted(
        fused.values(),
        key=lambda r: (
            float(r.get("score") or 0.0),
            float(r.get("keyword_score") or 0.0),
            float(r.get("dense_score") or 0.0),
        ),
        reverse=True,
    )


def hybrid_fuse_candidates(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    query_text_expanded: str,
    query_embedding: list[float],
    candidate_k: int,
) -> list[dict]:
    """Dense + keyword lists merged by RRF, or dense-only when hybrid is disabled."""
    dense = dense_candidates(
        db,
        workspace_id=workspace_id,
        query_embedding=query_embedding,
        candidate_k=candidate_k,
    )
    if not settings.retrieval_hybrid_enabled:
        fused: list[dict] = []
        for row in dense:
            fused.append(
                {
                    "document_id": row["document_id"],
                    "source_filename": row.get("source_filename"),
                    "chunk_id": row["chunk_id"],
                    "chunk_index": row["chunk_index"],
                    "page_number": row.get("page_number"),
                    "paragraph_index": row.get("paragraph_index"),
                    "text": row["text"],
                    "dense_score": float(row.get("dense_score") or 0.0),
                    "keyword_score": 0.0,
                    "score": float(row.get("dense_score") or 0.0),
                }
            )
        return fused

    keyword = keyword_candidates(
        db,
        workspace_id=workspace_id,
        query_text=query_text_expanded,
        candidate_k=candidate_k,
    )
    return rrf_fuse(
        dense,
        keyword,
        rrf_k=int(settings.retrieval_rrf_k),
        dense_weight=float(settings.retrieval_rrf_weight_dense),
        keyword_weight=float(settings.retrieval_rrf_weight_keyword),
    )
