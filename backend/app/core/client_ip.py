"""Trusted client IP resolution behind reverse proxies."""

from __future__ import annotations

from fastapi import Request

from app.core.config import settings


def _trusted_proxy_set() -> set[str]:
    raw = (settings.trusted_proxy_ips or "").strip()
    if not raw:
        return set()
    return {p.strip() for p in raw.split(",") if p.strip()}


def get_client_ip(request: Request) -> str:
    peer = (request.client.host if request.client else "") or ""
    if settings.use_forwarded_headers and peer in _trusted_proxy_set():
        xff = request.headers.get("x-forwarded-for") or ""
        if xff:
            return xff.split(",")[0].strip() or peer
    return peer or "unknown"
