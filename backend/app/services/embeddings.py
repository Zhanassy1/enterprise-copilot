from __future__ import annotations

import logging
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer

    model_name = settings.embedding_model_name
    logger.info("Loading embedding model: %s", model_name)
    model = SentenceTransformer(model_name)
    return model


def get_embedding_dim() -> int:
    """Dimension of vectors produced by the configured SentenceTransformer (must match DB column)."""
    return int(_get_model().get_sentence_embedding_dimension())


def assert_embedding_vector_dim(vec: list[float], *, expected_dim: int) -> None:
    if len(vec) != expected_dim:
        raise ValueError(
            f"Embedding dimension mismatch: expected {expected_dim}, got {len(vec)}"
        )


def embed_texts(
    texts: list[str],
    *,
    encode_batch_size: int | None = None,
) -> list[list[float]]:
    """Encode texts; optional ``encode_batch_size`` maps to SentenceTransformer ``encode(batch_size=...)``."""
    if not texts:
        return []
    model = _get_model()
    bs = encode_batch_size
    if bs is None:
        bs = min(len(texts), max(1, int(settings.embedding_batch_size)))
    bs = max(1, min(int(bs), len(texts)))
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=bs,
    )
    return [vec.tolist() for vec in embeddings]
