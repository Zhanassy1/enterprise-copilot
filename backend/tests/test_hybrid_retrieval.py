import unittest

from app.core.config import settings
from app.services.reranker import rerank_hits
from app.services.vector_search import _rrf_fuse


class HybridRetrievalTests(unittest.TestCase):
    def test_rrf_fusion_prioritizes_chunks_present_in_both_rankings(self) -> None:
        dense = [
            {"chunk_id": "c1", "document_id": "d1", "chunk_index": 0, "text": "alpha", "dense_score": 0.9},
            {"chunk_id": "c2", "document_id": "d1", "chunk_index": 1, "text": "beta", "dense_score": 0.8},
            {"chunk_id": "c3", "document_id": "d2", "chunk_index": 0, "text": "gamma", "dense_score": 0.7},
        ]
        keyword = [
            {"chunk_id": "c9", "document_id": "d9", "chunk_index": 0, "text": "other", "keyword_score": 1.0},
            {"chunk_id": "c2", "document_id": "d1", "chunk_index": 1, "text": "beta", "keyword_score": 0.9},
            {"chunk_id": "c3", "document_id": "d2", "chunk_index": 0, "text": "gamma", "keyword_score": 0.8},
        ]
        fused = _rrf_fuse(dense, keyword, rrf_k=60, dense_weight=1.0, keyword_weight=1.0)
        top_ids = [row["chunk_id"] for row in fused[:3]]
        self.assertIn("c2", top_ids)
        self.assertIn("c3", top_ids)

    def test_reranker_returns_same_hits_when_disabled(self) -> None:
        original = settings.reranker_enabled
        settings.reranker_enabled = False
        try:
            hits = [
                {"chunk_id": "c1", "text": "price 100"},
                {"chunk_id": "c2", "text": "penalty 2%"},
            ]
            out = rerank_hits("какая цена", hits, top_n=10)
            self.assertEqual(out, hits)
        finally:
            settings.reranker_enabled = original


if __name__ == "__main__":
    unittest.main()
