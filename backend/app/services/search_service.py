from __future__ import annotations

import re
import uuid

from app.core.config import settings
from app.schemas.documents import SearchOut
from app.services.embeddings import embed_texts
from app.services.nlp import (
    build_answer,
    build_clarifying_question,
    build_next_step,
    decide_response_mode,
    is_penalty_intent,
    is_price_intent,
)
from app.services.reranker import rerank_hits
from app.services.vector_search import search_chunks_pgvector


def _compact_hit_text(text: str, query: str, *, price_intent: bool) -> str:
    if not text:
        return text
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return text[:800]

    q = (query or "").lower().strip()
    stems = {tok[:4] for tok in re.findall(r"[0-9A-Za-zА-Яа-яЁё]+", q) if len(tok) >= 3}
    penalty_intent = is_penalty_intent(query)
    price_markers = ("цена", "стоим", "тенге", "kzt", "руб", "usd")
    penalty_markers = ("пен", "неусто", "штраф", "просроч")

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
        if price_intent and any(ch.isdigit() for ch in line):
            return True
        return False

    matched = [ln for ln in lines if keep_line(ln)]
    if matched:
        return "\n".join(matched[:12])[:1200]
    return "\n".join(lines[:8])[:800]


class SearchService:
    def __init__(self, db) -> None:
        self.db = db

    def search(self, *, workspace_id: uuid.UUID, user_id: uuid.UUID, query: str, top_k: int) -> SearchOut:
        from app.services.usage_metering import (
            EVENT_RERANK_CALL,
            EVENT_SEARCH_REQUEST,
            EVENT_TOKENS,
            assert_quota,
            estimate_tokens,
            record_event,
        )

        query_tokens = estimate_tokens(query)
        assert_quota(
            self.db,
            workspace_id=workspace_id,
            request_increment=1,
            token_increment=query_tokens,
        )
        price_intent = is_price_intent(query)
        qvec = embed_texts([query])[0]
        hits = search_chunks_pgvector(
            self.db,
            workspace_id=workspace_id,
            query_text=query,
            query_embedding=qvec,
            top_k=max(top_k, int(settings.reranker_top_n)),
        )
        if settings.reranker_enabled:
            assert_quota(self.db, workspace_id=workspace_id, rerank_increment=1)
        hits = rerank_hits(query, hits, top_n=int(settings.reranker_top_n))
        hits = hits[: int(top_k)]
        for h in hits:
            h["text"] = _compact_hit_text(str(h.get("text") or ""), query, price_intent=price_intent)

        decision, confidence = decide_response_mode(
            query,
            hits,
            answer_threshold=settings.answer_threshold,
            clarify_threshold=settings.clarify_threshold,
        )
        details: str | None = None
        clarifying_question: str | None = None
        if decision == "answer":
            answer = build_answer(query, hits)
            details = "Ответ сформирован строго по найденным фрагментам документов."
        else:
            answer = ""
            clarifying_question = build_clarifying_question(query)
        next_step = build_next_step(decision)
        output_tokens = estimate_tokens(answer or clarifying_question or "")
        assert_quota(
            self.db,
            workspace_id=workspace_id,
            token_increment=output_tokens,
        )
        record_event(
            self.db,
            workspace_id=workspace_id,
            user_id=user_id,
            event_type=EVENT_SEARCH_REQUEST,
            quantity=1,
            unit="count",
            metadata={"top_k": int(top_k)},
        )
        if settings.reranker_enabled:
            record_event(
                self.db,
                workspace_id=workspace_id,
                user_id=user_id,
                event_type=EVENT_RERANK_CALL,
                quantity=1,
                unit="count",
                metadata={"scope": "search"},
            )
        record_event(
            self.db,
            workspace_id=workspace_id,
            user_id=user_id,
            event_type=EVENT_TOKENS,
            quantity=query_tokens + output_tokens,
            unit="tokens",
            metadata={"scope": "search"},
        )
        self.db.commit()
        return SearchOut(
            answer=answer,
            details=details,
            decision=decision,
            confidence=confidence,
            clarifying_question=clarifying_question,
            next_step=next_step,
            evidence_collapsed_by_default=True,
            hits=hits,
        )
