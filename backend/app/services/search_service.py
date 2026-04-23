from __future__ import annotations

import uuid

from app.core.config import settings
from app.schemas.documents import AnswerStyle, SearchOut
from app.services.embeddings import embed_texts
from app.services.nlp import (
    build_answer_with_provenance,
    build_clarifying_question,
    build_next_step,
    decide_response_mode,
    resolve_answer_style,
    suggest_citation_index_to_chunk,
)
from app.services.rag_retrieval import retrieve_ranked_hits
from app.services.retrieval.query_input import normalize_search_query_for_retrieval


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
            EVENT_EMBEDDING_TOKENS,
            EVENT_GENERATION_TOKENS,
            EVENT_SEARCH_REQUEST,
            assert_quota,
            estimate_tokens,
            record_event,
        )

        query = normalize_search_query_for_retrieval(query)
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
        ev_ids: list[uuid.UUID] = []
        cit_map: dict[str, str] | None = None
        if decision == "answer":
            answer, ev_ids = build_answer_with_provenance(query, hits, answer_style=resolved_style)
            cit_map = suggest_citation_index_to_chunk(answer, hits)
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
            event_type=EVENT_EMBEDDING_TOKENS,
            quantity=query_tokens,
            unit="tokens",
            metadata={"scope": "search"},
        )
        record_event(
            self.db,
            workspace_id=workspace_id,
            user_id=user_id,
            event_type=EVENT_GENERATION_TOKENS,
            quantity=output_tokens,
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
            evidence_chunk_ids=ev_ids,
            citation_index_to_chunk_id=cit_map,
        )
