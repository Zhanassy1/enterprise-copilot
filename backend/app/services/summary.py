from __future__ import annotations

from app.services.llm import llm_enabled, llm_summarize
from app.services.nlp import tokenize


def summarize_document(text: str, *, max_sentences: int = 5, allow_llm: bool = True) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return "Документ пустой или текст не извлечен."

    if allow_llm and llm_enabled():
        llm_result, _, _ = llm_summarize(cleaned)
        if llm_result:
            return llm_result

    return _extractive_summary(cleaned, max_sentences=max_sentences)


def _extractive_summary(text: str, *, max_sentences: int = 5) -> str:
    sentences = _split_sentences(text)
    if len(sentences) <= max_sentences:
        return "\n".join(sentences)

    freqs: dict[str, int] = {}
    for tok in tokenize(text):
        freqs[tok] = freqs.get(tok, 0) + 1
    if not freqs:
        return "\n".join(sentences[:max_sentences])

    scored: list[tuple[int, float]] = []
    for idx, sent in enumerate(sentences):
        toks = tokenize(sent)
        if not toks:
            continue
        score = sum(freqs.get(t, 0) for t in toks) / len(toks)
        scored.append((idx, score))

    if not scored:
        return "\n".join(sentences[:max_sentences])

    top_idx = sorted(x[0] for x in sorted(scored, key=lambda x: x[1], reverse=True)[:max_sentences])
    return "\n".join(sentences[i] for i in top_idx)


def _split_sentences(text: str) -> list[str]:
    parts: list[str] = []
    buf = ""
    for ch in text:
        buf += ch
        if ch in ".!?":
            sent = " ".join(buf.strip().split())
            if sent:
                parts.append(sent)
            buf = ""
    tail = " ".join(buf.strip().split())
    if tail:
        parts.append(tail)
    return parts
