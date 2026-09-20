"""Pure construction of the public CGI base URL."""

from __future__ import annotations

from urllib.parse import urlsplit

MAX_HOST_HEADER_CHARS = 512
MAX_PROTO_HEADER_CHARS = 32


def build_public_base_url(host_header="", forwarded_proto="http", *, local_address, is_private_host):
    # HTTP headers should already be text, but keeping this helper strict
    # prevents an unexpected object or oversized value from allocating a
    # representation before URL parsing.
    raw_host = host_header.strip()[:MAX_HOST_HEADER_CHARS] if isinstance(host_header, str) else ""
    raw_host = raw_host or "127.0.0.1:5666"
    parsed = urlsplit("//" + raw_host)
    hostname = parsed.hostname or "127.0.0.1"
    try:
        port = parsed.port
    except ValueError:
        port = None
    if port is None:
        port = 5666
    if not is_private_host(hostname):
        resolved = local_address()
        hostname = resolved.strip() if isinstance(resolved, str) and resolved.strip() else "127.0.0.1"
    # URL authorities require brackets around IPv6 literals.
    authority_host = "[%s]" % hostname if ":" in hostname and not hostname.startswith("[") else hostname
    proto = forwarded_proto.strip().lower()[:MAX_PROTO_HEADER_CHARS] if isinstance(forwarded_proto, str) else "http"
    if proto not in ("http", "https"):
        proto = "http"
    return "%s://%s:%d/cgi/ThirdParty/fnaudio/index.cgi" % (proto, authority_host, port)


__all__ = ["build_public_base_url"]
