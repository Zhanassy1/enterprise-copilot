from __future__ import annotations

import logging
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)

VECTOR_DIM = 384


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer

    model_name = settings.embedding_model_name
    logger.info("Loading embedding model: %s", model_name)
    model = SentenceTransformer(model_name)
    return model


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _get_model()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [vec.tolist() for vec in embeddings]
