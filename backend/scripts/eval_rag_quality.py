#!/usr/bin/env python3
"""
Unified offline RAG quality report: retrieval (vector + ranked rerank-off), answer metrics,
optional paired rerank gain (slow when reranker loads a cross-encoder).

Run from ``backend/`` with migrations and ``DATABASE_URL`` (see ``eval/README.md``).

Examples::

  set RETRIEVAL_EVAL_WORKSPACE_ID=<uuid>
  python scripts/eval_rag_quality.py
  python scripts/eval_rag_quality.py --rerank-gain
  python scripts/eval_rag_quality.py --seed
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from uuid import UUID

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import SessionLocal  # noqa: E402
from app.eval.answer_eval_runner import (  # noqa: E402
    load_answer_gold_jsonl,
    run_answer_quality_eval,
)
from app.eval.eval_config import (  # noqa: E402
    load_retrieval_eval_config,
    resolve_answer_gold_path,
    resolve_backend_paths,
    resolve_p2_gold_paths,
)
from app.eval.retrieval_eval_runner import (  # noqa: E402
    load_gold_jsonl,
    run_rerank_gain_eval,
    run_retrieve_ranked_hits_eval,
    run_search_chunks_eval,
)
from app.eval.seed_corpus import seed_p2_rag_eval_corpus, seed_retrieval_eval_corpus  # noqa: E402
from app.models.workspace import Workspace  # noqa: E402


def main() -> int:
    default_config = BACKEND_ROOT / "eval" / "retrieval_eval.config.json"
    parser = argparse.ArgumentParser(description="Unified offline RAG quality JSON report.")
    parser.add_argument("--config", type=Path, default=default_config)
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Insert synthetic eval corpus and print workspace id JSON (same as eval_retrieval.py).",
    )
    parser.add_argument(
        "--rerank-gain",
        action="store_true",
        help="Include paired eval rerank off vs on (downloads/runs cross-encoder when enabled).",
    )
    parser.add_argument(
        "--p2",
        action="store_true",
        help="50-row P2 gold + seed_p2_rag_eval_corpus (see eval/baseline_p2_*.json).",
    )
    args = parser.parse_args()

    cfg = load_retrieval_eval_config(args.config)
    if args.p2:
        gold_path, answer_gold_path, _, _ = resolve_p2_gold_paths(BACKEND_ROOT, cfg)
    else:
        gold_path, _baseline = resolve_backend_paths(BACKEND_ROOT, cfg)
        answer_gold_path = resolve_answer_gold_path(BACKEND_ROOT, cfg)

    db = SessionLocal()
    try:
        workspace_id: UUID | None = None
        env_ws = os.environ.get("RETRIEVAL_EVAL_WORKSPACE_ID")
        if env_ws:
            workspace_id = UUID(env_ws.strip())
        elif args.seed:
            if args.p2:
                workspace_id, user_id, _ = seed_p2_rag_eval_corpus(db)
            else:
                workspace_id, user_id, _ = seed_retrieval_eval_corpus(db)
            db.commit()
            print(json.dumps({"workspace_id": str(workspace_id), "user_id": str(user_id), "p2": args.p2}))
            return 0
        else:
            print(
                "Set RETRIEVAL_EVAL_WORKSPACE_ID to the workspace uuid, or run with --seed once.",
                file=sys.stderr,
            )
            return 1

        ws_row = db.get(Workspace, workspace_id)
        if ws_row is None:
            print("Unknown workspace_id.", file=sys.stderr)
            return 1
        env_uid = os.environ.get("RETRIEVAL_EVAL_USER_ID")
        user_id: UUID = UUID(env_uid.strip()) if env_uid else ws_row.owner_user_id

        gold_rows = load_gold_jsonl(gold_path)
        if not gold_rows:
            print("Retrieval gold file empty.", file=sys.stderr)
            return 1

        answer_rows = load_answer_gold_jsonl(answer_gold_path)
        report: dict[str, object] = {
            "vector_search": run_search_chunks_eval(
                db,
                workspace_id=workspace_id,
                gold_rows=gold_rows,
                k_list=tuple(cfg.k_list),
            ),
            "ranked_hits_rerank_off": run_retrieve_ranked_hits_eval(
                db,
                workspace_id=workspace_id,
                user_id=user_id,
                gold_rows=gold_rows,
                k_list=cfg.k_list,
                reranker_enabled=False,
            ),
        }

        if answer_rows:
            report["answer_quality_rerank_off"] = run_answer_quality_eval(
                db,
                workspace_id=workspace_id,
                user_id=user_id,
                gold_rows=answer_rows,
                reranker_enabled=False,
                k_list=cfg.k_list,
            )

        if args.rerank_gain:
            report["rerank_gain"] = run_rerank_gain_eval(
                db,
                workspace_id=workspace_id,
                user_id=user_id,
                gold_rows=gold_rows,
                k_list=cfg.k_list,
            )
            if answer_rows:
                report["answer_quality_rerank_on"] = run_answer_quality_eval(
                    db,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    gold_rows=answer_rows,
                    reranker_enabled=True,
                    k_list=cfg.k_list,
                )

        print(json.dumps(report, indent=2))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
