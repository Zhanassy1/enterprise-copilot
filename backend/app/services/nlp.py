from __future__ import annotations

import json
import re
from typing import Literal, cast

_STOPWORDS = {
    "и",
    "в",
    "во",
    "на",
    "по",
    "с",
    "со",
    "к",
    "у",
    "за",
    "из",
    "для",
    "что",
    "как",
    "это",
    "the",
    "and",
    "for",
    "with",
}

_RU_SUFFIXES = (
    "иями",
    "ями",
    "ами",
    "иями",
    "ого",
    "ему",
    "ому",
    "ыми",
    "ими",
    "иях",
    "ах",
    "ях",
    "ия",
    "ья",
    "ие",
    "ые",
    "ое",
    "ая",
    "ой",
    "ей",
    "ам",
    "ям",
    "ом",
    "ем",
    "ой",
    "ей",
    "а",
    "я",
    "ы",
    "и",
    "е",
    "о",
    "у",
    "ю",
)

DecisionType = Literal["answer", "clarify", "insufficient_context"]


def _stem_token(token: str) -> str:
    t = token.lower()
    for sfx in _RU_SUFFIXES:
        if len(t) > 4 and t.endswith(sfx):
            return t[: -len(sfx)]
    return t


def tokenize(text: str) -> list[str]:
    raw = re.findall(r"[0-9A-Za-zА-Яа-яЁё]+", (text or "").lower())
    out: list[str] = []
    for tok in raw:
        if len(tok) < 2 or tok in _STOPWORDS:
            continue
        out.append(_stem_token(tok))
    return out


def keyword_overlap(query: str, text: str) -> float:
    q = set(tokenize(query))
    if not q:
        return 0.0
    t = set(tokenize(text))
    if not t:
        return 0.0
    matched = len(q.intersection(t))
    return float(matched) / float(len(q))


# Substrings indicating a monetary / total line inside document chunks (hybrid ranking, snippets).
PRICE_LINE_MARKERS: tuple[str, ...] = (
    "цен",
    "стоим",
    "сумм",
    "итого",
    "к оплате",
    "подлежит оплате",
    "прайс",
    "тариф",
    "тенге",
    "kzt",
    "руб",
    "price",
    "usd",
)

# Chunk text markers for penalty / sanctions (retrieval, confidence, snippets).
PENALTY_LINE_MARKERS: tuple[str, ...] = (
    "пен",
    "неусто",
    "штраф",
    "просроч",
    "санкц",
    "удержан",
)


def is_price_intent(query: str) -> bool:
    q = (query or "").lower()
    return any(
        x in q
        for x in (
            "цен",
            "стоим",
            "прайс",
            "тариф",
            "тенге",
            "kzt",
            "руб",
            "price",
            "сумм",
            "итого",
            "к оплате",
        )
    )


def is_penalty_intent(query: str) -> bool:
    q = (query or "").lower()
    return any(
        x in q
        for x in (
            "пен",
            "неусто",
            "штраф",
            "просроч",
            "санкц",
            "удержан",
        )
    )


def expand_query(query: str) -> str:
    q = (query or "").strip()
    if not q:
        return q
    low = q.lower()
    additions: list[str] = []
    if is_price_intent(low):
        additions.extend(
            ["цена", "стоимость", "тариф", "прайс", "тенге", "kzt", "сумма", "итого", "к оплате"]
        )
    if is_penalty_intent(low):
        additions.extend(["пеня", "неустойка", "штраф", "просрочка", "санкции", "удержание"])
    if not additions:
        return q
    extra = " ".join(dict.fromkeys(additions))
    return f"{q} {extra}"


def boilerplate_penalty(text: str) -> float:
    low = (text or "").lower()
    bad_markers = (
        "реквизиты и подписи сторон",
        "реквизиты",
        "подписи сторон",
        "приложение №",
        "акт выполненных работ",
        "бин/иин",
        "иик",
        "бик",
    )
    hits = sum(1 for m in bad_markers if m in low)
    return min(0.25, hits * 0.06)


