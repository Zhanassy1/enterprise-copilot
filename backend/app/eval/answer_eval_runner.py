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
    evidence_covers_required_chunk_ids,
    forbidden_satisfied,
    gold_chunks_in_top_k,
    grounded_line_ratio,
    must_appear_satisfied,
    must_cover_satisfied,
    reference_token_f1,
)
from app.services.embeddings import embed_texts
from app.services.nlp import build_answer_with_provenance
from app.services.rag_retrieval import retrieve_ranked_hits


@dataclass(frozen=True)
class AnswerGoldRow:
    query_id: str
    query_text: str
    gold_chunk_ids: set[str]
    must_appear_in_answer: tuple[str, ...]
    source_top_k: int
    must_cover: tuple[str, ...] = ()
    forbidden_phrases: tuple[str, ...] = ()
    reference_answer: str | None = None
    required_evidence_chunk_ids: frozenset[str] = frozenset()


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
            mcover = obj.get("must_cover") or []
            fbd = obj.get("forbidden_phrases") or []
            ref = obj.get("reference_answer")
            rev = obj.get("required_evidence_chunk_ids") or []
            rows.append(
                AnswerGoldRow(
                    query_id=str(obj["query_id"]),
                    query_text=str(obj["query_text"]),
                    gold_chunk_ids={str(x) for x in gids},
                    must_appear_in_answer=tuple(str(x) for x in must),
                    source_top_k=int(obj.get("source_top_k") or 5),
                    must_cover=tuple(str(x) for x in mcover),
                    forbidden_phrases=tuple(str(x) for x in fbd),
                    reference_answer=str(ref) if ref is not None else None,
                    required_evidence_chunk_ids=frozenset(str(x) for x in rev),
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
    extractive_only: bool = True,
) -> dict[str, float]:
    """
    For each gold row: ranked hits → gold ids in top-K → build answer (default extractive) →
    must-appear + optional completeness/forbidden/reference/evidence + lexical grounding.

    When ``extractive_only=True`` (default for CI) results are deterministic without an LLM.
    Set ``extractive_only=False`` only for manual/nightly LLM path with ``RUN_ANSWER_LLM_EVAL=1``
    and API keys (see also ``app.eval.answer_faithfulness_eval``).
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
    n_cover = 0
    cover_ok = 0
    n_forbid = 0
    forbid_ok = 0
    n_ref = 0
    ref_f1_sum = 0.0
    n_evid = 0
    evid_ok = 0

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

            answer, prov = build_answer_with_provenance(
                row.query_text,
                hits,
                extractive_only=extractive_only,
            )

            if must_appear_satisfied(answer, list(row.must_appear_in_answer)):
                must_ok += 1
            grounded_sum += grounded_line_ratio(answer, hits)

            if row.must_cover:
                n_cover += 1
                if must_cover_satisfied(answer, list(row.must_cover)):
                    cover_ok += 1
            if row.forbidden_phrases:
                n_forbid += 1
                if forbidden_satisfied(answer, list(row.forbidden_phrases)):
                    forbid_ok += 1
            if row.reference_answer and row.reference_answer.strip():
                n_ref += 1
                ref_f1_sum += reference_token_f1(answer, row.reference_answer)
            if row.required_evidence_chunk_ids:
                n_evid += 1
                if evidence_covers_required_chunk_ids(prov, set(row.required_evidence_chunk_ids)):
                    evid_ok += 1

    n = float(len(gold_rows))
    out: dict[str, float] = {
        "source_gold_all_in_top_k_rate": source_hits / n,
        "must_appear_rate": must_ok / n,
        "mean_grounded_line_ratio": grounded_sum / n,
    }
    if n_cover:
        out["must_cover_rate"] = cover_ok / float(n_cover)
    if n_forbid:
        out["forbidden_satisfied_rate"] = forbid_ok / float(n_forbid)
    if n_ref:
        out["mean_reference_token_f1"] = ref_f1_sum / float(n_ref)
    if n_evid:
        out["required_evidence_coverage_rate"] = evid_ok / float(n_evid)
    return out
