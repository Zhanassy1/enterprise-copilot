from __future__ import annotations

import logging

from app.core.config import settings
from app.core.settings.llm import AnswerStyle
from app.services.nlp import is_advisory_intent, is_contract_value_query, is_price_intent
from app.services.prompt_templates import (
    RAG_ADVISORY_SUFFIX,
    RAG_CONTRACT_VALUE_SUFFIX,
    RAG_PRICE_FOCUS_SUFFIX,
    RAG_PRICE_NARRATIVE_SUFFIX,
    RAG_SYSTEM_PROMPT,
    SUMMARY_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

_client = None

# Returned by llm_chat when the API key is missing or the upstream call fails (no document context).
LLM_SERVICE_UNAVAILABLE_RU = (
    "Генерация ответа языковой моделью сейчас недоступна (нет ключа API или ошибка сервиса)."
)

_FALLBACK_CHUNK_SIZE = 24


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(
            api_key=settings.llm_api_key or "not-set",
            base_url=settings.llm_base_url,
            timeout=settings.llm_request_timeout_seconds,
        )
    return _client


def llm_enabled() -> bool:
    return bool(settings.llm_api_key)


def _yield_text_chunks(text: str, *, size: int = _FALLBACK_CHUNK_SIZE):
    t = text or ""
    if not t:
        return
    for i in range(0, len(t), size):
        yield t[i : i + size]


def _extractive_fallback_answer(
    query: str,
    context_chunks: list[str],
    *,
    answer_style: AnswerStyle = "concise",
) -> str:
    from app.services.nlp import _answer_extractive

    hits = [{"text": c} for c in context_chunks if c]
    return _answer_extractive(query, hits, answer_style=answer_style)


def llm_chat_stream(
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int = 1024,
):
    """Yield text deltas from OpenAI chat completions (streaming)."""
    if not llm_enabled():
        return
    client = _get_client()
    stream = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=settings.llm_temperature,
        max_tokens=max_tokens,
        stream=True,
        timeout=settings.llm_request_timeout_seconds,
    )
    try:
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
    except Exception as e:
        logger.error("LLM stream failed: %s", e)
        raise


def llm_chat(
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int = 1024,
) -> str:
    if not llm_enabled():
        return LLM_SERVICE_UNAVAILABLE_RU

    client = _get_client()
    try:
        resp = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=settings.llm_temperature,
            max_tokens=max_tokens,
            timeout=settings.llm_request_timeout_seconds,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return LLM_SERVICE_UNAVAILABLE_RU


def _rag_system_prompt(
    query: str,
    *,
    answer_style: AnswerStyle = "concise",
    advisory: bool = False,
) -> str:
    if advisory:
        return f"{RAG_SYSTEM_PROMPT} {RAG_ADVISORY_SUFFIX}"
    if is_price_intent(query):
        parts = [RAG_SYSTEM_PROMPT]
        if answer_style == "narrative":
            parts.append(RAG_PRICE_NARRATIVE_SUFFIX)
        else:
            parts.append(RAG_PRICE_FOCUS_SUFFIX)
        if is_contract_value_query(query):
            parts.append(RAG_CONTRACT_VALUE_SUFFIX)
        return " ".join(parts)
    return RAG_SYSTEM_PROMPT


def _rag_user_prompt(query: str, context: str, *, conversation_history: str | None) -> str:
    if conversation_history:
        return (
            f"История диалога (кратко):\n\n{conversation_history}\n\n---\n\n"
            f"Контекст из документов:\n\n{context}\n\n---\n\n"
            f"Текущий вопрос:\n{query}"
        )
    return f"Контекст из документов:\n\n{context}\n\n---\n\nВопрос пользователя: {query}"


