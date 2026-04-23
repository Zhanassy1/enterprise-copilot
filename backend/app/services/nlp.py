# -*- coding: utf-8 -*-  # noqa: UP009
from __future__ import annotations

import json
import re
import uuid
from typing import Literal, cast

from app.core.settings.llm import AnswerStyle

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

# Shown when «сумма/цена договора» was asked but no chunk line ties contract-price wording to an amount.
CONTRACT_VALUE_UNAVAILABLE_RU = (
    "Во фрагментах нет однозначной строки с суммой (ценой) договора вместе с суммой. "
    "Откройте полный документ или приложение с разделом о цене."
)

# How many top hits may support intent_signal in compute_confidence (reranker may reorder noise first).
CONFIDENCE_INTENT_TOP_K = 5

# Money-like amount (not a bare clause number such as "5.1.")
_AMOUNT_RE = re.compile(
    r"""
    (?:
        \d[\d\s]{2,}
        \s*
        (?:тг|тенге|руб|рублей|₸|₽|\$|usd|kzt|eur|€)
    )
    |
    (?:
        (?:тг|тенге|руб|рублей|₸|₽|\$|usd|kzt|eur|€)
        \s*
        \d[\d\s]{2,}
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_CLAUSE_RE = re.compile(r"^\s*(?:\d{1,2}\.){1,3}\s*[А-ЯA-Z]")

# Spaces (and common thin spaces) between digits — e.g. "1 500 000" vs "1500000"
_COLLAPSE_INTRADIGIT_SPACE_RE = re.compile(r"(?<=\d)[\s\u00a0\u202f]+(?=\d)")


def _collapse_intradigit_spaces(s: str) -> str:
    return _COLLAPSE_INTRADIGIT_SPACE_RE.sub("", s)


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
    "\u20b8",  # ₸
    "\u20bd",  # ₽
    "eur",
    "\u20ac",  # €
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

# Chunk text markers for termination / expiry of contract (retrieval, confidence, snippets).
TERMINATION_LINE_MARKERS: tuple[str, ...] = (
    "расторж",
    "прекращен",
    "расторгнут",
    "односторон",
    "уведомлен",
)

# Chunk text: price/total tied to the contract (retrieval boost, grounding, answer squeeze).
# Literal substrings (lemma forms); inflected RU phrases like «цена договора» are matched via
# ``_CONTRACT_VALUE_MORPH_RE`` below — bare «цена договор» does not occur in real text.
CONTRACT_VALUE_TEXT_MARKERS: tuple[str, ...] = (
    "стоимость договор",
    "ценой договор",
    "цена договор",
    "сумма договор",
    "суммой договор",
    "стоимостью договор",
    "общая сумма",
    "общей суммой",
    "цена работ",
    "стоимость работ",
    "вознагражден",
    "стоимость услуг",
    "цена услуг",
    "договорная цена",
    "договорная сумма",
    "предмет договор",
    # Common document wordings (including inflected «договора»).
    "цена договора",
    "цены договора",
    "стоимость договора",
    "стоимости договора",
    "сумма договора",
    "суммы договора",
    "суммой договора",
    "сумме договора",
    "ценой договора",
    "стоимостью договора",
    "предметом договора",
    "предмета договора",
    "предмет договора",
    "предметам договора",
    "предметами договора",
    "цена контракта",
    "стоимость контракта",
    "сумма контракта",
)

# «Цена/стоимость/сумма … договор*» / контракт* — avoids «сумму обеспечения … договора» (not сумма+договор adjacent).
_CONTRACT_VALUE_MORPH_RE = re.compile(
    r"(?:"
    r"цена|цену|цены|ценой|"
    r"стоимость|стоимости|стоимостью|"
    r"сумма|суммы|сумме|суммой|сумму"
    r")\s+договор[а-яё]{0,10}\b",
    re.IGNORECASE | re.UNICODE,
)
_CONTRACT_VALUE_CONT_RE = re.compile(
    r"(?:цена|цену|стоимость|сумма|сумму|суммы)\s+контракт[а-яё]{0,10}\b",
    re.IGNORECASE | re.UNICODE,
)
# Price / total phrasing near «по договору» (same line).
_CONTRACT_VALUE_PO_DOG_RE = re.compile(
    r"(?:цен|стоимост|сумм|оплат|итог)[а-яё]{0,12}\s+по\s+договор[а-яё]{0,10}\b",
    re.IGNORECASE | re.UNICODE,
)

# Chunk text: security / collateral (deprioritize for «стоимость договора» when no contract-value cue).
SECURITY_CASH_MARKERS: tuple[str, ...] = (
    "обеспечен",
    "залог",
    "обеспечительн",
)

# For list-line grounding under price_intent: descriptive money cues (not bare currency tokens).
_PRICE_DESC_MARKERS_FOR_LIST: tuple[str, ...] = (
    "стоим",
    "цен",
    "сумм",
    "итого",
    "оплат",
    "тариф",
    "прайс",
    "вознагражд",
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
            "сколько стоит",
            "размер оплаты",
            "стоимость договора",
            "цена договора",
        )
    )


def is_contract_value_query(query: str) -> bool:
    """User asks for contract price/total (not e.g. generic «сколько стоит»)."""
    q = (query or "").lower()
    if any(
        x in q
        for x in (
            "стоимость договора",
            "цена договора",
            "сумма договора",
            "сумма по договору",
            "цена по договору",
            "стоимость по договору",
            "стоимость контракта",
            "цена контракта",
        )
    ):
        return True
    if "договор" not in q and "контракт" not in q:
        return False
    return any(x in q for x in ("стоим", "цен", "сумм", "итого", "оплат", "размер"))


def is_strict_contract_value_query(query: str) -> bool:
    """Explicit «total/price of the contract» phrasing (not e.g. generic «оплата по договору»)."""
    q = (query or "").lower()
    return any(
        x in q
        for x in (
            "стоимость договора",
            "цена договора",
            "сумма договора",
            "сумма по договору",
            "цена по договору",
            "стоимость по договору",
            "стоимость контракта",
            "цена контракта",
        )
    )


def text_has_contract_value_signal(text: str) -> bool:
    low = (text or "").lower()
    if any(m in low for m in CONTRACT_VALUE_TEXT_MARKERS):
        return True
    if _CONTRACT_VALUE_MORPH_RE.search(low):
        return True
    if _CONTRACT_VALUE_CONT_RE.search(low):
        return True
    if _CONTRACT_VALUE_PO_DOG_RE.search(low):
        return True
    return False


def text_is_primarily_security_deposit(text: str) -> bool:
    """True if every line that cites a money amount is about security/collateral, not contract price."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    amount_lines = [ln for ln in lines if _line_has_amount(ln)]
    if not amount_lines:
        return False
    for ln in amount_lines:
        low = ln.lower()
        if not any(m in low for m in SECURITY_CASH_MARKERS):
            return False
    return True


def text_suggests_security_deposit_without_contract_value(text: str) -> bool:
    low = (text or "").lower()
    if not any(m in low for m in SECURITY_CASH_MARKERS):
        return False
    if text_is_primarily_security_deposit(text):
        return True
    return not text_has_contract_value_signal(text)


def reorder_hits_for_contract_value_query(hits: list[dict]) -> list[dict]:
    """Cross-encoder may rank obligation blocks above a contract price line — fix final order."""
    if not hits:
        return hits
    preferred: list[dict] = []
    neutral: list[dict] = []
    deprioritized: list[dict] = []
    for h in hits:
        t = str(h.get("text") or "")
        if text_suggests_security_deposit_without_contract_value(t):
            deprioritized.append(h)
        elif text_has_contract_value_signal(t) and text_has_monetary_amount(t):
            preferred.append(h)
        else:
            neutral.append(h)
    return preferred + neutral + deprioritized


def adjust_hit_scores_for_contract_value_query(hits: list[dict]) -> None:
    """Align UI relevance % and confidence with contract-price vs security-only snippets."""
    for h in hits:
        t = str(h.get("text") or "")
        s = float(h.get("score") or 0.0)
        if text_suggests_security_deposit_without_contract_value(t):
            s = min(s, 0.20)
        elif text_has_contract_value_signal(t) and text_has_monetary_amount(t):
            s = min(1.0, s + 0.42)
        h["score"] = max(0.0, min(1.0, s))


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


def is_termination_intent(query: str) -> bool:
    q = (query or "").lower()
    return any(
        x in q
        for x in (
            "расторж",
            "прекращен",
            "расторгнут",
            "односторон",
            "уведомлен",
            "денонсир",
            "отказ от договора",
            "прекращение действия",
        )
    )


def is_advisory_intent(query: str) -> bool:
    """Риски, норма условий, сравнение — отдельный режим промпта (не подменяет строгий RAG по фактам)."""
    q = (query or "").lower()
    return any(
        x in q
        for x in (
            "риск",
            "опасн",
            "подводн",
            "нормальн",
            "норма ",
            "норму ",
            "переплат",
            "перегруз",
            "выгодн",
            "невыгодн",
            "сравни",
            "сравнить",
            "лучше ли",
            "хуже ли",
            "стоит ли подпис",
            "на рынке",
            "рыночн",
            "типичн",
            "юридически безопас",
            "что скажешь",
            "как думаешь",
            "оцени",
            "подводные камни",
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
    if is_contract_value_query(low):
        additions.extend(
            ["стоимость договора", "цена договора", "сумма договора", "договорная цена", "общая сумма"]
        )
    if is_penalty_intent(low):
        additions.extend(["пеня", "неустойка", "штраф", "просрочка", "санкции", "удержание"])
    if is_termination_intent(low):
        additions.extend(
            ["расторжение", "прекращение", "расторгнуть", "уведомление", "односторонний отказ"]
        )
    if is_advisory_intent(low):
        additions.extend(["риск", "ответственность", "штраф", "неустойка", "срок", "условия"])
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


def _line_has_amount(line: str) -> bool:
    return bool(_AMOUNT_RE.search(line))


def text_has_monetary_amount(text: str) -> bool:
    """True if text contains a money-like amount (excludes bare clause refs like «5.1.»)."""
    return bool(_AMOUNT_RE.search(text or ""))


def _line_is_clause_header(line: str) -> bool:
    return bool(_CLAUSE_RE.match(line)) and not _line_has_amount(line)


def extract_relevant_lines(query: str, text: str, *, max_lines: int = 6) -> list[str]:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return []
    if is_contract_value_query(query):
        out_cv: list[str] = []
        for ln in lines:
            s = ln.strip()
            if text_suggests_security_deposit_without_contract_value(s):
                continue
            if text_has_contract_value_signal(s) and _line_has_amount(s):
                out_cv.append(ln)
        return out_cv[:max_lines]

    q_stems = set(tokenize(query))
    out: list[str] = []
    for ln in lines:
        low = ln.lower()
        if q_stems and any(st in low for st in q_stems):
            if _line_is_clause_header(ln):
                continue
            out.append(ln)
            continue
        if is_price_intent(query):
            if any(m in low for m in PRICE_LINE_MARKERS) and _line_has_amount(ln):
                out.append(ln)
                continue
            if _line_has_amount(ln):
                out.append(ln)
                continue
        if is_penalty_intent(query) and (any(m in low for m in PENALTY_LINE_MARKERS) or "%" in low):
            out.append(ln)
            continue
        if is_termination_intent(query) and any(m in low for m in TERMINATION_LINE_MARKERS):
            out.append(ln)
            continue
    if out:
        return out[:max_lines]
    return lines[: min(3, max_lines)]


def resolve_answer_style(requested: AnswerStyle | None, default: AnswerStyle) -> AnswerStyle:
    return requested if requested is not None else default


def postprocess_llm_answer(
    query: str,
    raw: str,
    hits: list[dict],
    *,
    answer_style: AnswerStyle,
) -> str:
    adv = is_advisory_intent(query)
    text = filter_ungrounded_sentences(raw, query, hits, advisory=adv)
    if text:
        return compress_price_answer(
            query,
            text,
            hits,
            answer_style=answer_style,
            advisory=adv,
        )
    return ""


def _parse_hit_chunk_id(h: dict) -> uuid.UUID | None:
    raw = h.get("chunk_id")
    if raw is None:
        return None
    if isinstance(raw, uuid.UUID):
        return raw
    return uuid.UUID(str(raw))


def _provenance_for_llm_context(hits: list[dict], *, k: int = 6) -> list[uuid.UUID]:
    out: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for h in hits[:k]:
        uid = _parse_hit_chunk_id(h)
        if uid is not None and uid not in seen:
            seen.add(uid)
            out.append(uid)
    return out


def _answer_extractive_with_provenance(
    query: str, hits: list[dict], *, answer_style: AnswerStyle
) -> tuple[str, list[uuid.UUID]]:
    """Extractive string + ordered unique chunk_ids that supplied first use of each line in ``parts``."""
    parts: list[str] = []
    provenance: list[uuid.UUID] = []
    seen_lines: set[str] = set()
    for h in hits[:3]:
        uid = _parse_hit_chunk_id(h)
        for ln in extract_relevant_lines(query, str(h.get("text") or ""), max_lines=3):
            if ln in seen_lines:
                continue
            seen_lines.add(ln)
            parts.append(ln)
            if uid is not None and uid not in provenance:
                provenance.append(uid)
            if len(parts) >= 5:
                break
        if len(parts) >= 5:
            break

    if not parts:
        if is_contract_value_query(query):
            return CONTRACT_VALUE_UNAVAILABLE_RU, []
        return "По загруженным документам релевантной информации не найдено.", []
    joined = "\n".join(parts[:5])
    if is_price_intent(query):
        out = compress_price_answer(
            query,
            joined,
            hits,
            answer_style=answer_style,
            advisory=is_advisory_intent(query),
        )
        return out, provenance
    return joined, provenance


def _answer_extractive(query: str, hits: list[dict], *, answer_style: AnswerStyle) -> str:
    return _answer_extractive_with_provenance(query, hits, answer_style=answer_style)[0]


def build_answer_with_provenance(
    query: str,
    hits: list[dict],
    *,
    conversation_history: str | None = None,
    answer_style: AnswerStyle = "concise",
    extractive_only: bool = False,
) -> tuple[str, list[uuid.UUID]]:
    if not hits:
        return "По загруженным документам релевантной информации не найдено.", []

    chunks_text = [str(h.get("text") or "") for h in hits[:6] if h.get("text")]

    from app.services.llm import llm_enabled, rag_answer

    if llm_enabled() and not extractive_only:
        llm_result = rag_answer(
            query,
            chunks_text,
            conversation_history=conversation_history,
            answer_style=answer_style,
            advisory=is_advisory_intent(query),
        )
        if llm_result:
            grounded = postprocess_llm_answer(query, llm_result, hits, answer_style=answer_style)
            if grounded:
                return grounded, _provenance_for_llm_context(hits, k=6)

    return _answer_extractive_with_provenance(query, hits, answer_style=answer_style)


def build_answer(
    query: str,
    hits: list[dict],
    *,
    conversation_history: str | None = None,
    answer_style: AnswerStyle = "concise",
    extractive_only: bool = False,
) -> str:
    return build_answer_with_provenance(
        query,
        hits,
        conversation_history=conversation_history,
        answer_style=answer_style,
        extractive_only=extractive_only,
    )[0]


_CITATION_BRACKET_RE = re.compile(r"\[(\d+)\]")


def suggest_citation_index_to_chunk(
    answer: str, hits: list[dict]
) -> dict[str, str] | None:
    """
    If ``answer`` contains ``[1]``-style markers, map each index to the ``chunk_id`` of the
    n-th hit (1-based). None when no such markers. Used for API provenance, not a guarantee
    the model used those chunks correctly.
    """
    if not (answer or "").strip() or not hits:
        return None
    indices: set[int] = set()
    for m in _CITATION_BRACKET_RE.finditer(answer):
        indices.add(int(m.group(1)))
    if not indices:
        return None
    out: dict[str, str] = {}
    for n in sorted(indices):
        if n < 1 or n > len(hits):
            continue
        uid = _parse_hit_chunk_id(hits[n - 1])
        if uid is not None:
            out[str(n)] = str(uid)
    return out or None


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


_LIST_LINE_RE = re.compile(r"^(?:[-•*]|\d{1,3}[.)])\s+", re.UNICODE)
_MULTI_NUMBERED_LIST_RE = re.compile(r"(?m)^\s*\d{1,3}[\).]\s+")


def _best_contract_value_line_from_hits(hits: list[dict]) -> str:
    for h in hits[:8]:
        for raw in str(h.get("text") or "").splitlines():
            s = raw.strip()
            if text_suggests_security_deposit_without_contract_value(s):
                continue
            if text_has_contract_value_signal(s) and _line_has_amount(s):
                return s
    return ""


def _contract_value_answer_sentence(line: str) -> str:
    """Single grounded sentence for UI; amount/currency copied from the source line."""
    m = _AMOUNT_RE.search(line or "")
    if not m:
        return (line or "").strip()
    return f"Стоимость договора составляет {m.group(0).strip()}."


def _should_force_answer_from_evidence(query: str, hits: list[dict]) -> bool:
    """If retrieved chunks already support the question, answer instead of clarify/insufficient."""
    if not hits:
        return False
    window = hits[:8]
    if is_contract_value_query(query) and _best_contract_value_line_from_hits(hits):
        return True
    if is_penalty_intent(query):
        if any(
            any(m in str(h.get("text") or "").lower() for m in PENALTY_LINE_MARKERS) for h in window
        ):
            return True
    if is_termination_intent(query):
        if any(
            any(m in str(h.get("text") or "").lower() for m in TERMINATION_LINE_MARKERS) for h in window
        ):
            return True
    return False


def compress_price_answer(
    query: str,
    answer: str,
    hits: list[dict],
    *,
    answer_style: AnswerStyle = "concise",
    advisory: bool = False,
) -> str:
    """Concise mode: one short sentence with amount when the model pasted numbered obligations.
    Narrative mode: keep a short coherent paragraph when it is still grounded."""
    if advisory:
        t_adv = (answer or "").strip()
        if not t_adv:
            return t_adv
        if is_contract_value_query(query) and is_price_intent(query) and not _best_contract_value_line_from_hits(hits):
            return CONTRACT_VALUE_UNAVAILABLE_RU
        return t_adv

    if not is_price_intent(query):
        return (answer or "").strip()
    t = (answer or "").strip()
    if not t:
        return t

    best = _best_contract_value_line_from_hits(hits) if is_contract_value_query(query) else ""
    if is_contract_value_query(query) and not best:
        return CONTRACT_VALUE_UNAVAILABLE_RU

    list_like = len(_MULTI_NUMBERED_LIST_RE.findall(t)) >= 2
    long_body = len(t) > 280
    pool_text = "\n".join(str(h.get("text") or "") for h in hits[:8])
    collapsed_pool = _collapse_intradigit_spaces(pool_text.lower())

    if answer_style == "narrative":
        if is_contract_value_query(query) and best:
            if not list_like and len(t) <= 1200 and _AMOUNT_RE.search(t):
                collapsed_t = _collapse_intradigit_spaces(t.lower())
                if best.strip().lower() in collapsed_t or any(
                    len(seq) >= 4 and seq in collapsed_pool for seq in re.findall(r"\d{3,}", collapsed_t)
                ):
                    return t
        elif not is_contract_value_query(query) and not list_like and len(t) <= 1200:
            return t

    if is_contract_value_query(query):
        if best and (list_like or long_body):
            return _contract_value_answer_sentence(best)
        first_block = t.split("\n")[0].strip()
        if best and first_block and not _AMOUNT_RE.search(first_block):
            return _contract_value_answer_sentence(best)

    if list_like or long_body:
        for para in re.split(r"\n+", t):
            para = para.strip()
            if not para:
                continue
            for p in re.split(r"(?<=[.!?])\s+", para):
                p = p.strip()
                if p and _AMOUNT_RE.search(p):
                    return p
        for raw in t.splitlines():
            s = raw.strip()
            if s and _AMOUNT_RE.search(s):
                return s
    if is_contract_value_query(query) and best:
        if t.strip() == best.strip():
            return _contract_value_answer_sentence(best)
        if _AMOUNT_RE.search(t) and best in t.replace("\n", " "):
            return _contract_value_answer_sentence(best)
    return t


def _fragment_amount_digit_grounded(fragment: str, support_pool: str) -> bool:
    """Ground fragments that cite a multi-digit sum present in sources (handles spaced thousands)."""
    line = fragment.strip()
    if not line:
        return False
    has_money_shape = bool(_AMOUNT_RE.search(line))
    collapsed_line = _collapse_intradigit_spaces(line.lower())
    collapsed_pool = _collapse_intradigit_spaces(support_pool)
    for seq in re.findall(r"\d{3,}", collapsed_line):
        if seq not in collapsed_pool:
            continue
        # Short runs (e.g. "100") only with explicit currency/sum pattern; longer sums without it.
        if has_money_shape or len(seq) >= 5:
            return True
    return False


def _fragment_grounded(fragment: str, query: str, support_pool: str) -> bool:
    line = fragment.strip()
    if not line:
        return False
    if "недостаточно данных" in line.lower():
        return True
    if _fragment_amount_digit_grounded(line, support_pool):
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


def _price_intent_list_line_grounded(fragment: str, query: str, support_pool: str) -> bool:
    """Reject numbered obligation lines that only share a currency amount with the context pool."""
    line = fragment.strip()
    if not line:
        return False
    if "недостаточно данных" in line.lower():
        return True
    if text_suggests_security_deposit_without_contract_value(line):
        return False
    if _fragment_amount_digit_grounded(line, support_pool):
        low = line.lower()
        if text_has_contract_value_signal(line):
            return True
        if keyword_overlap(query, line) >= 0.22:
            return True
        if any(m in low for m in _PRICE_DESC_MARKERS_FOR_LIST) and not any(m in low for m in SECURITY_CASH_MARKERS):
            return True
        return False
    return _fragment_grounded(line, query, support_pool)


def _is_list_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    return bool(_LIST_LINE_RE.match(s))


_ADVISORY_META_MARKERS: tuple[str, ...] = (
    "не является юридической",
    "не юридическая консультация",
    "информационный характер",
    "информационных целях",
    "не заменяет профессиональную",
    "обратитесь к юрист",
)


def _is_advisory_meta_line(line: str) -> bool:
    low = line.lower()
    return any(m in low for m in _ADVISORY_META_MARKERS)


def _advisory_section_or_hypothesis(line: str, support_pool: str) -> bool:
    s = line.strip().lower()
    if s.startswith(("по документам", "возможные точки внимания", "возможные риски")):
        return True
    low = s
    if not any(x in low for x in ("риск", "вниман", "если ", "может ", "срок", "штраф", "неустой")):
        return False
    return keyword_overlap(line, support_pool) >= 0.06


def filter_ungrounded_sentences(
    answer: str,
    query: str,
    hits: list[dict],
    *,
    advisory: bool = False,
) -> str:
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
            if advisory:
                if (
                    _is_advisory_meta_line(line)
                    or _advisory_section_or_hypothesis(line, support_pool)
                    or _fragment_grounded(line, query, support_pool)
                ):
                    kept.append(line)
            elif _fragment_grounded(line, query, support_pool):
                kept.append(line)

    for line in text.splitlines():
        if _is_list_line(line):
            flush_paragraph()
            line_st = line.strip()
            if is_price_intent(query):
                ok = _price_intent_list_line_grounded(line_st, query, support_pool)
            else:
                ok = _fragment_grounded(line_st, query, support_pool)
            if advisory and (
                _is_advisory_meta_line(line_st)
                or _advisory_section_or_hypothesis(line_st, support_pool)
            ):
                ok = True
            if ok:
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


def _intent_signal_from_hits(query: str, hits: list[dict]) -> float:
    """1.0 if any of the top CONFIDENCE_INTENT_TOP_K hits supports the active query intent(s)."""
    if not hits:
        return 0.0
    k = min(CONFIDENCE_INTENT_TOP_K, len(hits))
    window = hits[:k]
    checks: list[bool] = []

    if is_price_intent(query):
        if is_contract_value_query(query):
            checks.append(
                any(
                    text_has_contract_value_signal(str(h.get("text") or ""))
                    and text_has_monetary_amount(str(h.get("text") or ""))
                    for h in window
                )
            )
        else:
            checks.append(
                any(
                    any(m in str(h.get("text") or "").lower() for m in PRICE_LINE_MARKERS)
                    and text_has_monetary_amount(str(h.get("text") or ""))
                    for h in window
                )
            )
    if is_penalty_intent(query):
        checks.append(
            any(
                any(m in str(h.get("text") or "").lower() for m in PENALTY_LINE_MARKERS)
                for h in window
            )
        )
    if is_termination_intent(query):
        checks.append(
            any(
                any(m in str(h.get("text") or "").lower() for m in TERMINATION_LINE_MARKERS)
                for h in window
            )
        )

    if not checks:
        return 0.0
    return 1.0 if any(checks) else 0.0


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

    intent_signal = _intent_signal_from_hits(query, hits)

    confidence = 0.45 * top_score + 0.20 * margin + 0.25 * overlap + 0.10 * intent_signal
    confidence = _clamp01(confidence)

    # Strict «стоимость/цена договора» + чанки без явной договорной цены: keyword overlap on «договор»
    # inflates score — penalize unless a top hit ties amount to contract-price wording.
    if is_strict_contract_value_query(query) and hits:
        k = min(8, len(hits))
        has_contract_price_hit = any(
            text_has_contract_value_signal(str(h.get("text") or ""))
            and text_has_monetary_amount(str(h.get("text") or ""))
            for h in hits[:k]
        )
        if not has_contract_price_hit:
            confidence = _clamp01(confidence - 0.22)

    return confidence


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
    if _should_force_answer_from_evidence(query, hits):
        return "answer", confidence
    if confidence >= clarify_threshold:
        return "clarify", confidence
    return "insufficient_context", confidence


def build_clarifying_question(query: str) -> str:
    if is_price_intent(query):
        return "Уточните, по какому документу, разделу или периоду нужна цена?"
    if is_penalty_intent(query):
        return "Уточните, по какому договору и за какой период нужно условие по штрафам?"
    if is_termination_intent(query):
        return "Уточните документ или раздел: условия расторжения могут отличаться в приложениях."
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
    answer_style: AnswerStyle | None = None,
) -> str | None:
    """JSON for assistant ChatMessage.reply_meta_json."""
    body: dict = {"decision": decision, "next_step": next_step}
    if answer_style is not None:
        body["answer_style"] = answer_style
    if decision == "answer":
        body["details"] = details
    else:
        body["clarifying_question"] = clarifying_question
    return json.dumps(body, ensure_ascii=False)


def parse_reply_meta(
    raw: str | None,
) -> tuple[str | None, str | None, str | None, DecisionType | None, AnswerStyle | None]:
    """Returns (details, next_step, clarifying_question, decision, answer_style) from stored JSON."""
    if not (raw or "").strip():
        return (None, None, None, None, None)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return (None, None, None, None, None)
    if not isinstance(obj, dict):
        return (None, None, None, None, None)
    dec_raw = obj.get("decision")
    dec: DecisionType | None = (
        cast(DecisionType, dec_raw)
        if dec_raw in ("answer", "clarify", "insufficient_context")
        else None
    )
    st_raw = obj.get("answer_style")
    style: AnswerStyle | None = st_raw if st_raw in ("concise", "narrative") else None
    return (
        obj.get("details") if isinstance(obj.get("details"), str) else None,
        obj.get("next_step") if isinstance(obj.get("next_step"), str) else None,
        obj.get("clarifying_question") if isinstance(obj.get("clarifying_question"), str) else None,
        dec,
        style,
    )
