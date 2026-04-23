"""
Shared RAG retrieval: pgvector hybrid search, cross-encoder rerank, quotas, optional snippet compaction.
Used by search and chat so both follow the same ranking pipeline.

Stages: vector search (generic + domain rules) → cross-encoder rerank → snippet compaction → contract-value post-rules.
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
    text_suggests_security_deposit_without_contract_value,
)
from app.services.reranker import rerank_hits
from app.services.retrieval.query_input import normalize_search_query_for_retrieval
from app.services.usage_metering import EVENT_RERANK, assert_quota, record_event
from app.services.vector_search import search_chunks_pgvector


def _trim_leading_mid_word_line(line: str) -> str:
    """If a line starts with a short lowercase fragment (chunk boundary), drop the first token."""
    s = line.strip()
    if not s or not s[0].islower():
        return line
    parts = s.split(None, 1)
    if len(parts) == 2 and parts[0].isalpha() and len(parts[0]) <= 6:
        return parts[1]
    return line


def _trim_compact_snippet_mid_word_prefix(text: str) -> str:
    if not (text or "").strip():
        return text
    lines = text.split("\n")
    lines[0] = _trim_leading_mid_word_line(lines[0])
    return "\n".join(lines)


def compact_hit_text(text: str, query: str, *, price_intent: bool) -> str:
    """Narrow hit text to query-relevant lines (same logic as legacy search UI)."""
    if not text:
        return text
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return _trim_compact_snippet_mid_word_prefix(text[:800])

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
            cv_lines = [
                ln
                for ln in matched
                if not text_suggests_security_deposit_without_contract_value(ln)
            ]
            if not cv_lines:
                cv_lines = [
                    ln
                    for ln in lines
                    if ln.strip() and not text_suggests_security_deposit_without_contract_value(ln)
                ]
            if not cv_lines:
                cv_lines = matched
            pri = [
                ln
                for ln in cv_lines
                if text_has_contract_value_signal(ln) and text_has_monetary_amount(ln)
            ]
            rest = [ln for ln in cv_lines if ln not in pri]
            ordered = pri + rest
            return _trim_compact_snippet_mid_word_prefix("\n".join(ordered[:12])[:1200])
        return _trim_compact_snippet_mid_word_prefix("\n".join(matched[:12])[:1200])
    return _trim_compact_snippet_mid_word_prefix("\n".join(lines[:8])[:800])


def retrieve_vector_search_hits(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    query: str,
    query_embedding: list[float],
    top_k: int,
) -> list[dict]:
    """Stage 1: hybrid pgvector retrieval + domain rules (no rerank, no snippet compaction)."""
    return search_chunks_pgvector(
        db,
        workspace_id=workspace_id,
        query_text=query,
        query_embedding=query_embedding,
        top_k=top_k,
    )


def run_cross_encoder_rerank(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    query: str,
    hits: list[dict],
    top_k: int,
) -> list[dict]:
    """
    Stage 2: optional cross-encoder rerank with quota + audit event.

    Returns ``hits`` unchanged when ``reranker_enabled`` is false, ``top_k == 0``, or
    there is at most one candidate (no ``rerank_hits``, no rerank quota, no ``EVENT_RERANK``).
    """
    will_rerank = settings.reranker_enabled and int(top_k) > 0 and len(hits) > 1
    if will_rerank:
        assert_quota(
            db,
            workspace_id=workspace_id,
            user_id=user_id,
            rerank_increment=1,
        )
        hits = rerank_hits(query, hits, top_n=int(settings.reranker_top_n))
        record_event(
            db,
            workspace_id=workspace_id,
            user_id=user_id,
            event_type=EVENT_RERANK,
            quantity=1,
            unit="count",
            metadata={"top_n": int(settings.reranker_top_n), "candidates": len(hits)},
        )
    return hits


def apply_snippet_compaction(hits: list[dict], query: str, *, price_intent: bool) -> None:
    """Stage 3: mutate hit text in place for UI/prompt compactness."""
    for h in hits:
        h["text"] = compact_hit_text(str(h.get("text") or ""), query, price_intent=price_intent)


def apply_contract_value_post_rank_rules_for_query(query: str, hits: list[dict]) -> list[dict]:
    """Reorder and adjust scores for contract-value queries."""
    if not is_contract_value_query(query):
        return hits
    hits = reorder_hits_for_contract_value_query(hits)
    adjust_hit_scores_for_contract_value_query(hits)
    return hits


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
    Full pipeline: vector search → rerank → optional snippet compaction → contract-value rules.

    When reranking is enabled, ``assert_quota`` for rerank runs before ``rerank_hits``;
    ``EVENT_RERANK`` is recorded only after a successful rerank. With reranking disabled,
    or when ``top_k == 0`` or there is at most one candidate, skips ``rerank_hits`` and
    rerank quota.
    """
    query = normalize_search_query_for_retrieval(query)
    price_intent = is_price_intent(query)
    effective_k = max(int(top_k), int(settings.reranker_top_n))
    hits = retrieve_vector_search_hits(
        db,
        workspace_id=workspace_id,
        query=query,
        query_embedding=query_embedding,
        top_k=effective_k,
    )
    hits = run_cross_encoder_rerank(
        db,
        workspace_id=workspace_id,
        user_id=user_id,
        query=query,
        hits=hits,
        top_k=int(top_k),
    )
    hits = hits[: int(top_k)]
    if compact_snippets:
        apply_snippet_compaction(hits, query, price_intent=price_intent)
    hits = apply_contract_value_post_rank_rules_for_query(query, hits)
    return hits
