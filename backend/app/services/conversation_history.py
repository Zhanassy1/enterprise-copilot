"""Format prior session messages for RAG prompts (truncated, token-budgeted)."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.config import settings
from app.models.chat import ChatMessage
from app.services.usage_metering import estimate_tokens


def _truncate_chars(text: str, max_chars: int) -> str:
    s = (text or "").strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1].rstrip() + "…"


def format_prior_messages_for_rag(messages: list[ChatMessage]) -> str | None:
    """Turn DB messages into a compact Russian transcript; None if nothing to send."""
    max_msgs = settings.chat_history_max_messages
    budget = settings.chat_history_budget_tokens
    asst_max = settings.chat_history_assistant_max_chars
    user_max = settings.chat_history_user_max_chars

    if not messages:
        return None

    tail = messages[-max_msgs:]
    parts: list[str] = []
    for m in tail:
        role = (m.role or "").strip().lower()
        raw = m.content or ""
        if role == "assistant":
            body = _truncate_chars(raw, asst_max)
            parts.append(f"Ассистент: {body}")
        elif role == "user":
            body = _truncate_chars(raw, user_max)
            parts.append(f"Пользователь: {body}")
        else:
            continue

    while parts and estimate_tokens("\n\n".join(parts)) > budget:
        if len(parts) > 1:
            parts.pop(0)
            continue
        one = parts[0]
        n = len(one)
        if n <= 120:
            break
        parts[0] = _truncate_chars(one, max(120, int(n * 0.82)))

    text = "\n\n".join(parts).strip()
    return text or None


def load_prior_messages_for_rag(db, session_id: uuid.UUID) -> list[ChatMessage]:
    return list(
        db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        ).all()
    )
