"""Router ``/chat`` — sessions & messages; LLM RAG unit tests (no DB)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

_INTEGRATION = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 (PostgreSQL integration).",
)


@_INTEGRATION
def test_chat_sessions_list_happy_path(client: TestClient, two_workspaces: dict) -> None:
    a = two_workspaces["a"]
    r = client.get(
        "/api/v1/chat/sessions",
        headers={"Authorization": f"Bearer {a['token']}", "X-Workspace-Id": a["ws"]},
    )
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


@_INTEGRATION
def test_chat_sessions_unauthorized(client: TestClient, two_workspaces: dict) -> None:
    a = two_workspaces["a"]
    r = client.get("/api/v1/chat/sessions", headers={"X-Workspace-Id": a["ws"]})
    assert r.status_code == 401


@_INTEGRATION
def test_chat_sessions_foreign_workspace_forbidden(
    client: TestClient, two_workspaces: dict
) -> None:
    a = two_workspaces["a"]
    b = two_workspaces["b"]
    r = client.get(
        "/api/v1/chat/sessions",
        headers={"Authorization": f"Bearer {a['token']}", "X-Workspace-Id": b["ws"]},
    )
    assert r.status_code == 403


@patch("app.services.llm.llm_enabled", return_value=False)
def test_rag_answer_extractive_when_llm_disabled(_mock_enabled: object) -> None:
    from app.services.llm import rag_answer

    chunks = ["Тариф: плата 777 KZT за услугу."]
    out = rag_answer("стоимость KZT", chunks)
    assert out.strip()
    assert "777" in out


@patch("app.services.llm.llm_enabled", return_value=True)
def test_rag_answer_extractive_on_upstream_error(_mock_enabled: object) -> None:
    from app.services.llm import rag_answer

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("upstream unavailable")

    with patch("app.services.llm._get_client", return_value=mock_client):
        out = rag_answer("стоимость KZT", ["Цена 42 тенге за единицу."])

    assert out.strip()
    assert "42" in out
    mock_client.chat.completions.create.assert_called_once()


@patch("app.services.llm.llm_enabled", return_value=True)
def test_rag_answer_stream_extractive_on_upstream_error(_mock_enabled: object) -> None:
    from app.services.llm import rag_answer_stream

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("upstream unavailable")

    with patch("app.services.llm._get_client", return_value=mock_client):
        parts = list(rag_answer_stream("стоимость KZT", ["Цена 99 тенге за услугу."]))

    assert parts
    joined = "".join(parts)
    assert "99" in joined
    mock_client.chat.completions.create.assert_called_once()
