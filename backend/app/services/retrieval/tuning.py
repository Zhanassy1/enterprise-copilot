"""
Query-kind-aware retrieval parameters (candidate pool, RRF/weighted fusion).

Defaults merge with :class:`app.core.config.settings`; per-kind overrides are small and
tuned via offline eval (``scripts/tune_retrieval.py``), not at runtime in production
unless env reflects the chosen policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.core.config import settings
from app.core.settings.retrieval_tuning import retrieval_kind_policies
from app.services.nlp import (
    is_contract_value_query,
    is_penalty_intent,
    is_price_intent,
    is_termination_intent,
)
from app.services.retrieval.keyword_query import is_code_like_keyword_query

QueryKind = Literal[
    "code_like",
    "price_intent",
    "penalty_intent",
    "termination_intent",
    "contract_value",
    "default",
]


@dataclass(frozen=True)
class RetrievalContext:
    query_kind: str
    candidate_multiplier: int
    candidate_floor: int
    rrf_k: int
    dense_weight: float
    keyword_weight: float
    fusion_mode: str
    score_fusion_alpha: float
    weighted_fusion_magnitude: float


def infer_query_kind(query_text: str) -> QueryKind:
    q = (query_text or "").strip()
    if is_code_like_keyword_query(q):
        return "code_like"
    if is_price_intent(q) and not (is_penalty_intent(q) or is_termination_intent(q)):
        return "price_intent"
    if is_penalty_intent(q):
        return "penalty_intent"
    if is_termination_intent(q):
        return "termination_intent"
    if is_contract_value_query(q):
        return "contract_value"
    return "default"


def _merge_int(base: int, override: int | None) -> int:
    return int(override) if override is not None else base


def _merge_float(base: float, override: float | None) -> float:
    return float(override) if override is not None else base


def _merge_str(base: str, override: str | None) -> str:
    return str(override) if override is not None else base


def build_retrieval_context(query_text: str) -> RetrievalContext:
    kind = infer_query_kind(query_text)
    pol = retrieval_kind_policies().get(str(kind), {})
    if not isinstance(pol, dict):
        pol = {}

    mult = _merge_int(int(settings.retrieval_candidate_multiplier), pol.get("retrieval_candidate_multiplier"))  # type: ignore[arg-type]
    fl = _merge_int(int(settings.retrieval_candidate_floor), pol.get("retrieval_candidate_floor"))  # type: ignore[arg-type]
    rrf_k = _merge_int(int(settings.retrieval_rrf_k), pol.get("retrieval_rrf_k"))  # type: ignore[arg-type]
    dw = _merge_float(float(settings.retrieval_rrf_weight_dense), pol.get("retrieval_rrf_weight_dense"))  # type: ignore[arg-type]
    kw = _merge_float(float(settings.retrieval_rrf_weight_keyword), pol.get("retrieval_rrf_weight_keyword"))  # type: ignore[arg-type]
    mode = _merge_str(str(settings.retrieval_fusion_mode), pol.get("retrieval_fusion_mode"))  # type: ignore[arg-type]
    alpha = _merge_float(float(settings.retrieval_score_fusion_alpha), pol.get("retrieval_score_fusion_alpha"))  # type: ignore[arg-type]
    mag = _merge_float(
        float(settings.retrieval_weighted_fusion_magnitude),
        pol.get("retrieval_weighted_fusion_magnitude"),  # type: ignore[arg-type]
    )
    return RetrievalContext(
        query_kind=str(kind),
        candidate_multiplier=mult,
        candidate_floor=fl,
        rrf_k=rrf_k,
        dense_weight=dw,
        keyword_weight=kw,
        fusion_mode=mode,
        score_fusion_alpha=alpha,
        weighted_fusion_magnitude=mag,
    )


def candidate_k_for_context(*, top_k: int, ctx: RetrievalContext) -> int:
    return max(
        int(top_k) * int(ctx.candidate_multiplier),
        int(ctx.candidate_floor),
    )
