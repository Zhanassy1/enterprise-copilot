"""Offline answer + source-alignment eval (synthetic gold, extractive answers by default).

Adds P2-style metrics: citation precision, faithfulness proxy, expected_mode match, and
``retrieval__*`` from the same ranked lists (``aggregate_metrics_stratified``).
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
from app.eval.answer_metrics import (
    citation_chunk_precision,
    evidence_covers_required_chunk_ids,
    faithfulness_proxy_row,
    forbidden_satisfied,
    gold_chunks_in_top_k,
    grounded_line_ratio,
    must_appear_satisfied,
    must_cover_satisfied,
    reference_token_f1,
)
from app.services.embeddings import embed_texts
from app.services.nlp import (
    build_answer_with_provenance,
    decide_response_mode,
)
from app.services.rag_retrieval import retrieve_ranked_hits
from app.services.retrieval_metrics import (
    aggregate_metrics_stratified,
    primary_segment_key,
)


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
    # Optional: stratified report / README (e.g. lang_ru, lang_en). Same as retrieval ``query_type``.
    query_type: str | None = None
    tags: frozenset[str] = frozenset()
    # expected_mode in: answer | clarify | insufficient_context — compared when set.
    expected_mode: str | None = None


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
            raw_tags = obj.get("tags") or []
            tag_set = frozenset(str(t) for t in raw_tags if str(t).strip())
            qtype = obj.get("query_type")
            em = obj.get("expected_mode")
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
                    query_type=str(qtype).strip() if qtype is not None and str(qtype).strip() else None,
                    tags=tag_set,
                    expected_mode=str(em).strip() if em is not None and str(em).strip() else None,
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
    k_list: tuple[int, ...] = (1, 3, 5, 10),
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

    top_k_run = max(max(row.source_top_k for row in gold_rows), max(k_list))
    # Retrieval + stratified examples (shared ranked list as retrieval eval).
    retrieval_examples: list[tuple[set[str], list[str], str | None]] = []
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
    cite_sum = 0.0
    n_cite = 0
    faith_sum = 0.0
    n_faith = 0
    n_mode = 0
    mode_ok = 0

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
            seg = primary_segment_key(query_type=row.query_type, tags=row.tags)
            retrieval_examples.append((row.gold_chunk_ids, ranked, seg))
            if gold_chunks_in_top_k(row.gold_chunk_ids, ranked, row.source_top_k):
                source_hits += 1

            answer, prov = build_answer_with_provenance(
                row.query_text,
                hits,
                extractive_only=extractive_only,
            )

            if must_appear_satisfied(answer, list(row.must_appear_in_answer)):
                must_ok += 1
            gr = grounded_line_ratio(answer, hits)
            grounded_sum += gr

            if row.must_cover:
                n_cover += 1
                if must_cover_satisfied(answer, list(row.must_cover)):
                    cover_ok += 1
            forb_ok = True
            if row.forbidden_phrases:
                n_forbid += 1
                forb_ok = forbidden_satisfied(answer, list(row.forbidden_phrases))
                if forb_ok:
                    forbid_ok += 1
            ref1: float | None = None
            if row.reference_answer and row.reference_answer.strip():
                n_ref += 1
                ref1 = reference_token_f1(answer, row.reference_answer)
                ref_f1_sum += ref1
            has_req = bool(row.required_evidence_chunk_ids)
            evid_m = has_req and evidence_covers_required_chunk_ids(
                prov, set(row.required_evidence_chunk_ids)
            )
            if row.required_evidence_chunk_ids:
                n_evid += 1
                if evid_m:
                    evid_ok += 1
            g_rel = set(row.required_evidence_chunk_ids) if row.required_evidence_chunk_ids else row.gold_chunk_ids
            if g_rel:
                n_cite += 1
                cite_sum += citation_chunk_precision(prov, gold_relevant=g_rel)

            faith_sum += faithfulness_proxy_row(
                gr,
                evidence_ok=evid_m if has_req else True,
                forbidden_ok=forb_ok,
                has_required_evidence=has_req,
                reference_f1=ref1,
            )
            n_faith += 1

            if row.expected_mode is not None:
                dec, _ = decide_response_mode(
                    row.query_text,
                    hits,
                    answer_threshold=settings.answer_threshold,
                    clarify_threshold=settings.clarify_threshold,
                )
                n_mode += 1
                if dec == row.expected_mode:
                    mode_ok += 1

    n = float(len(gold_rows))
    out: dict[str, float] = {
        "source_gold_all_in_top_k_rate": source_hits / n,
        "must_appear_rate": must_ok / n,
        "mean_grounded_line_ratio": grounded_sum / n,
    }
    if n_faith:
        out["mean_faithfulness_proxy"] = faith_sum / float(n_faith)
    if n_cite:
        out["mean_citation_chunk_precision"] = cite_sum / float(n_cite)
    if n_mode:
        out["expected_mode_accuracy"] = float(mode_ok) / float(n_mode)
    if n_cover:
        out["must_cover_rate"] = cover_ok / float(n_cover)
    if n_forbid:
        out["forbidden_satisfied_rate"] = forbid_ok / float(n_forbid)
    if n_ref:
        out["mean_reference_token_f1"] = ref_f1_sum / float(n_ref)
    if n_evid:
        out["required_evidence_coverage_rate"] = evid_ok / float(n_evid)
    rmetrics = aggregate_metrics_stratified(retrieval_examples, k_list=k_list)
    for k, v in rmetrics.items():
        out[f"retrieval__{k}"] = v
    return out
