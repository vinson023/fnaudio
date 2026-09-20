"""Pure, bounded extraction of HTTP context used by DLNA diagnostics."""

from __future__ import annotations

import ipaddress
from typing import Any


def request_context(headers: Any, client_address: Any) -> dict[str, str]:
    getter = getattr(headers, "get", None)
    if not callable(getter):
        getter = lambda key, default="": default
    def text(name: str) -> str:
        try:
            value = getter(name, "")
        except Exception:
            value = ""
        return value.strip()[:512] if isinstance(value, str) else ""
    try:
        address = client_address[0] if isinstance(client_address, (tuple, list)) and client_address else ""
    except (IndexError, TypeError, ValueError):
        address = ""
    if not isinstance(address, str):
        address = ""
    try:
        peer_is_loopback = ipaddress.ip_address(address).is_loopback
    except ValueError:
        peer_is_loopback = False
    forwarded = text("X-Forwarded-For") or text("X-Real-IP") if peer_is_loopback else ""
    if forwarded:
        forwarded = forwarded.split(",", 1)[0].strip()
    return {
        "client_ip": (forwarded or address)[:128],
        "user_agent": text("User-Agent")[:300],
        "range": text("Range")[:128],
        "accept": text("Accept")[:256],
    }


__all__ = ["request_context"]
