from __future__ import annotations

import logging

from app.core.config import settings
from app.services.nlp import is_price_intent
from app.services.prompt_templates import RAG_PRICE_FOCUS_SUFFIX, RAG_SYSTEM_PROMPT, SUMMARY_SYSTEM_PROMPT

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


def llm_chat_stream(
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int = 1024,
):
    """Yield text deltas from OpenAI chat completions (streaming). No yields if LLM disabled."""
    if not llm_enabled():
        return
    client = _get_client()
    try:
        stream = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=settings.llm_temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
    except Exception as e:
        logger.error("LLM stream failed: %s", e)
        return


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


def _rag_system_prompt(query: str) -> str:
    if is_price_intent(query):
        return f"{RAG_SYSTEM_PROMPT} {RAG_PRICE_FOCUS_SUFFIX}"
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
) -> str:
    """Generate a RAG answer from retrieved chunks. Falls back to extractive if no LLM key."""
    if not context_chunks:
        return "По загруженным документам релевантной информации не найдено."

    if not llm_enabled():
        return ""

    context = "\n\n---\n\n".join(context_chunks[: 8])

    system = _rag_system_prompt(query)

    user = _rag_user_prompt(query, context, conversation_history=conversation_history)

    return llm_chat(system, user, max_tokens=1024)


def rag_answer_stream(
    query: str,
    context_chunks: list[str],
    *,
    conversation_history: str | None = None,
):
    """Stream RAG answer tokens from the LLM. Empty generator if disabled or no chunks."""
    if not context_chunks:
        return
    if not llm_enabled():
        return

    context = "\n\n---\n\n".join(context_chunks[:8])
    system = _rag_system_prompt(query)
    user = _rag_user_prompt(query, context, conversation_history=conversation_history)
    yield from llm_chat_stream(system, user, max_tokens=1024)


def llm_summarize(text: str) -> str:
    """Generate an LLM-based summary. Returns empty string if LLM is not configured."""
    if not llm_enabled():
        return ""

    truncated = text[:settings.llm_max_context_tokens * 3]

    system = SUMMARY_SYSTEM_PROMPT

    user = f"Документ:\n\n{truncated}"

    return llm_chat(system, user, max_tokens=1024)
