import time
from collections import defaultdict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

_metrics_counter: dict[str, int] = defaultdict(int)
_metrics_latency_sum_ms: dict[str, float] = defaultdict(float)


def record_request_metrics(method: str, path: str, status_code: int, elapsed_ms: float) -> None:
    _metrics_counter[f"requests_total:{method}:{path}:{status_code}"] += 1
    _metrics_latency_sum_ms[f"latency_ms_sum:{method}:{path}"] += elapsed_ms


def get_metrics_state() -> tuple[dict[str, int], dict[str, float]]:
    return _metrics_counter, _metrics_latency_sum_ms


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        record_request_metrics(request.method, request.url.path, response.status_code, elapsed_ms)
        return response
