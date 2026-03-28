"""Pluggable antivirus / content scanning hook (no-op in dev)."""

from __future__ import annotations


def scan_uploaded_file_safe(local_path: str) -> None:
    """
    Inspect a file on disk after upload. Raise RuntimeError to reject the file.
    Override in production with ClamAV, cloud AV API, etc.
    """
    _ = local_path
    return None
