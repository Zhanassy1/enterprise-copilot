"""Offline retrieval metrics for comparing ranked lists (e.g. before/after rerank)."""

from __future__ import annotations


def reciprocal_rank(gold_ids: set[str], ranked_ids: list[str]) -> float:
    """MRR for a single query: 1/rank of first relevant id, or 0 if none in the list."""
    for i, cid in enumerate(ranked_ids, start=1):
        if cid in gold_ids:
            return 1.0 / float(i)
    return 0.0


def recall_at_k(gold_ids: set[str], ranked_ids: list[str], k: int) -> float:
    """1.0 if any gold id appears in the top-k ranked ids, else 0.0."""
    if k <= 0:
        return 0.0
    top = ranked_ids[:k]
    return 1.0 if gold_ids & set(top) else 0.0


def mean_reciprocal_rank(examples: list[tuple[set[str], list[str]]]) -> float:
    """Mean of per-query reciprocal ranks."""
    if not examples:
        return 0.0
    return sum(reciprocal_rank(g, r) for g, r in examples) / float(len(examples))


def mean_recall_at_k(examples: list[tuple[set[str], list[str]]], k: int) -> float:
    if not examples:
        return 0.0
    return sum(recall_at_k(g, r, k) for g, r in examples) / float(len(examples))
