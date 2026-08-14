from __future__ import annotations

import ipaddress
import socket
import urllib.request
from urllib.parse import urlparse

MAX_DLNA_XML_BYTES = 1024 * 1024


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def lan_http_url(value: str) -> str:
    """Validate a DLNA peer endpoint before the server makes an outbound request."""
    parsed = urlparse(str(value or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("DLNA endpoint must be an unauthenticated HTTP(S) URL")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise ValueError("DLNA endpoint has an invalid port") from exc
    if not 1 <= port <= 65535:
        raise ValueError("DLNA endpoint has an invalid port")
    try:
        addresses = {row[4][0] for row in socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise ValueError("DLNA endpoint host cannot be resolved") from exc
    if not addresses:
        raise ValueError("DLNA endpoint host cannot be resolved")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not (ip.is_private or ip.is_loopback or ip.is_link_local) or ip.is_multicast or ip.is_unspecified:
            raise ValueError("DLNA endpoint must resolve only to LAN addresses")
    return parsed.geturl()


def optional_lan_http_url(value: str) -> str:
    value = str(value or "").strip()
    return lan_http_url(value) if value else ""


def fetch_lan(request_or_url, timeout: float = 3, max_bytes: int = MAX_DLNA_XML_BYTES) -> bytes:
    url = request_or_url.full_url if isinstance(request_or_url, urllib.request.Request) else request_or_url
    lan_http_url(url)
    opener = urllib.request.build_opener(_NoRedirect())
    with opener.open(request_or_url, timeout=max(0.1, float(timeout))) as response:
        lan_http_url(response.geturl())
        length = response.headers.get("Content-Length")
        if length and int(length) > max_bytes:
            raise ValueError("DLNA response exceeds the size limit")
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise ValueError("DLNA response exceeds the size limit")
        return body
