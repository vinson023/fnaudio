"""Pure API route classification and scope policy.

This module intentionally contains no networking or authentication state.  It
normalizes request paths and maps them to the minimum API scope required by the
server.  Keeping the policy separate makes it possible to test authorization
decisions without constructing an HTTP handler.
"""

from __future__ import annotations


PUBLIC_API_PATHS = frozenset({"/api/health", "/api/access"})
PRIVATE_MEDIA_PREFIXES = ("/media/", "/cover/", "/metadata/artwork/")
PRIVILEGED_WRITE_SCOPES = frozenset({"settings.write", "files.manage"})


def normalize_path(path: str) -> str:
    """Return a bounded, query-free path suitable for policy matching."""
    if not isinstance(path, str):
        return ""
    value = path
    # Policy matching never needs an unbounded query or path value.  Keep the
    # same prefix semantics while preventing hostile objects/URLs from
    # expanding authorization work or diagnostics payloads.
    value = value.split("?", 1)[0]
    return value[:4096]


def requires_resource_auth(path: str) -> bool:
    return normalize_path(path).startswith(PRIVATE_MEDIA_PREFIXES)


def required_scope(method: str, path: str) -> str:
    method = method.upper() if isinstance(method, str) else "GET"
    path = normalize_path(path)
    if path in PUBLIC_API_PATHS:
        return ""
    if requires_resource_auth(path):
        return "library.read"
    if path == "/api/state/user":
        return "state.read" if method in ("GET", "HEAD") else "state.write"
    if path.startswith("/api/metadata/"):
        # Candidate/lyrics status is part of normal library presentation. Only
        # mutating metadata operations (refresh, apply, tag-write retry) need
        # settings permission; treating every metadata read as settings made
        # authenticated playback clients lose lyric/artwork enrichment.
        return "library.read" if method in ("GET", "HEAD") else "settings.write"
    if path.startswith("/api/config/"):
        return "settings.read" if method in ("GET", "HEAD") else "settings.write"
    if path.startswith("/api/fs/") or path == "/api/library/location":
        return "files.read" if method in ("GET", "HEAD") else "files.manage"
    if path.startswith(("/api/playback/", "/api/player/", "/api/upnp/", "/api/dac/", "/api/airplay/")):
        return "playback.read" if method in ("GET", "HEAD") else "playback.control"
    return "library.read" if method in ("GET", "HEAD") else "settings.write"
