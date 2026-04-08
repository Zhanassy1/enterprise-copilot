from __future__ import annotations

import uuid

from app.core.config import settings
from app.schemas.documents import AnswerStyle, SearchOut
from app.services.embeddings import embed_texts
from app.services.nlp import (
    build_answer,
    build_clarifying_question,
    build_next_step,
    decide_response_mode,
    resolve_answer_style,
)
from app.services.rag_retrieval import retrieve_ranked_hits


class SearchService:
    def __init__(self, db) -> None:
        self.db = db

    def search(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        query: str,
        top_k: int,
        answer_style: AnswerStyle | None = None,
    ) -> SearchOut:
        from app.services.usage_metering import (
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
            user_id=user_id,
            request_increment=1,
            token_increment=query_tokens,
        )
        qvec = embed_texts([query])[0]
        hits = retrieve_ranked_hits(
            self.db,
            workspace_id=workspace_id,
            user_id=user_id,
            query=query,
            query_embedding=qvec,
            top_k=top_k,
            compact_snippets=True,
        )

        decision, confidence = decide_response_mode(
            query,
            hits,
            answer_threshold=settings.answer_threshold,
            clarify_threshold=settings.clarify_threshold,
        )
        resolved_style = resolve_answer_style(answer_style, settings.default_answer_style)
        details: str | None = None
        clarifying_question: str | None = None
        if decision == "answer":
            answer = build_answer(query, hits, answer_style=resolved_style)
            details = "Ответ сформирован строго по найденным фрагментам документов."
        else:
            answer = ""
            clarifying_question = build_clarifying_question(query)
        next_step = build_next_step(decision)
        output_tokens = estimate_tokens(answer or clarifying_question or "")
        assert_quota(
            self.db,
            workspace_id=workspace_id,
            user_id=user_id,
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
            evidence_collapsed_by_default=(resolved_style == "narrative"),
            answer_style=resolved_style,
            hits=hits,
        )
