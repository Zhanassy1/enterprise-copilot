"""Unit tests for domain retrieval rules (no database)."""

from __future__ import annotations

from app.core.settings.retrieval_rules import RetrievalRuleWeights
from app.services.retrieval.domain_rules import (
    apply_domain_retrieval_rules,
    apply_quality_heuristics,
)


def test_apply_quality_heuristics_respects_rrf_scale() -> None:
    w = RetrievalRuleWeights(rrf_score_scale=2.0)
    rows = [{"chunk_id": "x", "text": "цена 100 тенге", "score": 0.1}]
    out = apply_quality_heuristics("цена договора", rows, weights=w)
    assert len(out) == 1
    assert out[0]["_base_score"] == 0.1
    assert out[0]["score"] > w.rrf_score_scale * 0.1


def test_domain_rules_pipeline_returns_top_k() -> None:
    fused = [
        {"chunk_id": "a", "text": "цена договора 50000 тенге", "score": 0.05},
        {"chunk_id": "b", "text": "прочий текст без суммы", "score": 0.08},
    ]
    out = apply_domain_retrieval_rules(query_text="стоимость договора", fused_rows=fused, top_k=1)
    assert len(out) == 1
