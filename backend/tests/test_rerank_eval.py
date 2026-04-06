"""
Golden-style offline checks: MRR / Recall@k on chunk id rankings.

Uses synthetic hit lists and a deterministic fake rerank (promotes labeled relevant chunk)
to assert metrics behave as expected — no DB or CrossEncoder load.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.retrieval_metrics import (
    mean_recall_at_k,
    mean_reciprocal_rank,
    recall_at_k,
    reciprocal_rank,
)


def _fake_rerank_promotes_gold(_query: str, hits: list[dict], *, top_n: int) -> list[dict]:
    """Move chunk with id 'gold' to the front if present (simulates perfect rerank)."""
    gold = [h for h in hits if h.get("chunk_id") == "gold"]
    rest = [h for h in hits if h.get("chunk_id") != "gold"]
    return gold + rest


def test_reciprocal_rank_first_position() -> None:
    assert reciprocal_rank({"a"}, ["a", "b"]) == 1.0
    assert reciprocal_rank({"b"}, ["a", "b"]) == 0.5


def test_recall_at_k() -> None:
    assert recall_at_k({"c"}, ["a", "b", "c"], k=2) == 0.0
    assert recall_at_k({"b"}, ["a", "b", "c"], k=2) == 1.0


def test_golden_mrr_improves_after_deterministic_rerank() -> None:
    """Simulate vector order putting relevant chunk second; rerank moves it first → higher MRR."""
    hits_before = [
        {"chunk_id": "noise", "text": "n", "score": 0.9},
        {"chunk_id": "gold", "text": "answer", "score": 0.4},
        {"chunk_id": "other", "text": "o", "score": 0.3},
    ]
    gold = {"gold"}
    ids_before = [str(h["chunk_id"]) for h in hits_before]
    mrr_before = reciprocal_rank(gold, ids_before)
    assert mrr_before == pytest.approx(0.5)

    hits_after = _fake_rerank_promotes_gold("q", hits_before, top_n=10)
    ids_after = [str(h["chunk_id"]) for h in hits_after]
    mrr_after = reciprocal_rank(gold, ids_after)
    assert mrr_after == 1.0
    assert mrr_after > mrr_before


def test_mean_metrics_on_mini_golden_set() -> None:
    examples = [
        ({"g1"}, ["x", "g1", "y"]),
        ({"g2"}, ["g2", "a"]),
    ]
    assert mean_reciprocal_rank(examples) == pytest.approx((1.0 / 2.0 + 1.0) / 2.0)
    assert mean_recall_at_k(examples, k=2) == 1.0


def test_retrieve_ranked_hits_respects_fake_rerank_for_metrics() -> None:
    """Integration of metrics with retrieve_ranked_hits when rerank is patched."""
    import uuid

    from app.core.config import settings
    from app.services.rag_retrieval import retrieve_ranked_hits

    ws = uuid.uuid4()
    uid = uuid.uuid4()
    db = MagicMock()

    raw_hits = [
        {"chunk_id": "n1", "text": "noise", "score": 0.95},
        {"chunk_id": "gold", "text": "target", "score": 0.2},
    ]

    with (
        patch("app.services.rag_retrieval.search_chunks_pgvector", return_value=raw_hits),
        patch("app.services.rag_retrieval.rerank_hits", side_effect=_fake_rerank_promotes_gold),
        patch("app.services.rag_retrieval.assert_quota"),
        patch("app.services.rag_retrieval.record_event"),
        patch.object(settings, "reranker_enabled", False),
    ):
        out = retrieve_ranked_hits(
            db,
            workspace_id=ws,
            user_id=uid,
            query="q",
            query_embedding=[0.0] * 384,
            top_k=2,
            compact_snippets=False,
        )

    ranked = [str(h["chunk_id"]) for h in out]
    assert reciprocal_rank({"gold"}, ranked) == 1.0
