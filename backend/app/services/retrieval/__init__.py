"""Retrieval subpackage: generic hybrid fusion vs domain-specific rules."""

from app.services.retrieval.domain_rules import (
    apply_domain_retrieval_rules,
    apply_intent_pool_filters,
    apply_quality_heuristics,
    filter_min_score_and_dedupe,
)
from app.services.retrieval.generic_hybrid import (
    dense_candidates,
    hybrid_fuse_candidates,
    keyword_candidates,
    rrf_fuse,
)

__all__ = [
    "apply_domain_retrieval_rules",
    "apply_intent_pool_filters",
    "apply_quality_heuristics",
    "dense_candidates",
    "filter_min_score_and_dedupe",
    "hybrid_fuse_candidates",
    "keyword_candidates",
    "rrf_fuse",
]
