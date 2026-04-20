"""
Offline retrieval evaluation: load gold JSONL, run search pipeline, aggregate metrics.

Used by ``scripts/eval_retrieval.py`` and integration tests. Does not log queries or chunk text.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.embeddings import embed_texts
from app.services.rag_retrieval import retrieve_ranked_hits
from app.services.retrieval_metrics import aggregate_metrics
from app.services.vector_search import search_chunks_pgvector


@dataclass(frozen=True)
class GoldRow:
    query_id: str
    query_text: str
    gold_chunk_ids: set[str]


def load_gold_jsonl(path: Path) -> list[GoldRow]:
    rows: list[GoldRow] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj: dict[str, Any] = json.loads(line)
            gids = obj.get("gold_chunk_ids") or []
            rows.append(
                GoldRow(
                    query_id=str(obj["query_id"]),
                    query_text=str(obj["query_text"]),
                    gold_chunk_ids={str(x) for x in gids},
                )
            )
    return rows


def run_search_chunks_eval(
    db: Session,
    *,
    workspace_id: UUID,
    gold_rows: list[GoldRow],
    k_list: tuple[int, ...] = (1, 3, 5, 10),
) -> dict[str, float]:
    """Vector search only (generic + domain rules), no rerank."""
    examples: list[tuple[set[str], list[str]]] = []
    for row in gold_rows:
        qvec = embed_texts([row.query_text])[0]
        hits = search_chunks_pgvector(
            db,
            workspace_id=workspace_id,
            query_text=row.query_text,
            query_embedding=qvec,
            top_k=max(k_list),
        )
        ranked = [str(h["chunk_id"]) for h in hits]
        examples.append((row.gold_chunk_ids, ranked))
    return aggregate_metrics(examples, k_list=k_list)


def run_retrieve_ranked_hits_eval(
    db: Session,
    *,
    workspace_id: UUID,
    user_id: UUID,
    gold_rows: list[GoldRow],
    k_list: tuple[int, ...] = (1, 3, 5, 10),
    reranker_enabled: bool = False,
) -> dict[str, float]:
    """
    Full RAG path: vector → rerank → snippet compaction → contract-value post-rules.

    Default ``reranker_enabled=False`` matches the committed ranked baseline (no cross-encoder).
    """
    examples: list[tuple[set[str], list[str]]] = []
    top_k = max(k_list)
    with patch.object(settings, "reranker_enabled", reranker_enabled):
        for row in gold_rows:
            qvec = embed_texts([row.query_text])[0]
            hits = retrieve_ranked_hits(
                db,
                workspace_id=workspace_id,
                user_id=user_id,
                query=row.query_text,
                query_embedding=qvec,
                top_k=top_k,
                compact_snippets=True,
            )
            ranked = [str(h["chunk_id"]) for h in hits]
            examples.append((row.gold_chunk_ids, ranked))
    return aggregate_metrics(examples, k_list=k_list)


def build_rerank_gain_report(
    metrics_off: dict[str, float],
    metrics_on: dict[str, float],
) -> dict[str, object]:
    """Pair retrieval metrics with per-key deltas (on minus off)."""
    delta: dict[str, float] = {}
    for key in sorted(set(metrics_off) & set(metrics_on)):
        delta[key] = float(metrics_on[key]) - float(metrics_off[key])
    return {
        "reranker_disabled": dict(metrics_off),
        "reranker_enabled": dict(metrics_on),
        "delta": delta,
    }


def run_rerank_gain_eval(
    db: Session,
    *,
    workspace_id: UUID,
    user_id: UUID,
    gold_rows: list[GoldRow],
    k_list: tuple[int, ...] = (1, 3, 5, 10),
) -> dict[str, object]:
    """
    Run ``retrieve_ranked_hits`` twice: reranker off vs on (cross-encoder when enabled in settings).

    Intended for offline reports and optional CI (``RUN_RERANK_EVAL=1``); PR jobs should patch
    ``rerank_hits`` or keep rerank off to avoid model load.
    """
    off = run_retrieve_ranked_hits_eval(
        db,
        workspace_id=workspace_id,
        user_id=user_id,
        gold_rows=gold_rows,
        k_list=k_list,
        reranker_enabled=False,
    )
    on = run_retrieve_ranked_hits_eval(
        db,
        workspace_id=workspace_id,
        user_id=user_id,
        gold_rows=gold_rows,
        k_list=k_list,
        reranker_enabled=True,
    )
    return build_rerank_gain_report(off, on)


def load_baseline_metrics(path: Path) -> dict[str, float]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return {str(k): float(v) for k, v in data.items()}


def compare_to_baseline(
    metrics: dict[str, float],
    baseline: dict[str, float],
    *,
    epsilon: float,
) -> tuple[bool, list[str]]:
    """
    Return (ok, failures). Each metric must satisfy ``metrics[k] + epsilon >= baseline[k]``
    for every key in baseline (regression gate).
    """
    failures: list[str] = []
    for key, base_val in baseline.items():
        if key not in metrics:
            failures.append(f"missing metric: {key}")
            continue
        if metrics[key] + epsilon < base_val:
            failures.append(f"{key}: {metrics[key]:.6f} < {base_val:.6f} - {epsilon}")
    return (len(failures) == 0, failures)


def default_eval_paths() -> tuple[Path, Path]:
    root = Path(__file__).resolve().parents[2]
    return root / "eval" / "retrieval_gold.jsonl", root / "eval" / "baseline_metrics.json"
