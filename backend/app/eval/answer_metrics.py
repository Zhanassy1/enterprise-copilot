"""Deterministic answer quality metrics (grounding vs retrieved hits, no LLM)."""

from __future__ import annotations

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
