from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(
            api_key=settings.llm_api_key or "not-set",
            base_url=settings.llm_base_url,
        )
    return _client


def llm_enabled() -> bool:
    return bool(settings.llm_api_key)


def llm_chat(
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int = 1024,
) -> str:
    if not llm_enabled():
        return ""

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
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return ""


def rag_answer(query: str, context_chunks: list[str]) -> str:
    """Generate a RAG answer from retrieved chunks. Falls back to extractive if no LLM key."""
    if not context_chunks:
        return "По загруженным документам релевантной информации не найдено."

    if not llm_enabled():
        return ""

    context = "\n\n---\n\n".join(context_chunks[: 8])

    system = (
        "Ты — AI-ассистент для анализа бизнес-документов. "
        "Отвечай на русском языке, строго по делу и только на основе предоставленного контекста. "
        "Нельзя добавлять предположения, внешние знания и общие фразы. "
        "Если факт нельзя подтвердить контекстом, не включай его в ответ. "
        "Если данных недостаточно, ответь ровно: 'Недостаточно данных в предоставленных документах.' "
        "Формат ответа: 1-2 коротких абзаца без списков, максимум 5 предложений."
    )

    user = f"Контекст из документов:\n\n{context}\n\n---\n\nВопрос пользователя: {query}"

    return llm_chat(system, user, max_tokens=1024)


def llm_summarize(text: str) -> str:
    """Generate an LLM-based summary. Returns empty string if LLM is not configured."""
    if not llm_enabled():
        return ""

    truncated = text[:settings.llm_max_context_tokens * 3]

    system = (
        "Ты — AI-ассистент для анализа бизнес-документов. "
        "Составь краткое структурированное резюме документа на русском языке. "
        "Выдели: тип документа, стороны, ключевые условия (суммы, сроки, обязательства), важные пункты. "
        "Будь точен, не выдумывай."
    )

    user = f"Документ:\n\n{truncated}"

    return llm_chat(system, user, max_tokens=1024)
