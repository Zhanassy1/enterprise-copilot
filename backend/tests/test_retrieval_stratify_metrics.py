"""Stratified aggregation for offline eval (query_type / tags on gold)."""

from __future__ import annotations

import unittest

from app.services.retrieval_metrics import (
    aggregate_metrics_stratified,
    primary_segment_key,
)


class StratifiedMetricsTests(unittest.TestCase):
    def test_global_matches_unlabeled_when_one_segment(self) -> None:
        g1 = {"a"}
        g2 = {"b"}
        r1 = ["x", "a", "y"]
        r2 = ["b", "z"]
        ex = [
            (g1, r1, "alpha"),
            (g2, r2, "alpha"),
        ]
        st = aggregate_metrics_stratified(ex, k_list=(1, 2))
        flat = [
            (g1, r1),
            (g2, r2),
        ]
        from app.services.retrieval_metrics import aggregate_metrics

        g = aggregate_metrics(flat, k_list=(1, 2))
        self.assertAlmostEqual(st["mrr"], g["mrr"], places=5)
        self.assertAlmostEqual(st["mrr__alpha"], g["mrr"], places=5)

    def test_primary_segment_query_type_wins(self) -> None:
        s = primary_segment_key(query_type="x", tags=frozenset({"a", "b"}))
        self.assertEqual(s, "x")

    def test_primary_segment_uses_first_sorted_tag(self) -> None:
        s = primary_segment_key(query_type=None, tags=frozenset({"zebra", "apple"}))
        self.assertEqual(s, "apple")


if __name__ == "__main__":
    unittest.main()
