#!/usr/bin/env python3
"""
Offline retrieval evaluation: load gold JSONL, run vector search, aggregate MRR / Recall@k / nDCG.

Committed assets (see ``backend/eval/README.md``):
  - This script + ``app/eval`` modules (evaluator logic).
  - ``eval/retrieval_eval.config.json`` — paths, k-list, regression epsilon.
  - Small **synthetic** gold files only (dummy queries + chunk ids from ``seed_corpus``).

Do **not** commit production documents, scans, or gold files with personal data.

Usage (from ``backend/``, DB migrated, sync ingest flags as in integration tests)::

  set DATABASE_URL=postgresql+psycopg://...
  python scripts/eval_retrieval.py --seed
  set RETRIEVAL_EVAL_WORKSPACE_ID=<uuid from stdout>
  python scripts/eval_retrieval.py
  python scripts/eval_retrieval.py --compare-baseline

Override gold file::

  python scripts/eval_retrieval.py --gold eval/retrieval_gold_smoke.jsonl
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
from app.eval.eval_config import (  # noqa: E402
    load_retrieval_eval_config,
    resolve_backend_paths,
)
from app.eval.retrieval_eval_harness import retrieval_overrides_from_mapping  # noqa: E402
from app.eval.retrieval_eval_runner import (  # noqa: E402
    compare_to_baseline,
    load_baseline_metrics,
    load_gold_jsonl,
    run_search_chunks_eval,
)
from app.eval.seed_corpus import seed_retrieval_eval_corpus  # noqa: E402


def main() -> int:
    default_config = BACKEND_ROOT / "eval" / "retrieval_eval.config.json"

    parser = argparse.ArgumentParser(
        description="Retrieval offline eval (MRR, Recall@k, nDCG). Synthetic gold only in repo."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=default_config,
        help="Path to retrieval_eval.config.json (default: backend/eval/retrieval_eval.config.json)",
    )
    parser.add_argument("--gold", type=Path, default=None, help="Override gold JSONL path")
    parser.add_argument("--baseline", type=Path, default=None, help="Override baseline_metrics.json path")
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Insert synthetic eval corpus (fixed chunk UUIDs) and print workspace id JSON",
    )
    parser.add_argument(
        "--compare-baseline",
        action="store_true",
        help="Exit 1 if metrics regress vs baseline (uses regression_epsilon from config)",
    )
    parser.add_argument(
        "--epsilon",
        type=float,
        default=None,
        help="Override regression epsilon (default: from config)",
    )
    parser.add_argument(
        "--overrides-json",
        type=Path,
        default=None,
        help="Optional JSON with retrieval_* settings to patch for this run (tuning / ablation).",
    )
    args = parser.parse_args()

    cfg = load_retrieval_eval_config(args.config)
    gold_path, baseline_path = resolve_backend_paths(BACKEND_ROOT, cfg)
    if args.gold is not None:
        gold_path = args.gold.resolve()
    if args.baseline is not None:
        baseline_path = args.baseline.resolve()

    epsilon = float(cfg.regression_epsilon if args.epsilon is None else args.epsilon)

    db = SessionLocal()
    try:
        workspace_id: UUID | None = None
        env_ws = os.environ.get("RETRIEVAL_EVAL_WORKSPACE_ID")
        if env_ws:
            workspace_id = UUID(env_ws.strip())
        elif args.seed:
            workspace_id, user_id, _ = seed_retrieval_eval_corpus(db)
            db.commit()
            print(json.dumps({"workspace_id": str(workspace_id), "user_id": str(user_id)}))
        else:
            print(
                "Set RETRIEVAL_EVAL_WORKSPACE_ID to the workspace uuid, or run with --seed once.",
                file=sys.stderr,
            )
            return 1

        gold_rows = load_gold_jsonl(gold_path)
        if not gold_rows:
            print("Gold file empty.", file=sys.stderr)
            return 1

        ovr = None
        if args.overrides_json is not None:
            with args.overrides_json.open(encoding="utf-8") as f:
                ovr = retrieval_overrides_from_mapping(json.load(f))

        metrics = run_search_chunks_eval(
            db,
            workspace_id=workspace_id,
            gold_rows=gold_rows,
            k_list=tuple(cfg.k_list),
            settings_overrides=ovr,
        )
        print(json.dumps(metrics, indent=2))

        if args.compare_baseline:
            baseline = load_baseline_metrics(baseline_path)
            ok, failures = compare_to_baseline(metrics, baseline, epsilon=epsilon)
            if not ok:
                for f in failures:
                    print(f"REGRESSION: {f}", file=sys.stderr)
                return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
