"""Opt-in load/perf scenarios: parallel HTTP against ASGI (no separate server process).

Run from ``backend/``::

  RUN_PERF_TESTS=1 RUN_INTEGRATION_TESTS=1 pytest tests/test_perf_load.py -v

Cold rerank cache check needs only ``RUN_PERF_TESTS=1`` (mocked CrossEncoder).
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from unittest.mock import MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport

from app.core.config import settings
from app.main import app
from app.services import reranker

pytestmark = pytest.mark.perf

_SKIP_PERF = pytest.mark.skipif(
    os.environ.get("RUN_PERF_TESTS") != "1",
    reason="Set RUN_PERF_TESTS=1 for perf/load scenarios.",
)

_SKIP_PERF_DB = pytest.mark.skipif(
    os.environ.get("RUN_PERF_TESTS") != "1" or os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_PERF_TESTS=1 and RUN_INTEGRATION_TESTS=1 (PostgreSQL).",
)


def _api_base() -> str:
    return "http://test" + settings.api_v1_prefix


@_SKIP_PERF_DB
def test_parallel_document_uploads() -> None:
    """Many concurrent small uploads; all must succeed (sync ingest)."""

    async def _run() -> None:
        transport = ASGITransport(app=app, lifespan="on")
        async with httpx.AsyncClient(
            transport=transport, base_url=_api_base(), timeout=120.0
        ) as client:
            pwd = "PerfLoadUpload1!"
            email = f"perf_up_{uuid.uuid4().hex[:12]}@example.com"
            reg = await client.post(
                "/auth/register",
                json={"email": email, "password": pwd, "full_name": "Perf Upload"},
            )
            if reg.status_code == 503:
                pytest.skip("Database unavailable for perf test.")
            assert reg.status_code == 200, reg.text
            login = await client.post("/auth/login", json={"email": email, "password": pwd})
            assert login.status_code == 200, login.text
            token = login.json()["access_token"]
            wl = await client.get("/workspaces", headers={"Authorization": f"Bearer {token}"})
            assert wl.status_code == 200, wl.text
            ws_id = str(wl.json()[0]["id"])
            headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": ws_id}
            marker = uuid.uuid4().hex[:10]

            async def one_upload(i: int) -> int:
                body = f"perf parallel doc {marker} idx={i}\nunique line {uuid.uuid4().hex}\n".encode()
                r = await client.post(
                    "/documents/upload",
                    headers=headers,
                    files={"file": (f"p_{marker}_{i}.txt", body, "text/plain")},
                )
                return r.status_code

            n = 12
            codes = await asyncio.gather(*[one_upload(i) for i in range(n)])
            assert all(c == 200 for c in codes), codes

    asyncio.run(_run())


@_SKIP_PERF_DB
def test_bulk_search_parallel() -> None:
    """After one upload, many concurrent search requests must stay 2xx."""

    async def _run() -> None:
        transport = ASGITransport(app=app, lifespan="on")
        async with httpx.AsyncClient(
            transport=transport, base_url=_api_base(), timeout=120.0
        ) as client:
            pwd = "PerfLoadSearch1!"
            email = f"perf_se_{uuid.uuid4().hex[:12]}@example.com"
            reg = await client.post(
                "/auth/register",
                json={"email": email, "password": pwd, "full_name": "Perf Search"},
            )
            if reg.status_code == 503:
                pytest.skip("Database unavailable for perf test.")
            assert reg.status_code == 200, reg.text
            login = await client.post("/auth/login", json={"email": email, "password": pwd})
            assert login.status_code == 200, login.text
            token = login.json()["access_token"]
            wl = await client.get("/workspaces", headers={"Authorization": f"Bearer {token}"})
            assert wl.status_code == 200, wl.text
            ws_id = str(wl.json()[0]["id"])
            headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": ws_id}
            fact = uuid.uuid4().hex[:12]
            file_bytes = (
                f"Договор perf bulk {fact}\nЦена товара: 42 KZT за единицу.\n".encode()
            )
            up = await client.post(
                "/documents/upload",
                headers=headers,
                files={"file": (f"bulk_{fact}.txt", file_bytes, "text/plain")},
            )
            assert up.status_code == 200, up.text
            assert (up.json().get("chunks_created") or 0) > 0

            async def one_search(_i: int) -> tuple[int, float]:
                t0 = time.perf_counter()
                r = await client.post(
                    "/search",
                    headers=headers,
                    json={"query": f"какая цена в договоре {fact}", "top_k": 5},
                )
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                return r.status_code, elapsed_ms

            n = 24
            results = await asyncio.gather(*[one_search(i) for i in range(n)])
            codes = [c for c, _ in results]
            assert all(200 <= c < 300 for c in codes), codes
            latencies = [ms for _, ms in results]
            latencies.sort()
            p95 = latencies[int(0.95 * (len(latencies) - 1))]
            assert p95 < 120_000.0, "absurdly slow search (sanity ceiling, not an SLA)"

    asyncio.run(_run())


@_SKIP_PERF_DB
def test_long_chat_session_many_turns() -> None:
    """Repeated chat messages in one session (DB + retrieval path)."""

    async def _run() -> None:
        transport = ASGITransport(app=app, lifespan="on")
        async with httpx.AsyncClient(
            transport=transport, base_url=_api_base(), timeout=120.0
        ) as client:
            pwd = "PerfLoadChat1!"
            email = f"perf_ch_{uuid.uuid4().hex[:12]}@example.com"
            reg = await client.post(
                "/auth/register",
                json={"email": email, "password": pwd, "full_name": "Perf Chat"},
            )
            if reg.status_code == 503:
                pytest.skip("Database unavailable for perf test.")
            assert reg.status_code == 200, reg.text
            login = await client.post("/auth/login", json={"email": email, "password": pwd})
            assert login.status_code == 200, login.text
            token = login.json()["access_token"]
            wl = await client.get("/workspaces", headers={"Authorization": f"Bearer {token}"})
            assert wl.status_code == 200, wl.text
            ws_id = str(wl.json()[0]["id"])
            headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": ws_id}
            sess = await client.post("/chat/sessions", headers=headers, json={"title": "perf"})
            assert sess.status_code == 200, sess.text
            session_id = sess.json()["id"]

            for i in range(28):
                r = await client.post(
                    f"/chat/sessions/{session_id}/messages",
                    headers=headers,
                    json={"message": f"вопрос {i}: цена договора в тенге?", "top_k": 3},
                )
                assert r.status_code == 200, r.text

    asyncio.run(_run())


@_SKIP_PERF
@patch.object(settings, "reranker_enabled", True)
@patch.object(settings, "reranker_device", "cpu")
@patch.object(settings, "reranker_predict_timeout_seconds", 0.0)
def test_reranker_cross_encoder_loaded_once_per_cache_key() -> None:
    """Cold path loads model; second predict reuses lru_cache (no second CrossEncoder ctor)."""
    mock_model = MagicMock()
    mock_model.predict.return_value = [0.9, 0.1]

    reranker._load_cross_encoder.cache_clear()
    try:
        with patch("sentence_transformers.CrossEncoder", return_value=mock_model) as mock_ce:
            reranker.rerank_hits(
                "q1",
                [{"chunk_id": "c1", "text": "a"}, {"chunk_id": "c2", "text": "b"}],
                top_n=10,
            )
            reranker.rerank_hits(
                "q2",
                [{"chunk_id": "c1", "text": "a"}, {"chunk_id": "c2", "text": "b"}],
                top_n=10,
            )
        assert mock_ce.call_count == 1
        assert mock_model.predict.call_count == 2
    finally:
        reranker._load_cross_encoder.cache_clear()
