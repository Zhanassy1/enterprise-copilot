#!/usr/bin/env python3
"""
Offline answer synthesis metrics: same gold as ``eval/answer_gold.jsonl``,
default deterministic extractive path; optional ``--llm-answer`` (needs ``RUN_ANSWER_LLM_EVAL=1`` + key).

Examples::

  set RETRIEVAL_EVAL_WORKSPACE_ID=<uuid>
  python scripts/eval_answer_synthesis.py
  set RUN_ANSWER_LLM_EVAL=1
  python scripts/eval_answer_synthesis.py --llm-answer
  python scripts/eval_answer_synthesis.py --llm-answer --judge
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
from app.eval.answer_faithfulness_eval import (  # noqa: E402
    run_llm_judge_eval,
)
from app.eval.eval_config import (  # noqa: E402
    load_retrieval_eval_config,
    resolve_answer_gold_path,
)
from app.eval.seed_corpus import seed_retrieval_eval_corpus  # noqa: E402
from app.models.workspace import Workspace  # noqa: E402


def main() -> int:
    default_config = BACKEND_ROOT / "eval" / "retrieval_eval.config.json"
    p = argparse.ArgumentParser(description="Answer synthesis / gold eval (det extractive, optional LLM + judge).")
    p.add_argument("--config", type=Path, default=default_config)
    p.add_argument(
        "--seed",
        action="store_true",
        help="Insert synthetic eval corpus; print workspace_id JSON; exit 0.",
    )
    p.add_argument(
        "--llm-answer",
        action="store_true",
        help="Call build_answer with LLM (requires API key; confirm with RUN_ANSWER_LLM_EVAL=1).",
    )
    p.add_argument(
        "--judge",
        action="store_true",
        help="With --llm-answer, add LLM-as-judge faithfulness+completeness (extra API calls).",
    )
    args = p.parse_args()

    cfg = load_retrieval_eval_config(args.config)
    answer_gold_path = resolve_answer_gold_path(BACKEND_ROOT, cfg)
    if args.judge and not args.llm_answer:
        print("--judge requires --llm-answer", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        if args.seed:
            workspace_id, user_id, _ = seed_retrieval_eval_corpus(db)
            db.commit()
            print(json.dumps({"workspace_id": str(workspace_id), "user_id": str(user_id)}))
            return 0

        env_ws = os.environ.get("RETRIEVAL_EVAL_WORKSPACE_ID")
        if not env_ws:
            print(
                "Set RETRIEVAL_EVAL_WORKSPACE_ID or use --seed.",
                file=sys.stderr,
            )
            return 1
        workspace_id = UUID(env_ws.strip())

        ws_row = db.get(Workspace, workspace_id)
        if ws_row is None:
            print("Unknown workspace_id.", file=sys.stderr)
            return 1
        env_uid = os.environ.get("RETRIEVAL_EVAL_USER_ID")
        user_id: UUID = UUID(env_uid.strip()) if env_uid else ws_row.owner_user_id

        answer_rows = load_answer_gold_jsonl(answer_gold_path)
        if not answer_rows:
            print("Answer gold file empty.", file=sys.stderr)
            return 1

        extractive_only = not args.llm_answer
        report: dict[str, object] = run_answer_quality_eval(
            db,
            workspace_id=workspace_id,
            user_id=user_id,
            gold_rows=answer_rows,
            reranker_enabled=False,
            extractive_only=extractive_only,
        )
        if args.llm_answer and args.judge:
            report = dict(report)
            report.update(
                run_llm_judge_eval(
                    db,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    gold_rows=answer_rows,
                    reranker_enabled=False,
                )
            )
        print(json.dumps(report, indent=2))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
