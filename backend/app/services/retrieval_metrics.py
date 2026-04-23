"""Offline retrieval metrics for comparing ranked lists (e.g. before/after rerank)."""

from __future__ import annotations

import math


def reciprocal_rank(gold_ids: set[str], ranked_ids: list[str]) -> float:
    """MRR for a single query: 1/rank of first relevant id, or 0 if none in the list."""
    for i, cid in enumerate(ranked_ids, start=1):
        if cid in gold_ids:
            return 1.0 / float(i)
    return 0.0


def recall_at_k(gold_ids: set[str], ranked_ids: list[str], k: int) -> float:
    """
    Binary recall@k: 1.0 if any gold id appears in the top-k ranked ids, else 0.0.

    For multiple gold labels, see ``recall_at_k_multi``.
    """
    if k <= 0:
        return 0.0
    top = ranked_ids[:k]
    return 1.0 if gold_ids & set(top) else 0.0


def recall_at_k_multi(gold_ids: set[str], ranked_ids: list[str], k: int) -> float:
    """
    Proportion of gold ids that appear in the top-k ranked list (in [0, 1]).

    Returns 0.0 if ``gold_ids`` is empty.
    """
    if k <= 0 or not gold_ids:
        return 0.0
    top = set(ranked_ids[:k])
    return len(gold_ids & top) / float(len(gold_ids))


def mean_reciprocal_rank(examples: list[tuple[set[str], list[str]]]) -> float:
    """Mean of per-query reciprocal ranks."""
    if not examples:
        return 0.0
    return sum(reciprocal_rank(g, r) for g, r in examples) / float(len(examples))


def mean_recall_at_k(examples: list[tuple[set[str], list[str]]], k: int) -> float:
    if not examples:
        return 0.0
    return sum(recall_at_k(g, r, k) for g, r in examples) / float(len(examples))


def mean_recall_at_k_multi(examples: list[tuple[set[str], list[str]]], k: int) -> float:
    if not examples:
        return 0.0
    return sum(recall_at_k_multi(g, r, k) for g, r in examples) / float(len(examples))


def _dcg_at_k(relevance_scores: list[float], k: int) -> float:
    """DCG: sum_j rel(j) / log2(rank(j)+1) with rank 1-based (standard nDCG formulation)."""
    if k <= 0:
        return 0.0
    scores = relevance_scores[:k]
    dcg = 0.0
    for j in range(len(scores)):
        rank = j + 1
        dcg += scores[j] / math.log2(float(rank + 1))
    return dcg


def ndcg_at_k(gold_ids: set[str], ranked_ids: list[str], k: int) -> float:
    """
    nDCG@k with binary relevance; multiple gold ids yield gain 1 if any gold appears at that rank.

    For each rank position, relevance is 1 if ``ranked_ids[i]`` is in ``gold_ids``, else 0.
    Ideal DCG is computed from the best possible ordering (all relevant items at the top).
    """
    if k <= 0:
        return 0.0
    if not gold_ids:
        return 0.0

    ranked = ranked_ids[:k]
    gains = [1.0 if rid in gold_ids else 0.0 for rid in ranked]
    dcg = _dcg_at_k(gains, k)

    rel_count = min(len(gold_ids), k)
    ideal_gains = [1.0] * rel_count + [0.0] * max(0, k - rel_count)
    idcg = _dcg_at_k(ideal_gains, k)
    if idcg <= 0.0:
        return 0.0
    return dcg / idcg


def mean_ndcg_at_k(examples: list[tuple[set[str], list[str]]], k: int) -> float:
    if not examples:
        return 0.0
    return sum(ndcg_at_k(g, r, k) for g, r in examples) / float(len(examples))


def aggregate_metrics(
    examples: list[tuple[set[str], list[str]]],
    *,
    k_list: tuple[int, ...] = (1, 3, 5, 10),
) -> dict[str, float]:
    """Convenience bundle for offline eval reports and CI baselines."""
    out: dict[str, float] = {"mrr": mean_reciprocal_rank(examples)}
    for k in k_list:
        out[f"recall_at_{k}"] = mean_recall_at_k(examples, k)
        out[f"recall_multi_at_{k}"] = mean_recall_at_k_multi(examples, k)
        out[f"ndcg_at_{k}"] = mean_ndcg_at_k(examples, k)
    return out


def _sanitize_segment_key(segment: str) -> str:
    s = (segment or "").strip()
    if not s:
        return "default"
    out: list[str] = []
    for c in s:
        if c.isalnum() or c in ("_", "-"):
            out.append(c)
        elif c.isspace():
            out.append("_")
        else:
            out.append("_")
    collapsed = "".join(out).strip("_")
    return collapsed or "default"


def primary_segment_key(*, query_type: str | None, tags: frozenset[str] | list[str] | None) -> str | None:
    """
    One segment per gold row for stratified metrics: explicit ``query_type`` wins, else first tag
    in sorted order (stable) when multiple tags are present.
    """
    if query_type and str(query_type).strip():
        return _sanitize_segment_key(str(query_type))
    if not tags:
        return None
    if isinstance(tags, frozenset):
        tag_list = sorted(tags)
    else:
        tag_list = [str(t) for t in tags if str(t).strip()]
        tag_list.sort()
    if not tag_list:
        return None
    return _sanitize_segment_key(tag_list[0])


def aggregate_metrics_stratified(
    examples: list[tuple[set[str], list[str], str | None]],
    *,
    k_list: tuple[int, ...] = (1, 3, 5, 10),
) -> dict[str, float]:
    """
    Global MRR/Recall/nDCG plus per-segment metrics when the third field is a non-empty segment key.
    Keys: ``mrr``, ``recall_at_k``, ... and ``mrr__<segment>``, ``recall_at_k__<segment>``, ...
    """
    unlabeled: list[tuple[set[str], list[str]]] = [(g, r) for g, r, _ in examples]
    out = aggregate_metrics(unlabeled, k_list=k_list)
    by_seg: dict[str, list[tuple[set[str], list[str]]]] = {}
    for g, r, seg in examples:
        if not seg:
            continue
        k = _sanitize_segment_key(seg)
        by_seg.setdefault(k, []).append((g, r))
    for seg, sub in by_seg.items():
        if len(sub) < 1:
            continue
        sub_m = aggregate_metrics(sub, k_list=k_list)
        for key, val in sub_m.items():
            out[f"{key}__{seg}"] = val
    return out
