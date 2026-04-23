"""
Generic hybrid retrieval: dense pgvector + PostgreSQL full-text, fused via RRF.

No domain heuristics — only candidate generation and rank fusion.
SQL for ``document_chunks`` lives in :class:`app.repositories.document_chunks.DocumentChunkRepository`.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.document_chunks import DocumentChunkRepository
from app.services.retrieval.tuning import RetrievalContext, build_retrieval_context


def dense_candidates(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    query_embedding: list[float],
    candidate_k: int,
) -> list[dict]:
    return DocumentChunkRepository(db).dense_candidates(
        workspace_id=workspace_id,
        query_embedding=query_embedding,
        candidate_k=candidate_k,
    )


def keyword_candidates(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    query_text: str,
    candidate_k: int,
) -> list[dict]:
    return DocumentChunkRepository(db).keyword_candidates(
        workspace_id=workspace_id,
        query_text=query_text,
        candidate_k=candidate_k,
    )


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


def _min_max_norm_map(values: list[float]) -> dict[int, float]:
    if not values:
        return {}
    lo = min(values)
    hi = max(values)
    if hi <= lo + 1e-12:
        return {i: 0.5 for i in range(len(values))}
    return {i: (values[i] - lo) / (hi - lo) for i in range(len(values))}


def weighted_score_fuse(
    dense: list[dict],
    keyword: list[dict],
    *,
    alpha: float,
    score_magnitude: float,
) -> list[dict]:
    """
    Min-max each list, combine: alpha * norm_dense + (1-alpha) * norm_keyword; missing side uses 0.
    Final score scaled by ``score_magnitude`` to sit near raw RRF magnitudes.
    """
    a = max(0.0, min(1.0, float(alpha)))
    mag = float(score_magnitude)
    dense_raw = [float(r.get("dense_score") or 0.0) for r in dense]
    key_raw = [float(r.get("keyword_score") or 0.0) for r in keyword]
    dn = _min_max_norm_map(dense_raw)
    kn = _min_max_norm_map(key_raw)
    dense_by_id: dict[str, float] = {
        str(dense[i]["chunk_id"]): dn[i] for i in range(len(dense)) if i in dn
    }
    key_by_id: dict[str, float] = {
        str(keyword[i]["chunk_id"]): kn[i] for i in range(len(keyword)) if i in kn
    }
    row_by_id: dict[str, dict] = {}
    for r in dense:
        cid = str(r["chunk_id"])
        if cid not in row_by_id:
            row_by_id[cid] = {
                "document_id": r["document_id"],
                "source_filename": r.get("source_filename"),
                "chunk_id": r["chunk_id"],
                "chunk_index": r["chunk_index"],
                "page_number": r.get("page_number"),
                "paragraph_index": r.get("paragraph_index"),
                "text": r["text"],
                "dense_score": float(r.get("dense_score") or 0.0),
                "keyword_score": 0.0,
            }
    for r in keyword:
        cid = str(r["chunk_id"])
        if cid not in row_by_id:
            row_by_id[cid] = {
                "document_id": r["document_id"],
                "source_filename": r.get("source_filename"),
                "chunk_id": r["chunk_id"],
                "chunk_index": r["chunk_index"],
                "page_number": r.get("page_number"),
                "paragraph_index": r.get("paragraph_index"),
                "text": r["text"],
                "dense_score": 0.0,
                "keyword_score": float(r.get("keyword_score") or 0.0),
            }
        else:
            row_by_id[cid]["keyword_score"] = float(r.get("keyword_score") or 0.0)

    fused: list[dict] = []
    for cid, base_row in row_by_id.items():
        row = base_row
        nd = dense_by_id.get(cid, 0.0)
        nk = key_by_id.get(cid, 0.0)
        comb = a * nd + (1.0 - a) * nk
        row = dict(row)
        row["score"] = comb * mag
        fused.append(row)
    return sorted(
        fused,
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
    retrieval_ctx: RetrievalContext | None = None,
) -> list[dict]:
    """Dense + keyword lists merged by RRF (default) or weighted min-max, or dense-only if hybrid is disabled."""
    ctx = retrieval_ctx or build_retrieval_context(query_text_expanded)
    repo = DocumentChunkRepository(db)
    dense = repo.dense_candidates(
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

    keyword = repo.keyword_candidates(
        workspace_id=workspace_id,
        query_text=query_text_expanded,
        candidate_k=candidate_k,
    )
    if ctx.fusion_mode == "weighted_scores":
        return weighted_score_fuse(
            dense,
            keyword,
            alpha=ctx.score_fusion_alpha,
            score_magnitude=ctx.weighted_fusion_magnitude,
        )
    return rrf_fuse(
        dense,
        keyword,
        rrf_k=int(ctx.rrf_k),
        dense_weight=float(ctx.dense_weight),
        keyword_weight=float(ctx.keyword_weight),
    )