def extract_relevant_lines(query: str, text: str, *, max_lines: int = 6) -> list[str]:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return []
    q_stems = set(tokenize(query))
    out: list[str] = []
    for ln in lines:
        low = ln.lower()
        if q_stems and any(st in low for st in q_stems):
            out.append(ln)
            continue
        if is_price_intent(query) and (
            any(x in low for x in PRICE_LINE_MARKERS) or any(ch.isdigit() for ch in ln)
        ):
            out.append(ln)
            continue
        if is_penalty_intent(query) and (any(x in low for x in PENALTY_LINE_MARKERS) or "%" in low):
            out.append(ln)
            continue
    if out:
        return out[:max_lines]
    return lines[: min(3, max_lines)]


def build_answer(query: str, hits: list[dict], *, conversation_history: str | None = None) -> str:
    if not hits:
        return "По загруженным документам релевантной информации не найдено."

    chunks_text = [str(h.get("text") or "") for h in hits[:6] if h.get("text")]

    from app.services.llm import llm_enabled, rag_answer

    if llm_enabled():
        llm_result = rag_answer(query, chunks_text, conversation_history=conversation_history)
        if llm_result:
            grounded = filter_ungrounded_sentences(llm_result, query, hits)
            if grounded:
                return grounded

    parts: list[str] = []
    for h in hits[:3]:
        for ln in extract_relevant_lines(query, str(h.get("text") or ""), max_lines=3):
            if ln not in parts:
                parts.append(ln)
            if len(parts) >= 5:
                break
        if len(parts) >= 5:
            break

    if not parts:
        return "По загруженным документам релевантной информации не найдено."
    return "\n".join(parts[:5])


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


_LIST_LINE_RE = re.compile(r"^(?:[-•*]|\d{1,3}\.)\s+", re.UNICODE)


def _fragment_grounded(fragment: str, query: str, support_pool: str) -> bool:
    line = fragment.strip()
    if not line:
        return False
    if "недостаточно данных" in line.lower():
        return True
    overlap_q = keyword_overlap(query, line)
    line_tokens = {t for t in tokenize(line) if len(t) >= 3}
    support_hits = sum(1 for t in line_tokens if t in support_pool)
    if support_hits >= 2:
        return True
    if not line_tokens:
        return support_hits >= 1
    # Single token anchored in chunks: require tie to the user question or strong token coverage.
    overlap_s = keyword_overlap(line, support_pool)
    frac = support_hits / float(len(line_tokens))
    return support_hits >= 1 and (overlap_q >= 0.12 or overlap_s >= 0.25 or frac >= 0.34)


def _is_list_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    return bool(_LIST_LINE_RE.match(s))


def filter_ungrounded_sentences(answer: str, query: str, hits: list[dict]) -> str:
    text = (answer or "").strip()
    if not text:
        return ""
    support_pool = "\n".join(str(h.get("text") or "") for h in hits[:8]).lower()
    if not support_pool:
        return ""

    kept: list[str] = []
    para_buf: list[str] = []

    def flush_paragraph() -> None:
        if not para_buf:
            return
        block = "\n".join(para_buf).strip()
        para_buf.clear()
        if not block:
            return
        pieces = re.split(r"(?<=[.!?])\s+", block)
        for piece in pieces:
            line = piece.strip()
            if not line:
                continue
            if _fragment_grounded(line, query, support_pool):
                kept.append(line)

    for line in text.splitlines():
        if _is_list_line(line):
            flush_paragraph()
            line_st = line.strip()
            if _fragment_grounded(line_st, query, support_pool):
                kept.append(line_st)
        elif not line.strip():
            flush_paragraph()
        else:
            para_buf.append(line)
    flush_paragraph()

    if kept:
        # Preserve list structure when present.
        if any(_is_list_line(k) for k in kept):
            return "\n".join(kept)
        return " ".join(kept)
    return "Недостаточно данных в предоставленных документах."


