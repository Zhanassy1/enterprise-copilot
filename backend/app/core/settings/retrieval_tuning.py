"""Default per-``query_kind`` retrieval overrides; JSON merge from ``LLMSettings.retrieval_query_kind_policy_json``."""

from __future__ import annotations

import copy
import json
from typing import Any


def _default_policies() -> dict[str, dict[str, Any]]:
    return {
        "code_like": {
            "retrieval_candidate_multiplier": 14,
            "retrieval_rrf_weight_keyword": 1.2,
            "retrieval_rrf_weight_dense": 0.9,
        },
        "price_intent": {
            "retrieval_candidate_multiplier": 12,
        },
        "penalty_intent": {
            "retrieval_rrf_weight_keyword": 1.05,
        },
        "termination_intent": {
            "retrieval_rrf_weight_keyword": 1.05,
        },
        "contract_value": {
            "retrieval_candidate_multiplier": 12,
        },
        "default": {},
    }


def parse_kind_policy_json(raw: str) -> dict[str, dict[str, Any]]:
    s = (raw or "").strip()
    if not s:
        return {}
    data = json.loads(s)
    if not isinstance(data, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for k, v in data.items():
        if isinstance(v, dict):
            out[str(k)] = {str(k2): v2 for k2, v2 in v.items()}
    return out


def merge_kind_policies(
    base: dict[str, dict[str, Any]], override: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    merged = copy.deepcopy(base)
    for k, d in override.items():
        if k in merged and isinstance(merged[k], dict):
            merged[k] = {**merged[k], **d}
        else:
            merged[k] = copy.deepcopy(d) if isinstance(d, dict) else {}
    return merged


def retrieval_kind_policies() -> dict[str, dict[str, Any]]:
    from app.core.config import settings

    base = _default_policies()
    try:
        extra = parse_kind_policy_json(settings.retrieval_query_kind_policy_json)
    except json.JSONDecodeError:
        extra = {}
    return merge_kind_policies(base, extra)
