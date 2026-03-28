"""Resolve client IP when behind a reverse proxy (trusted hops only)."""

from __future__ import annotations

import ipaddress
from functools import lru_cache

from fastapi import Request


@lru_cache(maxsize=1)
def _parse_trusted_networks(raw: str) -> tuple[ipaddress._BaseNetwork, ...]:
    nets: list[ipaddress._BaseNetwork] = []
    for part in (raw or "").split(","):
        p = part.strip()
        if not p:
            continue
        if "/" in p:
            nets.append(ipaddress.ip_network(p, strict=False))
        else:
            try:
                addr = ipaddress.ip_address(p)
            except ValueError:
                continue
            nets.append(ipaddress.ip_network((addr, addr.max_prefixlen)))
    return tuple(nets)


def _addr_in_trusted(ip: str, networks: tuple[ipaddress._BaseNetwork, ...]) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in n for n in networks)


def get_effective_client_ip(request: Request, *, use_forwarded_headers: bool, trusted_proxy_ips: str) -> str:
    """Return client IP: use X-Forwarded-For only when the immediate peer is a trusted proxy."""
    direct = (request.client.host if request.client else "") or "unknown"
    if not use_forwarded_headers or not (trusted_proxy_ips or "").strip():
        return direct
    nets = _parse_trusted_networks(trusted_proxy_ips)
    if not nets or not _addr_in_trusted(direct, nets):
        return direct
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if not xff:
        return direct
    parts = [p.strip() for p in xff.split(",") if p.strip()]
    if not parts:
        return direct
    return parts[0]