def compute_confidence(query: str, hits: list[dict]) -> float:
    if not hits:
        return 0.0

    top1 = float(hits[0].get("score") or 0.0)
    top2 = float(hits[1].get("score") or 0.0) if len(hits) > 1 else 0.0
    top_score = _clamp01(top1)
    margin = _clamp01(top1 - top2)

    overlap_values = [keyword_overlap(query, str(h.get("text") or "")) for h in hits[:3]]
    overlap = sum(overlap_values) / len(overlap_values) if overlap_values else 0.0
    overlap = _clamp01(overlap)

    intent_signal = 0.0
    top_text = str(hits[0].get("text") or "").lower()
    if is_price_intent(query):
        has_price = any(m in top_text for m in PRICE_LINE_MARKERS)
        has_digits = any(ch.isdigit() for ch in top_text)
        intent_signal = 1.0 if has_price and has_digits else 0.0
    elif is_penalty_intent(query):
        intent_signal = 1.0 if any(m in top_text for m in PENALTY_LINE_MARKERS) else 0.0

    confidence = 0.45 * top_score + 0.20 * margin + 0.25 * overlap + 0.10 * intent_signal
    return _clamp01(confidence)


def decide_response_mode(
    query: str,
    hits: list[dict],
    *,
    answer_threshold: float,
    clarify_threshold: float,
) -> tuple[DecisionType, float]:
    confidence = compute_confidence(query, hits)
    if confidence >= answer_threshold:
        return "answer", confidence
    if confidence >= clarify_threshold:
        return "clarify", confidence
    return "insufficient_context", confidence


def build_clarifying_question(query: str) -> str:
    if is_price_intent(query):
        return "Уточните, по какому документу, разделу или периоду нужна цена?"
    if is_penalty_intent(query):
        return "Уточните, по какому договору и за какой период нужно условие по штрафам?"
    return "Уточните документ, период и конкретный параметр, который нужно найти."


def build_next_step(decision: DecisionType) -> str:
    if decision == "answer":
        return "Проверьте источники и, при необходимости, уточните документ или период."
    if decision == "clarify":
        return "Добавьте документ/период/параметр, чтобы я дал точный ответ."
    return "Уточните формулировку запроса или загрузите документ с нужными данными."


def compose_response_text(
    *,
    decision: DecisionType,
    answer: str,
    details: str | None,
    clarifying_question: str | None,
    next_step: str,
) -> str:
    if decision == "answer":
        return (answer or "").strip()
    if decision == "clarify":
        return f"Нужна конкретизация: {clarifying_question}\n\nСледующий шаг: {next_step}"
    return f"Недостаточно подтвержденных данных в документах.\n\nУточнение: {clarifying_question}\n\nСледующий шаг: {next_step}"


def serialize_reply_meta(
    *,
    decision: DecisionType,
    details: str | None,
    next_step: str,
    clarifying_question: str | None,
) -> str | None:
    """JSON for assistant ChatMessage.reply_meta_json."""
    body: dict = {"decision": decision, "next_step": next_step}
    if decision == "answer":
        body["details"] = details
    else:
        body["clarifying_question"] = clarifying_question
    return json.dumps(body, ensure_ascii=False)


def parse_reply_meta(raw: str | None) -> tuple[str | None, str | None, str | None, DecisionType | None]:
    """Returns (details, next_step, clarifying_question, decision) from stored JSON."""
    if not (raw or "").strip():
        return (None, None, None, None)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return (None, None, None, None)
    if not isinstance(obj, dict):
        return (None, None, None, None)
    dec_raw = obj.get("decision")
    dec: DecisionType | None = (
        cast(DecisionType, dec_raw) if dec_raw in ("answer", "clarify", "insufficient_context") else None
    )
    return (
        obj.get("details") if isinstance(obj.get("details"), str) else None,
        obj.get("next_step") if isinstance(obj.get("next_step"), str) else None,
        obj.get("clarifying_question") if isinstance(obj.get("clarifying_question"), str) else None,
        dec,
    )

