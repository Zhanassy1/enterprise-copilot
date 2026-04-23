"""LLM-path answer eval + optional LLM-as-judge (nightly / manual; not for deterministic CI)."""

from __future__ import annotations

import os
from uuid import UUID

from sqlalchemy.orm import Session
from unittest.mock import patch

from app.core.config import settings
from app.eval.answer_eval_runner import AnswerGoldRow
from app.services.embeddings import embed_texts
from app.services.llm import answer_quality_judge_scores, llm_enabled
from app.services.nlp import build_answer_with_provenance
from app.services.rag_retrieval import retrieve_ranked_hits

RUN_ANSWER_LLM_EVAL = "RUN_ANSWER_LLM_EVAL"


def llm_synthesis_eval_enabled() -> bool:
    return os.environ.get(RUN_ANSWER_LLM_EVAL) == "1" and llm_enabled()


def assert_llm_synthesis_eval_or_raise() -> None:
    if os.environ.get(RUN_ANSWER_LLM_EVAL) != "1":
        raise RuntimeError(
            f"Set {RUN_ANSWER_LLM_EVAL}=1 to run LLM-based answer eval (uses API, non-deterministic)."
        )
    if not llm_enabled():
        raise RuntimeError("llm_api_key is required for LLM answer / judge eval.")


def run_llm_judge_eval(
    db: Session,
    *,
    workspace_id: UUID,
    user_id: UUID,
    gold_rows: list[AnswerGoldRow],
    reranker_enabled: bool = False,
) -> dict[str, float]:
    """
    For each row: same retrieval as offline eval, ``build_answer_with_provenance`` with LLM, then
    one judge call. Aggregates non-None faithfulness & completeness. Empty gold → zeros.
    """
    if not gold_rows:
        return {"judge_faithfulness_mean": 0.0, "judge_completeness_mean": 0.0, "judge_n": 0.0}
    assert_llm_synthesis_eval_or_raise()

    top_k = max(row.source_top_k for row in gold_rows)
    f_sum, c_sum, n = 0.0, 0.0, 0

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
            answer, _ = build_answer_with_provenance(
                row.query_text,
                hits,
                extractive_only=False,
            )
            ev = "\n\n---\n\n".join(str(h.get("text") or "") for h in hits[:8])
            f_v, c_v = answer_quality_judge_scores(row.query_text, answer, ev)
            if f_v is not None and c_v is not None:
                f_sum += f_v
                c_sum += c_v
                n += 1

    if n == 0:
        return {"judge_faithfulness_mean": 0.0, "judge_completeness_mean": 0.0, "judge_n": 0.0}
    return {
        "judge_faithfulness_mean": f_sum / float(n),
        "judge_completeness_mean": c_sum / float(n),
        "judge_n": float(n),
    }
