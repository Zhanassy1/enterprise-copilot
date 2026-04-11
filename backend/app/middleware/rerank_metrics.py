"""Counters for CrossEncoder rerank (exposed on /metrics when observability is enabled)."""

from __future__ import annotations

rerank_calls_total: int = 0
rerank_latency_ms_sum: float = 0.0
rerank_timeouts_total: int = 0


def record_rerank_predict(*, elapsed_ms: float, timed_out: bool) -> None:
    global rerank_calls_total, rerank_latency_ms_sum, rerank_timeouts_total
    rerank_calls_total += 1
    rerank_latency_ms_sum += float(elapsed_ms)
    if timed_out:
        rerank_timeouts_total += 1


def get_rerank_metrics_state() -> tuple[int, float, int]:
    return rerank_calls_total, rerank_latency_ms_sum, rerank_timeouts_total
