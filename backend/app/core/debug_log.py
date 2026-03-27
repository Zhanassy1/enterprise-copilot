from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def debug_log(*, hypothesisId: str, location: str, message: str, data: dict[str, Any]) -> None:
    # #region agent log
    try:
        payload = {
            "sessionId": "ed07b8",
            "runId": "pre-fix-3",
            "hypothesisId": hypothesisId,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        p = Path(__file__).resolve()
        candidates = [
            p.parents[3] / "debug-ed07b8.log",  # local run: workspace root
            p.parents[2] / "debug-ed07b8.log",  # docker run: /app/debug-ed07b8.log
        ]
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        for path in candidates:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as f:
                    f.write(line)
            except Exception:
                continue
    except Exception:
        pass
    # #endregion

