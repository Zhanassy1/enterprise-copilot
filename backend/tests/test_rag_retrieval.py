"""Unit tests for shared RAG retrieval (effective_k, rerank quota)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import settings
from app.services.nlp import (
    adjust_hit_scores_for_contract_value_query,
    reorder_hits_for_contract_value_query,
)
from app.services.rag_retrieval import retrieve_ranked_hits


def test_contract_value_query_reorder_prefers_price_over_security() -> None:
    hits = [
        {
            "text": "1) Обеспечить исполнение.\n2) внести сумму обеспечения 906 660.00 тенге",
            "score": 0.9,
        },
        {"text": "Цена договора составляет 12 000 000 тенге.", "score": 0.5},
    ]
    out = reorder_hits_for_contract_value_query(hits)
    assert "12 000 000" in out[0]["text"]
    adjust_hit_scores_for_contract_value_query(out)
    assert out[0]["score"] > out[1]["score"]
    assert out[1]["score"] <= 0.32


def test_retrieve_ranked_hits_passes_effective_top_k_to_vector_search() -> None:
    """Candidate pool must be at least reranker_top_n so rerank can reorder like /search."""
    ws = uuid.uuid4()
    uid = uuid.uuid4()
    db = MagicMock()
    captured: dict[str, int] = {}

    def fake_search_chunks(db_arg, *, workspace_id, query_text, query_embedding, top_k: int):
        captured["top_k"] = top_k
        return [
            {"chunk_id": str(uuid.uuid4()), "text": "line one", "score": 0.9, "document_id": str(ws)},
            {"chunk_id": str(uuid.uuid4()), "text": "line two", "score": 0.8, "document_id": str(ws)},
        ]

    with (
        patch("app.services.rag_retrieval.search_chunks_pgvector", side_effect=fake_search_chunks),
        patch("app.services.rag_retrieval.rerank_hits", side_effect=lambda q, h, top_n: h),
        patch("app.services.rag_retrieval.assert_quota"),
        patch("app.services.rag_retrieval.record_event"),
        patch.object(settings, "reranker_enabled", False),
    ):
        retrieve_ranked_hits(
            db,
            workspace_id=ws,
            user_id=uid,
            query="test query",
            query_embedding=[0.0] * 384,
            top_k=5,
            compact_snippets=False,
        )

    assert captured["top_k"] == max(5, int(settings.reranker_top_n))


def test_retrieve_ranked_hits_asserts_rerank_quota_when_enabled() -> None:
    ws = uuid.uuid4()
    uid = uuid.uuid4()
    db = MagicMock()
    calls: list[dict] = []

    def capture_quota(db_arg, **kwargs):
        if kwargs.get("rerank_increment"):
            calls.append(kwargs)

    with (
        patch(
            "app.services.rag_retrieval.search_chunks_pgvector",
            return_value=[{"chunk_id": "c1", "text": "x", "score": 0.5}],
        ),
        patch("app.services.rag_retrieval.rerank_hits", side_effect=lambda q, h, top_n: h),
        patch("app.services.rag_retrieval.assert_quota", side_effect=capture_quota),
        patch("app.services.rag_retrieval.record_event"),
        patch.object(settings, "reranker_enabled", True),
    ):
        retrieve_ranked_hits(
            db,
            workspace_id=ws,
            user_id=uid,
            query="q",
            query_embedding=[0.0] * 384,
            top_k=3,
            compact_snippets=False,
        )

    assert any(c.get("rerank_increment") == 1 for c in calls)


def test_retrieve_ranked_hits_skips_rerank_quota_when_disabled() -> None:
    ws = uuid.uuid4()
    uid = uuid.uuid4()
    db = MagicMock()
    rerank_calls: list[int] = []

    def capture_quota(db_arg, **kwargs):
        rerank_calls.append(int(kwargs.get("rerank_increment") or 0))

    with (
        patch(
            "app.services.rag_retrieval.search_chunks_pgvector",
            return_value=[{"chunk_id": "c1", "text": "x", "score": 0.5}],
        ),
        patch("app.services.rag_retrieval.rerank_hits", side_effect=lambda q, h, top_n: h),
        patch("app.services.rag_retrieval.assert_quota", side_effect=capture_quota),
        patch("app.services.rag_retrieval.record_event") as rec,
        patch.object(settings, "reranker_enabled", False),
    ):
        retrieve_ranked_hits(
            db,
            workspace_id=ws,
            user_id=uid,
            query="q",
            query_embedding=[0.0] * 384,
            top_k=3,
            compact_snippets=False,
        )

    assert max(rerank_calls, default=0) == 0
    rec.assert_not_called()


@pytest.mark.parametrize("request_top_k", [3, 5, 20])
def test_effective_k_always_at_least_reranker_top_n(request_top_k: int) -> None:
    ws = uuid.uuid4()
    uid = uuid.uuid4()
    db = MagicMock()
    captured: dict[str, int] = {}

    def fake_search_chunks(db_arg, *, workspace_id, query_text, query_embedding, top_k: int):
        captured["top_k"] = top_k
        return [{"chunk_id": str(i), "text": f"t{i}", "score": 0.5} for i in range(top_k)]

    with (
        patch("app.services.rag_retrieval.search_chunks_pgvector", side_effect=fake_search_chunks),
        patch("app.services.rag_retrieval.rerank_hits", side_effect=lambda q, h, top_n: h),
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
            top_k=request_top_k,
            compact_snippets=False,
        )

    assert captured["top_k"] == max(request_top_k, int(settings.reranker_top_n))
    assert len(out) == request_top_k
