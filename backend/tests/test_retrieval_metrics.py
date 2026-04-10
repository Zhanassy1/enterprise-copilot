"""Unit tests for retrieval_metrics (nDCG, multi-recall)."""

from __future__ import annotations

import math

import pytest

from app.services.retrieval_metrics import (
    aggregate_metrics,
    mean_ndcg_at_k,
    ndcg_at_k,
    recall_at_k_multi,
    reciprocal_rank,
)


def test_ndcg_perfect_ranking() -> None:
    gold = {"a"}
    ranked = ["a", "b", "c"]
    assert ndcg_at_k(gold, ranked, k=3) == pytest.approx(1.0)


def test_ndcg_relevant_second() -> None:
    gold = {"b"}
    ranked = ["a", "b", "c"]
    dcg = 1.0 / math.log2(3.0)
    idcg = 1.0
    assert ndcg_at_k(gold, ranked, k=3) == pytest.approx(dcg / idcg)


def test_ndcg_empty_gold() -> None:
    assert ndcg_at_k(set(), ["a", "b"], k=5) == 0.0


def test_recall_multi_partial() -> None:
    gold = {"a", "b", "c"}
    assert recall_at_k_multi(gold, ["a", "x"], k=1) == pytest.approx(1.0 / 3.0)
    assert recall_at_k_multi(gold, ["a", "b"], k=2) == pytest.approx(2.0 / 3.0)


def test_aggregate_metrics_keys() -> None:
    ex = [({"g"}, ["x", "g", "y"])]
    m = aggregate_metrics(ex, k_list=(1, 5))
    assert "mrr" in m and "ndcg_at_5" in m and "recall_multi_at_5" in m
    assert m["recall_at_1"] == 0.0
    assert m["recall_at_5"] == 1.0


def test_mean_ndcg_matches_manual() -> None:
    examples = [({"a"}, ["b", "a"]), ({"x"}, ["x", "y"])]
    m = mean_ndcg_at_k(examples, k=2)
    n1 = ndcg_at_k({"a"}, ["b", "a"], 2)
    n2 = ndcg_at_k({"x"}, ["x", "y"], 2)
    assert m == pytest.approx((n1 + n2) / 2.0)


def test_reciprocal_rank_multi_gold_first_match() -> None:
    assert reciprocal_rank({"a", "b"}, ["c", "a"]) == pytest.approx(0.5)
