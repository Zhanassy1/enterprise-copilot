"""
Shared RAG retrieval: pgvector hybrid search, cross-encoder rerank, quotas, optional snippet compaction.
Used by search and chat so both follow the same ranking pipeline.
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.nlp import (
    PENALTY_LINE_MARKERS,
    PRICE_LINE_MARKERS,
    TERMINATION_LINE_MARKERS,
    adjust_hit_scores_for_contract_value_query,
    is_contract_value_query,
    is_penalty_intent,
    is_price_intent,
    is_termination_intent,
    reorder_hits_for_contract_value_query,
    text_has_contract_value_signal,
    text_has_monetary_amount,
)
from app.services.reranker import rerank_hits
from app.services.usage_metering import EVENT_RERANK, assert_quota, record_event
from app.services.vector_search import search_chunks_pgvector


def compact_hit_text(text: str, query: str, *, price_intent: bool) -> str:
    """Narrow hit text to query-relevant lines (same logic as legacy search UI)."""
    if not text:
        return text
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return text[:800]

    q = (query or "").lower().strip()
    stems = {tok[:4] for tok in re.findall(r"[0-9A-Za-zА-Яа-яЁё]+", q) if len(tok) >= 3}
    penalty_intent = is_penalty_intent(query)
    termination_intent = is_termination_intent(query)
    price_markers = PRICE_LINE_MARKERS
    penalty_markers = PENALTY_LINE_MARKERS
    termination_markers = TERMINATION_LINE_MARKERS

    def keep_line(line: str) -> bool:
        low = line.lower()
        if q and q in low:
            return True
        if stems and any(s in low for s in stems):
            return True
        if price_intent and any(m in low for m in price_markers):
            return True
        if penalty_intent and any(m in low for m in penalty_markers):
            return True
        if termination_intent and any(m in low for m in termination_markers):
            return True
        if price_intent and text_has_monetary_amount(line):
            return True
        return False

    matched = [ln for ln in lines if keep_line(ln)]
    if matched:
        if price_intent and is_contract_value_query(query):
            pri = [
                ln
                for ln in matched
                if text_has_contract_value_signal(ln) and text_has_monetary_amount(ln)
            ]
            rest = [ln for ln in matched if ln not in pri]
            ordered = pri + rest
            return "\n".join(ordered[:12])[:1200]
        return "\n".join(matched[:12])[:1200]
    return "\n".join(lines[:8])[:800]


def retrieve_ranked_hits(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    query: str,
    query_embedding: list[float],
    top_k: int,
    compact_snippets: bool = True,
) -> list[dict]:
    """
    Retrieve hybrid candidates, rerank with the same settings as /search, enforce rerank quota when enabled,
    then return the top ``top_k`` hits (after optional snippet compaction).
    """
    price_intent = is_price_intent(query)
    effective_k = max(int(top_k), int(settings.reranker_top_n))
    hits = search_chunks_pgvector(
        db,
        workspace_id=workspace_id,
        query_text=query,
        query_embedding=query_embedding,
        top_k=effective_k,
    )
    hits = rerank_hits(query, hits, top_n=int(settings.reranker_top_n))
    if settings.reranker_enabled:
        assert_quota(
            db,
            workspace_id=workspace_id,
            user_id=user_id,
            rerank_increment=1,
        )
        record_event(
            db,
            workspace_id=workspace_id,
            user_id=user_id,
            event_type=EVENT_RERANK,
            quantity=1,
            unit="count",
            metadata={"top_n": int(settings.reranker_top_n), "candidates": len(hits)},
        )
    hits = hits[: int(top_k)]
    if compact_snippets:
        for h in hits:
            h["text"] = compact_hit_text(str(h.get("text") or ""), query, price_intent=price_intent)
    if is_contract_value_query(query):
        hits = reorder_hits_for_contract_value_query(hits)
        adjust_hit_scores_for_contract_value_query(hits)
    return hits
