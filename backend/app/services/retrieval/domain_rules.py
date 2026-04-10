"""Domain-specific retrieval rules applied after generic hybrid fusion (before rerank)."""

from __future__ import annotations

from app.core.config import settings
from app.core.settings.retrieval_rules import RetrievalRuleWeights
from app.services.nlp import (
    PENALTY_LINE_MARKERS,
    PRICE_LINE_MARKERS,
    TERMINATION_LINE_MARKERS,
    boilerplate_penalty,
    is_contract_value_query,
    is_penalty_intent,
    is_price_intent,
    is_termination_intent,
    keyword_overlap,
    text_has_contract_value_signal,
    text_has_monetary_amount,
    text_is_primarily_security_deposit,
    text_suggests_security_deposit_without_contract_value,
)


def apply_quality_heuristics(
    query_text: str,
    rows: list[dict],
    *,
    weights: RetrievalRuleWeights | None = None,
) -> list[dict]:
    w = weights or settings.retrieval_domain_rules
    price_intent = is_price_intent(query_text)
    penalty_intent = is_penalty_intent(query_text)
    termination_intent = is_termination_intent(query_text)
    contract_value_q = is_contract_value_query(query_text)
    tuned: list[dict] = []
    for row in rows:
        text_value = str(row.get("text") or "")
        low = text_value.lower()
        overlap = keyword_overlap(query_text, text_value)
        boiler = boilerplate_penalty(text_value)
        length_penalty = min(
            w.length_penalty_cap,
            max(
                0.0,
                (len(text_value) - float(w.length_penalty_chars_threshold)) / w.length_penalty_divisor,
            ),
        )

        bonus = 0.0
        hard_penalty = 0.0
        has_price_markers = any(m in low for m in PRICE_LINE_MARKERS)
        has_amount = text_has_monetary_amount(text_value)
        has_penalty_markers = any(m in low for m in PENALTY_LINE_MARKERS)
        has_termination_markers = any(m in low for m in TERMINATION_LINE_MARKERS)
        if contract_value_q and text_has_contract_value_signal(text_value) and has_amount:
            bonus += w.bonus_contract_value_with_amount
        if contract_value_q and text_suggests_security_deposit_without_contract_value(text_value):
            hard_penalty += w.hard_penalty_security_deposit_mismatch
        if price_intent and has_price_markers:
            bonus += w.bonus_price_line_markers
        if price_intent and has_amount:
            bonus += w.bonus_price_monetary_amount
        if penalty_intent and has_penalty_markers:
            bonus += w.bonus_penalty_markers
        if termination_intent and has_termination_markers:
            bonus += w.bonus_termination_markers
        if price_intent and not (has_price_markers and has_amount):
            hard_penalty += w.hard_penalty_intent_mismatch
        if penalty_intent and not has_penalty_markers:
            hard_penalty += w.hard_penalty_intent_mismatch
        if termination_intent and not has_termination_markers:
            hard_penalty += w.hard_penalty_intent_mismatch
        if overlap == 0.0:
            hard_penalty += w.hard_penalty_zero_keyword_overlap

        intent_match = (
            (price_intent and has_price_markers and has_amount)
            or (penalty_intent and has_penalty_markers)
            or (termination_intent and has_termination_markers)
        )
        base = float(row.get("score") or 0.0)
        final_score = (
            (base * w.rrf_score_scale)
            + w.overlap_weight * overlap
            + bonus
            - boiler
            - length_penalty
            - hard_penalty
        )
        row["score"] = final_score
        page_no = row.get("page_number")
        para_idx = row.get("paragraph_index")
        if page_no is not None:
            row["citation_anchor"] = f"page:{int(page_no)}:paragraph:{int(para_idx or 0)}"
        else:
            row["citation_anchor"] = f"paragraph:{int(para_idx or row.get('chunk_index') or 0)}"
        row["_base_score"] = base
        row["_overlap"] = overlap
        row["_boiler"] = boiler
        row["_length_penalty"] = length_penalty
        row["_hard_penalty"] = hard_penalty
        row["_intent_match"] = 1 if intent_match else 0
        row["_cv_tier"] = (
            1
            if contract_value_q
            and text_has_contract_value_signal(text_value)
            and has_amount
            and not text_is_primarily_security_deposit(text_value)
            else 0
        )
        tuned.append(row)

    tuned.sort(
        key=lambda r: (
            int(r.get("_cv_tier") or 0) if contract_value_q else 0,
            int(r.get("_intent_match") or 0),
            float(r.get("score") or 0.0),
            float(r.get("_overlap") or 0.0),
        ),
        reverse=True,
    )
    return tuned


def apply_intent_pool_filters(query_text: str, reranked: list[dict]) -> list[dict]:
    """Optionally restrict to intent-matching chunks when strong signals exist."""
    penalty_intent = is_penalty_intent(query_text)
    price_intent = is_price_intent(query_text)
    termination_intent = is_termination_intent(query_text)

    if penalty_intent or termination_intent:
        intent_hits = [r for r in reranked if int(r.get("_intent_match") or 0) == 1]
        if intent_hits:
            reranked = intent_hits
    if price_intent:

        def _price_match(row: dict) -> bool:
            txt = str(row.get("text") or "").lower()
            return any(m in txt for m in PRICE_LINE_MARKERS) and text_has_monetary_amount(txt)

        price_hits = [r for r in reranked if _price_match(r)]
        if price_hits:
            reranked = price_hits
        if is_contract_value_query(query_text):
            cv_hits = [
                r
                for r in reranked
                if text_has_contract_value_signal(str(r.get("text") or ""))
                and text_has_monetary_amount(str(r.get("text") or ""))
            ]
            if cv_hits:
                reranked = cv_hits
    return reranked


def filter_min_score_and_dedupe(
    reranked: list[dict],
    *,
    top_k: int,
    min_score: float | None = None,
    max_dup_overlap: float | None = None,
) -> list[dict]:
    min_s = float(settings.retrieval_min_score if min_score is None else min_score)
    max_ov = float(
        settings.retrieval_max_near_duplicate_overlap if max_dup_overlap is None else max_dup_overlap
    )
    reranked = [r for r in reranked if float(r.get("score") or 0.0) >= min_s]

    deduped: list[dict] = []
    for row in reranked:
        row_text = str(row.get("text") or "")
        is_duplicate = False
        for kept in deduped:
            kept_text = str(kept.get("text") or "")
            overlap = keyword_overlap(row_text, kept_text)
            if overlap >= max_ov:
                is_duplicate = True
                break
        if not is_duplicate:
            deduped.append(row)
        if len(deduped) >= int(top_k):
            break
    return deduped[: int(top_k)]


def strip_rule_debug_fields(rows: list[dict]) -> None:
    for row in rows:
        row.pop("_base_score", None)
        row.pop("_overlap", None)
        row.pop("_boiler", None)
        row.pop("_length_penalty", None)
        row.pop("_hard_penalty", None)
        row.pop("_intent_match", None)
        row.pop("_cv_tier", None)


def apply_domain_retrieval_rules(
    *,
    query_text: str,
    fused_rows: list[dict],
    top_k: int,
    weights: RetrievalRuleWeights | None = None,
) -> list[dict]:
    """Full domain layer: heuristics → intent pools → min score → near-dup dedup."""
    reranked = apply_quality_heuristics(query_text, fused_rows, weights=weights)
    reranked = apply_intent_pool_filters(query_text, reranked)
    out = filter_min_score_and_dedupe(reranked, top_k=top_k)
    strip_rule_debug_fields(out)
    return out
