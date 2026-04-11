"""Alembic stores revision in alembic_version.version_num (VARCHAR(32) by default)."""

from __future__ import annotations

import re
from pathlib import Path

_MAX_REVISION_LEN = 32


def test_alembic_revision_ids_fit_default_version_column() -> None:
    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    assert versions_dir.is_dir(), versions_dir
    pattern = re.compile(r"^revision\s*=\s*[\"']([^\"']+)[\"']", re.MULTILINE)
    for path in sorted(versions_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for m in pattern.finditer(text):
            rid = m.group(1)
            assert len(rid) <= _MAX_REVISION_LEN, (
                f"{path.name}: revision {rid!r} has length {len(rid)}; "
                f"Postgres alembic_version.version_num is VARCHAR({_MAX_REVISION_LEN})"
            )
