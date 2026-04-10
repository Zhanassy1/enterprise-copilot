"""
End-to-end: sync ingest → POST /search → hits scoped to uploaded document with grounded text.

Requires PostgreSQL + pgvector (same as test_api_integration). Run::

  RUN_INTEGRATION_TESTS=1 pytest tests/test_retrieval_e2e.py -v

Fixture skips before touching the DB when ``RUN_INTEGRATION_TESTS`` is unset (unit job).
"""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def retrieval_e2e_tenant(client: TestClient) -> dict[str, str]:
    """Single registered user + personal workspace; skips unless integration mode."""
    if os.environ.get("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("Set RUN_INTEGRATION_TESTS=1 for retrieval e2e (PostgreSQL).")
    pwd = "RetrievalE2EPass1!"
    email = f"e2e_ret_{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": pwd, "full_name": "E2E Retrieval"},
    )
    if reg.status_code == 503:
        pytest.skip("Database unavailable; start PostgreSQL for retrieval e2e.")
    assert reg.status_code == 200, reg.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    wl = client.get("/api/v1/workspaces", headers={"Authorization": f"Bearer {token}"})
    assert wl.status_code == 200, wl.text
    wlist = wl.json()
    assert len(wlist) >= 1
    return {"token": token, "ws": str(wlist[0]["id"]), "email": email}


def test_e2e_upload_search_hits_tie_to_document_and_contain_fact(
    client: TestClient, retrieval_e2e_tenant: dict[str, str]
) -> None:
    """Upload a unique contract snippet; search must return hits from that document with the fact in snippet text."""
    headers = {
        "Authorization": f"Bearer {retrieval_e2e_tenant['token']}",
        "X-Workspace-Id": retrieval_e2e_tenant["ws"],
    }
    marker = f"E2E_RETRIEVAL_{uuid.uuid4().hex[:12]}"
    unique_amount = "777_331"
    file_bytes = (
        f"Договор поставки #{marker}\n"
        f"Цена товара: {unique_amount} тенге по курсу НБ РК на дату оплаты.\n"
        "Неустойка за просрочку поставки: 0.05% за каждый день.\n"
    ).encode()
    up = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": (f"{marker}.txt", file_bytes, "text/plain")},
    )
    assert up.status_code == 200, up.text
    payload = up.json()
    assert payload.get("chunks_created", 0) > 0
    document_id = payload["document"]["id"]

    search = client.post(
        "/api/v1/search",
        headers=headers,
        json={"query": f"какая цена товара в договоре {marker}", "top_k": 5},
    )
    assert search.status_code == 200, search.text
    body = search.json()
    hits = body.get("hits") or []
    assert len(hits) >= 1, body

    doc_ids = {str(h.get("document_id")) for h in hits}
    assert str(document_id) in doc_ids, f"expected uploaded doc in hits, got {doc_ids}"

    texts = " ".join(str(h.get("text") or "") for h in hits)
    assert unique_amount in texts or "777" in texts, texts[:500]

    for h in hits:
        assert float(h.get("score", 0.0)) >= 0.0
        assert h.get("chunk_id")
        if h.get("source_filename"):
            assert marker in str(h["source_filename"])


def test_e2e_search_penalty_query_retrieves_penalty_chunk(
    client: TestClient, retrieval_e2e_tenant: dict[str, str]
) -> None:
    """Intent-style query should surface the penalty line from the same upload."""
    headers = {
        "Authorization": f"Bearer {retrieval_e2e_tenant['token']}",
        "X-Workspace-Id": retrieval_e2e_tenant["ws"],
    }
    tag = uuid.uuid4().hex[:10]
    file_bytes = (
        f"Приложение к договору {tag}\n"
        "Поставщик обязуется отгрузить товар в срок.\n"
        "Неустойка за просрочку поставки составляет 0.05% за каждый календарный день.\n"
    ).encode()
    up = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": (f"penalty_{tag}.txt", file_bytes, "text/plain")},
    )
    assert up.status_code == 200, up.text
    document_id = up.json()["document"]["id"]

    search = client.post(
        "/api/v1/search",
        headers=headers,
        json={"query": "какая неустойка за просрочку поставки", "top_k": 5},
    )
    assert search.status_code == 200, search.text
    hits = search.json().get("hits") or []
    assert len(hits) >= 1
    assert any(str(h.get("document_id")) == str(document_id) for h in hits)
    joined = " ".join(str(h.get("text") or "").lower() for h in hits)
    assert "неустой" in joined or "0.05" in joined
