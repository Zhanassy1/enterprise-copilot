from __future__ import annotations

import logging
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_reranker():
    from sentence_transformers import CrossEncoder

    model_name = settings.reranker_model_name
    logger.info("Loading reranker model: %s", model_name)
    return CrossEncoder(model_name)


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
    scores = model.predict(pairs, show_progress_bar=False)
    for idx, score in enumerate(scores):
        candidates[idx]["reranker_score"] = float(score)

    candidates.sort(key=lambda h: float(h.get("reranker_score") or 0.0), reverse=True)
    tail = hits[candidate_limit:]
    return candidates + tail
