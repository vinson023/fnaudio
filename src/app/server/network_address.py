"""Small network-address helpers kept independent of HTTP handlers."""

from __future__ import annotations

import socket


def local_address(socket_factory=socket.socket):
    """Return the primary outbound IPv4 address, with a loopback fallback."""
    sock = socket_factory(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


__all__ = ["local_address"]
