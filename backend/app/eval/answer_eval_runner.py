"""Offline answer + source-alignment eval (synthetic gold, extractive answers)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.eval.answer_metrics import (
    gold_chunks_in_top_k,
    grounded_line_ratio,
    must_appear_satisfied,
)
from app.services.embeddings import embed_texts
from app.services.nlp import build_answer
from app.services.rag_retrieval import retrieve_ranked_hits


@dataclass(frozen=True)
class AnswerGoldRow:
    query_id: str
    query_text: str
    gold_chunk_ids: set[str]
    must_appear_in_answer: tuple[str, ...]
    source_top_k: int


def load_answer_gold_jsonl(path: Path) -> list[AnswerGoldRow]:
    rows: list[AnswerGoldRow] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj: dict[str, Any] = json.loads(line)
            gids = obj.get("gold_chunk_ids") or []
            must = obj.get("must_appear_in_answer") or []
            rows.append(
                AnswerGoldRow(
                    query_id=str(obj["query_id"]),
                    query_text=str(obj["query_text"]),
                    gold_chunk_ids={str(x) for x in gids},
                    must_appear_in_answer=tuple(str(x) for x in must),
                    source_top_k=int(obj.get("source_top_k") or 5),
                )
            )
    return rows


def run_answer_quality_eval(
    db: Session,
    *,
    workspace_id: UUID,
    user_id: UUID,
    gold_rows: list[AnswerGoldRow],
    reranker_enabled: bool = False,
) -> dict[str, float]:
    """
    For each gold row: ranked hits → all gold ids in top-K → extractive answer → must-appear + grounding.

    Uses ``extractive_only=True`` so results are deterministic without an LLM.
    """
    if not gold_rows:
        return {
            "source_gold_all_in_top_k_rate": 0.0,
            "must_appear_rate": 0.0,
            "mean_grounded_line_ratio": 0.0,
        }

    top_k_run = max(row.source_top_k for row in gold_rows)
    source_hits = 0
    must_ok = 0
    grounded_sum = 0.0

    with patch.object(settings, "reranker_enabled", reranker_enabled):
        for row in gold_rows:
            qvec = embed_texts([row.query_text])[0]
            hits = retrieve_ranked_hits(
                db,
                workspace_id=workspace_id,
                user_id=user_id,
                query=row.query_text,
                query_embedding=qvec,
                top_k=top_k_run,
                compact_snippets=True,
            )
            ranked = [str(h["chunk_id"]) for h in hits]
            if gold_chunks_in_top_k(row.gold_chunk_ids, ranked, row.source_top_k):
                source_hits += 1

            answer = build_answer(
                row.query_text,
                hits,
                extractive_only=True,
            )
            if must_appear_satisfied(answer, list(row.must_appear_in_answer)):
                must_ok += 1
            grounded_sum += grounded_line_ratio(answer, hits)

    n = float(len(gold_rows))
    return {
        "source_gold_all_in_top_k_rate": source_hits / n,
        "must_appear_rate": must_ok / n,
        "mean_grounded_line_ratio": grounded_sum / n,
    }
