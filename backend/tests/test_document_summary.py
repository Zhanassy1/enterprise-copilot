"""Document summary: viewer extractive path, LLM cache, member metering (PostgreSQL)."""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from tests.test_rbac_workspace import _add_membership

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 (PostgreSQL integration).",
)


def test_summary_viewer_no_llm_call(
    client: TestClient, two_workspaces: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = two_workspaces["a"]
    b = two_workspaces["b"]
    file_bytes = b"Price 999 USD exclusive viewer summary test.\n" * 5
    up = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {a['token']}", "X-Workspace-Id": a["ws"]},
        files={"file": ("v.txt", file_bytes, "text/plain")},
    )
    assert up.status_code == 200, up.text
    doc_id = up.json()["document"]["id"]

    calls: list[int] = []

    def _boom(_text: str) -> tuple[str, int, int]:
        calls.append(1)
        return ("should_not_use", 1, 1)

    monkeypatch.setattr("app.api.routers.documents.llm_summarize", _boom)
    monkeypatch.setattr("app.api.routers.documents.llm_enabled", lambda: True)

    _add_membership(workspace_id=uuid.UUID(a["ws"]), user_email=b["email"], role_key="viewer")
    r = client.get(
        f"/api/v1/documents/{doc_id}/summary",
        headers={"Authorization": f"Bearer {b['token']}", "X-Workspace-Id": a["ws"]},
    )
    assert r.status_code == 200, r.text
    assert calls == []
    body = r.json()
    assert "999" in body["summary"] or "USD" in body["summary"]


def test_summary_member_caches_second_request(
    client: TestClient, two_workspaces: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = two_workspaces["a"]
    file_bytes = b"Unique cache key xyzabc123.\nParagraph two.\nParagraph three.\n" * 3
    up = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {a['token']}", "X-Workspace-Id": a["ws"]},
        files={"file": ("cache.txt", file_bytes, "text/plain")},
    )
    assert up.status_code == 200, up.text
    doc_id = up.json()["document"]["id"]

    calls: list[int] = []

    def _once(_text: str) -> tuple[str, int, int]:
        calls.append(1)
        return ("LLM_ONE_OFF_SUMMARY", 10, 20)

    monkeypatch.setattr("app.api.routers.documents.llm_summarize", _once)
    monkeypatch.setattr("app.api.routers.documents.llm_enabled", lambda: True)

    h = {"Authorization": f"Bearer {a['token']}", "X-Workspace-Id": a["ws"]}
    r1 = client.get(f"/api/v1/documents/{doc_id}/summary", headers=h)
    r2 = client.get(f"/api/v1/documents/{doc_id}/summary", headers=h)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert len(calls) == 1
    assert r1.json()["summary"] == "LLM_ONE_OFF_SUMMARY"


def test_summary_viewer_reads_cache_after_owner_generated(
    client: TestClient, two_workspaces: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = two_workspaces["a"]
    b = two_workspaces["b"]
    file_bytes = b"Shared cache 777777.\nMore text for scoring.\n"
    up = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {a['token']}", "X-Workspace-Id": a["ws"]},
        files={"file": ("shared.txt", file_bytes, "text/plain")},
    )
    assert up.status_code == 200, up.text
    doc_id = up.json()["document"]["id"]

    calls: list[int] = []

    def _once(_text: str) -> tuple[str, int, int]:
        calls.append(1)
        return ("OWNER_LLM_SUMMARY", 3, 4)

    monkeypatch.setattr("app.api.routers.documents.llm_summarize", _once)
    monkeypatch.setattr("app.api.routers.documents.llm_enabled", lambda: True)

    h_owner = {"Authorization": f"Bearer {a['token']}", "X-Workspace-Id": a["ws"]}
    r0 = client.get(f"/api/v1/documents/{doc_id}/summary", headers=h_owner)
    assert r0.status_code == 200
    assert len(calls) == 1

    _add_membership(workspace_id=uuid.UUID(a["ws"]), user_email=b["email"], role_key="viewer")
    h_viewer = {"Authorization": f"Bearer {b['token']}", "X-Workspace-Id": a["ws"]}
    r_viewer = client.get(f"/api/v1/documents/{doc_id}/summary", headers=h_viewer)
    assert r_viewer.status_code == 200
    assert len(calls) == 1
    assert r_viewer.json()["summary"] == "OWNER_LLM_SUMMARY"
