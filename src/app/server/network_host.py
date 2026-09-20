"""Network host parsing and private-address classification."""

from __future__ import annotations

import ipaddress
import socket

PRIVATE_HOSTS = {"localhost", "127.0.0.1", "::1"}


def is_private_host(value, resolver=socket.gethostbyname):
    host = (value or "").split(",", 1)[0].strip().lower()
    if host.startswith("["):
        host = host[1:].split("]", 1)[0]
    elif host.count(":") == 1:
        host = host.rsplit(":", 1)[0]
    if not host:
        return False
    if host in PRIVATE_HOSTS or host.endswith(".local") or host.endswith(".lan"):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        try:
            address = ipaddress.ip_address(resolver(host))
        except (OSError, ValueError):
            return False
    return bool(address.is_private or address.is_loopback or address.is_link_local)


__all__ = ["is_private_host"]
