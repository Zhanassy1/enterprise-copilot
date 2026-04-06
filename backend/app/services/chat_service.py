from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.models.chat import ChatMessage, ChatSession
from app.schemas.chat import (
    ChatMessageOut,
    ChatReplyOut,
    ChatSessionOut,
)
from app.schemas.documents import SearchHit
from app.services.conversation_history import (
    format_prior_messages_for_rag,
    load_prior_messages_for_rag,
)
from app.services.embeddings import embed_texts
from app.services.nlp import (
    build_answer,
    build_clarifying_question,
    build_next_step,
    compose_response_text,
    decide_response_mode,
    filter_ungrounded_sentences,
    parse_reply_meta,
    serialize_reply_meta,
)
from app.services.rag_retrieval import retrieve_ranked_hits
from app.services.usage_metering import (
    EVENT_CHAT_MESSAGE,
    EVENT_TOKENS,
    assert_quota,
    estimate_tokens,
    record_event,
)

logger = logging.getLogger(__name__)

_SSE_CHUNK = 24


def _sse_event(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _yield_string_chunks(text: str, size: int = _SSE_CHUNK):
    t = text or ""
    if not t:
        return
    for i in range(0, len(t), size):
        yield t[i : i + size]


def _hit_for_source_event(h: dict) -> dict:
    return {
        "document_id": str(h.get("document_id")),
        "chunk_id": str(h.get("chunk_id")),
        "chunk_index": int(h.get("chunk_index") or 0),
        "text": str(h.get("text") or ""),
        "score": float(h.get("score") or 0.0),
    }


def _to_session_out(session: ChatSession) -> ChatSessionOut:
    return ChatSessionOut(id=session.id, title=session.title, created_at=session.created_at, updated_at=session.updated_at)


def _to_message_out(message: ChatMessage) -> ChatMessageOut:
    raw = message.sources_json or "[]"
    try:
        loaded = json.loads(raw)
        sources = [SearchHit(**x) for x in loaded if isinstance(x, dict)]
    except Exception as e:
        logger.warning("failed to parse sources_json for message %s: %s", message.id, e)
        sources = []
    details, next_step, clarifying_question, decision = parse_reply_meta(message.reply_meta_json)
    return ChatMessageOut(
        id=message.id,
        session_id=message.session_id,
        role=message.role,
        content=message.content,
        sources=sources,
        created_at=message.created_at,
        details=details,
        next_step=next_step,
        clarifying_question=clarifying_question,
        decision=decision,
    )


class ChatService:
    def __init__(self, db) -> None:
        self.db = db

    def list_sessions(self, workspace_id: uuid.UUID) -> list[ChatSessionOut]:
        rows = self.db.scalars(
            select(ChatSession).where(ChatSession.workspace_id == workspace_id).order_by(ChatSession.updated_at.desc())
        ).all()
        return [_to_session_out(x) for x in rows]

    def create_session(self, workspace_id: uuid.UUID, owner_id: uuid.UUID, title: str | None) -> ChatSessionOut:
        normalized_title = (title or "").strip() or "Новый чат"
        session = ChatSession(owner_id=owner_id, workspace_id=workspace_id, title=normalized_title)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return _to_session_out(session)

    def list_messages(self, workspace_id: uuid.UUID, session_id: uuid.UUID) -> list[ChatMessageOut]:
        session = self.db.scalar(
            select(ChatSession).where(ChatSession.id == session_id, ChatSession.workspace_id == workspace_id)
        )
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        rows = self.db.scalars(select(ChatMessage).where(ChatMessage.session_id == session.id).order_by(ChatMessage.created_at.asc())).all()
        return [_to_message_out(x) for x in rows]

    def send_message(self, workspace_id: uuid.UUID, user_id: uuid.UUID, session_id: uuid.UUID, message: str, top_k: int) -> ChatReplyOut:
        session = self.db.scalar(
            select(ChatSession).where(ChatSession.id == session_id, ChatSession.workspace_id == workspace_id)
        )
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        prior_rows = load_prior_messages_for_rag(self.db, session.id)
        conversation_history = format_prior_messages_for_rag(prior_rows)
        query_tokens = estimate_tokens(message)
        assert_quota(
            self.db,
            workspace_id=workspace_id,
            user_id=user_id,
            request_increment=1,
            token_increment=query_tokens,
        )

        qvec = embed_texts([message])[0]
        hits = retrieve_ranked_hits(
            self.db,
            workspace_id=workspace_id,
            user_id=user_id,
            query=message,
            query_embedding=qvec,
            top_k=top_k,
            compact_snippets=True,
        )
        decision, confidence = decide_response_mode(
            message,
            hits,
            answer_threshold=settings.answer_threshold,
            clarify_threshold=settings.clarify_threshold,
        )
        details: str | None = None
        clarifying_question: str | None = None
        if decision == "answer":
            answer = build_answer(message, hits, conversation_history=conversation_history)
            details = "Ответ подтвержден найденными фрагментами документов."
        else:
            answer = ""
            clarifying_question = build_clarifying_question(message)
        next_step = build_next_step(decision)
        assistant_content = compose_response_text(
            decision=decision,
            answer=answer,
            details=details,
            clarifying_question=clarifying_question,
            next_step=next_step,
        )
        output_tokens = estimate_tokens(assistant_content)
        assert_quota(
            self.db,
            workspace_id=workspace_id,
            user_id=user_id,
            token_increment=output_tokens,
        )

        user_msg = ChatMessage(session_id=session.id, role="user", content=message, sources_json="[]")
        assistant_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=assistant_content,
            reply_meta_json=serialize_reply_meta(
                decision=decision,
                details=details,
                next_step=next_step,
                clarifying_question=clarifying_question,
            ),
            sources_json=json.dumps(hits, ensure_ascii=False, default=str),
        )
        self.db.add(user_msg)
        self.db.add(assistant_msg)
        session.updated_at = datetime.now(UTC)
        self.db.add(session)
        record_event(
            self.db,
            workspace_id=workspace_id,
            user_id=user_id,
            event_type=EVENT_CHAT_MESSAGE,
            quantity=1,
            unit="count",
            metadata={"session_id": str(session.id), "top_k": int(top_k)},
        )
        record_event(
            self.db,
            workspace_id=workspace_id,
            user_id=user_id,
            event_type=EVENT_TOKENS,
            quantity=query_tokens + output_tokens,
            unit="tokens",
            metadata={"scope": "chat", "session_id": str(session.id)},
        )
        self.db.commit()
        self.db.refresh(session)
        self.db.refresh(user_msg)
        self.db.refresh(assistant_msg)

        return ChatReplyOut(
            session=_to_session_out(session),
            user_message=_to_message_out(user_msg),
            assistant_message=_to_message_out(assistant_msg),
            decision=decision,
            confidence=confidence,
            details=details,
            clarifying_question=clarifying_question,
            next_step=next_step,
            evidence_collapsed_by_default=True,
        )

    def iter_chat_sse(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        message: str,
        top_k: int,
    ):
        """Yield Server-Sent Event lines (``data: …\\n\\n``) for chat reply streaming."""
        from app.services.llm import llm_enabled, rag_answer_stream

        session = self.db.scalar(
            select(ChatSession).where(ChatSession.id == session_id, ChatSession.workspace_id == workspace_id)
        )
        if not session:
            yield _sse_event({"type": "error", "content": "Chat session not found"})
            return

        try:
            query_tokens = estimate_tokens(message)
            assert_quota(
                self.db,
                workspace_id=workspace_id,
                user_id=user_id,
                request_increment=1,
                token_increment=query_tokens,
            )

            prior_rows = load_prior_messages_for_rag(self.db, session.id)
            conversation_history = format_prior_messages_for_rag(prior_rows)

            qvec = embed_texts([message])[0]
            hits = retrieve_ranked_hits(
                self.db,
                workspace_id=workspace_id,
                user_id=user_id,
                query=message,
                query_embedding=qvec,
                top_k=top_k,
                compact_snippets=True,
            )
            decision, _confidence = decide_response_mode(
                message,
                hits,
                answer_threshold=settings.answer_threshold,
                clarify_threshold=settings.clarify_threshold,
            )
        except HTTPException as e:
            msg = e.detail if isinstance(e.detail, str) else str(e.detail)
            yield _sse_event({"type": "error", "content": msg})
            return
        except Exception as e:
            logger.exception("chat stream setup failed: %s", e)
            yield _sse_event({"type": "error", "content": str(e) or "chat stream failed"})
            return

        details: str | None = None
        clarifying_question: str | None = None
        raw_llm_body = ""

        try:
            if decision == "answer":
                details = "Ответ подтвержден найденными фрагментами документов."
                next_step = build_next_step(decision)
                chunks_text = [str(h.get("text") or "") for h in hits[:6] if h.get("text")]

                if llm_enabled() and chunks_text:
                    try:
                        for delta in rag_answer_stream(
                            message, chunks_text, conversation_history=conversation_history
                        ):
                            raw_llm_body += delta
                            yield _sse_event({"type": "token", "content": delta})
                    except Exception as e:
                        logger.warning("rag stream interrupted: %s", e)
                    answer = filter_ungrounded_sentences(raw_llm_body.strip(), message, hits) if raw_llm_body.strip() else ""
                    if not answer and raw_llm_body.strip():
                        answer = "Недостаточно данных в предоставленных документах."
                    if not answer:
                        answer = build_answer(message, hits, conversation_history=conversation_history)
                        for part in _yield_string_chunks(answer):
                            yield _sse_event({"type": "token", "content": part})
                else:
                    answer = build_answer(message, hits, conversation_history=conversation_history)
                    for part in _yield_string_chunks(answer):
                        yield _sse_event({"type": "token", "content": part})

                assistant_content = compose_response_text(
                    decision=decision,
                    answer=answer,
                    details=details,
                    clarifying_question=clarifying_question,
                    next_step=next_step,
                )
            else:
                answer = ""
                clarifying_question = build_clarifying_question(message)
                next_step = build_next_step(decision)
                assistant_content = compose_response_text(
                    decision=decision,
                    answer=answer,
                    details=None,
                    clarifying_question=clarifying_question,
                    next_step=next_step,
                )
                for part in _yield_string_chunks(assistant_content):
                    yield _sse_event({"type": "token", "content": part})

            output_tokens = estimate_tokens(assistant_content)
            try:
                assert_quota(
                    self.db,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    token_increment=output_tokens,
                )
            except HTTPException as e:
                self.db.rollback()
                msg = e.detail if isinstance(e.detail, str) else str(e.detail)
                yield _sse_event({"type": "error", "content": msg})
                return

            user_msg = ChatMessage(session_id=session.id, role="user", content=message, sources_json="[]")
            assistant_msg = ChatMessage(
                session_id=session.id,
                role="assistant",
                content=assistant_content,
                reply_meta_json=serialize_reply_meta(
                    decision=decision,
                    details=details,
                    next_step=next_step,
                    clarifying_question=clarifying_question,
                ),
                sources_json=json.dumps(hits, ensure_ascii=False, default=str),
            )
            self.db.add(user_msg)
            self.db.add(assistant_msg)
            session.updated_at = datetime.now(UTC)
            self.db.add(session)
            record_event(
                self.db,
                workspace_id=workspace_id,
                user_id=user_id,
                event_type=EVENT_CHAT_MESSAGE,
                quantity=1,
                unit="count",
                metadata={"session_id": str(session.id), "top_k": int(top_k), "stream": True},
            )
            record_event(
                self.db,
                workspace_id=workspace_id,
                user_id=user_id,
                event_type=EVENT_TOKENS,
                quantity=query_tokens + output_tokens,
                unit="tokens",
                metadata={"scope": "chat", "session_id": str(session.id), "stream": True},
            )
            self.db.commit()
            self.db.refresh(user_msg)
            self.db.refresh(assistant_msg)

            for h in hits:
                yield _sse_event({"type": "source", "content": _hit_for_source_event(h)})

            yield _sse_event({"type": "done", "content": ""})
        except HTTPException as e:
            self.db.rollback()
            msg = e.detail if isinstance(e.detail, str) else str(e.detail)
            yield _sse_event({"type": "error", "content": msg})
        except Exception as e:
            self.db.rollback()
            logger.exception("chat stream persist failed: %s", e)
            yield _sse_event({"type": "error", "content": str(e) or "chat stream failed"})
