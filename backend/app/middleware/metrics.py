import time
from collections import defaultdict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

RequestCounterKey = tuple[str, str, int]
LatencySumKey = tuple[str, str]

_metrics_counter: dict[RequestCounterKey, int] = defaultdict(int)
_metrics_latency_sum_ms: dict[LatencySumKey, float] = defaultdict(float)


def record_request_metrics(method: str, path: str, status_code: int, elapsed_ms: float) -> None:
    _metrics_counter[(method, path, status_code)] += 1
    _metrics_latency_sum_ms[(method, path)] += elapsed_ms


def get_metrics_state() -> tuple[dict[RequestCounterKey, int], dict[LatencySumKey, float]]:
    return _metrics_counter, _metrics_latency_sum_ms


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        record_request_metrics(request.method, request.url.path, response.status_code, elapsed_ms)
        return response
