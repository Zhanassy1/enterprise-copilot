from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from functools import lru_cache
from typing import Any

from app.core.config import settings
from app.middleware.rerank_metrics import record_rerank_predict

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="reranker_predict")


def _resolve_reranker_device(want: str) -> str:
    if want != "auto":
        return want
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


@lru_cache(maxsize=8)
def _load_cross_encoder(model_name: str, device: str, max_length: int) -> Any:
    from sentence_transformers import CrossEncoder

    t0 = time.perf_counter()
    logger.info(
        "Loading reranker model: %s device=%s max_length=%s",
        model_name,
        device,
        max_length,
    )
    model = CrossEncoder(model_name, device=device, max_length=max_length)
    load_ms = (time.perf_counter() - t0) * 1000.0
    logger.info(
        "Reranker model loaded: %s device=%s max_length=%s load_ms=%.2f",
        model_name,
        device,
        max_length,
        load_ms,
    )
    return model


def _get_reranker():
    resolved = _resolve_reranker_device(str(settings.reranker_device))
    return _load_cross_encoder(
        str(settings.reranker_model_name),
        resolved,
        int(settings.reranker_max_length),
    )


def _predict_scores(model: Any, pairs: list[tuple[str, str]]) -> Any:
    bs = max(1, min(int(settings.reranker_batch_size), len(pairs)))
    return model.predict(pairs, batch_size=bs, show_progress_bar=False)


def rerank_hits(query: str, hits: list[dict], *, top_n: int) -> list[dict]:
    if not settings.reranker_enabled:
        return hits
    if not hits:
        return hits

    candidate_limit = max(1, min(int(top_n), len(hits)))
    candidates = hits[:candidate_limit]
    pairs = [(query, str(h.get("text") or "")) for h in candidates]
    if not pairs:
        return hits

    model = _get_reranker()
    timeout_sec = float(settings.reranker_predict_timeout_seconds)
    t0 = time.perf_counter()
    resolved_device = _resolve_reranker_device(str(settings.reranker_device))

    try:
        if timeout_sec > 0.0:
            fut = _executor.submit(_predict_scores, model, pairs)
            try:
                scores = fut.result(timeout=timeout_sec)
            except FutureTimeoutError:
                logger.warning(
                    "Reranker predict timed out after %.3fs (candidates=%s batch_size_cap=%s); keeping vector order",
                    timeout_sec,
                    len(pairs),
                    int(settings.reranker_batch_size),
                )
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                record_rerank_predict(elapsed_ms=elapsed_ms, timed_out=True)
                return hits
        else:
            scores = _predict_scores(model, pairs)
    except Exception:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        record_rerank_predict(elapsed_ms=elapsed_ms, timed_out=False)
        raise

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    record_rerank_predict(elapsed_ms=elapsed_ms, timed_out=False)

    logger.info(
        "Reranker predict: model=%s candidates=%s batch_size_cap=%s duration_ms=%.2f device=%s",
        settings.reranker_model_name,
        len(pairs),
        int(settings.reranker_batch_size),
        elapsed_ms,
        resolved_device,
    )

    for idx, score in enumerate(scores):
        candidates[idx]["reranker_score"] = float(score)

    candidates.sort(key=lambda h: float(h.get("reranker_score") or 0.0), reverse=True)
    tail = hits[candidate_limit:]
    return candidates + tail
