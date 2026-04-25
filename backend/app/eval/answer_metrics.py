"""Deterministic answer quality metrics (grounding vs retrieved hits, no LLM)."""

from __future__ import annotations

import re
import uuid

from app.services.nlp import tokenize


def _nontrivial_answer_lines(answer: str, *, min_chars: int = 8) -> list[str]:
    return [ln.strip() for ln in (answer or "").splitlines() if len(ln.strip()) >= min_chars]


def line_grounded_in_hits(line: str, hits: list[dict], *, min_chars: int = 8) -> bool:
    """True if a non-trivial line has lexical overlap with at least one hit body."""
    s = line.strip()
    if len(s) < min_chars:
        return True
    qtok = set(tokenize(s))
    low = s.lower()
    for h in hits:
        t = str(h.get("text") or "").strip()
        if not t:
            continue
        tl = t.lower()
        if low in tl or tl in low:
            return True
        if qtok and (qtok & set(tokenize(t))):
            return True
    return False


def grounded_line_ratio(answer: str, hits: list[dict], *, min_chars: int = 8) -> float:
    """Fraction of non-trivial lines supported by at least one hit (1.0 if no non-trivial lines)."""
    lines = _nontrivial_answer_lines(answer, min_chars=min_chars)
    if not lines:
        return 1.0
    ok = sum(1 for ln in lines if line_grounded_in_hits(ln, hits, min_chars=min_chars))
    return ok / float(len(lines))


def must_appear_satisfied(answer: str, must_appear: list[str]) -> bool:
    if not must_appear:
        return True
    low = (answer or "").lower()
    return all((req or "").lower() in low for req in must_appear)


def gold_chunks_in_top_k(gold_ids: set[str], ranked_chunk_ids: list[str], k: int) -> bool:
    """All gold chunk ids appear within the first ``k`` ranks (set inclusion)."""
    if not gold_ids:
        return True
    if k <= 0:
        return False
    top = set(ranked_chunk_ids[:k])
    return gold_ids <= top


def must_cover_satisfied(answer: str, must_cover: list[str]) -> bool:
    """All substrings in ``must_cover`` appear in ``answer`` (case-insensitive)."""
    if not must_cover:
        return True
    low = (answer or "").lower()
    return all((c or "").lower() in low for c in must_cover)


def forbidden_satisfied(answer: str, forbidden: list[str]) -> bool:
    """True if none of the ``forbidden`` substrings appear in ``answer`` (case-insensitive)."""
    if not forbidden:
        return True
    low = (answer or "").lower()
    for phrase in forbidden:
        if (phrase or "").lower() in low:
            return False
    return True


def reference_token_f1(answer: str, reference: str) -> float:
    """
    Simple token F1 between answer and a reference string (synthetic / smoke only).
    Returns 0.0 if ``reference`` is empty.
    """
    ref = (reference or "").strip()
    if not ref:
        return 0.0
    a = set(tokenize(answer or ""))
    r = set(tokenize(ref))
    if not a and not r:
        return 1.0
    if not a or not r:
        return 0.0
    inter = a & r
    if not inter:
        return 0.0
    p = len(inter) / float(len(a))
    rec = len(inter) / float(len(r))
    if p + rec == 0.0:
        return 0.0
    return 2.0 * p * rec / (p + rec)


def evidence_covers_required_chunk_ids(
    evidence_chunk_ids: list[uuid.UUID] | list[str],
    required: set[str],
) -> bool:
    """
    All ``required`` chunk id strings (normalized) appear in the provenance list.
    """
    if not required:
        return True
    have = {_uuid_str(x) for x in evidence_chunk_ids}
    need = {_uuid_str(x) for x in required}
    return need <= have


def _uuid_str(x: uuid.UUID | str) -> str:
    if isinstance(x, uuid.UUID):
        return str(x)
    return str(uuid.UUID(str(x)))


def citation_chunk_precision(
    provenance_ids: list[uuid.UUID] | list[str] | None,
    *,
    gold_relevant: set[str],
) -> float:
    """
    |provenance ∩ gold_relevant| / max(1, |provenance|). Gold-relevant ids only.

    If ``gold_relevant`` is empty, returns 1.0. Empty provenance with non-empty
    gold returns 0.0.
    """
    if not gold_relevant:
        return 1.0
    p = []
    for x in provenance_ids or []:
        p.append(_uuid_str(x))
    pset = set(p)
    if not pset:
        return 0.0
    return float(len(pset & gold_relevant)) / float(len(pset))


def faithfulness_proxy_row(
    grounded: float,
    *,
    evidence_ok: bool,
    forbidden_ok: bool,
    has_required_evidence: bool,
    reference_f1: float | None,
) -> float:
    """
    Deterministic 0..1 score: lexical grounding + required evidence (if any) +
    forbidden phrases + optional reference F1. Not semantic entailment.
    """
    parts: list[float] = [max(0.0, min(1.0, grounded))]
    if has_required_evidence:
        parts.append(1.0 if evidence_ok else 0.0)
    parts.append(1.0 if forbidden_ok else 0.0)
    if reference_f1 is not None:
        parts.append(max(0.0, min(1.0, reference_f1)))
    return sum(parts) / float(len(parts)) if parts else 0.0


_CIT_RE = re.compile(r"\[(\d+)\]")


def parse_citation_indices_from_answer(answer: str) -> set[int]:
    """Indices n from ``[n]`` markers in the answer text, if the model emits them."""
    if not (answer or "").strip():
        return set()
    return {int(m.group(1)) for m in _CIT_RE.finditer(answer)}
