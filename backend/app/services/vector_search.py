"""
Vector / keyword retrieval uses SQLAlchemy ``text()`` with bound parameters only
(``:workspace_id``, ``:qtext``, ``:candidate_k``, ``:qvec``). No user-controlled
fragments are interpolated into SQL strings.

Pipeline: :mod:`generic_hybrid` (dense + keyword + RRF) → :mod:`domain_rules`
(heuristics, intent pools, dedup).
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.nlp import expand_query
from app.services.retrieval.domain_rules import apply_domain_retrieval_rules
from app.services.retrieval.generic_hybrid import hybrid_fuse_candidates
from app.services.retrieval.tuning import build_retrieval_context, candidate_k_for_context


def search_chunks_pgvector(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    query_text: str,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    """
    Requires pgvector + a `document_chunks.embedding_vector vector(<dim>)` column.
    Returns: [{document_id, chunk_id, chunk_index, text, score}]
    """
    expanded_query = expand_query(query_text)
    rctx = build_retrieval_context(query_text)
    candidate_k = candidate_k_for_context(top_k=int(top_k), ctx=rctx)
    fused = hybrid_fuse_candidates(
        db,
        workspace_id=workspace_id,
        query_text_expanded=expanded_query,
        query_embedding=query_embedding,
        candidate_k=candidate_k,
        retrieval_ctx=rctx,
    )
    return apply_domain_retrieval_rules(
        query_text=query_text,
        fused_rows=fused,
        top_k=top_k,
    )
