"""Small, testable TCP port probing helpers for application startup."""

from __future__ import annotations

import socket


def _port_number(value):
    """Return a valid TCP port without truncating or coercing booleans."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 1 <= value <= 65535 else None


def is_tcp_port_available(port, current_port=0, socket_factory=socket.socket):
    port = _port_number(port)
    current = _port_number(current_port)
    if port is None:
        return False
    if current is not None and port == current:
        return True
    probe = socket_factory(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("0.0.0.0", port))
        return True
    except OSError:
        return False
    finally:
        probe.close()


def find_free_tcp_port(socket_factory=socket.socket):
    sock = socket_factory(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("0.0.0.0", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


__all__ = ["find_free_tcp_port", "is_tcp_port_available"]
