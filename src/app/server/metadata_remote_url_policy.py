"""Validation for URLs supplied by metadata providers.

Provider search endpoints are application-owned, but artwork and secondary
lyrics URLs are returned by third parties. Keep those URLs out of local and
link-local address space before handing them to urllib.
"""

from __future__ import annotations

import ipaddress
import socket
import urllib.parse


MAX_METADATA_REMOTE_URL_LENGTH = 2048


def public_metadata_http_url(value, maximum=MAX_METADATA_REMOTE_URL_LENGTH):
    """Return a conservative HTTP(S) URL or an empty string when unsafe."""
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if not value or len(value) > maximum or any(ord(character) < 32 for character in value):
        return ""
    try:
        parsed = urllib.parse.urlsplit(value)
        port = parsed.port
    except (TypeError, ValueError):
        return ""
    if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
        return ""
    if parsed.username is not None or parsed.password is not None:
        return ""
    if port is not None and not 1 <= port <= 65535:
        return ""
    hostname = parsed.hostname.rstrip(".").lower()
    if not hostname or hostname == "localhost" or hostname.endswith(".localhost"):
        return ""
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        # A provider can return a harmless-looking hostname which resolves to
        # loopback, link-local, or RFC1918 space.  Checking only literal IPs
        # leaves that DNS-based SSRF path open.  Reject a hostname when any
        # currently-resolved address is non-global; unresolved names remain
        # allowed because provider domains may be absent from the local DNS
        # environment and urllib will report that failure without a request.
        try:
            port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
            rows = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
            addresses = {row[4][0] for row in rows if row and len(row) > 4 and row[4]}
        except (OSError, ValueError, TypeError):
            addresses = set()
        if any(not ipaddress.ip_address(item).is_global for item in addresses):
            return ""
        return value
    return value if address.is_global else ""


__all__ = ["MAX_METADATA_REMOTE_URL_LENGTH", "public_metadata_http_url"]
