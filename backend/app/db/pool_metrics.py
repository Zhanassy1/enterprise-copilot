"""In-process DB pool / session acquire counters (exposed on /metrics when enabled)."""

from __future__ import annotations

import threading

_lock = threading.Lock()
db_pool_checkout_total: int = 0
db_session_acquire_total: int = 0
db_session_acquire_ms_sum: float = 0.0
db_session_slow_acquire_total: int = 0


def record_pool_checkout() -> None:
    global db_pool_checkout_total
    with _lock:
        db_pool_checkout_total += 1


def record_session_acquire(
    *, elapsed_ms: float, slow_threshold_ms: float, count_slow: bool
) -> None:
    global db_session_acquire_total, db_session_acquire_ms_sum, db_session_slow_acquire_total
    with _lock:
        db_session_acquire_total += 1
        db_session_acquire_ms_sum += float(elapsed_ms)
        if count_slow and slow_threshold_ms > 0 and float(elapsed_ms) >= float(slow_threshold_ms):
            db_session_slow_acquire_total += 1


def get_db_pool_metrics_state() -> tuple[int, int, float, int]:
    return (
        db_pool_checkout_total,
        db_session_acquire_total,
        db_session_acquire_ms_sum,
        db_session_slow_acquire_total,
    )