def rag_answer(
    query: str,
    context_chunks: list[str],
    *,
    conversation_history: str | None = None,
    answer_style: AnswerStyle = "concise",
    advisory: bool | None = None,
) -> str:
    """Generate a RAG answer from retrieved chunks. Falls back to extractive if LLM is off or fails."""
    if not context_chunks:
        return "По загруженным документам релевантной информации не найдено."

    adv = is_advisory_intent(query) if advisory is None else advisory
    context = "\n\n---\n\n".join(context_chunks[:8])

    if not llm_enabled():
        return _extractive_fallback_answer(query, context_chunks, answer_style=answer_style)

    system = _rag_system_prompt(query, answer_style=answer_style, advisory=adv)
    user = _rag_user_prompt(query, context, conversation_history=conversation_history)
    max_tok = 1536 if adv else 1024
    out = llm_chat(system, user, max_tokens=max_tok)
    if not out or out == LLM_SERVICE_UNAVAILABLE_RU:
        return _extractive_fallback_answer(query, context_chunks, answer_style=answer_style)
    return out


def rag_answer_stream(
    query: str,
    context_chunks: list[str],
    *,
    conversation_history: str | None = None,
    answer_style: AnswerStyle = "concise",
    advisory: bool | None = None,
):
    """Stream RAG tokens from the LLM, or chunked extractive text if LLM is off or errors."""
    if not context_chunks:
        return

    adv = is_advisory_intent(query) if advisory is None else advisory
    context = "\n\n---\n\n".join(context_chunks[:8])
    system = _rag_system_prompt(query, answer_style=answer_style, advisory=adv)
    user = _rag_user_prompt(query, context, conversation_history=conversation_history)
    max_tok = 1536 if adv else 1024

    def _yield_extractive_stream() -> None:
        text = _extractive_fallback_answer(query, context_chunks, answer_style=answer_style)
        yield from _yield_text_chunks(text)

    if not llm_enabled():
        yield from _yield_extractive_stream()
        return

    try:
        yield from llm_chat_stream(system, user, max_tokens=max_tok)
    except Exception:
        logger.warning("rag_answer_stream: falling back to extractive after LLM stream failure")
        yield from _yield_extractive_stream()


def llm_summarize(text: str) -> str:
    """Generate an LLM-based summary. Returns empty string if LLM is not configured or call failed."""
    if not llm_enabled():
        return ""

    truncated = text[: settings.llm_max_context_tokens * 3]

    system = SUMMARY_SYSTEM_PROMPT

    user = f"Документ:\n\n{truncated}"

    out = llm_chat(system, user, max_tokens=1024)
    if out == LLM_SERVICE_UNAVAILABLE_RU:
        return ""
    return out


_FAITHFULNESS_JUDGE_SYSTEM = (
    "Ты оценщик RAG-ответа. Сравни ответ с цитатами дословно: каждое сущностное "
    "утверждение в ответе должно вытекать из фрагментов.\n"
    "Верни ровно одну строку формата: `faithfulness=0.00 completeness=0.00` — числа от 0 до 1. "
    "faithfulness: нет фактов вне evidence. completeness: вопрос закрыт в пределах evidence."
)


def answer_quality_judge_scores(
    query: str,
    answer: str,
    evidence: str,
) -> tuple[float | None, float | None]:
    """
    Optional LLM-as-judge (temperature 0). Returns (faithfulness, completeness) in [0,1] or (None, None).
    For offline / nightly use with synthetic gold, not for deterministic CI.
    """
    if not llm_enabled() or not (answer or "").strip():
        return None, None
    import re

    user = (
        f"Вопрос:\n{query}\n\n"
        f"Фрагменты (доказательная база):\n{evidence[:12000]}\n\n"
        f"Ответ ассистента:\n{answer[:8000]}"
    )
    client = _get_client()
    try:
        resp = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": _FAITHFULNESS_JUDGE_SYSTEM},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
            max_tokens=64,
            timeout=settings.llm_request_timeout_seconds,
        )
        raw = (resp.choices[0].message.content or "").strip()
    except Exception as e:  # pragma: no cover - network
        logger.warning("answer_quality_judge_scores failed: %s", e)
        return None, None

    m1 = re.search(r"faithfulness\s*=\s*([0-1](?:\.\d+)?)", raw, re.I)
    m2 = re.search(r"completeness\s*=\s*([0-1](?:\.\d+)?)", raw, re.I)
    f_v = float(m1.group(1)) if m1 else None
    c_v = float(m2.group(1)) if m2 else None
    if f_v is not None:
        f_v = min(1.0, max(0.0, f_v))
    if c_v is not None:
        c_v = min(1.0, max(0.0, c_v))
    return f_v, c_v
