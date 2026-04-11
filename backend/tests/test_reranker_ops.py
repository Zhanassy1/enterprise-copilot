"""CrossEncoder rerank: batching, metrics, timeout fallback (mocked model)."""

from __future__ import annotations

from concurrent.futures import TimeoutError as FutureTimeoutError
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import settings
from app.middleware import rerank_metrics
from app.services import reranker


def _reset_rerank_metrics() -> None:
    rerank_metrics.rerank_calls_total = 0
    rerank_metrics.rerank_latency_ms_sum = 0.0
    rerank_metrics.rerank_timeouts_total = 0


@pytest.fixture(autouse=True)
def _reset_metrics():
    _reset_rerank_metrics()
    yield
    _reset_rerank_metrics()


@pytest.fixture(autouse=True)
def _clear_rerank_cache():
    reranker._load_cross_encoder.cache_clear()
    yield
    reranker._load_cross_encoder.cache_clear()


@patch.object(settings, "reranker_enabled", True)
@patch.object(settings, "reranker_device", "cpu")
@patch.object(settings, "reranker_batch_size", 7)
@patch.object(settings, "reranker_max_length", 256)
@patch.object(settings, "reranker_predict_timeout_seconds", 0.0)
def test_predict_uses_batch_size_and_records_metrics() -> None:
    mock_model = MagicMock()
    mock_model.predict.return_value = [0.9, 0.1]

    with patch.object(reranker, "_load_cross_encoder", return_value=mock_model):
        hits = [
            {"chunk_id": "c1", "text": "first"},
            {"chunk_id": "c2", "text": "second"},
        ]
        out = reranker.rerank_hits("q", hits, top_n=10)

    mock_model.predict.assert_called_once()
    _, kwargs = mock_model.predict.call_args
    assert kwargs["batch_size"] == 2
    assert kwargs["show_progress_bar"] is False

    assert out[0]["chunk_id"] == "c1"
    assert out[0]["reranker_score"] == 0.9

    calls, latency_sum, timeouts = rerank_metrics.get_rerank_metrics_state()
    assert calls == 1
    assert timeouts == 0
    assert latency_sum >= 0.0


@patch.object(settings, "reranker_enabled", True)
@patch.object(settings, "reranker_device", "cpu")
@patch.object(settings, "reranker_predict_timeout_seconds", 0.01)
def test_predict_timeout_keeps_vector_order_and_counts_timeout() -> None:
    mock_model = MagicMock()
    mock_fut = MagicMock()
    mock_fut.result.side_effect = FutureTimeoutError()

    hits = [
        {"chunk_id": "c1", "text": "first"},
        {"chunk_id": "c2", "text": "second"},
    ]
    original_ids = [h["chunk_id"] for h in hits]

    with patch.object(reranker, "_load_cross_encoder", return_value=mock_model):
        with patch.object(reranker._executor, "submit", return_value=mock_fut):
            out = reranker.rerank_hits("q", hits, top_n=10)

    assert [h["chunk_id"] for h in out] == original_ids
    mock_model.predict.assert_not_called()

    _calls, _latency, timeouts = rerank_metrics.get_rerank_metrics_state()
    assert timeouts == 1


@patch.object(settings, "reranker_enabled", True)
@patch.object(settings, "reranker_device", "cpu")
@patch.object(settings, "reranker_predict_timeout_seconds", 0.0)
def test_load_cross_encoder_receives_device_and_max_length() -> None:
    mock_model = MagicMock()
    mock_model.predict.return_value = [1.0]

    with patch("sentence_transformers.CrossEncoder", return_value=mock_model) as mock_ce:
        with patch.object(settings, "reranker_max_length", 128):
            reranker._load_cross_encoder.cache_clear()
            reranker.rerank_hits("q", [{"text": "x"}], top_n=5)

    mock_ce.assert_called_once()
    _args, kwargs = mock_ce.call_args
    assert kwargs.get("device") == "cpu"
    assert kwargs.get("max_length") == 128
