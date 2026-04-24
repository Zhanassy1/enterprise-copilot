"""Guard: pipeline code must not reintroduce legacy job/document status strings (pending, done)."""

from __future__ import annotations

import re
from pathlib import Path

_APP = Path(__file__).resolve().parents[1] / "app"


def _scan_files() -> list[Path]:
    services = sorted((_APP / "services").glob("ingestion*.py"))
    task = _APP / "tasks" / "ingestion.py"
    out = [p for p in services if p.is_file()]
    if task.is_file():
        out.append(task)
    return out


def test_ingestion_pipeline_files_reject_legacy_pending_and_done_status_literals() -> None:
    """
    INGESTION_JOB_STATUSES / document pipeline exclude 'pending' and 'done'.
    Catch reintroduction in the narrow ingestion service + Celery task modules only.
    """
    status_assign = re.compile(
        r"(?P<lhs>(?:job|document)\.status)\s*=\s*(?P<q>[\"'])(?P<val>[^\"']+)(?P=q)"
    )
    sql_pending = re.compile(r"status\s*=\s*['\"]pending['\"]", re.IGNORECASE)
    sql_in_pending = re.compile(r"IN\s*\([^)]*['\"]pending['\"]", re.IGNORECASE)

    for path in _scan_files():
        text = path.read_text(encoding="utf-8")
        for m in status_assign.finditer(text):
            assert m.group("val") not in (
                "pending",
                "done",
            ), f"{path.relative_to(_APP.parent)}: legacy status {m.group(0)!r}"
        assert not sql_pending.search(text), f"{path.relative_to(_APP.parent)}: SQL references status pending"
        assert not sql_in_pending.search(text), f"{path.relative_to(_APP.parent)}: SQL IN clause includes pending"
