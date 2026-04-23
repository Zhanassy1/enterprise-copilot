"""
Temporary overrides of retrieval-related settings for offline eval and tuning.

Use as a context manager so each eval run sees a consistent configuration.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass, fields
from typing import Any, Iterator
from unittest.mock import patch

from app.core.config import settings


@dataclass
class RetrievalEvalParamOverrides:
    """Patch ``settings`` fields when non-None. Omitted fields keep current values."""

    retrieval_candidate_multiplier: int | None = None
    retrieval_candidate_floor: int | None = None
    retrieval_rrf_k: int | None = None
    retrieval_rrf_weight_dense: float | None = None
    retrieval_rrf_weight_keyword: float | None = None
    retrieval_hybrid_enabled: bool | None = None
    retrieval_fusion_mode: str | None = None
    retrieval_score_fusion_alpha: float | None = None
    retrieval_weighted_fusion_magnitude: float | None = None
    retrieval_query_kind_policy_json: str | None = None


def _patches_for_overrides(overrides: RetrievalEvalParamOverrides) -> list[Any]:
    out: list[Any] = []
    for f in fields(overrides):
        val = getattr(overrides, f.name)
        if val is not None:
            out.append(patch.object(settings, f.name, val))
    return out


@contextmanager
def apply_retrieval_eval_overrides(overrides: RetrievalEvalParamOverrides) -> Iterator[None]:
    pats = _patches_for_overrides(overrides)
    if not pats:
        yield
        return
    from contextlib import ExitStack

    with ExitStack() as stack:
        for p in pats:
            stack.enter_context(p)
        yield


@contextmanager
def apply_retrieval_eval_overrides_mapping(raw: dict[str, Any] | None) -> Iterator[None]:
    if not raw:
        yield
        return
    coerced: dict[str, Any] = {}
    for k, v in raw.items():
        if v is None:
            continue
        if k in ("retrieval_candidate_multiplier", "retrieval_candidate_floor", "retrieval_rrf_k"):
            coerced[k] = int(v)
        elif k in (
            "retrieval_rrf_weight_dense",
            "retrieval_rrf_weight_keyword",
            "retrieval_score_fusion_alpha",
            "retrieval_weighted_fusion_magnitude",
        ):
            coerced[k] = float(v)
        elif k == "retrieval_hybrid_enabled":
            coerced[k] = bool(v)
        elif k == "retrieval_fusion_mode":
            coerced[k] = str(v)
        elif k == "retrieval_query_kind_policy_json":
            coerced[k] = v if isinstance(v, str) else json.dumps(v)
        else:
            coerced[k] = v
    known = {f.name for f in fields(RetrievalEvalParamOverrides)}
    unknown = set(coerced) - known
    if unknown:
        raise ValueError(f"Unknown override keys: {sorted(unknown)}")
    o = RetrievalEvalParamOverrides(**{k: coerced[k] for k in coerced if k in known})
    with apply_retrieval_eval_overrides(o):
        yield


def retrieval_overrides_from_mapping(raw: dict[str, Any]) -> RetrievalEvalParamOverrides:
    """Build overrides from a JSON object; unknown keys ignored."""
    known = {f.name for f in fields(RetrievalEvalParamOverrides)}
    kwargs = {k: raw[k] for k in raw if k in known and raw[k] is not None}
    return RetrievalEvalParamOverrides(**kwargs)
